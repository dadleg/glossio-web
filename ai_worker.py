#!/usr/bin/env python3
"""
AI Translation Worker

Background worker process that:
1. Connects to Redis queue
2. Loads the Gemma translation model
3. Processes translation jobs segment by segment
4. Updates database with AI suggestions
5. Publishes progress updates via Redis pub/sub

Usage:
    python ai_worker.py [--test]
"""

import os
import sys
import time
import signal
import argparse
from datetime import datetime

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///catapp.db')
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')

# Flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    global shutdown_requested
    print("\nShutdown signal received, finishing current job...")
    shutdown_requested = True


def setup_database():
    """Set up SQLAlchemy for standalone worker."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    return Session()


def process_job(job_data: dict, session, task_queue, gemma_service):
    """
    Process a single translation job.
    
    Args:
        job_data: Dict with job_id, project_id, segment_ids, target_lang
        session: SQLAlchemy session
        task_queue: TaskQueue instance for progress updates
        gemma_service: GemmaService instance
    """
    from app.models import AITranslationJob, AISuggestion, Segment
    
    job_id = job_data['job_id']
    segment_ids = job_data['segment_ids']
    target_lang = job_data.get('target_lang', 'ES')
    
    print(f"Processing job {job_id}: {len(segment_ids)} segments -> {target_lang}")
    
    # Update job status
    job = session.query(AITranslationJob).get(job_id)
    if not job:
        print(f"Job {job_id} not found in database")
        return
    
    job.status = 'running'
    job.started_at = datetime.utcnow()
    session.commit()
    
    total_time_ms = 0
    completed = 0
    
    try:
        for segment_id in segment_ids:
            if shutdown_requested:
                print("Shutdown requested, pausing job...")
                job.status = 'pending'  # Can be resumed
                session.commit()
                return
            
            # Get segment
            segment = session.query(Segment).get(segment_id)
            if not segment or not segment.source_text:
                completed += 1
                continue
            
            # Skip if already has a pending suggestion
            existing = session.query(AISuggestion).filter_by(
                segment_id=segment_id,
                status='pending'
            ).first()
            if existing:
                completed += 1
                continue
            
            # Translate
            time_ms = 0  # default in case of skip or error
            try:
                translation, time_ms = gemma_service.translate(
                    segment.source_text,
                    source_lang=job_data.get('source_lang', 'en'),
                    target_lang=target_lang
                )
                total_time_ms += time_ms
                
                # Create suggestion
                suggestion = AISuggestion(
                    segment_id=segment_id,
                    job_id=job_id,
                    suggested_text=translation,
                    status='pending',
                    translation_time_ms=time_ms
                )
                session.add(suggestion)
                
            except Exception as e:
                print(f"Error translating segment {segment_id}: {e}")
                # Continue with other segments
            
            completed += 1
            
            # Update job progress
            job.completed_segments = completed
            if completed > 0 and total_time_ms > 0:
                job.avg_time_per_segment = (total_time_ms / completed) / 1000
            session.commit()
            
            # Publish progress
            task_queue.publish_progress(
                job_id=job_id,
                completed=completed,
                total=len(segment_ids),
                segment_id=segment_id,
                status='running'
            )
            
            if time_ms > 0:
                print(f"  [{completed}/{len(segment_ids)}] Segment {segment_id}: {time_ms}ms")
            else:
                print(f"  [{completed}/{len(segment_ids)}] Segment {segment_id}: skipped")
        
        # Job completed
        job.status = 'completed'
        job.completed_at = datetime.utcnow()
        session.commit()
        
        task_queue.publish_progress(
            job_id=job_id,
            completed=completed,
            total=len(segment_ids),
            status='completed'
        )
        
        avg_time = (total_time_ms / completed) if completed > 0 else 0
        print(f"Job {job_id} completed: {completed} segments, avg {avg_time:.0f}ms/segment")
        
    except Exception as e:
        print(f"Job {job_id} failed: {e}")
        job.status = 'failed'
        job.error_message = str(e)
        job.completed_at = datetime.utcnow()
        session.commit()
        
        task_queue.publish_progress(
            job_id=job_id,
            completed=completed,
            total=len(segment_ids),
            status='failed'
        )


def run_worker():
    """Main worker loop."""
    global shutdown_requested
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 60)
    print("AI Translation Worker Starting")
    print(f"Database: {DATABASE_URL}")
    print(f"Redis: {REDIS_URL}")
    print("=" * 60)
    
    # Initialize services
    from app.services.task_queue import TaskQueue
    from app.services.gemma_service import GemmaService
    
    task_queue = TaskQueue(REDIS_URL)
    gemma_service = GemmaService()
    
    # Pre-load model
    print("\nLoading translation model...")
    gemma_service.initialize()
    print(f"Model ready: {gemma_service.device_info}")
    
    # Set up database
    session = setup_database()
    
    print("\nWorker ready, waiting for jobs...")
    
    while not shutdown_requested:
        try:
            # Wait for job with 5 second timeout
            job_data = task_queue.dequeue_job(timeout=5)
            
            if job_data:
                process_job(job_data, session, task_queue, gemma_service)
            
        except Exception as e:
            print(f"Worker error: {e}")
            time.sleep(1)  # Brief pause before retry
    
    print("\nWorker shutting down...")
    session.close()
    gemma_service.unload()


def run_test():
    """Quick test of the translation service."""
    from app.services.gemma_service import GemmaService
    
    print("Running translation test...")
    service = GemmaService()
    service.initialize()
    
    test_cases = [
        ("Hello, how are you?", "es"),
        ("The quick brown fox jumps over the lazy dog.", "es"),
        ("God so loved the world that He gave His only begotten Son.", "es"),
    ]
    
    print("\n" + "=" * 60)
    print("TRANSLATION TEST RESULTS")
    print("=" * 60)
    
    total_time = 0
    for source, lang in test_cases:
        translation, time_ms = service.translate(source, lang)
        total_time += time_ms
        print(f"\nSource: {source}")
        print(f"Target ({lang}): {translation}")
        print(f"Time: {time_ms}ms")
    
    avg_time = total_time / len(test_cases)
    print("\n" + "=" * 60)
    print(f"Average translation time: {avg_time:.0f}ms")
    print(f"Device: {service.device_info['device']}")
    print(f"Quantized: {service.device_info['quantized']}")
    print("=" * 60)
    
    # Estimate for document
    segments_per_doc = 500
    estimated_minutes = (avg_time * segments_per_doc) / 1000 / 60
    print(f"\nEstimated time for {segments_per_doc} segments: {estimated_minutes:.1f} minutes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Translation Worker")
    parser.add_argument('--test', action='store_true', help='Run translation test')
    args = parser.parse_args()
    
    if args.test:
        run_test()
    else:
        run_worker()

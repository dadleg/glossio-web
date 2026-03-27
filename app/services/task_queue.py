"""
Redis-based task queue for AI translation jobs.

This module provides functionality for:
- Enqueuing translation jobs
- Dequeuing jobs for processing
- Publishing/subscribing to progress updates
"""

import redis
import json
import os
from typing import Optional, List, Dict, Any

class TaskQueue:
    """Manages Redis-based job queue for AI translations."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.environ.get('REDIS_URL', 'redis://localhost:6379')
        self._redis = None
        self.queue_name = 'ai_translation_jobs'
        self.pubsub_channel = 'translation_progress'
    
    @property
    def redis(self):
        """Lazy connection to Redis."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis
    
    def enqueue_job(self, job_id: int, project_id: int, segment_ids: List[int], 
                    target_lang: str = 'ES') -> bool:
        """
        Add a translation job to the queue.
        
        Args:
            job_id: Database ID of the AITranslationJob
            project_id: Project being translated
            segment_ids: List of segment IDs to translate
            target_lang: Target language code
        
        Returns:
            True if successful
        """
        job_data = {
            'job_id': job_id,
            'project_id': project_id,
            'segment_ids': segment_ids,
            'target_lang': target_lang
        }
        self.redis.rpush(self.queue_name, json.dumps(job_data))
        return True
    
    def dequeue_job(self, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """
        Get the next job from the queue.
        
        Args:
            timeout: Seconds to wait for a job (0 = non-blocking)
        
        Returns:
            Job data dict or None if queue is empty
        """
        if timeout > 0:
            result = self.redis.blpop(self.queue_name, timeout=timeout)
            if result:
                return json.loads(result[1])
        else:
            result = self.redis.lpop(self.queue_name)
            if result:
                return json.loads(result)
        return None
    
    def publish_progress(self, job_id: int, completed: int, total: int, 
                         segment_id: Optional[int] = None,
                         status: str = 'running') -> None:
        """
        Publish progress update for subscribers.
        
        Args:
            job_id: The job being updated
            completed: Number of completed segments
            total: Total number of segments
            segment_id: The segment just completed (if any)
            status: Current job status
        """
        message = {
            'job_id': job_id,
            'completed': completed,
            'total': total,
            'progress_percent': int((completed / total) * 100) if total > 0 else 0,
            'segment_id': segment_id,
            'status': status
        }
        self.redis.publish(self.pubsub_channel, json.dumps(message))
    
    def subscribe_progress(self):
        """
        Subscribe to progress updates.
        
        Returns:
            Redis pubsub object for listening to updates
        """
        pubsub = self.redis.pubsub()
        pubsub.subscribe(self.pubsub_channel)
        return pubsub
    
    def get_queue_length(self) -> int:
        """Get the number of pending jobs in the queue."""
        return self.redis.llen(self.queue_name)
    
    def cancel_job(self, job_id: int) -> bool:
        """
        Attempt to remove a job from the queue before it starts.
        Note: This won't stop a job that's already being processed.
        
        Returns:
            True if job was found and removed
        """
        # Get all items, filter out the job, and replace queue
        all_jobs = self.redis.lrange(self.queue_name, 0, -1)
        found = False
        
        pipeline = self.redis.pipeline()
        pipeline.delete(self.queue_name)
        
        for job_str in all_jobs:
            job_data = json.loads(job_str)
            if job_data.get('job_id') == job_id:
                found = True
                continue  # Skip this one
            pipeline.rpush(self.queue_name, job_str)
        
        pipeline.execute()
        return found


# Singleton instance for the application
_task_queue = None

def get_task_queue() -> TaskQueue:
    """Get the global task queue instance."""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
    return _task_queue

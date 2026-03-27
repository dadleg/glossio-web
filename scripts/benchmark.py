"""
Benchmark script for Gemma AI Translation.

Measures translation performance and estimates document completion times.
Usage: python scripts/benchmark.py [--segments 50] [--output benchmark.json]
"""

import sys
import os
import time
import argparse
import json
import statistics
from datetime import timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.gemma_service import GemmaService

# Sample texts (mixed lengths)
SAMPLE_TEXTS = [
    "Hello, how are you today?",
    "The integration of artificial intelligence in daily workflows significantly enhances productivity.",
    "Sustainable development goals aim to address global challenges including poverty, inequality, climate change, environmental degradation, peace and justice.",
    "Short segment.",
    "In the beginning God created the heaven and the earth.",
    "This is a technical document describing the architecture of a distributed system using microservices and containerization technologies.",
    "Please translate this sentence accurately.",
    "The quick brown fox jumps over the lazy dog.",
    "Data analysis revealed a strong correlation between variable X and variable Y, suggesting a causal relationship.",
    "Thank you for your business."
]

def run_benchmark(num_segments=10, output_file=None):
    print("=" * 60)
    print(f"Starting Gemma Translation Benchmark ({num_segments} segments)")
    print("=" * 60)
    
    # Initialize service
    print("Initializing model (this may take time)...")
    service = GemmaService()
    service.initialize()
    print(f"Device Info: {service.device_info}")
    
    times = []
    results = []
    
    print("\nRunning translations...")
    for i in range(num_segments):
        # Cycle through sample texts
        text = SAMPLE_TEXTS[i % len(SAMPLE_TEXTS)]
        
        print(f"[{i+1}/{num_segments}] Translating ({len(text)} chars)... ", end="", flush=True)
        
        translation, time_ms = service.translate(text, "es")
        times.append(time_ms)
        
        results.append({
            "id": i+1,
            "source_len": len(text),
            "target_len": len(translation),
            "time_ms": time_ms
        })
        
        print(f"{time_ms}ms")
    
    # Calculate stats
    avg_time = statistics.mean(times)
    min_time = min(times)
    max_time = max(times)
    p95 = sorted(times)[int(len(times) * 0.95)] if len(times) >= 20 else max_time
    
    stats = {
        "total_segments": num_segments,
        "total_time_ms": sum(times),
        "avg_time_ms": avg_time,
        "min_time_ms": min_time,
        "max_time_ms": max_time,
        "p95_time_ms": p95,
        "device_info": service.device_info,
        "estimates": {
            "1_page_doc_50_segs": f"{timedelta(milliseconds=avg_time * 50)}",
            "10_page_doc_500_segs": f"{timedelta(milliseconds=avg_time * 500)}",
            "large_doc_2000_segs": f"{timedelta(milliseconds=avg_time * 2000)}"
        }
    }
    
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Device: {stats['device_info']['device']} (Quantized: {stats['device_info']['quantized']})")
    print(f"Average time per segment: {avg_time:.0f} ms")
    print(f"p95 time: {p95} ms")
    print("-" * 30)
    print(f"Est. 1 page document (50 segs):  {stats['estimates']['1_page_doc_50_segs']}")
    print(f"Est. 10 page document (500 segs): {stats['estimates']['10_page_doc_500_segs']}")
    print("=" * 60)
    
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(stats, f, indent=2)
        print(f"Results saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--segments", type=int, default=10, help="Number of segments to test")
    parser.add_argument("--output", help="Output JSON file for results")
    args = parser.parse_args()
    
    run_benchmark(args.segments, args.output)

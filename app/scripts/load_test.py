import asyncio
import time
import random
import json
import os
import httpx
import numpy as np
from typing import List, Dict, Any

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

async def simulate_user(client: httpx.AsyncClient, user_id: int, num_requests: int) -> List[float]:
    """Simulates a single user making sequential recommendation requests."""
    latencies = []
    for _ in range(num_requests):
        start = time.time()
        try:
            # Randomly select number of recommendations between 3 and 10
            n = random.randint(3, 10)
            response = await client.get(f"{API_URL}/recommendations?user_id={user_id}&n={n}")
            latency = (time.time() - start) * 1000.0  # in ms
            
            if response.status_code == 200:
                latencies.append(latency)
            else:
                # Append negative value to signify error code
                latencies.append(-response.status_code)
        except Exception as e:
            # Connection error or timeout
            latencies.append(-1.0)
            
        # Simulate thinking time (50ms - 150ms)
        await asyncio.sleep(random.uniform(0.05, 0.15))
        
    return latencies

async def run_load_test(num_concurrent_users: int = 10, requests_per_user: int = 20) -> Dict[str, Any]:
    """Runs the concurrent load test using asyncio."""
    # We will query the DB or guess user IDs 1 to 10
    # Our seed script created users with IDs 1 to 12. So we can use user_ids 1 to 10.
    user_ids = list(range(1, 11))
    
    limits = httpx.Limits(max_keepalive_connections=num_concurrent_users, max_connections=num_concurrent_users * 2)
    timeout = httpx.Timeout(10.0, connect=5.0)
    
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        start_time = time.time()
        
        # Create user tasks
        tasks = []
        for i in range(num_concurrent_users):
            # Map task to a user ID
            uid = user_ids[i % len(user_ids)]
            tasks.append(simulate_user(client, user_id=uid, num_requests=requests_per_user))
            
        # Gather all user latencies
        results = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
    # Flatten latencies
    all_latencies = [lat for user_recs in results for lat in user_recs]
    
    successful_latencies = [lat for lat in all_latencies if lat > 0]
    errors = [lat for lat in all_latencies if lat <= 0]
    
    total_reqs = len(all_latencies)
    success_count = len(successful_latencies)
    error_count = len(errors)
    
    # Calculate performance statistics
    avg_latency = float(np.mean(successful_latencies)) if successful_latencies else 0.0
    p50_latency = float(np.percentile(successful_latencies, 50)) if successful_latencies else 0.0
    p95_latency = float(np.percentile(successful_latencies, 95)) if successful_latencies else 0.0
    p99_latency = float(np.percentile(successful_latencies, 99)) if successful_latencies else 0.0
    min_latency = float(np.min(successful_latencies)) if successful_latencies else 0.0
    max_latency = float(np.max(successful_latencies)) if successful_latencies else 0.0
    
    throughput = success_count / total_time if total_time > 0 else 0.0
    
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "concurrent_users": num_concurrent_users,
        "total_requests": total_reqs,
        "successful_requests": success_count,
        "failed_requests": error_count,
        "total_duration_sec": round(total_time, 2),
        "throughput_req_per_sec": round(throughput, 2),
        "latency": {
            "avg_ms": round(avg_latency, 2),
            "p50_ms": round(p50_ms := p50_latency, 2),
            "p95_ms": round(p95_ms := p95_latency, 2),
            "p99_ms": round(p99_ms := p99_latency, 2),
            "min_ms": round(min_latency, 2),
            "max_ms": round(max_latency, 2)
        },
        "all_successful_latencies": successful_latencies
    }
    
    return report

def main():
    print(f"Starting load test on {API_URL}...")
    print("Simulating 10 concurrent users, 20 requests each (total 200 requests)...")
    
    try:
        report = asyncio.run(run_load_test(num_concurrent_users=10, requests_per_user=20))
        
        # Save to file
        report_path = "load_test_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
            
        print("\n--- Load Test Performance Report ---")
        print(f"Timestamp: {report['timestamp']}")
        print(f"Concurrent Users: {report['concurrent_users']}")
        print(f"Total Requests: {report['total_requests']}")
        print(f"Success Rate: {report['successful_requests']}/{report['total_requests']} ({report['successful_requests']/report['total_requests']*100:.1f}%)")
        print(f"Throughput: {report['throughput_req_per_sec']} req/sec")
        print(f"Latency Avg: {report['latency']['avg_ms']} ms")
        print(f"Latency P95: {report['latency']['p95_ms']} ms")
        print(f"Latency P99: {report['latency']['p99_ms']} ms")
        print(f"Report saved to {os.path.abspath(report_path)}")
        
    except Exception as e:
        print(f"Failed to execute load test: {e}")
        # Create an error report
        err_report = {
            "error": str(e),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "failed"
        }
        with open("load_test_report.json", "w") as f:
            json.dump(err_report, f, indent=2)

if __name__ == "__main__":
    main()

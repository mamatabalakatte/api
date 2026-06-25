import subprocess
import sys
import time
import os
import signal

def run():
    print("==================================================")
    print("      GenAI Recommendation System Launcher        ")
    print("==================================================")

    # Resolve paths relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Start FastAPI Backend
    print("Starting FastAPI Backend (http://127.0.0.1:8000)...")
    backend_cmd = [
        sys.executable, "-m", "uvicorn", "app.api.main:app", 
        "--host", "127.0.0.1", "--port", "8000"
    ]
    
    backend_process = subprocess.Popen(
        backend_cmd,
        cwd=script_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Wait for the backend to start up (read its output until it shows startup lines)
    backend_started = False
    start_wait = time.time()
    while time.time() - start_wait < 10:
        # Check if process died
        if backend_process.poll() is not None:
            break
            
        line = backend_process.stdout.readline()
        if not line:
            time.sleep(0.1)
            continue
        print(f"[Backend] {line.strip()}")
        if "Application startup complete" in line:
            backend_started = True
            break
            
    if not backend_started:
        print("Error: FastAPI backend failed to start.")
        if backend_process.poll() is not None:
            out, _ = backend_process.communicate()
            print(out)
        sys.exit(1)

    # 2. Start Streamlit Frontend
    print("Starting Streamlit Dashboard (http://127.0.0.1:8501)...")
    frontend_cmd = [
        sys.executable, "-m", "streamlit", "run", "ui/dashboard.py",
        "--server.port", "8501", "--server.address", "127.0.0.1"
    ]
    
    frontend_process = subprocess.Popen(
        frontend_cmd,
        cwd=script_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    print("\nSystem running! Press Ctrl+C to terminate both servers.")
    print("Backend API docs: http://127.0.0.1:8000/docs")
    print("Dashboard App:    http://127.0.0.1:8501")
    print("==================================================\n")

    # Function to stream process outputs in a non-blocking thread
    import threading
    def stream_output(process, prefix):
        try:
            for line in iter(process.stdout.readline, ''):
                if line:
                    print(f"[{prefix}] {line.strip()}")
        except Exception:
            pass

    # Start output streaming threads
    t1 = threading.Thread(target=stream_output, args=(backend_process, "Backend"), daemon=True)
    t2 = threading.Thread(target=stream_output, args=(frontend_process, "Dashboard"), daemon=True)
    t1.start()
    t2.start()

    try:
        # Keep launcher running
        while True:
            # Check if either process has exited
            if backend_process.poll() is not None:
                print("FastAPI backend exited unexpectedly.")
                break
            if frontend_process.poll() is not None:
                print("Streamlit dashboard exited unexpectedly.")
                break
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutdown signal received. Stopping servers...")
    finally:
        # Terminate processes
        for proc, name in [(backend_process, "Backend"), (frontend_process, "Dashboard")]:
            if proc.poll() is None:
                print(f"Terminating {name}...")
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    print(f"Force killing {name}...")
                    proc.kill()
        print("Cleanup complete. Goodbye!")

if __name__ == "__main__":
    run()

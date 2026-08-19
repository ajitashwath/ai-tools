#!/usr/bin/env python3
import subprocess
import sys
import time
import atexit

# Start uvicorn server
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "aidev.server:app", "--host", "0.0.0.0", "--port", "18003"],
    cwd="E:/ai-tools",
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

# Wait for startup
time.sleep(3)

# Register cleanup on exit
atexit.register(lambda: proc.terminate())

# Check if process is still running
if proc.poll() is not None:
    print("Server failed to start")
    stderr = proc.stderr.read().decode()
    print(f"Stderr: {stderr[:500]}")
else:
    print(f"Server running on port 18003 (PID: {proc.pid})")
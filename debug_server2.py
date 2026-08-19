import subprocess
import sys
import time
import urllib.request
import json

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "aidev.server:app", "--host", "0.0.0.0", "--port", "8000"],
    cwd="E:/ai-tools",
    stdout=open("server_stdout2.txt", "w"),
    stderr=open("server_stderr2.txt", "w"),
)

time.sleep(3)

print("Process PID:", proc.pid)
print("Still running:", proc.poll() is None)

# Test API
try:
    req = urllib.request.Request("http://localhost:8000/api/spans")
    resp = urllib.request.urlopen(req, timeout=3)
    data = json.loads(resp.read())
    print("API test passed! Spans:", data)
except Exception as e:
    print("API test failed:", e)
    with open("server_stderr2.txt") as f:
        print("Stderr:", f.read())

proc.terminate()
proc.wait()
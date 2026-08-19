import subprocess
import time
import urllib.request
import json
import sys

# Start the server
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "aidev.server:app", "--host", "0.0.0.0", "--port", "8000"],
    cwd="E:/ai-tools",
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

# Wait for it to start
time.sleep(3)

try:
    # Test the API
    req = urllib.request.Request("http://localhost:8000/api/spans")
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    print("API test passed!")
    print(f"Spans: {data}")
except Exception as e:
    print(f"API test failed: {e}")
    print(f"Server stderr: {proc.stderr.read().decode()}")
finally:
    proc.terminate()
    proc.wait()
import subprocess
import sys
import time
import urllib.request
import json

# Start server in background
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "aidev.server:app", "--host", "0.0.0.0", "--port", "9001"],
    cwd="E:/ai-tools",
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

# Wait for startup
time.sleep(3)

# Test if server is running
try:
    req = urllib.request.Request("http://localhost:9001/api/spans")
    resp = urllib.request.urlopen(req, timeout=3)
    data = json.loads(resp.read())
    print("API OK:", data)
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code)
    body = e.read().decode()
    print("Body:", body[:500])
except Exception as e:
    print("Error:", type(e).__name__, e)

# Terminate server
proc.terminate()
proc.wait()
print("Done")
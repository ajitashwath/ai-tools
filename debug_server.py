import subprocess
import sys

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "aidev.server:app", "--host", "0.0.0.0", "--port", "8001"],
    cwd="E:/ai-tools",
    stdout=open("server_stdout.txt", "w"),
    stderr=open("server_stderr.txt", "w"),
)

import time
time.sleep(3)

print("Process PID:", proc.pid)
print("Still running:", proc.poll() is None)

# Read stderr
with open("server_stderr.txt") as f:
    print("STDERR:", f.read())

proc.terminate()
proc.wait()
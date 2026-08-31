import subprocess
import sys
import time

proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'aidev.server:app', '--host', '0.0.0.0', '--port', '8003'],
    cwd='E:/ai-tools',
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

time.sleep(3)

# Read output
time.sleep(1)
out = proc.stdout.read().decode()
err = proc.stderr.read().decode()
print('STDOUT:', out[-500:])
print('STDERR:', err[-500:])

proc.terminate()
proc.wait()

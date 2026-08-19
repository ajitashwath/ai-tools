import subprocess, sys, time

proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'aidev.server:app', '--host', '0.0.0.0', '--port', '18006'],
    cwd='E:/ai-tools',
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
time.sleep(3)
out = proc.stdout.read().decode()
err = proc.stderr.read().decode()
print('STDOUT:', out[-300:])
print('STDERR:', err[-300:])
proc.terminate()
proc.wait()
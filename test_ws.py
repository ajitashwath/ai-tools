#!/usr/bin/env python3
import subprocess, sys, time, os
import urllib.request
import json
import websockets
import asyncio

# Start server
proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'aidev.server:app', '--host', '0.0.0.0', '--port', '18005'],
    cwd='E:/ai-tools',
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

# Wait for startup
time.sleep(3)

# Check if process is alive
if proc.poll() is not None:
    print("Server failed to start")
    stderr = proc.stderr.read().decode()
    print("Stderr:", stderr[:500])
    proc.wait()
    sys.exit(1)

print(f"Server started (PID: {proc.pid})")

# Test 1: REST API
print("\n--- Test 1: REST API ---")
try:
    req = urllib.request.Request("http://localhost:18005/api/spans")
    resp = urllib.request.urlopen(req, timeout=3)
    data = json.loads(resp.read())
    print(f"REST API OK: {len(data)} spans")
except urllib.error.HTTPError as e:
    print(f"REST API HTTP Error: {e.code}")
    body = e.read().decode()
    print(f"Body: {body[:200]}")
except Exception as e:
    print(f"REST API error: {type(e).__name__}: {e}")

# Test 2: WebSocket
print("\n--- Test 2: WebSocket ---")

async def test_ws():
    try:
        async with websockets.connect("ws://localhost:18005/ws") as ws:
            # Send get_spans message
            await ws.send("get_spans")
            # Receive response with timeout
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=3.0)
                data = json.loads(response)
                print(f"WebSocket OK: type={data.get('type')}, spans={len(data.get('spans', []))}")
            except asyncio.TimeoutError:
                print("WebSocket: receive timed out (may be ok if no data sent)")
    except Exception as e:
        print(f"WebSocket error: {type(e).__name__}: {e}")

asyncio.run(test_ws())

# Terminate server
proc.terminate()
proc.wait()
print("\nAll tests done!")
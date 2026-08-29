import asyncio
import websockets
import subprocess
import os
import json
import threading
import queue
import psutil
import socket
from zeroconf.asyncio import AsyncZeroconf
from zeroconf import ServiceInfo
from dotenv import load_dotenv

load_dotenv()

# Configuration
PORT = 8888
PASSWORD = os.getenv("TERMINAL_PASSWORD", "11606")
NODE_NAME = socket.gethostname()

class RemoteSession:
    def __init__(self):
        self.proc = subprocess.Popen(
            ['powershell.exe', '-NoExit', '-Command', '-'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        self.out_queue = queue.Queue()
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self):
        def stream_reader(pipe, q):
            for line in iter(pipe.readline, ""):
                q.put(line)

        threading.Thread(target=stream_reader, args=(self.proc.stdout, self.out_queue), daemon=True).start()
        threading.Thread(target=stream_reader, args=(self.proc.stderr, self.out_queue), daemon=True).start()

    def execute(self, cmd):
        if self.proc.poll() is None:
            self.proc.stdin.write(cmd + "\n")
            self.proc.stdin.flush()

    def get_output(self):
        lines = []
        while not self.out_queue.empty():
            lines.append(self.out_queue.get())
        return "".join(lines)

session = RemoteSession()

async def telemetry_pusher(websocket):
    """Pushes system stats periodically."""
    while True:
        try:
            cwd = os.getcwd()
            try:
                p = psutil.Process(session.proc.pid)
                cwd = p.cwd()
            except:
                pass
            stats = {
                "type": "telemetry",
                "payload": {
                    "cpu": psutil.cpu_percent(),
                    "ram": psutil.virtual_memory().percent,
                    "disk": psutil.disk_usage('/').percent,
                    "cwd": cwd
                }
            }
            await websocket.send(json.dumps(stats))
            await asyncio.sleep(2)
        except websockets.ConnectionClosed:
            break

async def output_pusher(websocket):
    """Continuously pushes new output to the client."""
    while True:
        try:
            output = session.get_output()
            if output:
                await websocket.send(json.dumps({"type": "output", "payload": output}))
            await asyncio.sleep(0.1)
        except websockets.ConnectionClosed:
            break

async def handler(websocket):
    print(f"New connection from {websocket.remote_address}")
    authenticated = False

    output_task = asyncio.create_task(output_pusher(websocket))
    telemetry_task = asyncio.create_task(telemetry_pusher(websocket))

    try:
        async for message in websocket:
            data = json.loads(message)

            if not authenticated:
                if data.get("password") == PASSWORD:
                    authenticated = True
                    await websocket.send(json.dumps({"type": "auth", "status": "success"}))
                    continue
                else:
                    await websocket.send(json.dumps({"type": "auth", "status": "fail"}))
                    await websocket.close()
                    break

            if data.get("type") == "command":
                cmd = data.get("payload")
                session.execute(cmd)

    except websockets.ConnectionClosed:
        print("Connection closed")
    finally:
        output_task.cancel()
        telemetry_task.cancel()

async def main():
    local_ip = socket.gethostbyname(socket.gethostname())
    info = ServiceInfo(
        "_pilot._tcp.local.",
        f"{NODE_NAME}._pilot._tcp.local.",
        addresses=[socket.inet_aton(local_ip)],
        port=PORT,
        properties={'node_name': NODE_NAME}
    )

    aiozc = AsyncZeroconf()
    await aiozc.zeroconf.async_register_service(info)

    print(f"Pilot Agent '{NODE_NAME}' registered at {local_ip}:{PORT}")
    print(f"Listening on port {PORT}...")

    try:
        async with websockets.serve(handler, "0.0.0.0", PORT):
            await asyncio.Future()
    finally:
        await aiozc.zeroconf.async_unregister_all_services()
        await aiozc.async_close()

if __name__ == "__main__":
    asyncio.run(main())

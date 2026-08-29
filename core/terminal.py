import subprocess
import threading
import queue
import os
import json
import websocket
import time
import psutil
import socket
from functools import lru_cache
from zeroconf import ServiceBrowser, Zeroconf

class BaseTerminal:
    def __init__(self):
        self.telemetry = {"cpu": 0, "ram": 0, "disk": 0}
    def execute(self, command):
        raise NotImplementedError
    def get_new_output(self):
        raise NotImplementedError
    def get_telemetry(self):
        return self.telemetry

class LocalTerminal(BaseTerminal):
    def __init__(self):
        super().__init__()
        shell_command = "powershell.exe" if os.name == "nt" else "bash"
        self.proc = subprocess.Popen(
            [shell_command] if os.name != "nt" else [shell_command, '-NoExit', '-Command', '-'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        self.out_queue = queue.Queue()
        threading.Thread(target=self._read_output, name="LocalTerminalRead", daemon=True).start()
        threading.Thread(target=self._update_telemetry, daemon=True).start()

    def _read_output(self):
        try:
            for line in iter(self.proc.stdout.readline, ""):
                self.out_queue.put(line)
        except Exception:
            pass

    def _update_telemetry(self):
        while True:
            self.telemetry = {
                "cpu": psutil.cpu_percent(),
                "ram": psutil.virtual_memory().percent,
                "disk": psutil.disk_usage('/').percent
            }
            time.sleep(2)

    def execute(self, command):
        if self.proc.poll() is None:
            self.proc.stdin.write(command + "\n")
            self.proc.stdin.flush()

    def get_new_output(self):
        lines = []
        while not self.out_queue.empty():
            lines.append(self.out_queue.get())
        return "".join(lines)

class RemoteTerminal(BaseTerminal):
    def __init__(self, host, port, password):
        super().__init__()
        self.url = f"ws://{host}:{port}"
        self.password = password
        self.out_queue = queue.Queue()
        self.ws = None
        self.connected = False
        threading.Thread(target=self._connect_loop, daemon=True).start()

    def _connect_loop(self):
        while True:
            try:
                self.ws = websocket.create_connection(self.url, timeout=5)
                self.ws.send(json.dumps({"password": self.password}))
                resp = json.loads(self.ws.recv())
                if resp.get("status") == "success":
                    self.connected = True
                    while self.connected:
                        msg = self.ws.recv()
                        data = json.loads(msg)
                        if data.get("type") == "output":
                            self.out_queue.put(data.get("payload"))
                        elif data.get("type") == "telemetry":
                            self.telemetry = data.get("payload")
                else:
                    self.connected = False
            except Exception:
                self.connected = False
                time.sleep(5)

    def execute(self, command):
        if self.connected and self.ws:
            try:
                self.ws.send(json.dumps({"type": "command", "payload": command}))
            except:
                self.connected = False

    def get_new_output(self):
        lines = []
        while not self.out_queue.empty():
            lines.append(self.out_queue.get())
        return "".join(lines)

class DiscoveryWorker:
    def __init__(self, node_manager):
        self.node_manager = node_manager
        self.zeroconf = Zeroconf()
        self.browser = ServiceBrowser(self.zeroconf, "_pilot._tcp.local.", self)

    def remove_service(self, zeroconf, type, name):
        # Could handle removal if needed
        pass

    def update_service(self, zeroconf, type, name):
        """Required by newer zeroconf versions."""
        pass

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            addresses = [socket.inet_ntoa(addr) for addr in info.addresses]
            if addresses:
                host = addresses[0]
                port = info.port
                node_name = info.properties.get(b'node_name', b'Unknown').decode('utf-8')
                # Avoid adding self or duplicates
                if node_name != socket.gethostname() and node_name not in self.node_manager.nodes:
                    print(f"Discovered new node: {node_name} at {host}:{port}")
                    self.node_manager.add_remote_node(node_name, host, port)

class NodeManager:
    def __init__(self):
        self.nodes = {
            "Local Machine": LocalTerminal()
        }
        self.active_node_name = "Local Machine"
        self.password = os.getenv("TERMINAL_PASSWORD", "11606")
        # Start background discovery
        self.discovery = DiscoveryWorker(self)

    def get_active_node(self) -> BaseTerminal:
        return self.nodes[self.active_node_name]

    def broadcast(self, command):
        for node in self.nodes.values():
            node.execute(command)

    def add_remote_node(self, name, host, port=8888):
        if name not in self.nodes:
            self.nodes[name] = RemoteTerminal(host, port, self.password)

    def list_nodes(self):
        return list(self.nodes.keys())

@lru_cache(maxsize=1)
def get_node_manager():
    return NodeManager()

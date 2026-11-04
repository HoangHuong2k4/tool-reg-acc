"""Loopback-only authenticated HTTP publish + WebSocket fan-out, no dependencies."""
import base64
from collections import deque
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import queue
import re
import secrets
import select
import socket
import struct
import threading
import time
import uuid

from configure import configure

MAX_AGE_MS = 120000
MAX_BODY = 4096
CODE_PATTERN = re.compile(r"[A-Za-z0-9_-]{6,128}\Z")
ORIGIN_PATTERN = re.compile(r"chrome-extension://[a-p]{32}\Z")


def now_ms():
    return int(time.time() * 1000)


class Hub:
    def __init__(self, token):
        self.token = token
        self.epoch = str(uuid.uuid4())
        self.sequence = 0
        self.events = deque(maxlen=500)
        self.clients = {}
        self.reports = deque(maxlen=50)
        self.probes = {}
        self.lock = threading.Lock()

    def authenticate(self, value):
        return isinstance(value, str) and secrets.compare_digest(value, self.token)

    def status(self):
        with self.lock:
            return {"success": True, "service": "grok-local-relay", "version": 1,
                    "receivers": len(self.clients), "sequence": self.sequence, "epoch": self.epoch,
                    "lastCode": self.events[-1]["code"] if self.events else None, "reports": list(self.reports)}

    def begin_probe(self):
        probe_id = str(uuid.uuid4())
        with self.lock:
            self.probes = {probe_id: {}}
            for client in self.clients.values():
                try:
                    client.put_nowait({"type": "probe", "probeId": probe_id})
                except queue.Full:
                    client.overflow = True
        return probe_id

    def report(self, client_key, raw):
        if not isinstance(raw, dict):
            return
        with self.lock:
            if raw.get("type") == "probe_result" and raw.get("probeId") in self.probes:
                self.probes[raw["probeId"]][client_key] = {"clientId": client_key[:8], "ready": raw.get("ready") is True, "note": str(raw.get("note", ""))[:250]}
            elif raw.get("type") == "result" and raw.get("epoch") == self.epoch:
                event = next((item for item in self.events if item["sequence"] == raw.get("sequence")), None)
                if event and raw.get("status") in ("opened", "failed", "duplicate"):
                    self.reports.appendleft({"clientId": client_key[:8], "code": event["code"], "status": raw["status"], "timestamp": now_ms(), "error": str(raw.get("error", ""))[:250]})
                    print(f'Receiver {client_key[:8]}: {raw["status"]} (sequence {event["sequence"]})', flush=True)

    def publish(self, raw):
        code, timestamp, event_id = raw.get("code"), raw.get("timestamp"), raw.get("eventId")
        if not isinstance(code, str) or not CODE_PATTERN.fullmatch(code):
            raise ValueError("Invalid referral code")
        if type(timestamp) not in (int, float) or not now_ms() - MAX_AGE_MS <= timestamp <= now_ms() + 30000:
            raise ValueError("Code is older than 2 minutes or has an invalid timestamp")
        if not isinstance(event_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", event_id):
            raise ValueError("Invalid event ID")
        with self.lock:
            # Same event retried after an HTTP timeout must not be broadcast again.
            for previous in self.events:
                if previous["eventId"] == event_id or (raw.get("retry") is not True and raw.get("force") is not True and previous["code"] == code and now_ms() - previous["timestamp"] <= 15000):
                    return {"success": True, "duplicate": True, "receivers": len(self.clients), "sequence": previous["sequence"]}
            self.sequence += 1
            event = {"type": "code", "version": 1, "epoch": self.epoch, "sequence": self.sequence,
                     "eventId": event_id, "code": code, "timestamp": timestamp, "retry": raw.get("retry") is True}
            self.events.append(event)
            print(f'Code detected: {code} -> {len(self.clients)} Receiver(s)', flush=True)
            for client in list(self.clients.values()):
                try:
                    client.put_nowait(event)
                except queue.Full:
                    # Slow clients reconnect and resume from their saved cursor.
                    client.overflow = True
            return {"success": True, "receivers": len(self.clients), "sequence": self.sequence}

    def subscribe(self, raw):
        if not self.authenticate(raw.get("token")):
            raise ValueError("Wrong installation key; use files from the same package")
        since = raw.get("since")
        after = raw.get("after", 0)
        if type(since) not in (int, float) or since > now_ms() + 30000:
            raise ValueError("Invalid subscription start time")
        if type(after) is not int or after < 0:
            raise ValueError("Invalid cursor")
        client_key, messages = str(uuid.uuid4()), queue.Queue(maxsize=512)
        with self.lock:
            resume = raw.get("epoch") == self.epoch
            messages.put_nowait({"type": "hello", "version": 1, "epoch": self.epoch, "sequence": self.sequence, "clientId": client_key[:8]})
            for event in self.events:
                if event["timestamp"] < since or now_ms() - event["timestamp"] > MAX_AGE_MS:
                    continue
                if not resume or event["sequence"] > after:
                    messages.put_nowait(event)
            self.clients[client_key] = messages
            print(f'Receiver {client_key[:8]} connected; total {len(self.clients)}', flush=True)
        return client_key, messages

    def unsubscribe(self, key):
        with self.lock:
            self.clients.pop(key, None)
            print(f'Receiver {key[:8]} disconnected; total {len(self.clients)}', flush=True)


def websocket_frame(payload, opcode=1):
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    length = len(payload)
    header = bytes([0x80 | opcode])
    if length < 126:
        return header + bytes([length]) + payload
    if length < 65536:
        return header + b"\x7e" + struct.pack("!H", length) + payload
    return header + b"\x7f" + struct.pack("!Q", length) + payload


def read_exact(stream, count):
    parts = bytearray()
    while len(parts) < count:
        value = stream.read(count - len(parts))
        if not value:
            raise ConnectionError("Connection closed")
        parts.extend(value)
    return bytes(parts)


def read_client_frame(stream):
    first, second = read_exact(stream, 2)
    opcode = first & 0x0F
    if not first & 0x80 or first & 0x70 or not second & 0x80:
        raise ValueError("Only complete masked client frames are supported")
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", read_exact(stream, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", read_exact(stream, 8))[0]
    if length > MAX_BODY or (opcode >= 8 and length > 125):
        raise ValueError("WebSocket frame too large")
    mask = read_exact(stream, 4)
    payload = read_exact(stream, length)
    return opcode, bytes(value ^ mask[index % 4] for index, value in enumerate(payload))


class RelayServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, hub):
        if address[0] != "127.0.0.1":
            raise ValueError("Relay must bind only to loopback")
        self.hub = hub
        super().__init__(address, RelayHandler)


class RelayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    # Unbuffered reads allow select() to see any unread WebSocket data.
    rbufsize = 0

    def log_message(self, *args):
        pass  # Never log secrets, URLs, or referral content.

    def valid_origin(self):
        origin = self.headers.get("Origin")
        return origin is None or bool(ORIGIN_PATTERN.fullmatch(origin))

    def authenticated(self):
        value = self.headers.get("Authorization", "")
        return self.valid_origin() and value.startswith("Bearer ") and self.server.hub.authenticate(value[7:])

    def json_response(self, status, value):
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        origin = self.headers.get("Origin")
        if origin and self.valid_origin():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(payload)
        self.close_connection = True

    def do_OPTIONS(self):
        if not self.valid_origin():
            self.json_response(403, {"success": False, "error": "Origin not allowed"})
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", "null"))
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path == "/events" and self.headers.get("Upgrade", "").lower() == "websocket":
            self.handle_websocket()
            return
        if not self.authenticated():
            self.json_response(403, {"success": False, "error": "Unauthorized"})
            return
        if self.path == "/status":
            self.json_response(200, self.server.hub.status())
        else:
            self.json_response(404, {"success": False, "error": "Not found"})

    def do_POST(self):
        if not self.authenticated():
            self.json_response(403, {"success": False, "error": "Unauthorized"})
            return
        if self.path not in ("/publish", "/probe"):
            self.json_response(404, {"success": False, "error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                raise ValueError("Invalid request length")
            self.connection.settimeout(5)
            raw = json.loads(read_exact(self.rfile, length))
            if not isinstance(raw, dict):
                raise ValueError("Expected JSON object")
            if self.path == "/probe":
                probe_id = self.server.hub.begin_probe()
                time.sleep(0.8)
                result = self.server.hub.status()
                with self.server.hub.lock:
                    result["probeResults"] = list(self.server.hub.probes.get(probe_id, {}).values())
                self.json_response(200, result)
            else:
                self.json_response(200, self.server.hub.publish(raw))
        except (ValueError, ConnectionError, TimeoutError) as error:
            self.json_response(400, {"success": False, "error": str(error)})

    def handle_websocket(self):
        key = self.headers.get("Sec-WebSocket-Key", "")
        try:
            if not self.valid_origin() or self.headers.get("Sec-WebSocket-Version") != "13" or len(base64.b64decode(key, validate=True)) != 16:
                raise ValueError("Invalid WebSocket handshake")
        except ValueError:
            self.json_response(403, {"success": False, "error": "Invalid WebSocket handshake"})
            return
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        self.wfile.flush()
        client_key = None
        self.close_connection = True
        try:
            self.connection.settimeout(5)
            opcode, payload = read_client_frame(self.rfile)
            raw = json.loads(payload.decode("utf-8"))
            if opcode != 1 or not isinstance(raw, dict) or raw.get("type") != "subscribe":
                raise ValueError("Subscribe first")
            client_key, messages = self.server.hub.subscribe(raw)
            last_heartbeat = time.monotonic()
            while True:
                if getattr(messages, "overflow", False):
                    raise ConnectionError("Slow client must reconnect")
                while not messages.empty():
                    message = messages.get_nowait()
                    self.connection.sendall(websocket_frame(json.dumps(message)))
                if time.monotonic() - last_heartbeat >= 20:
                    self.connection.sendall(websocket_frame(json.dumps({"type": "heartbeat", "timestamp": now_ms()})))
                    last_heartbeat = time.monotonic()
                if select.select([self.connection], [], [], 0.2)[0]:
                    opcode, payload = read_client_frame(self.rfile)
                    if opcode == 8:
                        self.connection.sendall(websocket_frame(payload, 8))
                        break
                    if opcode == 9:
                        self.connection.sendall(websocket_frame(payload, 10))
                    elif opcode == 1:
                        self.server.hub.report(client_key, json.loads(payload.decode("utf-8")))
                    elif opcode not in (1, 10):
                        raise ValueError("Unsupported frame type")
        except (ValueError, ConnectionError, OSError):
            try:
                self.connection.sendall(websocket_frame(struct.pack("!H", 1008), 8))
            except OSError:
                pass
        finally:
            if client_key:
                self.server.hub.unsubscribe(client_key)


def main():
    config = configure(Path(__file__).resolve().parent.parent)
    try:
        server = RelayServer(("127.0.0.1", config["port"]), Hub(config["token"]))
    except OSError as error:
        print(f'Cannot start relay on port {config["port"]}: {error}', flush=True)
        print("Another relay may already be running. Check the extension connection button.", flush=True)
        return 1
    print(f'Grok relay ready at http://127.0.0.1:{config["port"]}', flush=True)
    print("Keep this window open. One Hunter profile can now send to all Receiver profiles.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

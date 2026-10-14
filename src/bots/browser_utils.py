def get_window_bounds(index, batch_size=3, max_cols=4, screen_w=1800, screen_h=1000, zero_based_index=False):
    """
    Tính toán kích thước và vị trí của trình duyệt để chia đều màn hình.
    Trả về: (window_width, window_height, x, y)
    """
    cols = min(batch_size, max_cols)
    window_width = screen_w // cols
    window_height = screen_h
    
    idx = index % cols if zero_based_index else (index - 1) % cols
    x = idx * window_width
    y = 0
    return window_width, window_height, x, y

import socket
import select
import base64
import threading

class LocalProxyRelay:
    """
    Local TCP proxy relay chạy trên localhost.
    Trình duyệt kết nối vào đây không cần auth,
    relay tự động thêm Proxy-Authorization và forward lên proxy thật.
    """
    def __init__(self, upstream_host, upstream_port, username="", password="", local_port=0):
        self.upstream_host = upstream_host
        self.upstream_port = int(upstream_port)
        self.auth_b64 = base64.b64encode(f"{username}:{password}".encode()).decode() if (username and password) else None
        self.local_port = local_port
        self._sock = None
        self._running = False

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", self.local_port))
        self.local_port = self._sock.getsockname()[1]
        self._sock.listen(64)
        self._sock.settimeout(1.0)
        self._running = True
        t = threading.Thread(target=self._accept_loop, daemon=True)
        t.start()
        # Không tự log để tránh phụ thuộc logger bên ngoài, người gọi có thể log sau khi start
        return self

    def stop(self):
        self._running = False
        if self._sock:
            try: self._sock.close()
            except: pass

    def _accept_loop(self):
        while self._running:
            try:
                client, _ = self._sock.accept()
                threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _recv_headers(self, sock):
        data = b""
        sock.settimeout(10)
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
            if len(data) > 65536:
                break
        return data

    def _tunnel(self, a, b):
        a.settimeout(600)
        b.settimeout(600)
        try:
            while True:
                r, _, _ = select.select([a, b], [], [], 300)
                if not r:
                    break
                for s in r:
                    other = b if s is a else a
                    chunk = s.recv(65536)
                    if not chunk:
                        return
                    other.sendall(chunk)
        except Exception:
            pass
        finally:
            for s in (a, b):
                try: s.close()
                except: pass

    def _handle_client(self, client):
        upstream = None
        try:
            raw = self._recv_headers(client)
            if not raw:
                return
            first_line = raw.split(b"\r\n")[0].decode(errors="replace")
            upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            upstream.settimeout(15)
            upstream.connect((self.upstream_host, self.upstream_port))

            auth_header = f"Proxy-Authorization: Basic {self.auth_b64}\r\n".encode() if self.auth_b64 else b""

            if b"\r\n\r\n" in raw:
                head, body = raw.split(b"\r\n\r\n", 1)
                lines = head.split(b"\r\n")
                lines = [l for l in lines if not l.lower().startswith(b"proxy-authorization:")]
                if auth_header:
                    modified = b"\r\n".join(lines) + b"\r\n" + auth_header + b"\r\n" + body
                else:
                    modified = b"\r\n".join(lines) + b"\r\n\r\n" + body
            else:
                modified = raw + (auth_header if auth_header else b"") + b"\r\n"

            upstream.sendall(modified)

            if first_line.upper().startswith("CONNECT "):
                resp = b""
                while b"\r\n\r\n" not in resp:
                    chunk = upstream.recv(4096)
                    if not chunk:
                        break
                    resp += chunk
                if b" 407 " in resp.split(b"\r\n")[0]:
                    client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    return
                client.sendall(resp)
                if b"200" in resp.split(b"\r\n")[0]:
                    self._tunnel(client, upstream)
            else:
                self._tunnel(client, upstream)
        except Exception:
            pass
        finally:
            if upstream:
                try: upstream.close()
                except: pass
            if client:
                try: client.close()
                except: pass


def get_settings_from_db():
    import sqlite3
    import os
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "database.db"))
    settings = {}
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT `key`, `value` FROM settings")
        settings = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
    except Exception:
        pass
    return settings

def get_rotated_proxy(logger_func=None):
    import requests
    import random
    FALLBACK_PROXY  = {"host": "180.93.2.171", "port": 3131, "user": "kierangrayson226", "pass": "odq0nda0odmzoa=="}
    
    def _log(msg, level="INFO"):
        if logger_func:
            logger_func(msg, level)
        else:
            print(f"[{level}] {msg}")

    try:
        settings = get_settings_from_db()
        proxy_type = settings.get("PROXY_TYPE", "proxyquick")
        if proxy_type == "proxyxoay":
            key = settings.get("PROXYXOAY_KEY", "")
            url = f"https://proxyxoay.shop/api/get.php?key={key}&&nhamang=random&&tinhthanh=0&whitelist="
            _log("Đang xoay IP qua ProxyXoay.shop API...", "INFO")
            resp = requests.get(url, timeout=15).json()
            if resp.get("status") == 100:
                proxy_str = resp.get("proxyhttp", "")
                parts = proxy_str.split(":")
                _log(f"Xoay IP thành công → {parts[0]}:{parts[1]}", "OK")
                return {"host": parts[0], "port": int(parts[1]), "user": "", "pass": ""}
            else:
                _log(f"API xoay proxy lỗi: {resp} → dùng proxy cố định", "WARN")
        else:
            token = settings.get("PROXY_API_TOKEN", "")
            merchant = settings.get("PROXY_MERCHANT", "")
            proxy_id = settings.get("PROXY_ID", "953319")
            headers = {"Authorization": f"Bearer {token}", "x-merchant-id": merchant}
            url = f"https://proxyquick.click/api/v2/proxies/{proxy_id}/rotate"
            _log("Đang xoay IP qua ProxyQuick API v2...", "INFO")
            resp = requests.get(url, headers=headers, proxies={"http": None, "https": None}, timeout=15).json()
            if resp.get("status") == "success":
                proxy_str = resp.get("proxy", "")
                parts = proxy_str.split(":")
                if len(parts) >= 4:
                    _log(f"Xoay IP thành công → {resp.get('ip', '')}", "OK")
                    return {"host": parts[0], "port": int(parts[1]), "user": parts[2], "pass": parts[3]}
            _log(f"API xoay proxy lỗi: {resp} → dùng proxy cố định", "WARN")
    except Exception as e:
        _log(f"Lỗi gọi API proxy: {e}", "ERR")
    
    _log(f"Dùng proxy cố định: {FALLBACK_PROXY['host']}:{FALLBACK_PROXY['port']}", "OK")
    return FALLBACK_PROXY

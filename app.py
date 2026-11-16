import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import queue
import time
import json
import hashlib
import uuid
import csv
import requests
from typing import Optional, Dict, Any, List

class AtomicMailClient:
    API_BASE = "https://api.atomicmail.io/v1"
    
    def __init__(self, timeout: int = 15):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://atomicmail.io",
            "Referer": "https://atomicmail.io/app/login",
        })
        self.timeout = timeout
        self.user_id = None
        self.access_token = None

    @staticmethod
    def hash_password(password: str) -> str:
        password = password.strip()
        # Nếu đã là chuỗi SHA256 (64 ký tự hex) thì giữ nguyên
        if len(password) == 64 and all(c in "0123456789abcdefABCDEF" for c in password):
            return password.lower()
        # Plaintext thì hash bằng SHA256 chuẩn
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    @staticmethod
    def extract_username(email_or_user: str) -> tuple[str, bool]:
        """Tách username và kiểm tra có phải enterprise domain hay không."""
        email_or_user = email_or_user.strip()
        if "@" in email_or_user:
            username, domain = email_or_user.split("@", 1)
            domain = domain.lower()
            if domain == "atomicmail.io":
                return username.strip(), False
            else:
                # Domain doanh nghiệp riêng
                return email_or_user.lower(), True
        return email_or_user, False

    def sign_in(self, email_or_user: str, password_raw: str, device_id: Optional[str] = None) -> Dict[str, Any]:
        """Thực hiện đăng nhập qua POST /v1/auth/sign-in"""
        username, is_enterprise = self.extract_username(email_or_user)
        pw_hash = self.hash_password(password_raw)
        
        if not device_id:
            device_id = uuid.uuid4().hex

        payload = {
            "isEnterprise": is_enterprise,
            "username": username,
            "password": pw_hash,
            "platform": "web",
            "deviceId": device_id
        }

        url = f"{self.API_BASE}/auth/sign-in"
        resp = self.session.post(url, json=payload, timeout=self.timeout)

        # Nếu gửi nguyên chuỗi 64-char hex bị 401, thử hash tiếp một lần nữa phòng trường hợp mật khẩu gốc dài 64 ký tự
        if resp.status_code == 401 and len(password_raw.strip()) == 64:
            alt_hash = hashlib.sha256(password_raw.strip().encode("utf-8")).hexdigest()
            payload["password"] = alt_hash
            resp = self.session.post(url, json=payload, timeout=self.timeout)

        try:
            data = resp.json()
        except Exception:
            raise Exception(f"HTTP {resp.status_code}: Không parse được JSON phản hồi ({resp.text[:100]})")

        if resp.status_code not in (200, 201) or not data.get("success", False):
            err_msg = data.get("error") or data.get("message") or f"Lỗi đăng nhập (HTTP {resp.status_code})"
            raise Exception(err_msg)

        self.user_id = data.get("id")
        self.access_token = data.get("accessToken")
        
        # Cập nhật auth headers cho các request sau
        if self.user_id:
            self.session.headers["x-user-id"] = self.user_id
        if self.access_token:
            self.session.headers["Authorization"] = f"Bearer {self.access_token}"

        return data

    def get_mailboxes(self) -> List[Dict[str, Any]]:
        """Lấy danh sách mailboxes từ GET /v1/mailboxes"""
        url = f"{self.API_BASE}/mailboxes"
        resp = self.session.get(url, timeout=self.timeout)
        try:
            data = resp.json()
        except Exception:
            raise Exception(f"HTTP {resp.status_code}: Lỗi lấy danh sách mailbox")

        if resp.status_code != 200 or not data.get("success", False):
            raise Exception(data.get("error", f"Không lấy được mailboxes (HTTP {resp.status_code})"))

        return data.get("results", [])

    def get_inbox_id(self) -> str:
        """Tìm mailbox ID của INBOX"""
        mailboxes = self.get_mailboxes()
        # Tìm mailbox có path == 'INBOX'
        for mb in mailboxes:
            if mb.get("path") == "INBOX" or mb.get("name") == "INBOX":
                return mb.get("id")
        # Nếu không có, lấy mailbox đầu tiên
        if mailboxes:
            return mailboxes[0].get("id")
        raise Exception("Không tìm thấy mailbox nào trong tài khoản")

    def get_messages(self, mailbox_id: str) -> List[Dict[str, Any]]:
        """Lấy danh sách thư từ GET /v1/mailboxes/<mailbox_id>/messages"""
        url = f"{self.API_BASE}/mailboxes/{mailbox_id}/messages"
        resp = self.session.get(url, timeout=self.timeout)
        try:
            data = resp.json()
        except Exception:
            raise Exception(f"HTTP {resp.status_code}: Lỗi lấy danh sách messages")

        if resp.status_code != 200 or not data.get("success", False):
            raise Exception(data.get("error", f"Không lấy được messages (HTTP {resp.status_code})"))

        return data.get("results", [])

    def find_keyword_in_messages(self, mailbox_id: str, keyword: str = "Pro monthly") -> Optional[Dict[str, Any]]:
        """Duyệt qua danh sách thư và tìm kiếm keyword, trả về thông tin thư chứa keyword"""
        messages = self.get_messages(mailbox_id)
        for msg in messages:
            msg_str = json.dumps(msg, ensure_ascii=False)
            if keyword.lower() in msg_str.lower():
                return {
                    "id": msg.get("id"),
                    "subject": msg.get("subject", ""),
                    "date": msg.get("date", ""),
                    "intro": msg.get("intro", ""),
                    "from": msg.get("from", {}).get("address", "") if isinstance(msg.get("from"), dict) else str(msg.get("from")),
                    "raw_message": msg
                }
        return None


class AtomicMailGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AtomicMail Automation Tool - Auto Read & Check Pro Monthly")
        self.root.geometry("1100x720")
        self.root.minsize(950, 600)

        # Trạng thái luồng & dữ liệu
        self.is_running = False
        self.stop_requested = False
        self.log_queue = queue.Queue()
        self.results_data = []

        self._init_styles()
        self._build_ui()
        self._start_queue_listener()

    def _init_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Cấu hình màu sắc hiện đại
        style.configure("Treeview", 
                        background="#FFFFFF", 
                        foreground="#2D3748", 
                        rowheight=26, 
                        fieldbackground="#FFFFFF",
                        font=("Segoe UI", 9))
        style.configure("Treeview.Heading", 
                        font=("Segoe UI", 9, "bold"), 
                        background="#EDF2F7", 
                        foreground="#1A202C")
        style.map("Treeview", background=[("selected", "#3182CE")], foreground=[("selected", "#FFFFFF")])

    def _build_ui(self):
        # 1. Header Frame
        header_frame = tk.Frame(self.root, bg="#2B6CB0", height=60)
        header_frame.pack(fill=tk.X, side=tk.TOP)
        header_frame.pack_propagate(False)

        title_label = tk.Label(header_frame, 
                               text="⚡ AtomicMail Auto Sign-In & Message Checker", 
                               font=("Segoe UI", 14, "bold"), 
                               fg="#FFFFFF", 
                               bg="#2B6CB0")
        title_label.pack(side=tk.LEFT, padx=20, pady=5)

        subtitle_label = tk.Label(header_frame, 
                                  text="Tự động đăng nhập, lấy Mailbox ID (INBOX) và quét 'Pro monthly'", 
                                  font=("Segoe UI", 9), 
                                  fg="#E2E8F0", 
                                  bg="#2B6CB0")
        subtitle_label.pack(side=tk.LEFT, padx=5, pady=8)

        # 2. Main PanedWindow (Trái: Input, Phải: Kết quả & Log)
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # === PANEL TRÁI: Nhập danh sách tài khoản & Cài đặt ===
        left_frame = ttk.Frame(main_paned, width=350)
        main_paned.add(left_frame, weight=1)

        input_label_frame = ttk.LabelFrame(left_frame, text=" Danh sách tài khoản (email | pass) ")
        input_label_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Hướng dẫn định dạng
        tip_label = ttk.Label(input_label_frame, 
                              text="Định dạng: email | pass (hoặc user | pass)\nMỗi tài khoản 1 dòng:", 
                              font=("Segoe UI", 8), foreground="#4A5568")
        tip_label.pack(anchor="w", padx=8, pady=(4, 2))

        # Text input
        self.text_input = scrolledtext.ScrolledText(input_label_frame, wrap=tk.WORD, font=("Consolas", 9), height=14)
        self.text_input.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        
        # Thêm mẫu ví dụ
        example_acc = "dnishghori611@atomicmail.io | 63ec2764ac81ee393d4a427e255835ea272531b9c7c4f2c780e88f905ce3a347\n"
        self.text_input.insert(tk.END, example_acc)

        # Nút tiện ích cho Text input
        btn_input_frame = ttk.Frame(input_label_frame)
        btn_input_frame.pack(fill=tk.X, padx=8, pady=4)

        btn_load_file = ttk.Button(btn_input_frame, text="📂 Nạp từ file TXT", command=self.load_from_file)
        btn_load_file.pack(side=tk.LEFT, padx=(0, 4))

        btn_clear_input = ttk.Button(btn_input_frame, text="🗑️ Xóa trắng", command=self.clear_input)
        btn_clear_input.pack(side=tk.LEFT)

        self.lbl_acc_count = ttk.Label(btn_input_frame, text="Tổng: 1", font=("Segoe UI", 8, "italic"))
        self.lbl_acc_count.pack(side=tk.RIGHT)
        self.text_input.bind("<KeyRelease>", self._update_acc_count)

        # Config Frame (Số luồng, từ khóa tìm kiếm)
        config_frame = ttk.LabelFrame(left_frame, text=" Tùy chọn cấu hình ")
        config_frame.pack(fill=tk.X, padx=5, pady=5)

        # Từ khóa tìm kiếm
        ttk.Label(config_frame, text="Từ khóa tìm:").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.entry_keyword = ttk.Entry(config_frame, font=("Segoe UI", 9))
        self.entry_keyword.insert(0, "Pro monthly")
        self.entry_keyword.grid(row=0, column=1, sticky="ew", padx=8, pady=4)

        # Số luồng
        ttk.Label(config_frame, text="Số luồng (Threads):").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self.spin_threads = ttk.Spinbox(config_frame, from_=1, to=10, width=5)
        self.spin_threads.set(3)
        self.spin_threads.grid(row=1, column=1, sticky="w", padx=8, pady=4)
        config_frame.columnconfigure(1, weight=1)

        # Control Buttons
        action_frame = ttk.Frame(left_frame)
        action_frame.pack(fill=tk.X, padx=5, pady=8)

        self.btn_start = tk.Button(action_frame, text="▶ BẮT ĐẦU CHẠY", 
                                   bg="#38A169", fg="#FFFFFF", font=("Segoe UI", 10, "bold"),
                                   relief=tk.FLAT, padx=12, pady=6, cursor="hand2", command=self.start_process)
        self.btn_start.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self.btn_stop = tk.Button(action_frame, text="⏹ DỪNG", 
                                  bg="#E53E3E", fg="#FFFFFF", font=("Segoe UI", 10, "bold"),
                                  relief=tk.FLAT, padx=12, pady=6, cursor="hand2", state=tk.DISABLED, command=self.stop_process)
        self.btn_stop.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # === PANEL PHẢI: Thống kê, Bảng kết quả & Nhật ký ===
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=3)

        # Thống kê nhanh
        stats_frame = ttk.Frame(right_frame)
        stats_frame.pack(fill=tk.X, pady=(0, 5))

        self.lbl_stat_total = self._create_stat_badge(stats_frame, "Tổng số:", "0", "#4A5568")
        self.lbl_stat_done = self._create_stat_badge(stats_frame, "Đã xong:", "0", "#3182CE")
        self.lbl_stat_found = self._create_stat_badge(stats_frame, "Tìm thấy Pro:", "0", "#38A169")
        self.lbl_stat_fail = self._create_stat_badge(stats_frame, "Thất bại:", "0", "#E53E3E")

        btn_export = ttk.Button(stats_frame, text="💾 Xuất CSV kết quả", command=self.export_csv)
        btn_export.pack(side=tk.RIGHT, padx=5)

        # Bảng kết quả Treeview
        tree_frame = ttk.LabelFrame(right_frame, text=" Bảng kết quả chi tiết ")
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=4)

        columns = ("stt", "email", "status", "mailbox_id", "date", "intro")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        
        self.tree.heading("stt", text="#")
        self.tree.heading("email", text="Email / Username")
        self.tree.heading("status", text="Trạng thái")
        self.tree.heading("mailbox_id", text="Mailbox ID (INBOX)")
        self.tree.heading("date", text="Pro Monthly Date")
        self.tree.heading("intro", text="Tóm tắt nội dung / Lỗi")

        self.tree.column("stt", width=40, anchor="center")
        self.tree.column("email", width=190, anchor="w")
        self.tree.column("status", width=95, anchor="center")
        self.tree.column("mailbox_id", width=190, anchor="w")
        self.tree.column("date", width=180, anchor="center")
        self.tree.column("intro", width=260, anchor="w")

        tree_scroll_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        tree_scroll_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.tree.bind("<Double-1>", self._on_tree_double_click)

        # Nhật ký thời gian thực (Console Log)
        log_frame = ttk.LabelFrame(right_frame, text=" Nhật ký hệ thống (Live Logs) ")
        log_frame.pack(fill=tk.BOTH, expand=False, pady=4)
        log_frame.config(height=130)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, font=("Consolas", 8), bg="#1A202C", fg="#E2E8F0")
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def _create_stat_badge(self, parent, label_text, default_val, color):
        f = tk.Frame(parent, bg="#EDF2F7", padx=8, pady=4, relief=tk.GROOVE, bd=1)
        f.pack(side=tk.LEFT, padx=3)
        tk.Label(f, text=label_text, font=("Segoe UI", 8), bg="#EDF2F7", fg="#4A5568").pack(side=tk.LEFT)
        val_lbl = tk.Label(f, text=default_val, font=("Segoe UI", 9, "bold"), bg="#EDF2F7", fg=color)
        val_lbl.pack(side=tk.LEFT, padx=(4, 0))
        return val_lbl

    def _update_acc_count(self, event=None):
        content = self.text_input.get("1.0", tk.END).strip()
        lines = [line for line in content.splitlines() if line.strip()]
        self.lbl_acc_count.config(text=f"Tổng: {len(lines)}")

    def log(self, message: str, level: str = "INFO"):
        now = time.strftime("%H:%M:%S")
        self.log_queue.put((f"[{now}] [{level}] {message}\n", level))

    def _start_queue_listener(self):
        """Hàm cập nhật log và kết quả lên UI theo thời gian thực (Thread-safe)"""
        try:
            while not self.log_queue.empty():
                item = self.log_queue.get_nowait()
                if isinstance(item, tuple) and len(item) == 2:
                    msg, level = item
                    self.log_text.insert(tk.END, msg)
                    self.log_text.see(tk.END)
                elif isinstance(item, dict) and item.get("type") == "ROW_RESULT":
                    self._add_row_result(item["data"])
                elif isinstance(item, dict) and item.get("type") == "STATS_UPDATE":
                    self.lbl_stat_done.config(text=str(item["done"]))
                    self.lbl_stat_found.config(text=str(item["found"]))
                    self.lbl_stat_fail.config(text=str(item["fail"]))
        except Exception:
            pass
        finally:
            self.root.after(100, self._start_queue_listener)

    def _add_row_result(self, row: dict):
        self.results_data.append(row)
        stt = len(self.results_data)
        self.tree.insert("", tk.END, values=(
            stt,
            row.get("email", ""),
            row.get("status", ""),
            row.get("mailbox_id", ""),
            row.get("date", ""),
            row.get("intro", "")
        ))

    def _on_tree_double_click(self, event):
        selected_item = self.tree.selection()
        if not selected_item:
            return
        item_vals = self.tree.item(selected_item[0], "values")
        if item_vals:
            detail = (
                f"STT: {item_vals[0]}\n"
                f"Email: {item_vals[1]}\n"
                f"Trạng thái: {item_vals[2]}\n"
                f"Mailbox ID (INBOX): {item_vals[3]}\n"
                f"Pro Monthly Date: {item_vals[4]}\n"
                f"Chi tiết nội dung:\n{item_vals[5]}"
            )
            messagebox.showinfo("Chi tiết tài khoản", detail)

    def load_from_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.text_input.delete("1.0", tk.END)
                self.text_input.insert(tk.END, content)
                self._update_acc_count()
                self.log(f"Đã nạp file {file_path}", "INFO")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không đọc được file: {e}")

    def clear_input(self):
        self.text_input.delete("1.0", tk.END)
        self._update_acc_count()

    def export_csv(self):
        if not self.results_data:
            messagebox.showwarning("Thông báo", "Chưa có kết quả nào để xuất!")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if file_path:
            try:
                with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(["STT", "Email", "Trạng thái", "Mailbox ID (INBOX)", "Pro Monthly Date", "Nội dung tóm tắt / Lỗi"])
                    for i, r in enumerate(self.results_data, 1):
                        writer.writerow([i, r.get("email"), r.get("status"), r.get("mailbox_id"), r.get("date"), r.get("intro")])
                messagebox.showinfo("Thành công", f"Đã lưu kết quả ra:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không xuất được file: {e}")

    def start_process(self):
        raw_text = self.text_input.get("1.0", tk.END).strip()
        if not raw_text:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập ít nhất một tài khoản dạng email | pass!")
            return

        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        if not lines:
            messagebox.showwarning("Cảnh báo", "Danh sách tài khoản trống!")
            return

        keyword = self.entry_keyword.get().strip()
        try:
            threads_count = int(self.spin_threads.get())
        except ValueError:
            threads_count = 3

        # Reset UI
        self.tree.delete(*self.tree.get_children())
        self.results_data.clear()
        self.lbl_stat_total.config(text=str(len(lines)))
        self.lbl_stat_done.config(text="0")
        self.lbl_stat_found.config(text="0")
        self.lbl_stat_fail.config(text="0")
        self.log_text.delete("1.0", tk.END)

        self.is_running = True
        self.stop_requested = False
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)

        # Chạy worker trong thread riêng để không block GUI
        worker_thread = threading.Thread(
            target=self._run_batch,
            args=(lines, keyword, threads_count),
            daemon=True
        )
        worker_thread.start()

    def stop_process(self):
        if self.is_running:
            self.stop_requested = True
            self.log("Đã yêu cầu dừng tiến trình...", "WARN")
            self.btn_stop.config(state=tk.DISABLED)

    def _run_batch(self, lines: List[str], keyword: str, threads_count: int):
        self.log(f"Bắt đầu xử lý {len(lines)} tài khoản với {threads_count} luồng. Từ khóa tìm: '{keyword}'", "INFO")
        
        task_queue = queue.Queue()
        for idx, line in enumerate(lines, 1):
            task_queue.put((idx, line))

        done_count = 0
        found_count = 0
        fail_count = 0
        lock = threading.Lock()

        def worker():
            nonlocal done_count, found_count, fail_count
            while not task_queue.empty() and not self.stop_requested:
                try:
                    idx, line = task_queue.get_nowait()
                except queue.Empty:
                    break

                # Tách email và pass
                parts = [p.strip() for p in line.split("|", 1)]
                if len(parts) < 2:
                    email_or_user = parts[0]
                    pass_raw = ""
                else:
                    email_or_user, pass_raw = parts[0], parts[1]

                self.log(f"[{idx}/{len(lines)}] Đang xử lý: {email_or_user}...", "INFO")
                
                client = AtomicMailClient()
                row_res = {
                    "email": email_or_user,
                    "status": "Thất bại",
                    "mailbox_id": "",
                    "date": "",
                    "intro": ""
                }

                try:
                    # 1. Đăng nhập
                    client.sign_in(email_or_user, pass_raw)
                    self.log(f"[{email_or_user}] Đăng nhập thành công (User ID: {client.user_id})", "SUCCESS")
                    
                    # 2. Lấy Mailbox ID (INBOX)
                    inbox_id = client.get_inbox_id()
                    row_res["mailbox_id"] = inbox_id
                    self.log(f"[{email_or_user}] Lấy thành công INBOX Mailbox ID: {inbox_id}", "INFO")

                    # 3. Quét messages tìm keyword
                    matched = client.find_keyword_in_messages(inbox_id, keyword=keyword)
                    if matched:
                        row_res["status"] = "Tìm thấy Pro"
                        row_res["date"] = matched.get("date", "")
                        row_res["intro"] = f"[{matched.get('subject')}] {matched.get('intro')}"
                        self.log(f"[{email_or_user}] ✅ TÌM THẤY '{keyword}'! Date: {row_res['date']}", "SUCCESS")
                        with lock:
                            found_count += 1
                    else:
                        row_res["status"] = "Đăng nhập OK"
                        row_res["intro"] = f"Không có thư chứa '{keyword}'"
                        self.log(f"[{email_or_user}] Đăng nhập OK nhưng không tìm thấy '{keyword}'", "INFO")

                except Exception as e:
                    row_res["status"] = "Lỗi"
                    row_res["intro"] = str(e)
                    self.log(f"[{email_or_user}] ❌ Lỗi: {e}", "ERROR")
                    with lock:
                        fail_count += 1

                with lock:
                    done_count += 1
                    self.log_queue.put({"type": "STATS_UPDATE", "done": done_count, "found": found_count, "fail": fail_count})

                self.log_queue.put({"type": "ROW_RESULT", "data": row_res})
                task_queue.task_done()
                time.sleep(0.1)

        # Khởi chạy threads
        threads = []
        actual_threads = min(threads_count, len(lines))
        for _ in range(actual_threads):
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        self.is_running = False
        self.root.after(0, self._on_finish)

    def _on_finish(self):
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        if self.stop_requested:
            self.log("Tiến trình đã dừng theo yêu cầu của người dùng.", "WARN")
            messagebox.showinfo("Thông báo", "Đã dừng tiến trình!")
        else:
            self.log("Hoàn tất toàn bộ danh sách!", "SUCCESS")
            messagebox.showinfo("Hoàn tất", "Đã xử lý xong toàn bộ danh sách!")


if __name__ == "__main__":
    root = tk.Tk()
    app = AtomicMailGUI(root)
    root.mainloop()

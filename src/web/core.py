import threading
import queue
import json
import collections
from datetime import datetime

class BotState:
    def __init__(self, bot_name):
        self.name = bot_name
        self.log_queue = queue.Queue()
        self.recent_logs = collections.deque(maxlen=60)
        self.task_stop = threading.Event()
        self.task_thread = None
        self.is_running = False
        self.module = None
        self.last_start_id = 0

    def log(self, msg, level="INFO"):
        now = datetime.now().strftime("%H:%M:%S")
        entry = {"type": "log", "level": level, "time": now, "msg": msg}
        serialized = json.dumps(entry)
        self.recent_logs.append(serialized)
        self.log_queue.put(serialized)
        icons = {"OK": "✅", "WARN": "⚠️ ", "ERR": "❌", "INFO": "📌"}
        print(f"[{self.name}] [{now}] {icons.get(level,'📌')} {msg}")

state_capcut = BotState("CapCut")
state_higgsfield = BotState("Higgsfield")
state_gpt = BotState("GPT")
state_gpm = BotState("GPM")
state_dreamina = BotState("Dreamina")
state_grok = BotState("Grok")

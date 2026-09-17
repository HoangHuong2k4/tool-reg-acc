import sys
import os

# Add root directory to python path
sys.path.append(os.getcwd())

from src.bots.grok_hotmail import send_telegram_message
print("Sending test message...")
send_telegram_message("✅ DONE ACC: bethelschwering95625@outlook.com\nMasa168 đã thanh toán thành công!")
print("Done!")

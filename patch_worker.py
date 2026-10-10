import re

with open('src/web/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_worker = """            def worker(i):
                try:
                    time.sleep((i % threads) * 2.5)
                    while not bot.HOTMAIL_QUEUE.empty() and not state_capcut.task_stop.is_set():
                        res = bot.register_one_account(i, join_link if mode == 2 else None, keep_open=(mode == 1), batch_size=threads, headless=headless, browser_type=browser_type, get_link=(mode == 3), mail_api_source=mail_api_source, incognito=incognito)
                        state_capcut.log_queue.put(json.dumps({"type": "result", "success": bool(res)}))
                        if res: done["ok"] += 1
                        else: done["fail"] += 1
                except Exception as e:
                    import traceback
                    err_msg = "".join(traceback.format_exception(type(e), e, e.__traceback__))
                    state_capcut.log(f"Worker Error: {err_msg}", "ERR")"""

content = re.sub(r'            def worker\(i\):\n                time\.sleep\(\(i % threads\) \* 2\.5\)\n                while not bot\.HOTMAIL_QUEUE\.empty\(\) and not state_capcut\.task_stop\.is_set\(\):\n                    res = bot\.register_one_account[^\n]*\n                    state_capcut\.log_queue\.put[^\n]*\n                    if res: done\["ok"\] \+= 1\n                    else: done\["fail"\] \+= 1', new_worker, content, flags=re.MULTILINE)

with open('src/web/app.py', 'w', encoding='utf-8') as f:
    f.write(content)


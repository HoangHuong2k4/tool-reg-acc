"""One installation key shared by the relay and both unpacked extensions."""
import json
from pathlib import Path
import secrets


def configure(root: Path):
    config_path = root / "relay" / "config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        config = {"port": 17865, "token": secrets.token_urlsafe(32)}
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    if not isinstance(config.get("port"), int) or not 1024 <= config["port"] <= 65535:
        raise ValueError("Relay port must be between 1024 and 65535")
    if not isinstance(config.get("token"), str) or len(config["token"]) < 32:
        raise ValueError("Relay token is missing or too short")
    browser_config = {
        "baseUrl": f'http://127.0.0.1:{config["port"]}',
        "wsUrl": f'ws://127.0.0.1:{config["port"]}/events',
        "token": config["token"],
    }
    script = "// Local installation configuration. Do not publish this key.\n"
    script += "globalThis.GROK_RELAY_CONFIG = Object.freeze(" + json.dumps(browser_config) + ");\n"
    for directory in (root,):
        target = directory / "relay-config.js"
        if not target.exists() or target.read_text(encoding="utf-8") != script:
            target.write_text(script, encoding="utf-8")
    return config


if __name__ == "__main__":
    configure(Path(__file__).resolve().parent.parent)
    print("Relay and both extensions now share the same installation key.")

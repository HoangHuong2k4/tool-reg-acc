"""Package the Grok Auto Link Opener extension and local relay."""
from pathlib import Path
import json
from zipfile import ZIP_DEFLATED, ZipFile

from configure import configure


def main():
    root = Path(__file__).resolve().parent.parent
    configure(root)
    version = json.loads((root / "manifest.json").read_text(encoding="utf-8"))["version"]
    files = [root / name for name in (
        "manifest.json", "background.js", "receiver-engine.js", "popup.html", "popup.js", "popup.css",
        "README.md", "START-RELAY.cmd", "start-relay.sh", "start-relay.command", "relay-config.js",
        "relay/server.py", "relay/configure.py", "relay/config.json", "relay/package.py",
    )]
    files += sorted(path for path in (root / "icons").iterdir() if path.is_file())
    
    zip_path = root / f"grok-auto-opener-v{version}.zip"
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, file.relative_to(root).as_posix())
    with ZipFile(zip_path) as archive:
        assert archive.testzip() is None
    print(f"Packaged {len(files)} files into {zip_path.name}")


if __name__ == "__main__":
    main()

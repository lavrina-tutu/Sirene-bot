"""Bootstrap .env from hermes .env (used once during setup)."""
import sys
from pathlib import Path

src = Path(r"C:\Users\tkachenkoav\AppData\Local\hermes\.env")
dst = Path(r"C:\Users\tkachenkoav\Documents\Cursor_projects\MoveFromFF\.env")

wanted = {"FIREFLIES_API_KEY", "TELEGRAM_BOT_TOKEN"}
found = {}
for raw in src.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    k = k.strip()
    if k in wanted:
        found[k] = v.strip()

missing = wanted - found.keys()
if missing:
    print("MISSING:", missing)
    sys.exit(1)

out = []
out.append(r"WORKVAULT_PATH=C:\Users\tkachenkoav\WorkVault")
out.append(r"PROJECT_PATH=C:\Users\tkachenkoav\Documents\Cursor_projects\MoveFromFF")
out.append(f"FIREFLIES_API_KEY={found['FIREFLIES_API_KEY']}")
out.append(f"TELEGRAM_BOT_TOKEN={found['TELEGRAM_BOT_TOKEN']}")
out.append("TELEGRAM_CHAT_ID=400307920")
out.append("DELETED_CHECK_WINDOW_DAYS=90")
dst.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"WROTE {dst} ({dst.stat().st_size} bytes)")
print(f"FF len={len(found['FIREFLIES_API_KEY'])}, TG len={len(found['TELEGRAM_BOT_TOKEN'])}")

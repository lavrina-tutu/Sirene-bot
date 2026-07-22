# Obsidian redirect server — полный код (развёрнуто 07.07.2026)

Назначение: превратить `obsidian://open?vault=...&file=...` (не кликается в Telegram у этого пользователя ни в каком виде) в обычный `http://` линк, который Telegram линкует нормально и который делает 302-редирект в Obsidian.

Расположение на ВМ: `~/services/obsidian-redirect/`
Systemd: `~/.config/systemd/user/obsidian-redirect.service`, юнит `obsidian-redirect.service`, порт 8765.
Доступность: только из корп-сети tutu.ru (ВМ `hermes-agents.devel.tutu.ru`, IP `10.2.24.163`, нет публичного адреса).
Память: ~11 МБ в простое (чистый `http.server`, без Flask/gunicorn).

## Файлы

### `.secret`
Один раз сгенерированный `secrets.token_hex(32)`, chmod 600. **Не перегенерировать без явного разрешения Саши** — это инвалидирует все ранее разосланные ссылки (HMAC делается по этому ключу).

### `server.py`
```python
#!/usr/bin/env python3
"""
Obsidian redirect server.
Serves short HTTP links that redirect to obsidian://open?... URIs,
so Telegram (which won't linkify custom URI schemes) can show clickable links.

Security:
- Each link is HMAC-signed with a secret key stored in .secret (chmod 600).
- Invalid signature -> same 404 response as unknown path (no info leak).
- Rate limiting: 5 failed attempts per IP -> 10 min block.
- All requests logged to access.log.

Only reachable from the tutu.ru corporate network (VM has no public IP).
"""
import hashlib
import hmac
import http.server
import logging
import socketserver
import threading
import time
import urllib.parse
from pathlib import Path

BASE_DIR = Path(__file__).parent
SECRET_FILE = BASE_DIR / ".secret"
LOG_FILE = BASE_DIR / "access.log"
PORT = 8765

MAX_FAILS = 5
BLOCK_SECONDS = 10 * 60
FAIL_WINDOW_SECONDS = 10 * 60  # count fails within this window before blocking

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(message)s",
)

with open(SECRET_FILE, "r") as f:
    SECRET = f.read().strip()

# in-memory rate limit state: ip -> {"fails": [timestamps], "blocked_until": ts}
_lock = threading.Lock()
_state = {}


def sign(vault: str, file: str) -> str:
    msg = f"{vault}\n{file}".encode("utf-8")
    return hmac.new(SECRET.encode(), msg, hashlib.sha256).hexdigest()[:32]


def make_link(vault: str, file: str, base_url: str) -> str:
    sig = sign(vault, file)
    q = urllib.parse.urlencode({"vault": vault, "file": file, "sig": sig})
    return f"{base_url}/r?{q}"


def is_blocked(ip: str) -> bool:
    with _lock:
        entry = _state.get(ip)
        if not entry:
            return False
        blocked_until = entry.get("blocked_until", 0)
        if blocked_until and time.time() < blocked_until:
            return True
        return False


def register_fail(ip: str):
    now = time.time()
    with _lock:
        entry = _state.setdefault(ip, {"fails": [], "blocked_until": 0})
        entry["fails"] = [t for t in entry["fails"] if now - t < FAIL_WINDOW_SECONDS]
        entry["fails"].append(now)
        if len(entry["fails"]) >= MAX_FAILS:
            entry["blocked_until"] = now + BLOCK_SECONDS
            entry["fails"] = []
            logging.warning(f"BLOCKED ip={ip} for {BLOCK_SECONDS}s after {MAX_FAILS} failed attempts")


def register_success(ip: str):
    with _lock:
        if ip in _state:
            _state[ip]["fails"] = []


REDIRECT_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={obs_url}">
<title>Opening Obsidian...</title></head>
<body>
<p>Opening in Obsidian... If nothing happens, <a href="{obs_url}">click here</a>.</p>
<script>window.location.href = "{obs_url}";</script>
</body></html>"""

NOT_FOUND_BODY = b"404 Not Found"


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # disable default stderr logging; we use our own

    def _send_404(self):
        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(NOT_FOUND_BODY)))
        self.end_headers()
        self.wfile.write(NOT_FOUND_BODY)

    def do_GET(self):
        ip = self.client_address[0]
        parsed = urllib.parse.urlparse(self.path)

        if is_blocked(ip):
            logging.info(f"BLOCKED-REQUEST ip={ip} path={self.path}")
            self._send_404()
            return

        if parsed.path != "/r":
            logging.info(f"UNKNOWN-PATH ip={ip} path={self.path}")
            self._send_404()
            return

        qs = urllib.parse.parse_qs(parsed.query)
        vault = qs.get("vault", [""])[0]
        file = qs.get("file", [""])[0]
        sig = qs.get("sig", [""])[0]

        if not vault or not file or not sig:
            register_fail(ip)
            logging.info(f"MISSING-PARAMS ip={ip} path={self.path}")
            self._send_404()
            return

        expected = sign(vault, file)
        if not hmac.compare_digest(expected, sig):
            register_fail(ip)
            logging.info(f"BAD-SIG ip={ip} vault={vault} file={file}")
            self._send_404()
            return

        register_success(ip)
        logging.info(f"OK ip={ip} vault={vault} file={file}")

        obs_url = f"obsidian://open?vault={urllib.parse.quote(vault)}&file={urllib.parse.quote(file)}"
        body = REDIRECT_HTML.format(obs_url=obs_url).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    logging.info(f"Server starting on port {PORT}")
    server.serve_forever()
```

### `make_link.py`
```python
#!/usr/bin/env python3
"""Generate a signed obsidian-redirect link for a WorkVault file.

Usage: python3 make_link.py "<relative/path/from/vault/root.md>"
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from server import make_link, SECRET  # noqa: E402

BASE_URL = "http://hermes-agents.devel.tutu.ru:8765"
VAULT = "WorkVault"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: make_link.py <relative-file-path-without-.md>")
        sys.exit(1)
    file_path = sys.argv[1]
    print(make_link(VAULT, file_path, BASE_URL))
```

## systemd unit
`~/.config/systemd/user/obsidian-redirect.service`:
```ini
[Unit]
Description=Obsidian redirect server (WorkVault links for Telegram)
After=network.target

[Service]
Type=simple
ExecStart=/home/tkachenkoav/hermes-agent/.venv/bin/python3 /home/tkachenkoav/services/obsidian-redirect/server.py
Restart=on-failure
RestartSec=5
WorkingDirectory=/home/tkachenkoav/services/obsidian-redirect

[Install]
WantedBy=default.target
```
Установка/проверка:
```bash
systemctl --user daemon-reload
systemctl --user enable --now obsidian-redirect.service
systemctl --user status obsidian-redirect.service --no-pager
```
`loginctl show-user $(whoami) | grep Linger` должен быть `yes` — иначе сервис не переживёт разлогин (на этой ВМ уже включён).

## Использование

```bash
cd ~/services/obsidian-redirect
python3 make_link.py "Meetings/NewMeetings/2026-07-07 07-35-00 Кирилл 1-1 - summary"
# -> http://hermes-agents.devel.tutu.ru:8765/r?vault=WorkVault&file=...&sig=...
```
Путь — относительно корня vault, **без** `.md` на конце. Вставлять в обычную markdown-ссылку `[имя](url)`.

## Проверка (сделана при развёртывании)
- Верная подпись → 200 + HTML с `obsidian://` редиректом (meta-refresh + JS).
- Неверная/отсутствующая подпись → 404, тело "404 Not Found", неотличимо от несуществующего пути.
- 5 неудачных попыток с одного IP подряд → 6-я и далее в течение 10 минут получают 404 с логом `BLOCKED-REQUEST`, независимо от того, был ли токен верным.
- Все события пишутся в `access.log` (`OK`, `BAD-SIG`, `MISSING-PARAMS`, `UNKNOWN-PATH`, `BLOCKED`, `BLOCKED-REQUEST`).

## Если нужно перегенерировать секрет
Спросить Сашу явно — старые ссылки перестанут работать. Процедура:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))" > ~/services/obsidian-redirect/.secret
chmod 600 ~/services/obsidian-redirect/.secret
systemctl --user restart obsidian-redirect.service
```

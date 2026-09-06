#!/usr/bin/env python3
"""Render Hermes kanban board as a PNG column card image (for Telegram).

Reads `hermes kanban list --json`, groups cards by status, draws columns with
coloured cards, saves to a PNG. Telegram renders it as a native photo.
Wrap in skill `kanban-board-image`.

Usage:
    python3 kanban_render.py [output_path] [statuses_csv]
"""
import json, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

def load_font(size):
    for p in ["/usr/share/fonts/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()

def render(out="/tmp/kanban_board.png", statuses=None):
    r = subprocess.run(["hermes", "kanban", "list", "--json"],
                       capture_output=True, text=True)
    try:
        cards = json.loads(r.stdout)
    except Exception as e:
        print("parse error:", e, file=sys.stderr)
        print(r.stdout[:500], file=sys.stderr)
        return 1

    order = ["triage", "todo", "ready", "running", "review", "blocked",
             "done", "scheduled", "archived"]
    color = {
        "triage": (230, 230, 230), "todo": (230, 240, 255),
        "ready": (255, 245, 210), "running": (210, 240, 255),
        "review": (240, 220, 255), "blocked": (255, 215, 215),
        "done": (210, 245, 215), "scheduled": (235, 235, 250),
        "archived": (200, 200, 200)}
    cols = {}
    for c in cards:
        st = c.get("status")
        if statuses and st not in statuses:
            continue
        cols.setdefault(st, []).append(c)

    def sortkey(s):
        return order.index(s) if s in order else 99
    active = sorted([(s, l) for s, l in cols.items() if l], key=lambda x: sortkey(x[0]))

    COL_W, HDR, PAD, CARD_H, GAP = 240, 40, 10, 120, 14
    n = len(active) if active else 1
    W = n * COL_W + (n + 1) * PAD
    H = HDR + 60 + max((len(l) for _, l in active), default=1) * (CARD_H + GAP) + 40
    img = Image.new("RGB", (W, H), (250, 250, 250))
    d = ImageDraw.Draw(img)
    f_h = load_font(14); f_s = load_font(12); f_t = load_font(10)

    x = PAD
    for st, lst in active:
        y = HDR
        d.rectangle([x, y, x + COL_W - 4, y + 26], fill=color.get(st, (220, 220, 220)))
        d.text((x + 6, y + 5), f"{st.upper()} ({len(lst)})", fill=(30, 30, 30), font=f_h)
        y += 34
        for c in lst:
            text = c.get("title", "")
            d.rectangle([x, y, x + COL_W - 4, y + CARD_H], fill=(255, 255, 255), outline=(0, 0, 0))
            d.rectangle([x, y, x + COL_W - 4, y + 3], fill=color.get(st, (200, 200, 200)))
            words = text.split(); lines = []; cur = ""
            for w in words:
                if len(cur) + len(w) + 1 <= 38:
                    cur = (cur + " " + w).strip()
                else:
                    lines.append(cur); cur = w
            lines.append(cur)
            yy = y + 8
            for ln in lines[:4]:
                d.text((x + 6, yy), ln, fill=(20, 20, 20), font=f_s); yy += 14
            d.text((x + 6, y + CARD_H - 14), f"#{c.get('id','')}",
                   fill=(120, 120, 120), font=f_t)
            y += CARD_H + GAP
        x += COL_W + PAD

    img.save(out)
    sys.stdout.write(out + "\n")
    return 0

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/kanban_board.png"
    statuses = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    raise SystemExit(render(out, statuses))

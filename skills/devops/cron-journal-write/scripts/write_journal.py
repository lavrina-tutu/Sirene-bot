#!/usr/bin/env python3
"""Записать строку в ~/.hermes/cron-journal.md.

Usage:
    python3 write_journal.py --job "имя задачи" --status OK --tl-dr "краткий итог" --output "путь к output"
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True, help="Имя крон-задачи")
    ap.add_argument("--status", choices=["OK", "PROBLEM"], default="OK")
    ap.add_argument("--tl-dr", required=True, help="Краткий итог (макс 80 символов)")
    ap.add_argument("--output", default="-", help="Путь к output-файлу крона")
    args = ap.parse_args()

    journal = Path.home() / ".hermes" / "cron-journal.md"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    tl_dr = args.tl_dr[:80]
    line = f"- {now} | {args.job} | {args.status} | {tl_dr} | output: {args.output}\n"

    try:
        content = journal.read_text(encoding="utf-8") if journal.exists() else ""
        lines = content.splitlines(keepends=True)
        header_end = 5  # строки 0-4: шапка файла
        body = lines[header_end:]
        body = body[-49:] if len(body) >= 49 else body
        body.append(line)
        new_content = "".join(lines[:header_end]) + "".join(body)
        journal.write_text(new_content, encoding="utf-8")
        print(f"Journal updated: {line.strip()}")
    except Exception as e:
        print(f"[warn] journal write failed: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()

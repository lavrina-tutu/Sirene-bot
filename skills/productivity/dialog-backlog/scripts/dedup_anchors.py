#!/usr/bin/env python3
"""
dedup_anchors.py — найти и перенумеровать дублирующиеся ^bk-NNN якоря в dialog-backlog.md.

Алгоритм:
- Для каждого anchor — оставить ПЕРВОЕ вхождение (правильное), второму дать новый номер.
- Новые номера идут с max_existing + 1.
- Обновляет next_id в frontmatter.
- Создаёт .bak перед записью.

Usage:
    python dedup_anchors.py [--file PATH] [--dry-run]
"""
import re
import shutil
import argparse
from pathlib import Path

DEFAULT_FILE = Path.home() / "WorkVault" / "Hermes-Backlog" / "dialog-backlog.md"
ANCHOR_RE = re.compile(r'\^(bk-\d+)')
FM_NEXT_ID_RE = re.compile(r'(next_id:\s*)(\d+)')


def find_duplicates(lines):
    seen = {}
    duplicates = {}
    for i, line in enumerate(lines):
        m = ANCHOR_RE.search(line)
        if not m:
            continue
        anchor = m.group(1)
        if anchor in seen:
            duplicates[i] = anchor
        else:
            seen[anchor] = i
    return seen, duplicates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(DEFAULT_FILE))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = Path(args.file)
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")

    seen, duplicates = find_duplicates(lines)

    if not duplicates:
        print("✅ Дублей нет.")
        return

    all_nums = [int(a.split("-")[1]) for a in seen]
    next_new = max(all_nums) + 1

    print(f"Найдено дублей: {len(duplicates)}")
    replacements = {}
    for idx, old_anchor in sorted(duplicates.items()):
        new_anchor = f"bk-{next_new:03d}"
        replacements[idx] = (old_anchor, new_anchor)
        print(f"  строка {idx+1}: ^{old_anchor} → ^{new_anchor}")
        next_new += 1

    if args.dry_run:
        print("(dry-run, файл не изменён)")
        return

    new_lines = list(lines)
    for idx, (old, new) in replacements.items():
        new_lines[idx] = new_lines[idx].replace(f"^{old}", f"^{new}", 1)

    new_text = "\n".join(new_lines)
    new_text = FM_NEXT_ID_RE.sub(lambda m: f"{m.group(1)}{next_new}", new_text, count=1)

    shutil.copy2(path, str(path) + ".bak")
    path.write_text(new_text, encoding="utf-8")
    print(f"✅ Записано. Новый next_id={next_new}. Бэкап: {path}.bak")


if __name__ == "__main__":
    main()

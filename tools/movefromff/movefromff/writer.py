"""Атомарная запись 3 markdown-файлов на встречу (v2.0, без SHA-256)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Dict

from .ff_schema import FFMeeting
from .filename import build_filename
from .renderer import render_actions, render_summary, render_transcript


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """tmp + os.replace — атомарная запись текста."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=".tmp_", suffix=".part", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as f:
            f.write(content)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass


def write_meeting_files(meeting: FFMeeting, out_dir: Path) -> Dict[str, str]:
    """Отрендерить и атомарно записать 3 файла на встречу.

    При ошибке — удалить все уже записанные файлы (rollback) и пробросить
    исключение наверх (ТЗ §3, шаг 3.4).

    Возвращает dict[kind → filename] (только имя, без пути).
    """
    dt = meeting.meeting_datetime
    title = meeting.display_title
    plan = {
        "transcript": (build_filename(dt, title, "transcript"), render_transcript(meeting)),
        "summary": (build_filename(dt, title, "summary"), render_summary(meeting)),
        "actions": (build_filename(dt, title, "actions"), render_actions(meeting)),
    }

    written: Dict[str, str] = {}
    written_paths = []
    try:
        for kind, (name, content) in plan.items():
            target = out_dir / name
            atomic_write_text(target, content)
            written_paths.append(target)
            written[kind] = name
    except Exception:
        # Rollback: подчистить частично записанные файлы.
        for p in written_paths:
            try:
                if p.exists():
                    p.unlink()
            except OSError:
                pass
        raise

    return written

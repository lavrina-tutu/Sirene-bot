"""MPP default calendar → calendarsData for gantt-chart-planner."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path


def _ensure_jvm() -> None:
    import mpxj  # noqa: F401
    import jpype
    import jpype.imports  # noqa: F401

    if not jpype.isJVMStarted():
        jpype.startJVM()


def _to_str(x) -> str | None:
    return None if x is None else str(x)


def base_recurrent_intervals() -> list[dict]:
    return [
        {"recurrentStartDate": "at 12:00", "recurrentEndDate": "at 13:00", "isWorking": False},
        {"recurrentStartDate": "at 18:00", "recurrentEndDate": "at 09:00", "isWorking": False},
        {"recurrentStartDate": "on Sun", "recurrentEndDate": "on Mon", "isWorking": False},
        {"recurrentStartDate": "on Sat", "recurrentEndDate": "on Sun", "isWorking": False},
    ]


def calendar_from_mpp(mpp_path: Path) -> list[dict]:
    _ensure_jvm()
    from org.mpxj.reader import UniversalProjectReader

    pj = UniversalProjectReader().read(str(mpp_path))
    cal = pj.getDefaultCalendar()
    intervals = base_recurrent_intervals()
    for x in cal.getCalendarExceptions():
        if not x.getWorking():
            f = date.fromisoformat(_to_str(x.getFromDate()))
            t = date.fromisoformat(_to_str(x.getToDate()))
            intervals.append(
                {
                    "startDate": f.isoformat() + " 00:00",
                    "endDate": (t + timedelta(days=1)).isoformat() + " 00:00",
                    "isWorking": False,
                }
            )
    return [{"id": "general", "name": "General", "unspecifiedTimeIsWorking": True, "intervals": intervals}]

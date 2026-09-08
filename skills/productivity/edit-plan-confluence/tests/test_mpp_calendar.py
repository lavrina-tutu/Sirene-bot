from __future__ import annotations

import pytest

from mpp_calendar import base_recurrent_intervals, calendar_from_mpp


def test_base_recurrent_intervals():
    ivs = base_recurrent_intervals()
    assert len(ivs) == 4
    lunch = ivs[0]
    assert lunch["recurrentStartDate"] == "at 12:00"
    assert lunch["recurrentEndDate"] == "at 13:00"
    night = ivs[1]
    assert night["recurrentStartDate"] == "at 18:00"
    assert night["recurrentEndDate"] == "at 09:00"


@pytest.mark.slow
def test_calendar_from_mpp_fixture(mpp_fixture):
    cal = calendar_from_mpp(mpp_fixture)
    assert len(cal) == 1
    assert cal[0]["id"] == "general"
    intervals = cal[0]["intervals"]
    assert len(intervals) > 4
    exceptions = [i for i in intervals if "startDate" in i]
    assert exceptions
    for ex in exceptions:
        assert ex["endDate"].endswith("00:00")
        assert ex["isWorking"] is False

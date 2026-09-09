"""Follow policy classification."""
from __future__ import annotations

from deepmine.follow import classify_outbound, is_denylist_title, parse_follow_outbound, stub_reason
from deepmine.project_config import FollowPolicy


def test_parse_follow_outbound():
  body = "See [link](https://dom.tutu.ru/pages/viewpage.action?pageId=123456)"
  assert "123456" in parse_follow_outbound(body)


def test_denylist_title():
  policy = FollowPolicy(denylist_title_substrings=["шаблон ПРО"])
  assert is_denylist_title("Новый шаблон ПРО v2", policy)


def test_classify_pull_vs_stub():
  policy = FollowPolicy(allowed_spaces=["DPAN", "PMO"], max_outbound_pull=24)
  action, reason = classify_outbound(
    "1", space="DPAN", title="Brief", policy=policy, known_spaces={"DPAN"}, pull_count=0,
  )
  assert action == "pull"
  assert reason is None
  action2, reason2 = classify_outbound(
    "2", space="OTHER", title="X", policy=policy, known_spaces={"DPAN"}, pull_count=0,
  )
  assert action2 == "stub"
  assert reason2


def test_stub_reason_over_limit():
  policy = FollowPolicy()
  assert "max_outbound_pull" in stub_reason(space="DPAN", title="T", policy=policy, over_limit=True)

"""cmd_mine must not call run_digest."""
from __future__ import annotations

from unittest.mock import patch

from deepmine.cli import cmd_mine
import argparse


def test_mine_does_not_call_digest(mini_workvault):
  args = argparse.Namespace(
    slug="TestProject",
    workvault=str(mini_workvault),
    dry_run=True,
    json_out=False,
    skip_llm=True,
    skip_a=True,
    skip_b=True,
    skip_c=True,
    skip_d=True,
    skip_e=False,
    skip_entity=True,
    extract_tables=False,
  )
  with patch("deepmine.cli.cmd_collect", return_value=0):
    with patch("deepmine.cli.cmd_graph", return_value=0):
      with patch("deepmine.cli.cmd_facts", return_value=0):
        with patch("deepmine.cli.cmd_charter", return_value=0):
          with patch("deepmine.cli.cmd_architecture", return_value=0):
            with patch("deepmine.digest_run.run_digest") as mock_digest:
              rc = cmd_mine(args)
  assert rc == 0
  mock_digest.assert_not_called()

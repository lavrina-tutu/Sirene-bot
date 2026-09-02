"""T3: fail-loud on Confluence errors."""
import pytest

from deepmine.fail import ConfluenceDownError, EXIT_CONFLUENCE, confluence_down
from deepmine.confluence_pull import _check_pull_output, PullResult


def test_ping_false_exit_3():
  with pytest.raises(ConfluenceDownError) as exc:
    confluence_down("ping failed")
  assert exc.value.exit_code == EXIT_CONFLUENCE


def test_pull_403_fails():
  result = PullResult(page_id="1", returncode=0, stdout="", stderr="HTTP 403 Forbidden")
  with pytest.raises(ConfluenceDownError):
    _check_pull_output(result)


def test_pull_nonzero_fails():
  result = PullResult(page_id="1", returncode=1, stdout="", stderr="error")
  with pytest.raises(ConfluenceDownError):
    _check_pull_output(result)

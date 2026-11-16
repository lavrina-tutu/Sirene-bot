"""Real process ownership, busy refusal and automatic release after SIGKILL."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from plan_lock import PlanLockBusy, batch_lock
from test_plan_batch import batch_case, create

pytestmark = pytest.mark.archive_integration


def test_lock_busy_independent_process_and_release_after_death(tmp_path):
    db = tmp_path/"state/index.sqlite"
    ready = tmp_path/"ready"
    scripts = Path(__file__).resolve().parents[1]/"scripts"
    code = "import sys,time;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from plan_lock import batch_lock\nwith batch_lock(Path(sys.argv[2]),'same'):\n Path(sys.argv[3]).touch()\n time.sleep(30)\n"
    child = subprocess.Popen([sys.executable,"-c",code,str(scripts),str(db),str(ready)], stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic()+10
        while not ready.exists():
            assert child.poll() is None and time.monotonic() < deadline
            time.sleep(.01)
        with pytest.raises(PlanLockBusy):
            with batch_lock(db, "same"): pass
        # Different batches remain independent; this does not parallelize MPP in
        # the same batch or allow an unrelated cache-dir to bypass ownership.
        with batch_lock(db, "different"): pass
    finally:
        child.kill(); child.wait(timeout=5)
    with batch_lock(db, "same"): pass


def test_two_batch_handlers_busy_without_duplicate_arrivals(batch_case, tmp_path):
    import plan_batch as pb
    from mofs_index.db import connect_durable
    from mofs_index.plan import query as q
    context, sources = batch_case
    first = create(batch_case)
    ready = tmp_path/"busy-ready"
    cfg = tmp_path/"busy.json"
    cfg.write_text(json.dumps({"db":str(context.db),"sources":[str(p) for p in sources]}))
    scripts = str(Path(__file__).resolve().parents[1]/"scripts")
    code = "import sys,json,time;from pathlib import Path;sys.path[:0]=" + repr([scripts, '/home/tkachenkoav/USERTOOLS/MofsIndex']) + ";import plan_batch as pb\nreal=pb._current\ndef hold(conn,batch_id,*args):\n Path(sys.argv[2]).touch()\n time.sleep(30)\n return real(conn,batch_id,*args)\npb._current=hold\ncfg=json.loads(Path(sys.argv[1]).read_text());pb.resume_batch('test',db_path=cfg['db'])"
    child = subprocess.Popen([sys.executable,"-c",code,str(cfg),str(ready)], stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic()+10
        while not ready.exists():
            assert child.poll() is None and time.monotonic() < deadline
            time.sleep(.01)
        busy = pb.resume_batch("test", context=context)
        assert busy["exit_code"] == 4 and busy["error"]["code"] == "batch_busy", busy
        busy = create(batch_case)
        assert busy["exit_code"] == 4 and busy["error"]["code"] == "batch_busy"
        assert pb.show_batch("test", context=context)["items"] == first["items"]
    finally:
        child.kill(); child.wait(timeout=5)
    assert pb.resume_batch("test", context=context)["exit_code"] == 0
    c = connect_durable(context.db)
    assert len(q.get_batch_items(c,"test")) == 3
    c.close()

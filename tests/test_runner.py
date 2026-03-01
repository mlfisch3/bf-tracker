from datetime import datetime, timedelta, timezone

from tracker.runner import should_run


def test_should_run_force() -> None:
    cfg = {"force_run": True, "kill_switch": False, "state": "stopped"}
    assert should_run(cfg, {}) is True


def test_should_run_interval() -> None:
    now = datetime.now(timezone.utc)
    last = {"finished_at": (now - timedelta(minutes=31)).isoformat()}
    cfg = {"state": "running", "interval_minutes": 30, "kill_switch": False}
    assert should_run(cfg, last) is True


def test_should_run_wait() -> None:
    now = datetime.now(timezone.utc)
    last = {"finished_at": (now - timedelta(minutes=5)).isoformat()}
    cfg = {"state": "running", "interval_minutes": 30, "kill_switch": False}
    assert should_run(cfg, last) is False

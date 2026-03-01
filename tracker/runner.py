from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from .config import DATA_DIR, get_subforum_map, load_config, load_threads, save_threads, _save_json
from .fetcher import FetchError, fetch_page
from .parser import find_views_by_titles, normalize_title
from .rate_limit import RateLimiter
from .storage import append_sample, thread_id_for


LAST_RUN_PATH = DATA_DIR / "last_run.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_last_run(payload: dict[str, Any]) -> None:
    with LAST_RUN_PATH.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def load_last_run() -> dict[str, Any]:
    if not LAST_RUN_PATH.exists():
        return {}
    with LAST_RUN_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def should_run(tracker_cfg: dict[str, Any], last_run: dict[str, Any]) -> bool:
    # Ad hoc updates can run even if the tracker is paused/stopped.
    if tracker_cfg.get("kill_switch"):
        return False
    if tracker_cfg.get("force_run"):
        return True
    state = tracker_cfg.get("state", "stopped")
    if state != "running":
        return False
    if tracker_cfg.get("run_on_next"):
        return True
    interval = int(tracker_cfg.get("interval_minutes", 30))
    last_finished = last_run.get("finished_at")
    if not last_finished:
        return True
    try:
        last_dt = datetime.fromisoformat(last_finished)
    except ValueError:
        return True
    return datetime.now(timezone.utc) >= last_dt + timedelta(minutes=interval)


def next_run_at(tracker_cfg: dict[str, Any], last_run: dict[str, Any]) -> str | None:
    if tracker_cfg.get("state") != "running" or tracker_cfg.get("kill_switch"):
        return None
    interval = int(tracker_cfg.get("interval_minutes", 30))
    finished_at = last_run.get("finished_at")
    if not finished_at:
        return None
    try:
        finished_dt = datetime.fromisoformat(finished_at)
    except ValueError:
        return None
    return (finished_dt + timedelta(minutes=interval)).isoformat()


def ensure_thread_ids(threads_payload: dict[str, Any]) -> bool:
    changed = False
    for thread in threads_payload.get("threads", []):
        if not thread.get("id"):
            thread_id = thread_id_for(thread["title"], thread["subforum_key"])
            thread["id"] = thread_id
            thread.setdefault("created_at", utc_now())
            changed = True
    return changed


def group_threads(threads_payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for thread in threads_payload.get("threads", []):
        status = thread.get("status", "active")
        if status != "active":
            continue
        grouped[thread["subforum_key"]].append(thread)
    return grouped


def build_page_url(base: str, page: int) -> str:
    if page <= 1:
        return base
    if base.endswith("/"):
        return f"{base}page-{page}"
    return f"{base}/page-{page}"


def run() -> None:
    config = load_config()
    threads_payload = load_threads()
    if ensure_thread_ids(threads_payload):
        save_threads(threads_payload)

    tracker_cfg = config.tracker or {}
    last_run = load_last_run()
    run_summary: dict[str, Any] = {
        "started_at": utc_now(),
        "threads_checked": 0,
        "threads_found": 0,
        "errors": [],
        "state": tracker_cfg.get("state", "stopped"),
        "kill_switch": bool(tracker_cfg.get("kill_switch")),
    }

    if tracker_cfg.get("kill_switch"):
        run_summary["finished_at"] = utc_now()
        run_summary["note"] = "Kill switch enabled. Exiting without work."
        run_summary["next_run_at"] = None
        save_last_run(run_summary)
        return

    if not should_run(tracker_cfg, last_run):
        run_summary["finished_at"] = utc_now()
        run_summary["note"] = "Tracker idle. Waiting for next interval or manual run."
        run_summary["next_run_at"] = next_run_at(tracker_cfg, last_run)
        save_last_run(run_summary)
        return

    limiter = RateLimiter(
        max_requests_per_minute=config.global_config.max_requests_per_minute,
        min_delay=config.global_config.min_delay_seconds,
        max_delay=config.global_config.max_delay_seconds,
    )
    subforum_map = get_subforum_map(config)
    grouped = group_threads(threads_payload)

    force_ids = set(tracker_cfg.get("force_thread_ids", []))
    if force_ids:
        filtered = defaultdict(list)
        for subforum_key, items in grouped.items():
            filtered[subforum_key] = [t for t in items if t.get("id") in force_ids]
        grouped = filtered

    session = requests.Session()

    for subforum_key, threads in grouped.items():
        subforum = subforum_map.get(subforum_key)
        if not subforum:
            run_summary["errors"].append(
                {"subforum_key": subforum_key, "error": "Unknown subforum"}
            )
            continue
        target_titles = [t["title"] for t in threads]
        remaining = set(normalize_title(t) for t in target_titles)
        for page in range(1, subforum.max_pages_per_update + 1):
            if not remaining:
                break
            url = build_page_url(subforum.url, page)
            try:
                html = fetch_page(
                    session,
                    url,
                    limiter,
                    max_retries=config.global_config.max_retries,
                )
            except FetchError as exc:
                run_summary["errors"].append(
                    {"subforum_key": subforum_key, "error": str(exc)}
                )
                break
            found = find_views_by_titles(html, target_titles)
            for thread in threads:
                title = thread["title"]
                if normalize_title(title) not in remaining:
                    continue
                if title in found and found[title].get("views") is not None:
                    views = int(found[title]["views"])
                    position = found[title].get("position")
                    append_sample(thread["id"], title, views, page, position)
                    thread["last_seen_at"] = utc_now()
                    thread["last_view_count"] = views
                    thread["last_found_page"] = page
                    thread["last_found_above"] = position
                    run_summary["threads_found"] += 1
                    remaining.discard(normalize_title(title))
            run_summary["threads_checked"] += len(threads)

    tracker_cfg["run_on_next"] = False
    tracker_cfg["force_run"] = False
    tracker_cfg["force_thread_ids"] = []
    config_payload = {
        "schema_version": config.schema_version,
        "tracker": tracker_cfg,
        "global": {
            "max_requests_per_minute": config.global_config.max_requests_per_minute,
            "min_delay_seconds": config.global_config.min_delay_seconds,
            "max_delay_seconds": config.global_config.max_delay_seconds,
            "max_retries": config.global_config.max_retries,
        },
        "subforums": [
            {
                "key": item.key,
                "name": item.name,
                "url": item.url,
                "max_pages_per_update": item.max_pages_per_update,
            }
            for item in config.subforums
        ],
    }
    _save_json(DATA_DIR / "config.json", config_payload)

    save_threads(threads_payload)
    run_summary["finished_at"] = utc_now()
    run_summary["next_run_at"] = next_run_at(tracker_cfg, run_summary)
    save_last_run(run_summary)


if __name__ == "__main__":
    run()

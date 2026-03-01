from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .config import DATA_DIR, get_subforum_map, load_config, load_threads, save_threads
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

    limiter = RateLimiter(
        max_requests_per_minute=config.global_config.max_requests_per_minute,
        min_delay=config.global_config.min_delay_seconds,
        max_delay=config.global_config.max_delay_seconds,
    )
    subforum_map = get_subforum_map(config)
    grouped = group_threads(threads_payload)

    session = requests.Session()
    run_summary: dict[str, Any] = {
        "started_at": utc_now(),
        "threads_checked": 0,
        "threads_found": 0,
        "errors": [],
    }

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
                if title in found and found[title] is not None:
                    views = int(found[title])
                    append_sample(thread["id"], title, views)
                    thread["last_seen_at"] = utc_now()
                    thread["last_view_count"] = views
                    thread["last_found_page"] = page
                    run_summary["threads_found"] += 1
                    remaining.discard(normalize_title(title))
            run_summary["threads_checked"] += len(threads)

    save_threads(threads_payload)
    run_summary["finished_at"] = utc_now()
    save_last_run(run_summary)


if __name__ == "__main__":
    run()

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from .config import load_samples, save_samples


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def thread_id_for(title: str, subforum_key: str) -> str:
    raw = f"{subforum_key}::{title}".encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()[:12]
    safe = "-".join(title.lower().split())
    safe = "".join(ch for ch in safe if ch.isalnum() or ch == "-")
    safe = safe[:40].strip("-")
    return f"{safe}-{digest}" if safe else digest


def append_sample(
    thread_id: str, title: str, views: int, page: int | None, above: int | None
) -> dict[str, Any]:
    payload = load_samples(thread_id)
    payload.setdefault("thread_id", thread_id)
    payload.setdefault("title", title)
    payload.setdefault("samples", [])
    payload["samples"].append(
        {"ts": utc_now(), "views": views, "page": page, "above": above}
    )
    save_samples(thread_id, payload)
    return payload

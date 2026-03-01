from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CONFIG_PATH = DATA_DIR / "config.json"
THREADS_PATH = DATA_DIR / "threads.json"
SAMPLES_DIR = DATA_DIR / "samples"


@dataclass
class GlobalConfig:
    max_requests_per_minute: int
    min_delay_seconds: float
    max_delay_seconds: float
    max_retries: int


@dataclass
class SubforumConfig:
    key: str
    name: str
    url: str
    max_pages_per_update: int


@dataclass
class AppConfig:
    schema_version: int
    tracker: dict[str, Any]
    global_config: GlobalConfig
    subforums: list[SubforumConfig]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    raw = _load_json(path)
    tracker = raw.get("tracker", {})
    global_raw = raw.get("global", {})
    global_cfg = GlobalConfig(
        max_requests_per_minute=int(global_raw.get("max_requests_per_minute", 12)),
        min_delay_seconds=float(global_raw.get("min_delay_seconds", 3)),
        max_delay_seconds=float(global_raw.get("max_delay_seconds", 9)),
        max_retries=int(global_raw.get("max_retries", 2)),
    )
    subforums = [
        SubforumConfig(
            key=item["key"],
            name=item["name"],
            url=item["url"],
            max_pages_per_update=int(item.get("max_pages_per_update", 3)),
        )
        for item in raw.get("subforums", [])
    ]
    return AppConfig(
        schema_version=int(raw.get("schema_version", 1)),
        tracker=tracker,
        global_config=global_cfg,
        subforums=subforums,
    )


def load_threads(path: Path = THREADS_PATH) -> dict[str, Any]:
    return _load_json(path)


def save_threads(payload: dict[str, Any], path: Path = THREADS_PATH) -> None:
    _save_json(path, payload)


def load_samples(thread_id: str) -> dict[str, Any]:
    path = SAMPLES_DIR / f"{thread_id}.json"
    if not path.exists():
        return {"thread_id": thread_id, "samples": []}
    return _load_json(path)


def save_samples(thread_id: str, payload: dict[str, Any]) -> None:
    path = SAMPLES_DIR / f"{thread_id}.json"
    _save_json(path, payload)


def get_subforum_map(config: AppConfig) -> dict[str, SubforumConfig]:
    return {item.key: item for item in config.subforums}

from __future__ import annotations

import re
from typing import Iterable, Optional

from bs4 import BeautifulSoup, Tag


_THREAD_LINK_RE = re.compile(r"/threads/")


def normalize_title(text: str) -> str:
    return " ".join(text.split()).strip()


def parse_abbrev_number(raw: str) -> Optional[int]:
    if not raw:
        return None
    text = raw.strip().replace(",", "")
    match = re.match(r"^(\d+(?:\.\d+)?)([KkMm])?$", text)
    if not match:
        digits = re.sub(r"[^0-9]", "", text)
        return int(digits) if digits else None
    value = float(match.group(1))
    suffix = match.group(2)
    if suffix:
        if suffix.lower() == "k":
            value *= 1_000
        elif suffix.lower() == "m":
            value *= 1_000_000
    return int(value)


def extract_views(container: Tag) -> Optional[int]:
    for dt in container.find_all("dt"):
        label = normalize_title(dt.get_text(" "))
        if label.lower() == "views":
            dd = dt.find_next_sibling("dd")
            if dd:
                return parse_abbrev_number(dd.get_text(" "))
    return None


def _candidate_containers(soup: BeautifulSoup) -> list[Tag]:
    candidates = soup.select(".structItem--thread, .discussionListItem")
    if candidates:
        return list(candidates)
    # Fallback: find parents of thread links.
    containers: list[Tag] = []
    seen: set[int] = set()
    for link in soup.find_all("a", href=_THREAD_LINK_RE):
        container = link.find_parent(
            class_=lambda c: c and ("structItem" in c or "discussionListItem" in c)
        )
        if container is None:
            container = link.find_parent(["article", "li", "div"])
        if container is None:
            continue
        ident = id(container)
        if ident in seen:
            continue
        seen.add(ident)
        containers.append(container)
    return containers


def _extract_title(container: Tag) -> Optional[str]:
    title_tag = container.select_one(".structItem-title a")
    if title_tag is None:
        title_tag = container.find("a", href=_THREAD_LINK_RE)
    if title_tag is None:
        return None
    title = normalize_title(title_tag.get_text(" "))
    return title or None


def parse_thread_items(html: str) -> list[dict[str, Optional[int]]]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for index, container in enumerate(_candidate_containers(soup)):
        title = _extract_title(container)
        if not title:
            continue
        views = extract_views(container)
        items.append({"title": title, "views": views, "position": index})
    return items


def find_views_by_titles(
    html: str, titles: Iterable[str]
) -> dict[str, dict[str, Optional[int]]]:
    normalized_targets = {normalize_title(t): t for t in titles}
    results: dict[str, dict[str, Optional[int]]] = {}
    for item in parse_thread_items(html):
        title = normalize_title(item["title"])
        if title in normalized_targets:
            original = normalized_targets[title]
            results[original] = {
                "views": item.get("views"),
                "position": item.get("position"),
            }
    return results

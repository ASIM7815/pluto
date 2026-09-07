"""Entity extraction for PLUTO's local NLU.

Rule-based + dictionary extraction of the *things* users mention in commands:
applications, websites, file/folder paths, numbers, ordinals, recipients,
search queries, etc. This is deliberately deterministic and offline.

The precise behaviour (e.g. resolving a relative path) is still the job of the
planner (``app/agent/nlu.py``); this module provides the structured entity
snapshot the brain reports alongside an intent so the UI and the planner both
have a shared, inspectable view of what was said.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

# Spoken locations -> home-relative folder (matches the planner's aliases).
_DIR_ALIASES: Dict[str, str] = {
    "desktop": "~/Desktop",
    "documents": "~/Documents",
    "document": "~/Documents",
    "docs": "~/Documents",
    "downloads": "~/Downloads",
    "download": "~/Downloads",
    "pictures": "~/Pictures",
    "photos": "~/Pictures",
    "picture": "~/Pictures",
    "music": "~/Music",
    "videos": "~/Videos",
    "video": "~/Videos",
    "movies": "~/Videos",
    "projects": "~/Projects",
    "project": "~/Projects",
    "home": "~",
    "home folder": "~",
    "home directory": "~",
}

# Ordinal words/numbers -> zero-based index (used for "the second video").
ORDINAL_TO_INDEX: Dict[str, int] = {
    "first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2,
    "fourth": 3, "4th": 3, "fifth": 4, "5th": 4, "sixth": 5, "6th": 5,
    "seventh": 6, "7th": 6, "eighth": 7, "8th": 7, "ninth": 8, "9th": 8,
    "tenth": 9, "10th": 9,
}

# Number words -> value (for volume, counts, "first/second" style numbers).
_NUMBER_WORDS: Dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
}

_SCREENSHOT_AREA_WORDS = {
    "window": ("window", "active window", "this window", "current window"),
    "select": ("select", "selection", "region", "area", "a part"),
}


def _apps_and_sites() -> Dict[str, Dict[str, str]]:
    """Lazy single-source lookup of app/website aliases from the tool layer."""
    apps: Dict[str, str] = {}
    sites: Dict[str, str] = {}
    try:
        from app.tools.application_tools import APP_MAPPINGS, KNOWN_WEBSITES

        for alias, exec_ in APP_MAPPINGS.items():
            apps[alias] = exec_
        for alias, url in KNOWN_WEBSITES.items():
            sites[alias] = url
    except Exception:  # noqa: BLE001 - never block extraction on optional imports
        logger.debug("entities_app_sources_unavailable")
    try:
        from app.tools.browser import _SITE_URLS

        for alias, url in _SITE_URLS.items():
            sites[alias] = url
    except Exception:  # noqa: BLE001
        logger.debug("entities_site_sources_unavailable")
    return {"apps": apps, "sites": sites}


def _find_longest_alias(text: str, aliases: Dict[str, str]) -> Optional[tuple]:
    """Return ``(matched_alias, canonical)`` for the longest alias in ``text``."""
    t = text.lower()
    best: Optional[tuple] = None
    for alias in aliases:
        if re.search(rf"\b{re.escape(alias)}\b", t):
            if best is None or len(alias) > len(best[0]):
                best = (alias, aliases[alias])
    return best


def extract_entities(text: str) -> Dict[str, Any]:
    """Return a structured dict of entities found in a command.

    Keys present when relevant: app, site, url, directory, file, numbers,
    ordinal, recipient, query, volume, area, clipboard_text, process.
    """
    if not text:
        return {}
    entities: Dict[str, Any] = {}
    t = text.lower()
    sources = _apps_and_sites()

    # --- application -----------------------------------------------------
    app_hit = _find_longest_alias(text, sources["apps"])
    if app_hit:
        # Don't treat a known site alias (e.g. "youtube") as a desktop app here.
        if not re.search(rf"\b{re.escape(app_hit[0])}\b", " ".join(sources["sites"])):
            entities["app"] = app_hit[1]

    # --- website ----------------------------------------------------------
    site_hit = _find_longest_alias(text, sources["sites"])
    if site_hit:
        entities["site"] = site_hit[0]

    # --- explicit URL -----------------------------------------------------
    m_url = re.search(r"https?://\S+", text)
    if m_url:
        entities["url"] = m_url.group(0).rstrip(".,;!?")

    # --- directory / path -------------------------------------------------
    m_path = re.search(r"(?:/|~/)[\w./~-]+", text)
    if m_path:
        entities["path"] = os.path.expanduser(m_path.group(0)).rstrip("/")
    else:
        best_dir = None
        for alias, folder in _DIR_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", t):
                if best_dir is None or len(alias) > len(best_dir):
                    best_dir = alias
                    chosen = folder
        if best_dir is not None:
            entities["directory"] = chosen

    # --- file name (after called/named or a *.ext token) ------------------
    quoted = re.search(r"[\"']([^\"']+)[\"']", text)
    if quoted and "." in quoted.group(1):
        entities["file"] = quoted.group(1).strip()
    m_file = re.search(
        r"(?:called|named)\s+([\w.\- ]+?)(?=\s+(?:in|inside|under|on|at|to|for|please|and|then|\s*$))",
        text, re.I,
    )
    if m_file:
        name = m_file.group(1).strip().strip(" .")
        if name and name.lower() not in ("a folder", "folder", "the folder",
                                         "a file", "file", "the file"):
            entities["file"] = name
    m_ext = re.search(r"([\w.\-]+\.(?:txt|md|pdf|docx?|png|jpg|jpeg|py|json|csv|zip|xlsx?|ppt?x?))", text, re.I)
    if m_ext and "file" not in entities:
        entities["file"] = m_ext.group(1)

    # --- numbers & ordinals ------------------------------------------------
    nums = re.findall(r"\b\d{1,3}\b", t)
    if nums:
        entities["numbers"] = [int(n) for n in nums][:6]
    for word, value in _NUMBER_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", t):
            entities.setdefault("numbers", []).append(value)
    for word, idx in ORDINAL_TO_INDEX.items():
        if re.search(rf"\b{re.escape(word)}\b", t):
            entities["ordinal"] = idx
            break

    # --- volume ------------------------------------------------------------
    m_vol = re.search(r"(\d{1,3})\s*%?", t)
    if m_vol and any(k in t for k in ("volume", "sound", "audio", "vol", "louder", "quieter")):
        entities["volume"] = max(0, min(100, int(m_vol.group(1))))
    if any(k in t for k in ("mute", "muted")):
        entities["volume_action"] = "mute"
    if any(k in t for k in ("unmute", "un-mute", "sound back on")):
        entities["volume_action"] = "unmute"

    # --- screenshot area ---------------------------------------------------
    if any(k in t for k in ("screenshot", "screen capture", "capture", "snapshot")):
        if any(k in t for k in _SCREENSHOT_AREA_WORDS["window"]):
            entities["area"] = "window"
        elif any(k in t for k in _SCREENSHOT_AREA_WORDS["select"]):
            entities["area"] = "select"
        else:
            entities["area"] = "full"

    # --- clipboard text -----------------------------------------------------
    if "clipboard" in t or "clip board" in t:
        if quoted:
            entities["clipboard_text"] = quoted.group(1).strip()
        else:
            m_clip = re.search(
                r"copy\s+(?:the\s+)?(.+?)(?:\s+(?:to|on|onto|into)\s+the? clipboard)", t)
            if m_clip:
                entities["clipboard_text"] = m_clip.group(1).strip()

    # --- search query -------------------------------------------------------
    m_query = re.search(
        r"(?:search\s+(?:for\s+)?|look\s+(?:up|for)\s+|find\s+|google\s+)"
        r"(.+?)(?:\s+(?:on|in|for)\s+\w+|\s+(?:youtube|google|github|reddit|wikipedia)$|$)",
        text, re.I,
    )
    if m_query:
        entities["query"] = m_query.group(1).strip(" ,.;:!?")

    # --- recipient (after "to" / "message X" / app-verb) --------------------
    if any(k in t for k in ("message", "text", "send", "whatsapp", "telegram", "signal")):
        m_recip = re.search(
            r"(?:to|message|text)(?:\s+(?:on|via|using))?\s+([a-z][a-z0-9_.\- ]{0,30}?)"
            r"(?:\s+(?:saying|that|that says|the message|:|,)\b)", t)
        if m_recip:
            entities["recipient"] = m_recip.group(1).strip()

    # --- process name ---------------------------------------------------------
    m_proc = re.search(
        r"(?:kill|stop|end|terminate|is|are|check)\s+(?:the\s+)?(?:process|task|application|program|app)?"
        r"\s*(?:named|called)?\s*([a-z0-9_.-]{2,40})", t)
    if m_proc:
        entities["process"] = m_proc.group(1).strip()

    return entities


def summarize_entities(entities: Dict[str, Any]) -> str:
    """A short human-readable summary of the extracted entities."""
    if not entities:
        return ""
    parts = []
    if entities.get("app"):
        parts.append(f"app={entities['app']}")
    if entities.get("site"):
        parts.append(f"site={entities['site']}")
    if entities.get("url"):
        parts.append(f"url={entities['url']}")
    if entities.get("file"):
        parts.append(f"file={entities['file']}")
    if entities.get("directory"):
        parts.append(f"dir={entities['directory']}")
    if entities.get("query"):
        parts.append(f"query={entities['query']}")
    if entities.get("recipient"):
        parts.append(f"to={entities['recipient']}")
    if entities.get("volume") is not None:
        parts.append(f"volume={entities['volume']}")
    if entities.get("ordinal") is not None:
        parts.append(f"index={entities['ordinal']}")
    return ", ".join(parts)

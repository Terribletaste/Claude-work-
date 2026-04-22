#!/usr/bin/env python3
"""
convert_events.py
=================

Convert NYC_Events_[Month].docx files into structured JSON for use with
event_ranker.html.

Usage:
    python convert_events.py NYC_Events_April.docx
    # -> writes events_april.json to the same directory

Requirements:
    python-docx  (pip install python-docx)
    Python 3.8+
"""

import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

try:
    from docx import Document
except ImportError:
    sys.stderr.write(
        "Error: python-docx is required. Install with:\n"
        "    pip install python-docx\n"
    )
    sys.exit(1)


DAY_NAMES = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
MONTHS = {m.lower(): i + 1 for i, m in enumerate(MONTH_NAMES)}

DATE_HEADING_RE = re.compile(
    r"^\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*,\s*"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"(\d{1,2})\s*,\s*(\d{4})\s*$",
    re.IGNORECASE,
)


def parse_heading_date(text):
    m = DATE_HEADING_RE.match(text.strip())
    if not m:
        return None
    month_name, day, year = m.groups()
    try:
        return date(int(year), MONTHS[month_name.lower()], int(day))
    except (ValueError, KeyError):
        return None


def clean_title(raw):
    """Extract a clean ~80-char title from the first line of an event."""
    line = raw.strip().splitlines()[0] if raw.strip() else ""
    line = re.sub(r"^\s*sponsored\s*::\s*", "", line, flags=re.IGNORECASE)
    line = re.sub(
        r"^\s*\((?:thru|through|until)\s+[^)]+\)\s*:\s*",
        "", line, flags=re.IGNORECASE,
    )
    line = re.sub(
        r"^\s*\(?\s*(?:thru|through|until)\s+\d{1,2}/\d{1,2}(?:/\d{2,4})?\s*\)?\s*:\s*",
        "", line, flags=re.IGNORECASE,
    )
    line = re.sub(
        r"^\s*\(?\s*(?:thru|through|until)\s+[A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?\s*\)?\s*:\s*",
        "", line, flags=re.IGNORECASE,
    )
    line = re.sub(r"^\s*\d{1,2}/\d{1,2}(?:[-–]\d{1,2}/\d{1,2})?\s*:\s*", "", line)
    line = line.strip()
    if len(line) > 80:
        cut = line[:80]
        sp = cut.rfind(" ")
        if sp > 40:
            cut = cut[:sp]
        line = cut.rstrip(",;:-—– ") + "…"
    return line


def detect_ongoing(full_text):
    t = full_text.strip().lower()
    if not t:
        return False
    if t.startswith("thru ") or t.startswith("through ") or t.startswith("until "):
        return True
    if t.startswith("(thru") or t.startswith("(through"):
        return True
    if re.search(r"\b(?:thru|through|until)\s+[A-Za-z]+\s+\d", t):
        return True
    if re.search(r"\b(?:thru|through|until)\s+\d{1,2}/\d{1,2}", t):
        return True
    if re.search(r"\d{1,2}/\d{1,2}\s*[-–]\s*\d{1,2}/\d{1,2}", t):
        return True
    return False


def extract_venue(full_text):
    """Best-effort venue extraction. Returns None when nothing plausible is found."""
    m = re.search(r"@\s*([A-Z][A-Za-z0-9'&\-\. ]{2,60}?)(?=[.,;)\n])", full_text)
    if m:
        return m.group(1).strip().rstrip(".")
    m = re.search(r"\bat\s+([A-Z][A-Za-z0-9'&\-\. ]{2,60}?)(?=[.,;)\n])", full_text)
    if m:
        return m.group(1).strip().rstrip(".")
    return None


def paragraph_style(p):
    try:
        return (p.style.name or "").strip()
    except Exception:
        return ""


def derive_description(full_text):
    """Return everything after the first non-empty line, trimmed."""
    lines = [l for l in full_text.splitlines() if l.strip()]
    if len(lines) <= 1:
        return ""
    return "\n".join(lines[1:]).strip()


def parse_document(path):
    doc = Document(str(path))
    current_date = None
    events = []
    current = None
    current_saw_link = False

    def finalize():
        nonlocal current, current_saw_link
        if current is None:
            return
        full = "\n".join(current["source_lines"]).strip()
        current["full_text"] = full
        current["title"] = clean_title(full)
        current["description"] = derive_description(full)
        current["venue"] = extract_venue(full)
        current["ongoing"] = detect_ongoing(full)
        events.append(current)
        current = None
        current_saw_link = False

    def start_event(text):
        nonlocal current, current_saw_link
        current = {
            "date": current_date.isoformat(),
            "day_of_week": DAY_NAMES[current_date.weekday()],
            "source_lines": [text],
        }
        current_saw_link = False

    for p in doc.paragraphs:
        text = (p.text or "").strip()
        style = paragraph_style(p)
        style_lower = style.lower()

        if style_lower.startswith("heading 1"):
            finalize()
            d = parse_heading_date(text)
            if d is not None:
                current_date = d
            continue

        if not text:
            if current is not None and current_saw_link:
                finalize()
            continue

        if style_lower == "list paragraph":
            finalize()
            if current_date is None:
                continue
            start_event(text)
            continue

        # Normal / other body paragraphs
        if text.lower() == "link":
            if current is not None:
                current_saw_link = True
            continue

        if current is not None:
            current["source_lines"].append(text)
        else:
            if current_date is None:
                continue
            start_event(text)

    finalize()
    return events


def format_weekend_label(idx, days):
    if not days:
        return f"Weekend {idx}"
    first, last = days[0], days[-1]
    if first == last:
        return f"Weekend {idx}: {first.strftime('%a')} {first.strftime('%b')} {first.day}"
    if first.month == last.month:
        return (
            f"Weekend {idx}: {first.strftime('%a')} {first.strftime('%b')} {first.day} "
            f"– {last.strftime('%a')} {last.strftime('%b')} {last.day}"
        )
    return (
        f"Weekend {idx}: {first.strftime('%a')} {first.strftime('%b')} {first.day} "
        f"– {last.strftime('%a')} {last.strftime('%b')} {last.day}"
    )


def assign_ids(events, weekend_idx):
    out = []
    for j, e in enumerate(events, start=1):
        out.append({
            "id": f"w{weekend_idx}-{j:03d}",
            "title": e["title"],
            "date": e["date"],
            "day_of_week": e["day_of_week"],
            "venue": e.get("venue"),
            "description": e.get("description", ""),
            "ongoing": bool(e.get("ongoing", False)),
        })
    return out


def group_into_weekends(events):
    """Group events into Fri/Sat/Sun weekends.

    A weekend is Fri+Sat+Sun of the same calendar week. Partial weekends at
    the start (Sat-only or Sat+Sun) or end (Fri-only) of the range are kept.
    """
    if not events:
        return []

    by_date = {}
    for e in events:
        d = date.fromisoformat(e["date"])
        by_date.setdefault(d, []).append(e)

    min_d = min(by_date)
    max_d = max(by_date)

    weekends = []
    current_wk = None
    d = min_d
    while d <= max_d:
        wd = d.weekday()  # Mon=0 .. Sun=6; Fri=4, Sat=5, Sun=6
        if wd == 4:
            if current_wk is not None:
                weekends.append(current_wk)
            current_wk = {"days": [d], "events": list(by_date.get(d, []))}
        elif wd == 5:
            if current_wk is None:
                current_wk = {"days": [], "events": []}
            current_wk["days"].append(d)
            current_wk["events"].extend(by_date.get(d, []))
        elif wd == 6:
            if current_wk is None:
                current_wk = {"days": [], "events": []}
            current_wk["days"].append(d)
            current_wk["events"].extend(by_date.get(d, []))
            weekends.append(current_wk)
            current_wk = None
        d += timedelta(days=1)
    if current_wk is not None:
        weekends.append(current_wk)

    weekends = [w for w in weekends if w["events"]]

    out = []
    for i, wk in enumerate(weekends, start=1):
        days = sorted(set(wk["days"]))
        evs = sorted(wk["events"], key=lambda e: e["date"])
        out.append({
            "label": format_weekend_label(i, days),
            "dates": [d.isoformat() for d in days],
            "events": assign_ids(evs, i),
        })
    return out


def derive_month_label(events, docx_path):
    if events:
        dates = [date.fromisoformat(e["date"]) for e in events]
        (year, month), _ = Counter((d.year, d.month) for d in dates).most_common(1)[0]
        return f"{MONTH_NAMES[month - 1]} {year}"
    stem = Path(docx_path).stem
    m = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)",
        stem, re.IGNORECASE,
    )
    if m:
        return m.group(1).capitalize()
    return stem


def output_filename(month_label):
    first = month_label.split()[0].lower() if month_label else "events"
    return f"events_{first}.json"


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("Usage: python convert_events.py NYC_Events_[Month].docx\n")
        return 2
    docx_path = Path(argv[1])
    if not docx_path.exists():
        sys.stderr.write(f"Error: file not found: {docx_path}\n")
        return 1

    events = parse_document(docx_path)
    month_label = derive_month_label(events, docx_path)
    weekends = group_into_weekends(events)

    out = {"month": month_label, "weekends": weekends}
    out_path = docx_path.parent / output_filename(month_label)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    total = sum(len(w["events"]) for w in weekends)
    print(f"Wrote {out_path}")
    print(f"  month:    {month_label}")
    print(f"  weekends: {len(weekends)}")
    print(f"  events:   {total}")
    for w in weekends:
        print(f"    - {w['label']}: {len(w['events'])} events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

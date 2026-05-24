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


LEADING_PREFIX_RES = [
    re.compile(r"^\s*sponsored\s*::?\s*", re.IGNORECASE),               # sponsored::
    re.compile(r"^\s*\([^)]*\)\s*:\s*"),                                # (thru 10/26):  (+ other dates tba):
    re.compile(r"^\s*(?:thru|through|until)\b[^:]*?:\s*", re.IGNORECASE),  # thru:  thru 8/31:  through April 5:
    re.compile(r"^\s*\d{1,2}/\d{1,2}(?:[-–]\d{1,2}/\d{1,2})?\s*:\s*"),  # 4/5:  4/5-4/6:
]


def strip_leading_prefix(text):
    """Remove leading date/sponsor prefixes like '(thru 10/26):' or 'thru 8/31:'."""
    prev = None
    while text != prev:
        prev = text
        for rx in LEADING_PREFIX_RES:
            text = rx.sub("", text, count=1)
    return text.strip()


def join_wrapped(raw):
    """Collapse the doc's hard line-wraps into one string plus the raw line list."""
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    joined = re.sub(r"\s{2,}", " ", " ".join(lines)).strip()
    return joined, lines


def split_on_colon(text):
    """Split 'name: description' on the first colon. Returns (name, desc) or None."""
    idx = text.find(":")
    if idx == -1:
        return None
    name = text[:idx].strip(" .,;—–-")
    desc = text[idx + 1:].strip()
    if not name:
        return None
    return name, desc


def split_event(raw, head_end=None):
    """Split an event block into (name, description).

    Lowercase newsletter events read like '[date prefix]: NAME: description...'
    wrapped across paragraphs — we rejoin the wraps, drop the date prefix, and
    split name from description on the first colon.

    Featured (Title-Case) events instead isolate their headline with a blank
    line before the body; head_end (set by the parser) is the number of source
    lines in that headline. When present, that boundary wins over the first
    colon, because a featured body often contains stray colons (prices, times).
    """
    joined, lines = join_wrapped(raw)

    if head_end and 0 < head_end < len(lines):
        headline = strip_leading_prefix(" ".join(lines[:head_end]))
        rest = " ".join(lines[head_end:]).strip()
        split = split_on_colon(headline)
        if split:
            name, head_desc = split
            desc = (head_desc + " " + rest).strip() if head_desc else rest
        else:
            name, desc = headline, rest
        if name:
            return name, desc

    body = strip_leading_prefix(joined)
    split = split_on_colon(body)
    if split:
        return split
    # No usable colon: fall back to the first physical line as the name.
    name = strip_leading_prefix(lines[0]) if lines else ""
    desc = " ".join(lines[1:]).strip() if len(lines) > 1 else ""
    return name, desc


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


PHOTO_CREDIT_RE = re.compile(
    r"^\s*(?:"
    r"cast\s+photo|"
    r"photo(?:graph)?\s*(?:by|credit|:|courtesy\s+of)|"
    r"image\s*(?:by|credit|:|courtesy\s+of)|"
    r"courtesy\s+of|"
    r"pictured\s*(?:above|below|:)"
    r")\b",
    re.IGNORECASE,
)


def is_photo_credit(text):
    return bool(PHOTO_CREDIT_RE.match(text or ""))


URL_ONLY_RE = re.compile(r"^\s*https?://\S+\s*$", re.IGNORECASE)
EMAIL_ONLY_RE = re.compile(r"^\s*[\w.+-]+@[\w-]+\.[\w.-]+\s*$")
DIVIDER_RE = re.compile(r"^\s*[-=_*~]{6,}\s*$")
TRAILING_LINK_RE = re.compile(r"\s+link\s*[.!?]?\s*$", re.IGNORECASE)
PRESENTER_PREFIX_RE = re.compile(
    r"(?:presents|presented\s+by|co-presents?|in\s+association\s+with)\s*[:.]?\s*$",
    re.IGNORECASE,
)
STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "and", "or",
    "but", "for", "with", "by", "as", "is", "from", "vs", "vs.",
}
LIST_PARA_DATE_PREFIX_RE = re.compile(
    r"^\s*\(?\s*(\d{1,2})/(\d{1,2})\b[^a-z]*?:",
    re.IGNORECASE,
)


def is_url_only(text):
    return bool(URL_ONLY_RE.match(text or ""))


def is_email_only(text):
    return bool(EMAIL_ONLY_RE.match(text or ""))


def is_divider(text):
    return bool(DIVIDER_RE.match(text or ""))


def is_presenter_prefix(text):
    return bool(PRESENTER_PREFIX_RE.search((text or "").strip()))


def ends_with_link_token(text):
    return bool(TRAILING_LINK_RE.search((text or "").rstrip()))


def strip_trailing_link(text):
    return TRAILING_LINK_RE.sub("", text or "").rstrip()


def looks_like_headline(text):
    t = (text or "").strip()
    if not t or len(t) > 120:
        return False
    letters = [c for c in t if c.isalpha()]
    if not letters:
        return False
    # Ryan's lowercase events start with a lowercase letter; rejecting that
    # alone distinguishes them from Title Case / all-caps featured headlines.
    first_alpha = next((c for c in t if c.isalpha()), "")
    if first_alpha and not first_alpha.isupper():
        return False
    # All-caps headline
    if t == t.upper():
        return True
    # Title Case: majority of significant words start uppercase
    words = re.findall(r"[A-Za-z][A-Za-z']*", t)
    significant = [w for w in words if w.lower() not in STOPWORDS]
    if len(significant) < 2:
        return False
    title_words = sum(1 for w in significant if w[0].isupper())
    return title_words / len(significant) >= 0.7


RYAN_STYLE_START_RE = re.compile(
    r"^\s*\(?\s*(?:"
    r"(?:thru|through|until)\s+(?:\d{1,2}/\d{1,2}|[A-Za-z]+\s+\d)|"
    r"\d{1,2}/\d{1,2}(?:\s*[-–]\s*\d{1,2}/\d{1,2})?\s*[:,]|"
    r"sponsored\s*[:.]"
    r")",
    re.IGNORECASE,
)


def is_ryan_style_start(text):
    """A lowercase 'thru 8/31:', 'M/D:', 'sponsored:' etc. prefix marks the
    start of a Ryan-style event even when the paragraph style is Normal."""
    return bool(RYAN_STYLE_START_RE.match(text or ""))


LOWERCASE_COLON_TITLE_RE = re.compile(r"^[a-z][\w' +\-&/]{0,40}:\s\S")


def is_lowercase_colon_title(text):
    """A 'lowercase-name: content' pattern (e.g. 'indieplaza: rough trade...',
    'five miles of vhs tape: gibson + recoder: ...'). Used as a secondary
    signal for Ryan-style event starts that lack a 'thru'/'M/D:'/'sponsored:'
    prefix. Match is case-sensitive — description labels like 'Featuring:' or
    'Artists:' start uppercase and won't trigger."""
    return bool(LOWERCASE_COLON_TITLE_RE.match(text or ""))


def is_featured_headline_start(records, i):
    """Does records[i] start a new featured (non-List-Paragraph) event?

    Signature: preceded by blank, is a Title Case / all-caps short line,
    followed by blank, then a substantial prose paragraph. Rejects venue
    lines because those are followed by short 'Continues' / URL / nothing.
    """
    rec = records[i]
    if rec["style_lower"] != "normal" or rec["blank"]:
        return False
    if not looks_like_headline(rec["text"]):
        return False
    prev = records[i - 1] if i > 0 else None
    if prev is None or not prev["blank"]:
        return False
    if i + 2 >= len(records):
        return False
    if not records[i + 1]["blank"]:
        return False
    nxt = records[i + 2]
    if nxt["style_lower"] != "normal" or nxt["blank"]:
        return False
    nxt_text = nxt["text"].strip()
    if is_url_only(nxt_text) or is_email_only(nxt_text) or is_divider(nxt_text):
        return False
    if len(nxt_text) < 40:
        return False
    # Real descriptions start with a letter, not a digit, symbol, or time marker.
    if not nxt_text[0].isalpha():
        return False
    # Two Title Case short lines in a row = venue + "Continues" style section
    if looks_like_headline(nxt_text) and len(nxt_text) < 40:
        return False
    return True


def is_section_header(records, i):
    """Short standalone paragraph followed by a List Paragraph is a
    section header, not an event."""
    rec = records[i]
    text = rec["text"].strip()
    if len(text) == 0 or len(text) > 60:
        return False
    # Must be mostly lowercase (Ryan's section labels are lowercase)
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    if upper_ratio > 0.2:
        return False
    # Look forward past blanks for the next styled paragraph
    j = i + 1
    while j < len(records) and records[j]["blank"]:
        j += 1
    if j >= len(records):
        return False
    return records[j]["style_lower"] == "list paragraph"


def override_date_from_prefix(text, fallback_date):
    """If list-paragraph title starts with 'M/D,' or 'M/D ', override date.

    Only applies when the prefix resolves to a valid date within +/- 60 days
    of fallback_date (preventing misreads of random numbers)."""
    m = LIST_PARA_DATE_PREFIX_RE.match(text or "")
    if not m:
        return fallback_date
    month, day = int(m.group(1)), int(m.group(2))
    try:
        candidate = date(fallback_date.year, month, day)
    except ValueError:
        return fallback_date
    delta = abs((candidate - fallback_date).days)
    if delta > 60:
        return fallback_date
    return candidate


def paragraph_style(p):
    try:
        return (p.style.name or "").strip()
    except Exception:
        return ""


def parse_document(path):
    doc = Document(str(path))
    records = []
    for p in doc.paragraphs:
        text = (p.text or "").rstrip()
        style = paragraph_style(p)
        records.append({
            "text": text,
            "style": style,
            "style_lower": style.lower(),
            "blank": not text.strip(),
        })

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
        name, desc = split_event(full, current.get("head_end"))
        current["title"] = name
        current["description"] = desc
        current["ongoing"] = detect_ongoing(full)
        events.append(current)
        current = None
        current_saw_link = False

    def start_event(text, event_date):
        nonlocal current, current_saw_link
        current = {
            "date": event_date.isoformat(),
            "day_of_week": DAY_NAMES[event_date.weekday()],
            "source_lines": [text],
        }
        current_saw_link = False

    for i, rec in enumerate(records):
        text = rec["text"].strip()
        style_lower = rec["style_lower"]

        if style_lower.startswith("heading 1"):
            finalize()
            d = parse_heading_date(text)
            if d is not None:
                current_date = d
            continue

        if rec["blank"]:
            if current is not None and current_saw_link:
                finalize()
            elif current is not None and "head_end" not in current and current["source_lines"]:
                # A blank line inside an event, before any link terminator,
                # marks the boundary between a featured event's headline and
                # its body. Lowercase newsletter events never hit this — their
                # only blank is the terminating one after "link".
                current["head_end"] = len(current["source_lines"])
            continue

        if style_lower == "list paragraph":
            finalize()
            if current_date is None:
                continue
            event_date = override_date_from_prefix(text, current_date)
            start_event(text, event_date)
            continue

        # Normal / other body paragraphs.
        # Handle the "link" terminator in both standalone and inline forms.
        if text.lower() == "link":
            if current is not None:
                current_saw_link = True
            continue
        if ends_with_link_token(text):
            cleaned = strip_trailing_link(text)
            if current is not None:
                if cleaned:
                    current["source_lines"].append(cleaned)
                current_saw_link = True
            continue

        # URL / email / divider paragraphs act as close signals between events.
        if is_url_only(text) or is_email_only(text) or is_divider(text):
            if current is not None:
                current_saw_link = True
            continue

        # Section headers ("earth day related events", "420-themed events")
        # close the current event and are not themselves events.
        if is_section_header(records, i):
            finalize()
            continue

        # If we're inside an event and this paragraph looks like a new
        # featured-event headline, close the current event first — unless
        # the current event is just a presenter prefix ("X presents"), in
        # which case the new headline IS this event's title.
        if current is not None and is_featured_headline_start(records, i):
            only_line = current["source_lines"][0] if len(current["source_lines"]) == 1 else None
            if not (only_line is not None and is_presenter_prefix(only_line)):
                finalize()

        # A Ryan-style lowercase event start ("thru 8/31: ...", "sponsored: ...")
        # can appear inside a Normal-styled block and should close the current
        # event even though it has no List Paragraph style.
        if current is not None and is_ryan_style_start(text):
            finalize()

        # A 'lowercase-name: content' paragraph preceded by blank, appearing
        # deep inside the current event's body (>= 6 source lines), is very
        # likely a Normal-styled Ryan event whose boundary wasn't marked by a
        # `link` or URL. Gated on prior blank + event-length to avoid
        # misfiring on legitimate description labels.
        if (
            current is not None
            and len(current["source_lines"]) >= 6
            and is_lowercase_colon_title(text)
            and i > 0
            and records[i - 1]["blank"]
        ):
            finalize()

        if current is not None:
            current["source_lines"].append(text)
        else:
            if current_date is None:
                continue
            if is_photo_credit(text):
                continue
            start_event(text, current_date)

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
            "description": e.get("description", ""),
            "ongoing": bool(e.get("ongoing", False)),
        })
    return out


def dedupe_events(events):
    """Drop events with the same (normalized title, date). Source docs
    sometimes reprint the same bullet in two places."""
    seen = set()
    out = []
    for e in events:
        key = (e["date"], re.sub(r"\s+", " ", (e.get("title") or "")).strip().lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def group_into_weekends(events):
    """Group events into Fri/Sat/Sun weekends.

    A weekend is Fri+Sat+Sun of the same calendar week. Partial weekends at
    the start (Sat-only or Sat+Sun) or end (Fri-only) of the range are kept.
    """
    if not events:
        return []

    events = dedupe_events(events)

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

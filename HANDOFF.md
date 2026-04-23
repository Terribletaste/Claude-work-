# Handoff: NYC Event Ranker — Phase 2 (HTML tool)

## Context

Two-part project. Phase 1 (Python `.docx` → JSON converter) is **done and shipped**. Phase 2 (self-contained HTML ranking/tiering tool) is **not yet started**.

## Repo

- **Repo:** `Terribletaste/claude-work-` (GitHub)
- **Branch:** `claude/draft-python-plugin-Ln9gZ`
- **Full spec:** `nyc-event-ranker-html` skill — Ryan has the original prompt. Covers both deliverables in detail.

## Phase 1: what's already built (no changes needed unless bug reports)

- **File:** `convert_events.py` — parses `NYC_Events_[Month].docx` → `events_[month].json`
- **Dependencies:** `python-docx` (Python 3.8+). No other deps.
- **Usage:** `python convert_events.py NYC_Events_April.docx` → writes `events_april.json`
- **Status:** Tested against `NYC_Events_April.docx` (committed to default branch `claude/api-health-check-Z0Y81` for test access). Produces 160 events across 4 weekends. Passed two red-team audits except for one known structural limitation: "The Brooklyn Choir Project" stays buried because its only separator from the prior event is a single blank line and a Title-Case prose opener — no parser heuristic can catch it without introducing false positives.
- **Review artifact:** `events_review.md` lists the full parsed event list for verification.

## JSON schema the HTML tool will consume

```json
{
  "month": "April 2025",
  "weekends": [
    {
      "label": "Weekend 1: Fri Apr 4 – Sun Apr 6",
      "dates": ["2025-04-04", "2025-04-05", "2025-04-06"],
      "events": [
        {
          "id": "w1-001",
          "title": "smorgasburg outdoor food markets open for the season",
          "date": "2025-04-04",
          "day_of_week": "Friday",
          "venue": "World Trade Center / Williamsburg / Prospect Park",
          "description": "...",
          "ongoing": true
        }
      ]
    }
  ]
}
```

## Phase 2: what to build (`event_ranker.html`)

Single self-contained HTML file (HTML + inline CSS + inline JS, no external deps, no CDN, no build step, no localStorage). Must work opened via `file://` in Chrome. File size target: under 2000 lines.

### Five screens (state transitions, no routing)

1. **File load** — button opens file picker (uses `FileReader` API); user selects `events_[month].json`.
2. **Weekend selection** — cards per weekend showing label + event count.
3. **Drag ranking** — all events for the selected weekend in a single draggable list. Initial order: chronological (Fri → Sat → Sun). Each card shows rank number, title, day-of-week pill, venue, optional `[ongoing]` badge, expand/collapse for description. Use native HTML5 drag-and-drop + touch handlers for mobile.
4. **Tiering** — three cascading dropdowns set cutoffs for Must Go → Want to Go → Can Go; everything below = Cut. Each dropdown shows only events ranked below the previous tier's cutoff. Each dropdown needs a "None" option. Visual tier badges update live.
5. **Summary & Download** — tier-colored sections listing events, plus CSV download. CSV columns: `month,weekend_dates,rank,event_name,day,venue,tier,date_ranked`. Filename: `NYC_Events_Log_[weekend_dates].csv`. Accumulate results across multiple weekends ranked in the same session.

### Colors (spec-mandated)

- Must Go: `#22c55e` / bg `#f0fdf4`
- Want to Go: `#3b82f6` / bg `#eff6ff`
- Can Go: `#eab308` / bg `#fefce8`
- Cut: `#9ca3af` / bg `#f3f4f6`
- Friday pill: `#6366f1`, Saturday: `#10b981`, Sunday: `#f59e0b`

## Development branch for Phase 2

Develop on the same branch: **`claude/draft-python-plugin-Ln9gZ`**. Push commits there.

## Warnings for the next Claude

- **Don't rewrite `convert_events.py`.** It works; two audits confirmed it. Ryan only wants the HTML now.
- **The `NYC_Events_April.docx` test file lives on `claude/api-health-check-Z0Y81`, not this branch.** Pull it on-demand for testing, don't commit it.
- **Session context is limited.** This HTML file is up to ~2000 lines. Write it in one go if possible. If the session runs out of budget, commit partial work and note where you stopped. Don't try to do it in a single turn with the converter work — that's what caused failures earlier in this project.
- **Test the HTML from `file://` in a browser before reporting done.** Can't just trust that the code parses.

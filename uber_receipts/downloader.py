"""Download every Uber trip receipt as a PDF.

Usage:
    python downloader.py --out ./receipts
    python downloader.py --out ./receipts --since 2024-01-01 --until 2024-12-31
    python downloader.py --out ./receipts --headed        # watch it work
    python downloader.py --login                          # just log in and exit

First run opens a real browser window so you can sign in (email, SMS code,
Google/Apple SSO — whatever your account uses). The session is stored in
./.uber_profile and reused on every later run, so subsequent runs are
non-interactive until Uber invalidates the cookie.

Files are named `YYYY-MM-DD__<label>__<trip-id>.pdf` so they sort by
trip date. Runs are resumable: a receipt whose file already exists is
skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

from playwright.async_api import (
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)


ACTIVITY_URL = "https://riders.uber.com/trips"
LOGIN_URL = "https://auth.uber.com/login/"
TRIP_ID_RE = re.compile(r"/trips/([0-9a-f-]{36})", re.IGNORECASE)
LONG_DATE_RE = re.compile(r"([A-Z][a-z]+ \d{1,2},\s*\d{4})")
ISO_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


@dataclasses.dataclass
class Trip:
    trip_id: str
    url: str
    label: str  # short human-readable string used in the filename


def sanitize(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")


def build_filename(trip: Trip, trip_date: date | None) -> str:
    parts = []
    if trip_date is not None:
        parts.append(trip_date.isoformat())
    label = sanitize(trip.label)
    if label:
        parts.append(label)
    parts.append(trip.trip_id)
    return "__".join(parts) + ".pdf"


def existing_pdf_for(trip: Trip, out_dir: Path) -> Path | None:
    """Return a previously downloaded PDF for this trip, if any."""
    for p in out_dir.glob(f"*{trip.trip_id}.pdf"):
        if p.stat().st_size > 0:
            return p
    return None


async def ensure_logged_in(page: Page, *, interactive: bool) -> None:
    """Navigate to the activity page; if bounced to login, wait for the user."""
    await page.goto(ACTIVITY_URL, wait_until="domcontentloaded")
    if "auth.uber.com" in page.url or "login" in page.url:
        if not interactive:
            raise RuntimeError(
                "Not logged in and running headless. Run once with --login "
                "(or --headed) to sign in and save the session."
            )
        print("Please sign in to Uber in the opened window.")
        print("Waiting for redirect back to riders.uber.com/trips ...")
        await page.wait_for_url(
            re.compile(r"https://riders\.uber\.com/trips.*"),
            timeout=10 * 60 * 1000,
        )
    await page.wait_for_selector("a[href*='/trips/']", timeout=60_000)


async def scroll_all_trips(page: Page) -> None:
    """Scroll the activity list until no more trips load."""
    last_count = -1
    stable_rounds = 0
    while stable_rounds < 3:
        count = await page.locator("a[href*='/trips/']").count()
        if count == last_count:
            stable_rounds += 1
        else:
            stable_rounds = 0
            last_count = count

        await page.mouse.wheel(0, 20000)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        for label in ("More", "Show more", "Load more"):
            btn = page.get_by_role("button", name=re.compile(label, re.I))
            if await btn.count():
                try:
                    await btn.first.click(timeout=1000)
                except Exception:
                    pass
        await page.wait_for_timeout(1200)


async def collect_trips(page: Page) -> list[Trip]:
    await scroll_all_trips(page)
    seen: dict[str, Trip] = {}
    anchors = await page.locator("a[href*='/trips/']").all()
    for a in anchors:
        href = await a.get_attribute("href") or ""
        m = TRIP_ID_RE.search(href)
        if not m:
            continue
        trip_id = m.group(1).lower()
        if trip_id in seen:
            continue
        try:
            label = (await a.inner_text()).strip().splitlines()[0][:80]
        except Exception:
            label = ""
        seen[trip_id] = Trip(
            trip_id=trip_id,
            url=urljoin(ACTIVITY_URL, href),
            label=label,
        )
    return list(seen.values())


async def extract_trip_date(page: Page) -> date | None:
    """Best-effort date parse from a trip detail page."""
    try:
        body = await page.locator("body").inner_text()
    except Exception:
        return None
    m = LONG_DATE_RE.search(body)
    if m:
        try:
            return datetime.strptime(m.group(1), "%B %d, %Y").date()
        except ValueError:
            pass
    m = ISO_DATE_RE.search(body)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass
    return None


async def open_receipt(page: Page) -> Page:
    """From a trip page, click 'View receipt' and return the receipt page."""
    candidates = [
        page.get_by_role("link", name=re.compile(r"receipt", re.I)),
        page.get_by_role("button", name=re.compile(r"receipt", re.I)),
    ]
    for locator in candidates:
        if await locator.count() == 0:
            continue
        target = locator.first
        try:
            async with page.context.expect_page(timeout=5_000) as new_page_info:
                await target.click()
            receipt = await new_page_info.value
            await receipt.wait_for_load_state("domcontentloaded")
            return receipt
        except PlaywrightTimeoutError:
            await target.click()
            await page.wait_for_load_state("domcontentloaded")
            return page
    raise RuntimeError("Could not find a 'View receipt' link on the trip page.")


async def save_receipt_pdf(receipt: Page, dest: Path) -> None:
    """Save the receipt page as a PDF (download button, else print-to-PDF)."""
    pdf_btn = receipt.get_by_role(
        "link", name=re.compile(r"download.*pdf|pdf", re.I)
    )
    if await pdf_btn.count() == 0:
        pdf_btn = receipt.get_by_role(
            "button", name=re.compile(r"download.*pdf|pdf", re.I)
        )
    if await pdf_btn.count():
        try:
            async with receipt.expect_download(timeout=15_000) as dl_info:
                await pdf_btn.first.click()
            download = await dl_info.value
            await download.save_as(dest)
            return
        except PlaywrightTimeoutError:
            pass

    await receipt.emulate_media(media="screen")
    await receipt.pdf(
        path=str(dest),
        format="Letter",
        print_background=True,
        margin={"top": "0.4in", "bottom": "0.4in", "left": "0.4in", "right": "0.4in"},
    )


async def process_trip(
    context: BrowserContext,
    trip: Trip,
    out_dir: Path,
    since: date | None,
    until: date | None,
) -> tuple[str, Path | None, date | None]:
    """
    Return (status, path, trip_date). Status is one of:
        'saved', 'existing', 'no-receipt', 'filtered'.
    """
    existing = existing_pdf_for(trip, out_dir)
    if existing is not None:
        return "existing", existing, None

    page = await context.new_page()
    try:
        await page.goto(trip.url, wait_until="domcontentloaded")
        trip_date = await extract_trip_date(page)

        if trip_date is not None:
            if since and trip_date < since:
                return "filtered", None, trip_date
            if until and trip_date > until:
                return "filtered", None, trip_date

        try:
            await page.wait_for_selector(
                "text=/receipt/i", timeout=15_000, state="visible"
            )
        except PlaywrightTimeoutError:
            return "no-receipt", None, trip_date

        receipt = await open_receipt(page)
        dest = out_dir / build_filename(trip, trip_date)
        await save_receipt_pdf(receipt, dest)
        return "saved", dest, trip_date
    finally:
        for p in list(context.pages):
            if p is not page and p is not context.pages[0]:
                try:
                    await p.close()
                except Exception:
                    pass
        try:
            await page.close()
        except Exception:
            pass


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


async def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    profile_dir = Path(args.profile).expanduser().resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    since = parse_date(args.since) if args.since else None
    until = parse_date(args.until) if args.until else None

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=not (args.headed or args.login),
            accept_downloads=True,
            viewport={"width": 1280, "height": 900},
        )
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            await ensure_logged_in(page, interactive=args.headed or args.login)

            if args.login:
                print("Login saved. Rerun without --login to download receipts.")
                return 0

            print("Collecting trips ...")
            trips = await collect_trips(page)
            print(f"Found {len(trips)} trips.")

            manifest_path = out_dir / "manifest.jsonl"
            ok = fail = skipped = 0
            with manifest_path.open("a", encoding="utf-8") as manifest:
                for i, trip in enumerate(trips, 1):
                    prefix = f"[{i}/{len(trips)}] {trip.trip_id}"
                    try:
                        status, path, trip_date = await process_trip(
                            context, trip, out_dir, since, until
                        )
                        if status == "saved":
                            ok += 1
                            print(f"{prefix} -> {path.name}")
                            manifest.write(
                                json.dumps(
                                    {
                                        "trip_id": trip.trip_id,
                                        "url": trip.url,
                                        "label": trip.label,
                                        "date": trip_date.isoformat() if trip_date else None,
                                        "file": path.name,
                                    }
                                )
                                + "\n"
                            )
                            manifest.flush()
                        elif status == "existing":
                            skipped += 1
                            print(f"{prefix} exists ({path.name}), skip")
                        elif status == "filtered":
                            skipped += 1
                            print(f"{prefix} {trip_date} outside window, skip")
                        else:  # no-receipt
                            fail += 1
                            print(f"{prefix} no receipt available")
                    except Exception as exc:  # noqa: BLE001
                        fail += 1
                        print(f"{prefix} ERROR: {exc}")

            print(f"\nDone. saved={ok} failed={fail} skipped={skipped}")
            print(f"PDFs in {out_dir}")
            return 0 if fail == 0 else 1
        finally:
            await context.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="./receipts", help="Directory to write PDFs into.")
    parser.add_argument(
        "--profile",
        default="./.uber_profile",
        help="Persistent browser profile directory (holds the login cookie).",
    )
    parser.add_argument("--since", help="Only download trips on or after YYYY-MM-DD.")
    parser.add_argument("--until", help="Only download trips on or before YYYY-MM-DD.")
    parser.add_argument(
        "--headed", action="store_true", help="Show the browser window while running."
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Open a browser for interactive login, save the session, and exit.",
    )
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())

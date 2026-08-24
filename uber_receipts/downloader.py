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

The script is resumable: a receipt whose PDF already exists in --out is
skipped, so you can Ctrl-C at any time and rerun.
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


@dataclasses.dataclass
class Trip:
    trip_id: str
    url: str
    label: str  # short human-readable string used in the filename

    @property
    def filename(self) -> str:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", self.label).strip("_")
        return f"{safe}__{self.trip_id}.pdf" if safe else f"{self.trip_id}.pdf"


async def ensure_logged_in(page: Page, *, interactive: bool) -> None:
    """Navigate to the activity page; if bounced to login, wait for the user."""
    await page.goto(ACTIVITY_URL, wait_until="domcontentloaded")
    # Uber redirects unauthenticated users to auth.uber.com.
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
            timeout=10 * 60 * 1000,  # 10 minutes
        )
    # Wait for the trip list to render.
    await page.wait_for_selector("a[href*='/trips/']", timeout=60_000)


async def scroll_all_trips(page: Page) -> None:
    """Scroll the activity list until no more trips load."""
    last_count = -1
    stable_rounds = 0
    while stable_rounds < 3:
        anchors = await page.locator("a[href*='/trips/']").all()
        count = len(anchors)
        if count == last_count:
            stable_rounds += 1
        else:
            stable_rounds = 0
            last_count = count

        # Uber uses infinite scroll; nudge the bottom of the page.
        await page.mouse.wheel(0, 20000)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        # Also try clicking a "Show more" / "Load more" button if present.
        for label in ("More", "Show more", "Load more"):
            btn = page.get_by_role("button", name=re.compile(label, re.I))
            if await btn.count():
                try:
                    await btn.first.click(timeout=1000)
                except Exception:
                    pass
        await page.wait_for_timeout(1200)


async def collect_trips(page: Page) -> list[Trip]:
    """Return every trip visible on the activity page."""
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
        # Use the anchor's text as a rough label (date + destination).
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
    """Best-effort date parse from the trip detail page for --since/--until."""
    # Uber renders the date somewhere near the top of the trip page. Grab any
    # ISO-ish or long-form date substring we can find.
    body = await page.locator("body").inner_text()
    # Try "January 5, 2024" first.
    m = re.search(
        r"([A-Z][a-z]+ \d{1,2},\s*\d{4})",
        body,
    )
    if m:
        try:
            return datetime.strptime(m.group(1), "%B %d, %Y").date()
        except ValueError:
            pass
    m = re.search(r"(\d{4}-\d{2}-\d{2})", body)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass
    return None


async def open_receipt(page: Page) -> Page:
    """From a trip page, click 'View receipt' and return the receipt page."""
    # The receipt link is sometimes an <a target=_blank>, sometimes a button
    # that navigates in place. Handle both.
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
            # No new tab — the current page navigated instead.
            await target.click()
            await page.wait_for_load_state("domcontentloaded")
            return page
    raise RuntimeError("Could not find a 'View receipt' link on the trip page.")


async def download_receipt_pdf(
    context: BrowserContext, trip: Trip, out_dir: Path
) -> Path | None:
    """Open the trip, save its receipt as a PDF, return the written path."""
    dest = out_dir / trip.filename
    if dest.exists() and dest.stat().st_size > 0:
        return dest  # resume: already have it

    page = await context.new_page()
    try:
        await page.goto(trip.url, wait_until="domcontentloaded")
        try:
            await page.wait_for_selector(
                "text=/receipt/i", timeout=15_000, state="visible"
            )
        except PlaywrightTimeoutError:
            print(f"  no receipt control on {trip.trip_id}, skipping")
            return None

        receipt = await open_receipt(page)

        # Path A: an explicit "Download PDF" button that emits a file download.
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
                return dest
            except PlaywrightTimeoutError:
                pass  # fall through to print-to-PDF

        # Path B: render the current receipt page to a PDF via Chromium.
        # (Only works in Chromium, which is what we launched.)
        await receipt.emulate_media(media="screen")
        await receipt.pdf(
            path=str(dest),
            format="Letter",
            print_background=True,
            margin={"top": "0.4in", "bottom": "0.4in", "left": "0.4in", "right": "0.4in"},
        )
        return dest
    finally:
        # Close any extra tabs we opened.
        for p in list(context.pages):
            if p is not page and p.url.startswith("http") and p != context.pages[0]:
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
            since = parse_date(args.since) if args.since else None
            until = parse_date(args.until) if args.until else None

            ok = fail = skipped = 0
            with manifest_path.open("a", encoding="utf-8") as manifest:
                for i, trip in enumerate(trips, 1):
                    prefix = f"[{i}/{len(trips)}] {trip.trip_id}"
                    try:
                        # Cheap date filter, if requested: peek at the trip page.
                        if since or until:
                            probe = await context.new_page()
                            try:
                                await probe.goto(trip.url, wait_until="domcontentloaded")
                                trip_date = await extract_trip_date(probe)
                            finally:
                                await probe.close()
                            if trip_date is None:
                                pass  # can't tell — download anyway
                            else:
                                if since and trip_date < since:
                                    skipped += 1
                                    print(f"{prefix} before {since}, skip")
                                    continue
                                if until and trip_date > until:
                                    skipped += 1
                                    print(f"{prefix} after {until}, skip")
                                    continue

                        path = await download_receipt_pdf(context, trip, out_dir)
                        if path is None:
                            fail += 1
                            print(f"{prefix} no receipt available")
                        else:
                            ok += 1
                            print(f"{prefix} -> {path.name}")
                            manifest.write(
                                json.dumps(
                                    {
                                        "trip_id": trip.trip_id,
                                        "url": trip.url,
                                        "label": trip.label,
                                        "file": path.name,
                                    }
                                )
                                + "\n"
                            )
                            manifest.flush()
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

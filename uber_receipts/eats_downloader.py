"""Download every Uber Eats order receipt as a PDF.

Usage:
    python eats_downloader.py --out ./eats_receipts
    python eats_downloader.py --out ./eats_receipts --since 2024-01-01 --until 2024-12-31
    python eats_downloader.py --out ./eats_receipts --headed
    python eats_downloader.py --login

First run opens a browser for you to sign in to ubereats.com. The session
is persisted in ./.ubereats_profile and reused on every later run.

Uber Eats doesn't publish a "Download PDF" button on the order detail
page, so this script renders each order page to a PDF via Chromium. It
does the same thing you'd get by using File → Print → Save as PDF.

Files are named `YYYY-MM-DD__<restaurant>__<order-id>.pdf`. Resumable —
existing files are skipped.
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


ORDERS_URL = "https://www.ubereats.com/orders"
ORDER_ID_RE = re.compile(r"/orders/([0-9a-f-]{36})", re.IGNORECASE)
LONG_DATE_RE = re.compile(r"([A-Z][a-z]+ \d{1,2},\s*\d{4})")
ISO_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
SHORT_DATE_RE = re.compile(r"([A-Z][a-z]{2}\s+\d{1,2},\s*\d{4})")  # "Jan 5, 2024"


@dataclasses.dataclass
class Order:
    order_id: str
    url: str
    label: str  # usually the restaurant name


def sanitize(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")


def build_filename(order: Order, order_date: date | None) -> str:
    parts = []
    if order_date is not None:
        parts.append(order_date.isoformat())
    label = sanitize(order.label)
    if label:
        parts.append(label)
    parts.append(order.order_id)
    return "__".join(parts) + ".pdf"


def existing_pdf_for(order: Order, out_dir: Path) -> Path | None:
    for p in out_dir.glob(f"*{order.order_id}.pdf"):
        if p.stat().st_size > 0:
            return p
    return None


async def ensure_logged_in(page: Page, *, interactive: bool) -> None:
    await page.goto(ORDERS_URL, wait_until="domcontentloaded")
    if "auth.uber.com" in page.url or "login" in page.url:
        if not interactive:
            raise RuntimeError(
                "Not logged in and running headless. Run once with --login "
                "(or --headed) to sign in and save the session."
            )
        print("Please sign in to Uber Eats in the opened window.")
        print("Waiting for redirect back to ubereats.com/orders ...")
        await page.wait_for_url(
            re.compile(r"https://www\.ubereats\.com/orders.*"),
            timeout=10 * 60 * 1000,
        )
    await page.wait_for_selector("a[href*='/orders/']", timeout=60_000)


async def scroll_all_orders(page: Page) -> None:
    """Uber Eats paginates via a 'Show more' button and lazy scroll."""
    last_count = -1
    stable_rounds = 0
    while stable_rounds < 3:
        count = await page.locator("a[href*='/orders/']").count()
        if count == last_count:
            stable_rounds += 1
        else:
            stable_rounds = 0
            last_count = count

        await page.mouse.wheel(0, 20000)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        for label in ("Show more", "See more", "Load more", "More orders"):
            btn = page.get_by_role("button", name=re.compile(label, re.I))
            if await btn.count():
                try:
                    await btn.first.click(timeout=1000)
                except Exception:
                    pass
        await page.wait_for_timeout(1500)


async def collect_orders(page: Page) -> list[Order]:
    await scroll_all_orders(page)
    seen: dict[str, Order] = {}
    anchors = await page.locator("a[href*='/orders/']").all()
    for a in anchors:
        href = await a.get_attribute("href") or ""
        m = ORDER_ID_RE.search(href)
        if not m:
            continue
        order_id = m.group(1).lower()
        if order_id in seen:
            continue
        try:
            text = (await a.inner_text()).strip()
            # First non-empty line is usually the restaurant name.
            label = next(
                (ln.strip() for ln in text.splitlines() if ln.strip()), ""
            )[:80]
        except Exception:
            label = ""
        seen[order_id] = Order(
            order_id=order_id,
            url=urljoin(ORDERS_URL, href),
            label=label,
        )
    return list(seen.values())


async def extract_order_date(page: Page) -> date | None:
    """Best-effort date parse from an order detail page."""
    try:
        body = await page.locator("body").inner_text()
    except Exception:
        return None
    for regex, fmt in (
        (LONG_DATE_RE, "%B %d, %Y"),
        (SHORT_DATE_RE, "%b %d, %Y"),
        (ISO_DATE_RE, "%Y-%m-%d"),
    ):
        m = regex.search(body)
        if not m:
            continue
        try:
            return datetime.strptime(m.group(1), fmt).date()
        except ValueError:
            continue
    return None


async def render_order_pdf(page: Page, dest: Path) -> None:
    """Render the current order detail page to a PDF."""
    # Expand any 'View receipt' / 'Show details' sections so the PDF is complete.
    for name in ("View receipt", "Show receipt", "See receipt", "Show details"):
        btn = page.get_by_role("button", name=re.compile(name, re.I))
        if await btn.count():
            try:
                await btn.first.click(timeout=2000)
                await page.wait_for_timeout(500)
            except Exception:
                pass
        link = page.get_by_role("link", name=re.compile(name, re.I))
        if await link.count():
            try:
                await link.first.click(timeout=2000)
                await page.wait_for_load_state("domcontentloaded")
            except Exception:
                pass

    await page.emulate_media(media="screen")
    await page.pdf(
        path=str(dest),
        format="Letter",
        print_background=True,
        margin={"top": "0.4in", "bottom": "0.4in", "left": "0.4in", "right": "0.4in"},
    )


async def process_order(
    context: BrowserContext,
    order: Order,
    out_dir: Path,
    since: date | None,
    until: date | None,
) -> tuple[str, Path | None, date | None]:
    existing = existing_pdf_for(order, out_dir)
    if existing is not None:
        return "existing", existing, None

    page = await context.new_page()
    try:
        await page.goto(order.url, wait_until="domcontentloaded")
        try:
            await page.wait_for_load_state("networkidle", timeout=10_000)
        except PlaywrightTimeoutError:
            pass
        order_date = await extract_order_date(page)

        if order_date is not None:
            if since and order_date < since:
                return "filtered", None, order_date
            if until and order_date > until:
                return "filtered", None, order_date

        dest = out_dir / build_filename(order, order_date)
        await render_order_pdf(page, dest)
        return "saved", dest, order_date
    finally:
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

            print("Collecting orders ...")
            orders = await collect_orders(page)
            print(f"Found {len(orders)} orders.")

            manifest_path = out_dir / "manifest.jsonl"
            ok = fail = skipped = 0
            with manifest_path.open("a", encoding="utf-8") as manifest:
                for i, order in enumerate(orders, 1):
                    prefix = f"[{i}/{len(orders)}] {order.order_id}"
                    try:
                        status, path, order_date = await process_order(
                            context, order, out_dir, since, until
                        )
                        if status == "saved":
                            ok += 1
                            print(f"{prefix} -> {path.name}")
                            manifest.write(
                                json.dumps(
                                    {
                                        "order_id": order.order_id,
                                        "url": order.url,
                                        "label": order.label,
                                        "date": order_date.isoformat() if order_date else None,
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
                            print(f"{prefix} {order_date} outside window, skip")
                        else:
                            fail += 1
                            print(f"{prefix} could not render")
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
    parser.add_argument("--out", default="./eats_receipts", help="Directory to write PDFs into.")
    parser.add_argument(
        "--profile",
        default="./.ubereats_profile",
        help="Persistent browser profile directory (holds the login cookie).",
    )
    parser.add_argument("--since", help="Only download orders on or after YYYY-MM-DD.")
    parser.add_argument("--until", help="Only download orders on or before YYYY-MM-DD.")
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

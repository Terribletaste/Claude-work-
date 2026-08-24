# Uber Receipts Downloader

Two Playwright scripts that download every receipt from your Uber
account as a PDF:

- `downloader.py` — Uber **rides** (riders.uber.com/trips)
- `eats_downloader.py` — Uber **Eats** orders (ubereats.com/orders)

## How it works

Both scripts drive a real Chromium via Playwright. Uber's login flow
(SMS, email code, Google/Apple SSO, occasional CAPTCHA) is a bad fit for
a headless bot, so the first run opens a browser window and asks you to
sign in yourself. The resulting session is written to a per-site profile
directory and reused on every later run.

**Rides.** For each trip on `riders.uber.com/trips`, the script opens
the trip page, clicks **View receipt**, then either clicks a **Download
PDF** button (if Uber is showing one) or renders the receipt page to a
PDF via Chromium.

**Eats.** For each order on `ubereats.com/orders`, the script opens the
order detail page, expands any collapsed receipt/details sections, and
renders the page to a PDF via Chromium. (Uber Eats doesn't ship a
"Download PDF" button.)

Files are named `YYYY-MM-DD__<label>__<id>.pdf` so they sort by date.
Runs are resumable — any file already present in the output directory is
skipped (matched by the id suffix, so a rename doesn't cause duplicates).

## Setup

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Use — rides

```bash
python downloader.py --login                          # sign in once
python downloader.py --out ./receipts                 # download everything
python downloader.py --out ./receipts --since 2024-01-01 --until 2024-12-31
python downloader.py --out ./receipts --headed        # watch it work
```

## Use — Uber Eats

```bash
python eats_downloader.py --login                     # sign in once
python eats_downloader.py --out ./eats_receipts       # download everything
python eats_downloader.py --out ./eats_receipts --since 2024-01-01 --until 2024-12-31
python eats_downloader.py --out ./eats_receipts --headed
```

Each script writes a `manifest.jsonl` alongside the PDFs — one line per
downloaded receipt, with the id, URL, label, date, and file name.

## Notes

- DOM selectors (`View receipt`, `Download PDF`, `Show more`, the order
  list on `/orders`) are what Uber ships today. If they rename a button,
  adjust the regex — `open_receipt`/`save_receipt_pdf` in the rides
  script, `render_order_pdf` in the Eats script.
- The two scripts use separate profile directories
  (`.uber_profile` vs `.ubereats_profile`) so a session that expires on
  one site doesn't affect the other. In practice Uber often shares
  cookies across `uber.com` and `ubereats.com`, but keeping them
  separate is more predictable.
- Uber will invalidate the saved session after a while. When it does,
  rerun with `--login`.
- Only use this for your own account. Respect Uber's Terms of Service.

# Uber Receipts Downloader

Downloads every Uber trip receipt from your account as a PDF.

## How it works

The script drives a real Chromium via Playwright. Uber's login flow (SMS,
email code, Google/Apple SSO, occasional CAPTCHA) is a bad fit for a
headless bot, so the first run opens a browser window and asks you to sign
in yourself. The resulting session is written to `./.uber_profile` and
reused on every later run.

For each trip on `riders.uber.com/trips`, the script opens the trip page,
clicks **View receipt**, and either:

1. clicks a **Download PDF** button if one is present, or
2. renders the receipt page to a PDF via Chromium.

Runs are resumable — if `<trip-id>.pdf` already exists in the output
directory, that trip is skipped.

## Setup

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Use

```bash
# First run: sign in (browser opens), then exit.
python downloader.py --login

# Download everything.
python downloader.py --out ./receipts

# Or a date window (dates as YYYY-MM-DD).
python downloader.py --out ./receipts --since 2024-01-01 --until 2024-12-31

# Watch it work.
python downloader.py --out ./receipts --headed
```

A `manifest.jsonl` file is appended alongside the PDFs, one line per
downloaded receipt (`trip_id`, `url`, `label`, `file`).

## Notes

- The DOM selectors here (`View receipt`, `Download PDF`, the trip list on
  `/trips`) are what Uber ships today. If they rename a button, adjust the
  regex in `open_receipt` / `download_receipt_pdf`.
- Uber will invalidate the saved session after a while. When it does, run
  with `--login` again.
- Only use this for your own account. Respect Uber's Terms of Service.

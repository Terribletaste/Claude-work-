# Path to 100K

A Skyrim-inspired constellation of U.S. careers that pay over $100,000 a year
and don't require a college degree. Answer a short quiz on the landing page,
land in the tree with your answers persisted as filters, and click any star to
see the credentials, upfront cost, timeline, and live job listings (≥ $100K
only) for that career.

## Stack

- **Next.js 14** (App Router) + **React 18** + **TypeScript**
- **Tailwind CSS** for styling
- **SVG constellation** — no chart library
- **Jobs agent** (`lib/jobs-agent.ts`) — pluggable source interface, stub
  source ships in v1, real sources land in `sources/` next

## Local development

```bash
npm install
npm run dev
# open http://localhost:3000
```

## Deploy

Point Vercel at this repo. Zero config needed for the default build.

## Data model

- `lib/types.ts` — `CareerNode`, `QuizAnswers`, `JobListing`
- `lib/careers.ts` — the seed constellation (22 careers, 6 branches, 3 tiers)
- `lib/filters.ts` — quiz answers → eligible nodes + prerequisite paths
- `lib/jobs-agent.ts` — `JobsSource` interface, $100K/yr enforcement, affiliate
  wrap layer

## Adding a real jobs source

1. Create `lib/sources/<name>.ts` exporting a `JobsSource`.
2. Push it into `SOURCES` in `lib/jobs-agent.ts`.
3. Every returned listing must clear `MIN_ANNUAL_USD` or `MIN_HOURLY_USD` —
   `enforcePayFloor` runs both at source-level and aggregator-level.

## Roadmap

- Real ingestion sources (Indeed Publisher, USAJobs, ZipRecruiter, direct ATS)
- Affiliate partnerships wired into `AFFILIATE_PARTNERS`
- Career detail pages with day-in-the-life content
- Save/share personalized paths

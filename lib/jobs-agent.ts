import type { CareerNode, JobListing } from "./types";
import { CAREERS } from "./careers";

// -----------------------------------------------------------------------------
// Jobs Agent
//
// v1 goal: define the interface so the site can render "live" listings for
// each career node while real ingestion is being built. Every source MUST
// enforce the $100K/yr floor (or hourly equivalent ~ $48/hr for 40 hr/wk).
// Real sources land in `sources/` (indeed publisher API, USAJobs, ZipRecruiter
// publisher, direct-company ATS). The affiliate layer wraps the returned
// urls at render-time so we can swap partners without changing the data model.
// -----------------------------------------------------------------------------

export const MIN_ANNUAL_USD = 100_000;
export const MIN_HOURLY_USD = 48; // ~ 100k / 2080

export interface JobsSource {
  name: string;
  fetchForCareer(node: CareerNode): Promise<JobListing[]>;
}

export function enforcePayFloor(listings: JobListing[]): JobListing[] {
  return listings.filter((l) => {
    if (typeof l.annualPayUsd === "number" && l.annualPayUsd >= MIN_ANNUAL_USD) return true;
    if (typeof l.hourlyPayUsd === "number" && l.hourlyPayUsd >= MIN_HOURLY_USD) return true;
    return false;
  });
}

// --- Stub source used in v1. Replace with real HTTP fetches per source. ------
const stubSource: JobsSource = {
  name: "stub",
  async fetchForCareer(node) {
    // Deterministic pseudo-listings so the UI has something real-looking.
    const rand = mulberry32(hash(node.id));
    const count = 3 + Math.floor(rand() * 3);
    const cities = [
      "Austin, TX",
      "Phoenix, AZ",
      "Columbus, OH",
      "Nashville, TN",
      "Denver, CO",
      "Charlotte, NC",
      "Remote",
    ];
    const employers = node.employers.length
      ? node.employers
      : ["Regional employer"];

    const listings: JobListing[] = [];
    for (let i = 0; i < count; i++) {
      const annual = Math.max(
        MIN_ANNUAL_USD,
        Math.round((node.medianSalary * (1.15 + rand() * 0.9)) / 1000) * 1000,
      );
      listings.push({
        id: `${node.id}-stub-${i}`,
        careerId: node.id,
        title: node.name,
        company: employers[Math.floor(rand() * employers.length)],
        location: cities[Math.floor(rand() * cities.length)],
        postedAt: new Date(Date.now() - Math.floor(rand() * 12) * 86400000).toISOString(),
        annualPayUsd: annual,
        url: "https://example.com/jobs/preview",
        source: "stub",
      });
    }
    return enforcePayFloor(listings);
  },
};

export const SOURCES: JobsSource[] = [
  stubSource,
  // TODO: add real sources here as they come online.
  // require('./sources/indeed').indeedSource,
  // require('./sources/usajobs').usaJobsSource,
];

export async function fetchListingsForCareer(id: string): Promise<JobListing[]> {
  const node = CAREERS.find((c) => c.id === id);
  if (!node) return [];
  const results = await Promise.all(SOURCES.map((s) => s.fetchForCareer(node)));
  return enforcePayFloor(results.flat()).sort(
    (a, b) => (b.annualPayUsd ?? 0) - (a.annualPayUsd ?? 0),
  );
}

// Affiliate wrap. Config lives in env / DB later; for now the mapping is empty
// and we return the raw url so the CTA works.
export function wrapAffiliate(listing: JobListing): string {
  const partner = AFFILIATE_PARTNERS[listing.source];
  if (!partner) return listing.affiliateUrl ?? listing.url;
  return partner(listing);
}

const AFFILIATE_PARTNERS: Record<string, (l: JobListing) => string> = {
  // 'ziprecruiter': (l) => `https://ziprecruiter.com/aff/YOURID?redir=${encodeURIComponent(l.url)}`,
  // 'indeed': (l) => `https://indeed.com/aff/YOURID?redir=${encodeURIComponent(l.url)}`,
};

// --- utilities ---------------------------------------------------------------
function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}
function mulberry32(a: number) {
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

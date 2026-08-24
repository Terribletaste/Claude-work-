export type Branch =
  | "trades"
  | "energy"
  | "transport"
  | "public-safety"
  | "sales-business"
  | "tech";

export type Physicality = "physical" | "mixed" | "desk";

// Every capstone (tier-3) node MUST be reachable in ≤ ~2 years from zero and
// must pay $100K on the day you land the job (via base, or realistic OT /
// shift-diff / commission at the role, not "after five more years of grinding").
// Tier-1 = the entry credential / gate (cert, license application, academy
// admission). Tier-2 = an on-ramp earning role (paid apprenticeship year,
// SDR seat) — used only where the path really has one.
export type CareerNode = {
  id: string;
  name: string;
  branch: Branch;
  tier: 1 | 2 | 3;
  medianSalary: number; // realistic median for someone actually holding the role
  hundredKPath: string; // one-liner on how the $100K happens on this role
  entryMonths: number; // months of training/cert/apprenticeship to be *hireable*
  yearsToHundredK: number; // years AFTER entry until you'd realistically clear $100K. 0 = at hire.
  upfrontCostUsd: number; // out-of-pocket to enter (school, tools, licenses)
  physicality: Physicality;
  relocationHelps: boolean; // materially easier if willing to move
  felonyEligible: boolean; // realistic w/ a felony record (may vary by state)
  requiresHsDiploma: boolean; // HS diploma / GED — most roles do, a few don't
  requires: string[]; // ids of prerequisite nodes
  credentials: string[]; // certs, licenses, apprenticeships
  employers: string[]; // typical employer types / examples
  blurb: string;
  // grid position on the constellation, in canvas units (0-1000 range)
  x: number;
  y: number;
};

export type QuizAnswers = {
  willingToRelocate: boolean;
  criminalRecord: boolean;
  physicality: "any" | Physicality;
  maxUpfrontCostUsd: number; // 0 means "no cash"
  maxYears: number; // patience in years
};

export type JobListing = {
  id: string;
  careerId: string;
  title: string;
  company: string;
  location: string; // "City, ST" or "Remote"
  postedAt: string; // ISO
  annualPayUsd: number; // must be >= 100_000
  hourlyPayUsd?: number;
  url: string; // apply / details
  source: string; // "indeed", "ziprecruiter", "usajobs", "direct", ...
  affiliateUrl?: string; // set by monetization layer
};

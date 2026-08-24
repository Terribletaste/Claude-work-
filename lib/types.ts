export type Branch =
  | "trades"
  | "healthcare"
  | "tech"
  | "transport-energy"
  | "sales-business"
  | "public-safety";

export type Physicality = "physical" | "mixed" | "desk";

export type CareerNode = {
  id: string;
  name: string;
  branch: Branch;
  tier: 1 | 2 | 3; // 1 = starting perk, 2 = mid, 3 = >$100K capstone
  medianSalary: number;
  hundredKPath: string; // one-liner on how you clear $100K
  yearsToHundredK: number; // typical
  upfrontCostUsd: number; // rough out-of-pocket to enter (school, tools, licenses)
  physicality: Physicality;
  relocationHelps: boolean; // materially easier if willing to move
  feltonEligible: boolean; // realistic w/ a felony record (may vary by state)
  requires: string[]; // ids of prerequisite nodes
  credentials: string[]; // certs, licenses, apprenticeships
  employers: string[]; // typical employer types / examples
  blurb: string;
  // grid position on the constellation, in canvas units (0-1000 range roughly)
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

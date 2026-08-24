import type { CareerNode, QuizAnswers } from "./types";

export const DEFAULT_ANSWERS: QuizAnswers = {
  willingToRelocate: true,
  criminalRecord: false,
  physicality: "any",
  maxUpfrontCostUsd: 25000,
  maxYears: 10,
};

export type EligibilityReason = {
  ok: boolean;
  reasons: string[]; // reasons node is *excluded*, if any
};

export function nodeEligibility(
  node: CareerNode,
  answers: QuizAnswers,
): EligibilityReason {
  const reasons: string[] = [];

  if (!answers.willingToRelocate && node.relocationHelps && node.tier === 3) {
    // capstone nodes that materially require moving get downweighted, not excluded
    // (so the user can still see them). We flag but keep ok=true.
  }

  if (answers.criminalRecord && !node.feltonEligible) {
    reasons.push("Typical licensing rules exclude candidates with a felony record.");
  }

  if (answers.physicality !== "any" && node.physicality !== answers.physicality) {
    // desk-seekers really do want to exclude physical roles; physical-seekers might tolerate mixed
    if (answers.physicality === "desk" && node.physicality !== "desk") {
      reasons.push("You said desk-based; this role is physically demanding.");
    }
    if (answers.physicality === "physical" && node.physicality === "desk") {
      reasons.push("You wanted a physical role; this one is desk-based.");
    }
  }

  if (node.upfrontCostUsd > answers.maxUpfrontCostUsd) {
    reasons.push(
      `Upfront cost ~$${node.upfrontCostUsd.toLocaleString()} exceeds your budget of $${answers.maxUpfrontCostUsd.toLocaleString()}.`,
    );
  }

  if (node.yearsToHundredK > answers.maxYears) {
    reasons.push(
      `Typical timeline to $100K is ${node.yearsToHundredK} yrs; you set a ${answers.maxYears}-yr cap.`,
    );
  }

  return { ok: reasons.length === 0, reasons };
}

// Given all careers + answers, return the ids of viable capstones (tier 3)
// plus the full path (prerequisite chain) leading into them.
export function viablePaths(
  nodes: CareerNode[],
  answers: QuizAnswers,
): { capstoneIds: Set<string>; pathIds: Set<string> } {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const capstoneIds = new Set<string>();
  const pathIds = new Set<string>();

  const collectPath = (id: string, visited = new Set<string>()) => {
    if (visited.has(id)) return;
    visited.add(id);
    pathIds.add(id);
    const n = byId.get(id);
    if (!n) return;
    for (const req of n.requires) collectPath(req, visited);
  };

  for (const n of nodes) {
    if (n.tier !== 3) continue;
    // Capstone eligible if it AND every prerequisite are eligible.
    const chain: CareerNode[] = [];
    const walk = (id: string, seen = new Set<string>()) => {
      if (seen.has(id)) return;
      seen.add(id);
      const nn = byId.get(id);
      if (!nn) return;
      chain.push(nn);
      for (const req of nn.requires) walk(req, seen);
    };
    walk(n.id);
    const chainOk = chain.every((c) => nodeEligibility(c, answers).ok);
    if (chainOk) {
      capstoneIds.add(n.id);
      for (const c of chain) collectPath(c.id);
    }
  }
  return { capstoneIds, pathIds };
}

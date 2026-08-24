"use client";

import { useMemo, useState } from "react";
import type { CareerNode, JobListing, QuizAnswers } from "@/lib/types";
import { nodeEligibility, viablePaths } from "@/lib/filters";

type Props = {
  nodes: CareerNode[];
  answers: QuizAnswers;
};

const ORIGIN = { x: 500, y: 500 };

export default function SkillTree({ nodes, answers }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const [listings, setListings] = useState<JobListing[]>([]);
  const [loadingListings, setLoadingListings] = useState(false);

  const { pathIds, capstoneIds } = useMemo(
    () => viablePaths(nodes, answers),
    [nodes, answers],
  );

  const nodeMap = useMemo(
    () => new Map(nodes.map((n) => [n.id, n])),
    [nodes],
  );

  const selectedNode = selected ? nodeMap.get(selected) ?? null : null;

  const handleSelect = async (id: string) => {
    setSelected(id);
    setListings([]);
    setLoadingListings(true);
    try {
      const res = await fetch(`/api/jobs?career=${encodeURIComponent(id)}`);
      const data = (await res.json()) as { listings: JobListing[] };
      setListings(data.listings);
    } catch {
      setListings([]);
    } finally {
      setLoadingListings(false);
    }
  };

  return (
    <div className="grid gap-4 md:grid-cols-[1fr,320px]">
      <div className="relative aspect-square w-full overflow-hidden rounded-lg border border-white/10 bg-black/40">
        <svg
          viewBox="0 0 1000 1000"
          className="h-full w-full"
          role="img"
          aria-label="Career constellation"
        >
          {/* Constellation lines from origin to Tier 1, and prerequisite lines. */}
          {nodes.map((n) => {
            const isEligible = nodeEligibility(n, answers).ok;
            const onPath = pathIds.has(n.id);
            const parents = n.requires.length
              ? n.requires
              : ([null] as (string | null)[]);
            return parents.map((pid, i) => {
              const from = pid ? nodeMap.get(pid) : null;
              const start = from ? { x: from.x, y: from.y } : ORIGIN;
              const cls = !isEligible
                ? "constellation-line locked"
                : onPath
                  ? "constellation-line active"
                  : "constellation-line";
              return (
                <line
                  key={`${n.id}-line-${i}`}
                  x1={start.x}
                  y1={start.y}
                  x2={n.x}
                  y2={n.y}
                  className={cls}
                />
              );
            });
          })}

          {/* Origin marker */}
          <circle cx={ORIGIN.x} cy={ORIGIN.y} r={10} fill="#e8f1ff" opacity={0.8} />
          <circle cx={ORIGIN.x} cy={ORIGIN.y} r={18} fill="none" stroke="#e8f1ff" strokeOpacity={0.35} />
          <text
            x={ORIGIN.x}
            y={ORIGIN.y + 34}
            textAnchor="middle"
            className="h-display"
            fill="#e8f1ff"
            opacity={0.65}
            fontSize={12}
          >
            YOU
          </text>

          {/* Nodes */}
          {nodes.map((n) => {
            const eligible = nodeEligibility(n, answers).ok;
            const onPath = pathIds.has(n.id);
            const isCapstone = capstoneIds.has(n.id);
            const isSelected = selected === n.id;

            const baseR = n.tier === 3 ? 14 : n.tier === 2 ? 11 : 9;

            let fill = "#3a4152"; // locked
            let stroke = "rgba(255,255,255,0.25)";
            if (eligible) {
              fill = onPath ? "#f4c26b" : "#7cd7ff";
              stroke = onPath ? "#fff2d0" : "#c8ecff";
            }

            return (
              <g
                key={n.id}
                onClick={() => handleSelect(n.id)}
                style={{ cursor: "pointer" }}
                className={onPath ? "node-pulse" : ""}
              >
                {isCapstone && eligible && (
                  <circle
                    cx={n.x}
                    cy={n.y}
                    r={baseR + 12}
                    fill="none"
                    stroke="#f4c26b"
                    strokeOpacity={0.35}
                  />
                )}
                <circle
                  cx={n.x}
                  cy={n.y}
                  r={baseR}
                  fill={fill}
                  stroke={stroke}
                  strokeWidth={isSelected ? 3 : 1.2}
                  opacity={eligible ? 1 : 0.55}
                />
                <text
                  x={n.x}
                  y={n.y + baseR + 14}
                  textAnchor="middle"
                  fill={eligible ? "#e8f1ff" : "#7c8598"}
                  fontSize={12}
                  fontFamily="Inter, system-ui, sans-serif"
                >
                  {n.name}
                </text>
                {n.tier === 3 && (
                  <text
                    x={n.x}
                    y={n.y + baseR + 28}
                    textAnchor="middle"
                    fill="#f4c26b"
                    fontSize={10}
                    opacity={eligible ? 0.9 : 0.4}
                  >
                    ${(n.medianSalary / 1000).toFixed(0)}K
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      <DetailPanel
        node={selectedNode}
        eligibility={selectedNode ? nodeEligibility(selectedNode, answers) : null}
        listings={listings}
        loadingListings={loadingListings}
      />
    </div>
  );
}

function DetailPanel({
  node,
  eligibility,
  listings,
  loadingListings,
}: {
  node: CareerNode | null;
  eligibility: ReturnType<typeof nodeEligibility> | null;
  listings: JobListing[];
  loadingListings: boolean;
}) {
  if (!node)
    return (
      <div className="rounded-lg border border-white/10 bg-black/40 p-5 text-sm text-white/60 backdrop-blur">
        Click any star to see the path, the pay, and current job listings that
        clear $100K.
      </div>
    );

  return (
    <div className="space-y-4 rounded-lg border border-white/10 bg-black/40 p-5 backdrop-blur">
      <div>
        <div className="text-xs uppercase tracking-widest text-white/50">
          Tier {node.tier} · {branchLabel(node.branch)}
        </div>
        <h3 className="h-display text-xl text-ember">{node.name}</h3>
        <p className="mt-1 text-sm text-white/70">{node.blurb}</p>
      </div>

      <dl className="grid grid-cols-2 gap-3 text-sm">
        <Stat label="Median pay" value={`$${node.medianSalary.toLocaleString()}`} />
        <Stat
          label="Training to hire"
          value={
            node.entryMonths === 0
              ? "none / on-the-job"
              : node.entryMonths < 12
                ? `${node.entryMonths} mo`
                : `${(node.entryMonths / 12).toFixed(node.entryMonths % 12 === 0 ? 0 : 1)} yr`
          }
        />
        <Stat
          label="At $100K in"
          value={
            node.yearsToHundredK === 0
              ? "day one"
              : `${node.yearsToHundredK} yr${node.yearsToHundredK === 1 ? "" : "s"}`
          }
        />
        <Stat
          label="Upfront cost"
          value={node.upfrontCostUsd === 0 ? "$0" : `~$${node.upfrontCostUsd.toLocaleString()}`}
        />
      </dl>

      <div>
        <div className="text-xs uppercase tracking-widest text-white/50">$100K path</div>
        <p className="text-sm">{node.hundredKPath}</p>
      </div>

      <div>
        <div className="text-xs uppercase tracking-widest text-white/50">Credentials</div>
        <ul className="mt-1 list-inside list-disc text-sm text-white/80">
          {node.credentials.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </div>

      {eligibility && !eligibility.ok && (
        <div className="rounded border border-red-400/30 bg-red-500/5 p-3 text-xs text-red-200">
          <div className="mb-1 font-semibold">Locked based on your answers:</div>
          <ul className="list-inside list-disc space-y-1">
            {eligibility.reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <div className="mb-1 text-xs uppercase tracking-widest text-white/50">
          Live listings ≥ $100K
        </div>
        {loadingListings && <p className="text-xs text-white/50">Loading…</p>}
        {!loadingListings && listings.length === 0 && (
          <p className="text-xs text-white/50">No listings meeting the pay floor right now.</p>
        )}
        <ul className="space-y-2">
          {listings.slice(0, 5).map((l) => (
            <li key={l.id} className="rounded border border-white/10 bg-white/5 p-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-white">{l.title}</span>
                <span className="text-ember">${l.annualPayUsd.toLocaleString()}</span>
              </div>
              <div className="text-white/60">
                {l.company} · {l.location}
              </div>
              <a
                href={l.affiliateUrl ?? l.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 inline-block text-aurora underline underline-offset-2 hover:text-white"
              >
                View listing →
              </a>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-widest text-white/50">{label}</dt>
      <dd className="text-sm text-white/90">{value}</dd>
    </div>
  );
}

function branchLabel(b: CareerNode["branch"]): string {
  switch (b) {
    case "trades":
      return "Skilled Trades";
    case "energy":
      return "Energy";
    case "transport":
      return "Transport";
    case "public-safety":
      return "Public Safety";
    case "sales-business":
      return "Sales & Business";
    case "tech":
      return "Tech";
  }
}

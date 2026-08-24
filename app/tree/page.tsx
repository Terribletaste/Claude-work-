"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import FilterPanel from "@/components/FilterPanel";
import SkillTree from "@/components/SkillTree";
import { CAREERS } from "@/lib/careers";
import { DEFAULT_ANSWERS, nodeEligibility } from "@/lib/filters";
import type { QuizAnswers } from "@/lib/types";

export default function TreePage() {
  const [answers, setAnswers] = useState<QuizAnswers>(DEFAULT_ANSWERS);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem("p100k:answers");
      if (raw) setAnswers({ ...DEFAULT_ANSWERS, ...JSON.parse(raw) });
    } catch {
      // ignore
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem("p100k:answers", JSON.stringify(answers));
    } catch {
      // ignore
    }
  }, [answers, hydrated]);

  const visibleCount = useMemo(
    () => CAREERS.filter((n) => nodeEligibility(n, answers).ok).length,
    [answers],
  );

  return (
    <main className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <Link href="/" className="h-display text-lg text-star hover:text-ember">
          Path to 100K
        </Link>
        <Link href="/" className="text-xs text-white/50 hover:text-white">
          ← Home
        </Link>
      </div>

      <div className="grid gap-6 md:grid-cols-[auto,1fr]">
        <FilterPanel
          answers={answers}
          onChange={setAnswers}
          visibleCount={visibleCount}
          totalCount={CAREERS.length}
        />
        <SkillTree nodes={CAREERS} answers={answers} />
      </div>

      <footer className="mt-10 text-center text-xs text-white/40">
        Every capstone is a $100K+ role reachable with no college degree in
        roughly two years or less. Salary and timeline estimates are directional
        (BLS, union scale, industry surveys). Job listings are placeholders
        while the ingestion agent comes online.
      </footer>
    </main>
  );
}

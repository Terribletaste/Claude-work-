"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import QuizWizard from "@/components/QuizWizard";
import type { QuizAnswers } from "@/lib/types";
import { DEFAULT_ANSWERS } from "@/lib/filters";

export default function LandingPage() {
  const router = useRouter();
  const [showQuiz, setShowQuiz] = useState(false);
  const [hasSavedAnswers, setHasSavedAnswers] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      setHasSavedAnswers(!!window.localStorage.getItem("p100k:answers"));
    } catch {
      // ignore
    }
  }, []);

  const complete = (answers: QuizAnswers) => {
    try {
      window.localStorage.setItem("p100k:answers", JSON.stringify(answers));
    } catch {
      // ignore
    }
    router.push("/tree");
  };

  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <header className="mb-16 text-center">
        <div className="mb-3 text-xs uppercase tracking-[0.4em] text-aurora">
          U.S. careers · no degree required
        </div>
        <h1 className="h-display text-5xl leading-tight text-star sm:text-6xl">
          The Path to <span className="text-ember">100K</span>
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-white/70">
          A skill-tree of American jobs that pay over $100,000 a year and don&rsquo;t
          require a college degree. Answer a few questions and the constellation
          lights up the paths that are actually open to you.
        </p>
      </header>

      {!showQuiz ? (
        <section className="mx-auto max-w-xl space-y-4 text-center">
          <button
            onClick={() => setShowQuiz(true)}
            className="rounded bg-ember px-6 py-3 font-semibold text-black shadow-emberGlow transition hover:brightness-110"
          >
            Start the quiz
          </button>
          <div className="flex justify-center gap-4 text-sm">
            <button
              onClick={() => complete(DEFAULT_ANSWERS)}
              className="text-white/60 underline underline-offset-4 hover:text-white"
            >
              Skip and just explore the tree
            </button>
            {hasSavedAnswers && (
              <button
                onClick={() => router.push("/tree")}
                className="text-aurora underline underline-offset-4 hover:text-white"
              >
                Resume with saved answers
              </button>
            )}
          </div>
          <ul className="mt-10 grid gap-4 text-left text-sm text-white/70 sm:grid-cols-3">
            <Feature title="Real pay floor">
              Every job on this map clears $100K/year (or the hourly equivalent) in
              its target tier.
            </Feature>
            <Feature title="Six branches">
              Trades, healthcare, tech, transport &amp; energy, sales &amp; business,
              and public safety.
            </Feature>
            <Feature title="Filtered to your situation">
              Willing to move? Felony on record? Cash-strapped? The tree respects it.
            </Feature>
          </ul>
        </section>
      ) : (
        <QuizWizard onComplete={complete} />
      )}
    </main>
  );
}

function Feature({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <li className="rounded border border-white/10 bg-black/30 p-4 backdrop-blur">
      <div className="mb-1 h-display text-ember">{title}</div>
      <p>{children}</p>
    </li>
  );
}

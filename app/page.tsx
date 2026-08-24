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
          U.S. jobs · no college · $100K now
        </div>
        <h1 className="h-display text-5xl leading-tight text-star sm:text-6xl">
          The Path to <span className="text-ember">100K</span>
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-white/70">
          A constellation of American jobs that pay <strong>over $100,000 a year today</strong>,
          reachable through a certification, license, or paid apprenticeship &mdash; not
          a college degree. Every star is a role you can be hired into and earning six
          figures at within about two years. Answer five questions and we&rsquo;ll light
          up the ones actually open to you.
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
            <Feature title="No degree, ever">
              Certs, licenses, and paid apprenticeships only. If it needs a
              bachelor&rsquo;s or associate&rsquo;s, it&rsquo;s not on this map.
            </Feature>
            <Feature title="$100K now — not someday">
              Every role pays $100K on the day you land it, or within ~2 years of
              starting from zero. Growth paths that take 5+ years are cut.
            </Feature>
            <Feature title="Upskill or relocate">
              Two levers. The map is honest about which roles need you to move (union
              trades, offshore energy, top-metro public safety) versus which travel.
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

"use client";

import { useState } from "react";
import type { QuizAnswers } from "@/lib/types";
import { DEFAULT_ANSWERS } from "@/lib/filters";

type Props = {
  onComplete: (answers: QuizAnswers) => void;
};

const steps = [
  "relocate",
  "record",
  "physicality",
  "cash",
  "years",
] as const;
type Step = (typeof steps)[number];

export default function QuizWizard({ onComplete }: Props) {
  const [answers, setAnswers] = useState<QuizAnswers>(DEFAULT_ANSWERS);
  const [i, setI] = useState(0);
  const step: Step = steps[i];

  const set = <K extends keyof QuizAnswers>(k: K, v: QuizAnswers[K]) =>
    setAnswers((a) => ({ ...a, [k]: v }));

  const next = () => {
    if (i === steps.length - 1) onComplete(answers);
    else setI(i + 1);
  };
  const back = () => setI(Math.max(0, i - 1));

  return (
    <div className="mx-auto max-w-xl rounded-lg border border-white/10 bg-black/40 p-6 backdrop-blur">
      <div className="mb-4 flex items-center justify-between text-xs text-white/60">
        <span>
          Step {i + 1} of {steps.length}
        </span>
        <div className="flex gap-1">
          {steps.map((_, idx) => (
            <span
              key={idx}
              className={`h-1 w-8 rounded ${
                idx <= i ? "bg-ember" : "bg-white/15"
              }`}
            />
          ))}
        </div>
      </div>

      {step === "relocate" && (
        <QuestionYesNo
          question="Are you willing to move for the right job?"
          value={answers.willingToRelocate}
          onChange={(v) => set("willingToRelocate", v)}
        />
      )}
      {step === "record" && (
        <QuestionYesNo
          question="Do you have a felony conviction on your record?"
          value={answers.criminalRecord}
          onChange={(v) => set("criminalRecord", v)}
          note="Some licenses (nursing, real estate, federal jobs) restrict this. We'll flag paths that typically won't clear."
        />
      )}
      {step === "physicality" && (
        <div>
          <h3 className="mb-3 text-lg">What kind of work do you want?</h3>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {(["any", "physical", "mixed", "desk"] as const).map((v) => (
              <button
                key={v}
                onClick={() => set("physicality", v)}
                className={`rounded border px-3 py-2 text-sm capitalize transition ${
                  answers.physicality === v
                    ? "border-ember bg-ember/10 text-ember"
                    : "border-white/15 hover:border-white/40"
                }`}
              >
                {v}
              </button>
            ))}
          </div>
        </div>
      )}
      {step === "cash" && (
        <QuestionSlider
          question="How much cash can you put toward training, tools, or licensing up front?"
          value={answers.maxUpfrontCostUsd}
          onChange={(v) => set("maxUpfrontCostUsd", v)}
          min={0}
          max={25000}
          step={500}
          format={(v) => (v === 0 ? "$0" : `$${v.toLocaleString()}`)}
        />
      )}
      {step === "years" && (
        <QuestionSlider
          question="How many years until you want to be earning $100K?"
          value={answers.maxYears}
          onChange={(v) => set("maxYears", v)}
          min={1}
          max={5}
          step={1}
          format={(v) => `${v} year${v === 1 ? "" : "s"}`}
        />
      )}

      <div className="mt-6 flex items-center justify-between">
        <button
          onClick={back}
          disabled={i === 0}
          className="text-sm text-white/50 hover:text-white/80 disabled:opacity-30"
        >
          ← Back
        </button>
        <div className="flex gap-3">
          <button
            onClick={() => onComplete(DEFAULT_ANSWERS)}
            className="text-sm text-white/50 underline underline-offset-4 hover:text-white/80"
          >
            Skip, just show me everything
          </button>
          <button
            onClick={next}
            className="rounded bg-ember px-4 py-2 text-sm font-semibold text-black shadow-emberGlow hover:brightness-110"
          >
            {i === steps.length - 1 ? "See my paths" : "Next"}
          </button>
        </div>
      </div>
    </div>
  );
}

function QuestionYesNo({
  question,
  value,
  onChange,
  note,
}: {
  question: string;
  value: boolean;
  onChange: (v: boolean) => void;
  note?: string;
}) {
  return (
    <div>
      <h3 className="mb-3 text-lg">{question}</h3>
      <div className="flex gap-3">
        {[
          { label: "Yes", v: true },
          { label: "No", v: false },
        ].map((o) => (
          <button
            key={o.label}
            onClick={() => onChange(o.v)}
            className={`flex-1 rounded border px-4 py-3 transition ${
              value === o.v
                ? "border-ember bg-ember/10 text-ember"
                : "border-white/15 hover:border-white/40"
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
      {note && <p className="mt-3 text-xs text-white/50">{note}</p>}
    </div>
  );
}

function QuestionSlider({
  question,
  value,
  onChange,
  min,
  max,
  step,
  format,
}: {
  question: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step: number;
  format: (v: number) => string;
}) {
  return (
    <div>
      <h3 className="mb-3 text-lg">{question}</h3>
      <div className="text-2xl font-semibold text-ember">{format(value)}</div>
      <input
        aria-label={question}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-4 w-full accent-ember"
      />
      <div className="mt-1 flex justify-between text-xs text-white/40">
        <span>{format(min)}</span>
        <span>{format(max)}</span>
      </div>
    </div>
  );
}

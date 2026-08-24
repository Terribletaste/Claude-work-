"use client";

import type { QuizAnswers } from "@/lib/types";

type Props = {
  answers: QuizAnswers;
  onChange: (a: QuizAnswers) => void;
  visibleCount: number;
  totalCount: number;
};

export default function FilterPanel({
  answers,
  onChange,
  visibleCount,
  totalCount,
}: Props) {
  const set = <K extends keyof QuizAnswers>(k: K, v: QuizAnswers[K]) =>
    onChange({ ...answers, [k]: v });

  return (
    <aside className="w-full space-y-5 rounded-lg border border-white/10 bg-black/40 p-5 backdrop-blur md:w-72">
      <div>
        <h3 className="h-display text-sm uppercase tracking-widest text-ember">
          Your filters
        </h3>
        <p className="text-xs text-white/50">
          Showing {visibleCount} of {totalCount} careers
        </p>
      </div>

      <Toggle
        label="Willing to relocate"
        value={answers.willingToRelocate}
        onChange={(v) => set("willingToRelocate", v)}
      />
      <Toggle
        label="Felony on record"
        value={answers.criminalRecord}
        onChange={(v) => set("criminalRecord", v)}
      />

      <div>
        <label className="mb-1 block text-xs text-white/60">Work type</label>
        <div className="grid grid-cols-4 gap-1">
          {(["any", "physical", "mixed", "desk"] as const).map((v) => (
            <button
              key={v}
              onClick={() => set("physicality", v)}
              className={`rounded border px-2 py-1 text-xs capitalize ${
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

      <Slider
        label="Max upfront cost"
        value={answers.maxUpfrontCostUsd}
        onChange={(v) => set("maxUpfrontCostUsd", v)}
        min={0}
        max={30000}
        step={500}
        format={(v) => (v === 0 ? "$0" : `$${v.toLocaleString()}`)}
      />
      <Slider
        label="Max years to $100K"
        value={answers.maxYears}
        onChange={(v) => set("maxYears", v)}
        min={1}
        max={10}
        step={1}
        format={(v) => `${v} yr${v === 1 ? "" : "s"}`}
      />
    </aside>
  );
}

function Toggle({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between text-sm">
      <span>{label}</span>
      <button
        role="switch"
        aria-checked={value}
        onClick={() => onChange(!value)}
        className={`relative h-5 w-9 rounded-full transition ${
          value ? "bg-ember" : "bg-white/20"
        }`}
      >
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition ${
            value ? "left-4" : "left-0.5"
          }`}
        />
      </button>
    </label>
  );
}

function Slider({
  label,
  value,
  onChange,
  min,
  max,
  step,
  format,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step: number;
  format: (v: number) => string;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs text-white/60">
        <span>{label}</span>
        <span className="text-ember">{format(value)}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-ember"
      />
    </div>
  );
}

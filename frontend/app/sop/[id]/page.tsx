"use client";

import { useEffect, useState } from "react";
import { formatTimestamp, getSop, Sop } from "@/lib/api";

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const percent = Math.round(confidence * 100);
  const color =
    confidence >= 0.8 ? "text-signal-green border-signal-green/50" :
    confidence >= 0.5 ? "text-amber-400 border-amber-500/50" :
    "text-signal-red border-signal-red/50";
  return (
    <span className={`stamp border px-1.5 py-0.5 text-[10px] ${color}`}>
      {percent}% confidence
    </span>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border border-graphite-700 bg-graphite-900 p-5">
      <h2 className="stamp mb-3 text-xs text-amber-400">{title}</h2>
      {children}
    </section>
  );
}

function TagList({ items, emptyLabel }: { items: string[]; emptyLabel: string }) {
  if (!items.length) {
    return <p className="text-sm italic text-graphite-500">{emptyLabel}</p>;
  }
  return (
    <ul className="flex flex-wrap gap-2">
      {items.map((item, i) => (
        <li key={i} className="border border-graphite-600 bg-graphite-800 px-2.5 py-1 text-xs text-graphite-200">
          {item}
        </li>
      ))}
    </ul>
  );
}

export default function SopPage({ params }: { params: { id: string } }) {
  const [sop, setSop] = useState<Sop | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSop(params.id)
      .then(setSop)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load this SOP."));
  }, [params.id]);

  if (error) {
    return (
      <div className="mx-auto max-w-2xl border border-signal-red/40 bg-signal-red/10 p-6">
        <p className="stamp text-xs text-signal-red">Could not load SOP</p>
        <p className="mt-2 text-sm text-graphite-200">{error}</p>
      </div>
    );
  }

  if (!sop) {
    return <p className="font-mono text-sm text-graphite-500">Loading SOP…</p>;
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div className="border border-graphite-700 bg-graphite-900 bg-diagonal-hatch p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span
            className={`stamp border px-2 py-1 text-[10px] ${
              sop.status === "REVIEW_REQUIRED"
                ? "border-amber-500/60 text-amber-400"
                : "border-signal-green/60 text-signal-green"
            }`}
          >
            {sop.status.replace(/_/g, " ")}
          </span>
          <span className="stamp text-[10px] text-graphite-500">
            Generated {new Date(sop.created_at).toLocaleString()}
          </span>
        </div>
        <h1 className="mt-4 font-display text-2xl font-bold text-graphite-100">{sop.title}</h1>
        <dl className="mt-4 grid grid-cols-2 gap-4 text-xs text-graphite-400 sm:grid-cols-4">
          <div>
            <dt className="stamp text-graphite-500">Duration</dt>
            <dd className="mt-1 font-mono text-graphite-200">{sop.estimated_duration}</dd>
          </div>
          <div>
            <dt className="stamp text-graphite-500">Steps</dt>
            <dd className="mt-1 font-mono text-graphite-200">{sop.steps.length}</dd>
          </div>
          <div className="col-span-2">
            <dt className="stamp text-graphite-500">Source video</dt>
            <dd className="mt-1 truncate font-mono text-graphite-200" title={sop.source_video}>
              {sop.source_video}
            </dd>
          </div>
        </dl>
      </div>

      <Section title="Purpose">
        <p className="text-sm leading-relaxed text-graphite-200">{sop.purpose}</p>
      </Section>

      <Section title="Scope">
        <p className="text-sm leading-relaxed text-graphite-200">{sop.scope}</p>
      </Section>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <Section title="Required tools">
          <TagList items={sop.required_tools} emptyLabel="Not specified in the source video." />
        </Section>
        <Section title="Required materials">
          <TagList items={sop.required_materials} emptyLabel="Not specified in the source video." />
        </Section>
      </div>

      <Section title="Safety">
        <TagList items={sop.safety} emptyLabel="No safety observations captured in the source video." />
      </Section>

      <section>
        <h2 className="stamp mb-4 text-xs text-amber-400">Procedure</h2>
        <ol className="flex flex-col gap-4">
          {sop.steps.map((step) => (
            <li key={step.step_number} className="border border-graphite-700 bg-graphite-900 p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-baseline gap-3">
                  <span className="font-display text-lg font-bold text-amber-400">
                    {String(step.step_number).padStart(2, "0")}
                  </span>
                  <h3 className="font-display text-base font-bold text-graphite-100">{step.title}</h3>
                </div>
                <ConfidenceBadge confidence={step.confidence} />
              </div>

              <p className="mt-2 font-mono text-xs text-graphite-500">
                {formatTimestamp(step.start_time)} – {formatTimestamp(step.end_time)}
                {step.visual_reference && <span className="ml-2">· ref: {step.visual_reference}</span>}
              </p>

              <p className="mt-3 text-sm leading-relaxed text-graphite-200">{step.description}</p>

              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div>
                  <p className="stamp text-[10px] text-graphite-500">Tools</p>
                  <p className="mt-1 text-xs text-graphite-300">
                    {step.tools.length ? step.tools.join(", ") : "—"}
                  </p>
                </div>
                <div>
                  <p className="stamp text-[10px] text-graphite-500">Materials</p>
                  <p className="mt-1 text-xs text-graphite-300">
                    {step.materials.length ? step.materials.join(", ") : "—"}
                  </p>
                </div>
                <div>
                  <p className="stamp text-[10px] text-graphite-500">Quality check</p>
                  <p className="mt-1 text-xs text-graphite-300">
                    {step.quality_check || "Not specified in the source video."}
                  </p>
                </div>
              </div>

              {step.safety_notes.length > 0 && (
                <div className="mt-3 border-l-2 border-amber-500/60 pl-3">
                  <p className="stamp text-[10px] text-amber-400">Safety note</p>
                  <ul className="mt-1 list-inside list-disc text-xs text-graphite-300">
                    {step.safety_notes.map((note, i) => (
                      <li key={i}>{note}</li>
                    ))}
                  </ul>
                </div>
              )}
            </li>
          ))}
        </ol>
      </section>

      <Section title="Quality checks (overall)">
        <TagList items={sop.quality_checks} emptyLabel="Not specified in the source video." />
      </Section>
    </div>
  );
}

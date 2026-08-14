import Link from "next/link";

export default function HomePage() {
  return (
    <div className="flex flex-col gap-10">
      <section className="border border-graphite-700 bg-graphite-900 bg-diagonal-hatch p-8">
        <p className="stamp mb-3 text-xs text-amber-400">Work Order Generator</p>
        <h1 className="font-display text-3xl font-bold leading-tight text-graphite-100 sm:text-4xl">
          Turn a floor-recorded training video into a
          <br className="hidden sm:block" /> reviewable Standard Operating Procedure.
        </h1>
        <p className="mt-4 max-w-2xl text-sm leading-relaxed text-graphite-300">
          The assistant watches the video frame by frame, listens to the narration, reads
          on-screen labels, and reconciles all three into a chronological activity timeline
          before drafting the SOP. Nothing is invented — anything not visible or audible in the
          source is marked{" "}
          <span className="font-mono text-graphite-200">&ldquo;Not specified in the source video.&rdquo;</span>
        </p>
        <Link
          href="/upload"
          className="mt-6 inline-flex items-center gap-2 border border-amber-500 bg-amber-500/10 px-5 py-2.5 text-sm font-medium text-amber-400 transition hover:bg-amber-500/20"
        >
          Start a new job →
        </Link>
      </section>

      <section className="grid grid-cols-1 gap-px border border-graphite-700 bg-graphite-700 sm:grid-cols-3">
        {[
          {
            step: "01",
            title: "Watch & listen",
            body: "Frames are sampled intelligently, transcribed with Whisper, and read with OCR for labels and torque values.",
          },
          {
            step: "02",
            title: "Build the timeline",
            body: "Qwen2.5:7b reconciles visual, spoken, and on-screen evidence into distinct, timestamped activities.",
          },
          {
            step: "03",
            title: "Draft & review",
            body: "A structured SOP is generated with a Review Required status — a supervisor signs off before it's official.",
          },
        ].map((item) => (
          <div key={item.step} className="bg-graphite-950 p-6">
            <span className="stamp text-xs text-amber-500">{item.step}</span>
            <h3 className="mt-2 font-display text-base font-bold text-graphite-100">{item.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-graphite-400">{item.body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}

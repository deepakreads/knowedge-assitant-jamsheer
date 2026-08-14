"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { getJobStatus, JobStatusResponse, STAGE_LABELS, STAGE_ORDER } from "@/lib/api";

const POLL_INTERVAL_MS = 3000;

export default function ProcessingPage({ params }: { params: { jobId: string } }) {
  const router = useRouter();
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const redirectedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    async function poll() {
      try {
        const status = await getJobStatus(params.jobId);
        if (cancelled) return;
        setJob(status);
        setPollError(null);

        if (status.status === "completed" && status.sop_id && !redirectedRef.current) {
          redirectedRef.current = true;
          router.push(`/sop/${status.sop_id}`);
          return;
        }
        if (status.status !== "error") {
          timer = setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (cancelled) return;
        setPollError(err instanceof Error ? err.message : "Could not reach the backend.");
        timer = setTimeout(poll, POLL_INTERVAL_MS);
      }
    }

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [params.jobId, router]);

  const currentStageIndex = job ? STAGE_ORDER.indexOf(job.stage) : -1;

  return (
    <div className="mx-auto max-w-2xl">
      <p className="stamp mb-2 text-xs text-amber-400">Step 2 of 3</p>
      <h1 className="font-display text-2xl font-bold text-graphite-100">Processing your video</h1>
      <p className="mt-2 font-mono text-xs text-graphite-500">job_id: {params.jobId}</p>

      {pollError && (
        <p className="mt-4 border border-signal-red/40 bg-signal-red/10 px-3 py-2 text-sm text-signal-red">
          {pollError} — retrying…
        </p>
      )}

      {job?.status === "error" && (
        <div className="mt-6 border border-signal-red/40 bg-signal-red/10 p-4">
          <p className="stamp text-xs text-signal-red">Processing failed</p>
          <p className="mt-2 text-sm text-graphite-200">
            {job.error_message || "An unknown error occurred while processing this video."}
          </p>
        </div>
      )}

      <div className="mt-8 border border-graphite-700 bg-graphite-900 p-6">
        <div className="progress-track h-2 w-full overflow-hidden border border-graphite-700">
          <div
            className="h-full bg-amber-500 transition-all duration-500"
            style={{ width: `${job?.progress ?? 0}%` }}
          />
        </div>
        <p className="mt-2 font-mono text-xs text-graphite-400">{job?.progress ?? 0}%</p>

        <ul className="mt-6 flex flex-col gap-2.5">
          {STAGE_ORDER.map((stage, index) => {
            const isDone = currentStageIndex > index || (job?.status === "completed" && stage === "completed");
            const isCurrent = currentStageIndex === index && job?.status === "processing";
            return (
              <li key={stage} className="flex items-center gap-3 text-sm">
                <span
                  className={`flex h-4 w-4 shrink-0 items-center justify-center border text-[10px] ${
                    isDone
                      ? "border-signal-green bg-signal-green/20 text-signal-green"
                      : isCurrent
                      ? "border-amber-500 bg-amber-500/20 text-amber-400"
                      : "border-graphite-600 text-graphite-600"
                  }`}
                >
                  {isDone ? "✓" : isCurrent ? "●" : "○"}
                </span>
                <span className={isDone || isCurrent ? "text-graphite-100" : "text-graphite-500"}>
                  {STAGE_LABELS[stage]}
                </span>
              </li>
            );
          })}
        </ul>
      </div>

      <p className="mt-4 text-xs text-graphite-500">
        This page updates automatically every few seconds. Vision and reasoning models run
        locally, so larger videos take longer — feel free to leave this tab open in the
        background.
      </p>
    </div>
  );
}

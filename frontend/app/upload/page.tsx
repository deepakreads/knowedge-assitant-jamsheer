"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { uploadVideo } from "@/lib/api";

const ALLOWED_EXTENSIONS = [".mp4", ".avi", ".mov", ".mkv"];

export default function UploadPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [uploadPercent, setUploadPercent] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  function validateAndSetFile(candidate: File | null) {
    setError(null);
    if (!candidate) {
      setFile(null);
      return;
    }
    const ext = "." + candidate.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError(`Unsupported file type ${ext}. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`);
      setFile(null);
      return;
    }
    setFile(candidate);
    if (!title) {
      setTitle(candidate.name.replace(/\.[^/.]+$/, ""));
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("Select a video file first.");
      return;
    }
    setError(null);
    setUploadPercent(0);
    try {
      const result = await uploadVideo(file, title, description, setUploadPercent);
      router.push(`/processing/${result.job_id}`);
    } catch (err) {
      setUploadPercent(null);
      setError(err instanceof Error ? err.message : "Upload failed.");
    }
  }

  const isUploading = uploadPercent !== null;

  return (
    <div className="mx-auto max-w-2xl">
      <p className="stamp mb-2 text-xs text-amber-400">Step 1 of 3</p>
      <h1 className="font-display text-2xl font-bold text-graphite-100">Submit a training video</h1>
      <p className="mt-2 text-sm text-graphite-400">
        MP4, AVI, MOV, or MKV. The video is processed locally — nothing leaves your Ollama host.
      </p>

      <form onSubmit={handleSubmit} className="mt-8 flex flex-col gap-6">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            validateAndSetFile(e.dataTransfer.files?.[0] ?? null);
          }}
          onClick={() => fileInputRef.current?.click()}
          className={`cursor-pointer border-2 border-dashed p-10 text-center transition ${
            isDragging ? "border-amber-500 bg-amber-500/5" : "border-graphite-700 bg-graphite-900"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={ALLOWED_EXTENSIONS.join(",")}
            className="hidden"
            onChange={(e) => validateAndSetFile(e.target.files?.[0] ?? null)}
          />
          {file ? (
            <div>
              <p className="font-mono text-sm text-graphite-100">{file.name}</p>
              <p className="mt-1 text-xs text-graphite-400">{(file.size / (1024 * 1024)).toFixed(1)} MB</p>
            </div>
          ) : (
            <div>
              <p className="text-sm text-graphite-300">Drop a video here, or click to browse</p>
              <p className="mt-1 text-xs text-graphite-500">{ALLOWED_EXTENSIONS.join("  ·  ")}</p>
            </div>
          )}
        </div>

        <label className="flex flex-col gap-1.5">
          <span className="stamp text-xs text-graphite-400">Title</span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Bracket Assembly — Station 4"
            className="border border-graphite-700 bg-graphite-900 px-3 py-2 text-sm text-graphite-100 outline-none placeholder:text-graphite-600 focus:border-amber-500"
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="stamp text-xs text-graphite-400">Description (optional)</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Any context useful for the reviewer"
            className="border border-graphite-700 bg-graphite-900 px-3 py-2 text-sm text-graphite-100 outline-none placeholder:text-graphite-600 focus:border-amber-500"
          />
        </label>

        {error && (
          <p className="border border-signal-red/40 bg-signal-red/10 px-3 py-2 text-sm text-signal-red">
            {error}
          </p>
        )}

        {isUploading && (
          <div>
            <div className="progress-track h-2 w-full overflow-hidden border border-graphite-700">
              <div
                className="h-full bg-amber-500 transition-all duration-300"
                style={{ width: `${uploadPercent}%` }}
              />
            </div>
            <p className="mt-1.5 font-mono text-xs text-graphite-400">Uploading… {uploadPercent}%</p>
          </div>
        )}

        <button
          type="submit"
          disabled={!file || isUploading}
          className="border border-amber-500 bg-amber-500/10 px-5 py-2.5 text-sm font-medium text-amber-400 transition hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:border-graphite-700 disabled:bg-transparent disabled:text-graphite-600"
        >
          {isUploading ? "Uploading…" : "Upload & start processing"}
        </button>
      </form>
    </div>
  );
}

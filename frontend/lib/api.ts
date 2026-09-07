export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export type JobStage =
  | "uploading"
  | "extracting_frames"
  | "analyzing_frames"
  | "transcribing"
  | "ocr"
  | "building_timeline"
  | "generating_sop"
  | "completed"
  | "error";

export interface JobStatusResponse {
  job_id: string;
  status: "processing" | "completed" | "error";
  progress: number;
  stage: JobStage;
  error_message?: string | null;
  sop_generated?: boolean;
  sop_id?: string | null;
  sop_steps?: SopStep[];
}

export interface UploadResponse {
  job_id: string;
  status: string;
  progress: number;
}

export interface SopStep {
  step_number: number;
  title: string;
  description: string;
  start_time: number;
  end_time: number;
  tools: string[];
  materials: string[];
  safety_notes: string[];
  quality_check: string | null;
  visual_reference: string | null;
  confidence: number;
}

export interface Sop {
  id: string;
  job_id: string;
  status: string;
  title: string;
  purpose: string;
  scope: string;
  required_tools: string[];
  required_materials: string[];
  safety: string[];
  steps: SopStep[];
  quality_checks: string[];
  estimated_duration: string;
  source_video: string;
  created_at: string;
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore parse failures, fall back to statusText
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function uploadVideo(
  file: File,
  title: string,
  description: string,
  onProgress?: (percent: number) => void,
  department?: string,
  machineName?: string,
  machineImage?: File | null
): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    if (title) form.append("title", title);
    if (description) form.append("description", description);
    if (department) form.append("department", department);
    if (machineName) form.append("machine_name", machineName);
    if (machineImage) form.append("machine_picture", machineImage);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/api/video-processing/upload`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      try {
        const body = JSON.parse(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(body);
        } else {
          reject(new Error(body.detail || "Upload failed"));
        }
      } catch {
        reject(new Error("Upload failed: could not parse server response"));
      }
    };
    xhr.onerror = () => reject(new Error("Upload failed: network error"));

    xhr.send(form);
  });
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const res = await fetch(`${API_BASE_URL}/api/video-processing/jobs/${jobId}`, {
    cache: "no-store",
  });
  return handle<JobStatusResponse>(res);
}

export async function getSop(sopId: string): Promise<Sop> {
  const res = await fetch(`${API_BASE_URL}/api/sop-generation/sops/${sopId}`, {
    cache: "no-store",
  });
  return handle<Sop>(res);
}

export function frameImageUrl(jobId: string, framePath: string | null): string | null {
  if (!framePath) return null;
  // frame_path from the backend is an absolute filesystem path; we only
  // need the filename to build a static-serving URL if/when the backend
  // exposes one. For the MVP we show the filename as a reference label
  // instead of fetching the binary, since the backend does not yet mount
  // a static file route for frames.
  return null;
}

export function formatTimestamp(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.floor(totalSeconds % 60);
  return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
}

export const STAGE_LABELS: Record<JobStage, string> = {
  uploading: "Uploading",
  extracting_frames: "Extracting frames",
  analyzing_frames: "Analyzing activities",
  transcribing: "Transcribing audio",
  ocr: "Reading on-screen text",
  building_timeline: "Building activity timeline",
  generating_sop: "Generating SOP",
  completed: "Completed",
  error: "Error",
};

export const STAGE_ORDER: JobStage[] = [
  "uploading",
  "extracting_frames",
  "analyzing_frames",
  "transcribing",
  "ocr",
  "building_timeline",
  "generating_sop",
  "completed",
];

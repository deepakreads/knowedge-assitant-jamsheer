"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

interface SopStep {
  step_number: number;
  title: string;
  description: string;
}

interface Sop {
  id: string;
  title: string;
  steps: SopStep[];
}

export default function CameraMonitorPage() {
  const params = useParams();
  const sopId = params.sopId as string;

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const [sop, setSop] = useState<Sop | null>(null);
  const [isMonitoring, setIsMonitoring] = useState<boolean>(false);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [statusMessage, setStatusMessage] = useState<string>("Waiting for initial step to begin...");
  const [currentStepDetected, setCurrentStepDetected] = useState<string>("Not Started / Waiting");
  const [detectedStepNumber, setDetectedStepNumber] = useState<number>(0);
  const [isViolation, setIsViolation] = useState<boolean>(false);
  const [evaluating, setEvaluating] = useState<boolean>(false);

  // Consecutive violation counter to eliminate false positives from isolated faulty frames
  const consecutiveViolationsRef = useRef<number>(0);
  const CONSECUTIVE_THRESHOLD = 2;

  useEffect(() => {
    async function fetchSop() {
      try {
        const res = await fetch(`http://localhost:8000/api/sop-generation/sops/${sopId}`);
        if (!res.ok) throw new Error("Failed to load SOP details.");
        const data = await res.json();
        setSop(data);
      } catch (err: any) {
        setError(err.message || "Error loading SOP");
      } finally {
        setLoading(false);
      }
    }
    fetchSop();
  }, [sopId]);

  useEffect(() => {
    async function setupCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: false });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch (err) {
        setError("Unable to access webcam. Please check browser permissions.");
      }
    }
    setupCamera();

    return () => {
      if (videoRef.current && videoRef.current.srcObject) {
        const stream = videoRef.current.srcObject as MediaStream;
        stream.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const playBeep = () => {
    if (isMuted) return;
    try {
      const AudioContextWindow = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioContextWindow) return;
      const ctx = new AudioContextWindow();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      gain.gain.setValueAtTime(0.25, ctx.currentTime);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.35);
    } catch (e) {
      console.error("Audio beep failed:", e);
    }
  };

  useEffect(() => {
    let interval: NodeJS.Timeout;
    let isExecuting = false;

    if (isMonitoring && sop) {
      interval = setInterval(async () => {
        if (isExecuting || !videoRef.current || !canvasRef.current) return;
        const video = videoRef.current;
        const canvas = canvasRef.current;
        
        if (video.videoWidth === 0 || video.videoHeight === 0) return;

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        isExecuting = true;
        canvas.toBlob(async (blob) => {
          if (!blob) {
            isExecuting = false;
            return;
          }
          const formData = new FormData();
          formData.append("file", blob, "webcam_frame.jpg");

          setEvaluating(true);
          try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000); // 10s timeout protection

            const res = await fetch(`http://localhost:8000/api/sop-generation/sops/${sopId}/evaluate-frame`, {
              method: "POST",
              body: formData,
              signal: controller.signal,
            });
            clearTimeout(timeoutId);

            if (res.ok) {
              const data = await res.json();
              setCurrentStepDetected(data.current_step_detected);
              setDetectedStepNumber(data.step_number);
              setStatusMessage(data.message);

              const rawViolation = data.step_number > 0 && (data.deviation_detected || !data.compliant);
              
              if (rawViolation) {
                consecutiveViolationsRef.current += 1;
              } else {
                consecutiveViolationsRef.current = 0;
              }

              const confirmedViolation = consecutiveViolationsRef.current >= CONSECUTIVE_THRESHOLD;
              setIsViolation(confirmedViolation);

              if (confirmedViolation) {
                playBeep();
              }
            }
          } catch (err) {
            console.error("Evaluation frame post failed or timed out:", err);
          } finally {
            setEvaluating(false);
            isExecuting = false;
          }
        }, "image/jpeg", 0.85);
      }, 4000);
    }

    return () => clearInterval(interval);
  }, [isMonitoring, sop, sopId, isMuted]);

  if (loading) return <div className="text-graphite-400">Loading monitoring console...</div>;
  if (error) return <div className="text-red-400">Error: {error}</div>;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center justify-between border-b border-graphite-700 pb-4">
        <div>
          <span className="stamp text-xs text-amber-400">Production Live Monitoring & Sequence Audit</span>
          <h1 className="font-display text-2xl font-bold text-graphite-100">{sop?.title}</h1>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => setIsMuted(!isMuted)}
            className="text-xs border border-graphite-700 bg-graphite-900 px-3 py-1.5 text-graphite-300 hover:text-amber-400 transition"
          >
            {isMuted ? "🔇 Unmute Audio Alarms" : "🔊 Mute Audio Alarms"}
          </button>
          <Link href={`/sop/${sopId}`} className="text-xs text-amber-400 hover:underline">
            ← Back to SOP Review
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 flex flex-col gap-4">
          <div
            className={`relative border-2 overflow-hidden bg-black transition-all duration-300 ${
              isViolation ? "border-red-500 shadow-[0_0_25px_rgba(239,68,68,0.6)] animate-pulse" : "border-graphite-700"
            }`}
          >
            <video ref={videoRef} autoPlay playsInline muted className="w-full h-auto object-cover" />
            <canvas ref={canvasRef} className="hidden" />

            {isViolation && (
              <div className="absolute top-4 left-4 bg-red-600 text-white px-3 py-1.5 text-xs font-bold uppercase tracking-wider flex items-center gap-2 shadow-lg">
                <span>⚠️ Sequence Violation / Deviation Confirmed!</span>
              </div>
            )}

            {detectedStepNumber === 0 && isMonitoring && (
              <div className="absolute top-4 left-4 bg-amber-600 text-graphite-950 px-3 py-1.5 text-xs font-bold uppercase tracking-wider shadow-lg">
                ⏳ Waiting for Initial Step (Step 1)
              </div>
            )}

            <div className="absolute bottom-4 right-4 bg-graphite-900/90 backdrop-blur px-3 py-1 text-xs text-graphite-300 border border-graphite-700">
              {evaluating ? "Evaluating frame..." : isMonitoring ? "● Live Auditor Active" : "Paused"}
            </div>
          </div>

          <div className="flex gap-4">
            {!isMonitoring ? (
              <button
                onClick={() => setIsMonitoring(true)}
                className="bg-amber-500 text-graphite-950 font-medium px-6 py-2.5 text-sm transition hover:bg-amber-400"
              >
                Start Live Monitoring
              </button>
            ) : (
              <button
                onClick={() => {
                  setIsMonitoring(false);
                  setIsViolation(false);
                  consecutiveViolationsRef.current = 0;
                }}
                className="border border-red-500 bg-red-500/10 text-red-400 font-medium px-6 py-2.5 text-sm transition hover:bg-red-500/20"
              >
                Stop Monitoring
              </button>
            )}
          </div>
        </div>

        <div className="border border-graphite-700 bg-graphite-900 p-6 flex flex-col gap-4">
          <h3 className="font-display text-base font-bold text-graphite-100">Sequence & Compliance Status</h3>
          
          <div className="flex flex-col gap-2">
            <span className="text-xs text-graphite-400 uppercase tracking-wider">Active Step Progression</span>
            <div className="text-sm font-mono text-amber-400 bg-graphite-950 p-3 border border-graphite-800">
              {detectedStepNumber === 0 ? "Waiting for Operator (Step 0)" : `Step ${detectedStepNumber}: ${currentStepDetected}`}
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <span className="text-xs text-graphite-400 uppercase tracking-wider">Auditor Assessment</span>
            <div className={`text-sm p-3 border ${isViolation ? "bg-red-950/40 border-red-800 text-red-300" : "bg-graphite-950 border-graphite-800 text-graphite-300"}`}>
              {statusMessage}
            </div>
          </div>

          <div className="mt-4 border-t border-graphite-800 pt-4">
            <h4 className="text-xs font-bold text-graphite-400 uppercase tracking-wider mb-2">Configured SOP Steps</h4>
            <ul className="flex flex-col gap-2 max-h-60 overflow-y-auto text-xs text-graphite-300">
              {sop?.steps.map((step) => (
                <li
                  key={step.step_number}
                  className={`border-b border-graphite-800 pb-2 transition-colors ${
                    detectedStepNumber === step.step_number ? "text-amber-400 font-bold bg-amber-500/10 p-1.5" : ""
                  }`}
                >
                  <span className="font-bold">Step {step.step_number}:</span> {step.title}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
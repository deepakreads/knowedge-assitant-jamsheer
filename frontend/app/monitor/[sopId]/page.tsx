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

interface FrameEvaluationResponse {
  compliant: boolean;
  current_step_detected: string;
  step_number: number;
  deviation_detected: boolean;
  message: string;
  violation_type?: string | null;
  expected_step?: number | null;
  workflow_started: boolean;
}

type MonitoringState = "idle" | "waiting_start" | "in_progress" | "violation" | "completed";

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

  // Enhanced state tracking
  const [monitoringState, setMonitoringState] = useState<MonitoringState>("idle");
  const [statusMessage, setStatusMessage] = useState<string>("Monitoring system ready");
  const [currentStepDetected, setCurrentStepDetected] = useState<string>("Not Started");
  const [detectedStepNumber, setDetectedStepNumber] = useState<number>(0);
  const [expectedStepNumber, setExpectedStepNumber] = useState<number>(0);
  const [isViolation, setIsViolation] = useState<boolean>(false);
  const [violationType, setViolationType] = useState<string | null>(null);
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [workflowStarted, setWorkflowStarted] = useState<boolean>(false);
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [violationHistory, setViolationHistory] = useState<Array<{ type: string; step: number; time: string }>>([]);
  const [workflowComplete, setWorkflowComplete] = useState<boolean>(false);
  const completionTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Violation confirmation tracking
  const violationCountRef = useRef<number>(0);
  const VIOLATION_CONFIRMATION_THRESHOLD = 1; // Alert on first confirmed violation
  const stepTransitionRef = useRef<number>(0); // Track rapid step changes

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

  const playBeep = (frequency: number = 880, duration: number = 350) => {
    if (isMuted) return;
    try {
      const AudioContextWindow = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioContextWindow) return;
      const ctx = new AudioContextWindow();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(frequency, ctx.currentTime);
      gain.gain.setValueAtTime(0.25, ctx.currentTime);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + duration / 1000);
    } catch (e) {
      console.error("Audio beep failed:", e);
    }
  };

  const handleViolation = (violationType: string | null) => {
    if (!violationType) return;

    violationCountRef.current += 1;

    if (violationCountRef.current >= VIOLATION_CONFIRMATION_THRESHOLD) {
      setMonitoringState("violation");
      setIsViolation(true);
      playBeep(650, 500); // Lower frequency for violation
      playBeep(650, 500);

      // Log violation
      const timestamp = new Date().toLocaleTimeString();
      setViolationHistory((prev) => [...prev, { type: violationType, step: detectedStepNumber, time: timestamp }]);
    }
  };

  const handleWorkflowStart = () => {
    setMonitoringState("in_progress");
    setWorkflowStarted(true);
    setCompletedSteps([1]);
    playBeep(880, 200); // Start chirp
  };

  const resetMonitoring = async () => {
    try {
      await fetch(`http://localhost:8000/api/sop-generation/sops/${sopId}/reset-monitoring`, {
        method: "POST",
      });
    } catch (err) {
      console.error("Failed to reset monitoring session:", err);
    }

    if (completionTimeoutRef.current) {
      clearTimeout(completionTimeoutRef.current);
    }

    setMonitoringState("idle");
    setIsMonitoring(false);
    setIsViolation(false);
    setViolationType(null);
    setWorkflowStarted(false);
    setDetectedStepNumber(0);
    setExpectedStepNumber(0);
    setCurrentStepDetected("Not Started");
    setCompletedSteps([]);
    setViolationHistory([]);
    setWorkflowComplete(false);
    setStatusMessage("Monitoring system ready");
    violationCountRef.current = 0;
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
            const timeoutId = setTimeout(() => controller.abort(), 10000);

            const res = await fetch(`http://localhost:8000/api/sop-generation/sops/${sopId}/evaluate-frame`, {
              method: "POST",
              body: formData,
              signal: controller.signal,
            });
            clearTimeout(timeoutId);

            if (res.ok) {
              const data: FrameEvaluationResponse = await res.json();

              setStatusMessage(data.message);
              setCurrentStepDetected(data.current_step_detected);
              setDetectedStepNumber(data.step_number);
              setExpectedStepNumber(data.expected_step || 0);
              setViolationType(data.violation_type || null);

              // Handle workflow initialization - triggered when any step > 0 detected
              if (!workflowStarted && data.step_number > 0) {
                handleWorkflowStart();
              }

              // Handle workflow regression back to idle
              if (workflowStarted && data.step_number === 0) {
                setMonitoringState("waiting_start");
                setWorkflowStarted(false);
                setCompletedSteps([]);
                setWorkflowComplete(false);
              }
              // Handle workflow completion
              else if (data.message && data.message.includes("WORKFLOW COMPLETE")) {
                setMonitoringState("completed");
                setWorkflowComplete(true);
                playBeep(1047, 200); // High frequency completion beep
                playBeep(1047, 200);
                playBeep(1047, 200);
                
                // Auto-reset after 5 seconds
                if (completionTimeoutRef.current) {
                  clearTimeout(completionTimeoutRef.current);
                }
                completionTimeoutRef.current = setTimeout(() => {
                  resetMonitoring();
                }, 5000);
              }
              // Handle violations
              else if (data.deviation_detected) {
                handleViolation(data.violation_type);
              } else {
                // Clear violation state if compliant again
                if (isViolation) {
                  setIsViolation(false);
                  setMonitoringState("in_progress");
                  violationCountRef.current = 0;
                }

                // Update progress tracking - intelligently handle step jumps (backfill)
                if (data.workflow_started && data.step_number > 0) {
                  setCompletedSteps((prev) => {
                    // Build list of all steps up to detected step
                    const allStepsUntilDetected = Array.from(
                      { length: data.step_number },
                      (_, i) => i + 1
                    );
                    
                    // Merge with existing completed steps
                    const updated = Array.from(
                      new Set([...prev, ...allStepsUntilDetected])
                    ).sort((a, b) => a - b);
                    
                    return updated;
                  });
                }
              }
            }
          } catch (err) {
            console.error("Evaluation frame post failed or timed out:", err);
          } finally {
            setEvaluating(false);
            isExecuting = false;
          }
        }, "image/jpeg", 0.85);
      }, 2500); // Faster polling for better step transition detection
    }

    return () => clearInterval(interval);
  }, [isMonitoring, sop, sopId, isMuted, workflowStarted, isViolation]);

  const getMonitoringStateDisplay = () => {
    switch (monitoringState) {
      case "waiting_start":
        return { label: "⏳ Awaiting Workflow Start", color: "text-amber-400", bg: "bg-amber-900/30" };
      case "in_progress":
        return { label: "● Monitoring Active", color: "text-green-400", bg: "bg-green-900/30" };
      case "violation":
        return { label: "⚠️ Violation Detected", color: "text-red-400", bg: "bg-red-900/30" };
      case "completed":
        return { label: "✓ Workflow Complete", color: "text-emerald-400", bg: "bg-emerald-900/30" };
      default:
        return { label: "○ Paused", color: "text-graphite-400", bg: "bg-graphite-900/30" };
    }
  };

  const progressPercentage = sop ? Math.round((completedSteps.length / sop.steps.length) * 100) : 0;
  const stateDisplay = getMonitoringStateDisplay();

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
            {isMuted ? "🔇 Unmute Audio" : "🔊 Mute Audio"}
          </button>
          <Link href={`/sop/${sopId}`} className="text-xs text-amber-400 hover:underline">
            ← Back to SOP
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

            {isViolation && violationType && (
              <div className="absolute top-4 left-4 bg-red-600 text-white px-4 py-2 text-xs font-bold uppercase tracking-wider flex flex-col gap-1 shadow-lg max-w-xs">
                <span>⚠️ Sequence Violation Detected</span>
                <span className="font-normal text-red-200">
                  {violationType === "out_of_order" && `Step regression detected. Expected Step ${expectedStepNumber}`}
                  {violationType === "skipped" && `Steps skipped. Expected Step ${expectedStepNumber}`}
                  {violationType === "incorrect" && "Incorrect step execution detected"}
                </span>
              </div>
            )}

            {!workflowStarted && isMonitoring && !workflowComplete && (
              <div className="absolute top-4 left-4 bg-amber-600 text-graphite-950 px-3 py-1.5 text-xs font-bold uppercase tracking-wider shadow-lg animate-pulse">
                ⏳ Ready - Waiting for Workflow Start
              </div>
            )}

            {workflowComplete && (
              <div className="absolute inset-0 bg-gradient-to-b from-emerald-950/60 to-emerald-900/60 flex flex-col items-center justify-center gap-4 backdrop-blur-sm">
                <div className="text-5xl">✓</div>
                <div className="text-center">
                  <h2 className="text-2xl font-bold text-emerald-300 mb-1">Workflow Complete</h2>
                  <p className="text-sm text-emerald-200">All steps completed successfully in correct sequence</p>
                  <p className="text-xs text-emerald-300 mt-3">Auto-resetting for next cycle...</p>
                </div>
              </div>
            )}

            <div className={`absolute bottom-4 right-4 ${stateDisplay.bg} backdrop-blur px-3 py-1.5 text-xs ${stateDisplay.color} border border-graphite-700 font-medium`}>
              {evaluating ? "Evaluating frame..." : stateDisplay.label}
            </div>
          </div>

          <div className="flex gap-4">
            {!isMonitoring ? (
              <button
                onClick={() => {
                  setIsMonitoring(true);
                  setMonitoringState("waiting_start");
                  setStatusMessage("Monitoring active - awaiting operator to begin workflow...");
                }}
                className="bg-amber-500 text-graphite-950 font-medium px-6 py-2.5 text-sm transition hover:bg-amber-400"
              >
                ▶ Start Live Monitoring
              </button>
            ) : (
              <button
                onClick={() => {
                  setIsMonitoring(false);
                  setMonitoringState("idle");
                }}
                className="border border-graphite-700 bg-graphite-900 text-graphite-300 font-medium px-6 py-2.5 text-sm transition hover:bg-graphite-800"
              >
                ⏸ Pause Monitoring
              </button>
            )}

            {(isViolation || workflowComplete || (workflowStarted && isMonitoring)) && (
              <button
                onClick={resetMonitoring}
                className={`font-medium px-6 py-2.5 text-sm transition ${
                  workflowComplete
                    ? "border border-emerald-500 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
                    : "border border-amber-500 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20"
                }`}
              >
                {workflowComplete ? "✓ Start New Cycle" : "↻ Reset Session"}
              </button>
            )}
          </div>
        </div>

        {/* Right Sidebar */}
        <div className="border border-graphite-700 bg-graphite-900 p-6 flex flex-col gap-6">
          {/* Progress Section */}
          <div>
            <h3 className="font-display text-sm font-bold text-graphite-100 mb-4">Workflow Progress</h3>
            <div className="w-full bg-graphite-800 h-2 rounded overflow-hidden mb-2">
              <div
                className={`h-full transition-all duration-300 ${
                  monitoringState === "completed" ? "bg-emerald-500" : isViolation ? "bg-red-500" : "bg-amber-500"
                }`}
                style={{ width: `${progressPercentage}%` }}
              />
            </div>
            <div className={`text-xs ${workflowComplete ? "text-emerald-400 font-semibold" : "text-graphite-400"}`}>
              {workflowComplete ? "✓ All steps completed!" : `${completedSteps.length} of ${sop?.steps.length} steps completed`}
            </div>
          </div>

          {/* Current State */}
          <div>
            <h3 className="font-display text-sm font-bold text-graphite-100 mb-3">Current State</h3>
            <div className="flex flex-col gap-2 text-xs">
              <div className="flex justify-between">
                <span className="text-graphite-400">Active Step:</span>
                <span className={detectedStepNumber > 0 ? "text-amber-400 font-mono" : "text-graphite-400"}>
                  {detectedStepNumber > 0 ? `Step ${detectedStepNumber}` : "Idle"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-graphite-400">Status:</span>
                <span className={stateDisplay.color}>{stateDisplay.label.split(" ").slice(1).join(" ")}</span>
              </div>
              {isViolation && expectedStepNumber > 0 && (
                <div className="flex justify-between text-red-400">
                  <span>Expected:</span>
                  <span className="font-mono">Step {expectedStepNumber}</span>
                </div>
              )}
            </div>
          </div>

          {/* Message */}
          <div>
            <h3 className="font-display text-xs font-bold text-graphite-400 uppercase tracking-wider mb-2">Auditor Assessment</h3>
            <div
              className={`text-xs p-3 border rounded ${
                workflowComplete
                  ? "bg-emerald-950/40 border-emerald-800 text-emerald-300 font-semibold"
                  : isViolation
                  ? "bg-red-950/40 border-red-800 text-red-300"
                  : workflowStarted
                  ? "bg-green-950/40 border-green-800 text-green-300"
                  : "bg-graphite-950 border-graphite-800 text-graphite-300"
              }`}
            >
              {statusMessage}
            </div>
          </div>

          {/* Violations */}
          {violationHistory.length > 0 && (
            <div>
              <h3 className="font-display text-xs font-bold text-graphite-400 uppercase tracking-wider mb-2">Violations</h3>
              <ul className="flex flex-col gap-1 max-h-32 overflow-y-auto text-xs">
                {violationHistory.map((v, i) => (
                  <li key={i} className="text-red-400 border-b border-graphite-800 pb-1">
                    <span className="font-mono text-red-300">{v.time}</span>: {v.type} at Step {v.step}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Steps Reference */}
          <div className="border-t border-graphite-800 pt-4">
            <h4 className="text-xs font-bold text-graphite-400 uppercase tracking-wider mb-3">SOP Steps</h4>
            <ul className="flex flex-col gap-2 max-h-48 overflow-y-auto text-xs">
              {sop?.steps.map((step) => {
                const isCompleted = completedSteps.includes(step.step_number);
                const isCurrent = detectedStepNumber === step.step_number;
                return (
                  <li
                    key={step.step_number}
                    className={`border-l-2 pl-2 py-1 transition-colors ${
                      isCompleted ? "border-emerald-500 text-emerald-400" : isCurrent ? "border-amber-500 text-amber-400 font-bold bg-amber-500/10 px-2" : "border-graphite-700 text-graphite-400"
                    }`}
                  >
                    {isCompleted && "✓ "}
                    <span className="font-bold">Step {step.step_number}:</span> {step.title}
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

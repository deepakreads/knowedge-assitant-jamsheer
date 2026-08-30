'use client'

import { useState, useEffect, useRef } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'

interface SOP {
  id: string
  title: string
  purpose: string
  steps: Step[]
  estimated_duration: string
}

interface Step {
  step_number: number
  title: string
  description: string
  duration: number
  tools?: string[]
  safety_notes?: string
}

interface MonitoringResult {
  current_step: number
  total_steps: number
  step_title: string
  compliance: number
  overall_compliance: number
  feedback: string
  next_step_ready: boolean
  warnings: string[]
  time_remaining: number
  progress_percent: number
  tools_required?: string[]
}

export default function MonitoringPage() {
  const params = useParams()
  const sopId = params.sopId as string

  const [sop, setSop] = useState<SOP | null>(null)
  const [loading, setLoading] = useState(true)
  const [cameraActive, setCameraActive] = useState(false)
  const [currentResult, setCurrentResult] = useState<MonitoringResult | null>(null)
  const [framesSent, setFramesSent] = useState(0)

  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const frameIntervalRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    fetch(`${apiUrl}/api/sops/${sopId}`)
      .then(r => r.json())
      .then(setSop)
      .catch(err => console.error('Failed to fetch SOP:', err))
      .finally(() => setLoading(false))
  }, [sopId])

  const startMonitoring = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      if (videoRef.current) videoRef.current.srcObject = stream

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const wsProtocol = apiUrl.startsWith('https') ? 'wss:' : 'ws:'
      const wsHost = apiUrl.replace('http://', '').replace('https://', '')
      const wsUrl = `${wsProtocol}//${wsHost}/ws/monitor/${sopId}`
      wsRef.current = new WebSocket(wsUrl)

      wsRef.current.onmessage = (event) => {
        try {
          setCurrentResult(JSON.parse(event.data))
        } catch (e) {
          console.error(e)
        }
      }

      setCameraActive(true)
      setFramesSent(0)

      frameIntervalRef.current = setInterval(() => {
        if (videoRef.current && canvasRef.current && wsRef.current?.readyState === WebSocket.OPEN) {
          const ctx = canvasRef.current.getContext('2d')
          if (ctx) {
            ctx.drawImage(videoRef.current, 0, 0)
            const frame = canvasRef.current.toDataURL('image/jpeg', 0.7).split(',')[1]
            wsRef.current?.send(JSON.stringify({ frame }))
            setFramesSent((p) => p + 1)
          }
        }
      }, 1000)
    } catch (err) {
      console.error(err)
    }
  }

  const stopMonitoring = () => {
    if (frameIntervalRef.current) clearInterval(frameIntervalRef.current)
    if (videoRef.current?.srcObject) {
      (videoRef.current.srcObject as MediaStream).getTracks().forEach((t) => t.stop())
    }
    if (wsRef.current) wsRef.current.close()
    setCameraActive(false)
  }

  useEffect(() => {
    return () => stopMonitoring()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-100">
        <p className="text-slate-600">Loading SOP...</p>
      </div>
    )
  }

  if (!sop) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-100">
        <div className="text-center bg-white p-8 rounded-lg shadow">
          <p className="text-slate-900 font-semibold mb-4">SOP not found</p>
          <Link href="/sops" className="px-4 py-2 bg-blue-500 text-white rounded">Back</Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      <div className="bg-white border-b border-slate-200 sticky top-0 z-40">
        <div className="container mx-auto px-4 py-4">
          <Link href="/sops" className="text-blue-600 text-sm font-medium">← Back to SOPs</Link>
          <h1 className="text-2xl font-bold text-slate-900 mt-2">{sop.title}</h1>
          <p className="text-slate-600 text-sm mt-1">{sop.purpose}</p>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-2">
            <div className="bg-white rounded-lg border border-slate-200 overflow-hidden shadow">
              <div className="relative bg-black aspect-video">
                {cameraActive ? (
                  <>
                    <video ref={videoRef} autoPlay playsInline className="w-full h-full object-cover" />
                    <div className="absolute top-4 right-4 px-3 py-1 bg-red-500 text-white text-xs font-bold rounded-full animate-pulse">● REC</div>
                  </>
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-slate-400">
                    <svg className="w-16 h-16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  </div>
                )}
                <canvas ref={canvasRef} hidden />
              </div>

              <div className="p-4 bg-slate-50 border-t flex gap-2">
                {!cameraActive ? (
                  <button onClick={startMonitoring} className="flex-1 px-4 py-2 bg-green-500 text-white font-semibold rounded-lg hover:bg-green-600">
                    Start
                  </button>
                ) : (
                  <button onClick={stopMonitoring} className="flex-1 px-4 py-2 bg-red-500 text-white font-semibold rounded-lg hover:bg-red-600">
                    Stop
                  </button>
                )}
              </div>

              {cameraActive && (
                <div className="px-4 py-2 bg-blue-50 text-xs text-slate-600 border-t">
                  Frames: {framesSent}
                </div>
              )}
            </div>
          </div>

          <div className="col-span-1 space-y-4">
            {currentResult && (
              <div className="bg-white rounded-lg border border-slate-200 p-6 shadow">
                <h3 className="text-sm font-semibold text-slate-600 uppercase mb-4">Compliance</h3>
                <div className="text-center">
                  <div className="text-4xl font-bold text-blue-600">{Math.round(currentResult.overall_compliance)}%</div>
                  <div className="w-full bg-slate-200 rounded-full h-3 mt-2">
                    <div className={`h-3 rounded-full ${currentResult.overall_compliance >= 80 ? 'bg-green-500' : currentResult.overall_compliance >= 50 ? 'bg-yellow-500' : 'bg-red-500'}`} style={{width: `${currentResult.overall_compliance}%`}} />
                  </div>
                </div>
              </div>
            )}

            {currentResult && (
              <div className="bg-white rounded-lg border border-slate-200 p-6 shadow">
                <h3 className="text-sm font-semibold text-slate-600 uppercase mb-3">Step</h3>
                <p className="text-sm font-semibold">{currentResult.step_title}</p>
                <p className="text-xs text-slate-600">{currentResult.current_step}/{currentResult.total_steps}</p>
                <p className="text-sm text-slate-800 mt-2">{currentResult.feedback}</p>
              </div>
            )}
          </div>
        </div>

        {currentResult && (
          <div className="mt-6 bg-white rounded-lg border border-slate-200 p-6 shadow">
            <div className="flex justify-between mb-2">
              <h3 className="text-sm font-semibold text-slate-600">Progress</h3>
              <span className="text-sm font-bold">{Math.round(currentResult.progress_percent)}%</span>
            </div>
            <div className="w-full bg-slate-200 rounded-full h-4">
              <div className="bg-blue-500 h-4 rounded-full" style={{width: `${currentResult.progress_percent}%`}} />
            </div>
          </div>
        )}

        <div className="mt-6 bg-white rounded-lg border border-slate-200 p-6 shadow">
          <h3 className="text-sm font-semibold text-slate-600 uppercase mb-4">Steps</h3>
          <div className="space-y-2">
            {sop.steps.map((step, idx) => {
              const stepNum = idx + 1
              const isCompleted = currentResult && stepNum < currentResult.current_step
              const isCurrent = currentResult && stepNum === currentResult.current_step
              return (
                <div key={idx} className={`p-3 rounded-lg border-l-4 ${isCompleted ? 'bg-green-50 border-green-500' : isCurrent ? 'bg-blue-50 border-blue-500' : 'bg-slate-50 border-slate-300'}`}>
                  <p className="text-sm font-semibold">Step {stepNum}: {step.title}</p>
                  <p className="text-xs text-slate-600 mt-1">{step.description}</p>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
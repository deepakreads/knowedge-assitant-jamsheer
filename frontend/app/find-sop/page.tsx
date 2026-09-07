'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';

interface SOP {
  id: string;
  title: string;
  status: string;
  estimated_duration: string;
  machine_name?: string;
  department?: string;
  match_score?: number;
}

interface Department {
  name: string;
  count: number;
}

interface Machine {
  name: string;
  count: number;
}

export default function FindSOPPage() {
  const [activeTab, setActiveTab] = useState<'department' | 'machine' | 'image'>('department');

  // Department search
  const [departments, setDepartments] = useState<string[]>([]);
  const [selectedDept, setSelectedDept] = useState('');
  const [deptResults, setDeptResults] = useState<SOP[]>([]);
  const [deptLoading, setDeptLoading] = useState(false);

  // Machine search
  const [machines, setMachines] = useState<string[]>([]);
  const [selectedMachine, setSelectedMachine] = useState('');
  const [machineResults, setMachineResults] = useState<SOP[]>([]);
  const [machineLoading, setMachineLoading] = useState(false);

  // Image search
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [machineDetected, setMachineDetected] = useState<string | null>(null);
  const [analysisText, setAnalysisText] = useState<string>('');
  const [imageResults, setImageResults] = useState<SOP[]>([]);
  const [imageLoading, setImageLoading] = useState(false);
  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const cameraRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  // Load departments on mount
  useEffect(() => {
    fetchDepartments();
    fetchMachines();
  }, []);

  const fetchDepartments = async () => {
    try {
      const response = await fetch(`${apiUrl}/api/find-sop/departments`);
      if (response.ok) {
        const data = await response.json();
        setDepartments(data.departments || []);
      }
    } catch (error) {
      console.error('Failed to fetch departments:', error);
    }
  };

  const fetchMachines = async () => {
    try {
      const response = await fetch(`${apiUrl}/api/find-sop/machines`);
      if (response.ok) {
        const data = await response.json();
        setMachines(data.machines || []);
      }
    } catch (error) {
      console.error('Failed to fetch machines:', error);
    }
  };

  const searchByDepartment = async () => {
    if (!selectedDept) return;

    setDeptLoading(true);
    try {
      const response = await fetch(
        `${apiUrl}/api/find-sop/by-department?department=${encodeURIComponent(selectedDept)}`
      );
      if (response.ok) {
        const data = await response.json();
        setDeptResults(data.sops || []);
      } else {
        setDeptResults([]);
      }
    } catch (error) {
      console.error('Failed to search by department:', error);
      setDeptResults([]);
    } finally {
      setDeptLoading(false);
    }
  };

  const searchByMachine = async () => {
    if (!selectedMachine) return;

    setMachineLoading(true);
    try {
      const response = await fetch(
        `${apiUrl}/api/find-sop/by-machine-name?machine_name=${encodeURIComponent(selectedMachine)}`
      );
      if (response.ok) {
        const data = await response.json();
        setMachineResults(data.sops || []);
      } else {
        setMachineResults([]);
      }
    } catch (error) {
      console.error('Failed to search by machine:', error);
      setMachineResults([]);
    } finally {
      setMachineLoading(false);
    }
  };

  const handleImageSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setImageFile(file);
      const reader = new FileReader();
      reader.onload = (e) => {
        setImagePreview(e.target?.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const searchByImage = async () => {
    if (!imageFile) return;

    setImageLoading(true);
    try {
      const formData = new FormData();
      formData.append('image', imageFile);

      const response = await fetch(`${apiUrl}/api/find-sop/by-image`, {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setMachineDetected(data.machine_detected);
        setAnalysisText(data.analysis);
        setImageResults(data.matching_sops || []);
      } else {
        console.error('Failed to analyze image');
        setImageResults([]);
      }
    } catch (error) {
      console.error('Failed to search by image:', error);
      setImageResults([]);
    } finally {
      setImageLoading(false);
    }
  };

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
        audio: false,
      });
      setCameraStream(stream);
      setIsCameraActive(true);
      if (cameraRef.current) {
        cameraRef.current.srcObject = stream;
      }
    } catch (error) {
      console.error('Failed to access camera:', error);
      alert('Unable to access camera. Please check permissions.');
    }
  };

  const stopCamera = () => {
    if (cameraStream) {
      cameraStream.getTracks().forEach((track) => track.stop());
      setCameraStream(null);
      setIsCameraActive(false);
    }
  };

  const captureImage = () => {
    if (cameraRef.current && canvasRef.current) {
      const context = canvasRef.current.getContext('2d');
      if (context) {
        canvasRef.current.width = cameraRef.current.videoWidth;
        canvasRef.current.height = cameraRef.current.videoHeight;
        context.drawImage(cameraRef.current, 0, 0);

        canvasRef.current.toBlob((blob) => {
          if (blob) {
            const file = new File([blob], 'camera-capture.jpg', { type: 'image/jpeg' });
            setImageFile(file);
            setImagePreview(canvasRef.current!.toDataURL());
            stopCamera();
          }
        }, 'image/jpeg');
      }
    }
  };

  const SOPCard = ({ sop }: { sop: SOP }) => (
    <div className="border border-graphite-700 bg-graphite-950 p-6 hover:bg-graphite-900 transition">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-graphite-100">{sop.title}</h3>
          {sop.machine_name && (
            <p className="text-sm text-graphite-400 mt-1">🤖 {sop.machine_name}</p>
          )}
          {sop.department && (
            <p className="text-sm text-graphite-400">📍 {sop.department}</p>
          )}
          <p className="text-sm text-graphite-500 mt-2">⏱️ {sop.estimated_duration}</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          {sop.match_score && (
            <div className="bg-emerald-500/20 border border-emerald-500 px-3 py-1 rounded text-sm font-semibold text-emerald-400">
              {sop.match_score}% match
            </div>
          )}
          <span
            className={`px-3 py-1 rounded text-xs font-semibold ${
              sop.status === 'APPROVED'
                ? 'bg-emerald-500/20 border border-emerald-500 text-emerald-400'
                : 'bg-amber-500/20 border border-amber-500 text-amber-400'
            }`}
          >
            {sop.status === 'APPROVED' ? '✅ Approved' : '⏳ Review Required'}
          </span>
        </div>
      </div>
      <Link
        href={`/monitor/${sop.id}`}
        className="mt-4 inline-flex items-center gap-2 border border-blue-500 bg-blue-500/10 px-4 py-2 text-sm font-medium text-blue-400 hover:bg-blue-500/20 transition"
      >
        Monitor SOP →
      </Link>
    </div>
  );

  return (
    <div className="flex flex-col gap-8">
      {/* Header */}
      <div className="border border-graphite-700 bg-graphite-900 bg-diagonal-hatch p-8">
        <p className="stamp mb-3 text-xs text-green-400">Machine-Based SOP Discovery</p>
        <h1 className="font-display text-3xl font-bold leading-tight text-graphite-100 sm:text-4xl">
          Find the right SOP for your machine
        </h1>
        <p className="mt-4 max-w-2xl text-sm leading-relaxed text-graphite-300">
          Search for Standard Operating Procedures by department, machine name, or upload an image
          of your machine. Our AI will identify what you have and find the matching procedures.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-graphite-700">
        <button
          onClick={() => setActiveTab('department')}
          className={`px-4 py-3 font-medium border-b-2 transition ${
            activeTab === 'department'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-graphite-400 hover:text-graphite-300'
          }`}
        >
          By Department
        </button>
        <button
          onClick={() => setActiveTab('machine')}
          className={`px-4 py-3 font-medium border-b-2 transition ${
            activeTab === 'machine'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-graphite-400 hover:text-graphite-300'
          }`}
        >
          By Machine Name
        </button>
        <button
          onClick={() => setActiveTab('image')}
          className={`px-4 py-3 font-medium border-b-2 transition ${
            activeTab === 'image'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-graphite-400 hover:text-graphite-300'
          }`}
        >
          By Machine Image
        </button>
      </div>

      {/* Department Tab */}
      {activeTab === 'department' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Search Panel */}
          <div className="lg:col-span-1">
            <div className="border border-graphite-700 bg-graphite-950 p-6">
              <h2 className="font-display text-lg font-bold text-graphite-100 mb-4">Select Department</h2>
              {departments.length > 0 ? (
                <>
                  <select
                    value={selectedDept}
                    onChange={(e) => setSelectedDept(e.target.value)}
                    className="w-full bg-graphite-900 border border-graphite-700 text-graphite-100 px-4 py-2 mb-4 focus:outline-none focus:border-blue-500"
                  >
                    <option value="">Choose a department...</option>
                    {departments.map((dept) => (
                      <option key={dept} value={dept}>
                        {dept}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={searchByDepartment}
                    disabled={!selectedDept || deptLoading}
                    className="w-full border border-blue-500 bg-blue-500/10 px-4 py-2 font-medium text-blue-400 hover:bg-blue-500/20 transition disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {deptLoading ? 'Searching...' : 'Search'}
                  </button>
                </>
              ) : (
                <p className="text-graphite-400">No departments available</p>
              )}
            </div>
          </div>

          {/* Results Panel */}
          <div className="lg:col-span-2">
            <h2 className="font-display text-lg font-bold text-graphite-100 mb-4">
              {selectedDept ? `SOPs for ${selectedDept}` : 'Results'}
            </h2>
            {deptResults.length > 0 ? (
              <div className="grid gap-4">
                {deptResults.map((sop) => (
                  <SOPCard key={sop.id} sop={sop} />
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-graphite-400">
                {selectedDept ? 'No SOPs found for this department' : 'Select a department to see results'}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Machine Name Tab */}
      {activeTab === 'machine' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Search Panel */}
          <div className="lg:col-span-1">
            <div className="border border-graphite-700 bg-graphite-950 p-6">
              <h2 className="font-display text-lg font-bold text-graphite-100 mb-4">Select Machine</h2>
              {machines.length > 0 ? (
                <>
                  <select
                    value={selectedMachine}
                    onChange={(e) => setSelectedMachine(e.target.value)}
                    className="w-full bg-graphite-900 border border-graphite-700 text-graphite-100 px-4 py-2 mb-4 focus:outline-none focus:border-blue-500"
                  >
                    <option value="">Choose a machine...</option>
                    {machines.map((machine) => (
                      <option key={machine} value={machine}>
                        {machine}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={searchByMachine}
                    disabled={!selectedMachine || machineLoading}
                    className="w-full border border-blue-500 bg-blue-500/10 px-4 py-2 font-medium text-blue-400 hover:bg-blue-500/20 transition disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {machineLoading ? 'Searching...' : 'Search'}
                  </button>
                </>
              ) : (
                <p className="text-graphite-400">No machines available</p>
              )}
            </div>
          </div>

          {/* Results Panel */}
          <div className="lg:col-span-2">
            <h2 className="font-display text-lg font-bold text-graphite-100 mb-4">
              {selectedMachine ? `SOPs for ${selectedMachine}` : 'Results'}
            </h2>
            {machineResults.length > 0 ? (
              <div className="grid gap-4">
                {machineResults.map((sop) => (
                  <SOPCard key={sop.id} sop={sop} />
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-graphite-400">
                {selectedMachine ? 'No SOPs found for this machine' : 'Select a machine to see results'}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Image Tab */}
      {activeTab === 'image' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Image Capture Panel */}
          <div className="lg:col-span-1">
            <div className="border border-graphite-700 bg-graphite-950 p-6 space-y-4">
              <h2 className="font-display text-lg font-bold text-graphite-100">Upload or Capture Image</h2>

              {/* Camera Preview */}
              {isCameraActive && (
                <div className="border border-graphite-700 bg-black aspect-video">
                  <video
                    ref={cameraRef}
                    autoPlay
                    playsInline
                    className="w-full h-full object-cover"
                  />
                </div>
              )}

              {/* Image Preview */}
              {!isCameraActive && imagePreview && (
                <div className="border border-graphite-700 bg-graphite-900 aspect-video overflow-hidden">
                  <img
                    src={imagePreview}
                    alt="Preview"
                    className="w-full h-full object-cover"
                  />
                </div>
              )}

              {/* Camera Controls */}
              {!isCameraActive ? (
                <>
                  <button
                    onClick={startCamera}
                    className="w-full border border-amber-500 bg-amber-500/10 px-4 py-2 font-medium text-amber-400 hover:bg-amber-500/20 transition"
                  >
                    📷 Use Camera
                  </button>
                  <label className="block">
                    <span className="w-full border border-blue-500 bg-blue-500/10 px-4 py-2 font-medium text-blue-400 hover:bg-blue-500/20 transition text-center cursor-pointer">
                      📁 Upload Image
                    </span>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleImageSelect}
                      className="hidden"
                    />
                  </label>
                </>
              ) : (
                <>
                  <button
                    onClick={captureImage}
                    className="w-full border border-green-500 bg-green-500/10 px-4 py-2 font-medium text-green-400 hover:bg-green-500/20 transition"
                  >
                    ✅ Capture
                  </button>
                  <button
                    onClick={stopCamera}
                    className="w-full border border-graphite-600 bg-graphite-800 px-4 py-2 font-medium text-graphite-400 hover:bg-graphite-700 transition"
                  >
                    Cancel
                  </button>
                </>
              )}

              {/* Search Button */}
              {imageFile && !isCameraActive && (
                <button
                  onClick={searchByImage}
                  disabled={imageLoading}
                  className="w-full border border-emerald-500 bg-emerald-500/10 px-4 py-2 font-medium text-emerald-400 hover:bg-emerald-500/20 transition disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {imageLoading ? 'Analyzing...' : '🤖 Find Matching SOPs'}
                </button>
              )}
            </div>
          </div>

          {/* Results Panel */}
          <div className="lg:col-span-2">
            {machineDetected && (
              <>
                <div className="border border-graphite-700 bg-graphite-950 p-6 mb-6">
                  <h3 className="font-display text-lg font-bold text-graphite-100 mb-2">Machine Detected</h3>
                  <div className="bg-green-500/10 border border-green-500 rounded p-4 mb-4">
                    <p className="text-green-400 font-semibold">{machineDetected}</p>
                  </div>
                  {analysisText && (
                    <>
                      <h4 className="text-graphite-300 font-semibold mb-2">Analysis:</h4>
                      <p className="text-graphite-400 text-sm leading-relaxed">{analysisText}</p>
                    </>
                  )}
                </div>

                <h2 className="font-display text-lg font-bold text-graphite-100 mb-4">Matching SOPs</h2>
                {imageResults.length > 0 ? (
                  <div className="grid gap-4">
                    {imageResults.map((sop) => (
                      <SOPCard key={sop.id} sop={sop} />
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-graphite-400">No SOPs found for this machine</div>
                )}
              </>
            )}

            {!machineDetected && (
              <div className="text-center py-12 text-graphite-400">
                <p className="text-lg">📸 Upload or capture an image to get started</p>
                <p className="text-sm mt-2">Our AI will identify the machine and find matching SOPs</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Hidden Canvas for image capture */}
      <canvas ref={canvasRef} className="hidden" />

      {/* Back Button */}
      <div>
        <Link
          href="/"
          className="text-blue-400 hover:text-blue-300 text-sm inline-flex items-center gap-2"
        >
          ← Back to Home
        </Link>
      </div>
    </div>
  );
}

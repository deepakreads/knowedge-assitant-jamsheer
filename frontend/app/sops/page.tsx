'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

interface SOP {
  id: string
  title: string
  purpose: string
  scope?: string
  steps?: any[]
  estimated_duration: string
  required_tools?: string[]
  status?: string
}

export default function SOPBrowser() {
  const [sops, setSops] = useState<SOP[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionInProgress, setActionInProgress] = useState<string | null>(null)
  const router = useRouter()

  useEffect(() => {
    fetchSOPs()
  }, [])

  const fetchSOPs = async () => {
    setLoading(true)
    setError(null)
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const res = await fetch(`${apiUrl}/api/sops/`)
      if (!res.ok) throw new Error(`Failed to fetch SOPs (${res.status})`)

      const data = await res.json()
      setSops(data.sops || [])
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      setError(message)
      console.error('Failed to fetch SOPs:', err)
    } finally {
      setLoading(false)
    }
  }

  const approveSOP = async (sopId: string, sopTitle: string) => {
    if (!confirm(`Are you sure you want to approve "${sopTitle}"?`)) {
      return
    }

    setActionInProgress(sopId)
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const res = await fetch(`${apiUrl}/api/sops/${sopId}/approve`, {
        method: 'PATCH'
      })

      if (!res.ok) throw new Error('Failed to approve SOP')

      // Refresh the list
      fetchSOPs()
    } catch (err) {
      alert(`Error approving SOP: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setActionInProgress(null)
    }
  }

  const deleteSOP = async (sopId: string, sopTitle: string) => {
    if (!confirm(`Are you sure you want to delete "${sopTitle}"? This action cannot be undone.`)) {
      return
    }

    setActionInProgress(sopId)
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const res = await fetch(`${apiUrl}/api/sops/${sopId}`, {
        method: 'DELETE'
      })

      if (!res.ok) throw new Error('Failed to delete SOP')

      // Refresh the list
      fetchSOPs()
    } catch (err) {
      alert(`Error deleting SOP: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setActionInProgress(null)
    }
  }

  const approvedSOPs = sops.filter(sop => sop.status === 'APPROVED')
  const reviewRequiredSOPs = sops.filter(sop => sop.status !== 'APPROVED')

  const filteredApproved = approvedSOPs.filter(sop =>
    sop.title.toLowerCase().includes(search.toLowerCase()) ||
    sop.purpose.toLowerCase().includes(search.toLowerCase())
  )

  const filteredReviewRequired = reviewRequiredSOPs.filter(sop =>
    sop.title.toLowerCase().includes(search.toLowerCase()) ||
    sop.purpose.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between mb-4">
            <Link
              href="/"
              className="text-blue-600 hover:text-blue-700 text-sm font-medium flex items-center gap-1"
            >
              ← Back to Home
            </Link>
            <button
              onClick={fetchSOPs}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition"
            >
              ↻ Refresh
            </button>
          </div>
          <div>
            <h1 className="text-3xl font-bold text-slate-900">
              Standard Operating Procedures
            </h1>
            <p className="text-slate-600 mt-1">
              Select a procedure to monitor compliance in real-time
            </p>
          </div>
        </div>
      </div>

      {/* Search Bar */}
      <div className="bg-white border-b border-slate-200">
        <div className="container mx-auto px-4 py-4">
          <div className="relative">
            <svg
              className="absolute left-3 top-3 w-5 h-5 text-slate-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <input
              type="search"
              placeholder="Search SOPs by title or purpose..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="container mx-auto px-4 py-8">
        {/* Error State */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-800 font-semibold">Error loading SOPs</p>
            <p className="text-red-600 text-sm mt-1">{error}</p>
            <button
              onClick={fetchSOPs}
              className="mt-2 px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 transition text-sm"
            >
              Try Again
            </button>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block">
              <div className="w-12 h-12 border-4 border-slate-300 border-t-blue-500 rounded-full animate-spin"></div>
            </div>
            <p className="text-slate-600 mt-4">Loading SOPs...</p>
          </div>
        )}

        {/* SOP Sections */}
        {!loading && (
          <>
            {filteredApproved.length === 0 && filteredReviewRequired.length === 0 ? (
              <div className="text-center py-12">
                {sops.length === 0 ? (
                  <>
                    <svg
                      className="mx-auto w-12 h-12 text-slate-400 mb-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1.5}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                    <p className="text-slate-600">No SOPs available yet.</p>
                    <p className="text-slate-500 text-sm mt-1">
                      Upload a video to generate your first SOP.
                    </p>
                    <Link
                      href="/upload"
                      className="inline-block mt-4 px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition"
                    >
                      Create SOP from Video
                    </Link>
                  </>
                ) : (
                  <>
                    <svg
                      className="mx-auto w-12 h-12 text-slate-400 mb-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1.5}
                        d="M10 21h7a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v11m0 5l4.59-4.59a1 1 0 011.42 0L16 21"
                      />
                    </svg>
                    <p className="text-slate-600">No SOPs match your search.</p>
                    <p className="text-slate-500 text-sm mt-1">
                      Try a different search term.
                    </p>
                  </>
                )}
              </div>
            ) : (
              <>
                {/* APPROVED SECTION */}
                {filteredApproved.length > 0 && (
                  <div className="mb-12">
                    <div className="flex items-center gap-2 mb-6">
                      <div className="w-1 h-6 bg-green-500 rounded"></div>
                      <h2 className="text-2xl font-bold text-slate-900">Approved SOPs</h2>
                      <span className="ml-2 px-3 py-1 bg-green-100 text-green-800 text-sm font-semibold rounded-full">
                        {filteredApproved.length}
                      </span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                      {filteredApproved.map((sop) => (
                  <div
                    key={sop.id}
                    className="bg-white rounded-lg border border-slate-200 hover:border-blue-300 hover:shadow-lg transition overflow-hidden"
                  >
                    {/* Card Header */}
                    <div className="p-6">
                      <h3 className="text-lg font-bold text-slate-900 mb-2 line-clamp-2">
                        {sop.title}
                      </h3>
                      <p className="text-slate-600 text-sm mb-4 line-clamp-3">
                        {sop.purpose}
                      </p>

                      {/* Stats */}
                      <div className="flex gap-4 text-sm text-slate-600 mb-4">
                        <div className="flex items-center gap-1">
                          <svg
                            className="w-4 h-4"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                            />
                          </svg>
                          <span>{sop.steps?.length || 0} steps</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <svg
                            className="w-4 h-4"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                            />
                          </svg>
                          <span>{sop.estimated_duration}</span>
                        </div>
                      </div>

                      {/* Tools */}
                      {sop.required_tools && sop.required_tools.length > 0 && (
                        <div className="mb-4">
                          <p className="text-xs font-semibold text-slate-500 uppercase mb-2">
                            Tools Required
                          </p>
                          <div className="flex flex-wrap gap-1">
                            {sop.required_tools.slice(0, 3).map((tool, idx) => (
                              <span
                                key={idx}
                                className="px-2 py-1 bg-slate-100 text-slate-700 text-xs rounded"
                              >
                                {tool}
                              </span>
                            ))}
                            {sop.required_tools.length > 3 && (
                              <span className="px-2 py-1 bg-slate-100 text-slate-700 text-xs rounded">
                                +{sop.required_tools.length - 3}
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Card Footer - Actions for Approved SOPs */}
                    <div className="bg-slate-50 px-6 py-4 border-t border-slate-200 flex gap-2">
                      <button
                        onClick={() => router.push(`/monitor/${sop.id}`)}
                        className="flex-1 px-3 py-2 bg-blue-500 text-white text-sm font-medium rounded hover:bg-blue-600 transition flex items-center justify-center gap-2 disabled:opacity-50"
                        disabled={actionInProgress === sop.id}
                      >
                        <svg
                          className="w-4 h-4"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                          />
                        </svg>
                        Start Monitoring
                      </button>
                      <button
                        onClick={() => deleteSOP(sop.id, sop.title)}
                        className="flex-1 px-3 py-2 bg-red-500 text-white text-sm font-medium rounded hover:bg-red-600 transition flex items-center justify-center gap-2 disabled:opacity-50"
                        disabled={actionInProgress === sop.id}
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                        {actionInProgress === sop.id ? 'Processing...' : 'Delete'}
                      </button>
                    </div>
                  </div>
                ))}
                    </div>
                  </div>
                )}

                {/* REVIEW REQUIRED SECTION */}
                {filteredReviewRequired.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-6">
                      <div className="w-1 h-6 bg-yellow-500 rounded"></div>
                      <h2 className="text-2xl font-bold text-slate-900">Review Required</h2>
                      <span className="ml-2 px-3 py-1 bg-yellow-100 text-yellow-800 text-sm font-semibold rounded-full">
                        {filteredReviewRequired.length}
                      </span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                      {filteredReviewRequired.map((sop) => (
                  <div
                    key={sop.id}
                    className="bg-white rounded-lg border border-yellow-200 hover:border-yellow-300 hover:shadow-lg transition overflow-hidden"
                  >
                    {/* Card Header */}
                    <div className="p-6">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="px-2 py-1 bg-yellow-100 text-yellow-800 text-xs font-semibold rounded">
                          PENDING
                        </span>
                      </div>
                      <h3 className="text-lg font-bold text-slate-900 mb-2 line-clamp-2">
                        {sop.title}
                      </h3>
                      <p className="text-slate-600 text-sm mb-4 line-clamp-3">
                        {sop.purpose}
                      </p>

                      {/* Stats */}
                      <div className="flex gap-4 text-sm text-slate-600 mb-4">
                        <div className="flex items-center gap-1">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <span>{sop.steps?.length || 0} steps</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <span>{sop.estimated_duration}</span>
                        </div>
                      </div>

                      {/* Tools */}
                      {sop.required_tools && sop.required_tools.length > 0 && (
                        <div className="mb-4">
                          <p className="text-xs font-semibold text-slate-500 uppercase mb-2">
                            Tools Required
                          </p>
                          <div className="flex flex-wrap gap-1">
                            {sop.required_tools.slice(0, 3).map((tool, idx) => (
                              <span key={idx} className="px-2 py-1 bg-slate-100 text-slate-700 text-xs rounded">
                                {tool}
                              </span>
                            ))}
                            {sop.required_tools.length > 3 && (
                              <span className="px-2 py-1 bg-slate-100 text-slate-700 text-xs rounded">
                                +{sop.required_tools.length - 3}
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Card Footer - Actions for Review Required SOPs */}
                    <div className="bg-slate-50 px-6 py-4 border-t border-slate-200 flex gap-2">
                      <button
                        onClick={() => approveSOP(sop.id, sop.title)}
                        className="flex-1 px-3 py-2 bg-green-500 text-white text-sm font-medium rounded hover:bg-green-600 transition flex items-center justify-center gap-2 disabled:opacity-50"
                        disabled={actionInProgress === sop.id}
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        {actionInProgress === sop.id ? 'Processing...' : 'Approve'}
                      </button>
                      <button
                        onClick={() => deleteSOP(sop.id, sop.title)}
                        className="flex-1 px-3 py-2 bg-red-500 text-white text-sm font-medium rounded hover:bg-red-600 transition flex items-center justify-center gap-2 disabled:opacity-50"
                        disabled={actionInProgress === sop.id}
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                        {actionInProgress === sop.id ? 'Processing...' : 'Delete'}
                      </button>
                    </div>
                  </div>
                ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}

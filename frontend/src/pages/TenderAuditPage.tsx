// ---------------------------------------------------------------------------
// frontend/src/pages/TenderAuditPage.tsx
// Tender Compliance Audit — 4-stage coordinator
// IDLE → UPLOADING → POLLING → RESULTS
//
// PDF export calls backend POST /api/audit/export-pdf (ReportLab, server-side)
//   - Accepted rows → AI-recommended corrected specification in PDF
//   - Rejected rows → Original specification from tender document in PDF
// ---------------------------------------------------------------------------

import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { RotateCcw, ArrowLeft, FileDown, X, Pencil, Check, AlertCircle } from 'lucide-react'
import { Shell } from '@/components/layout/Shell'
import { useTranslation } from '@/i18n/I18nContext'

import {
  uploadAuditFiles,
  createAuditJob,
  getAuditJobResults,
  rerunAuditItem,
  type AuditResultsResponse,
  type AuditedItemDTO,
  type AuditJobPollResponse,
  type CreateJobRequest,
} from '@/lib/auditApi'
import { AuditUploadZone } from '@/components/audit/AuditUploadZone'
import { AuditProgressView } from '@/components/audit/AuditProgressView'
import { AuditScorecardBanner } from '@/components/audit/AuditScorecardBanner'
import { AuditItemCard, type AcceptedRecommendation } from '@/components/audit/AuditItemCard'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'

// ── Stage type ───────────────────────────────────────────────────────────────
type Stage = 'idle' | 'uploading' | 'polling' | 'results' | 'error'

// ── Editable row in the pre-export modal ─────────────────────────────────────
interface EditableRow {
  key: string
  slNo: number
  materialCode: string
  shortDescription: string
  technicalSpecification: string    // shown in modal for editing
  unit: string
  quantity: string
  action: 'accepted' | 'rejected' | 'compliant'
  originalSpecification: string     // always the raw original spec from the tender
}

// ── Backend PDF export API call ───────────────────────────────────────────────
async function callExportPdf(payload: {
  ref_no: string
  title: string
  organization?: string
  date?: string
  rows: Array<{
    sl_no: number
    material_code: string
    short_description: string
    technical_specification: string
    unit: string
    quantity: string
    action: string
    original_specification: string
  }>
}): Promise<void> {
  const res = await fetch('/api/audit/export-pdf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try { const d = await res.json(); if (d.detail) msg = d.detail } catch {}
    throw new Error(msg)
  }

  // Trigger browser download from blob
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  const today = new Date().toISOString().slice(0, 10)
  const safe = payload.ref_no.replace(/[^a-zA-Z0-9]/g, '_')
  a.href = url
  a.download = `Audit_Report_${safe}_${today}.pdf`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// ── PDF Export Modal ──────────────────────────────────────────────────────────
function PdfExportModal({
  rows,
  onClose,
}: {
  rows: EditableRow[]
  onClose: () => void
}) {
  const [editRows, setEditRows] = useState<EditableRow[]>(rows)
  const [refNo, setRefNo] = useState('100001922')
  const [title, setTitle] = useState('Procurement Technical Specification — BIS Audit Report')
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)

  const updateCell = (key: string, field: keyof EditableRow, value: string) => {
    setEditRows(prev =>
      prev.map(r => r.key === key ? { ...r, [field]: value } : r)
    )
  }

  const handleExport = async () => {
    setExporting(true)
    setExportError(null)
    try {
      await callExportPdf({
        ref_no: refNo,
        title,
        rows: editRows.map(r => ({
          sl_no: r.slNo,
          material_code: r.materialCode,
          short_description: r.shortDescription,
          // Pass the edited technical specification (compliant spec, accepted AI clause, or original tender spec)
          technical_specification: r.technicalSpecification || r.originalSpecification || '',
          unit: r.unit,
          quantity: r.quantity,
          action: r.action,
          original_specification: r.originalSpecification,
        })),
      })
      onClose()
    } catch (e: any) {
      setExportError(e.message ?? 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  const accepted = editRows.filter(r => r.action === 'accepted')
  const rejected = editRows.filter(r => r.action === 'rejected')
  const compliant = editRows.filter(r => r.action === 'compliant')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-6xl max-h-[92vh] flex flex-col bg-white dark:bg-zinc-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-zinc-700 overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-800/50 shrink-0">
          <div className="flex items-center gap-3">
            <FileDown className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-zinc-100">Export Audit Report PDF</h2>
              <p className="text-xs text-slate-500 dark:text-zinc-400 flex flex-wrap gap-x-1">
                {compliant.length > 0 && <span className="text-teal-600 dark:text-teal-400 font-semibold">{compliant.length} compliant</span>}
                {accepted.length > 0 && <span className="text-emerald-600 dark:text-emerald-400 font-semibold">{accepted.length} accepted</span>}
                {rejected.length > 0 && <span className="text-rose-500 dark:text-rose-400 font-semibold">{rejected.length} rejected</span>}
                <span>· All fields editable before export</span>
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-xl hover:bg-slate-200 dark:hover:bg-zinc-700 text-slate-500 dark:text-zinc-400 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Meta fields */}
        <div className="px-6 py-3 border-b border-slate-100 dark:border-zinc-800 bg-white dark:bg-zinc-900 shrink-0">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-zinc-500 mb-1">Ref No</label>
              <input
                value={refNo}
                onChange={e => setRefNo(e.target.value)}
                className="w-full px-3 py-1.5 text-xs border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-slate-800 dark:text-zinc-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-zinc-500 mb-1">Document Title</label>
              <input
                value={title}
                onChange={e => setTitle(e.target.value)}
                className="w-full px-3 py-1.5 text-xs border border-slate-200 dark:border-zinc-700 rounded-lg bg-white dark:bg-zinc-800 text-slate-800 dark:text-zinc-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Legend */}
        <div className="px-6 py-2 border-b border-slate-100 dark:border-zinc-800 bg-white dark:bg-zinc-900 shrink-0 flex items-center gap-4 text-[11px] flex-wrap">
          <span className="flex items-center gap-1.5 text-teal-700 dark:text-teal-400">
            <span className="w-2.5 h-2.5 rounded-sm bg-teal-100 dark:bg-teal-900/60 border border-teal-300 dark:border-teal-700 inline-block" />
            ✓ Compliant — Already correct in tender (auto-included)
          </span>
          <span className="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400">
            <span className="w-2.5 h-2.5 rounded-sm bg-emerald-100 dark:bg-emerald-900/60 border border-emerald-300 dark:border-emerald-700 inline-block" />
            AI — Accepted corrected specification
          </span>
          <span className="flex items-center gap-1.5 text-slate-500 dark:text-zinc-500">
            <span className="w-2.5 h-2.5 rounded-sm bg-slate-100 dark:bg-zinc-800 border border-slate-300 dark:border-zinc-600 inline-block" />
            ORIG — Rejected (original spec from tender)
          </span>
        </div>

        {/* Editable table */}
        <div className="flex-1 overflow-auto px-4 py-4">
          {editRows.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 text-center">
              <p className="text-slate-400 dark:text-zinc-600 text-sm">No items in PDF yet.</p>
              <p className="text-slate-400 dark:text-zinc-600 text-xs mt-1">Compliant items are auto-included. Accept or Reject recommendations to add non-compliant items.</p>
            </div>
          ) : (
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50 dark:bg-zinc-800">
                  {['', 'Sl.no', 'Material Code', 'Short Description', 'Technical Specification', 'Unit', 'Qty'].map(h => (
                    <th key={h} className="px-2 py-2 font-bold text-slate-700 dark:text-zinc-300 border border-slate-200 dark:border-zinc-700 text-center text-[11px] whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {editRows.map(row => {
                  const isRejected = row.action === 'rejected'
                  const isCompliant = row.action === 'compliant'
                  const rowBg = isCompliant
                    ? 'bg-teal-50/40 dark:bg-teal-950/10'
                    : isRejected
                      ? 'bg-slate-50/80 dark:bg-zinc-800/30'
                      : 'bg-emerald-50/30 dark:bg-emerald-950/10'
                  const badgeClass = isCompliant
                    ? 'bg-teal-100 dark:bg-teal-900/60 text-teal-700 dark:text-teal-300'
                    : isRejected
                      ? 'bg-slate-100 dark:bg-zinc-700 text-slate-500 dark:text-zinc-400'
                      : 'bg-emerald-100 dark:bg-emerald-900/60 text-emerald-700 dark:text-emerald-300'
                  const badgeLabel = isCompliant ? '✓ OK' : isRejected ? 'ORIG' : 'AI'
                  const textClass = isRejected
                    ? 'text-slate-600 dark:text-zinc-400 italic'
                    : 'text-slate-800 dark:text-zinc-200'

                  return (
                    <tr key={row.key} className={rowBg}>
                      {/* Status badge */}
                      <td className="border border-slate-200 dark:border-zinc-700 px-2 py-1 text-center">
                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${badgeClass}`}>
                          {badgeLabel}
                        </span>
                      </td>
                      <td className="border border-slate-200 dark:border-zinc-700 p-1 text-center text-slate-600 dark:text-zinc-400 font-mono">
                        {row.slNo * 10}
                      </td>
                      {(['materialCode', 'shortDescription', 'technicalSpecification', 'unit', 'quantity'] as const).map(field => (
                        <td key={field} className="border border-slate-200 dark:border-zinc-700 p-1">
                          <div className="relative group">
                            <textarea
                              value={String(row[field] ?? '')}
                              onChange={e => updateCell(row.key, field, e.target.value)}
                              rows={field === 'technicalSpecification' ? 4 : 1}
                              className={`w-full resize-none px-1.5 py-1 text-xs bg-transparent border border-transparent rounded focus:outline-none focus:border-blue-400 focus:bg-blue-50/30 dark:focus:bg-blue-950/20 transition-colors leading-relaxed ${textClass}`}
                            />
                            <Pencil className="absolute top-1 right-1 w-2.5 h-2.5 text-slate-300 dark:text-zinc-600 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity" />
                          </div>
                        </td>
                      ))}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Error */}
        {exportError && (
          <div className="px-6 py-2 bg-rose-50 dark:bg-rose-950/30 border-t border-rose-200 dark:border-rose-800 shrink-0 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />
            <p className="text-xs text-rose-700 dark:text-rose-300">{exportError}</p>
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-800/50 shrink-0">
          <p className="text-xs text-slate-400 dark:text-zinc-500">
            <Pencil className="w-3 h-3 inline mr-1" />
            Click any cell to edit · PDF generated by backend (ReportLab)
          </p>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold rounded-xl border border-slate-200 dark:border-zinc-700 text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-700 transition-all"
            >
              Cancel
            </button>
            <button
              onClick={handleExport}
              disabled={exporting || editRows.length === 0}
              className="flex items-center gap-2 px-5 py-2 text-xs font-bold rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white shadow-sm transition-all"
            >
              {exporting ? (
                <>
                  <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Generating PDF…
                </>
              ) : (
                <>
                  <FileDown className="w-3.5 h-3.5" />
                  Download PDF
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Results view ─────────────────────────────────────────────────────────────
interface ResultsViewProps {
  results: AuditResultsResponse
  onReset: () => void
  onItemUpdate: (updatedItem: AuditedItemDTO) => void
  decidedRecs: AcceptedRecommendation[]
  onDecideRec: (rec: AcceptedRecommendation) => void
  onOpenPdfModal: () => void
  compliantCount: number
}

function ResultsView({
  results,
  onReset,
  onItemUpdate,
  decidedRecs,
  onDecideRec,
  onOpenPdfModal,
  compliantCount,
}: ResultsViewProps) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [rerunning, setRerunning] = useState<Set<number>>(new Set())

  const toggleExpand = (seqNo: number) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(seqNo)) next.delete(seqNo)
      else next.add(seqNo)
      return next
    })
  }

  const handleRerun = async (seqNo: number) => {
    if (!results.job_id || rerunning.has(seqNo)) return
    setRerunning(prev => new Set(prev).add(seqNo))
    try {
      const resp = await rerunAuditItem(results.job_id, seqNo)
      onItemUpdate(resp.item)
    } catch (e) {
      console.error('Rerun failed:', e)
    } finally {
      setRerunning(prev => {
        const next = new Set(prev)
        next.delete(seqNo)
        return next
      })
    }
  }

  const filenames = results.items.length > 0
    ? (results as any).filenames ?? null
    : null

  const allExpanded = expanded.size === results.items.length && results.items.length > 0
  const acceptedCount = decidedRecs.filter(r => r.action === 'accepted').length
  const rejectedCount = decidedRecs.filter(r => r.action === 'rejected').length
  const totalDecided = decidedRecs.length
  // Total items going into PDF = compliant (auto) + decided (accepted/rejected)
  const totalInPdf = compliantCount + totalDecided

  return (
    <div className="min-h-full px-4 py-6 space-y-6 max-w-5xl mx-auto">
      {/* Top bar */}
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-lg font-bold text-slate-900 dark:text-zinc-100 truncate">
            {t('audit.upload_title')}
          </h1>
          {filenames && (
            <p className="text-xs text-slate-400 dark:text-zinc-500 truncate">
              {Array.isArray(filenames) ? filenames.join(', ') : filenames}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {/* Export PDF button */}
          <button
            onClick={onOpenPdfModal}
            className="relative flex items-center gap-1.5 px-4 py-1.5 rounded-xl text-xs font-bold bg-blue-600 hover:bg-blue-700 text-white shadow-sm transition-all"
          >
            <FileDown className="w-3.5 h-3.5" />
            Export Audit PDF
            {totalInPdf > 0 && (
              <span className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-emerald-500 text-white text-[9px] font-bold flex items-center justify-center">
                {totalInPdf}
              </span>
            )}
          </button>

          <button
            onClick={onReset}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-600 dark:text-zinc-400 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700 hover:border-slate-300 dark:hover:border-zinc-600 shadow-sm transition-all"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            {t('audit.new_audit')}
          </button>
        </div>
      </div>

      {/* Status banner */}
      {(compliantCount > 0 || totalDecided > 0) && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800">
          <Check className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0" />
          <p className="text-xs text-blue-700 dark:text-blue-300 font-medium flex flex-wrap gap-x-1">
            {compliantCount > 0 && (
              <span><strong className="text-emerald-600 dark:text-emerald-400">{compliantCount} compliant</strong> (auto-included)</span>
            )}
            {compliantCount > 0 && totalDecided > 0 && <span>·</span>}
            {acceptedCount > 0 && (
              <strong className="text-blue-600 dark:text-blue-400">{acceptedCount} accepted</strong>
            )}
            {rejectedCount > 0 && (
              <><strong className="text-rose-500 dark:text-rose-400">{rejectedCount} rejected</strong> (original spec)</>
            )}
            {' '}— click <strong>Export Audit PDF</strong> to review and download.
          </p>
        </div>
      )}

      {/* Scorecard */}
      <AuditScorecardBanner results={results} />

      {/* Items header */}
      <div className="flex items-center gap-3">
        <h2 className="text-sm font-bold text-slate-800 dark:text-zinc-200">
          {t('audit.line_items').replace('{n}', String(results.items.length))}
        </h2>
        {results.items.length > 0 && (
          <button
            onClick={() => setExpanded(allExpanded ? new Set() : new Set(results.items.map(it => it.seq_no)))}
            className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
          >
            {allExpanded ? t('audit.collapse_all') : t('audit.expand_all')}
          </button>
        )}
      </div>

      {/* Item cards */}
      <div className="space-y-3">
        {results.items.map(item => (
          <AuditItemCard
            key={item.seq_no}
            item={item}
            isExpanded={expanded.has(item.seq_no)}
            onToggle={() => toggleExpand(item.seq_no)}
            onRerun={handleRerun}
            isRerunning={rerunning.has(item.seq_no)}
            onAcceptRecommendation={onDecideRec}
          />
        ))}
      </div>

      {results.items.length === 0 && (
        <div className="text-center py-20 text-slate-400 dark:text-zinc-600 text-sm">
          No items were produced by this audit job.
        </div>
      )}
    </div>
  )
}

// ── Main Page ────────────────────────────────────────────────────────────────
export function TenderAuditPage() {
  const [stage, setStage] = useState<Stage>('idle')
  const [jobId, setJobId] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [results, setResults] = useState<AuditResultsResponse | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  // ── Decided recommendations (both accept + reject) ────────────────────────
  const [decidedRecs, setDecidedRecs] = useState<AcceptedRecommendation[]>([])
  const [showPdfModal, setShowPdfModal] = useState(false)

  const handleDecideRec = useCallback((rec: AcceptedRecommendation) => {
    setDecidedRecs(prev => {
      // Deduplicate by seqNo + recommendedStandard — latest decision wins
      const key = `${rec.seqNo}::${rec.recommendedStandard}`
      const filtered = prev.filter(r => `${r.seqNo}::${r.recommendedStandard}` !== key)
      return [...filtered, rec]
    })
  }, [])

  // Helper: normalize quantity and unit in case they were extracted in reverse
  const normalizeQtyUnit = (rawQty: any, rawUnit: any): { qty: string; unit: string } => {
    let q = rawQty != null ? String(rawQty).trim() : ''
    let u = rawUnit != null ? String(rawUnit).trim() : ''
    const isNum = (s: string) => /^\d+(\.\d+)?$/.test(s)
    // If unit is numeric and qty is letters or empty, swap them
    if (isNum(u) && (!isNum(q) || q.length === 0)) {
      return { qty: u, unit: q }
    }
    return { qty: q, unit: u }
  }

  // Helper: extract the exact technical specification from a compliant item
  const getCompliantSpec = (item: AuditedItemDTO): string => {
    // 1. Direct verbatim technical specification extracted from the tender document
    if (item.technical_spec && item.technical_spec.trim().length > 0) {
      return item.technical_spec.trim()
    }
    const cited = item.cited_standards ?? []
    // 2. Check if the tender provided a verbatim specification quote
    for (const cs of cited) {
      if (cs.quote?.quote_text && cs.quote.quote_text.trim().length > 5) {
        return cs.quote.quote_text.trim()
      }
    }
    const findings = item.findings ?? []
    for (const f of findings) {
      const q = typeof f.evidence?.quote === 'string' ? f.evidence.quote.trim() : ''
      if (q && q.length > 5) {
        return q
      }
    }
    // 3. Format clean compliance specification from cited standards
    if (cited.length > 0) {
      const parts = cited
        .map(cs => {
          let num = cs.resolved_standard_number ?? cs.raw_citation ?? ''
          if (cs.resolved_year && !num.includes(String(cs.resolved_year))) {
            num = `${num}:${cs.resolved_year}`
          }
          return num
        })
        .filter(Boolean)
      if (parts.length > 0) {
        return `Material shall comply with ${parts.join(', ')} with up-to-date amendments.`
      }
    }
    return item.description ?? `Item ${item.seq_no} — Compliant`
  }

  // ── Build editable rows for modal ─────────────────────────────────────────
  const buildEditableRows = (): EditableRow[] => {
    if (!results || !results.items) return []

    const rows: EditableRow[] = []

    for (const item of results.items) {
      const isCompliant =
        item.status === 'compliant' ||
        item.status?.toLowerCase() === 'compliant' ||
        item.badge_color === 'green'

      const userDecisions = decidedRecs.filter(r => r.seqNo === item.seq_no)
      const matCode =
        item.material_code ||
        (item as any).material_code ||
        (item.item_id && typeof item.item_id === 'string' && !/^\d+$/.test(item.item_id) ? item.item_id : '')

      if (isCompliant) {
        // Compliant tender item cited correctly -> auto-included in technical specification table
        const spec = getCompliantSpec(item)
        const { qty, unit } = normalizeQtyUnit(item.quantity, item.unit)
        rows.push({
          key: `compliant-${item.seq_no}`,
          slNo: item.seq_no,
          materialCode: matCode,
          shortDescription: item.description ?? `Item ${item.seq_no}`,
          technicalSpecification: spec,
          unit,
          quantity: qty,
          action: 'compliant',
          originalSpecification: spec,
        })
      } else if (userDecisions.length > 0) {
        // User accepted or rejected recommendation(s) for this non-compliant item
        userDecisions.forEach((rec, idx) => {
          const isAccepted = rec.action === 'accepted'
          const { qty, unit } = normalizeQtyUnit(rec.quantity, rec.unit)
          // For rejected rows: ensure complete original spec from tender is preserved
          const originalSpec =
            item.technical_spec && item.technical_spec.trim().length > (rec.originalSpec?.length || 0)
              ? item.technical_spec.trim()
              : (rec.originalSpec || item.technical_spec || getCompliantSpec(item))

          rows.push({
            key: `decided-${rec.seqNo}-${idx}`,
            slNo: item.seq_no,
            materialCode: matCode,
            shortDescription: rec.description,
            technicalSpecification: isAccepted ? rec.clauseText : originalSpec,
            unit,
            quantity: qty,
            action: rec.action,
            originalSpecification: originalSpec,
          })
        })
      }
    }

    // Sort by sequence number in tender to preserve original order
    rows.sort((a, b) => a.slNo - b.slNo)

    // Number sequentially as 1, 2, 3...
    return rows.map((r, idx) => ({ ...r, slNo: idx + 1 }))
  }

  // ── File upload handler ───────────────────────────────────────────────────
  const handleFilesSelected = useCallback(async (files: File[]) => {
    setStage('uploading')
    setUploadError(null)
    setDecidedRecs([])
    try {
      const job = await uploadAuditFiles(files, 'gem')
      setJobId(job.id)
      setStage('polling')
    } catch (e: any) {
      setUploadError(e.message ?? 'Upload failed')
      setStage('idle')
    }
  }, [])

  // ── Text paste handler ────────────────────────────────────────────────────
  const handleTextSubmitted = useCallback(async (text: string) => {
    setStage('uploading')
    setUploadError(null)
    setDecidedRecs([])
    try {
      const payload: CreateJobRequest = {
        raw_items: [{ description: text, technical_spec: text }],
        doc_type: 'generic',
      }
      const job = await createAuditJob(payload)
      setJobId(job.id)
      setStage('polling')
    } catch (e: any) {
      setUploadError(e.message ?? 'Failed to create audit job')
      setStage('idle')
    }
  }, [])

  // ── Polling completion handlers ───────────────────────────────────────────
  const handlePollingCompleted = useCallback(async (pollData: AuditJobPollResponse) => {
    try {
      const finalResults = await getAuditJobResults(pollData.id)
      setResults(finalResults)
      setStage('results')
    } catch (e: any) {
      setErrorMsg(e.message ?? 'Failed to fetch audit results')
      setStage('error')
    }
  }, [])

  const handlePollingFailed = useCallback((msg: string) => {
    setErrorMsg(msg)
    setStage('error')
  }, [])

  // ── Single-item rerun update ──────────────────────────────────────────────
  const handleItemUpdate = useCallback((updatedItem: AuditedItemDTO) => {
    setResults(prev => {
      if (!prev) return prev
      return {
        ...prev,
        items: prev.items.map(it => it.seq_no === updatedItem.seq_no ? updatedItem : it),
      }
    })
  }, [])

  // ── Reset ─────────────────────────────────────────────────────────────────
  const handleReset = useCallback(() => {
    setStage('idle')
    setJobId(null)
    setResults(null)
    setErrorMsg(null)
    setUploadError(null)
    setDecidedRecs([])
  }, [])

  return (
    <Shell botContext="audit" botQueryContext={results?.job_id || jobId || undefined}>
      <div className="min-h-full bg-slate-50/30 dark:bg-zinc-950">
        <AnimatePresence mode="wait">

          {/* ── IDLE ── */}
          {stage === 'idle' && (
            <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2 }}>
              <AuditUploadZone
                onFilesSelected={handleFilesSelected}
                onTextSubmitted={handleTextSubmitted}
                isUploading={false}
                error={uploadError}
              />
            </motion.div>
          )}

          {/* ── UPLOADING ── */}
          {stage === 'uploading' && (
            <motion.div key="uploading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex flex-col items-center justify-center min-h-[calc(100vh-3.5rem)] gap-4"
            >
              <svg className="w-10 h-10 animate-spin text-blue-500" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              <p className="text-sm text-slate-500 dark:text-zinc-400">Uploading document…</p>
            </motion.div>
          )}

          {/* ── POLLING ── */}
          {stage === 'polling' && jobId && (
            <motion.div key="polling" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
              <AuditProgressView
                jobId={jobId}
                onCompleted={handlePollingCompleted}
                onFailed={handlePollingFailed}
              />
            </motion.div>
          )}

          {/* ── RESULTS ── */}
          {stage === 'results' && results && (
            <motion.div key="results" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            >
              <ErrorBoundary fallbackTitle="Audit Results Display Error" onReset={handleReset}>
                <ResultsView
                  results={results}
                  onReset={handleReset}
                  onItemUpdate={handleItemUpdate}
                  decidedRecs={decidedRecs}
                  onDecideRec={handleDecideRec}
                  onOpenPdfModal={() => setShowPdfModal(true)}
                  compliantCount={(results?.items ?? []).filter(
                    it => it.status === 'compliant' || it.status?.toLowerCase() === 'compliant' || it.badge_color === 'green'
                  ).length}
                />
              </ErrorBoundary>
            </motion.div>
          )}

          {/* ── ERROR ── */}
          {stage === 'error' && (
            <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="flex flex-col items-center justify-center min-h-[calc(100vh-3.5rem)] gap-5 px-6"
            >
              <div className="w-16 h-16 rounded-2xl bg-rose-100 dark:bg-rose-950/40 flex items-center justify-center">
                <svg className="w-8 h-8 text-rose-600 dark:text-rose-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><circle cx="12" cy="16" r="1" fill="currentColor" />
                </svg>
              </div>
              <div className="text-center space-y-1 max-w-md">
                <h2 className="text-base font-bold text-slate-900 dark:text-zinc-100">Audit Failed</h2>
                <p className="text-sm text-slate-500 dark:text-zinc-400">{errorMsg}</p>
              </div>
              <button onClick={handleReset} className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-blue-600 hover:bg-blue-700 text-white shadow-sm transition-all">
                <RotateCcw className="w-4 h-4" />
                Try Again
              </button>
            </motion.div>
          )}

        </AnimatePresence>
      </div>

      {/* ── PDF Export Modal (outside AnimatePresence) ── */}
      {showPdfModal && (
        <PdfExportModal
          rows={buildEditableRows()}
          onClose={() => setShowPdfModal(false)}
        />
      )}
    </Shell>
  )
}

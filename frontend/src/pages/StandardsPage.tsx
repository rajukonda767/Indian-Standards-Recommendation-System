import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search, X, ExternalLink, ChevronRight,
  Award, Layers, GitBranch, Loader2,
  LayoutGrid, ArrowLeft, ShieldCheck, FileText, CheckCircle2,
  ChevronDown, History, RotateCcw, BookOpen, RefreshCw, FileEdit
} from 'lucide-react'
import { Shell } from '@/components/layout/Shell'
import { useTranslation } from '@/i18n/I18nContext'
import {
  listStandards, getStandardDetail, getFilterOptions,
  type StandardSummary, type StandardDetail,
} from '@/lib/api'
import { clsx } from 'clsx'

// ── Department definitions (ETD, CED, MTD) ──────────────────────────────────
const DEPARTMENTS = [
  { code: 'ALL', label: 'All Depts', fullName: 'All Technical Sectors' },
  { code: 'ETD', label: 'ETD', fullName: 'Electrotechnical Department' },
  { code: 'CED', label: 'CED', fullName: 'Civil Engineering Department' },
  { code: 'MTD', label: 'MTD', fullName: 'Metallurgical Engineering' },
]

// ── Status options ──────────────────────────────────────────────────────────
const STATUS_OPTIONS = [
  { value: 'ALL', label: 'All Statuses' },
  { value: 'Current', label: 'Current' },
  { value: 'Reaffirmed', label: 'Reaffirmed' },
  { value: 'Under Review', label: 'Under Review' },
  { value: 'Published', label: 'Published' },
  { value: 'Withdrawn', label: 'Withdrawn' },
]

// ── Status badge color utility ──────────────────────────────────────────────
function getStatusDetails(status: string | null, reaffirmationYear?: number | null) {
  if (reaffirmationYear) {
    return {
      label: `Reaffirmed:${reaffirmationYear}`,
      className: 'bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 ring-1 ring-blue-200 dark:ring-blue-800'
    }
  }
  const s = (status || '').toLowerCase()
  if (s.includes('current') || s.includes('active')) {
    return {
      label: 'Current',
      className: 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 ring-1 ring-emerald-200 dark:ring-emerald-800'
    }
  }
  if (s.includes('reaffirm')) {
    return {
      label: 'Reaffirmed',
      className: 'bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 ring-1 ring-blue-200 dark:ring-blue-800'
    }
  }
  if (s.includes('under review')) {
    return {
      label: 'Under Review',
      className: 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 ring-1 ring-amber-200 dark:ring-amber-800'
    }
  }
  if (s.includes('withdraw') || s.includes('supersed')) {
    return {
      label: 'Withdrawn',
      className: 'bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 ring-1 ring-rose-200 dark:ring-rose-800'
    }
  }
  if (s.includes('publish')) {
    return {
      label: 'Published',
      className: 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 ring-1 ring-indigo-200 dark:ring-indigo-800'
    }
  }
  return {
    label: status || 'Standard',
    className: 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 ring-1 ring-zinc-200 dark:ring-zinc-700'
  }
}

function StatusBadge({ status, reaffirmationYear }: { status: string | null; reaffirmationYear?: number | null }) {
  const { label, className } = getStatusDetails(status, reaffirmationYear)
  return (
    <span className={clsx('inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold tracking-tight', className)}>
      {label}
    </span>
  )
}

function DeptBadge({ dept }: { dept: string | null }) {
  if (!dept) return null
  const cfg: Record<string, string> = {
    ETD: 'bg-cyan-50 dark:bg-cyan-950/50 text-cyan-700 dark:text-cyan-300 border-cyan-200 dark:border-cyan-800',
    CED: 'bg-amber-50 dark:bg-amber-950/50 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800',
    MTD: 'bg-purple-50 dark:bg-purple-950/50 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800',
  }
  return (
    <span className={clsx('inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold border uppercase tracking-wider', cfg[dept] ?? 'bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 border-slate-200 dark:border-zinc-700')}>
      {dept}
    </span>
  )
}

function MetaRow({ label, value }: { label: string; value?: string | number | null }) {
  if (!value && value !== 0) return null
  return (
    <div className="flex items-start gap-3 py-2.5 px-3 border-b border-slate-100 dark:border-zinc-800/80 last:border-0 hover:bg-slate-50/50 dark:hover:bg-zinc-800/20 transition-colors">
      <span className="text-[11px] font-semibold text-slate-400 dark:text-zinc-500 uppercase tracking-wider w-36 shrink-0 pt-0.5">
        {label}
      </span>
      <span className="text-xs text-slate-800 dark:text-zinc-200 leading-relaxed flex-1 font-medium">
        {String(value)}
      </span>
    </div>
  )
}

// ── Standard Card for 3-in-a-row Grid ─────────────────────────────────────────
interface StandardCardProps {
  standard: StandardSummary
  onClick: () => void
  selected?: boolean
}

function StandardCard({ standard, onClick, selected }: StandardCardProps) {
  return (
    <motion.div
      layout
      whileHover={{ y: -3, transition: { duration: 0.18 } }}
      onClick={onClick}
      className={clsx(
        'group cursor-pointer flex flex-col justify-between rounded-2xl p-5 transition-all text-left',
        'bg-white dark:bg-zinc-900 border',
        selected
          ? 'border-blue-500 dark:border-blue-500 ring-2 ring-blue-500/20 shadow-md'
          : 'border-slate-200 dark:border-zinc-800/90 hover:border-blue-400 dark:hover:border-blue-600/70 hover:shadow-lg hover:shadow-blue-500/5'
      )}
    >
      <div>
        {/* Top Badges */}
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-1.5 flex-wrap">
            <DeptBadge dept={standard.dept} />
            <StatusBadge status={standard.is_status_label} reaffirmationYear={standard.reaffirmation_year} />
          </div>
          {standard.qco_ministry && (
            <span
              title={`Mandatory QCO issued by ${standard.qco_ministry}`}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 ring-1 ring-amber-300 dark:ring-amber-700/60 shrink-0"
            >
              <ShieldCheck className="w-3 h-3 text-amber-500" />
              QCO
            </span>
          )}
        </div>

        {/* Standard Number */}
        <h3 className="text-base font-bold text-slate-900 dark:text-white tracking-tight group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors mb-2">
          {standard.standard_number}
        </h3>

        {/* Title */}
        <p className="text-xs text-slate-600 dark:text-zinc-400 leading-relaxed line-clamp-3 mb-4 font-normal">
          {standard.title}
        </p>
      </div>

      {/* Footer Stats & Action */}
      <div className="pt-3 border-t border-slate-100 dark:border-zinc-800/80 flex items-center justify-between text-[11px] text-slate-500 dark:text-zinc-400">
        <div className="flex items-center gap-3">
          {standard.active_licences > 0 ? (
            <span className="flex items-center gap-1 font-medium text-slate-700 dark:text-zinc-300">
              <Award className="w-3.5 h-3.5 text-blue-500" />
              {standard.active_licences} <span className="text-[10px] text-slate-400">licences</span>
            </span>
          ) : (
            <span className="text-slate-400 dark:text-zinc-500 text-[10px]">Standard Specification</span>
          )}
          {standard.references_count > 0 && (
            <span className="flex items-center gap-1 text-slate-500 dark:text-zinc-400 text-[10px]">
              <FileText className="w-3 h-3 text-slate-400" />
              {standard.references_count} refs
            </span>
          )}
        </div>

        <span className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 dark:text-blue-400 group-hover:translate-x-0.5 transition-transform">
          Inspect
          <ChevronRight className="w-3.5 h-3.5" />
        </span>
      </div>
    </motion.div>
  )
}

// ── Standard Lifecycle Timeline ──────────────────────────────────────────────
interface StandardLifecycleTimelineProps {
  detail: StandardDetail
  onSelectStandard?: (sn: string) => void
}

function StandardLifecycleTimeline({ detail, onSelectStandard }: StandardLifecycleTimelineProps) {
  // Extract predecessors and successors from lineage
  const predecessors = (detail.lineage || []).filter((l) => l.relationship === 'SUPERSEDES')
  const successors = (detail.lineage || []).filter((l) => l.relationship === 'SUPERSEDED_BY')

  // Parse revision label from title or revisions_count
  const revMatch = detail.title?.match(/\((first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+(?:st|nd|rd|th)?)\s+revision\)/i)
  const revisionLabel = revMatch
    ? `${revMatch[1].charAt(0).toUpperCase() + revMatch[1].slice(1)} Revision`
    : (detail.revisions_count && detail.revisions_count > 0 ? `Revision ${detail.revisions_count}` : 'Original Edition')

  const pubYear = detail.year || (detail.published_on ? new Date(detail.published_on).getFullYear() : null)
  const pubDateFormatted = detail.published_on
    ? new Date(detail.published_on).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
    : (pubYear ? `${pubYear}` : 'Published')

  const reaffYear = detail.reaffirmation_year
  const isWithdrawn = detail.is_status_label?.toLowerCase() === 'withdrawn'
  const isCurrent = !isWithdrawn && (detail.is_status_label?.toLowerCase() === 'current' || detail.is_status_label?.toLowerCase() === 'active')

  return (
    <div className="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/90 p-5 shadow-sm">
      <div className="flex items-center justify-between gap-2 mb-4 pb-3 border-b border-slate-100 dark:border-zinc-800/80">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 flex items-center justify-center">
            <History className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
              Standard Regulatory Lifecycle
            </h4>
            <p className="text-[11px] text-slate-500 dark:text-zinc-400 font-normal">
              Chronological evolution: Predecessors → Publication → Amendments → Reaffirmation
            </p>
          </div>
        </div>
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 border border-slate-200 dark:border-zinc-700">
          BIS Lifecycle Track
        </span>
      </div>

      <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-gradient-to-b before:from-slate-200 before:via-blue-300 before:to-emerald-400 dark:before:from-zinc-700 dark:before:via-blue-800 dark:before:to-emerald-600">
        
        {/* 1. Predecessor Editions (if superseded older standards exist) */}
        {predecessors.map((p, idx) => (
          <div key={`pred-${idx}`} className="relative group">
            <div className="absolute -left-6 top-0.5 w-5 h-5 rounded-full bg-slate-100 dark:bg-zinc-800 border-2 border-slate-400 dark:border-zinc-500 flex items-center justify-center shadow-xs">
              <RotateCcw className="w-2.5 h-2.5 text-slate-600 dark:text-zinc-400" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap mb-0.5">
                <span className="text-[11px] font-mono font-bold text-slate-500 dark:text-zinc-400">
                  {p.related_year ? `Year ${p.related_year}` : 'Predecessor Edition'}
                </span>
                <span className="px-1.5 py-0.2 rounded text-[10px] font-semibold bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 border border-slate-200 dark:border-zinc-700">
                  SUPERSEDED
                </span>
              </div>
              <h5 className="text-xs font-bold text-slate-800 dark:text-zinc-200 flex items-center gap-1.5">
                {p.related_standard_raw}
                {onSelectStandard && (
                  <button
                    onClick={() => onSelectStandard(p.related_standard_raw)}
                    className="inline-flex items-center gap-0.5 text-[10px] text-blue-600 dark:text-blue-400 hover:underline cursor-pointer ml-1"
                    title="Inspect predecessor standard"
                  >
                    Inspect <ExternalLink className="w-2.5 h-2.5" />
                  </button>
                )}
              </h5>
              <p className="text-[11px] text-slate-500 dark:text-zinc-400 leading-relaxed mt-0.5">
                Earlier standard specification. Withdrawn and replaced by the current edition.
              </p>
            </div>
          </div>
        ))}

        {/* 2. Official Publication / Revision */}
        <div className="relative group">
          <div className="absolute -left-6 top-0.5 w-5 h-5 rounded-full bg-blue-100 dark:bg-blue-950 border-2 border-blue-500 dark:border-blue-400 flex items-center justify-center shadow-xs">
            <BookOpen className="w-2.5 h-2.5 text-blue-600 dark:text-blue-300" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap mb-0.5">
              <span className="text-[11px] font-mono font-bold text-blue-700 dark:text-blue-300">
                {pubDateFormatted}
              </span>
              <span className="px-1.5 py-0.2 rounded text-[10px] font-semibold bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                {revisionLabel.toUpperCase()}
              </span>
            </div>
            <h5 className="text-xs font-bold text-slate-900 dark:text-white">
              Officially Published: {detail.standard_number}
            </h5>
            <p className="text-[11px] text-slate-600 dark:text-zinc-400 leading-relaxed mt-0.5">
              Published by BIS {detail.technical_committee ? `Technical Committee ${detail.technical_committee}` : 'Technical Committee'} ({detail.dept} Division Council) establishing primary technical requirements.
            </p>
          </div>
        </div>

        {/* 3. Amendments & Industrial Enforcement Period */}
        <div className="relative group">
          <div className="absolute -left-6 top-0.5 w-5 h-5 rounded-full bg-amber-100 dark:bg-amber-950 border-2 border-amber-500 dark:border-amber-400 flex items-center justify-center shadow-xs">
            <FileEdit className="w-2.5 h-2.5 text-amber-600 dark:text-amber-300" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap mb-0.5">
              <span className="text-[11px] font-mono font-bold text-amber-700 dark:text-amber-400">
                {pubYear ? `${pubYear} – ${reaffYear || 'Active'}` : 'Post-Publication Phase'}
              </span>
              <span className="px-1.5 py-0.2 rounded text-[10px] font-semibold bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
                AMENDMENTS & GOVERNANCE
              </span>
            </div>
            <h5 className="text-xs font-bold text-slate-900 dark:text-white">
              Gazette Amendments & Statutory Enforcement
            </h5>
            <p className="text-[11px] text-slate-600 dark:text-zinc-400 leading-relaxed mt-0.5">
              {detail.qco_ministry
                ? `Mandatory Quality Control Order (QCO) gazetted by ${detail.qco_ministry}. Manufacturing, sale, and procurement without BIS certification is punishable by law.`
                : detail.active_licences > 0
                ? `${detail.active_licences} verified domestic manufacturing units currently licensed under Scheme I (ISI Mark). Subject to regular BIS sectional committee updates.`
                : 'Subject to periodic BIS sectional committee amendments, test method alignments, and corrigenda.'}
            </p>
          </div>
        </div>

        {/* 4. Technical Committee 5-Year Reaffirmation */}
        <div className="relative group">
          <div className="absolute -left-6 top-0.5 w-5 h-5 rounded-full bg-emerald-100 dark:bg-emerald-950 border-2 border-emerald-500 dark:border-emerald-400 flex items-center justify-center shadow-xs">
            <RefreshCw className="w-2.5 h-2.5 text-emerald-600 dark:text-emerald-300" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap mb-0.5">
              <span className="text-[11px] font-mono font-bold text-emerald-700 dark:text-emerald-400">
                {reaffYear ? `Reaffirmed ${reaffYear}` : '5-Year Surveillance Cycle'}
              </span>
              <span className="px-1.5 py-0.2 rounded text-[10px] font-semibold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                {reaffYear ? 'REAFFIRMED BY COMMITTEE' : 'ACTIVE REVIEW CYCLE'}
              </span>
            </div>
            <h5 className="text-xs font-bold text-slate-900 dark:text-white">
              {reaffYear ? `Confirmed Current through ${reaffYear}` : 'Periodic Technical Committee Review'}
            </h5>
            <p className="text-[11px] text-slate-600 dark:text-zinc-400 leading-relaxed mt-0.5">
              {reaffYear
                ? `BIS Technical Committee formally completed the 5-year statutory reaffirmation review in ${reaffYear}, certifying that technical parameters remain valid without revision.`
                : 'Governed under continuous 5-year periodic reaffirmation surveillance by the technical sectional committee.'}
            </p>
          </div>
        </div>

        {/* 5. Current Regulatory Status */}
        <div className="relative group">
          <div className={clsx(
            "absolute -left-6 top-0.5 w-5 h-5 rounded-full border-2 flex items-center justify-center shadow-xs",
            isWithdrawn
              ? "bg-rose-100 dark:bg-rose-950 border-rose-500 text-rose-600 dark:text-rose-400"
              : isCurrent
              ? "bg-emerald-100 dark:bg-emerald-950 border-emerald-600 text-emerald-600 dark:text-emerald-400"
              : "bg-blue-100 dark:bg-blue-950 border-blue-500 text-blue-600 dark:text-blue-400"
          )}>
            <ShieldCheck className="w-2.5 h-2.5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap mb-0.5">
              <span className="text-[11px] font-mono font-bold text-slate-900 dark:text-white">
                Current Status
              </span>
              <span className={clsx(
                "px-1.5 py-0.2 rounded text-[10px] font-bold uppercase",
                isWithdrawn
                  ? "bg-rose-50 dark:bg-rose-950 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800"
                  : "bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
              )}>
                {detail.is_status_label || 'Current'}
              </span>
            </div>
            <h5 className="text-xs font-bold text-slate-900 dark:text-white">
              {isWithdrawn
                ? 'Standard Withdrawn — Do Not Cite in New Tenders'
                : 'Active for Public Procurement (GeM / CPPP)'}
            </h5>
            <p className="text-[11px] text-slate-600 dark:text-zinc-400 leading-relaxed mt-0.5">
              {isWithdrawn
                ? 'This edition has been withdrawn from circulation. Tenders must not cite this standard.'
                : 'Fully compliant with Rule 144 of the General Financial Rules (GFR) 2017 and BIS Act 2016 for tender technical schedules.'}
            </p>
          </div>
        </div>

        {/* 6. Successor Standards (if superseded by newer edition) */}
        {successors.map((s, idx) => (
          <div key={`succ-${idx}`} className="relative group">
            <div className="absolute -left-6 top-0.5 w-5 h-5 rounded-full bg-rose-100 dark:bg-rose-950 border-2 border-rose-500 dark:border-rose-400 flex items-center justify-center shadow-xs">
              <ExternalLink className="w-2.5 h-2.5 text-rose-600 dark:text-rose-400" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap mb-0.5">
                <span className="text-[11px] font-mono font-bold text-rose-700 dark:text-rose-400">
                  {s.related_year ? `Year ${s.related_year}` : 'Newer Edition'}
                </span>
                <span className="px-1.5 py-0.2 rounded text-[10px] font-semibold bg-rose-50 dark:bg-rose-950 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
                  SUPERSEDED BY
                </span>
              </div>
              <h5 className="text-xs font-bold text-rose-800 dark:text-rose-200 flex items-center gap-1.5">
                {s.related_standard_raw}
                {onSelectStandard && (
                  <button
                    onClick={() => onSelectStandard(s.related_standard_raw)}
                    className="inline-flex items-center gap-0.5 text-[10px] text-blue-600 dark:text-blue-400 hover:underline cursor-pointer ml-1"
                    title="Inspect newer replacement standard"
                  >
                    Inspect <ExternalLink className="w-2.5 h-2.5" />
                  </button>
                )}
              </h5>
              <p className="text-[11px] text-rose-600/80 dark:text-rose-400/80 leading-relaxed mt-0.5">
                This edition has been superseded by {s.related_standard_raw}. Tender specifications must be updated to reference the newer edition.
              </p>
            </div>
          </div>
        ))}

      </div>
    </div>
  )
}

// ── Detail Panel ─────────────────────────────────────────────────────────────
interface DetailPanelProps {
  standardNumber: string
  onClose: () => void
  onSelectStandard?: (sn: string) => void
}

function DetailPanel({ standardNumber, onClose, onSelectStandard }: DetailPanelProps) {
  const { t } = useTranslation()
  const [detail, setDetail] = useState<StandardDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    getStandardDetail(standardNumber)
      .then(setDetail)
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false))
  }, [standardNumber])

  // Use the source_url stored in DB — it contains the exact BIS portal URL with encryptedId
  // Falls back to BIS search portal if not stored
  const bisUrl = detail?.source_url
    || (detail?.standard_number
      ? `https://standards.bis.gov.in/#searchKeyword=${encodeURIComponent(detail.standard_number)}`
      : 'https://standards.bis.gov.in/')

  return (
    <div className="h-full flex flex-col bg-white dark:bg-zinc-950 border-l border-slate-200 dark:border-zinc-800">
      {/* Top action header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-zinc-800 bg-slate-50/70 dark:bg-zinc-900/40 flex-shrink-0">
        <button
          onClick={onClose}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-700 dark:text-zinc-300 hover:text-slate-900 dark:hover:text-white bg-white dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 shadow-sm hover:shadow transition-all"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Grid View
        </button>

        <div className="flex items-center gap-2">
          {detail?.source_url ? (
            <a
              href={bisUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-800 hover:bg-blue-100 dark:hover:bg-blue-900/60 transition-colors"
            >
              {t('standards.viewFull')}
              <ExternalLink className="w-3 h-3" />
            </a>
          ) : (
            <a
              href={bisUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={clsx(
                "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                loading
                  ? "text-slate-400 bg-slate-100 dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 pointer-events-none opacity-60"
                  : "text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-800 hover:bg-blue-100 dark:hover:bg-blue-900/60"
              )}
            >
              {t('standards.viewFull')}
              <ExternalLink className="w-3 h-3" />
            </a>
          )}
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-zinc-200 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
            title="Close details"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Body content */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {loading && (
          <div className="flex flex-col items-center justify-center py-24 text-slate-400">
            <Loader2 className="w-7 h-7 animate-spin mb-3 text-blue-600" />
            <p className="text-xs font-medium">Fetching technical standard specification...</p>
          </div>
        )}

        {error && (
          <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 text-xs">
            <p className="font-semibold mb-1">Failed to load standard details</p>
            <p>{error}</p>
          </div>
        )}

        {!loading && detail && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.24 }}
            className="space-y-6"
          >
            {/* Header info */}
            <div>
              <div className="flex items-center gap-2 flex-wrap mb-2.5">
                <DeptBadge dept={detail.dept} />
                <StatusBadge status={detail.is_status_label} reaffirmationYear={detail.reaffirmation_year} />
                {detail.qco_ministry && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 ring-1 ring-amber-300 dark:ring-amber-700">
                    <ShieldCheck className="w-3 h-3 text-amber-500" />
                    Mandatory QCO — {detail.qco_ministry}
                  </span>
                )}
                {detail.active_licences > 0 && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 ring-1 ring-emerald-200 dark:ring-emerald-800">
                    <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                    {detail.active_licences} Active BIS Licences
                  </span>
                )}
              </div>

              <h2 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight mb-2">
                {detail.standard_number}
              </h2>
              <p className="text-sm font-medium text-slate-700 dark:text-zinc-300 leading-relaxed">
                {detail.title}
              </p>
            </div>

            {/* Regulatory Lifecycle Timeline */}
            <StandardLifecycleTimeline detail={detail} onSelectStandard={onSelectStandard} />

            {/* Metadata Table */}
            <div>
              <h4 className="text-[11px] font-bold text-slate-400 dark:text-zinc-500 uppercase tracking-wider mb-2.5">
                Technical Registry Metadata
              </h4>
              <div className="rounded-2xl border border-slate-200 dark:border-zinc-800 overflow-hidden bg-white dark:bg-zinc-900 divide-y divide-slate-100 dark:divide-zinc-800/80 shadow-sm">
                <MetaRow label="Standard No." value={detail.standard_number} />
                <MetaRow label="Department" value={detail.dept} />
                <MetaRow label="Publication Year" value={detail.year} />
                <MetaRow label="Status" value={detail.is_status_label} />
                <MetaRow label="Reaffirmed Year" value={detail.reaffirmation_year} />
                <MetaRow label="Published On" value={detail.published_on} />
                <MetaRow label="Technical Committee" value={detail.technical_committee} />
                <MetaRow label="Standard Type" value={detail.type_of_standard} />
                <MetaRow label="ICS Code" value={detail.ics_code} />
                <MetaRow label="Group Name" value={detail.group_name} />
                <MetaRow label="Sub-group" value={detail.sub_group} />
                <MetaRow label="Certification Scheme" value={detail.certification} />
                <MetaRow label="Total ISI Licences" value={detail.total_isi_licences} />
                <MetaRow label="QCO Ministry" value={detail.qco_ministry} />
                <MetaRow label="Total References" value={detail.references_count} />
              </div>
            </div>

            {/* Lineage / References */}
            {detail.lineage && detail.lineage.length > 0 && (
              <div>
                <h4 className="text-[11px] font-bold text-slate-400 dark:text-zinc-500 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                  <GitBranch className="w-3.5 h-3.5 text-blue-500" />
                  Standard Lineage & Relationships ({detail.lineage.length})
                </h4>
                <div className="space-y-2">
                  {detail.lineage.map((rec, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-xs"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300 uppercase tracking-wider">
                          {rec.relationship}
                        </span>
                        <span className="font-semibold text-slate-800 dark:text-zinc-200">
                          {rec.related_standard_raw}
                        </span>
                      </div>
                      {rec.related_year && (
                        <span className="text-[11px] text-slate-400 dark:text-zinc-500 font-medium">
                          {rec.related_year}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </div>
    </div>
  )
}

// ── Main Page Component ───────────────────────────────────────────────────────
export function StandardsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [selected, setSelected] = useState<string | null>(searchParams.get('is'))

  // Filter states
  const [search, setSearch] = useState('')
  const [selectedDept, setSelectedDept] = useState('ALL')
  const [selectedStatus, setSelectedStatus] = useState('ALL')
  const [selectedCommittee, setSelectedCommittee] = useState('ALL')
  const [qcoOnly, setQcoOnly] = useState(false)

  // Remote filter options
  const [allCommittees, setAllCommittees] = useState<string[]>([])

  // Data states
  const [standards, setStandards] = useState<StandardSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const LIMIT = 48
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Load committee options from backend once
  useEffect(() => {
    getFilterOptions()
      .then((data) => setAllCommittees(data.committees || []))
      .catch((e) => console.error('Error fetching filter options:', e))
  }, [])

  // Sync ?is= query parameter with selected state
  useEffect(() => {
    const isParam = searchParams.get('is')
    if (isParam && isParam !== selected) {
      setSelected(isParam)
    }
  }, [searchParams, selected])

  const handleSelect = useCallback((sn: string) => {
    setSelected(sn)
    setSearchParams({ is: sn }, { replace: true })
  }, [setSearchParams])

  const handleCloseDetail = useCallback(() => {
    setSelected(null)
    setSearchParams({}, { replace: true })
  }, [setSearchParams])

  // Fetch standards from API
  const loadStandards = useCallback(async (
    searchVal: string,
    deptVal: string,
    statusVal: string,
    committeeVal: string,
    qcoVal: boolean,
    newOffset: number,
    append = false
  ) => {
    setLoading(true)
    setError(null)
    try {
      const data = await listStandards({
        search: searchVal || undefined,
        dept: deptVal === 'ALL' ? undefined : deptVal,
        status: statusVal === 'ALL' ? undefined : statusVal,
        committee: committeeVal === 'ALL' ? undefined : committeeVal,
        qco_only: qcoVal,
        limit: LIMIT,
        offset: newOffset,
      })
      setStandards((prev) => (append ? [...prev, ...data] : data))
      setHasMore(data.length === LIMIT)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  // Initial and reactive load on search / filter changes
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setOffset(0)
      loadStandards(search, selectedDept, selectedStatus, selectedCommittee, qcoOnly, 0, false)
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [search, selectedDept, selectedStatus, selectedCommittee, qcoOnly, loadStandards])

  const loadMore = () => {
    const next = offset + LIMIT
    setOffset(next)
    loadStandards(search, selectedDept, selectedStatus, selectedCommittee, qcoOnly, next, true)
  }

  // Filter committees based on active department
  const filteredCommittees = useMemo(() => {
    if (selectedDept === 'ALL') return allCommittees
    return allCommittees.filter((c) => c.startsWith(selectedDept))
  }, [allCommittees, selectedDept])

  const isFiltered = search !== '' || selectedDept !== 'ALL' || selectedStatus !== 'ALL' || selectedCommittee !== 'ALL' || qcoOnly

  const clearAllFilters = () => {
    setSearch('')
    setSelectedDept('ALL')
    setSelectedStatus('ALL')
    setSelectedCommittee('ALL')
    setQcoOnly(false)
  }

  return (
    <Shell botContext="standards" botQueryContext={selected ?? undefined}>
      <div className="flex flex-col h-full overflow-hidden bg-slate-50/50 dark:bg-zinc-950">

        {/* ── FILTER & SEARCH BAR HEADER ── */}
        <header className="px-6 py-4 bg-white dark:bg-zinc-900 border-b border-slate-200 dark:border-zinc-800 shadow-sm flex-shrink-0 space-y-3">
          {/* Row 1: Search & QCO Toggle */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
            {/* Search Input */}
            <div className="relative flex-1 max-w-xl">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search standard number (e.g. IS 694), title, or keywords..."
                className={clsx(
                  'w-full pl-10 pr-9 py-2 rounded-xl text-xs sm:text-sm font-medium transition-all outline-none',
                  'bg-slate-50 dark:bg-zinc-800/80 border border-slate-200 dark:border-zinc-700',
                  'text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-zinc-500',
                  'focus:border-blue-500 focus:bg-white dark:focus:bg-zinc-900 focus:ring-2 focus:ring-blue-500/10'
                )}
              />
              {search && (
                <button
                  onClick={() => setSearch('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-zinc-200"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* QCO Mandatory Toggle & Clear */}
            <div className="flex items-center gap-3 self-end sm:self-center">
              <button
                onClick={() => setQcoOnly((q) => !q)}
                className={clsx(
                  'inline-flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all border',
                  qcoOnly
                    ? 'bg-amber-500 text-white border-amber-600 shadow-sm'
                    : 'bg-slate-50 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 border-slate-200 dark:border-zinc-700 hover:border-slate-300'
                )}
              >
                <ShieldCheck className={clsx('w-3.5 h-3.5', qcoOnly ? 'text-white' : 'text-amber-500')} />
                Mandatory QCO Only
              </button>

              {isFiltered && (
                <button
                  onClick={clearAllFilters}
                  className="text-xs font-semibold text-rose-600 dark:text-rose-400 hover:underline px-2 py-1"
                >
                  Reset Filters
                </button>
              )}
            </div>
          </div>

          {/* Row 2: Department Tabs & Dropdowns */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-1 border-t border-slate-100 dark:border-zinc-800/80">
            {/* Department Filter Tabs (ETD, CED, MTD) */}
            <div className="flex items-center gap-1 p-1 bg-slate-100 dark:bg-zinc-800/80 rounded-xl">
              {DEPARTMENTS.map((dept) => (
                <button
                  key={dept.code}
                  onClick={() => {
                    setSelectedDept(dept.code)
                    setSelectedCommittee('ALL') // Reset committee if it doesn't match new dept
                  }}
                  className={clsx(
                    'px-3 py-1.5 rounded-lg text-xs font-bold transition-all',
                    selectedDept === dept.code
                      ? 'bg-white dark:bg-zinc-700 text-blue-600 dark:text-blue-400 shadow-sm'
                      : 'text-slate-600 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-white'
                  )}
                  title={dept.fullName}
                >
                  {dept.label}
                </button>
              ))}
            </div>

            {/* Dropdowns: Status & Committees */}
            <div className="flex items-center gap-2.5 flex-wrap">
              {/* Status Select */}
              <div className="relative">
                <select
                  value={selectedStatus}
                  onChange={(e) => setSelectedStatus(e.target.value)}
                  className={clsx(
                    'appearance-none pl-3 pr-8 py-1.5 rounded-xl text-xs font-medium cursor-pointer transition-all outline-none border',
                    'bg-slate-50 dark:bg-zinc-800 border-slate-200 dark:border-zinc-700 text-slate-800 dark:text-zinc-200',
                    'hover:border-slate-300 dark:hover:border-zinc-600 focus:border-blue-500'
                  )}
                >
                  {STATUS_OPTIONS.map((st) => (
                    <option key={st.value} value={st.value}>
                      {st.label}
                    </option>
                  ))}
                </select>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>

              {/* Committee Select */}
              <div className="relative max-w-xs">
                <select
                  value={selectedCommittee}
                  onChange={(e) => setSelectedCommittee(e.target.value)}
                  className={clsx(
                    'appearance-none pl-3 pr-8 py-1.5 rounded-xl text-xs font-medium cursor-pointer transition-all outline-none border truncate max-w-[240px]',
                    'bg-slate-50 dark:bg-zinc-800 border-slate-200 dark:border-zinc-700 text-slate-800 dark:text-zinc-200',
                    'hover:border-slate-300 dark:hover:border-zinc-600 focus:border-blue-500'
                  )}
                >
                  <option value="ALL">All Committees ({filteredCommittees.length})</option>
                  {filteredCommittees.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>
            </div>
          </div>
        </header>

        {/* ── CONTENT AREA: FULL-SCREEN GRID OR SPLIT VIEW ── */}
        <div className="flex-1 overflow-hidden relative">
          <AnimatePresence mode="wait">
            {!selected ? (
              /* ── FULL SCREEN 3-IN-A-ROW GRID VIEW ── */
              <motion.div
                key="grid-view"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
                className="h-full overflow-y-auto px-6 py-6"
              >
                {/* Status Bar */}
                <div className="flex items-center justify-between mb-5">
                  <p className="text-xs font-semibold text-slate-500 dark:text-zinc-400">
                    Showing <span className="text-slate-900 dark:text-white font-bold">{standards.length}</span> indexed standards
                    {selectedDept !== 'ALL' && ` in ${selectedDept}`}
                    {selectedStatus !== 'ALL' && ` (${selectedStatus})`}
                  </p>
                </div>

                {/* Error Banner */}
                {error && (
                  <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 text-xs mb-6">
                    <p className="font-semibold mb-1">Failed to query BIS Registry</p>
                    <p>{error}</p>
                  </div>
                )}

                {/* Initial Loading Skeletons */}
                {loading && standards.length === 0 && (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                    {[1, 2, 3, 4, 5, 6].map((i) => (
                      <div key={i} className="h-48 rounded-2xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 animate-pulse p-5" />
                    ))}
                  </div>
                )}

                {/* 3 in a Row Grid */}
                {!error && standards.length > 0 && (
                  <motion.div
                    initial="hidden"
                    animate="show"
                    variants={{
                      hidden: {},
                      show: { transition: { staggerChildren: 0.04 } }
                    }}
                    className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"
                  >
                    {standards.map((s) => (
                      <StandardCard
                        key={s.id}
                        standard={s}
                        onClick={() => handleSelect(s.standard_number)}
                      />
                    ))}
                  </motion.div>
                )}

                {/* Empty State */}
                {!loading && !error && standards.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-20 text-center">
                    <div className="w-14 h-14 rounded-2xl bg-slate-100 dark:bg-zinc-800 flex items-center justify-center mb-3">
                      <Layers className="w-6 h-6 text-slate-400" />
                    </div>
                    <p className="text-sm font-semibold text-slate-800 dark:text-zinc-200 mb-1">No Indian Standards Found</p>
                    <p className="text-xs text-slate-500 dark:text-zinc-400 max-w-sm mb-4">
                      Try broadening your search keywords or resetting the department and status filters.
                    </p>
                    <button
                      onClick={clearAllFilters}
                      className="px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                    >
                      Clear Filters
                    </button>
                  </div>
                )}

                {/* Load More Button */}
                {hasMore && !loading && standards.length > 0 && (
                  <div className="flex justify-center pt-8 pb-4">
                    <button
                      onClick={loadMore}
                      className="px-6 py-2.5 rounded-full text-xs font-bold text-blue-600 dark:text-blue-400 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700 hover:bg-blue-50 dark:hover:bg-blue-950/40 shadow-sm transition-all"
                    >
                      Load More Standards
                    </button>
                  </div>
                )}

                {loading && standards.length > 0 && (
                  <div className="flex justify-center py-6">
                    <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
                  </div>
                )}
              </motion.div>
            ) : (
              /* ── SPLIT VIEW (LEFT: COMPACT LIST, RIGHT: DETAIL WITH LEFT-TO-RIGHT EFFECT) ── */
              <motion.div
                key="split-view"
                initial={{ opacity: 0, x: 40 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 40 }}
                transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
                className="flex h-full overflow-hidden"
              >
                {/* Left Side: Compact standards list */}
                <div className="w-80 lg:w-96 flex-shrink-0 border-r border-slate-200 dark:border-zinc-800 flex flex-col h-full bg-white dark:bg-zinc-900/60 overflow-hidden">
                  <div className="p-3 border-b border-slate-200 dark:border-zinc-800 flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-700 dark:text-zinc-300">
                      Standards Catalog ({standards.length})
                    </span>
                    <button
                      onClick={handleCloseDetail}
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      <LayoutGrid className="w-3 h-3" />
                      Back to 3-Col
                    </button>
                  </div>

                  <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
                    {standards.map((s) => {
                      const isItemActive = selected === s.standard_number
                      return (
                        <button
                          key={s.id}
                          onClick={() => handleSelect(s.standard_number)}
                          className={clsx(
                            'w-full text-left rounded-xl p-3 transition-all',
                            isItemActive
                              ? 'bg-blue-50 dark:bg-blue-950/60 border border-blue-300 dark:border-blue-700 shadow-sm'
                              : 'bg-white dark:bg-zinc-900 border border-slate-100 dark:border-zinc-800 hover:border-slate-300 dark:hover:border-zinc-700'
                          )}
                        >
                          <div className="flex items-center justify-between gap-1 mb-1">
                            <span className={clsx('text-xs font-bold', isItemActive ? 'text-blue-700 dark:text-blue-300' : 'text-slate-900 dark:text-white')}>
                              {s.standard_number}
                            </span>
                            <StatusBadge status={s.is_status_label} reaffirmationYear={s.reaffirmation_year} />
                          </div>
                          <p className="text-[11px] text-slate-600 dark:text-zinc-400 line-clamp-2 leading-snug mb-1 font-normal">
                            {s.title}
                          </p>
                          <div className="flex items-center gap-2 text-[10px] text-slate-400">
                            {s.dept && <DeptBadge dept={s.dept} />}
                            {s.active_licences > 0 && <span>{s.active_licences} licences</span>}
                          </div>
                        </button>
                      )
                    })}
                  </div>
                </div>

                {/* Right Side: Detailed standard spec with left-to-right entrance */}
                <motion.div
                  key={selected}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
                  className="flex-1 h-full overflow-hidden"
                >
                  <DetailPanel standardNumber={selected} onClose={handleCloseDetail} onSelectStandard={handleSelect} />
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

      </div>
    </Shell>
  )
}

import { motion } from 'framer-motion'
import { ExternalLink, AlertTriangle, ShieldCheck, AlertCircle } from 'lucide-react'
import { useTranslation } from '@/i18n/I18nContext'
import type { PrimaryCandidate } from '@/lib/api'
import { clsx } from 'clsx'

const ITEM_VARIANT = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] as const } },
}

interface ResultCardProps {
  result: PrimaryCandidate
  onViewIS: () => void
  onViewSuperseded?: (newer: string) => void
}

function ConfidenceBadge({ score }: { score: number }) {
  return (
    <span className={clsx(
      'inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold tabular-nums',
      score >= 80 ? 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400 ring-1 ring-emerald-200 dark:ring-emerald-800' :
      score >= 50 ? 'bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-400 ring-1 ring-amber-200 dark:ring-amber-800' :
                   'bg-rose-50 dark:bg-rose-950/50 text-rose-700 dark:text-rose-400 ring-1 ring-rose-200 dark:ring-rose-800'
    )}>
      {score.toFixed(1)}% match
    </span>
  )
}

function StatusBadge({ status, supersededBy }: { status: string; supersededBy?: string | null }) {
  if (supersededBy) {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 ring-1 ring-rose-300 dark:ring-rose-800">
        <AlertTriangle className="w-3 h-3 text-rose-600 dark:text-rose-400" />
        Superseded by {supersededBy}
      </span>
    )
  }

  const isCurrent = status.toLowerCase() === 'current' || status.toLowerCase() === 'published' || status.toLowerCase() === 'active'
  const isReaffirmed = status.toLowerCase().includes('reaffirm')

  return (
    <span className={clsx(
      'inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium',
      isCurrent
        ? 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400 ring-1 ring-emerald-200 dark:ring-emerald-800'
        : isReaffirmed
        ? 'bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-400 ring-1 ring-blue-200 dark:ring-blue-800'
        : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 ring-1 ring-zinc-300 dark:ring-zinc-700'
    )}>
      {status || 'Current'}
    </span>
  )
}

export function ResultCard({ result, onViewIS, onViewSuperseded }: ResultCardProps) {
  const { t } = useTranslation()
  const cert = result.certification

  return (
    <motion.div
      variants={ITEM_VARIANT}
      className={clsx(
        'rounded-2xl border bg-white dark:bg-zinc-900 p-4 sm:p-5',
        'border-slate-200 dark:border-zinc-800',
        'hover:border-slate-300 dark:hover:border-zinc-700',
        'hover:shadow-sm transition-all'
      )}
    >
      {/* Top row */}
      <div className="flex items-start justify-between gap-3 mb-2.5">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-base font-bold text-slate-900 dark:text-white tracking-tight">
            {result.standard_number}
          </span>
          <StatusBadge status={result.is_status_label} supersededBy={result.superseded_by} />
          {result.superseded_by && onViewSuperseded && (
            <button
              onClick={() => onViewSuperseded(result.superseded_by!)}
              className="text-[11px] text-blue-600 dark:text-blue-400 hover:underline font-medium"
            >
              (Inspect Newer Standard →)
            </button>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[11px] text-slate-400 dark:text-zinc-500 font-medium">
            {t('recommend.confidence')}
          </span>
          <ConfidenceBadge score={result.confidence} />
        </div>
      </div>

      {/* Title */}
      <p className="text-sm font-semibold text-slate-800 dark:text-zinc-200 mb-2 leading-snug">
        {result.title}
      </p>

      {/* Rule 1.5 Conflict Warning if material mismatch detected */}
      {result.conflict_warning && (
        <div className="mb-3 px-3 py-2 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <p className="text-xs text-amber-800 dark:text-amber-300 leading-relaxed font-medium">
            {result.conflict_warning}
          </p>
        </div>
      )}

      {/* Grounded Why Text */}
      <p className="text-xs text-slate-600 dark:text-zinc-400 leading-relaxed mb-4">
        <span className="font-semibold text-slate-700 dark:text-zinc-300">{t('recommend.why')}: </span>
        {result.why}
      </p>

      {/* Bottom row: Rule 2 Certification Gating & Action Buttons */}
      <div className="flex items-center justify-between flex-wrap gap-2 pt-2 border-t border-slate-100 dark:border-zinc-800/80">
        {/* Rule 2 Certification Info */}
        <div className="flex items-center gap-2 flex-wrap">
          {cert.verified ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
              <span>{cert.value || 'Mandatory ISI Certification'}</span>
              {cert.qco_ministry && (
                <span className="text-[10px] text-emerald-600/80 dark:text-emerald-400/80">({cert.qco_ministry})</span>
              )}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
              <span>{cert.value || 'Certification status not verified — check BIS portal'}</span>
            </span>
          )}

          {cert.source_url && (
            <a
              href={cert.source_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium text-slate-600 dark:text-zinc-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
            >
              <span>BIS Manakonline</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>

        <button
          onClick={onViewIS}
          className={clsx(
            'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold shrink-0 transition-colors',
            'border border-blue-200 dark:border-blue-800',
            'bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-400',
            'hover:bg-blue-100 dark:hover:bg-blue-950 hover:border-blue-300 dark:hover:border-blue-700'
          )}
        >
          {t('recommend.viewFull')}
          <ExternalLink className="w-3.5 h-3.5" />
        </button>
      </div>
    </motion.div>
  )
}

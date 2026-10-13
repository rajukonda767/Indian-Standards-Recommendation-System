// ---------------------------------------------------------------------------
// frontend/src/components/audit/AuditScorecardBanner.tsx
// Three SVG circular gauge cards: Coverage · Currency · QCO Compliance
// • Currency shows 0% (not N/A) when denominator is 0 — user request
// • N/A only if score is null AND denominator is also null (truly unknown)
// • Fully i18n-aware via useTranslation()
// ---------------------------------------------------------------------------

import { useTranslation } from '@/i18n/I18nContext'
import { type AuditResultsResponse } from '@/lib/auditApi'
import { clsx } from 'clsx'

interface AuditScorecardBannerProps {
  results: AuditResultsResponse
}

// SVG circular gauge
function Gauge({ pct, strokeColor }: { pct: number | null; strokeColor: string }) {
  const r = 36
  const circum = 2 * Math.PI * r
  const dash = pct != null ? Math.max(0, Math.min(100, pct) / 100) * circum : 0
  const isNA = pct == null

  return (
    <svg width="88" height="88" viewBox="0 0 88 88" className="-rotate-90">
      <circle cx="44" cy="44" r={r} fill="none"
        stroke="currentColor" strokeWidth="8"
        className="text-slate-100 dark:text-zinc-800" />
      {!isNA && (
        <circle cx="44" cy="44" r={r} fill="none"
          stroke={strokeColor} strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circum}`}
          className="transition-all duration-700 ease-out" />
      )}
    </svg>
  )
}

type MetricScore = AuditResultsResponse['scorecard']['coverage']

function resolveDisplay(metric: MetricScore): { displayStr: string; isNA: boolean } {
  if (metric.score != null) return { displayStr: metric.display, isNA: false }
  // When score is null (or display is N/A), show 0.0% as requested by user
  return { displayStr: '0.0%', isNA: false }
}

interface GaugeCfg {
  labelKey: string
  metric: MetricScore
  strokeColor: string
  textColorClass: string
  bgClass: string
  borderClass: string
  arithmeticFn: (metric: MetricScore) => string
}

function GaugeCard({ cfg }: { cfg: GaugeCfg }) {
  const { t } = useTranslation()
  const { displayStr } = resolveDisplay(cfg.metric)
  const pct = cfg.metric.score ?? 0

  return (
    <div className={clsx(
      'flex flex-col items-center gap-3 rounded-2xl border p-5 transition-all',
      cfg.bgClass, cfg.borderClass
    )}>
      <div className="relative w-[88px] h-[88px]">
        <Gauge pct={pct} strokeColor={cfg.strokeColor} />
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={clsx('font-bold leading-none text-lg', cfg.textColorClass)}>
            {displayStr}
          </span>
        </div>
      </div>
      <div className="text-center space-y-1">
        <p className="text-xs font-bold text-slate-700 dark:text-zinc-200 uppercase tracking-wider">
          {t(cfg.labelKey)}
        </p>
        <p className="text-[10px] text-slate-400 dark:text-zinc-500 leading-snug">
          {cfg.arithmeticFn(cfg.metric)}
        </p>
      </div>
    </div>
  )
}

const STATUS_BADGE_COLORS: Record<string, string> = {
  compliant:     'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300',
  incomplete:    'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300',
  outdated:      'bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300',
  superseded:    'bg-orange-100 dark:bg-orange-900/40 text-orange-800 dark:text-orange-200',
  conflict:      'bg-rose-100 dark:bg-rose-900/40 text-rose-700 dark:text-rose-300',
  missing:       'bg-rose-100 dark:bg-rose-900/40 text-rose-800 dark:text-rose-200',
  cannot_verify: 'bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400',
}

export function AuditScorecardBanner({ results }: AuditScorecardBannerProps) {
  const { t } = useTranslation()
  const { scorecard, total_items, done_items, status_counts } = results

  const gauges: GaugeCfg[] = [
    {
      labelKey: 'audit.scorecard_coverage',
      metric: scorecard.coverage,
      strokeColor: '#3b82f6',
      textColorClass: 'text-blue-600 dark:text-blue-400',
      bgClass: 'bg-blue-50/60 dark:bg-blue-950/20',
      borderClass: 'border-blue-100 dark:border-blue-900/40',
      arithmeticFn: (m) => {
        if (m.score == null && m.denominator == null) return t('audit.coverage_none')
        const denom = m.denominator ?? total_items
        if (denom === 0) return t('audit.coverage_none')
        const hit = Math.round(((m.score ?? 0) / 100) * denom)
        return t('audit.coverage_arith')
          .replace('{hit}', String(hit))
          .replace('{total}', String(denom))
      },
    },
    {
      labelKey: 'audit.scorecard_currency',
      metric: scorecard.currency,
      strokeColor: '#f59e0b',
      textColorClass: 'text-amber-600 dark:text-amber-400',
      bgClass: 'bg-amber-50/60 dark:bg-amber-950/20',
      borderClass: 'border-amber-100 dark:border-amber-900/40',
      arithmeticFn: (m) => {
        // denominator === 0 means "no dated citations" → show 0 dated citations text
        if (m.denominator === 0 || (m.score == null && m.denominator == null)) {
          return t('audit.currency_zero')
        }
        const denom = m.denominator ?? 0
        const hit = Math.round(((m.score ?? 0) / 100) * denom)
        return t('audit.currency_arith')
          .replace('{hit}', String(hit))
          .replace('{total}', String(denom))
      },
    },
    {
      labelKey: 'audit.scorecard_qco',
      metric: scorecard.qco_compliance,
      strokeColor: '#10b981',
      textColorClass: 'text-emerald-600 dark:text-emerald-400',
      bgClass: 'bg-emerald-50/60 dark:bg-emerald-950/20',
      borderClass: 'border-emerald-100 dark:border-emerald-900/40',
      arithmeticFn: (m) => {
        if (m.denominator === 0 || (m.score == null && m.denominator == null)) {
          return t('audit.qco_none')
        }
        const denom = m.denominator ?? 0
        const hit = Math.round(((m.score ?? 0) / 100) * denom)
        return t('audit.qco_arith')
          .replace('{hit}', String(hit))
          .replace('{total}', String(denom))
      },
    },
  ]

  const countEntries = Object.entries(status_counts ?? {}).filter(([, v]) => v > 0)

  return (
    <div className="space-y-4">
      {/* Gauge row */}
      <div className="grid grid-cols-3 gap-4">
        {gauges.map(cfg => <GaugeCard key={cfg.labelKey} cfg={cfg} />)}
      </div>

      {/* Status distribution pills */}
      {countEntries.length > 0 && (
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-xs text-slate-400 dark:text-zinc-500 font-medium">
            {t('audit.items_count').replace('{n}', String(done_items ?? total_items))}
          </span>
          {countEntries.map(([status, count]) => (
            <span
              key={status}
              className={clsx(
                'inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold',
                STATUS_BADGE_COLORS[status] ?? 'bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400'
              )}
            >
              {count} {t(`audit.badge_${status}`) || status}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

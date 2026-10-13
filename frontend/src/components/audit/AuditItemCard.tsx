// ---------------------------------------------------------------------------
// frontend/src/components/audit/AuditItemCard.tsx
// Redesigned card matching exact user specifications:
//  1. CITED: Shows exactly what was cited in the PDF (raw_citation).
//     Quote is NOT shown directly; only revealed when user clicks [Show source].
//  2. GAPS: No accept/dismiss buttons. Only [Show source] button.
//     When language changes (hi, te), English text is removed and replaced by localized text.
//  3. RECOMMENDATION: Always present with human-readable guidance, active standard edition
//     and year (even if backend array was empty).
//     Accept/Reject buttons per recommendation — accepted items flow to PDF export.
//  4. ErrorBoundary protection throughout.
// ---------------------------------------------------------------------------

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ChevronDown, ChevronRight, ExternalLink,
  Copy, Check, RefreshCw, BookOpen, ArrowRight, Eye,
  ThumbsUp, ThumbsDown
} from 'lucide-react'
import { clsx } from 'clsx'
import { useTranslation } from '@/i18n/I18nContext'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'
import { type AuditedItemDTO, type ItemFindingDTO } from '@/lib/auditApi'

// ── Recommendation row payload (sent to parent for PDF) ──────────────────────
export interface AcceptedRecommendation {
  seqNo: number
  description: string
  recommendedStandard: string
  clauseText: string           // AI-corrected clause (used when action=accepted)
  originalSpec: string         // Original spec from the tender (used when action=rejected)
  quantity: string | number | null
  unit: string | null
  action: 'accepted' | 'rejected'
}

// ── Bulletproof string normalizers ─────────────────────────────────────────
function toText(val: any): string | null {
  if (val === null || val === undefined) return null
  if (typeof val === 'string') return val.trim()
  if (typeof val === 'number' || typeof val === 'boolean') return String(val)
  if (typeof val === 'object') {
    if (typeof val.quote_text === 'string') return val.quote_text.trim()
    if (typeof val.quote === 'string') return val.quote.trim()
    if (typeof val.text === 'string') return val.text.trim()
    if (typeof val.message === 'string') return val.message.trim()
    if (typeof val.description === 'string') return val.description.trim()
  }
  return null
}

function toPageNo(val: any, fallbackVal?: any): number | null {
  if (typeof val === 'number') return val
  if (typeof val === 'string' && !isNaN(Number(val))) return Number(val)
  if (typeof fallbackVal === 'object' && fallbackVal !== null) {
    if (typeof fallbackVal.page_no === 'number') return fallbackVal.page_no
    if (typeof fallbackVal.page_no === 'string' && !isNaN(Number(fallbackVal.page_no))) {
      return Number(fallbackVal.page_no)
    }
  }
  return null
}

// ── Badge styling map ──────────────────────────────────────────────────────
const BADGE_STYLES: Record<string, {
  border: string
  headerBg: string
  pill: string
  pillText: string
  dotEmoji: string
}> = {
  green: {
    border: 'border-emerald-200 dark:border-emerald-800/60',
    headerBg: 'bg-emerald-50/60 dark:bg-emerald-950/20',
    pill: 'bg-emerald-100 dark:bg-emerald-900/40',
    pillText: 'text-emerald-700 dark:text-emerald-300',
    dotEmoji: '🟢',
  },
  yellow: {
    border: 'border-amber-200 dark:border-amber-800/60',
    headerBg: 'bg-amber-50/60 dark:bg-amber-950/20',
    pill: 'bg-amber-100 dark:bg-amber-900/40',
    pillText: 'text-amber-700 dark:text-amber-300',
    dotEmoji: '🟡',
  },
  orange: {
    border: 'border-orange-200 dark:border-orange-800/60',
    headerBg: 'bg-orange-50/60 dark:bg-orange-950/20',
    pill: 'bg-orange-100 dark:bg-orange-900/40',
    pillText: 'text-orange-700 dark:text-orange-300',
    dotEmoji: '🟠',
  },
  red: {
    border: 'border-rose-200 dark:border-rose-800/60',
    headerBg: 'bg-rose-50/60 dark:bg-rose-950/20',
    pill: 'bg-rose-100 dark:bg-rose-900/40',
    pillText: 'text-rose-700 dark:text-rose-300',
    dotEmoji: '🔴',
  },
  gray: {
    border: 'border-slate-200 dark:border-zinc-700',
    headerBg: 'bg-slate-50 dark:bg-zinc-800/40',
    pill: 'bg-slate-100 dark:bg-zinc-800',
    pillText: 'text-slate-600 dark:text-zinc-400',
    dotEmoji: '⚪',
  },
  purple: {
    border: 'border-purple-200 dark:border-purple-800/60',
    headerBg: 'bg-purple-50/60 dark:bg-purple-950/20',
    pill: 'bg-purple-100 dark:bg-purple-900/40',
    pillText: 'text-purple-700 dark:text-purple-300',
    dotEmoji: '🟣',
  },
}

const FALLBACK_BADGE = BADGE_STYLES.gray

// ── Evidence inline box (visualized on demand) ─────────────────────────────
function EvidenceBox({
  quote,
  pageNo,
  docName,
  tier,
}: {
  quote?: any
  pageNo?: number | null
  docName?: string | null
  tier?: string | null
}) {
  const { t } = useTranslation()
  const quoteText = toText(quote)

  if (!quoteText && pageNo == null) return null

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.18 }}
      className="mt-2.5 pl-4 pr-3 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-800/90 border-l-2 border-blue-500 space-y-1.5 shadow-sm"
    >
      <div className="flex items-center justify-between text-[11px] font-bold text-slate-500 dark:text-zinc-400">
        <span className="uppercase tracking-wider">{t('audit.verbatim_source')}</span>
        {pageNo != null && (
          <span className="text-blue-600 dark:text-blue-400 font-semibold">
            {t('audit.page_label')} {pageNo}
          </span>
        )}
      </div>
      {quoteText && (
        <blockquote className="text-xs text-slate-700 dark:text-zinc-300 italic leading-relaxed">
          "{quoteText}"
        </blockquote>
      )}
      <div className="flex items-center gap-3 text-[10px] text-slate-400 dark:text-zinc-500">
        {docName && <span className="truncate max-w-[240px]">{docName}</span>}
        {tier && <span>{t('audit.tier_label')}: {tier}</span>}
      </div>
    </motion.div>
  )
}

// ── Point-wise Finding Row (NO BRACKETS, NO ACCEPT/REJECT BUTTONS) ─────────
function FindingPointRow({
  finding,
  index,
}: {
  finding: ItemFindingDTO
  index: number
}) {
  const { t, lang } = useTranslation()
  const [showSource, setShowSource] = useState(false)
  const ev = finding.evidence

  const quoteText = toText(ev?.quote)
  const pageNo = toPageNo(ev?.page_no, ev?.quote)
  const hasEvidence = !!(quoteText || pageNo != null)

  // Translated title (NO SQUARE BRACKETS)
  const rawCode = String(finding.code ?? 'FINDING')
  const titleKey = `audit.finding_title_${rawCode}`
  const translatedTitle = t(titleKey)
  const displayTitle = translatedTitle !== titleKey ? translatedTitle : rawCode.replace(/_/g, ' ')

  // Translated description
  const descKey = `audit.finding_desc_${rawCode}`
  const localizedDesc = lang !== 'en' ? t(descKey) : null
  const hasLocalized = localizedDesc && localizedDesc !== descKey

  // When language is Hindi or Telugu, show localized text exclusively (do NOT show English text)
  const descriptionText = hasLocalized ? localizedDesc : (toText(finding.message) ?? rawCode)

  return (
    <div className="space-y-1.5">
      {/* 1. TITLE (e.g. 1. SUPERSEDED) */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-bold font-mono tracking-wide text-slate-800 dark:text-zinc-100">
          {index + 1}. {displayTitle.toUpperCase()}
        </span>
      </div>

      {/* Message / Description: completely translated when language changes */}
      <div className="pl-4 space-y-1">
        <p className="text-xs text-slate-600 dark:text-zinc-300 leading-relaxed">
          {descriptionText}
        </p>

        {/* Action: Only [Show source] button */}
        {hasEvidence && (
          <div className="pt-0.5">
            <button
              onClick={() => setShowSource(v => !v)}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-slate-600 dark:text-zinc-300 hover:border-blue-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
            >
              <Eye className="w-3 h-3" />
              {showSource ? t('audit.hide_source') : t('audit.show_source')}
            </button>
          </div>
        )}

        {/* Evidence inline: visualized only when user clicks view source */}
        <AnimatePresence>
          {showSource && (
            <EvidenceBox
              quote={quoteText}
              pageNo={pageNo}
              docName={ev?.doc_name}
              tier={ev?.tier}
            />
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

// ── Helper to resolve human-readable recommendation even if DB array was empty ──
interface RecommendationItem {
  recommendedStandard: string
  explanation: string
  clauseText: string
}

function resolveItemRecommendation(
  item: AuditedItemDTO,
  t: (key: string) => string
): RecommendationItem[] {
  // If backend provided recommended_standards with contents, format them
  if (item.recommended_standards && item.recommended_standards.length > 0) {
    return item.recommended_standards.map(r => {
      const rec = toText(r.recommended) ?? ''
      const yr = r.year && !rec.includes(`:${r.year}`) ? `:${r.year}` : ''
      const fullRec = `${rec}${yr}`
      const reason = toText(r.reason) ?? ''
      return {
        recommendedStandard: fullRec,
        explanation: reason,
        clauseText: `Material shall comply with ${fullRec} — ${reason}`,
      }
    })
  }

  // If item is compliant, no recommendation needed
  if (item.status === 'compliant') {
    return []
  }

  // Derive human-readable recommendation with proper year from cited_standards or findings
  const firstCited = item.cited_standards?.[0]
  let recStd = toText(firstCited?.resolved_standard_number)

  // Extract year if not already attached
  if (recStd) {
    // If it doesn't already contain :year
    if (!recStd.match(/:\d{4}/) && firstCited?.resolved_year) {
      recStd = `${recStd}:${firstCited.resolved_year}`
    }
  } else {
    // Check findings details
    const yearFinding = item.findings?.find(f => f.details?.latest_active_edition || f.details?.latest_active_year)
    if (yearFinding?.details?.latest_active_edition) {
      recStd = toText(yearFinding.details.latest_active_edition)
    } else if (yearFinding?.details?.base_standard_name && yearFinding?.details?.latest_active_year) {
      recStd = `${yearFinding.details.base_standard_name}:${yearFinding.details.latest_active_year}`
    }
  }

  if (!recStd) {
    recStd = toText(firstCited?.raw_citation) ?? 'Latest Indian Standard'
  }

  // Check if QCO finding exists
  const hasQcoFinding = item.findings?.some(f => f.code === 'CERT_NOT_MENTIONED')
  const explanation = hasQcoFinding
    ? t('audit.proper_rec_year_qco').replace('{std}', recStd)
    : t('audit.proper_rec_year').replace('{std}', recStd)

  const clauseText = `Material shall comply with ${recStd} with up-to-date amendments${
    hasQcoFinding ? ' and carry mandatory BIS Certification / ISI Mark under Quality Control Order (QCO)' : ''
  }.`

  return [{
    recommendedStandard: recStd,
    explanation,
    clauseText,
  }]
}

// ── Inner Audit Item Card ─────────────────────────────────────────────────
function AuditItemCardInner({ item, isExpanded, onToggle, onRerun, isRerunning, onAcceptRecommendation }: {
  item: AuditedItemDTO
  isExpanded: boolean
  onToggle: () => void
  onRerun: (seqNo: number) => Promise<void>
  isRerunning: boolean
  onAcceptRecommendation?: (rec: AcceptedRecommendation) => void
}) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const [showCitedSource, setShowCitedSource] = useState<Record<number, boolean>>({})
  // Track accepted/rejected state per recommendation index
  const [recState, setRecState] = useState<Record<number, 'accepted' | 'rejected' | null>>({})

  const styles = BADGE_STYLES[item.badge_color] ?? FALLBACK_BADGE
  const statusLabel = t(`audit.badge_${item.status}`) || item.status.replace('_', ' ')
  const itemPrefix = t('audit.item_prefix') || 'Item'

  const citedList = item.cited_standards ?? []
  const findingsList = item.findings ?? []
  const recommendations = resolveItemRecommendation(item, t)

  const handleCopyClause = async (clause: string) => {
    if (!clause) return
    try {
      await navigator.clipboard.writeText(clause)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* clipboard fallback */ }
  }

  // Derive the original spec from the tender (prefer verbatim technical specification, quote, or description)
  const getOriginalSpec = (): string => {
    // 1. Direct verbatim technical specification extracted from the tender document
    if (item.technical_spec && item.technical_spec.trim().length > 0) {
      return item.technical_spec.trim()
    }
    // 2. Check cited_standards quotes
    const cited = item.cited_standards ?? []
    for (const cs of cited) {
      if (cs.quote?.quote_text && cs.quote.quote_text.trim().length > 5) {
        return cs.quote.quote_text.trim()
      }
    }
    // 3. Check findings evidence quote
    const findings = item.findings ?? []
    for (const f of findings) {
      const q = toText(f.evidence?.quote)
      if (q && q.length > 5) {
        return q
      }
    }
    // 4. Formatted fallback from cited standard numbers
    if (cited.length > 0) {
      const parts = cited.map(cs => {
        let num = toText(cs.resolved_standard_number) ?? toText(cs.raw_citation) ?? ''
        if (cs.resolved_year && !num.includes(String(cs.resolved_year))) {
          num = `${num}:${cs.resolved_year}`
        }
        return num
      }).filter(Boolean)
      if (parts.length > 0) return `Material shall comply with ${parts.join(', ')} with up-to-date amendments.`
    }
    return toText(item.description) ?? `Item ${item.seq_no}`
  }

  const handleAccept = (rec: RecommendationItem, idx: number) => {
    setRecState(prev => ({ ...prev, [idx]: 'accepted' }))
    onAcceptRecommendation?.({
      seqNo: item.seq_no,
      description: toText(item.description) ?? `Item ${item.seq_no}`,
      recommendedStandard: rec.recommendedStandard,
      clauseText: rec.clauseText,
      originalSpec: getOriginalSpec(),
      quantity: item.quantity,
      unit: item.unit,
      action: 'accepted',
    })
  }

  const handleReject = (rec: RecommendationItem, idx: number) => {
    setRecState(prev => ({ ...prev, [idx]: 'rejected' }))
    onAcceptRecommendation?.({
      seqNo: item.seq_no,
      description: toText(item.description) ?? `Item ${item.seq_no}`,
      recommendedStandard: rec.recommendedStandard,
      clauseText: rec.clauseText,
      originalSpec: getOriginalSpec(),
      quantity: item.quantity,
      unit: item.unit,
      action: 'rejected',
    })
  }

  return (
    <div className={clsx(
      'rounded-2xl border overflow-hidden transition-all duration-200 bg-white dark:bg-zinc-900',
      styles.border
    )}>
      {/* ── Top Header Row ──────────────────────────────────────────────── */}
      {/* 🟠 Item 1 — Control Cable, 4C x 2.5 sq mm     [Incomplete] */}
      <button
        onClick={onToggle}
        className={clsx(
          'w-full flex items-center gap-3 px-5 py-4 text-left transition-colors',
          isExpanded ? styles.headerBg : 'hover:bg-slate-50/80 dark:hover:bg-zinc-800/40'
        )}
      >
        <span className="text-base shrink-0 select-none">{styles.dotEmoji}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 truncate">
            <span className="text-sm font-bold text-slate-900 dark:text-zinc-100">
              {itemPrefix} {item.seq_no} — {toText(item.description) ?? `${itemPrefix} ${item.seq_no}`}
            </span>
          </div>
        </div>

        {/* Status Pill Badge */}
        <span className={clsx(
          'shrink-0 px-3 py-1 rounded-full text-xs font-bold',
          styles.pill, styles.pillText
        )}>
          {statusLabel}
        </span>

        {/* Chevron */}
        <span className="text-slate-400 dark:text-zinc-600 shrink-0">
          {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </span>
      </button>

      {/* ── Expanded Content Body ───────────────────────────────────────── */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <div className="px-6 py-5 border-t border-slate-100 dark:border-zinc-800 space-y-6">

              {/* ── SECTION 1: CITED (EXACTLY HOW IT WAS CITED IN THE PDF) ── */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-zinc-500">
                  {t('audit.cited')}
                </h4>

                {citedList.length > 0 ? (
                  citedList.map((cs, i) => {
                    // Show exactly how cited in PDF: raw_citation first (e.g. "IS : 7098")
                    const exactCitedText = toText(cs.raw_citation) ?? toText(cs.resolved_standard_number) ?? 'IS Standard'
                    const quoteText = toText(cs.quote)
                    const pageNo = toPageNo((cs as any).page_no, cs.quote)
                    const targetLink = toText(cs.resolved_standard_number) ?? exactCitedText

                    return (
                      <div key={i} className="space-y-1.5 pl-1">
                        {/* → IS : 7098 (exactly as in PDF) */}
                        <div className="flex items-center gap-2 flex-wrap text-sm font-mono font-bold text-slate-800 dark:text-zinc-100">
                          <ArrowRight className="w-4 h-4 text-slate-400 shrink-0" />
                          <span>{exactCitedText}</span>
                          {cs.mention_tier && (
                            <span className="text-[10px] font-sans font-bold uppercase px-1.5 py-0.5 rounded bg-slate-100 dark:bg-zinc-800 text-slate-500 dark:text-zinc-400">
                              {toText(cs.mention_tier)}
                            </span>
                          )}
                          <a
                            href={`/standards?is=${encodeURIComponent(targetLink)}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={e => e.stopPropagation()}
                            className="text-blue-500 hover:text-blue-700 dark:hover:text-blue-300 ml-1"
                            title="Open standard in BIS catalog"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                          </a>
                        </div>

                        {/* Source quote is NOT shown directly; only revealed when user clicks [Show source] */}
                        <div className="pl-6">
                          {pageNo != null && (
                            <button
                              onClick={() => setShowCitedSource(prev => ({ ...prev, [i]: !prev[i] }))}
                              className="inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium"
                            >
                              <Eye className="w-3 h-3" />
                              {showCitedSource[i]
                                ? t('audit.hide_source')
                                : `[${t('audit.show_source')}: ${t('audit.page_label')} ${pageNo}]`
                              }
                            </button>
                          )}

                          {/* Inline source expand: visualized on demand */}
                          <AnimatePresence>
                            {showCitedSource[i] && (
                              <EvidenceBox
                                quote={quoteText}
                                pageNo={pageNo}
                                docName={typeof cs.quote === 'object' ? cs.quote?.doc_name : undefined}
                                tier={cs.mention_tier}
                              />
                            )}
                          </AnimatePresence>
                        </div>
                      </div>
                    )
                  })
                ) : (
                  <p className="text-xs text-slate-400 dark:text-zinc-600 italic pl-1">
                    {t('audit.cited_none')}
                  </p>
                )}
              </div>

              {/* ── SECTION 2: GAPS FOUND (NO ACCEPT/REJECT BUTTONS) ──────── */}
              {findingsList.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-zinc-500">
                    {t('audit.gaps_found_n').replace('{n}', String(findingsList.length))}
                  </h4>

                  <div className="space-y-3 pl-1">
                    {findingsList.map((f, i) => (
                      <FindingPointRow
                        key={i}
                        finding={f}
                        index={i}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* ── SECTION 3: COMPLIANT STATUS (WHEN CITED CORRECTLY) ── */}
              {(item.status === 'compliant' || item.badge_color === 'green') && (
                <div className="space-y-2.5 rounded-xl p-3.5 border border-teal-200 dark:border-teal-800/60 bg-teal-50/60 dark:bg-teal-950/20">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2 text-xs font-bold text-teal-800 dark:text-teal-300">
                      <Check className="w-4 h-4 text-teal-600 dark:text-teal-400" />
                      <span>Compliant Specification (Cited Correctly)</span>
                    </div>
                    <span className="text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-teal-100 dark:bg-teal-900/60 text-teal-700 dark:text-teal-300">
                      ✓ Auto-Included in PDF Export
                    </span>
                  </div>
                  <p className="text-xs text-slate-700 dark:text-zinc-300 leading-relaxed pl-6 font-mono">
                    {getOriginalSpec()}
                  </p>
                </div>
              )}

              {/* ── SECTION 4: RECOMMENDED (ALWAYS PRESENT & HUMAN-READABLE) ── */}
              {recommendations.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-zinc-500">
                    {t('audit.recommended')}
                  </h4>

                  {recommendations.map((rec, i) => {
                    const state = recState[i] ?? null
                    return (
                      <div
                        key={i}
                        className={clsx(
                          'space-y-2 pl-1 rounded-xl p-3 border transition-all',
                          state === 'accepted'
                            ? 'border-emerald-300 dark:border-emerald-700 bg-emerald-50/60 dark:bg-emerald-950/20'
                            : state === 'rejected'
                              ? 'border-rose-200 dark:border-rose-800/50 bg-rose-50/40 dark:bg-rose-950/10 opacity-60'
                              : 'border-slate-100 dark:border-zinc-800 bg-slate-50/40 dark:bg-zinc-800/20'
                        )}
                      >
                        {/* → IS 7098 (Part 1):2025 (current edition) */}
                        <div className="flex items-center gap-2 flex-wrap text-sm font-mono font-bold text-emerald-700 dark:text-emerald-400">
                          <ArrowRight className="w-4 h-4 text-emerald-500 shrink-0" />
                          <span>{rec.recommendedStandard}</span>
                          <span className="text-xs font-sans text-emerald-600 dark:text-emerald-500 font-medium">
                            ({t('audit.current_edition')})
                          </span>
                          {state === 'accepted' && (
                            <span className="text-[10px] font-sans font-bold px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/60 text-emerald-700 dark:text-emerald-300">
                              ✓ Accepted — will appear in PDF
                            </span>
                          )}
                          {state === 'rejected' && (
                            <span className="text-[10px] font-sans font-bold px-2 py-0.5 rounded-full bg-rose-100 dark:bg-rose-900/60 text-rose-700 dark:text-rose-300">
                              ✕ Rejected
                            </span>
                          )}
                        </div>

                        {/* Human-readable guidance with year */}
                        <p className="pl-6 text-xs text-slate-600 dark:text-zinc-300 leading-relaxed">
                          {rec.explanation}
                        </p>

                        {/* Action buttons row */}
                        <div className="pl-6 flex items-center gap-2 pt-1 flex-wrap">
                          {/* Accept */}
                          <button
                            onClick={() => handleAccept(rec, i)}
                            disabled={state !== null}
                            className={clsx(
                              'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border shadow-sm transition-all',
                              state === 'accepted'
                                ? 'bg-emerald-100 dark:bg-emerald-900/50 border-emerald-300 dark:border-emerald-700 text-emerald-700 dark:text-emerald-300 cursor-default'
                                : state === 'rejected'
                                  ? 'opacity-40 cursor-not-allowed border-slate-200 dark:border-zinc-700 text-slate-400'
                                  : 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-100 dark:hover:bg-emerald-900/50'
                            )}
                          >
                            <ThumbsUp className="w-3.5 h-3.5" />
                            Accept
                          </button>

                          {/* Reject */}
                          <button
                            onClick={() => handleReject(rec, i)}
                            disabled={state !== null}
                            className={clsx(
                              'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border shadow-sm transition-all',
                              state === 'rejected'
                                ? 'bg-rose-100 dark:bg-rose-900/50 border-rose-300 dark:border-rose-700 text-rose-700 dark:text-rose-300 cursor-default'
                                : state === 'accepted'
                                  ? 'opacity-40 cursor-not-allowed border-slate-200 dark:border-zinc-700 text-slate-400'
                                  : 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 hover:bg-rose-100 dark:hover:bg-rose-900/50'
                            )}
                          >
                            <ThumbsDown className="w-3.5 h-3.5" />
                            Reject
                          </button>

                          {/* Divider */}
                          <span className="text-slate-300 dark:text-zinc-700">|</span>

                          {/* View standard */}
                          <a
                            href={`/standards?is=${encodeURIComponent(rec.recommendedStandard)}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-slate-700 dark:text-zinc-200 hover:border-blue-400 hover:text-blue-600 dark:hover:text-blue-400 shadow-sm transition-all"
                          >
                            <BookOpen className="w-3.5 h-3.5" />
                            {t('audit.view_standard')}
                          </a>

                          {/* Copy clause */}
                          <button
                            onClick={() => handleCopyClause(rec.clauseText)}
                            className={clsx(
                              'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border shadow-sm transition-all',
                              copied
                                ? 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-300 dark:border-emerald-700 text-emerald-700 dark:text-emerald-300'
                                : 'bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/50'
                            )}
                          >
                            {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                            {copied ? t('audit.copied') : t('audit.insert_clause')}
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}

              {/* ── Footer: Rerun this item ───────────────────────────────── */}
              <div className="flex justify-end pt-2 border-t border-slate-100 dark:border-zinc-800">
                <button
                  onClick={() => onRerun(item.seq_no)}
                  disabled={isRerunning}
                  className={clsx(
                    'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all',
                    isRerunning
                      ? 'opacity-60 cursor-wait border-slate-200 dark:border-zinc-700 text-slate-400'
                      : 'bg-white dark:bg-zinc-900 border-slate-200 dark:border-zinc-700 text-slate-600 dark:text-zinc-400 hover:border-blue-400 hover:text-blue-600 dark:hover:text-blue-400'
                  )}
                >
                  <RefreshCw className={clsx('w-3.5 h-3.5', isRerunning && 'animate-spin')} />
                  {isRerunning ? t('audit.rerunning') : t('audit.rerun_item')}
                </button>
              </div>

            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Exported AuditItemCard with ErrorBoundary ──────────────────────────────
export function AuditItemCard(props: {
  item: AuditedItemDTO
  isExpanded: boolean
  onToggle: () => void
  onRerun: (seqNo: number) => Promise<void>
  isRerunning: boolean
  onAcceptRecommendation?: (rec: AcceptedRecommendation) => void
}) {
  return (
    <ErrorBoundary fallbackTitle={`Error rendering item #${props.item.seq_no}`}>
      <AuditItemCardInner {...props} />
    </ErrorBoundary>
  )
}

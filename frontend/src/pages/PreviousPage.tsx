import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  History, ArrowUpRight, Trash2, RotateCcw,
  Layers, Clock
} from 'lucide-react'
import { Shell } from '@/components/layout/Shell'
import { useTranslation } from '@/i18n/I18nContext'
import {
  getPreviousRecommendations,
  deletePreviousRecommendation,
  clearPreviousRecommendations,
  restoreDefaultRecommendations,
  type SavedRecommendation
} from '@/utils/storage'
import { clsx } from 'clsx'

// ── Department badge helper ──────────────────────────────────────────────────
function DeptBadge({ dept }: { dept?: string }) {
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

// ── Relative time formatter ───────────────────────────────────────────────────
function formatTimeAgo(timestamp: number): string {
  const diffMs = Date.now() - timestamp
  const diffMins = Math.floor(diffMs / (1000 * 60))
  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}d ago`
}

// ── Card Component for 3-in-a-row layout ───────────────────────────────────────
interface RecCardProps {
  item: SavedRecommendation
  onOpen: (query: string) => void
  onDelete: (id: string) => void
}

function RecCard({ item, onOpen, onDelete }: RecCardProps) {
  const { t } = useTranslation()

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      whileHover={{ y: -3, transition: { duration: 0.18 } }}
      className={clsx(
        'group flex flex-col justify-between rounded-2xl p-5 transition-all text-left',
        'bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800',
        'hover:border-blue-400 dark:hover:border-blue-600/70 hover:shadow-lg hover:shadow-blue-500/5'
      )}
    >
      <div>
        {/* Top Badges & Meta */}
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-1.5 flex-wrap">
            <DeptBadge dept={item.dept} />
            {item.status && (
              <span className={clsx(
                'inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-tight',
                item.status.includes('Reaffirm')
                  ? 'bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 ring-1 ring-blue-200 dark:ring-blue-800'
                  : 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 ring-1 ring-emerald-200 dark:ring-emerald-800'
              )}>
                {item.status}
              </span>
            )}
            {item.confidence && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-bold text-slate-500 dark:text-zinc-400 bg-slate-100 dark:bg-zinc-800">
                {item.confidence}% match
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5 shrink-0 text-slate-400 dark:text-zinc-500 text-[11px]">
            <Clock className="w-3 h-3" />
            <span>{formatTimeAgo(item.timestamp)}</span>
            <button
              onClick={(e) => {
                e.stopPropagation()
                onDelete(item.id)
              }}
              title="Remove from history"
              className="p-1 rounded-md text-slate-400 hover:text-rose-500 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors ml-1"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Primary Standard Number */}
        <div className="flex items-baseline gap-2 mb-1.5">
          <span className="text-base font-bold text-slate-900 dark:text-white tracking-tight group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
            {item.primaryStandard}
          </span>
          {item.standardsCount > 0 && (
            <span className="text-[11px] text-slate-500 dark:text-zinc-400 font-medium">
              ({item.standardsCount} {t('previous.standards')})
            </span>
          )}
        </div>

        {/* Title / Description */}
        {item.primaryTitle && (
          <p className="text-xs font-medium text-slate-700 dark:text-zinc-300 line-clamp-1 mb-2">
            {item.primaryTitle}
          </p>
        )}

        {/* Query requirement bubble */}
        <div className="p-3 rounded-xl bg-slate-50 dark:bg-zinc-800/60 border border-slate-100 dark:border-zinc-800/80 mb-4">
          <p className="text-[11px] font-semibold text-slate-400 dark:text-zinc-500 uppercase tracking-wider mb-1">
            Procurement Requirement
          </p>
          <p className="text-xs text-slate-800 dark:text-zinc-200 line-clamp-2 leading-relaxed italic">
            "{item.query}"
          </p>
        </div>
      </div>

      {/* Card Action Button — matching user sketch: [ Re-open Recommendation ↗ ] */}
      <button
        onClick={() => onOpen(item.query)}
        className={clsx(
          'w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-bold transition-all',
          'bg-blue-600 hover:bg-blue-700 text-white shadow-sm hover:shadow',
          'group-hover:bg-blue-600 active:scale-[0.98]'
        )}
      >
        <span>Re-open Recommendation</span>
        <ArrowUpRight className="w-3.5 h-3.5" />
      </button>
    </motion.div>
  )
}

// ── Main Previous Page ────────────────────────────────────────────────────────
export function PreviousPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [items, setItems] = useState<SavedRecommendation[]>([])

  const loadData = useCallback(() => {
    const list = getPreviousRecommendations()
    setItems(list)
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleOpen = useCallback((query: string) => {
    navigate(`/recommend?query=${encodeURIComponent(query)}`)
  }, [navigate])

  const handleDelete = useCallback((id: string) => {
    deletePreviousRecommendation(id)
    loadData()
  }, [loadData])

  const handleClearAll = useCallback(() => {
    clearPreviousRecommendations()
    setItems([])
  }, [])

  const handleRestoreDefaults = useCallback(() => {
    restoreDefaultRecommendations()
    loadData()
  }, [loadData])

  return (
    <Shell botContext="general">
      <div className="min-h-full bg-slate-50/50 dark:bg-zinc-950 px-6 py-8">
        <div className="max-w-7xl mx-auto space-y-6">

          {/* ── Page Header ── */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-zinc-800">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 flex items-center justify-center">
                <History className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
                  {t('previous.title')}
                </h1>
                <p className="text-xs text-slate-500 dark:text-zinc-400 mt-0.5">
                  Showing previous sessions 
                </p>
              </div>
            </div>

            {/* Quick Actions Header */}
            <div className="flex items-center gap-2.5 self-end sm:self-center">
              <button
                onClick={handleRestoreDefaults}
                title="Restore 6 demo procurement recommendations"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-600 dark:text-zinc-400 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700 hover:border-slate-300 dark:hover:border-zinc-600 shadow-sm transition-all"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Reset Sample Data
              </button>

              {items.length > 0 && (
                <button
                  onClick={handleClearAll}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 hover:bg-rose-100 transition-all"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Clear History
                </button>
              )}
            </div>
          </div>

          {/* ── 3 IN A ROW CARDS GRID (6 Cards max) ── */}
          {items.length > 0 ? (
            <motion.div
              initial="hidden"
              animate="show"
              variants={{
                hidden: {},
                show: { transition: { staggerChildren: 0.05 } }
              }}
              className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"
            >
              <AnimatePresence>
                {items.map((item) => (
                  <RecCard
                    key={item.id}
                    item={item}
                    onOpen={handleOpen}
                    onDelete={handleDelete}
                  />
                ))}
              </AnimatePresence>
            </motion.div>
          ) : (
            /* ── Empty State ── */
            <div className="flex flex-col items-center justify-center py-20 text-center rounded-2xl border border-dashed border-slate-300 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-8">
              <div className="w-14 h-14 rounded-2xl bg-slate-100 dark:bg-zinc-800 flex items-center justify-center mb-3 text-slate-400">
                <Layers className="w-6 h-6" />
              </div>
              <h3 className="text-sm font-bold text-slate-800 dark:text-zinc-200 mb-1">
                {t('previous.empty')}
              </h3>
              <p className="text-xs text-slate-500 dark:text-zinc-400 max-w-sm mb-5 leading-relaxed">
                When you run procurement queries in the Recommend tab, up to 6 past sessions will automatically appear here.
              </p>
              <button
                onClick={handleRestoreDefaults}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold bg-blue-600 hover:bg-blue-700 text-white shadow-sm transition-all"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Load 6 Sample Recommendations
              </button>
            </div>
          )}

        </div>
      </div>
    </Shell>
  )
}

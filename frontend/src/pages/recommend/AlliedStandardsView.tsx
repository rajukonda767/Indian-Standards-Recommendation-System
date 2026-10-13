import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, ExternalLink } from 'lucide-react'
import { useTranslation } from '@/i18n/I18nContext'
import type { AlliedGroup, AlliedItem } from '@/lib/api'
import { clsx } from 'clsx'
import { useNavigate } from 'react-router-dom'

// ── Allied entry card ────────────────────────────────────────────────────────
function AlliedCard({ entry }: { entry: AlliedItem }) {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const status = entry.status || 'Current'
  const isNotInIndex = status === 'NOT_IN_INDEX'
  const isCurrent = !isNotInIndex && (status.toLowerCase() === 'current' || status.toLowerCase() === 'active' || status.toLowerCase() === 'published')
  const isReaffirmed = !isNotInIndex && status.toLowerCase().includes('reaffirm')

  // For NOT_IN_INDEX: distinguish international refs from missing IS entries
  const sn = entry.standard_number || ''
  const isInternational = /^(IEC|ISO|EN|BS)\b/.test(sn)
  const notInIndexLabel = isInternational ? 'International reference (IEC/ISO)' : 'Not yet indexed'

  return (
    <div className={clsx(
      'flex items-center justify-between px-3.5 py-3 rounded-xl transition-colors',
      'bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800',
      'hover:border-slate-300 dark:hover:border-zinc-700 hover:shadow-sm'
    )}>
      <div className="flex flex-col gap-0.5 min-w-0 mr-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[13px] font-bold text-slate-900 dark:text-white tracking-tight shrink-0">
            {entry.standard_number}
          </span>
          {isNotInIndex ? (
            <span className={clsx(
              'inline-flex px-2 py-0.5 rounded-full text-[11px] font-medium shrink-0',
              isInternational
                ? 'text-violet-700 dark:text-violet-400 bg-violet-50 dark:bg-violet-950/50 ring-1 ring-violet-200 dark:ring-violet-800'
                : 'text-slate-500 dark:text-zinc-400 bg-slate-100 dark:bg-zinc-800 ring-1 ring-slate-300 dark:ring-zinc-700'
            )}>
              {notInIndexLabel}
            </span>
          ) : (
            <span className={clsx(
              'inline-flex px-2 py-0.5 rounded-full text-[11px] font-medium shrink-0',
              isCurrent
                ? 'text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/50 ring-1 ring-emerald-200 dark:ring-emerald-800'
                : isReaffirmed
                ? 'text-blue-700 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/50 ring-1 ring-blue-200 dark:ring-blue-800'
                : 'text-zinc-500 dark:text-zinc-400 bg-zinc-100 dark:bg-zinc-800 ring-1 ring-zinc-300 dark:ring-zinc-700'
            )}>
              {status}
            </span>
          )}
        </div>
        <p className="text-xs text-slate-600 dark:text-zinc-400 leading-snug line-clamp-2">
          {entry.title}
        </p>
      </div>
      <button
        onClick={() => navigate(`/standards?is=${encodeURIComponent(entry.standard_number)}`)}
        className={clsx(
          'shrink-0 inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-colors',
          'border border-blue-200 dark:border-blue-800',
          'bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-400',
          'hover:bg-blue-100 dark:hover:bg-blue-950'
        )}
      >
        {t('recommend.viewFull')}
        <ExternalLink className="w-3 h-3" />
      </button>
    </div>
  )
}

// ── Section (collapsible) ────────────────────────────────────────────────────
interface SectionProps {
  title: string
  entries: AlliedItem[]
  defaultOpen?: boolean
}

function AlliedSection({ title, entries, defaultOpen = false }: SectionProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="rounded-xl border border-slate-200 dark:border-zinc-800 overflow-hidden">
      {/* Section header */}
      <button
        onClick={() => setOpen((o) => !o)}
        className={clsx(
          'w-full flex items-center justify-between px-4 py-3 transition-colors text-left',
          open
            ? 'bg-slate-50 dark:bg-zinc-900/70 border-b border-slate-200 dark:border-zinc-800'
            : 'bg-white dark:bg-zinc-900 hover:bg-slate-50 dark:hover:bg-zinc-800/50'
        )}
      >
        <div className="flex items-center gap-2.5">
          <span className={clsx(
            'w-1.5 h-1.5 rounded-full shrink-0',
            entries.length > 0 ? 'bg-blue-500' : 'bg-slate-300 dark:bg-zinc-600'
          )} />
          <span className="text-xs font-semibold text-slate-800 dark:text-zinc-200">
            {title}
          </span>
          <span className={clsx(
            'inline-flex items-center px-1.5 py-0.5 rounded-md text-[11px] font-semibold tabular-nums',
            entries.length > 0
              ? 'bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-400'
              : 'bg-slate-100 dark:bg-zinc-800 text-slate-500 dark:text-zinc-500'
          )}>
            {entries.length}
          </span>
        </div>
        <ChevronDown className={clsx(
          'w-4 h-4 text-slate-400 dark:text-zinc-500 transition-transform duration-200',
          open && 'rotate-180'
        )} />
      </button>

      {/* Collapsible content */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
            className="overflow-hidden"
          >
            <div className="p-3 space-y-2 bg-slate-50/50 dark:bg-zinc-900/30">
              {entries.length === 0 ? (
                <p className="text-[12px] text-slate-400 dark:text-zinc-500 italic px-1 py-1">
                  {t('recommend.allied_none') || 'No allied standards referenced under this category.'}
                </p>
              ) : (
                entries.map((e, idx) => (
                  <AlliedCard key={`${e.standard_number}-${idx}`} entry={e} />
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────
interface AlliedStandardsViewProps {
  graph: AlliedGroup
}

const SECTIONS: { title: string; key: keyof AlliedGroup; defaultOpen: boolean }[] = [
  { title: 'Normative References',            key: 'normative_references',        defaultOpen: true  },
  { title: 'Test Methods & Sampling',         key: 'test_methods',                defaultOpen: true  },
  { title: 'Terminology & Codes of Practice', key: 'terminology',                 defaultOpen: false },
  { title: 'Safety & Environmental Standards',key: 'safety_standards',            defaultOpen: false },
  { title: 'Installation & Workmanship',      key: 'installation_standards',      defaultOpen: false },
  { title: 'Related Product Standards',       key: 'related_product_standards',   defaultOpen: false },
]

export function AlliedStandardsView({ graph }: AlliedStandardsViewProps) {
  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={{ hidden: {}, show: { transition: { staggerChildren: 0.06 } } }}
      className="space-y-2"
    >
      {SECTIONS.map(({ title, key, defaultOpen }) => {
        const entries = (graph && graph[key]) || []
        return (
          <motion.div
            key={key}
            variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.22, 1, 0.36, 1] } } }}
          >
            <AlliedSection
              title={title}
              entries={entries}
              defaultOpen={defaultOpen}
            />
          </motion.div>
        )
      })}
    </motion.div>
  )
}

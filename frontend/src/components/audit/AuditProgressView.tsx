// ---------------------------------------------------------------------------
// frontend/src/components/audit/AuditProgressView.tsx
// Live progress bar + streaming item ticker while job is running
// Polls GET /api/audit/jobs/{job_id} every 1500ms
// ---------------------------------------------------------------------------

import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, Clock, AlertTriangle } from 'lucide-react'
import { clsx } from 'clsx'
import { useTranslation } from '@/i18n/I18nContext'
import { getAuditJobPoll, type AuditJobPollResponse, type AuditedItemDTO } from '@/lib/auditApi'


const POLL_INTERVAL_MS = 1500

interface AuditProgressViewProps {
  jobId: string
  onCompleted: (result: AuditJobPollResponse) => void
  onFailed: (errorMsg: string) => void
}

// Badge color → Tailwind class lookup (no dynamic template strings for Tailwind v4 purging)
const STATUS_DOT: Record<string, string> = {
  compliant:     'bg-emerald-500',
  incomplete:    'bg-amber-400',
  outdated:      'bg-orange-500',
  superseded:    'bg-orange-600',
  conflict:      'bg-rose-500',
  missing:       'bg-rose-600',
  cannot_verify: 'bg-slate-400',
  error:         'bg-slate-400',
}

function elapsed(startMs: number): string {
  const secs = Math.floor((Date.now() - startMs) / 1000)
  if (secs < 60) return `${secs}s`
  return `${Math.floor(secs / 60)}m ${secs % 60}s`
}

export function AuditProgressView({ jobId, onCompleted, onFailed }: AuditProgressViewProps) {
  const [job, setJob] = useState<AuditJobPollResponse | null>(null)
  const [streamedItems, setStreamedItems] = useState<AuditedItemDTO[]>([])
  const [elapsedStr, setElapsedStr] = useState('0s')
  const startMsRef = useRef(Date.now())
  const seenSeqNos = useRef<Set<number>>(new Set())
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const clockRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Elapsed clock
  useEffect(() => {
    clockRef.current = setInterval(() => {
      setElapsedStr(elapsed(startMsRef.current))
    }, 1000)
    return () => { if (clockRef.current) clearInterval(clockRef.current) }
  }, [])

  // Polling
  useEffect(() => {
    let stopped = false

    const poll = async () => {
      try {
        const data = await getAuditJobPoll(jobId)
        if (stopped) return

        setJob(data)

        // Append newly completed items to stream
        const newItems = (data.items ?? []).filter(it => !seenSeqNos.current.has(it.seq_no))
        if (newItems.length > 0) {
          newItems.forEach(it => seenSeqNos.current.add(it.seq_no))
          setStreamedItems(prev => [...prev, ...newItems])
        }

        if (data.status === 'done') {
          stopped = true
          if (timerRef.current) clearInterval(timerRef.current)
          if (clockRef.current) clearInterval(clockRef.current)
          onCompleted(data)
          return
        }

        if (data.status === 'failed' || data.status === 'timeout') {
          stopped = true
          if (timerRef.current) clearInterval(timerRef.current)
          if (clockRef.current) clearInterval(clockRef.current)
          onFailed(data.error_msg ?? `Job ${data.status}`)
          return
        }
      } catch (e: any) {
        if (!stopped) {
          // network blip — keep polling, don't abort
          console.warn('Poll error (will retry):', e.message)
        }
      }
    }

    poll() // immediate first call
    timerRef.current = setInterval(poll, POLL_INTERVAL_MS)

    return () => {
      stopped = true
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [jobId, onCompleted, onFailed])

  const total = job?.total_items ?? 0
  const done = job?.done_items ?? 0
  const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0
  const { t } = useTranslation()

  return (
    <div className="flex flex-col items-center justify-start min-h-[calc(100vh-3.5rem)] px-6 py-12 gap-8">
      <div className="w-full max-w-xl space-y-6">
        {/* Header */}
        <div className="text-center space-y-1">
          <h1 className="text-xl font-bold text-slate-900 dark:text-zinc-100">{t('audit.processing')}</h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400">
            {total > 0
              ? t('audit.processing_sub').replace('{n}', String(total))
              : t('audit.processing_sub').replace('{n}', '…')}
          </p>
        </div>

        {/* Progress bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-zinc-400">
            <span>{done} / {total > 0 ? total : '…'} items</span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {elapsedStr}
            </span>
          </div>
          <div className="h-3 rounded-full bg-slate-100 dark:bg-zinc-800 overflow-hidden">
            <motion.div
              className="h-full bg-blue-500 rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${pct}%` }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
            />
          </div>
          <div className="text-right text-xs font-semibold text-blue-600 dark:text-blue-400">{pct}%</div>
        </div>

        {/* Live item stream */}
        <div className="rounded-2xl border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 overflow-hidden">
          <div className="px-4 py-2.5 border-b border-slate-100 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-800/50">
            <p className="text-xs font-bold text-slate-600 dark:text-zinc-400 uppercase tracking-wide">
              {t('audit.live_stream')}
            </p>
          </div>
          <div className="max-h-72 overflow-y-auto">
            {streamedItems.length === 0 ? (
              <div className="px-4 py-6 text-center text-xs text-slate-400 dark:text-zinc-600">
                {t('audit.waiting_items')}
              </div>
            ) : (
              <AnimatePresence>
                {[...streamedItems].reverse().map((item) => (
                  <motion.div
                    key={item.seq_no}
                    initial={{ opacity: 0, x: -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.25 }}
                    className="flex items-center gap-3 px-4 py-2.5 border-b last:border-0 border-slate-100 dark:border-zinc-800"
                  >
                    <span className={clsx('w-2 h-2 rounded-full shrink-0', STATUS_DOT[item.status] ?? 'bg-slate-400')} />
                    <span className="text-xs text-slate-700 dark:text-zinc-300 flex-1 truncate">
                      {item.description}
                    </span>
                    <span className="text-[10px] uppercase tracking-wide font-semibold text-slate-400 dark:text-zinc-600 shrink-0">
                      {t(`audit.badge_${item.status}`) || item.status.replace('_', ' ')}
                    </span>
                  </motion.div>
                ))}
              </AnimatePresence>
            )}
          </div>
        </div>

        {/* Status indicators */}
        {(job?.status === 'failed' || job?.status === 'timeout') && (
          <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            {job.error_msg ?? t('common.error')}
          </div>
        )}

        {job?.status === 'done' && (
          <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-700 dark:text-emerald-300">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            {t('audit.results')} — {t('common.loading')}
          </div>
        )}
      </div>
    </div>
  )
}

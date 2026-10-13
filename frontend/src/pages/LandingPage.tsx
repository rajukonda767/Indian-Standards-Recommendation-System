import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight } from 'lucide-react'
import { useTranslation, LANGUAGES } from '@/i18n/I18nContext'
import { useTheme } from '@/hooks/useTheme'
import { clsx } from 'clsx'
import { Sun, Moon, Globe, Check, ChevronDown } from 'lucide-react'

// ── Stagger config ──────────────────────────────────────────────────────────
const CONTAINER = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.12, delayChildren: 0.1 },
  },
}

const ITEM = {
  hidden: { opacity: 0, y: 40 },
  show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] as const } },
}

// ── Minimal top-bar controls (no sidebar on landing) ──────────────────────
function LandingTopBar() {
  const { lang, setLang } = useTranslation()
  const { isDark, toggle } = useTheme()
  const [open, setOpen] = useState(false)
  const current = LANGUAGES.find((l) => l.code === lang) ?? LANGUAGES[0]

  return (
    <div className="flex items-center gap-2">
      {/* Theme */}
      <button
        onClick={toggle}
        className={clsx(
          'w-8 h-8 rounded-lg flex items-center justify-center transition-colors',
          'border border-slate-200 dark:border-zinc-700',
          'bg-white/80 dark:bg-zinc-900/80 text-slate-600 dark:text-zinc-300',
          'hover:bg-slate-100 dark:hover:bg-zinc-800'
        )}
        aria-label="Toggle theme"
      >
        {isDark
          ? <Sun className="w-3.5 h-3.5 text-amber-400" />
          : <Moon className="w-3.5 h-3.5" />
        }
      </button>

      {/* Language */}
      <div className="relative">
        <button
          onClick={() => setOpen((o) => !o)}
          className={clsx(
            'flex items-center gap-1.5 h-8 px-2.5 rounded-lg text-xs font-medium transition-colors',
            'border border-slate-200 dark:border-zinc-700',
            'bg-white/80 dark:bg-zinc-900/80 text-slate-700 dark:text-zinc-300',
            'hover:bg-slate-100 dark:hover:bg-zinc-800'
          )}
        >
          <Globe className="w-3.5 h-3.5 text-slate-400 dark:text-zinc-500" />
          <span>{current.nativeLabel}</span>
          <ChevronDown className={clsx('w-3 h-3 text-slate-400 transition-transform duration-150', open && 'rotate-180')} />
        </button>

        {open && (
          <div className={clsx(
            'absolute right-0 top-full mt-1.5 w-36 rounded-xl shadow-xl z-50 py-1',
            'bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700'
          )}>
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                onClick={() => { setLang(l.code); setOpen(false) }}
                className={clsx(
                  'w-full flex items-center justify-between px-3 py-2 text-xs transition-colors',
                  l.code === lang
                    ? 'bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-400 font-semibold'
                    : 'text-slate-700 dark:text-zinc-300 hover:bg-slate-50 dark:hover:bg-zinc-800'
                )}
              >
                <span>{l.nativeLabel}</span>
                {l.code === lang && <Check className="w-3 h-3 text-blue-600 dark:text-blue-400" />}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main Landing Page ───────────────────────────────────────────────────────
export function LandingPage() {
  const navigate = useNavigate()
  const { t } = useTranslation()

  return (
    <div className="relative flex flex-col min-h-screen bg-white dark:bg-zinc-950 overflow-hidden">

      {/* Subtle background grid */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,#e2e8f0_1px,transparent_1px),linear-gradient(to_bottom,#e2e8f0_1px,transparent_1px)] dark:bg-[linear-gradient(to_right,#27272a_1px,transparent_1px),linear-gradient(to_bottom,#27272a_1px,transparent_1px)] bg-[size:48px_48px] opacity-60 dark:opacity-30"
      />

      {/* Radial glow — center hero */}
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-[55%] w-[600px] h-[600px] rounded-full bg-blue-500/10 dark:bg-blue-500/8 blur-[96px]"
      />

      {/* Top nav bar */}
      <header className="relative z-10 flex items-center justify-between px-6 sm:px-10 h-16">
        <span className="text-sm font-bold tracking-tight text-slate-900 dark:text-white select-none">
          StandardSphere
        </span>
        <LandingTopBar />
      </header>

      {/* Hero content */}
      <main className="relative z-10 flex flex-1 items-center justify-center px-4">
        <motion.div
          variants={CONTAINER}
          initial="hidden"
          animate="show"
          className="flex flex-col items-center text-center max-w-2xl w-full"
        >
          {/* Eyebrow badge */}
          <motion.div variants={ITEM}>
            <span className={clsx(
              'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium mb-8',
              'bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-400',
              'border border-blue-200/60 dark:border-blue-800/60'
            )}>
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
              BIS · GeM · Government of India
            </span>
          </motion.div>

          {/* Title */}
          <motion.h1
            variants={ITEM}
            className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight text-slate-900 dark:text-white leading-[1.08] mb-5"
          >
            {t('landing.title')}
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            variants={ITEM}
            className="text-lg sm:text-xl font-medium text-slate-600 dark:text-zinc-400 mb-3"
          >
            {t('landing.subtitle')}
          </motion.p>

          {/* Tagline */}
          <motion.p
            variants={ITEM}
            className="text-sm sm:text-base text-slate-500 dark:text-zinc-500 max-w-md leading-relaxed mb-10"
          >
            {t('landing.tagline')}
          </motion.p>

          {/* CTA button */}
          <motion.div variants={ITEM}>
            <button
              onClick={() => navigate('/recommend')}
              className={clsx(
                'group inline-flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold',
                'bg-blue-600 hover:bg-blue-700 active:bg-blue-800',
                'text-white shadow-md shadow-blue-600/25 hover:shadow-lg hover:shadow-blue-600/30',
                'transition-all duration-150 active:scale-[0.98]'
              )}
            >
              {t('landing.cta')}
              <ArrowRight className="w-4 h-4 transition-transform duration-150 group-hover:translate-x-0.5" />
            </button>
          </motion.div>

          {/* Subtle trust row */}
          <motion.div
            variants={ITEM}
            className="flex items-center gap-2 mt-12 text-xs text-slate-400 dark:text-zinc-600"
          >
            <span className="w-1 h-1 rounded-full bg-slate-300 dark:bg-zinc-700" />
            <span>400 + BIS Standards indexed</span>
            <span className="w-1 h-1 rounded-full bg-slate-300 dark:bg-zinc-700" />
            <span>ISI · QCO · GeM compliant</span>
            <span className="w-1 h-1 rounded-full bg-slate-300 dark:bg-zinc-700" />
            <span>Multilingual</span>
          </motion.div>
        </motion.div>
      </main>

      {/* Footer strip */}
      <footer className="relative z-10 flex items-center justify-center pb-6 text-[11px] text-slate-400 dark:text-zinc-700">
        Bureau of Indian Standards · SIH 2026
      </footer>

    </div>
  )
}

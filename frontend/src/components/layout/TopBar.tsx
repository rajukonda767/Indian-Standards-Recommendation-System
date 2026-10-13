import { useState, useRef, useEffect } from 'react'
import { Sun, Moon, Globe, Check, ChevronDown } from 'lucide-react'
import { useTranslation, LANGUAGES } from '@/i18n/I18nContext'
import { useTheme } from '@/hooks/useTheme'
import { clsx } from 'clsx'

export function TopBar() {
  const { lang, setLang } = useTranslation()
  const { isDark, toggle } = useTheme()
  const [langOpen, setLangOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setLangOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const currentLang = LANGUAGES.find((l) => l.code === lang) ?? LANGUAGES[0]

  return (
    <div className="flex items-center gap-2">
      {/* Theme toggle */}
      <button
        onClick={toggle}
        className={clsx(
          'flex items-center justify-center w-8 h-8 rounded-lg transition-colors',
          'border border-slate-200 dark:border-zinc-700',
          'bg-white dark:bg-zinc-900 text-slate-600 dark:text-zinc-300',
          'hover:bg-slate-100 dark:hover:bg-zinc-800'
        )}
        title={isDark ? 'Switch to Light' : 'Switch to Dark'}
        aria-label="Toggle theme"
      >
        {isDark
          ? <Sun className="w-3.5 h-3.5 text-amber-400" />
          : <Moon className="w-3.5 h-3.5" />
        }
      </button>

      {/* Language selector */}
      <div ref={dropdownRef} className="relative">
        <button
          onClick={() => setLangOpen((o) => !o)}
          className={clsx(
            'flex items-center gap-1.5 h-8 px-2.5 rounded-lg text-xs font-medium transition-colors',
            'border border-slate-200 dark:border-zinc-700',
            'bg-white dark:bg-zinc-900 text-slate-700 dark:text-zinc-300',
            'hover:bg-slate-100 dark:hover:bg-zinc-800'
          )}
        >
          <Globe className="w-3.5 h-3.5 text-slate-400 dark:text-zinc-500" />
          <span>{currentLang.nativeLabel}</span>
          <ChevronDown
            className={clsx(
              'w-3 h-3 text-slate-400 transition-transform duration-150',
              langOpen && 'rotate-180'
            )}
          />
        </button>

        {langOpen && (
          <div className={clsx(
            'absolute right-0 top-full mt-1.5 w-36 rounded-xl shadow-lg z-50 py-1',
            'bg-white dark:bg-zinc-900',
            'border border-slate-200 dark:border-zinc-700',
            'ring-1 ring-black/5 dark:ring-white/5'
          )}>
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                onClick={() => { setLang(l.code); setLangOpen(false) }}
                className={clsx(
                  'w-full flex items-center justify-between px-3 py-2 text-xs transition-colors',
                  l.code === lang
                    ? 'text-blue-700 dark:text-blue-400 font-semibold bg-blue-50 dark:bg-blue-950/50'
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

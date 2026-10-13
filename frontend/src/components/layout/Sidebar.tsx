import { NavLink, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Home,
  Sparkles,
  BookOpen,
  ClipboardList,
  History,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { useTranslation } from '@/i18n/I18nContext'
import { clsx } from 'clsx'

interface NavItem {
  key: string
  to: string
  icon: React.ComponentType<{ className?: string }>
  labelKey: string
}

const NAV_ITEMS: NavItem[] = [
  { key: 'home',     to: '/',              icon: Home,          labelKey: 'nav.home' },
  { key: 'rec',      to: '/recommend',     icon: Sparkles,      labelKey: 'nav.recommend' },
  { key: 'std',      to: '/standards',     icon: BookOpen,      labelKey: 'nav.standards' },
  { key: 'audit',    to: '/tender-audit',  icon: ClipboardList, labelKey: 'nav.tenderAudit' },
  { key: 'prev',     to: '/previous',      icon: History,       labelKey: 'nav.previous' },
]

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { t } = useTranslation()
  const location = useLocation()

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 56 : 220 }}
      transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
      className="relative flex flex-col flex-shrink-0 h-full bg-white dark:bg-zinc-950 border-r border-slate-200 dark:border-zinc-800 overflow-hidden z-20"
    >
      {/* Brand / toggle row */}
      <div className="flex items-center h-14 px-3 border-b border-slate-200 dark:border-zinc-800 flex-shrink-0">
        <AnimatePresence initial={false}>
          {!collapsed && (
            <motion.span
              key="brand"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.15 }}
              className="flex-1 text-sm font-bold tracking-tight text-slate-900 dark:text-white truncate pr-2 select-none"
            >
              StandardSphere
            </motion.span>
          )}
        </AnimatePresence>

        <button
          onClick={onToggle}
          className={clsx(
            'flex items-center justify-center w-7 h-7 rounded-md text-slate-500 dark:text-zinc-400',
            'hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors flex-shrink-0',
            collapsed && 'mx-auto'
          )}
          title={collapsed ? t('nav.expand') : t('nav.collapse')}
          aria-label={collapsed ? t('nav.expand') : t('nav.collapse')}
        >
          {collapsed
            ? <ChevronRight className="w-4 h-4" />
            : <ChevronLeft className="w-4 h-4" />
          }
        </button>
      </div>

      {/* Nav items */}
      <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-hidden">
        {NAV_ITEMS.map(({ key, to, icon: Icon, labelKey }) => {
          const active =
            to === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(to)

          return (
            <NavLink
              key={key}
              to={to}
              className={clsx(
                'flex items-center gap-3 px-2.5 py-2 rounded-lg text-xs font-medium transition-colors group relative',
                active
                  ? 'bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-400'
                  : 'text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800/70 hover:text-slate-900 dark:hover:text-white'
              )}
              title={collapsed ? t(labelKey) : undefined}
            >
              <Icon
                className={clsx(
                  'w-4 h-4 flex-shrink-0',
                  active ? 'text-blue-600 dark:text-blue-400' : 'text-slate-400 dark:text-zinc-500 group-hover:text-slate-600 dark:group-hover:text-zinc-300'
                )}
              />
              <AnimatePresence initial={false}>
                {!collapsed && (
                  <motion.span
                    key={`label-${key}`}
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -6 }}
                    transition={{ duration: 0.15 }}
                    className="truncate leading-none"
                  >
                    {t(labelKey)}
                  </motion.span>
                )}
              </AnimatePresence>

              {/* Active indicator bar */}
              {active && (
                <motion.span
                  layoutId="sidebar-active-pill"
                  className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r-full bg-blue-600 dark:bg-blue-500"
                />
              )}
            </NavLink>
          )
        })}
      </nav>
    </motion.aside>
  )
}

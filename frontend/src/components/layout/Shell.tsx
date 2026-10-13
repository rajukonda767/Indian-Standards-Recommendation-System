import { useState, type ReactNode } from 'react'
import { Sparkles } from 'lucide-react'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { MiniBotDrawer } from '@/components/bot/MiniBotDrawer'

interface ShellProps {
  children: ReactNode
  headerTitle?: string
  botContext?: 'recommend' | 'standards' | 'audit' | 'general'
  showBot?: boolean
  /** Actual query string forwarded to bot for context-aware chips */
  botQueryContext?: string
  /** Detailed screen metadata (primary_is, job_id, etc.) */
  botScreenData?: Record<string, any>
  /** When true, drawer opens without sending any message */
  botForceOpen?: boolean
  onBotForceOpenConsumed?: () => void
}

export function Shell({
  children,
  headerTitle = 'AI-Powered Procurement Recommendation Assistant',
  botContext = 'general',
  showBot = true,
  botQueryContext,
  botScreenData,
  botForceOpen,
  onBotForceOpenConsumed,
}: ShellProps) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-zinc-950 overflow-hidden">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />

      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <header className="flex items-center justify-between px-4 sm:px-6 h-14 flex-shrink-0 border-b border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 gap-4">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-7 h-7 rounded-lg bg-blue-600/10 dark:bg-blue-500/10 border border-blue-600/20 dark:border-blue-400/20 flex items-center justify-center shrink-0">
              <Sparkles className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            </div>
            <h1 className="font-semibold text-xs sm:text-sm md:text-base text-slate-800 dark:text-zinc-100 truncate tracking-tight">
              {headerTitle}
            </h1>
          </div>
          <TopBar />
        </header>
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>

      {showBot && (
        <MiniBotDrawer
          context={botContext}
          queryContext={botQueryContext}
          screenData={botScreenData}
          forceOpen={botForceOpen}
          onForceOpenConsumed={onBotForceOpenConsumed}
        />
      )}
    </div>
  )
}

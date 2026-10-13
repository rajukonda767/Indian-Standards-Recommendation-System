export function SkeletonCard() {
  return (
    <div className="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 sm:p-5 animate-pulse">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="h-4 w-24 rounded-md bg-slate-200 dark:bg-zinc-800" />
          <div className="h-4 w-16 rounded-full bg-slate-200 dark:bg-zinc-800" />
        </div>
        <div className="h-4 w-10 rounded-full bg-slate-200 dark:bg-zinc-800" />
      </div>
      <div className="h-3.5 w-3/4 rounded-md bg-slate-200 dark:bg-zinc-800 mb-2" />
      <div className="h-3 w-full rounded-md bg-slate-100 dark:bg-zinc-800/60 mb-1.5" />
      <div className="h-3 w-5/6 rounded-md bg-slate-100 dark:bg-zinc-800/60 mb-4" />
      <div className="flex items-center justify-between">
        <div className="flex gap-1.5">
          <div className="h-5 w-20 rounded-md bg-slate-100 dark:bg-zinc-800/60" />
          <div className="h-5 w-16 rounded-md bg-slate-100 dark:bg-zinc-800/60" />
        </div>
        <div className="h-7 w-24 rounded-lg bg-slate-100 dark:bg-zinc-800/60" />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// frontend/src/components/audit/AuditUploadZone.tsx
// Multi-file upload zone: PDF, DOCX, XLSX, up to 25 MB each.
// Shows a file "chip list" so users clearly see multi-select is possible.
// Fully i18n-aware. Drag-and-drop + click + paste text modal.
// ---------------------------------------------------------------------------

import { useState, useRef, useCallback, type DragEvent, type ChangeEvent } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, FileText, FileSpreadsheet, X, ClipboardPaste,
  AlertTriangle, ChevronRight, Plus, Files
} from 'lucide-react'
import { clsx } from 'clsx'
import { useTranslation } from '@/i18n/I18nContext'

const MAX_BYTES = 25 * 1024 * 1024
const ALLOWED = ['.pdf', '.docx', '.xlsx', '.xlsm']

function fileExt(name: string) { return '.' + name.split('.').pop()!.toLowerCase() }

function FileIcon({ name }: { name: string }) {
  const ext = fileExt(name)
  if (ext === '.xlsx' || ext === '.xlsm')
    return <FileSpreadsheet className="w-4 h-4 text-emerald-500 shrink-0" />
  return <FileText className="w-4 h-4 text-blue-500 shrink-0" />
}

function validateFile(file: File): string | null {
  const ext = fileExt(file.name)
  if (!ALLOWED.includes(ext)) return `"${file.name}": unsupported format. Allowed: PDF, DOCX, XLSX.`
  if (file.size > MAX_BYTES) return `"${file.name}": exceeds 25 MB (${(file.size / 1024 / 1024).toFixed(1)} MB).`
  return null
}

interface AuditUploadZoneProps {
  onFilesSelected: (files: File[]) => void
  onTextSubmitted: (text: string) => void
  isUploading: boolean
  error: string | null
}

export function AuditUploadZone({ onFilesSelected, onTextSubmitted, isUploading, error }: AuditUploadZoneProps) {
  const { t } = useTranslation()
  const [dragActive, setDragActive] = useState(false)
  const [pasteOpen, setPasteOpen] = useState(false)
  const [pasteText, setPasteText] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  const addFiles = useCallback((files: FileList | File[]) => {
    const arr = Array.from(files)
    const errors: string[] = []
    const valid: File[] = []
    for (const f of arr) {
      // skip already added
      if (pendingFiles.some(p => p.name === f.name && p.size === f.size)) continue
      const err = validateFile(f)
      if (err) errors.push(err)
      else valid.push(f)
    }
    if (errors.length) { setLocalError(errors.join('\n')); return }
    setLocalError(null)
    setPendingFiles(prev => [...prev, ...valid])
  }, [pendingFiles])

  const handleDrag = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation()
    setDragActive(e.type === 'dragenter' || e.type === 'dragover')
  }
  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files)
  }
  const handleInput = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) addFiles(e.target.files)
    // reset input so same file can be re-selected
    e.target.value = ''
  }
  const removeFile = (idx: number) => setPendingFiles(p => p.filter((_, i) => i !== idx))

  const displayError = localError || error

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-3.5rem)] px-6 py-12">
      <div className="w-full max-w-2xl space-y-5">

        {/* Header */}
        <div className="text-center space-y-1.5">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-blue-600/10 dark:bg-blue-400/10 mb-2">
            <Files className="w-7 h-7 text-blue-600 dark:text-blue-400" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-zinc-100 tracking-tight">
            {t('audit.upload_title')}
          </h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400 max-w-md mx-auto">
            {t('audit.upload_sub')}
          </p>
        </div>

        {/* Drop zone */}
        <div
          onDragEnter={handleDrag} onDragLeave={handleDrag}
          onDragOver={handleDrag} onDrop={handleDrop}
          onClick={() => !isUploading && inputRef.current?.click()}
          className={clsx(
            'relative cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-all duration-200 select-none',
            dragActive
              ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30 scale-[1.01]'
              : 'border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 hover:border-blue-400 dark:hover:border-blue-600 hover:bg-blue-50/40 dark:hover:bg-blue-950/20',
            isUploading && 'pointer-events-none opacity-60'
          )}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,.xlsx,.xlsm"
            multiple
            className="hidden"
            onChange={handleInput}
          />
          <div className="flex flex-col items-center gap-3 pointer-events-none">
            <div className={clsx(
              'w-14 h-14 rounded-2xl flex items-center justify-center transition-colors',
              dragActive ? 'bg-blue-100 dark:bg-blue-900' : 'bg-slate-100 dark:bg-zinc-800'
            )}>
              <Upload className={clsx(
                'w-7 h-7',
                dragActive ? 'text-blue-600 dark:text-blue-400' : 'text-slate-400 dark:text-zinc-500'
              )} />
            </div>
            <div className="space-y-1">
              <p className="text-sm font-semibold text-slate-700 dark:text-zinc-300">
                {dragActive ? t('audit.drop_active') : t('audit.drop_prompt')}
              </p>
              <p className="text-xs text-slate-400 dark:text-zinc-500">
                {t('audit.drop_hint')}
              </p>
              <p className="text-[11px] text-blue-500 dark:text-blue-400 font-medium">
                {t('audit.drop_multiple')}
              </p>
            </div>
          </div>
        </div>

        {/* File chip list */}
        <AnimatePresence>
          {pendingFiles.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className="rounded-2xl border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 overflow-hidden"
            >
              {/* Header row */}
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-100 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-800/50">
                <span className="text-xs font-bold text-slate-500 dark:text-zinc-500 uppercase tracking-wider">
                  {pendingFiles.length} file{pendingFiles.length !== 1 ? 's' : ''} selected
                </span>
                <button
                  onClick={() => { setPendingFiles([]); setLocalError(null) }}
                  className="text-[11px] text-rose-500 hover:text-rose-600 font-semibold"
                >
                  Clear all
                </button>
              </div>

              {/* File rows */}
              {pendingFiles.map((f, i) => (
                <motion.div
                  key={f.name + f.size}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -4 }}
                  transition={{ delay: i * 0.05 }}
                  className="flex items-center gap-3 px-4 py-2.5 border-b last:border-0 border-slate-100 dark:border-zinc-800 hover:bg-slate-50 dark:hover:bg-zinc-800/40 transition-colors"
                >
                  <FileIcon name={f.name} />
                  <span className="flex-1 text-xs text-slate-700 dark:text-zinc-200 truncate font-medium">
                    {f.name}
                  </span>
                  <span className="text-[10px] text-slate-400 dark:text-zinc-600 shrink-0 tabular-nums">
                    {(f.size / 1024 / 1024).toFixed(1)} MB
                  </span>
                  <button
                    onClick={e => { e.stopPropagation(); removeFile(i) }}
                    className="shrink-0 text-slate-300 dark:text-zinc-700 hover:text-rose-500 dark:hover:text-rose-400 transition-colors"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </motion.div>
              ))}

              {/* Add more files button */}
              <button
                onClick={e => { e.stopPropagation(); inputRef.current?.click() }}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-xs text-blue-600 dark:text-blue-400 font-semibold hover:bg-blue-50 dark:hover:bg-blue-950/20 transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                Add more files
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Error banner */}
        <AnimatePresence>
          {displayError && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="flex items-start gap-2 px-4 py-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300"
            >
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span className="flex-1 whitespace-pre-wrap">{displayError}</span>
              <button onClick={() => setLocalError(null)} className="shrink-0">
                <X className="w-3.5 h-3.5" />
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Primary CTA + paste */}
        <div className="flex gap-3">
          <button
            onClick={() => pendingFiles.length > 0 && !isUploading && onFilesSelected(pendingFiles)}
            disabled={pendingFiles.length === 0 || isUploading}
            className={clsx(
              'flex-1 flex items-center justify-center gap-2 px-5 py-3.5 rounded-xl text-sm font-bold transition-all shadow-sm',
              pendingFiles.length > 0 && !isUploading
                ? 'bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white'
                : 'bg-slate-100 dark:bg-zinc-800 text-slate-400 dark:text-zinc-600 cursor-not-allowed shadow-none'
            )}
          >
            {isUploading ? (
              <>
                <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                {t('audit.uploading')}
              </>
            ) : (
              <>
                {pendingFiles.length === 0
                  ? t('audit.audit_files')
                  : pendingFiles.length === 1
                    ? `Audit 1 file`
                    : `Audit ${pendingFiles.length} files`
                }
                <ChevronRight className="w-4 h-4" />
              </>
            )}
          </button>

          <button
            onClick={() => setPasteOpen(true)}
            disabled={isUploading}
            className="flex items-center gap-2 px-4 py-3.5 rounded-xl text-sm font-semibold text-slate-600 dark:text-zinc-400 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700 hover:border-slate-300 dark:hover:border-zinc-600 shadow-sm transition-all"
          >
            <ClipboardPaste className="w-4 h-4" />
            {t('audit.paste_text')}
          </button>
        </div>
      </div>

      {/* Paste modal */}
      <AnimatePresence>
        {pasteOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
            onClick={() => setPasteOpen(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0, y: 10 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={e => e.stopPropagation()}
              className="w-full max-w-2xl bg-white dark:bg-zinc-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-zinc-700 p-6 space-y-4"
            >
              <div className="flex items-center justify-between">
                <h2 className="text-base font-bold text-slate-900 dark:text-zinc-100">
                  {t('audit.paste_title')}
                </h2>
                <button onClick={() => setPasteOpen(false)}>
                  <X className="w-5 h-5 text-slate-400 hover:text-slate-600 dark:hover:text-zinc-300" />
                </button>
              </div>
              <textarea
                autoFocus
                value={pasteText}
                onChange={e => setPasteText(e.target.value)}
                placeholder={t('audit.paste_ph')}
                className="w-full h-64 px-4 py-3 rounded-xl border border-slate-200 dark:border-zinc-700 bg-slate-50 dark:bg-zinc-800 text-sm text-slate-800 dark:text-zinc-200 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setPasteOpen(false)}
                  className="px-4 py-2 rounded-xl text-sm font-semibold text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
                >
                  {t('audit.cancel')}
                </button>
                <button
                  onClick={() => { onTextSubmitted(pasteText.trim()); setPasteOpen(false); setPasteText('') }}
                  disabled={!pasteText.trim()}
                  className={clsx(
                    'px-5 py-2 rounded-xl text-sm font-bold text-white transition-all',
                    pasteText.trim() ? 'bg-blue-600 hover:bg-blue-700' : 'bg-slate-300 dark:bg-zinc-700 cursor-not-allowed'
                  )}
                >
                  {t('audit.audit_text_btn')}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

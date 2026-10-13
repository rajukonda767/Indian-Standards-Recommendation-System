import { useState, useRef, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Plus, Mic, MicOff, ArrowUp, X, FileText, Loader2,
  FileOutput, Sparkles, AlertCircle, HelpCircle, ShieldCheck,
  ExternalLink, Zap, ChevronDown, ArrowRight, Volume2, VolumeX,
  Copy, Check
} from 'lucide-react'
import { Shell } from '@/components/layout/Shell'
import { useTranslation } from '@/i18n/I18nContext'
import {
  getRecommendations,
  type RecommendResponse,
  type PrimaryCandidate,
  type DisambiguationOption
} from '@/lib/api'
import { savePreviousRecommendation } from '@/utils/storage'
import { clsx } from 'clsx'
import { SkeletonCard } from './recommend/SkeletonCard'
import { AlliedStandardsView } from './recommend/AlliedStandardsView'

// ── Time-aware greeting key ─────────────────────────────────────────────────
function getGreetingKey() {
  const h = new Date().getHours()
  if (h < 12) return 'recommend.greeting_morning'
  if (h < 17) return 'recommend.greeting_afternoon'
  return 'recommend.greeting_evening'
}

// ── Extract clean user query from Groq condition heading ────────────────────
function extractCleanQueryFromDifferentiator(diffText: string, fallbackTitle?: string): string {
  if (!diffText) return fallbackTitle || ''
  let clean = diffText.trim().replace(/:+$/, '').trim()
  const prefixRegex = /^if\s+(you\s+require|your\s+specification\s+(calls\s+for|requires)|(the\s+)?application\s+(requires|is\s+for)|you\s+need|you\s+are\s+procuring|procuring|technical\s+requirements\s+call\s+for|requirements\s+call\s+for|design\s+specifications\s+mandate|structural\s+design\s+mandates|your\s+project\s+requires|working\s+voltage\s+is|grade\s+requirement\s+is|structural\s+section\s+is\s+a|structural\s+section\s+is|pipes\s+are\s+intended\s+for|specifications\s+require|your\s+electrical\s+installation\s+operates\s+at)\s+/i
  clean = clean.replace(prefixRegex, '').trim()
  clean = clean.replace(/^if\s+/i, '').trim()
  return clean || fallbackTitle || ''
}

// ── Derive differentiating "If X instead of Y" phrasing for alternative candidates ─
function deriveAlternativePhrase(primary: PrimaryCandidate, alt: PrimaryCandidate): string {
  const pTitle = primary.title.toLowerCase()
  const aTitle = alt.title.toLowerCase()

  // Voltage/rating differentiator
  const voltageMatch = aTitle.match(/(\d[\d.]*\s*k?v)/i)
  const primaryVoltageMatch = pTitle.match(/(\d[\d.]*\s*k?v)/i)
  if (voltageMatch && primaryVoltageMatch && voltageMatch[1] !== primaryVoltageMatch[1]) {
    return `If working voltage is ${voltageMatch[1].toUpperCase()} instead of ${primaryVoltageMatch[1].toUpperCase()}:`
  }

  // XLPE vs PVC insulation
  if (aTitle.includes('xlpe') && !pTitle.includes('xlpe')) {
    return 'If your specification requires cross-linked polyethylene (XLPE) insulation instead of PVC:'
  }
  if (pTitle.includes('xlpe') && !aTitle.includes('xlpe')) {
    return 'If your specification requires PVC insulation instead of XLPE:'
  }

  // Grade differentiator (TMT, Fe-500, 415, 550, etc.)
  const gradeMatch = aTitle.match(/fe[- ]?(\d{3})/i) || aTitle.match(/grade\s+(\d+)/i) || aTitle.match(/(\d{3}[a-z]?)\s+grade/i)
  const primaryGradeMatch = pTitle.match(/fe[- ]?(\d{3})/i) || pTitle.match(/grade\s+(\d+)/i)
  if (gradeMatch && primaryGradeMatch && gradeMatch[0] !== primaryGradeMatch[0]) {
    return `If grade requirement is ${gradeMatch[0].toUpperCase()} instead of ${primaryGradeMatch[0].toUpperCase()}:`
  }

  // Pipe/structural section application
  if (aTitle.includes('channel') && !pTitle.includes('channel')) return 'If structural section is a steel channel, not angle:'
  if (aTitle.includes('beam') && !pTitle.includes('beam')) return 'If structural section is a steel beam or joist:'
  if (aTitle.includes('corrugated') && !pTitle.includes('corrugated')) return 'If drainage design specifies single-wall corrugated pipes:'
  if (aTitle.includes('casing') || aTitle.includes('borewell') || aTitle.includes('tubewell')) return 'If you are procuring PVC screen and casing pipes for borewells/tubewells:'
  if (aTitle.includes('column pipe') || aTitle.includes('threaded column')) return 'If you require threaded column pipes for submersible pumps:'
  if (aTitle.includes('soil') || aTitle.includes('waste') || aTitle.includes('rainwater')) return 'If you need UPVC pipes for indoor soil, waste, and rainwater discharge:'
  if (aTitle.includes('pressure') && !pTitle.includes('pressure') && pTitle.includes('non-pressure')) return 'If application requires pressurized water transmission pipes:'
  if (aTitle.includes('non-pressure') && !pTitle.includes('non-pressure')) return 'If application is for non-pressure underground drainage/sewerage:'

  // Cement grade
  if (aTitle.includes('53') && !pTitle.includes('53')) return 'If structural design mandates 53-grade high-strength Portland cement:'
  if (aTitle.includes('43') && !pTitle.includes('43')) return 'If structural design mandates 43-grade Ordinary Portland cement:'
  if (aTitle.includes('pozzolana') && !pTitle.includes('pozzolana')) return 'If you are procuring Portland Pozzolana Cement (PPC) for durable concrete:'
  if (aTitle.includes('slag') && !pTitle.includes('slag')) return 'If requirements call for Portland Slag Cement (PSC):'

  // Underground / overhead
  if (aTitle.includes('underground') && !pTitle.includes('underground')) return 'If cables are for heavy-duty underground distribution:'
  if (aTitle.includes('aerial') && !pTitle.includes('aerial')) return 'If cables are for overhead/aerial bunched distribution:'

  // Fallback with standard title context
  const cleanTitle = alt.title.split(' - ')[0].split('—')[0].trim()
  return `If technical requirements call for ${cleanTitle}:`
}

// ── Omnibar ─────────────────────────────────────────────────────────────────
interface OmnibarProps {
  onSubmit: (text: string, file: File | null) => void
  loading: boolean
  value: string
  onChange: (v: string) => void
}

function Omnibar({ onSubmit, loading, value, onChange }: OmnibarProps) {
  const { t, lang } = useTranslation()
  const [file, setFile] = useState<File | null>(null)
  const [listening, setListening] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const recogRef = useRef<any>(null)

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(Math.max(el.scrollHeight, 64), 180)}px`
  }, [value])

  // Speech recognition
  useEffect(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SR) return
    const r = new SR()
    r.continuous = true
    r.interimResults = true
    r.lang = lang === 'hi' ? 'hi-IN' : lang === 'te' ? 'te-IN' : 'en-IN'
    r.onresult = (e: any) => {
      let transcript = ''
      for (let i = e.resultIndex; i < e.results.length; i++) transcript += e.results[i][0].transcript
      onChange(value ? `${value} ${transcript}` : transcript)
    }
    r.onend = () => setListening(false)
    r.onerror = () => setListening(false)
    recogRef.current = r
    return () => { try { r.abort() } catch { /* noop */ } }
  }, [lang, value, onChange])

  const toggleVoice = () => {
    if (!recogRef.current) return
    if (listening) { recogRef.current.stop(); setListening(false) }
    else { try { recogRef.current.start(); setListening(true) } catch { /* noop */ } }
  }

  const handleSubmit = () => {
    if (loading || (!value.trim() && !file)) return
    onSubmit(value.trim(), file)
  }

  return (
    <div className={clsx(
      'w-full max-w-2xl rounded-2xl border bg-white dark:bg-zinc-900',
      'border-slate-200 dark:border-zinc-700 shadow-sm',
      'focus-within:shadow-md focus-within:border-blue-500/40 dark:focus-within:border-blue-500/30 transition-all'
    )}>
      <input ref={fileRef} type="file" accept=".pdf,.doc,.docx" className="hidden"
        onChange={e => setFile(e.target.files?.[0] ?? null)} />

      {file && (
        <div className="px-4 pt-3 pb-0">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-400 text-xs font-medium max-w-[220px]">
            <FileText className="w-3 h-3 shrink-0" />
            <span className="truncate">{file.name}</span>
            <button onClick={() => setFile(null)} className="ml-0.5 hover:text-blue-900 dark:hover:text-blue-200 shrink-0">
              <X className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}

      <div className="px-4 pt-4 pb-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit() } }}
          placeholder={t('recommend.placeholder') || 'Enter procurement specifications, technical requirements, or colloquial terms (e.g. GI pipe, PVC cable 1100V, cement bags 50kg)...'}
          rows={3}
          className="w-full bg-transparent resize-none outline-none text-sm text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-zinc-500 leading-relaxed min-h-[72px]"
        />
      </div>

      <div className="flex items-center justify-between px-3 pb-3 gap-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => fileRef.current?.click()}
            className={clsx(
              'inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors',
              'border border-dashed border-slate-300 dark:border-zinc-600',
              'text-slate-500 dark:text-zinc-400 hover:text-slate-700 dark:hover:text-zinc-200',
              'hover:border-slate-400 dark:hover:border-zinc-500 hover:bg-slate-50 dark:hover:bg-zinc-800/60'
            )}
          >
            <Plus className="w-3.5 h-3.5" />
            {t('recommend.upload')}
          </button>
          {listening && (
            <span className="flex items-center gap-1.5 text-[11px] text-rose-500 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
              Listening
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={toggleVoice}
            className={clsx(
              'w-8 h-8 flex items-center justify-center rounded-full transition-all',
              listening
                ? 'bg-rose-500 text-white'
                : 'text-slate-400 dark:text-zinc-500 hover:text-slate-700 dark:hover:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800'
            )}
            title="Voice input"
          >
            {listening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>

          <button
            onClick={handleSubmit}
            disabled={loading || (!value.trim() && !file)}
            className={clsx(
              'inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-semibold transition-all',
              loading || (!value.trim() && !file)
                ? 'bg-slate-200 dark:bg-zinc-800 text-slate-400 dark:text-zinc-600 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white shadow-sm active:scale-95'
            )}
          >
            {loading
              ? <><Loader2 className="w-3.5 h-3.5 animate-spin" />{t('recommend.submitting')}</>
              : <><ArrowUp className="w-3.5 h-3.5" />{t('recommend.submit')}</>
            }
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Disambiguation Modal (Direct interactive typing at option 4 inside modal) ──
interface DisambiguationModalProps {
  question: string
  options: DisambiguationOption[]
  customOptionText?: string | null
  onSelect: (option: DisambiguationOption) => void
  onCustomSubmit: (customText: string) => void
  onClose: () => void
}

function stripISReferences(text?: string | null): string {
  if (!text) return ''
  return text
    .replace(/\s*\(\s*IS\b[^)]*\)/gi, '')
    .replace(/\bIS\s*[:\d][\w\s/().:-]*/gi, '')
    .replace(/\s{2,}/g, ' ')
    .replace(/\s+([?,.;])/g, '$1')
    .trim()
}

function DisambiguationModal({
  question,
  options,
  customOptionText,
  onSelect,
  onCustomSubmit,
  onClose
}: DisambiguationModalProps) {
  const [customInput, setCustomInput] = useState('')

  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  const cleanQuestion = stripISReferences(question) || 'Which specific specification or application do you need?'
  const cleanCustomText = stripISReferences(customOptionText) || 'Other application or custom specification:'

  return createPortal(
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
        background: 'rgba(2, 6, 23, 0.65)',
        backdropFilter: 'blur(3px)',
        WebkitBackdropFilter: 'blur(3px)',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 16 }}
        transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
        style={{ width: '100%', maxWidth: '34rem' }}
        className="bg-white dark:bg-zinc-900 rounded-2xl shadow-2xl border border-slate-200/80 dark:border-zinc-700/80 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="px-5 pt-5 pb-4 border-b border-slate-100 dark:border-zinc-800 flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-100 dark:bg-amber-900/60 border border-amber-200 dark:border-amber-700 flex items-center justify-center shrink-0 mt-0.5">
              <HelpCircle className="w-5 h-5 text-amber-700 dark:text-amber-300" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-white mb-1">
                Specification Clarification Needed
              </h2>
              <p className="text-xs text-slate-600 dark:text-zinc-400 leading-relaxed">
                {cleanQuestion}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-zinc-300 transition-colors"
            title="Dismiss"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Options (Clean specification options without any standard numbers or IS mentions) */}
        <div className="px-4 py-3 space-y-2 max-h-64 overflow-y-auto">
          {options.map((opt, idx) => {
            const cleanLabel = stripISReferences(opt.label) || opt.label
            return (
              <button
                key={idx}
                onClick={() => onSelect(opt)}
                className={clsx(
                  'w-full text-left px-4 py-3 rounded-xl border transition-all group',
                  'bg-slate-50 dark:bg-zinc-800/60 border-slate-200 dark:border-zinc-700',
                  'hover:bg-blue-50 dark:hover:bg-blue-950/40 hover:border-blue-300 dark:hover:border-blue-700',
                  'active:scale-[0.99] cursor-pointer'
                )}
              >
                <p className="text-sm font-semibold text-slate-800 dark:text-zinc-100 group-hover:text-blue-800 dark:group-hover:text-blue-300 leading-snug">
                  {cleanLabel}
                </p>
              </button>
            )
          })}
        </div>

        {/* 4th Option: Direct Interactive Typing directly inside the modal */}
        <div className="px-4 pb-4 pt-3 border-t border-slate-100 dark:border-zinc-800 bg-slate-50/50 dark:bg-zinc-900/50">
          <label className="block text-[11px] font-bold text-slate-700 dark:text-zinc-300 mb-1.5">
            {cleanCustomText}
          </label>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (customInput.trim()) onCustomSubmit(customInput.trim())
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              placeholder="Type specific application, grade, or dimensions directly here..."
              className="flex-1 bg-white dark:bg-zinc-800 border border-slate-300 dark:border-zinc-700 rounded-xl px-3.5 py-2 text-xs text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-zinc-500 outline-none focus:border-blue-500 dark:focus:border-blue-400 transition-all shadow-inner"
              autoFocus
            />
            <button
              type="submit"
              disabled={!customInput.trim()}
              className={clsx(
                'inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold shrink-0 transition-all',
                customInput.trim()
                  ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-sm active:scale-95 cursor-pointer'
                  : 'bg-slate-200 dark:bg-zinc-800 text-slate-400 dark:text-zinc-600 cursor-not-allowed'
              )}
            >
              <span>Recommend</span>
              <ArrowUp className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>
      </motion.div>
    </div>,
    document.body
  )
}

// ── Primary Result View — ONE prominent card + collapsible alternative specifications ─
interface PrimaryResultViewProps {
  candidates: PrimaryCandidate[]
  onViewIS: (sn: string) => void
  onViewSuperseded: (sn: string) => void
  onSelectAlternative: (cleanQuery: string, standardNumber: string) => void
}

function PrimaryResultView({ candidates, onViewIS, onViewSuperseded, onSelectAlternative }: PrimaryResultViewProps) {
  const primary = candidates[0]
  const alternatives = candidates.slice(1)
  const [altOpen, setAltOpen] = useState(false)
  const { t, lang } = useTranslation()
  const [speakingWhy, setSpeakingWhy] = useState(false)
  const [voiceNotice, setVoiceNotice] = useState(false)

  // Check if the OS has a voice for the current lang (Telugu/Hindi may not be installed on Windows)
  const hasVoiceForLang = useCallback(() => {
    if (lang === 'en') return true
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return false
    const voices = window.speechSynthesis.getVoices()
    const prefix = lang === 'hi' ? 'hi' : 'te'
    return voices.some(v => v.lang.replace('_', '-').toLowerCase().startsWith(prefix))
  }, [lang])

  const toggleSpeakWhy = () => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window) || !primary?.why) return
    if (speakingWhy) {
      window.speechSynthesis.cancel()
      setSpeakingWhy(false)
      return
    }
    // Show notice if no regional voice installed, but still attempt playback in English fallback
    if (!hasVoiceForLang()) {
      setVoiceNotice(true)
      return
    }
    setVoiceNotice(false)
    window.speechSynthesis.cancel()
    const targetLangCode = lang === 'hi' ? 'hi-IN' : lang === 'te' ? 'te-IN' : 'en-IN'
    const utterance = new SpeechSynthesisUtterance(primary.why.replace(/[*#_~`>]/g, ''))
    utterance.lang = targetLangCode
    try {
      const voices = window.speechSynthesis.getVoices()
      const langPrefix = targetLangCode.toLowerCase().slice(0, 2)
      const matchingVoice = voices.find(v => v.lang.replace('_', '-').toLowerCase().startsWith(langPrefix))
      if (matchingVoice) utterance.voice = matchingVoice
    } catch { /* noop */ }
    utterance.rate = 0.95
    utterance.onend = () => setSpeakingWhy(false)
    utterance.onerror = () => setSpeakingWhy(false)
    setSpeakingWhy(true)
    window.speechSynthesis.speak(utterance)
  }

  // Reset notice when language changes
  useEffect(() => { setVoiceNotice(false) }, [lang])

  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel()
      }
    }
  }, [])

  if (!primary) return null

  const cert = primary.certification

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
    >
      {/* ── 1. Top Recommended Standard ── */}
      <div className="mb-2">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs font-bold text-slate-600 dark:text-zinc-300 uppercase tracking-wider">
            {t('recommend.tab_primary') || 'Recommended Standard'}
          </span>
        </div>

        <div className={clsx(
          'rounded-2xl border bg-white dark:bg-zinc-900 p-5',
          'border-blue-200 dark:border-blue-800/60',
          'shadow-sm ring-1 ring-blue-100 dark:ring-blue-900/30'
        )}>
          {/* Header row */}
          <div className="flex items-start justify-between gap-3 mb-3">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-lg font-bold text-slate-900 dark:text-white tracking-tight">
                {primary.standard_number}
              </span>
              <span className={clsx(
                'inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium',
                primary.is_status_label.toLowerCase() === 'current' || primary.is_status_label.toLowerCase() === 'published'
                  ? 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400 ring-1 ring-emerald-200 dark:ring-emerald-800'
                  : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 ring-1 ring-zinc-300 dark:ring-zinc-700'
              )}>
                {primary.is_status_label}
              </span>
              {primary.superseded_by && (
                <button
                  onClick={() => onViewSuperseded(primary.superseded_by!)}
                  className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 ring-1 ring-rose-300 dark:ring-rose-800 hover:underline cursor-pointer"
                >
                  Superseded → {primary.superseded_by}
                </button>
              )}
            </div>
            <div className="shrink-0 flex items-center gap-1.5">
              <span className="text-[11px] text-slate-400 dark:text-zinc-500 font-medium">{t('recommend.confidence') || 'Confidence'}</span>
              <span className={clsx(
                'inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold tabular-nums',
                primary.confidence >= 80
                  ? 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400 ring-1 ring-emerald-200 dark:ring-emerald-800'
                  : 'bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-400 ring-1 ring-amber-200 dark:ring-amber-800'
              )}>
                {primary.confidence.toFixed(1)}% {t('recommend.match') || 'match'}
              </span>
            </div>
          </div>

          {/* Title */}
          <p className="text-sm font-semibold text-slate-800 dark:text-zinc-200 mb-2.5 leading-snug">
            {primary.title}
          </p>

          {/* Conflict warning */}
          {primary.conflict_warning && (
            <div className="mb-3 px-3 py-2 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              <p className="text-xs text-amber-800 dark:text-amber-300 leading-relaxed font-medium">
                {primary.conflict_warning}
              </p>
            </div>
          )}

          {/* Grounded Why Text with TTS Listen Button */}
          <div className="flex items-start gap-2 mb-4">
            <p className="text-xs text-slate-600 dark:text-zinc-400 leading-relaxed flex-1">
              <span className="font-semibold text-slate-700 dark:text-zinc-300">
                {t('recommend.why') ? `${t('recommend.why')}: ` : 'Why: '}
              </span>
              {primary.why}
            </p>
            <button
              type="button"
              onClick={toggleSpeakWhy}
              className={clsx(
                'shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium transition-all cursor-pointer',
                speakingWhy
                  ? 'bg-blue-100 dark:bg-blue-950/70 text-blue-700 dark:text-blue-300 ring-1 ring-blue-300 dark:ring-blue-700'
                  : 'text-slate-400 hover:text-slate-700 dark:text-zinc-500 dark:hover:text-zinc-200 hover:bg-slate-100 dark:hover:bg-zinc-800'
              )}
              title={speakingWhy ? 'Stop reading' : 'Read why aloud'}
            >
              {speakingWhy ? (
                <>
                  <VolumeX className="w-3 h-3 text-blue-600 dark:text-blue-400 animate-pulse" />
                  <span>{lang === 'te' ? 'ఆపు' : lang === 'hi' ? 'रोकें' : 'Stop'}</span>
                </>
              ) : (
                <>
                  <Volume2 className="w-3 h-3" />
                  <span>{lang === 'te' ? 'వినండి' : lang === 'hi' ? 'सुनें' : 'Listen'}</span>
                </>
              )}
            </button>
          </div>

          {/* Voice-not-available notice (shown when OS has no Telugu/Hindi voice) */}
          {voiceNotice && lang !== 'en' && (
            <div className="mb-3 px-3 py-2 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 flex items-start gap-2">
              <AlertCircle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              <p className="text-[11px] text-amber-800 dark:text-amber-300 leading-relaxed flex-1">
                {lang === 'te'
                  ? 'తెలుగు వాయిస్ ఇన్‌స్టాల్ కాలేదు. Windows Settings → Time & Language → Speech → Manage voices లో ఇన్‌స్టాల్ చేయండి.'
                  : 'हिन्दी आवाज़ इंस्टॉल नहीं है। Windows Settings → Time & Language → Speech → Manage voices में जाकर इंस्टॉल करें।'
                }
              </p>
              <button
                type="button"
                onClick={() => setVoiceNotice(false)}
                className="text-amber-500 hover:text-amber-700 dark:text-amber-400 dark:hover:text-amber-200 shrink-0 mt-0.5"
                title="Dismiss"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          )}

          {/* Bottom row */}
          <div className="flex items-center justify-between flex-wrap gap-2 pt-3 border-t border-slate-100 dark:border-zinc-800/80">
            <div className="flex items-center gap-2 flex-wrap">
              {cert.verified ? (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                  <span>{cert.value || 'Mandatory ISI Certification'}</span>
                  {cert.qco_ministry && (
                    <span className="text-[10px] text-emerald-600/80 dark:text-emerald-400/80">({cert.qco_ministry.split(' ')[0]})</span>
                  )}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  <span>Certification status not verified — check BIS portal</span>
                </span>
              )}
              {cert.source_url && (
                <a href={cert.source_url} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium text-slate-600 dark:text-zinc-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors">
                  BIS Portal <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
            <button
              onClick={() => onViewIS(primary.standard_number)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold shrink-0 transition-colors border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-950 cursor-pointer"
            >
              View Full IS <ExternalLink className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* ── 2. Other Specifications Considered (Collapsible Accordion) ── */}
      {alternatives.length > 0 && (
        <div className="mt-5 pt-4 border-t border-slate-200 dark:border-zinc-800">
          {/* Collapsible Trigger Bar */}
          <button
            type="button"
            onClick={() => setAltOpen(!altOpen)}
            aria-expanded={altOpen}
            className={clsx(
              'w-full flex items-center justify-between px-4 py-3 rounded-xl border transition-all text-left cursor-pointer select-none group',
              altOpen
                ? 'bg-blue-50/60 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800/80 shadow-2xs'
                : 'bg-white dark:bg-zinc-900/90 border-slate-200 dark:border-zinc-800 hover:border-slate-300 dark:hover:border-zinc-700 hover:bg-slate-50/80 dark:hover:bg-zinc-800/50'
            )}
          >
            <div className="flex items-center gap-2.5">
              <div className="w-2 h-2 rounded-full bg-blue-500" />
              <span className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-zinc-200">
                Other specifications this could match
              </span>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300 tabular-nums">
                {alternatives.length}
              </span>
            </div>

            <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-zinc-400">
              <span className="hidden sm:inline text-[11px] font-medium group-hover:text-slate-700 dark:group-hover:text-zinc-200">
                {altOpen ? 'Tap to close' : 'Tap to expand'}
              </span>
              <ChevronDown
                className={clsx(
                  'w-4 h-4 text-slate-400 dark:text-zinc-500 transition-transform duration-200',
                  altOpen && 'transform rotate-180 text-blue-600 dark:text-blue-400'
                )}
              />
            </div>
          </button>

          {/* Accordion Content */}
          <AnimatePresence>
            {altOpen && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
                className="overflow-hidden"
              >
                <div className="pt-3">
                  <p className="text-[11px] text-slate-500 dark:text-zinc-400 mb-3 px-1">
                    Alternative specifications if your project requires different grades, applications, or technical conditions:
                  </p>

                  <div className="space-y-3">
                    {alternatives.map((alt) => {
                      const conditionText = alt.differentiator || deriveAlternativePhrase(primary, alt)
                      const cleanQuery = extractCleanQueryFromDifferentiator(conditionText, alt.title)

                      return (
                        <div
                          key={alt.standard_number}
                          onClick={() => onSelectAlternative(cleanQuery, alt.standard_number)}
                          className={clsx(
                            'group relative rounded-xl border p-4 transition-all cursor-pointer',
                            'border-slate-200 dark:border-zinc-800/90 bg-white dark:bg-zinc-900/90 shadow-2xs',
                            'hover:border-blue-400 dark:hover:border-blue-600 hover:shadow-md hover:bg-blue-50/20 dark:hover:bg-blue-950/20 active:scale-[0.995]'
                          )}
                          role="button"
                          tabIndex={0}
                          title={`Click to recommend: ${cleanQuery}`}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault()
                              onSelectAlternative(cleanQuery, alt.standard_number)
                            }
                          }}
                        >
                          {/* BOLD data-driven condition as distinct sub-heading */}
                          <div className="mb-2 flex items-start justify-between gap-3">
                            <p className="text-xs font-bold text-blue-700 dark:text-blue-400 leading-snug group-hover:text-blue-800 dark:group-hover:text-blue-300 transition-colors">
                              {conditionText}
                            </p>
                            <span className="shrink-0 inline-flex items-center gap-1 text-[11px] font-semibold text-blue-600 dark:text-blue-400 group-hover:translate-x-0.5 transition-transform">
                              <span>Recommend</span>
                              <ArrowRight className="w-3 h-3" />
                            </span>
                          </div>

                          {/* Standard specification details directly below the condition in the same single box */}
                          <div className="flex items-start justify-between gap-3 pt-2.5 border-t border-slate-100 dark:border-zinc-800/80">
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2 flex-wrap mb-1">
                                <span className="text-sm font-bold text-slate-900 dark:text-white tracking-tight">
                                  → {alt.standard_number}
                                </span>
                                <span className="inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 ring-1 ring-slate-200 dark:ring-zinc-700">
                                  {alt.is_status_label}
                                </span>
                                <span className="text-[11px] text-slate-400 dark:text-zinc-500 font-mono">
                                  {alt.confidence.toFixed(1)}% match
                                </span>
                              </div>
                              <p className="text-xs text-slate-600 dark:text-zinc-400 leading-relaxed line-clamp-2">
                                {alt.title}
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation()
                                onViewIS(alt.standard_number)
                              }}
                              title="View full standard details"
                              className="shrink-0 inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-500 dark:text-zinc-400 hover:text-blue-700 dark:hover:text-blue-400 hover:bg-slate-100 dark:hover:bg-zinc-800 border border-slate-200 dark:border-zinc-700 transition-colors cursor-pointer"
                            >
                              <span>View IS</span>
                              <ExternalLink className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </motion.div>
  )
}

// ── Certification Card for Certifications Tab ───────────────────────────────
function CertSummaryCard({ candidate }: { candidate: PrimaryCandidate }) {
  const cert = candidate.certification
  const schemeName = cert.verified && cert.value
    ? (cert.value.includes('ISI') || cert.value === 'Mandatory' || cert.value === 'Voluntary')
      ? 'BIS ISI Mark Certification — Scheme I'
      : `BIS Certification — ${cert.value}`
    : null

  return (
    <div className="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 hover:border-slate-300 dark:hover:border-zinc-700 hover:shadow-sm transition-all">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3.5">
          <div className={clsx(
            'w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border',
            cert.verified
              ? 'bg-emerald-50 dark:bg-emerald-950/50 border-emerald-200 dark:border-emerald-800 text-emerald-600 dark:text-emerald-400'
              : 'bg-amber-50 dark:bg-amber-950/50 border-amber-200 dark:border-amber-800 text-amber-600 dark:text-amber-400'
          )}>
            {cert.verified ? <ShieldCheck className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          </div>
          <div>
            {cert.verified ? (
              <>
                <p className="text-sm font-bold text-slate-900 dark:text-white mb-0.5">
                  {schemeName}
                </p>
                <p className="text-xs text-slate-500 dark:text-zinc-400 mb-1">
                  Bureau of Indian Standards
                </p>
                <p className="text-xs text-slate-600 dark:text-zinc-300 font-medium mb-1.5">
                  {candidate.standard_number} — {candidate.title}
                </p>
              </>
            ) : (
              <>
                <p className="text-sm font-bold text-slate-900 dark:text-white mb-0.5">
                  Certification Status Not Verified
                </p>
                <p className="text-xs text-slate-600 dark:text-zinc-300 font-medium mb-1.5">
                  {candidate.standard_number} — {candidate.title}
                </p>
              </>
            )}
            {cert.qco_ministry && (
              <p className="text-xs text-slate-500 dark:text-zinc-400 leading-relaxed">
                Mandatory Quality Control Order (QCO) issued by: <span className="font-semibold text-slate-700 dark:text-zinc-300">{cert.qco_ministry}</span>
              </p>
            )}
          </div>
        </div>

        <a
          href={cert.source_url || 'https://www.bis.gov.in/certification-and-testing/certification/product-certification/'}
          target="_blank"
          rel="noreferrer"
          className={clsx(
            'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold shrink-0 transition-colors',
            cert.source_url
              ? 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/50 hover:bg-blue-100 dark:hover:bg-blue-950 border border-blue-200 dark:border-blue-800'
              : 'text-slate-500 dark:text-zinc-400 bg-slate-50 dark:bg-zinc-800 hover:bg-slate-100 dark:hover:bg-zinc-700 border border-slate-200 dark:border-zinc-700'
          )}
        >
          <span>BIS Portal</span>
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </div>
    </div>
  )
}

const SESSION_REC_KEY = 'ss_active_rec'

interface CachedRecSession {
  query: string
  response: RecommendResponse
  activeTab: 'primary' | 'aligned' | 'certification'
  lang: string
}

function getStoredRecSession(): CachedRecSession | null {
  try {
    const raw = sessionStorage.getItem(SESSION_REC_KEY)
    if (!raw) return null
    return JSON.parse(raw) as CachedRecSession
  } catch {
    return null
  }
}

function setStoredRecSession(data: CachedRecSession | null) {
  try {
    if (!data) {
      sessionStorage.removeItem(SESSION_REC_KEY)
    } else {
      sessionStorage.setItem(SESSION_REC_KEY, JSON.stringify(data))
    }
  } catch {
    /* ignore storage quota errors */
  }
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export function RecommendPage() {
  const { t, lang } = useTranslation()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const preloadQuery = searchParams.get('query')
  const initialCached = getStoredRecSession()

  // Restore cached session if valid (prevents resetting to empty screen on back-navigation)
  const [response, setResponse] = useState<RecommendResponse | null>(() => {
    if (preloadQuery && initialCached?.query !== preloadQuery) return null
    return initialCached?.response ?? null
  })
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'primary' | 'aligned' | 'certification'>(() => {
    return initialCached?.activeTab ?? 'primary'
  })
  const [queryText, setQueryText] = useState(() => {
    return preloadQuery || initialCached?.query || ''
  })
  const [lastQuery, setLastQuery] = useState(() => {
    return initialCached?.query || ''
  })
  const [botOpen, setBotOpen] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)

  // When language changes and there's an active result, silently re-fetch in new language
  // so the Why text and labels refresh without resetting to the empty home screen
  useEffect(() => {
    if (!lastQuery) return          // nothing searched yet — do nothing
    handleSubmit(lastQuery, null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang])

  useEffect(() => {
    if (preloadQuery) {
      const cached = getStoredRecSession()
      if (cached?.query === preloadQuery && cached?.response) {
        // Already loaded via lazy initialization
        return
      }
      setQueryText(preloadQuery)
      handleSubmit(preloadQuery, null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSubmit = useCallback(async (query: string, _file: File | null, selectedOption?: string) => {
    if (!query && !_file) return
    const nextTab = query !== lastQuery ? 'primary' : activeTab
    if (query !== lastQuery) setActiveTab('primary')
    setLastQuery(query)
    setErrorMessage(null)
    setLoading(true)
    setShowModal(false)

    try {
      const data = await getRecommendations({ query, selected_option: selectedOption, language: lang })
      setResponse(data)
      setStoredRecSession({
        query,
        response: data,
        activeTab: nextTab,
        lang,
      })
      setSearchParams({ query }, { replace: true })
      if (data.status === 'ambiguous') setShowModal(true)

      const allied = data.allied || {}
      const totalAllied = (
        (allied.normative_references?.length || 0) + (allied.test_methods?.length || 0) +
        (allied.terminology?.length || 0) + (allied.safety_standards?.length || 0) +
        (allied.installation_standards?.length || 0) + (allied.related_product_standards?.length || 0)
      )

      if (data.status === 'ok' && data.primary?.[0]) {
        savePreviousRecommendation({
          query: selectedOption ? `${query} (${selectedOption.split('—')[0].trim()})` : query,
          standardsCount: data.primary.length + totalAllied,
          primaryStandard: data.primary[0].standard_number,
          primaryTitle: data.primary[0].title,
          status: data.primary[0].is_status_label,
          confidence: Math.round(data.primary[0].confidence),
          results: data.primary,
        })
      }
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to retrieve BIS standard recommendations.')
    } finally {
      setLoading(false)
    }
  }, [lang, lastQuery, activeTab, setSearchParams])

  const handleSelectDisambiguation = (option: DisambiguationOption) => {
    setQueryText(option.rewritten_query)
    setShowModal(false)
    handleSubmit(option.rewritten_query, null, option.standard_number)
  }

  const handleCustomSubmit = (customQuery: string) => {
    setQueryText(customQuery)
    setShowModal(false)
    handleSubmit(customQuery, null)
  }

  const handleSelectAlternative = (cleanQuery: string, standardNumber: string) => {
    setQueryText(cleanQuery)
    handleSubmit(cleanQuery, null, standardNumber)
  }

  const handleTabChange = useCallback((newTab: 'primary' | 'aligned' | 'certification') => {
    setActiveTab(newTab)
    const cached = getStoredRecSession()
    if (cached) {
      setStoredRecSession({ ...cached, activeTab: newTab })
    }
  }, [])

  const handleResetSearch = useCallback(() => {
    setStoredRecSession(null)
    setResponse(null)
    setErrorMessage(null)
    setQueryText('')
    setLastQuery('')
    setActiveTab('primary')
    setSearchParams({}, { replace: true })
  }, [setSearchParams])

  const [copiedExport, setCopiedExport] = useState(false)

  const handleExportClipboard = async () => {
    if (!response || !response.primary?.[0]) return
    const primary = response.primary[0]
    const cert = primary.certification
    const allied = response.allied || {
      normative_references: [],
      test_methods: [],
      terminology: [],
      safety_standards: [],
      installation_standards: [],
      related_product_standards: [],
    }

    // 1. query = query in text box
    const currentQuery = queryText.trim() || lastQuery.trim() || response.extracted_spec?.product_category || ''

    // 2. primary standard= IS NO:YEAR only
    const primaryStandard = primary.standard_number?.trim() || ''

    // 3. allgined standards= testing :IS's numbers only,installation : IS 's numbers only like this if any thing is 0 dont mention them
    const categoryParts: string[] = []

    const addCategory = (label: string, items?: any[]) => {
      const numbers = (items || [])
        .map(item => (typeof item === 'string' ? item : item.standard_number)?.trim())
        .filter(Boolean)
      if (numbers.length > 0) {
        categoryParts.push(`${label} : ${numbers.join(', ')}`)
      }
    }

    addCategory('testing', allied.test_methods)
    addCategory('installation', allied.installation_standards)
    addCategory('normative', allied.normative_references)
    addCategory('safety', allied.safety_standards)
    addCategory('terminology', allied.terminology)
    addCategory('related products', allied.related_product_standards)

    const alignedText = categoryParts.length > 0 ? categoryParts.join(', ') : 'None'

    // 4. certifications : ___ Certificate or Not specifies check in BIS portal link
    let certText = ''
    if (cert && cert.verified) {
      let val = (cert.value || 'Mandatory ISI Certificate').trim()
      if (!/certificate/i.test(val)) {
        val = val.replace(/certification/i, 'Certificate')
        if (!/certificate/i.test(val)) {
          val = `${val} Certificate`
        }
      }
      if (cert.qco_ministry) {
        val += ` (${cert.qco_ministry})`
      }
      certText = val
    } else {
      const portalUrl = cert?.source_url || 'https://standardsbis.bsbedge.com/'
      certText = `Not specifies check in BIS portal link (${portalUrl})`
    }

    const textToCopy = [
      `query = ${currentQuery}`,
      `primary standard= ${primaryStandard}`,
      `allgined standards= ${alignedText}`,
      `certifications : ${certText}`,
    ].join('\n')

    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(textToCopy)
      } else {
        const textarea = document.createElement('textarea')
        textarea.value = textToCopy
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
      }
      setCopiedExport(true)
      setTimeout(() => setCopiedExport(false), 2500)
    } catch (err) {
      console.error('Failed to copy recommendation to clipboard:', err)
    }
  }

  const handleExportPDF = async () => {
    if (!response || !response.primary?.[0]) return
    const { jsPDF } = await import('jspdf')
    const doc = new jsPDF()
    const primary = response.primary[0]
    const cert = primary.certification
    const allied = response.allied || {
      normative_references: [],
      test_methods: [],
      safety_standards: [],
      terminology: [],
      installation_standards: [],
      related_product_standards: [],
    }

    let y = 20

    const checkPageBreak = (neededSpace: number) => {
      if (y + neededSpace > 275) {
        doc.addPage()
        y = 20
      }
    }

    // ── Header ─────────────────────────────────────────────────────────────
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(15)
    doc.setTextColor(15, 23, 42) // slate-900
    doc.text('StandardSphere — BIS Standards Recommendation Report', 14, y)
    y += 8

    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9)
    doc.setTextColor(71, 85, 105) // slate-600
    const queryLines = doc.splitTextToSize(`Procurement Query: ${lastQuery}`, 180)
    doc.text(queryLines, 14, y)
    y += queryLines.length * 4.5
    doc.text(`Generated: ${new Date().toLocaleString()}`, 14, y)
    y += 7

    // Divider line
    doc.setDrawColor(226, 232, 240)
    doc.line(14, y, 196, y)
    y += 8

    // ── 1. PRIMARY STANDARD ────────────────────────────────────────────────
    checkPageBreak(35)
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(12)
    doc.setTextColor(30, 58, 138) // blue-900
    doc.text('1. Recommended Primary Standard', 14, y)
    y += 6

    doc.setFont('helvetica', 'bold')
    doc.setFontSize(10.5)
    doc.setTextColor(15, 23, 42)
    const matchText = `${primary.standard_number} — ${primary.is_status_label} (${primary.confidence.toFixed(1)}% match)`
    doc.text(matchText, 14, y)
    y += 5.5

    doc.setFont('helvetica', 'normal')
    doc.setFontSize(8.5)
    doc.setTextColor(51, 65, 85)
    const titleLines = doc.splitTextToSize(primary.title, 180)
    checkPageBreak(titleLines.length * 4.5)
    doc.text(titleLines, 14, y)
    y += titleLines.length * 4.5 + 2

    // Grounded Why explanation
    if (primary.why) {
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(8.5)
      doc.setTextColor(30, 58, 138)
      doc.text('Technical Grounding (Why):', 14, y)
      y += 4.5
      doc.setFont('helvetica', 'normal')
      doc.setTextColor(51, 65, 85)
      const whyLines = doc.splitTextToSize(primary.why, 180)
      checkPageBreak(whyLines.length * 4 + 4)
      doc.text(whyLines, 14, y)
      y += whyLines.length * 4 + 6
    }

    // ── 2. ALLIED & NORMATIVE STANDARDS ───────────────────────────────────
    checkPageBreak(25)
    doc.setDrawColor(226, 232, 240)
    doc.line(14, y, 196, y)
    y += 7

    doc.setFont('helvetica', 'bold')
    doc.setFontSize(12)
    doc.setTextColor(30, 58, 138)
    doc.text('2. Allied & Normative Standards', 14, y)
    y += 6

    const alliedGroups = [
      { label: 'Normative References', list: allied.normative_references || [] },
      { label: 'Test Methods', list: allied.test_methods || [] },
      { label: 'Safety Standards', list: allied.safety_standards || [] },
      { label: 'Terminology Standards', list: allied.terminology || [] },
      { label: 'Installation Standards', list: allied.installation_standards || [] },
      { label: 'Related Product Standards', list: allied.related_product_standards || [] },
    ]

    let hasAllied = false
    alliedGroups.forEach((grp) => {
      if (!grp.list || grp.list.length === 0) return
      hasAllied = true
      checkPageBreak(12)
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(9.5)
      doc.setTextColor(71, 85, 105)
      doc.text(`• ${grp.label} (${grp.list.length})`, 16, y)
      y += 4.5

      doc.setFont('helvetica', 'normal')
      doc.setFontSize(8)
      grp.list.forEach((item) => {
        const itemLine = `${item.standard_number}: ${item.title}${item.status ? ` [${item.status}]` : ''}`
        const wrapped = doc.splitTextToSize(itemLine, 172)
        checkPageBreak(wrapped.length * 3.8 + 1)
        doc.setTextColor(51, 65, 85)
        doc.text(wrapped, 20, y)
        y += wrapped.length * 3.8 + 1.5
      })
      y += 2
    })

    if (!hasAllied) {
      doc.setFont('helvetica', 'italic')
      doc.setFontSize(8.5)
      doc.setTextColor(100, 116, 139)
      doc.text('No associated allied or normative standards identified for this specification.', 16, y)
      y += 6
    }

    // ── 3. CERTIFICATION & MANDATORY QCO ──────────────────────────────────
    checkPageBreak(28)
    doc.setDrawColor(226, 232, 240)
    doc.line(14, y, 196, y)
    y += 7

    doc.setFont('helvetica', 'bold')
    doc.setFontSize(12)
    doc.setTextColor(30, 58, 138)
    doc.text('3. Certification & Quality Control Order (QCO)', 14, y)
    y += 6

    doc.setFont('helvetica', 'bold')
    doc.setFontSize(9)
    if (cert?.verified) {
      doc.setTextColor(16, 149, 106) // emerald-600
      doc.text('Status: BIS ISI Mark Certification Verified', 16, y)
      y += 4.5
      doc.setFont('helvetica', 'normal')
      doc.setTextColor(51, 65, 85)
      if (cert.qco_ministry) {
        doc.text(`Governing Ministry: ${cert.qco_ministry}`, 16, y)
        y += 4
      }
      if (cert.value) {
        doc.text(`Scheme / Certification Mode: ${cert.value}`, 16, y)
        y += 4
      }
      doc.text('Statutory Mandate: Mandatory BIS Certification / ISI Mark required under Quality Control Order (QCO).', 16, y)
      y += 4
      if (cert.source_url) {
        const urlLines = doc.splitTextToSize(`Official BIS Portal: ${cert.source_url}`, 176)
        doc.text(urlLines, 16, y)
        y += urlLines.length * 4
      }
    } else {
      doc.setTextColor(217, 119, 6) // amber-600
      doc.text('Status: Certification Status Not Statically Verified — Check BIS Portal', 16, y)
      y += 4.5
      doc.setFont('helvetica', 'normal')
      doc.setTextColor(51, 65, 85)
      doc.text('Procurement officials should verify whether a specific QCO has been notified by the administrative ministry.', 16, y)
      y += 4
      if (cert?.source_url) {
        const urlLines = doc.splitTextToSize(`Official BIS Portal Reference: ${cert.source_url}`, 176)
        doc.text(urlLines, 16, y)
        y += urlLines.length * 4
      }
    }

    doc.save(`bis-recommendations-${Date.now()}.pdf`)
  }

  const primaryStandard = response?.primary?.[0]

  const alliedCount = response?.allied ? (
    (response.allied.normative_references?.length || 0) + (response.allied.test_methods?.length || 0) +
    (response.allied.terminology?.length || 0) + (response.allied.safety_standards?.length || 0) +
    (response.allied.installation_standards?.length || 0) + (response.allied.related_product_standards?.length || 0)
  ) : 0

  const TABS = [
    { key: 'primary' as const, label: t('recommend.tab_primary') || 'Recommended Standard', count: primaryStandard ? 1 : 0 },
    { key: 'aligned' as const, label: t('recommend.tab_aligned') || 'Allied Standards', count: alliedCount },
    { key: 'certification' as const, label: t('recommend.tab_certs') || 'Certifications & QCO', count: primaryStandard ? 1 : 0 },
  ]

  // Active = loading started OR response arrived — greeting hidden in this state
  const isActive = loading || !!response || showModal
  const hasOkResult = response?.status === 'ok'
  const primaryStandardNumber = primaryStandard?.standard_number

  return (
    <Shell
      botContext="recommend"
      botQueryContext={primaryStandardNumber || lastQuery}
      botScreenData={{
        query: lastQuery,
        primary_is: primaryStandardNumber,
        aligned_is: [
          ...(response?.allied?.normative_references || []),
          ...(response?.allied?.test_methods || []),
          ...(response?.allied?.related_product_standards || [])
        ].slice(0, 5).map(a => ({ is_number: a.standard_number, title: a.title }))
      }}
      botForceOpen={botOpen}
      onBotForceOpenConsumed={() => setBotOpen(false)}
    >
      <div className="flex flex-col min-h-full">

        {/* ── BEFORE SUBMIT: Vertically centered hero layout with greeting ── */}
        {!isActive && (
          <div className="flex flex-1 flex-col items-center justify-center px-4 sm:px-6 py-12">
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
              className="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-8 text-center"
            >
              {t(getGreetingKey())}{' '}
              <span className="text-blue-600 dark:text-blue-400">
                {t('recommend.greeting_officer')}
              </span>
            </motion.h1>
            <motion.div
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
              className="w-full flex justify-center"
            >
              <Omnibar onSubmit={handleSubmit} loading={loading} value={queryText} onChange={setQueryText} />
            </motion.div>
          </div>
        )}

        {/* ── AFTER SUBMIT / LOADING: Top pinned layout — NO greeting ── */}
        {isActive && (
          <div className="px-4 sm:px-6 py-6 max-w-3xl mx-auto w-full">

            {/* Pinned Omnibar only — greeting is intentionally absent */}
            <div className="flex justify-center mb-6">
              <Omnibar onSubmit={handleSubmit} loading={loading} value={queryText} onChange={setQueryText} />
            </div>

            {/* Error Message */}
            {errorMessage && (
              <div className="mb-6 p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
                <p className="text-xs text-rose-800 dark:text-rose-300 leading-relaxed font-medium">{errorMessage}</p>
              </div>
            )}

            <AnimatePresence>
              {(loading || response) && (
                <motion.div
                  key="results"
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                >
                  {/* Brand filter banner */}
                  {response?.extracted_spec?.brand_names_removed?.length! > 0 && (
                    <div className="mb-4 px-3.5 py-2.5 rounded-xl bg-blue-50/80 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 flex items-start gap-2.5">
                      <ShieldCheck className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
                      <div className="text-xs text-blue-900 dark:text-blue-200 leading-relaxed">
                        <span className="font-bold">GFR 2017 Rule 144(i)(b) Brand Filter Applied:</span>{' '}
                        Stripped [{response!.extracted_spec!.brand_names_removed.join(', ')}] from query.
                      </div>
                    </div>
                  )}

                  {/* Section header & tabs — only when status is ok */}
                  {response?.status === 'ok' && (
                    <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
                          {t('recommend.section') || 'Recommendations'}
                        </h2>
                        <div className="flex items-center gap-0.5 p-0.5 rounded-lg bg-slate-100 dark:bg-zinc-800">
                          {TABS.map(tab => (
                            <button
                              key={tab.key}
                              onClick={() => handleTabChange(tab.key)}
                              className={clsx(
                                'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer',
                                activeTab === tab.key
                                  ? 'bg-white dark:bg-zinc-700 text-slate-900 dark:text-white shadow-sm'
                                  : 'text-slate-500 dark:text-zinc-400 hover:text-slate-700 dark:hover:text-zinc-300'
                              )}
                            >
                              {tab.label}
                              {tab.count != null && (
                                <span className={clsx(
                                  'inline-flex items-center px-1.5 py-0.5 rounded-md text-[11px] font-semibold tabular-nums',
                                  activeTab === tab.key
                                    ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-400'
                                    : 'bg-slate-200 dark:bg-zinc-700 text-slate-500 dark:text-zinc-400'
                                )}>{tab.count}</span>
                              )}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-wrap">
                        {response?.timings && (
                          <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-mono bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400 border border-slate-200 dark:border-zinc-700">
                            <Zap className="w-3 h-3 text-amber-500 shrink-0" />
                            <span>{response.timings.total_ms || 0}ms</span>
                          </div>
                        )}
                        {response && (
                          <div className="flex items-center gap-1.5">
                            <button onClick={handleResetSearch} className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-slate-600 dark:text-zinc-400 hover:bg-slate-50 dark:hover:bg-zinc-800 transition-colors cursor-pointer" title="Start a fresh recommendation search">
                              <Plus className="w-3.5 h-3.5" />New Search
                            </button>
                            <button
                              onClick={handleExportClipboard}
                              className={clsx(
                                "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors cursor-pointer",
                                copiedExport
                                  ? "border-emerald-300 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300"
                                  : "border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-slate-600 dark:text-zinc-400 hover:bg-slate-50 dark:hover:bg-zinc-800"
                              )}
                              title="Copy recommendation summary to clipboard"
                            >
                              {copiedExport ? (
                                <>
                                  <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                                  <span>Copied!</span>
                                </>
                              ) : (
                                <>
                                  <Copy className="w-3.5 h-3.5" />
                                  <span>{t('recommend.export') || 'Export'}</span>
                                </>
                              )}
                            </button>
                            <button onClick={handleExportPDF} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-slate-600 dark:text-zinc-400 hover:bg-slate-50 dark:hover:bg-zinc-800 transition-colors cursor-pointer">
                              <FileOutput className="w-3.5 h-3.5" />{t('recommend.report') || 'Report'}
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* OUT-OF-SCOPE */}
                  {response?.status === 'out_of_scope' && (
                    <div className="p-6 rounded-2xl bg-slate-50 dark:bg-zinc-900/80 border border-slate-200 dark:border-zinc-800 text-center mb-6">
                      <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 mx-auto mb-3 flex items-center justify-center">
                        <AlertCircle className="w-5 h-5 text-slate-500 dark:text-zinc-400" />
                      </div>
                      <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-1.5">Item Outside Indexed Sectors</h3>
                      <p className="text-xs text-slate-600 dark:text-zinc-400 max-w-lg mx-auto leading-relaxed mb-4">
                        {response.message || 'No standard in our current dataset matches this description confidently.'}
                      </p>
                      <div className="flex flex-wrap items-center justify-center gap-2">
                        <span className="text-[11px] font-medium text-slate-500 dark:text-zinc-500">Try:</span>
                        {['PVC copper cable 1100V', '43 grade OPC cement', 'TMT 500D steel bar', 'GI pipe', 'steel angle'].map((item) => (
                          <button key={item} onClick={() => { setQueryText(item); handleSubmit(item, null) }}
                            className="px-2.5 py-1 rounded-lg text-xs font-medium bg-white dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 text-blue-600 dark:text-blue-400 hover:border-blue-300 transition-colors cursor-pointer">
                            {item}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Loading skeleton */}
                  {loading && (
                    <div className="space-y-3">{[1, 2, 3].map(i => <SkeletonCard key={i} />)}</div>
                  )}

                  {/* Tab content — only render when status=ok */}
                  {!loading && hasOkResult && (
                    <AnimatePresence mode="wait">
                      {/* PRIMARY RECOMMENDATION TAB */}
                      {activeTab === 'primary' && (
                        <motion.div key="primary" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
                          <PrimaryResultView
                            candidates={response!.primary}
                            onViewIS={(sn) => navigate(`/standards?is=${encodeURIComponent(sn)}`)}
                            onViewSuperseded={(sn) => navigate(`/standards?is=${encodeURIComponent(sn)}`)}
                            onSelectAlternative={handleSelectAlternative}
                          />
                          {!response!.primary.length && (
                            <p className="text-sm text-slate-400 dark:text-zinc-500 py-8 text-center">
                              {t('recommend.noResults') || 'No standards retrieved for this query.'}
                            </p>
                          )}
                        </motion.div>
                      )}

                      {/* ALLIED STANDARDS TAB (specifically for the recommended standard) */}
                      {activeTab === 'aligned' && response && (
                        <motion.div key="allied" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
                          {primaryStandard && (
                            <div className="text-xs text-slate-500 dark:text-zinc-400 font-medium mb-3">
                              Allied standards, normative references, and test methods referenced in <span className="font-bold text-slate-800 dark:text-zinc-200">{primaryStandard.standard_number}</span>:
                            </div>
                          )}
                          <AlliedStandardsView graph={response.allied} />
                        </motion.div>
                      )}

                      {/* CERTIFICATIONS TAB (strictly for that ONE recommended primary standard) */}
                      {activeTab === 'certification' && (
                        <motion.div key="certs" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
                          <div className="space-y-3">
                            {primaryStandard ? (
                              <>
                                <div className="text-xs text-slate-500 dark:text-zinc-400 font-medium mb-1">
                                  Official BIS Certification Scheme & Quality Control Order for recommended standard <span className="font-bold text-slate-800 dark:text-zinc-200">{primaryStandard.standard_number}</span>:
                                </div>
                                <CertSummaryCard candidate={primaryStandard} />
                              </>
                            ) : (
                              <p className="text-sm text-slate-400 dark:text-zinc-500 py-8 text-center">
                                {t('recommend.noResults') || 'No certification details available.'}
                              </p>
                            )}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  )}

                  {/* Follow-up button */}
                  {hasOkResult && !loading && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.5 }}
                      className="mt-6 flex justify-center"
                    >
                      <button
                        onClick={() => setBotOpen(true)}
                        className={clsx(
                          'inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-xs font-semibold transition-all',
                          'border border-slate-200 dark:border-zinc-700',
                          'bg-white dark:bg-zinc-900 text-slate-700 dark:text-zinc-300',
                          'hover:bg-blue-50 dark:hover:bg-blue-950/40 hover:border-blue-300 dark:hover:border-blue-700',
                          'hover:text-blue-700 dark:hover:text-blue-400 shadow-sm hover:shadow-md active:scale-95 cursor-pointer'
                        )}
                      >
                        <Sparkles className="w-3.5 h-3.5 text-blue-500" />
                        {t('recommend.followUp') || 'Ask AI Copilot about these standards'}
                      </button>
                    </motion.div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

      </div>

      {/* ── DISAMBIGUATION MODAL (true portal overlay with interactive 4th option input) ── */}
      {showModal && response?.status === 'ambiguous' && response.disambiguation_options?.length! > 0 && (
        <DisambiguationModal
          question={response.disambiguation_question || 'Which specific standard do you need?'}
          options={response.disambiguation_options!}
          customOptionText={response.custom_option_text}
          onSelect={handleSelectDisambiguation}
          onCustomSubmit={handleCustomSubmit}
          onClose={() => setShowModal(false)}
        />
      )}

    </Shell>
  )
}

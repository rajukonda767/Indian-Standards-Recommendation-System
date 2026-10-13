import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { MessageCircle, X, Send, Loader2, Mic, MicOff, Sparkles, Volume2, VolumeX } from 'lucide-react'
import { useTranslation } from '@/i18n/I18nContext'
import { getBotSuggestions, streamBotChat } from '@/lib/botApi'
import { clsx } from 'clsx'

interface MiniBotDrawerProps {
  context: 'recommend' | 'standards' | 'audit' | 'general'
  /** Actual query string — used to generate context-aware suggestion chips */
  queryContext?: string
  /** Detailed screen metadata forwarded to grounding retrieval service */
  screenData?: Record<string, any>
  /** When true, opens the drawer without sending any message */
  forceOpen?: boolean
  onForceOpenConsumed?: () => void
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  text: string
  streaming?: boolean
}

export function MiniBotDrawer({
  context,
  queryContext,
  screenData: propScreenData,
  forceOpen,
  onForceOpenConsumed,
}: MiniBotDrawerProps) {
  const { t, lang } = useTranslation()
  const [open, setOpen] = useState(false)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [suggestionsLoading, setSuggestionsLoading] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [listening, setListening] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const recogRef = useRef<any>(null)

  const screen = (context === 'general' ? 'home' : context) as 'audit' | 'recommend' | 'standards' | 'home'

  // forceOpen: just open the drawer, don't send anything
  useEffect(() => {
    if (forceOpen) {
      setOpen(true)
      onForceOpenConsumed?.()
    }
  }, [forceOpen, onForceOpenConsumed])

  // Load contextual suggestions whenever open + no messages + queryContext changes
  useEffect(() => {
    if (!open) return
    setSuggestionsLoading(true)
    getBotSuggestions(screen, lang, queryContext)
      .then(setSuggestions)
      .finally(() => setSuggestionsLoading(false))
  }, [open, screen, lang, queryContext])

  // Speech recognition
  useEffect(() => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SR) return
    const r = new SR()
    r.continuous = false
    r.interimResults = true
    r.lang = lang === 'hi' ? 'hi-IN' : lang === 'te' ? 'te-IN' : 'en-IN'
    r.onresult = (e: any) => {
      let transcript = ''
      for (let i = e.resultIndex; i < e.results.length; i++) transcript += e.results[i][0].transcript
      setInput(transcript)
    }
    r.onend = () => setListening(false)
    r.onerror = () => setListening(false)
    recogRef.current = r
    return () => { try { r.abort() } catch { /* noop */ } }
  }, [lang])

  const toggleVoice = () => {
    if (!recogRef.current) return
    if (listening) { recogRef.current.stop(); setListening(false) }
    else { try { recogRef.current.start(); setListening(true) } catch { /* noop */ } }
  }

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus input on open
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 220)
  }, [open])

  // Text-to-Speech (TTS) reading
  const [speakingId, setSpeakingId] = useState<string | null>(null)
  const [voiceToast, setVoiceToast] = useState(false)
  const voiceToastRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const stopSpeaking = useCallback(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel()
    }
    setSpeakingId(null)
  }, [])

  // Check if the OS has a voice for the given language
  const hasVoiceForLang = useCallback((targetLang: string): boolean => {
    if (targetLang === 'en') return true
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return false
    const voices = window.speechSynthesis.getVoices()
    const prefix = targetLang === 'hi' ? 'hi' : 'te'
    return voices.some(v => v.lang.replace('_', '-').toLowerCase().startsWith(prefix))
  }, [])

  const speakMessage = useCallback((text: string, id: string) => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return

    if (speakingId === id) {
      stopSpeaking()
      return
    }

    stopSpeaking()

    // Show notice and bail if no regional voice installed
    if (!hasVoiceForLang(lang)) {
      setVoiceToast(true)
      if (voiceToastRef.current) clearTimeout(voiceToastRef.current)
      voiceToastRef.current = setTimeout(() => setVoiceToast(false), 5000)
      return
    }

    // Clean formatting for pure speech
    const cleanText = text
      .replace(/[*#_~`>]/g, '')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .trim()

    if (!cleanText) return

    const targetLangCode = lang === 'hi' ? 'hi-IN' : lang === 'te' ? 'te-IN' : 'en-IN'
    const utterance = new SpeechSynthesisUtterance(cleanText)
    utterance.lang = targetLangCode

    try {
      const voices = window.speechSynthesis.getVoices()
      const langPrefix = targetLangCode.toLowerCase().slice(0, 2)
      const matchingVoice = voices.find(v =>
        v.lang.replace('_', '-').toLowerCase().startsWith(langPrefix)
      )
      if (matchingVoice) {
        utterance.voice = matchingVoice
      }
    } catch {
      /* ignore voice enumeration errors */
    }

    utterance.rate = 0.95
    utterance.onend = () => setSpeakingId(null)
    utterance.onerror = () => setSpeakingId(null)

    setSpeakingId(id)
    window.speechSynthesis.speak(utterance)
  }, [lang, speakingId, stopSpeaking, hasVoiceForLang])

  // Stop speech when drawer closes
  useEffect(() => {
    if (!open) {
      stopSpeaking()
    }
  }, [open, stopSpeaking])

  // Stop speech on unmount
  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel()
      }
      if (voiceToastRef.current) clearTimeout(voiceToastRef.current)
    }
  }, [])

  const streamResponse = useCallback(async (query: string) => {
    setLoading(true)
    const assistantId = crypto.randomUUID()
    setMessages((prev) => [...prev, { id: assistantId, role: 'assistant', text: '', streaming: true }])

    const screenData: Record<string, any> = {
      ...(propScreenData || {}),
      ...(screen === 'audit' && queryContext ? { job_id: queryContext } : {}),
      ...(screen === 'standards' && queryContext ? { is_number: queryContext } : {}),
      ...(screen === 'recommend' && queryContext ? { query: queryContext } : {}),
    }

    if (screen === 'recommend' && queryContext && !screenData.primary_is && /IS\s*\d+/i.test(queryContext)) {
      screenData.primary_is = queryContext
    }

    const historyPayload = messages.slice(-6).map((m) => ({
      role: m.role,
      content: m.text,
    }))

    await streamBotChat({
      message: query,
      screen,
      lang: (lang === 'hi' || lang === 'te') ? lang : 'en',
      screenData,
      history: historyPayload,
      onToken: (token: string) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, text: m.text + token } : m))
        )
      },
      onDone: () => {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m))
        )
        setLoading(false)
      },
      onError: (errMsg: string) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, text: m.text ? `${m.text}\n\n[${errMsg}]` : errMsg, streaming: false }
              : m
          )
        )
        setLoading(false)
      },
    })
  }, [screen, queryContext, lang, messages])

  const handleSend = useCallback(async (query: string) => {
    const q = query.trim()
    if (!q || loading) return
    setInput('')
    setListening(false)
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'user', text: q }])
    await streamResponse(q)
  }, [loading, streamResponse])

  const isEmpty = messages.length === 0

  return (
    <>
      {/* Floating action button (only when drawer is closed) */}
      {!open && (
        <motion.button
          onClick={() => setOpen(true)}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="fixed bottom-6 right-6 z-50 w-12 h-12 rounded-full shadow-lg flex items-center justify-center bg-blue-600 hover:bg-blue-700 text-white transition-colors"
          aria-label={t('bot.title')}
        >
          <MessageCircle className="w-5 h-5" />
        </motion.button>
      )}

      {/* Drawer panel */}
      <AnimatePresence>
        {open && (
          <motion.div
            key="bot-panel"
            initial={{ x: '100%', opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: '100%', opacity: 0 }}
            transition={{ type: 'spring', stiffness: 340, damping: 34, mass: 0.9 }}
            className={clsx(
              'fixed right-0 top-0 bottom-0 z-40 w-80 flex flex-col',
              'bg-white dark:bg-zinc-950 border-l border-slate-200 dark:border-zinc-800 shadow-2xl'
            )}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 h-14 border-b border-slate-200 dark:border-zinc-800 flex-shrink-0">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center">
                  <MessageCircle className="w-3.5 h-3.5 text-white" />
                </div>
                <span className="text-sm font-semibold text-slate-900 dark:text-white">{t('bot.title')}</span>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="w-7 h-7 rounded-md flex items-center justify-center text-slate-400 hover:text-slate-600 dark:hover:text-zinc-200 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Voice-not-available toast (auto-dismisses after 5s) */}
            {voiceToast && lang !== 'en' && (
              <div className="mx-3 mt-2 px-3 py-2 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 flex items-start gap-2 text-[11px] text-amber-800 dark:text-amber-300 leading-relaxed flex-shrink-0">
                <span className="shrink-0 mt-0.5">⚠️</span>
                <span className="flex-1">
                  {lang === 'te'
                    ? 'తెలుగు వాయిస్ ఇన్‌స్టాల్ కాలేదు. Windows Settings → Time & Language → Speech → Manage voices లో ఇన్‌స్టాల్ చేయండి.'
                    : 'हिन्दी आवाज़ इंस्टॉल नहीं है। Windows Settings → Time & Language → Speech → Manage voices में जाकर इंस्टॉल करें।'
                  }
                </span>
                <button type="button" onClick={() => setVoiceToast(false)} className="shrink-0 text-amber-500 hover:text-amber-700">
                  <X className="w-3 h-3" />
                </button>
              </div>
            )}

            {/* Content */}
            <div className="flex-1 overflow-y-auto">
              {/* ── EMPTY STATE (Gemini-style) ── */}
              {isEmpty && (
                <div className="flex flex-col items-center justify-start pt-10 px-5 h-full">
                  {/* Sparkle icon */}
                  <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center mb-4 shadow-md shadow-blue-500/25">
                    <Sparkles className="w-6 h-6 text-white" />
                  </div>
                  <p className="text-[15px] font-semibold text-slate-800 dark:text-zinc-200 mb-1 text-center">
                    Ready when you are
                  </p>
                  <p className="text-xs text-slate-400 dark:text-zinc-500 mb-8 text-center leading-relaxed">
                    Ask anything about standards, compliance, or procurement.
                  </p>

                  {/* Suggestion chips */}
                  {suggestionsLoading ? (
                    <div className="w-full space-y-2">
                      {[1, 2, 3].map(i => (
                        <div key={i} className="h-10 w-full rounded-xl bg-slate-100 dark:bg-zinc-800 animate-pulse" />
                      ))}
                    </div>
                  ) : (
                    <div className="w-full space-y-2">
                      {suggestions.map((s, i) => (
                        <button
                          key={i}
                          onClick={() => handleSend(s)}
                          className={clsx(
                            'w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-left transition-all',
                            'border border-slate-200 dark:border-zinc-700',
                            'bg-slate-50 dark:bg-zinc-900 text-slate-700 dark:text-zinc-300 text-xs leading-snug',
                            'hover:bg-white dark:hover:bg-zinc-800 hover:border-blue-300 dark:hover:border-blue-700',
                            'hover:text-blue-800 dark:hover:text-blue-300 hover:shadow-sm'
                          )}
                        >
                          <span className="w-5 h-5 rounded-lg bg-blue-50 dark:bg-blue-950/60 flex items-center justify-center shrink-0">
                            <Sparkles className="w-3 h-3 text-blue-500 dark:text-blue-400" />
                          </span>
                          {s}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* ── CONVERSATION ── */}
              {!isEmpty && (
                <div className="px-4 py-4 space-y-3">
                  {messages.map((msg) => (
                    <div key={msg.id} className={clsx('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
                      <div className={clsx('flex flex-col', msg.role === 'user' ? 'items-end max-w-[85%]' : 'items-start max-w-[88%]')}>
                        <div className={clsx(
                          'px-3 py-2.5 rounded-xl text-xs leading-relaxed',
                          msg.role === 'user'
                            ? 'bg-blue-600 text-white rounded-br-sm'
                            : 'bg-slate-100 dark:bg-zinc-800 text-slate-800 dark:text-zinc-200 rounded-bl-sm'
                        )}>
                          {msg.text || (msg.streaming && (
                            <span className="flex gap-1 items-center py-0.5">
                              <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                              <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: '120ms' }} />
                              <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: '240ms' }} />
                            </span>
                          ))}
                          {msg.text && msg.streaming && (
                            <span className="inline-block w-1.5 h-3.5 ml-0.5 bg-current opacity-70 animate-pulse align-middle rounded-sm" />
                          )}
                        </div>

                        {/* Speaker / Read response aloud button (Telugu, Hindi, English) */}
                        {msg.role === 'assistant' && !msg.streaming && msg.text && (
                          <button
                            type="button"
                            onClick={() => speakMessage(msg.text, msg.id)}
                            className={clsx(
                              'mt-1 inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-medium transition-all cursor-pointer',
                              speakingId === msg.id
                                ? 'bg-blue-100 dark:bg-blue-950/70 text-blue-700 dark:text-blue-300 ring-1 ring-blue-300 dark:ring-blue-700'
                                : 'text-slate-400 hover:text-slate-700 dark:text-zinc-500 dark:hover:text-zinc-200 hover:bg-slate-100 dark:hover:bg-zinc-800'
                            )}
                            title={speakingId === msg.id ? 'Stop reading' : 'Read aloud'}
                          >
                            {speakingId === msg.id ? (
                              <>
                                <VolumeX className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 animate-pulse" />
                                <span>{lang === 'te' ? 'ఆపు' : lang === 'hi' ? 'रोकें' : 'Stop'}</span>
                              </>
                            ) : (
                              <>
                                <Volume2 className="w-3.5 h-3.5" />
                                <span>{lang === 'te' ? 'వినండి' : lang === 'hi' ? 'सुनें' : 'Listen'}</span>
                              </>
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                  ))}

                  {loading && !messages.some(m => m.streaming) && (
                    <div className="flex justify-start">
                      <div className="px-3 py-2.5 rounded-xl rounded-bl-sm bg-slate-100 dark:bg-zinc-800">
                        <Loader2 className="w-3.5 h-3.5 text-slate-400 animate-spin" />
                      </div>
                    </div>
                  )}
                  <div ref={bottomRef} />
                </div>
              )}
            </div>

            {/* ── Input bar ── */}
            <div className="px-3 py-3 border-t border-slate-200 dark:border-zinc-800 flex-shrink-0">
              <div className={clsx(
                'flex items-center gap-2 rounded-xl px-3 py-2',
                'border border-slate-200 dark:border-zinc-700',
                'bg-slate-50 dark:bg-zinc-900',
                'focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/10 transition-all'
              )}>
                <input
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(input) }
                  }}
                  placeholder={t('bot.placeholder')}
                  className="flex-1 bg-transparent text-xs text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-zinc-500 outline-none"
                  disabled={loading}
                />

                {/* Mic */}
                <button
                  onClick={toggleVoice}
                  className={clsx(
                    'w-6 h-6 flex items-center justify-center rounded-lg transition-colors shrink-0',
                    listening
                      ? 'text-rose-500'
                      : 'text-slate-400 dark:text-zinc-500 hover:text-slate-600 dark:hover:text-zinc-300'
                  )}
                  title="Voice input"
                >
                  {listening ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
                </button>

                {/* Send */}
                <button
                  onClick={() => handleSend(input)}
                  disabled={loading || !input.trim()}
                  className={clsx(
                    'w-6 h-6 flex items-center justify-center rounded-lg transition-colors shrink-0',
                    loading || !input.trim()
                      ? 'text-slate-300 dark:text-zinc-600'
                      : 'text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300'
                  )}
                  title={t('bot.send')}
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}

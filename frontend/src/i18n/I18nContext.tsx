import { createContext, useContext, useState, useMemo, type ReactNode } from 'react'
import en from './en.json'
import hi from './hi.json'
import te from './te.json'
import { getLanguage, setLanguage as persistLanguage } from '@/utils/storage'

export type Lang = 'en' | 'hi' | 'te'

const dictionaries: Record<Lang, typeof en> = { en, hi: hi as typeof en, te: te as typeof en }

export const LANGUAGES: { code: Lang; label: string; nativeLabel: string }[] = [
  { code: 'en', label: 'English',  nativeLabel: 'English' },
  { code: 'hi', label: 'Hindi',    nativeLabel: 'हिन्दी' },
  { code: 'te', label: 'Telugu',   nativeLabel: 'తెలుగు' },
]

interface I18nCtx {
  lang: Lang
  setLang: (l: Lang) => void
  t: (key: string) => string
}

const I18nContext = createContext<I18nCtx>({} as I18nCtx)

export const I18nProvider = ({ children }: { children: ReactNode }) => {
  const [lang, setLangState] = useState<Lang>(() => {
    const saved = getLanguage()
    return (saved === 'hi' || saved === 'te') ? saved : 'en'
  })

  const setLang = (l: Lang) => {
    persistLanguage(l)
    setLangState(l)
  }

  // Rebuild t() every time lang changes — intentionally not memoised so all
  // consumers get the fresh dictionary on every language switch.
  const t = (key: string): string => {
    const parts = key.split('.')
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let val: any = dictionaries[lang]
    for (const p of parts) val = val?.[p]
    if (val !== undefined) return val as string
    // Fallback to English
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let fb: any = dictionaries['en']
    for (const p of parts) fb = fb?.[p]
    return (fb as string) ?? key
  }

  const value = useMemo(() => ({ lang, setLang, t }), 
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [lang]
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export const useTranslation = () => useContext(I18nContext)

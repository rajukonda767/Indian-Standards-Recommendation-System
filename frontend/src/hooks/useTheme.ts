import { useState, useEffect } from 'react'

/**
 * Manages the dark/light theme by toggling the `dark` class on <html>.
 * Persists to localStorage key `ss_theme`.
 */
export function useTheme() {
  const [isDark, setIsDark] = useState<boolean>(() => {
    const saved = localStorage.getItem('ss_theme')
    if (saved) return saved === 'dark'
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  })

  useEffect(() => {
    const root = document.documentElement
    if (isDark) {
      root.classList.add('dark')
      localStorage.setItem('ss_theme', 'dark')
    } else {
      root.classList.remove('dark')
      localStorage.setItem('ss_theme', 'light')
    }
  }, [isDark])

  return { isDark, toggle: () => setIsDark((d) => !d) }
}

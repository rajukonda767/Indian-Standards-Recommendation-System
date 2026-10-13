/**
 * frontend/src/lib/botApi.ts
 * ==========================
 * Client API for StandardSphere MiniBot assistant.
 * Communicates with backend /api/bot endpoints via Vite proxy.
 */

export interface BotHealth {
  ok: boolean
  model: string
  key_configured: boolean
}

export interface StreamChatOptions {
  message: string
  screen: 'audit' | 'recommend' | 'standards' | 'home'
  lang: 'en' | 'hi' | 'te'
  screenData?: Record<string, any>
  history?: Array<{ role: 'user' | 'assistant'; content: string }>
  onToken: (token: string) => void
  onDone?: () => void
  onError?: (error: string) => void
  signal?: AbortSignal
}

/**
 * Fetch static context-aware suggestion chips from the backend.
 */
export async function getBotSuggestions(
  screen: 'audit' | 'recommend' | 'standards' | 'home',
  lang: string = 'en',
  context?: string
): Promise<string[]> {
  try {
    const params = new URLSearchParams()
    params.set('screen', screen)
    params.set('lang', lang)
    if (context && context.trim()) {
      params.set('context', context.trim())
    }

    const res = await fetch(`/api/bot/suggestions?${params.toString()}`)
    if (!res.ok) {
      return []
    }
    const data = await res.json()
    return data.suggestions || []
  } catch (err) {
    console.warn('Failed to load bot suggestions:', err)
    return []
  }
}

/**
 * Check MiniBot service health and active model.
 */
export async function getBotHealth(): Promise<BotHealth | null> {
  try {
    const res = await fetch('/api/bot/health')
    if (!res.ok) return null
    return (await res.json()) as BotHealth
  } catch {
    return null
  }
}

/**
 * Stream chat completion from /api/bot/chat via Server-Sent Events (SSE).
 */
export async function streamBotChat({
  message,
  screen,
  lang,
  screenData = {},
  history = [],
  onToken,
  onDone,
  onError,
  signal,
}: StreamChatOptions): Promise<void> {
  try {
    const payload = {
      message: message.trim(),
      screen,
      lang,
      screen_data: screenData,
      history: history.slice(-6),
    }

    const response = await fetch('/api/bot/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
      signal,
    })

    if (!response.ok) {
      const errText = await response.text().catch(() => response.statusText)
      const msg = `AI service error (${response.status}): ${errText}`
      onError?.(msg)
      return
    }

    if (!response.body) {
      onError?.('No response stream received from server.')
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      // Retain incomplete trailing line
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (trimmed.startsWith('data:')) {
          const body = trimmed.slice(5).trim()
          if (!body) continue
          try {
            const data = JSON.parse(body)
            if (data.token) {
              onToken(data.token)
            }
            if (data.done) {
              onDone?.()
            }
            if (data.error) {
              onError?.(data.error)
            }
          } catch (e) {
            console.warn('MiniBot SSE parse error:', e, body)
          }
        }
      }
    }

    // Flush any remaining buffer if stream ends cleanly
    if (buffer.trim().startsWith('data:')) {
      try {
        const body = buffer.trim().slice(5).trim()
        if (body) {
          const data = JSON.parse(body)
          if (data.token) onToken(data.token)
          if (data.done) onDone?.()
          if (data.error) onError?.(data.error)
        }
      } catch {
        // noop
      }
    }
  } catch (err: any) {
    if (err.name === 'AbortError') {
      return
    }
    console.error('MiniBot streaming error:', err)
    onError?.('Failed to reach AI assistant. Please try again.')
  }
}

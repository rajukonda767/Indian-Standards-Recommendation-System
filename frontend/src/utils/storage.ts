// ---------------------------------------------------------------------------
// storage.ts — localStorage helpers
// ---------------------------------------------------------------------------

const KEYS = {
  LANGUAGE: 'ss_language',
  PREVIOUS: 'ss_previous_recs',
} as const

// ── Language ────────────────────────────────────────────────────────────────

export function getLanguage(): string {
  return localStorage.getItem(KEYS.LANGUAGE) ?? 'en'
}

export function setLanguage(code: string): void {
  localStorage.setItem(KEYS.LANGUAGE, code)
}

// ── Previous Recommendations (FIFO, max 6 per user specification) ─────────

export interface SavedRecommendation {
  id: string
  timestamp: number          // Unix ms
  query: string              // Original query text
  standardsCount: number
  primaryStandard: string    // e.g. "IS 694:2010"
  primaryTitle?: string
  status?: string
  dept?: string
  confidence?: number
  // Serialized full results — rehydrated on click
  results: unknown[]
}

// 6 Default Realistic Seed Recommendations (shown if localStorage is fresh)
export const DEFAULT_PREVIOUS_RECS: SavedRecommendation[] = [
  {
    id: 'seed-rec-1',
    timestamp: Date.now() - 1000 * 60 * 18, // 18 mins ago
    query: 'PVC insulated copper wiring 1.1kV for building electrification',
    standardsCount: 5,
    primaryStandard: 'IS 694:2010',
    primaryTitle: 'PVC Insulated Cables for Working Voltages up to and including 1100V',
    status: 'Current',
    dept: 'ETD',
    confidence: 94,
    results: [],
  },
  {
    id: 'seed-rec-2',
    timestamp: Date.now() - 1000 * 60 * 55, // 55 mins ago
    query: 'Ordinary Portland Cement 53 Grade for RCC bridge foundation',
    standardsCount: 4,
    primaryStandard: 'IS 269:2015',
    primaryTitle: 'Ordinary Portland Cement — Specification (33, 43 and 53 Grade)',
    status: 'Current',
    dept: 'CED',
    confidence: 97,
    results: [],
  },
  {
    id: 'seed-rec-3',
    timestamp: Date.now() - 1000 * 60 * 60 * 3, // 3 hours ago
    query: 'High strength Fe 500D TMT rebars for seismic resistant construction',
    standardsCount: 6,
    primaryStandard: 'IS 1786:2008',
    primaryTitle: 'High Strength Deformed Steel Bars and Wires for Concrete Reinforcement',
    status: 'Reaffirmed:2023',
    dept: 'CED',
    confidence: 96,
    results: [],
  },
  {
    id: 'seed-rec-4',
    timestamp: Date.now() - 1000 * 60 * 60 * 6, // 6 hours ago
    query: 'High density polyethylene (HDPE) pipes for potable water distribution',
    standardsCount: 5,
    primaryStandard: 'IS 4984:2016',
    primaryTitle: 'Polyethylene Pipes for Water Supply — Specification (Fifth Revision)',
    status: 'Current',
    dept: 'CED',
    confidence: 91,
    results: [],
  },
  {
    id: 'seed-rec-5',
    timestamp: Date.now() - 1000 * 60 * 60 * 22, // 22 hours ago
    query: 'Outdoor type oil immersed distribution transformers 11kV/433V 250kVA',
    standardsCount: 7,
    primaryStandard: 'IS 1180 (Part 1):2014',
    primaryTitle: 'Outdoor Type Oil Immersed Distribution Transformers up to and including 2500 kVA',
    status: 'Current',
    dept: 'ETD',
    confidence: 89,
    results: [],
  },
  {
    id: 'seed-rec-6',
    timestamp: Date.now() - 1000 * 60 * 60 * 36, // 1.5 days ago
    query: 'Hot rolled medium and high tensile structural steel angles and beams',
    standardsCount: 4,
    primaryStandard: 'IS 2062 (Part 1):2025',
    primaryTitle: 'Hot Rolled Medium and High Tensile Structural Steel — Specification',
    status: 'Current',
    dept: 'MTD',
    confidence: 92,
    results: [],
  },
]

export function getPreviousRecommendations(): SavedRecommendation[] {
  try {
    const raw = localStorage.getItem(KEYS.PREVIOUS)
    if (!raw) {
      // Seed with 6 realistic defaults so UI immediately renders 6 cards 3 in a row
      localStorage.setItem(KEYS.PREVIOUS, JSON.stringify(DEFAULT_PREVIOUS_RECS))
      return DEFAULT_PREVIOUS_RECS
    }
    const parsed = JSON.parse(raw) as SavedRecommendation[]
    return Array.isArray(parsed) && parsed.length > 0 ? parsed : DEFAULT_PREVIOUS_RECS
  } catch {
    return DEFAULT_PREVIOUS_RECS
  }
}

export function savePreviousRecommendation(entry: Omit<SavedRecommendation, 'id' | 'timestamp'>): void {
  const existing = getPreviousRecommendations()
  // Filter out any duplicate with identical query
  const filtered = existing.filter(r => r.query.toLowerCase() !== entry.query.toLowerCase())
  const next: SavedRecommendation = {
    ...entry,
    id: crypto.randomUUID(),
    timestamp: Date.now(),
  }
  // Keep maximum 6 items (FIFO)
  const updated = [next, ...filtered].slice(0, 6)
  localStorage.setItem(KEYS.PREVIOUS, JSON.stringify(updated))
}

export function deletePreviousRecommendation(id: string): void {
  const existing = getPreviousRecommendations()
  const updated = existing.filter(item => item.id !== id)
  localStorage.setItem(KEYS.PREVIOUS, JSON.stringify(updated))
}

export function clearPreviousRecommendations(): void {
  localStorage.setItem(KEYS.PREVIOUS, JSON.stringify([]))
}

export function restoreDefaultRecommendations(): void {
  localStorage.setItem(KEYS.PREVIOUS, JSON.stringify(DEFAULT_PREVIOUS_RECS))
}

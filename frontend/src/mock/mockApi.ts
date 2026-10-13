// ---------------------------------------------------------------------------
// mockApi.ts — Async API layer (Phase 1 MOCK)
// ALL functions return Promises with artificial delays (300–800ms) so loading
// states can be fully tested. In Phase 2: replace each function body with a
// real fetch/axios call to the corresponding /api/... endpoint.
// The function SIGNATURES must not change — no component needs to be updated.
// ---------------------------------------------------------------------------

import type { StandardRecord, AuditResult, RecommendResponse } from './mockData'
import {
  MOCK_STANDARDS,
  MOCK_AUDIT_RESULT,
  getMockRecommendResponse,
  getMockBotSuggestions,
} from './mockData'

const delay = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))
const rand = (min: number, max: number) => Math.floor(Math.random() * (max - min + 1)) + min

// Phase 2: POST /api/recommend { query }
export async function getRecommendations(query: string): Promise<RecommendResponse> {
  await delay(rand(600, 900))
  return getMockRecommendResponse(query)
}

// ── getStandardsList ───────────────────────────────────────────────────────
// Phase 2: GET /api/standards?search=&dept=
export async function getStandardsList(search?: string): Promise<StandardRecord[]> {
  await delay(rand(300, 500))
  if (!search) return MOCK_STANDARDS
  const q = search.toLowerCase()
  return MOCK_STANDARDS.filter(
    (s) =>
      s.isNumber.toLowerCase().includes(q) ||
      s.title.toLowerCase().includes(q) ||
      s.sector.toLowerCase().includes(q) ||
      s.dept.toLowerCase().includes(q)
  )
}

// ── getStandardDetail ──────────────────────────────────────────────────────
// Phase 2: GET /api/standards/{isNumber}
export async function getStandardDetail(isNumber: string): Promise<StandardRecord | null> {
  await delay(rand(200, 400))
  return (
    MOCK_STANDARDS.find(
      (s) =>
        s.isNumber.toLowerCase() === isNumber.toLowerCase() ||
        `${s.isNumber}:${s.year}`.toLowerCase() === isNumber.toLowerCase()
    ) ?? null
  )
}

// ── getTenderAuditResult ───────────────────────────────────────────────────
// Phase 2: POST /api/audit/pdf (multipart)
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export async function getTenderAuditResult(_file: File): Promise<AuditResult> {
  await delay(rand(1200, 1800)) // realistic "processing" pause
  return MOCK_AUDIT_RESULT
}

// ── getMiniBotSuggestions ─────────────────────────────────────────────────
// Phase 2: POST /api/bot/suggestions { context, query }
export async function getMiniBotSuggestions(context: string, query?: string): Promise<string[]> {
  await delay(rand(200, 400))
  return getMockBotSuggestions(context, query)
}

// ── getMiniBotResponse ─────────────────────────────────────────────────────
// Phase 2: POST /api/bot/chat { query, context }
// Returns a streaming-ready string (Phase 1: full string revealed via chunked
// setTimeout in MiniBotDrawer; Phase 2: replace with fetch + ReadableStream).
export async function getMiniBotResponse(query: string, context: string): Promise<string> {
  await delay(rand(800, 1400))

  const qLower = query.toLowerCase()

  if (qLower.includes('confidence') || qLower.includes('score')) {
    return 'Confidence scores are computed using a 5-factor hybrid formula: cosine similarity (60%), keyword boost (15%), title match (10%), QCO status (10%), and active licence count (5%). Scores ≥80% indicate high alignment with your specification; 50–79% are candidate matches requiring engineering review; below 50% signals an out-of-domain or ambiguous query.'
  }
  if (qLower.includes('qco') || qLower.includes('mandatory') || qLower.includes('certification')) {
    return 'Quality Control Orders (QCOs) are statutory instruments issued by various ministries under the BIS Act 2016. Products covered by a QCO cannot be sold in India without a valid ISI Mark licence from BIS. Currently, over 400 product categories are under mandatory QCO — including electrical cables, TMT bars, and Portland cement grades.'
  }
  if (qLower.includes('supersede') || qLower.includes('outdated') || qLower.includes('old')) {
    return 'Specifying a superseded standard in a government tender is non-compliant under the General Financial Rules 2017 and may result in a contract re-bid. The recommended action is to update the cited standard to its current revision. The AI engine\'s lineage check flags any standard whose `is_status_label` is "Superseded" or "Withdrawn" in the BIS registry.'
  }
  if (qLower.includes('why') || qLower.includes('chosen') || qLower.includes('selected')) {
    return `The primary standard was selected because it produced the highest hybrid score for your query in the context of "${context}". The engine retrieved the top 15 vector-similar standards from the BIS database, then applied keyword, QCO, and title-match boosts before selecting the top result. If the recommendation does not match your exact product, try adding the material type, voltage rating, or grade to your description.`
  }
  return `Based on the context of "${context}", the most relevant consideration is to ensure all cited standards are from the current active BIS revision. Cross-reference with the Tender Audit tab to verify that every item in your specification has a valid, current IS citation. Use the Standards Catalog to browse the full normative compliance suite for any primary standard.`
}

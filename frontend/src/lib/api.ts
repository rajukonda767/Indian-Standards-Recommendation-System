// ---------------------------------------------------------------------------
// api.ts — Real backend API client (all calls via Vite proxy → :8000)
// ---------------------------------------------------------------------------

// ── Response types matching backend Pydantic models ─────────────────────────

export interface StandardSummary {
  id: number
  standard_number: string
  base_number: string
  year: number | null
  dept: string | null
  title: string
  is_status_label: string | null
  qco_ministry: string | null
  active_licences: number
  references_count: number
  reaffirmation_year?: number | null
}

export interface LineageRecord {
  relationship: string
  related_standard_raw: string
  related_base_number: string | null
  related_year: number | null
}

export interface StandardDetail extends StandardSummary {
  status_raw: string | null
  published_on: string | null
  reaffirmation_year: number | null
  revisions_count: number | null
  technical_committee: string | null
  ics_code: string | null
  type_of_standard: string | null
  certification: string | null
  group_name: string | null
  sub_group: string | null
  sub_sub_group: string | null
  virtual_scope: string | null
  source_url: string | null
  total_isi_licences: number | null
  product_varieties: string | null
  lineage: LineageRecord[]
}

// ── Distinct 3 departments per user requirement and DB ───────────────────────
export const KNOWN_DEPTS: { code: string; label: string; desc: string }[] = [
  { code: 'ETD', label: 'ETD', desc: 'Electrotechnical Department' },
  { code: 'CED', label: 'CED', desc: 'Civil Engineering Department' },
  { code: 'MTD', label: 'MTD', desc: 'Metallurgical Engineering Department' },
]

export interface FilterOptionsResponse {
  committees: string[]
  statuses: string[]
}

// ── Fetch helpers ────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) {
    const err = await res.text().catch(() => res.statusText)
    throw new Error(`API ${res.status}: ${err}`)
  }
  return res.json() as Promise<T>
}

export interface ListStandardsParams {
  search?: string
  dept?: string
  committee?: string
  status?: string
  qco_only?: boolean
  limit?: number
  offset?: number
}

export async function listStandards(params: ListStandardsParams = {}): Promise<StandardSummary[]> {
  const q = new URLSearchParams()
  if (params.search)    q.set('search', params.search)
  if (params.dept)      q.set('dept', params.dept)
  if (params.committee) q.set('committee', params.committee)
  if (params.status)    q.set('status', params.status)
  if (params.qco_only)  q.set('qco_only', 'true')
  if (params.limit)     q.set('limit', String(params.limit))
  if (params.offset)    q.set('offset', String(params.offset))
  return apiFetch<StandardSummary[]>(`/api/standards?${q.toString()}`)
}

export async function getStandardDetail(standardNumber: string): Promise<StandardDetail> {
  return apiFetch<StandardDetail>(`/api/standards/${encodeURIComponent(standardNumber)}`)
}

export async function getFilterOptions(): Promise<FilterOptionsResponse> {
  return apiFetch<FilterOptionsResponse>('/api/standards/filters')
}

// ── Recommendation Types matching backend Pydantic models ──────────────────
export interface ExtractedSpec {
  product_category?: string | null
  material?: string | null
  voltage_rating?: string | null
  dimensions?: string | null
  application?: string | null
  cited_standard_raw?: string | null
  brand_names_removed: string[]
}

export interface CertificationInfo {
  verified: boolean
  value?: string | null
  qco_ministry?: string | null
  source_url?: string | null
}

export interface PrimaryCandidate {
  standard_id: number
  standard_number: string
  title: string
  confidence: number
  is_status_label: string
  superseded_by?: string | null
  why: string
  conflict_warning?: string | null
  certification: CertificationInfo
  differentiator?: string | null
}

export interface AlliedItem {
  standard_number: string
  title: string
  edge_type: string
  category: string
  status?: string | null
  latest_edition_year?: number | null
}

export interface AlliedGroup {
  normative_references: AlliedItem[]
  test_methods: AlliedItem[]
  terminology: AlliedItem[]
  safety_standards: AlliedItem[]
  installation_standards: AlliedItem[]
  related_product_standards: AlliedItem[]
}

export interface DisambiguationOption {
  label: string
  standard_number: string
  rewritten_query: string
}

export interface RecommendResponse {
  status: 'ok' | 'ambiguous' | 'out_of_scope'
  primary: PrimaryCandidate[]
  allied: AlliedGroup
  disambiguation_question?: string | null
  disambiguation_options?: DisambiguationOption[] | null
  custom_option_text?: string | null
  candidates?: PrimaryCandidate[] | null
  message?: string | null
  extracted_spec?: ExtractedSpec | null
  timings: Record<string, number>
}

export interface RecommendRequest {
  query?: string
  extracted?: ExtractedSpec
  selected_option?: string
  language?: string
}

export async function getRecommendations(req: RecommendRequest | string): Promise<RecommendResponse> {
  const payload = typeof req === 'string' ? { query: req } : req
  const res = await fetch('/api/recommend', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.text().catch(() => res.statusText)
    throw new Error(`API ${res.status}: ${err}`)
  }
  return res.json() as Promise<RecommendResponse>
}


// ---------------------------------------------------------------------------
// frontend/src/lib/auditApi.ts
// Typed client for Tender Compliance Audit v2 API (/api/audit)
// Verified directly against backend/app/routers/audit_v2.py
// ---------------------------------------------------------------------------

export interface CreateJobRequest {
  file_paths?: string[]
  raw_items?: Array<{
    description: string
    technical_spec?: string
    quantity?: string | number
    unit?: string
    material_code?: string
    [key: string]: any
  }>
  doc_type?: 'gem' | 'generic' | string
}

export interface AuditJobDTO {
  id: string
  status: 'pending' | 'running' | 'done' | 'failed' | 'timeout' | string
  filenames: string[] | null
  doc_type: string | null
  total_items: number
  done_items: number
  coverage: number | null
  currency: number | null
  qco_compliance: number | null
  coverage_denominator: number | null
  currency_denominator: number | null
  qco_denominator: number | null
  status_counts: Record<string, number>
  summary: string | null
  error_msg: string | null
  created_at: string
  updated_at: string
}

export interface ItemEvidence {
  quote?: string
  page_no?: number
  doc_name?: string
  block_idx?: number
  tier?: string
  description?: string
  [key: string]: any
}

export interface ItemFindingDTO {
  code: string
  severity: 'critical' | 'error' | 'warning' | 'info' | string
  message: string
  evidence: ItemEvidence
  details: Record<string, any>
}

export interface ResolvedStandardDTO {
  raw_citation: string
  base_key: string
  part: string | null
  cited_year: number | null
  resolved_standard_number: string | null
  resolved_year: number | null
  status: string
  is_withdrawn: boolean
  successor_standard_number: string | null
  successor_year: number | null
  qco_mandatory: boolean
  qco_ministry: string | null
  quote: {
    quote_text: string
    page_no: number
    doc_name: string
    block_idx: number
    tier: string
  } | null
  mention_tier?: string
}

export interface RecommendedStandardDTO {
  cited: string
  recommended: string
  year: number | null
  reason: string
}

export interface AuditedItemDTO {
  seq_no: number
  item_id: string
  description: string
  quantity: string | number | null
  unit: string | null
  status: 'compliant' | 'incomplete' | 'outdated' | 'superseded' | 'conflict' | 'missing' | 'cannot_verify' | string
  badge_color: 'green' | 'yellow' | 'orange' | 'red' | 'gray' | 'purple' | string
  findings: ItemFindingDTO[]
  cited_standards: ResolvedStandardDTO[]
  recommended_standards: RecommendedStandardDTO[]
  source_tier: string
  page_refs: number[]
  processing_ms?: number
  technical_spec?: string
  material_code?: string
}

export interface MetricScore {
  score: number | null
  denominator: number | null
  display: string
}

export interface AuditScorecard {
  coverage: MetricScore
  currency: MetricScore
  qco_compliance: MetricScore
}

export interface AuditJobPollResponse extends AuditJobDTO {
  items: AuditedItemDTO[]
}

export interface AuditResultsResponse {
  job_id: string
  status: string
  total_items: number
  done_items: number
  scorecard: AuditScorecard
  status_counts: Record<string, number>
  summary: string
  items: AuditedItemDTO[]
  created_at: string
  updated_at: string
}

export interface RerunItemResponse {
  message: string
  item: AuditedItemDTO
  job_status: AuditJobDTO
}

// ── API Fetch Helper ──────────────────────────────────────────────────────────

async function apiRequest<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  if (!res.ok) {
    let errMsg = `HTTP ${res.status} ${res.statusText}`
    try {
      const data = await res.json()
      if (data.detail) errMsg = data.detail
    } catch {
      // fallback
    }
    throw new Error(errMsg)
  }
  return res.json() as Promise<T>
}

// ── Route Implementations ───────────────────────────────────────────────────

/**
 * 1. POST /api/audit/jobs
 * Creates an asynchronous audit job from pre-parsed items or server file paths.
 */
export async function createAuditJob(payload: CreateJobRequest): Promise<AuditJobDTO> {
  return apiRequest<AuditJobDTO>('/api/audit/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

/**
 * 2. POST /api/audit/upload
 * Uploads tender files (PDF, DOCX, XLSX) and launches asynchronous audit job.
 */
export async function uploadAuditFiles(files: File[], docType: string = 'gem'): Promise<AuditJobDTO> {
  const formData = new FormData()
  for (const f of files) {
    formData.append('files', f)
  }
  formData.append('doc_type', docType)

  return apiRequest<AuditJobDTO>('/api/audit/upload', {
    method: 'POST',
    body: formData,
  })
}

/**
 * 3. GET /api/audit/jobs/{job_id}
 * Polls progress of an audit job (returns progressive items completed so far).
 */
export async function getAuditJobPoll(jobId: string): Promise<AuditJobPollResponse> {
  return apiRequest<AuditJobPollResponse>(`/api/audit/jobs/${encodeURIComponent(jobId)}`)
}

/**
 * 4. GET /api/audit/jobs/{job_id}/results
 * Fetches complete scorecard, status distribution, and all items for finished/running job.
 */
export async function getAuditJobResults(jobId: string): Promise<AuditResultsResponse> {
  return apiRequest<AuditResultsResponse>(`/api/audit/jobs/${encodeURIComponent(jobId)}/results`)
}

/**
 * 5. POST /api/audit/jobs/{job_id}/items/{seq_no}/rerun
 * Re-runs audit for a single line item, returning the updated item and refreshed job summary.
 */
export async function rerunAuditItem(jobId: string, seqNo: number): Promise<RerunItemResponse> {
  return apiRequest<RerunItemResponse>(`/api/audit/jobs/${encodeURIComponent(jobId)}/items/${seqNo}/rerun`, {
    method: 'POST',
  })
}

/**
 * 6. GET /api/audit/jobs
 * Lists past audit jobs with pagination.
 */
export async function listAuditJobs(limit: number = 20, offset: number = 0): Promise<AuditJobDTO[]> {
  return apiRequest<AuditJobDTO[]>(`/api/audit/jobs?limit=${limit}&offset=${offset}`)
}

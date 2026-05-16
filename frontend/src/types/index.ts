export interface Entity {
  id: string
  name: string
  type: 'person' | 'organization' | 'product' | 'event' | 'location' | 'technology' | 'concept'
  aliases: string[]
  description: string
  first_seen: string
  last_updated: string
}

export interface Relation {
  id: string
  source_id: string
  target_id: string
  relation_type: string
  valid_from: string | null
  valid_to: string | null
  confidence: number
  is_active: boolean
}

export interface QueryResponse {
  query_id: string
  answer: string
  confidence: number
  intent: string
  reasoning_trace: ReasoningStep[]
  sources: SourceReference[]
  conflicts: ConflictSummary[]
}

export interface ReasoningStep {
  step_id: number
  action: string
  tool: string
  input_params: Record<string, unknown>
  output_summary: string
  duration_ms: number
}

export interface SourceReference {
  document_id: string
  document_title: string
  chunk_text: string
  confidence: number
  relevance_score: number
}

export interface ConflictSummary {
  id: string
  type: 'temporal_overlap' | 'logical_contradiction' | 'source_disagreement'
  description: string
}

export interface DocumentInfo {
  id: string
  filename: string
  status: 'pending' | 'processing' | 'extracting' | 'merging' | 'completed' | 'failed'
  entity_count: number
  relation_count: number
  ingested_at: string
}

export interface GraphStats {
  total_entities: number
  total_relations: number
  total_documents: number
  active_conflicts: number
}

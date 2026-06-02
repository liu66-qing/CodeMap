const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`)
  }
  return res.json()
}

export const api = {
  // Documents
  uploadDocument: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch(`${BASE_URL}/documents`, { method: 'POST', body: formData })
    return res.json()
  },
  listDocuments: () => request<any[]>('/documents'),

  // Query
  query: (question: string, includeReasoning = true) =>
    request<any>('/query', {
      method: 'POST',
      body: JSON.stringify({ question, include_reasoning: includeReasoning }),
    }),

  // Graph
  searchEntities: (q: string) => request<any[]>(`/graph/entities?q=${encodeURIComponent(q)}`),
  getNeighborhood: (entityId: string, hops = 2) =>
    request<any>(`/graph/entities/${entityId}/neighborhood?hops=${hops}`),
  getGraphStats: () => request<any>('/graph/stats'),

  // Conflicts
  listConflicts: () => request<any>('/conflicts'),
  resolveConflict: (id: string, resolution: string, note?: string) =>
    request<any>(`/conflicts/${id}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ resolution, note }),
    }),

  // Timeline
  getEntityTimeline: (entityId: string) => request<any>(`/timeline/entity/${entityId}`),
  getSnapshot: (timestamp: string) =>
    request<any>(`/timeline/snapshot?timestamp=${encodeURIComponent(timestamp)}`),
  getDiff: (from: string, to: string) =>
    request<any>(`/timeline/diff?from_ts=${encodeURIComponent(from)}&to_ts=${encodeURIComponent(to)}`),

  // === Code repositories (code-evolution analysis) ===
  // List repositories that have been analyzed.
  listRepos: () => request<{ repositories: RepoSummary[]; total: number }>('/repositories'),
  // Kick off analysis. Provide a GitHub URL (repoUrl) or a local path (repoPath);
  // optional subdir scopes to a sub-app inside a monorepo. Runs async on the backend.
  analyzeRepo: (opts: {
    repoUrl?: string
    repoPath?: string
    repoId?: string
    subdir?: string
    maxCommits?: number
    entryPoint?: string
  }) =>
    request<AnalyzeRepoResponse>('/repositories', {
      method: 'POST',
      body: JSON.stringify({
        repo_url: opts.repoUrl,
        repo_path: opts.repoPath,
        repo_id: opts.repoId,
        subdir: opts.subdir,
        max_commits: opts.maxCommits,
        entry_point: opts.entryPoint,
      }),
    }),
  // Code graph (nodes = symbols, edges = CALLS/IMPORTS/INHERITS/DEFINES).
  getRepoGraph: (repoId: string, limit = 300) =>
    request<RepoGraphResponse>(`/repositories/${encodeURIComponent(repoId)}/graph?limit=${limit}`),
  // Commit history with per-commit counts and breaking-change flag.
  getRepoCommits: (repoId: string) =>
    request<RepoCommitsResponse>(`/repositories/${encodeURIComponent(repoId)}/commits`),
  // Detected breaking changes for a repo.
  getBreakingChanges: (repoId: string) =>
    request<BreakingChangesResponse>(`/repositories/${encodeURIComponent(repoId)}/breaking-changes`),
  // Node/relation/commit/breaking counts.
  getRepoStats: (repoId: string) =>
    request<RepoStats>(`/repositories/${encodeURIComponent(repoId)}/stats`),

  // === Code understanding (architecture / tour / review / symbol detail) ===
  // Architecture summary: layers / patterns / module boundaries.
  getArchitecture: (repoId: string, recompute = false) =>
    request<{ repo_id: string; architecture: ArchitectureSummary | null; message?: string }>(
      `/repositories/${encodeURIComponent(repoId)}/architecture${recompute ? '?recompute=true' : ''}`
    ),
  // Narrated code tour. Pass entryPoint to start somewhere specific.
  getTour: (repoId: string, entryPoint?: string) =>
    request<{ repo_id: string; tour: CodeTour | null; message?: string }>(
      `/repositories/${encodeURIComponent(repoId)}/tour${entryPoint ? `?entry_point=${encodeURIComponent(entryPoint)}` : ''}`
    ),
  // Review report: contradictions / omissions + confidence.
  getReview: (repoId: string) =>
    request<{ repo_id: string; review: ReviewReport | null; message?: string }>(
      `/repositories/${encodeURIComponent(repoId)}/review`
    ),
  // Guided learning path: ordered, layer-grouped reading list for newcomers.
  getLearningPath: (repoId: string) =>
    request<{ repo_id: string; learning_path: LearningPath | null; message?: string }>(
      `/repositories/${encodeURIComponent(repoId)}/learning-path`
    ),
  // Module-card system map: cards (modules) + aggregated dependency edges + meta.
  getModules: (repoId: string) =>
    request<{ repo_id: string; module_map: ModuleMap | null; message?: string }>(
      `/repositories/${encodeURIComponent(repoId)}/modules`
    ),
  // Module mechanism analysis: reads real code bodies, explains HOW a module works.
  getModuleMechanism: (repoId: string, moduleId: string) =>
    request<{ repo_id: string; module: string; mechanism: MechanismAnalysis | null; message?: string }>(
      `/repositories/${encodeURIComponent(repoId)}/modules/${encodeURIComponent(moduleId)}/mechanism`
    ),
  // Source code snippet for a symbol (from on-disk clone).
  getSymbolSource: (repoId: string, symbol: string, context = 3) =>
    request<{ repo_id: string; symbol: string; source: SourceSnippet | null; message?: string }>(
      `/repositories/${encodeURIComponent(repoId)}/symbols/${encodeURIComponent(symbol)}/source?context=${context}`
    ),
  // Generic source snippet (any file + line range).
  getSourceSnippet: (repoId: string, path: string, start: number, end: number) =>
    request<{ repo_id: string; source: SourceSnippet | null; message?: string }>(
      `/repositories/${encodeURIComponent(repoId)}/source?path=${encodeURIComponent(path)}&start=${start}&end=${end}`
    ),
  // Ask a question about the codebase (grounded in real source + citations).
  askCodebase: (repoId: string, question: string) =>
    request<AskCodebaseResponse>(
      `/repositories/${encodeURIComponent(repoId)}/ask`,
      { method: 'POST', body: JSON.stringify({ question }) }
    ),
  // Quickstart: how to install, run, and find the entry point.
  getQuickstart: (repoId: string) =>
    request<{ repo_id: string; quickstart: QuickstartInfo }>(
      `/repositories/${encodeURIComponent(repoId)}/quickstart`
    ),
  // Full detail for one symbol: callers / callees / module / change history.
  getSymbolDetail: (repoId: string, symbol: string) =>
    request<SymbolDetail>(
      `/repositories/${encodeURIComponent(repoId)}/symbols/${encodeURIComponent(symbol)}`
    ),
  // Plain-language, persona-tuned summary of a symbol (junior | pm | senior).
  explainSymbol: (repoId: string, symbol: string, persona: Persona) =>
    request<{ repo_id: string; explanation: SymbolExplanation | null; message?: string }>(
      `/repositories/${encodeURIComponent(repoId)}/symbols/${encodeURIComponent(symbol)}/explain?persona=${persona}`
    ),
  // Repo-scoped code-symbol search (global search bar in GraphExplorer).
  searchRepoSymbols: (repoId: string, q: string) =>
    request<CodeGraphNode[]>(
      `/graph/entities?repo_id=${encodeURIComponent(repoId)}&q=${encodeURIComponent(q)}`
    ),

  // Admin
  healthCheck: () => request<any>('/admin/health'),

  // === Multi-agent analysis (4-stage pipeline: overview / mainflow / showcase / takeaway) ===
  // Submit a repo URL or local path; returns a task_id that you poll via getAnalysisStatus.
  startAnalysis: (repoUrl: string) =>
    request<AnalysisStartResponse>('/analysis/repos/analyze', {
      method: 'POST',
      body: JSON.stringify({ repo_url: repoUrl }),
    }),
  getAnalysisStatus: (taskId: string) =>
    request<AnalysisStatusResponse>(`/analysis/repos/${encodeURIComponent(taskId)}/status`),
  getAnalysisFull: (taskId: string) =>
    request<AnalysisFullResponse>(`/analysis/repos/${encodeURIComponent(taskId)}`),
  getAnalysisOverview: (taskId: string) =>
    request<AnalysisStageResponse<OverviewStageData>>(
      `/analysis/repos/${encodeURIComponent(taskId)}/overview`
    ),
  getAnalysisMainflow: (taskId: string) =>
    request<AnalysisStageResponse<MainflowStageData>>(
      `/analysis/repos/${encodeURIComponent(taskId)}/mainflow`
    ),
  getAnalysisShowcase: (taskId: string) =>
    request<AnalysisStageResponse<ShowcaseStageData>>(
      `/analysis/repos/${encodeURIComponent(taskId)}/showcase`
    ),
  getAnalysisTakeaway: (taskId: string) =>
    request<AnalysisStageResponse<TakeawayStageData>>(
      `/analysis/repos/${encodeURIComponent(taskId)}/takeaway`
    ),
  getAnalysisTraces: (taskId: string) =>
    request<AnalysisTracesResponse>(`/analysis/repos/${encodeURIComponent(taskId)}/traces`),

  // === Learning Map (progress tracking, achievements, path) ===
  recordLearningEvent: (event: LearningEventRequest) =>
    request<{ ok: boolean; event: LearningEvent }>('/learning/events', {
      method: 'POST',
      body: JSON.stringify(event),
    }),
  getLearningProgress: (userId: string, taskId?: string) =>
    request<LearningProgress>(
      `/learning/progress/${encodeURIComponent(userId)}${taskId ? `?task_id=${encodeURIComponent(taskId)}` : ''}`
    ),
  getLearningAchievements: (userId: string) =>
    request<LearningAchievements>(`/learning/achievements/${encodeURIComponent(userId)}`),
  getLearningMapPath: (userId: string, level: string = 'standard') =>
    request<LearningPath2>(`/learning/path/${encodeURIComponent(userId)}?level=${level}`),
  getLearningStats: (userId: string) =>
    request<LearningMapStats>(`/learning/stats/${encodeURIComponent(userId)}`),
  getLearningHint: (userId: string) =>
    request<LearningHint>(`/learning/hint/${encodeURIComponent(userId)}`),
}

// === Code-domain response shapes (match the backend repositories endpoints) ===

export interface RepoSummary {
  repo_id: string
  nodes: number
  commits: number
}

export interface AnalyzeRepoResponse {
  repo_id: string
  status: string
  repo_path: string
  mode: string // "async" | "background"
}

export interface CodeGraphNode {
  id: string
  name: string
  kind: string | null // module | class | function | method
  signature: string | null
  file_path: string | null
}

export interface CodeGraphEdge {
  source: string
  target: string
  type: string // CALLS | IMPORTS | INHERITS | DEFINES
}

export interface RepoGraphResponse {
  repo_id: string
  nodes: CodeGraphNode[]
  edges: CodeGraphEdge[]
}

export interface RepoCommit {
  sha: string
  short_sha: string
  subject: string
  author: string | null
  timestamp: string | null
  callables: number | null
  files: number | null
  breaking_changes: number
}

export interface RepoCommitsResponse {
  repo_id: string
  commits: RepoCommit[]
  total: number
}

export interface BreakingChange {
  symbol: string
  type: string // SIGNATURE_CHANGED | REQUIRED_PARAM_ADDED | SYMBOL_REMOVED (in description)
  description: string
  old_signature: string | null
  new_signature: string | null
  affected_callers: string[] | null
  commit: string
  commit_subject: string
}

export interface BreakingChangesResponse {
  repo_id: string
  breaking_changes: BreakingChange[]
  total: number
}

export interface RepoStats {
  repo_id: string
  nodes: number
  relations: number
  commits: number
  breaking_changes: number
}

// === Code-understanding response shapes ===

export interface ArchLayer {
  name: string
  description: string
  modules: string[]
}

export interface ArchPattern {
  name: string
  evidence: string
  modules: string[]
}

export interface ArchBoundary {
  module: string
  role: string
  fan_in?: number
  fan_out?: number
  files?: string[]
  reason?: string
}

export interface ArchitectureSummary {
  layers: ArchLayer[]
  patterns: ArchPattern[]
  boundaries: ArchBoundary[]
  summary: string
  generated_by: 'llm' | 'heuristic' | 'empty'
  module_count?: number
}

export interface TourStep {
  order: number
  symbol: string
  kind: string
  signature: string
  file_path: string
  depth: number
  calls: string[]
  explanation: string
}

export interface CodeTour {
  entry_point: string | null
  auto_detected: boolean
  steps: TourStep[]
  generated_by: 'llm' | 'structural' | 'empty' | 'none'
}

export interface ReviewIssue {
  severity: 'error' | 'warning' | 'info'
  kind: string
  detail: string
}

export interface ReviewReport {
  issues: ReviewIssue[]
  coverage: { modules_total: number; modules_placed: number; unplaced: string[] }
  report: string
  confidence: number
  generated_by: 'llm' | 'deterministic'
}

export interface SymbolDetail {
  repo_id: string
  symbol: string
  node: CodeGraphNode | null
  callers: { caller: string; file_path: string | null }[]
  callees: { callee: string; file_path: string | null }[]
  module: string | null
  history: {
    commit: string
    subject: string
    change: string
    old_signature: string | null
    new_signature: string | null
  }[]
  related_tests?: { test_symbol: string; confidence: number; reason: string }[]
}

export type Persona = 'junior' | 'pm' | 'senior'

export interface LearningStep {
  order: number
  symbol: string
  kind: string
  layer: string
  signature: string
  file_path: string
  importance: number
  reason: string
}

export interface LearningPath {
  steps: LearningStep[]
  generated_by: 'llm' | 'structural' | 'empty'
}

// === Module-card system map ===

export interface ModuleCardSymbol {
  name: string
  kind: string
  signature: string | null
  file_path: string | null
}

export interface ModuleCard {
  id: string
  title: string
  module: string
  layer: string
  complexity: 'simple' | 'moderate' | 'complex'
  symbol_count: number
  file_count: number
  kinds: Record<string, number>
  files: string[]
  entities: string[]
  symbols: ModuleCardSymbol[]
  summary: string
}

export interface ModuleEdge {
  source: string
  target: string
  type: string
  weight: number
}

export interface ModuleMapMeta {
  nodes: number
  edges: number
  cards: number
  layers: number
  kinds: Record<string, number>
  file_types: Record<string, number>
  layer_counts: Record<string, number>
}

export interface ModuleMap {
  cards: ModuleCard[]
  edges: ModuleEdge[]
  meta: ModuleMapMeta
  generated_by: 'llm' | 'structural' | 'empty'
}

// === Mechanism analysis ===

export interface MechanismPart {
  symbol: string
  role: string
}

export interface MechanismAnalysis {
  module: string
  overview: string
  parts: MechanismPart[]
  connections: string
  data_flow: string
  state_memory: string | null
  grounded_in: string[]
  generated_by: 'llm' | 'structural'
}

// === Source code viewer ===

export interface SourceSnippet {
  file_path: string
  line_start: number
  line_end: number
  code: string
  language: string
  truncated: boolean
}

// === Ask codebase ===

export interface AskSource {
  symbol: string
  file_path: string
  line_start: number
  line_end: number
  snippet: string
  relevance?: string
}

export interface AskCodebaseResponse {
  repo_id: string
  question: string
  answer: string
  sources: AskSource[]
  generated_by: 'llm' | 'retrieval_only' | 'empty' | 'error'
}

// === Quickstart ===

export interface QuickstartInfo {
  available: boolean
  install?: string
  run?: string
  entrypoints?: string[]
  stack?: string[]
  has_docker?: boolean
  docker_cmd?: string
  make_targets?: string[]
  readme_excerpt?: string
  scripts?: Record<string, string>
  message?: string
}

export interface SymbolExplanation {
  symbol: string
  persona: Persona
  summary: string
  role: string
  generated_by: 'llm' | 'structural'
}

// === Multi-agent analysis (matches backend src/evograph/api/v1/analysis.py) ===

export interface AnalysisStartResponse {
  task_id: string
  status: string
}

export interface AnalysisProgressEntry {
  status: 'running' | 'done' | 'failed'
  ts: number
}

export interface AnalysisStatusResponse {
  task_id: string
  status: 'running' | 'done' | 'failed'
  progress: Record<string, AnalysisProgressEntry>
  started_at: number
  finished_at: number | null
  error: string | null
}

export interface AnalysisStageResponse<T> {
  task_id: string
  stage: string
  status: 'pending' | 'done' | 'failed'
  data: T | null
  error?: string
}

export interface OverviewStageData {
  positioning: string
  coreProblem: string
  mentalModel: {
    whatIsIt: { title: string; description: string }
    whoIsItFor: { title: string; description: string }
    howItWorks: { title: string; description: string }
  }
  readingOrder: { step: number; title: string; description: string; githubUrl: string }[]
  architectureSummary: string
  _signals?: { entry_points: string[]; architecture_style: string; layers: string[] }
}

export interface MainflowFlowNode {
  id: number
  title: string
  note: string
  detail: {
    explanation?: string
    whatToLook?: string
    whyFirst?: string
    outcome?: string
  }
}

export interface MainflowEvidenceLink {
  label: string
  githubUrl: string
}

export interface MainflowStageData {
  flowNodes: MainflowFlowNode[]
  evidenceLinks: MainflowEvidenceLink[]
}

export interface ShowcaseHighlight {
  title: string
  problem: string
  solution: string
  tradeoff: string
  evidence: { file: string; snippet: string; githubUrl: string }
}

export interface ShowcaseStageData {
  highlights: ShowcaseHighlight[]
}

export interface TakeawayPattern {
  name: string
  scenario: string
  coreIdea: string
  minimalCode: { language: string; code: string }
  limitations: string
  sourceHighlight?: string
}

export interface TakeawayStageData {
  patterns: TakeawayPattern[]
}

export interface AnalysisFullResponse {
  task_id: string
  status: 'running' | 'done' | 'failed'
  result: {
    overview?: OverviewStageData
    mainflow?: MainflowStageData
    showcase?: ShowcaseStageData
    takeaway?: TakeawayStageData
    _traces?: AnalysisTraces
  }
}

export interface AnalysisTraceToolCall {
  tool_name: string
  args: Record<string, unknown>
  result_preview: string
  duration_ms: number
  token_cost: number
  error: string | null
}

export interface AnalysisTraceLLMCall {
  prompt_chars: number
  response_chars: number
  duration_ms: number
  tokens_in: number
  tokens_out: number
  model: string
}

export interface AnalysisAgentTrace {
  agent_name: string
  started_at: number
  finished_at: number
  duration_ms: number
  tool_calls: AnalysisTraceToolCall[]
  llm_calls_detail: AnalysisTraceLLMCall[]
  llm_calls: number
  total_tokens: number
  output: unknown
  error: string | null
}

export interface AnalysisTraces {
  overview: AnalysisAgentTrace
  mainflow: AnalysisAgentTrace
  showcase: AnalysisAgentTrace
  takeaway: AnalysisAgentTrace
}

export interface AnalysisTracesResponse {
  task_id: string
  traces: AnalysisTraces
}

// === Learning Map types ===

export interface LearningEventRequest {
  user_id?: string
  task_id?: string
  repo_url?: string
  stage: string
  type: 'visit' | 'complete' | 'time_spent' | 'highlight_read' | 'pattern_copied'
  value?: number
  meta?: Record<string, unknown>
}

export interface LearningEvent {
  ts: number
  task_id: string
  repo_url: string
  stage: string
  type: string
  value: number
  meta: Record<string, unknown>
}

export interface LearningStageProgress {
  visited: boolean
  time_spent_seconds: number
  highlights_read: number
  patterns_copied: number
  complete: boolean
}

export interface LearningProgress {
  user_id: string
  task_id: string | null
  overall_percent: number
  stages: Record<string, LearningStageProgress>
  total_events: number
  distinct_repos: number
  total_time_seconds: number
  days_active: number
}

export interface LearningBadge {
  id: string
  title: string
  description: string
  icon: string
  unlocked: boolean
  unlocked_at: number | null
}

export interface LearningAchievements {
  user_id: string
  badges: LearningBadge[]
  unlocked_count: number
  total_count: number
}

export interface LearningPathStep {
  stage: string
  title: string
  action: 'learn' | 'revisit' | 'skim'
  estimated_minutes: number
  description: string
  status: 'pending' | 'done' | 'skipped'
}

export interface LearningPath2 {
  level: string
  total_minutes: number
  steps: LearningPathStep[]
  next_action: string
  mentor_hint: string
}

export interface LearningHint {
  user_id: string
  hint: string
  next_action: string
  overall_percent: number
}

export interface LearningMapStats {
  progress: LearningProgress
  badges: LearningBadge[]
  path: LearningPath2
}

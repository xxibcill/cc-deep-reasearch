import axios from 'axios';
import { dashboardRuntimeConfig } from '@/lib/runtime-config';

export interface KnowledgeNode {
  id: string;
  kind: string;
  label: string;
  properties: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

export interface KnowledgeEdge {
  id: string;
  kind: string;
  source_id: string;
  target_id: string;
  properties?: Record<string, unknown>;
}

export interface GraphSnapshot {
  exported_at: string;
  nodes: KnowledgeNode[];
  edges: KnowledgeEdge[];
}

export interface GraphSummary {
  total_nodes: number;
  total_edges: number;
  nodes_by_kind: Record<string, number>;
  edges_by_kind: Record<string, number>;
  vault_initialized: boolean;
}

export interface LintFinding {
  severity: 'error' | 'warning' | 'info';
  category: string;
  message: string;
  page_path?: string;
}

export interface LintFindingsResponse {
  findings: LintFinding[];
  total: number;
  error_count: number;
  warning_count: number;
  info_count: number;
  message?: string;
}

export interface NodeNeighbors {
  node: KnowledgeNode;
  neighbors: KnowledgeNode[];
  edges: KnowledgeEdge[];
}

export interface SessionContribution {
  session_id: string;
  knowledge_nodes_influenced: number;
  influenced_node_ids: string[];
  note?: string;
}

const knowledgeClient = axios.create({
  baseURL: `${dashboardRuntimeConfig.apiBaseUrl}/knowledge`,
  timeout: 15000,
});

export async function fetchGraphSummary(): Promise<GraphSummary> {
  const response = await knowledgeClient.get('/summary');
  return response.data;
}

export async function fetchGraphFull(): Promise<GraphSnapshot> {
  const response = await knowledgeClient.get('/graph');
  return response.data;
}

export async function fetchNodes(
  kind?: string,
  limit = 100,
  offset = 0,
): Promise<{ nodes: KnowledgeNode[]; total: number; limit: number; offset: number }> {
  const params = new URLSearchParams();
  if (kind) params.set('kind', kind);
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  const response = await knowledgeClient.get('/nodes', { params });
  return response.data;
}

export async function fetchNode(nodeId: string): Promise<KnowledgeNode> {
  const response = await knowledgeClient.get(`/nodes/${nodeId}`);
  return response.data;
}

export async function fetchNodeNeighbors(nodeId: string): Promise<NodeNeighbors> {
  const response = await knowledgeClient.get(`/nodes/${nodeId}/neighbors`);
  return response.data;
}

export async function fetchLintFindings(): Promise<LintFindingsResponse> {
  const response = await knowledgeClient.get('/lint-findings');
  return response.data;
}

export async function fetchSessionContribution(
  sessionId: string,
): Promise<SessionContribution> {
  const response = await knowledgeClient.get(`/session-contribution/${sessionId}`);
  return response.data;
}

export async function fetchVaultStatus(): Promise<{
  initialized: boolean;
  vault_path: string;
  can_initialize: boolean;
  has_index?: boolean;
  has_graph_index?: boolean;
  raw_session_count?: number;
  wiki_page_count?: number;
}> {
  const response = await knowledgeClient.get('/status');
  return response.data;
}

export interface InitVaultResponse {
  initialized: boolean;
  dry_run: boolean;
  created: Record<string, string>;
  error?: string;
}

export async function initVault(
  configPath?: string,
  dryRun = false,
): Promise<InitVaultResponse> {
  const params = new URLSearchParams();
  if (configPath) params.set('config_path', configPath);
  if (dryRun) params.set('dry_run', 'true');
  const response = await knowledgeClient.post('/init', null, { params });
  return response.data;
}

export interface BackfillResponse {
  dry_run: boolean;
  total_sessions: number;
  session_ids?: string[];
  ingested: number;
  failed: number;
  errors: Array<{ session_id: string; error: string }>;
  error?: string;
}

export async function backfillVault(
  limit?: number,
  dryRun = false,
): Promise<BackfillResponse> {
  const params = new URLSearchParams();
  if (limit != null) params.set('limit', String(limit));
  if (dryRun) params.set('dry_run', 'true');
  const response = await knowledgeClient.post('/backfill', null, { params });
  return response.data;
}

export interface RebuildIndexResponse {
  rebuilt: boolean;
  db_path: string;
  error?: string;
}

export async function rebuildIndex(configPath?: string): Promise<RebuildIndexResponse> {
  const params = new URLSearchParams();
  if (configPath) params.set('config_path', configPath);
  const response = await knowledgeClient.post('/rebuild-index', null, { params });
  return response.data;
}

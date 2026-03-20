export interface SearchCacheEntry {
  cache_key: string;
  provider: string;
  normalized_query: string;
  created_at: string;
  expires_at: string;
  last_accessed_at: string;
  hit_count: number;
  is_expired: boolean;
}

export interface SearchCacheListResponse {
  entries: SearchCacheEntry[];
  total: number;
  message?: string;
}

export interface SearchCacheStats {
  enabled: boolean;
  db_path: string;
  db_exists: boolean;
  ttl_seconds: number;
  max_entries: number;
  total_entries: number;
  active_entries: number;
  expired_entries: number;
  total_hits: number;
  approximate_size_bytes: number;
}

export interface SearchCachePurgeResponse {
  purged: number;
  message?: string;
  error?: string;
}

export interface SearchCacheDeleteResponse {
  cache_key?: string;
  deleted: boolean;
  error?: string;
}

export interface SearchCacheClearResponse {
  cleared: number;
  message?: string;
  error?: string;
}

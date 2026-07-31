import { apiClient } from '@/lib/api/client';
import type {
  SearchCacheListResponse,
  SearchCacheStats,
  SearchCachePurgeResponse,
  SearchCacheDeleteResponse,
  SearchCacheClearResponse,
} from '@/types/search-cache';

// Search Cache API helpers

export async function getSearchCacheEntries(
  includeExpired: boolean = false,
  limit: number = 100,
  offset: number = 0
): Promise<SearchCacheListResponse> {
  const response = await apiClient.get<SearchCacheListResponse>('/search-cache', {
    params: { include_expired: includeExpired, limit, offset },
  });
  return response.data;
}

export async function getSearchCacheStats(): Promise<SearchCacheStats> {
  const response = await apiClient.get<SearchCacheStats>('/search-cache/stats');
  return response.data;
}

export async function purgeExpiredSearchCacheEntries(): Promise<SearchCachePurgeResponse> {
  const response = await apiClient.post<SearchCachePurgeResponse>('/search-cache/purge-expired');
  return response.data;
}

export async function deleteSearchCacheEntry(cacheKey: string): Promise<SearchCacheDeleteResponse> {
  const response = await apiClient.delete<SearchCacheDeleteResponse>(`/search-cache/${encodeURIComponent(cacheKey)}`);
  return response.data;
}

export async function clearSearchCache(): Promise<SearchCacheClearResponse> {
  const response = await apiClient.delete<SearchCacheClearResponse>('/search-cache');
  return response.data;
}

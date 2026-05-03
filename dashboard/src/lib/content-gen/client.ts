import axios from 'axios';
import { dashboardRuntimeConfig } from '@/lib/runtime-config';
import { getApiErrorMessage } from '@/lib/api';

export const CONTENT_GEN_TIMEOUT_MS = 30000;
export const SCRIPTING_TIMEOUT_MS = 240000;

export const contentGenClient = axios.create({
  baseURL: `${dashboardRuntimeConfig.apiBaseUrl}/content-gen`,
  timeout: CONTENT_GEN_TIMEOUT_MS,
});

export function getContentGenErrorMessage(error: unknown, fallback: string): string {
  return getApiErrorMessage(error, fallback);
}
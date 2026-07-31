import axios from 'axios';
import { dashboardRuntimeConfig } from '@/lib/runtime-config';

export const apiClient = axios.create({
  baseURL: dashboardRuntimeConfig.apiBaseUrl,
  timeout: 10000,
});

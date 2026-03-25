export interface SecretFieldMetadata {
  field: string;
  persisted_present: boolean;
  effective_present: boolean;
  persisted_count: number;
  effective_count: number;
  overridden: boolean;
}

export type SecretFieldAction = 'replace' | 'clear';

export interface SecretFieldPatch {
  action: SecretFieldAction;
  value?: string | string[] | null;
}

export interface ConfigResponse {
  config_path: string;
  file_exists: boolean;
  persisted_config: Record<string, unknown>;
  effective_config: Record<string, unknown>;
  overridden_fields: string[];
  override_sources: Record<string, string[]>;
  secret_fields: SecretFieldMetadata[];
}

export interface ConfigFieldError {
  field: string;
  code: string;
  message: string;
}

export interface ConfigOverrideConflict {
  field: string;
  env_vars: string[];
  message: string;
}

export interface ConfigPatchErrorResponse {
  error: string;
  fields: ConfigFieldError[];
  conflicts: ConfigOverrideConflict[];
}

export interface ConfigPatchRequest {
  updates: Record<string, unknown | SecretFieldPatch>;
  save_overridden_fields?: boolean;
}

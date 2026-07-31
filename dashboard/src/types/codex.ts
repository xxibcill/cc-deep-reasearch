export type CodexLoginFlow = 'browser' | 'device_code';

export type CodexLoginStatus =
  | 'pending'
  | 'succeeded'
  | 'failed'
  | 'canceling'
  | 'canceled'
  | 'expired';

export interface CodexAccountResponse {
  runtime_status: string;
  authenticated: boolean;
  requires_openai_auth: boolean | null;
  account_type: string | null;
  email: string | null;
  plan_type: string | null;
  error_code: string | null;
  error_message: string | null;
}

export interface CodexLoginResponse {
  login_id: string;
  flow: CodexLoginFlow;
  status: CodexLoginStatus;
  auth_url: string | null;
  verification_url: string | null;
  user_code: string | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
}

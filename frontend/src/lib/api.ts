/**
 * PricePlus API client — typed fetch wrapper.
 * All requests include the JWT bearer token from localStorage.
 * Throws ApiError on non-2xx responses with the error detail from the backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('pp_access_token');
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch { /* ignore */ }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export interface AuthTokens { access_token: string; refresh_token: string; token_type: string; }
export interface User { id: string; email: string; is_active: boolean; created_at: string; }

export const authApi = {
  register: (email: string, password: string) =>
    request<AuthTokens>('/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    request<AuthTokens>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  me: () => request<User>('/auth/me'),
};

// ─── Stores ───────────────────────────────────────────────────────────────────

export interface Store {
  id: string; user_id: string; url: string; display_name: string | null;
  platform: string; status: string; last_error: string | null;
  products_count: number; created_at: string;
}

export const storesApi = {
  list: () => request<{ stores: Store[]; total: number }>('/stores'),
  create: (url: string, display_name?: string) =>
    request<Store>('/stores', { method: 'POST', body: JSON.stringify({ url, display_name }) }),
  delete: (id: string) => request<void>(`/stores/${id}`, { method: 'DELETE' }),
  triggerDiscovery: (id: string) =>
    request<{ run_id: string; message: string }>(`/stores/${id}/discover`, { method: 'POST' }),
  discoveryStatus: (id: string, runId: string) =>
    request<{ status: string; products_discovered: number; products_created: number }>(`/stores/${id}/discover/${runId}`),
};

// ─── Products ─────────────────────────────────────────────────────────────────

export interface DiscoveredProduct {
  id: string; store_id: string; handle: string; product_url: string;
  title: string | null; current_price: number | null; currency: string;
  is_available: boolean; image_url: string | null; is_tracked: boolean;
}

export const productsApi = {
  list: (storeId: string, page = 1, pageSize = 50) =>
    request<{ products: DiscoveredProduct[]; total: number }>(
      `/stores/${storeId}/products?page=${page}&page_size=${pageSize}`
    ),
};

// ─── Tracking ─────────────────────────────────────────────────────────────────

export interface TrackedProduct {
  id: string; user_id: string; discovered_product_id: string;
  is_active: boolean; created_at: string;
  product: DiscoveredProduct;
}

export interface TrackedProductList {
  tracked_products: TrackedProduct[];
  total: number;
  active_count: number;
}

export const trackingApi = {
  list: () => request<TrackedProductList>('/tracked'),
  track: (discoveredProductId: string) =>
    request<TrackedProduct>('/track', { method: 'POST', body: JSON.stringify({ discovered_product_id: discoveredProductId }) }),
  untrack: (trackedId: string) => request<void>(`/tracked/${trackedId}`, { method: 'DELETE' }),
};


// ─── Monitoring ───────────────────────────────────────────────────────────────

export interface TimelineEntry {
  kind: 'snapshot' | 'change'; timestamp: string; price: number | null;
  currency: string; is_available: boolean | null; change_type: string | null;
  old_price: number | null; new_price: number | null; pct_change: number | null;
  error_message: string | null; ref_id: string;
}

export interface TimelineResponse {
  entries: TimelineEntry[]; total_snapshots: number; total_changes: number;
  min_price: number | null; max_price: number | null; latest_price: number | null;
}

export const monitoringApi = {
  timeline: (trackedId: string, limit = 100) =>
    request<TimelineResponse>(`/tracked/${trackedId}/timeline?limit=${limit}`),
  priceChanges: (page = 1) =>
    request<{ changes: PriceChange[]; total: number }>(`/price-changes?page=${page}`),
};

export interface PriceChange {
  id: string; tracked_product_id: string; old_price: number | null;
  new_price: number | null; currency: string; pct_change: number | null;
  change_type: string; alert_sent: boolean; detected_at: string;
}

// ─── Alerts ───────────────────────────────────────────────────────────────────

export interface AlertRule {
  id: string; tracked_product_id: string; condition_type: string;
  threshold_pct: number | null; threshold_price: number | null;
  channel: string; is_enabled: boolean; cool_down_minutes: number;
  last_triggered_at: string | null; created_at: string;
}

export interface Alert {
  id: string; alert_rule_id: string; price_change_id: string | null;
  channel: string; delivered: boolean; trigger_summary: string | null;
  created_at: string;
}

export const alertsApi = {
  listRules: () => request<{ rules: AlertRule[]; total: number }>('/alert-rules'),
  createRule: (data: Partial<AlertRule> & { tracked_product_id: string; condition_type: string }) =>
    request<AlertRule>('/alert-rules', { method: 'POST', body: JSON.stringify(data) }),
  deleteRule: (id: string) => request<void>(`/alert-rules/${id}`, { method: 'DELETE' }),
  toggleRule: (id: string) => request<AlertRule>(`/alert-rules/${id}/toggle`, { method: 'PATCH' }),
  listAlerts: (page = 1) => request<{ alerts: Alert[]; total: number }>(`/alerts?page=${page}`),
  unreadCount: () => request<{ unread_count: number }>('/alerts/unread-count'),
};

// ─── Billing ──────────────────────────────────────────────────────────────────

export interface Plan {
  id: string; name: string; price_usd: number | null;
  max_stores: number; max_tracked_products: number; poll_interval_mins: number; is_active: boolean;
}

export interface Entitlements {
  plan_name: string; max_stores: number; current_stores: number;
  max_tracked_products: number; current_tracked_products: number;
  poll_interval_mins: number; subscription_status: string;
}

export const billingApi = {
  plans: () => request<Plan[]>('/billing/plans'),
  subscription: () => request<{ plan: Plan; status: string; current_period_end: string | null } | null>('/billing/subscription'),
  entitlements: () => request<Entitlements>('/billing/entitlements'),
  checkout: (planId: string, successUrl: string, cancelUrl: string) =>
    request<{ checkout_url: string }>('/billing/checkout', {
      method: 'POST',
      body: JSON.stringify({ plan_id: planId, success_url: successUrl, cancel_url: cancelUrl }),
    }),
  portal: (returnUrl: string) =>
    request<{ portal_url: string }>('/billing/portal', {
      method: 'POST', body: JSON.stringify({ return_url: returnUrl }),
    }),
};

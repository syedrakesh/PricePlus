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

    if (res.status === 401 && typeof window !== 'undefined' && !path.startsWith('/auth/')) {
      localStorage.removeItem('pp_access_token');
      localStorage.removeItem('pp_refresh_token');
      window.location.href = '/login';
    }

    throw new ApiError(res.status, detail);
  }


  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  redirect_url?: string;
  checkout_url?: string | null;
}
export interface User {
  id: string;
  email: string;
  full_name: string | null;
  phone_number: string | null;
  notification_email?: string | null;
  telegram_chat_id?: string | null;
  telegram_bot_token?: string | null;
  email_alerts_enabled?: boolean;
  telegram_alerts_enabled?: boolean;
  is_active: boolean;
  is_superuser: boolean;
  is_verified?: boolean;
  onboarding_completed?: boolean;
  role_slug: string;
  role_name: string;
  permissions: string[];
  created_at: string;
}

export const authApi = {
  register: (email: string, password: string, full_name?: string, plan_slug: string = 'free') =>
    request<AuthTokens>('/auth/register', { method: 'POST', body: JSON.stringify({ email, password, full_name, plan_slug }) }),
  login: (email: string, password: string) =>
    request<AuthTokens>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  me: () => request<User>('/auth/me'),
  completeOnboarding: () => request<{ message: string; onboarding_completed: boolean }>('/auth/complete-onboarding', { method: 'POST' }),
  updateProfile: (data: {
    full_name?: string | null;
    email?: string;
    phone_number?: string | null;
    notification_email?: string | null;
    telegram_chat_id?: string | null;
    telegram_bot_token?: string | null;
    email_alerts_enabled?: boolean;
    telegram_alerts_enabled?: boolean;
  }) => request<User>('/auth/me', { method: 'PATCH', body: JSON.stringify(data) }),
  changePassword: (current_password: string, new_password: string) =>
    request<{ message: string }>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password, new_password }),
    }),
};

// ─── Stores ───────────────────────────────────────────────────────────────────

export interface DiscoveryRunSummary {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'partial' | 'failed';
  products_discovered: number;
  products_fetched: number;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}

export interface Store {
  id: string; user_id: string; url: string; display_name: string | null;
  platform: string; status: string; last_error: string | null;
  last_discovery_at: string | null;
  products_count: number; created_at: string;
  latest_discovery_run: DiscoveryRunSummary | null;
}

export const storesApi = {
  list: () => request<{ stores: Store[]; total: number }>('/stores'),
  get: (id: string) => request<Store>(`/stores/${id}`),
  create: (url: string, display_name?: string) =>
    request<Store>('/stores', { method: 'POST', body: JSON.stringify({ url, display_name }) }),
  delete: (id: string) => request<void>(`/stores/${id}`, { method: 'DELETE' }),
  triggerDiscovery: (id: string) =>
    request<{ run_id: string; message: string }>(`/stores/${id}/discover`, { method: 'POST' }),
  discoveryStatus: (id: string, runId: string) =>
    request<{ status: string; products_discovered: number; products_created: number; products_fetched: number }>(`/stores/${id}/discover/${runId}`),
};

// ─── Products ─────────────────────────────────────────────────────────────────

export interface DiscoveredProduct {
  id: string; store_id: string; handle: string; product_url: string;
  title: string | null; current_price: number | null; compare_at_price: number | null;
  currency: string; is_on_sale: boolean;
  is_discontinued: boolean; image_url: string | null; is_tracked: boolean;
  tracking_status?: string | null;
}

export interface ProductFilters {
  q?: string;
  min_price?: number;
  max_price?: number;
}

export const productsApi = {
  list: (storeId: string, page = 1, pageSize = 50, filters: ProductFilters = {}) => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (filters.q?.trim()) params.append('q', filters.q.trim());
    if (filters.min_price !== undefined) params.append('min_price', String(filters.min_price));
    if (filters.max_price !== undefined) params.append('max_price', String(filters.max_price));

    return request<{ products: DiscoveredProduct[]; total: number; page: number; page_size: number }>(
      `/stores/${storeId}/products?${params.toString()}`
    );
  },
};


// ─── Tracking ─────────────────────────────────────────────────────────────────

export interface TrackedProduct {
  id: string; user_id: string; discovered_product_id: string;
  store_id: string; is_active: boolean; status?: string; created_at: string;
  tracking_interval_minutes?: number | null;
  is_priority?: boolean;
  next_check_at?: string | null;
  handle?: string | null; product_url?: string | null; title?: string | null;
  current_price?: number | null; currency?: string | null;
  image_url?: string | null;
  product?: DiscoveredProduct;
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
  update: (trackedId: string, data: { tracking_interval_minutes?: number | null; is_priority?: boolean }) =>
    request<TrackedProduct>(`/tracked/${trackedId}`, { method: 'PATCH', body: JSON.stringify(data) }),
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

export interface MonitoringEngineStatus {
  status: 'running' | 'idle' | 'stalled' | 'stopped' | 'error';
  is_running: boolean;
  started_at: string | null;
  last_run_at: string | null;
  next_run_at: string | null;
  seconds_until_next_run: number;
  interval_seconds: number;
  total_cycles_run: number;
  last_polled_count: number;
  last_changes_count: number;
  last_error_count: number;
  last_error_message: string | null;
  user_plan_poll_interval_mins?: number;
  seconds_until_next_product_check?: number | null;
  earliest_next_check_at?: string | null;
  user_tracked_count?: number;
}

export const monitoringApi = {
  timeline: (trackedId: string, limit = 100) =>
    request<TimelineResponse>(`/tracked/${trackedId}/timeline?limit=${limit}`),
  priceChanges: (page = 1) =>
    request<{ changes: PriceChange[]; total: number }>(`/price-changes?page=${page}`),
  getEngineStatus: () =>
    request<MonitoringEngineStatus>('/monitoring/engine/status'),
  triggerPollNow: () =>
    request<{ message: string; result: any; engine: MonitoringEngineStatus }>('/monitoring/engine/trigger', { method: 'POST' }),
  restartEngine: () =>
    request<{ message: string; engine: MonitoringEngineStatus }>('/monitoring/engine/restart', { method: 'POST' }),
};

export interface PriceChange {
  id: string; tracked_product_id: string; old_price: number | null;
  new_price: number | null; currency: string; pct_change: number | null;
  change_type: string; alert_sent: boolean; detected_at: string;
}

// ─── Alerts ───────────────────────────────────────────────────────────────────

export interface AlertRule {
  id: string; tracked_product_id: string | null; condition_type: string;
  threshold_pct: number | null; threshold_price: number | null;
  channel: string; webhook_url?: string | null; is_enabled: boolean; cool_down_minutes: number;
  last_triggered_at: string | null; created_at: string;
}

export interface Alert {
  id: string; alert_rule_id: string; price_change_id: string | null;
  channel: string; delivered: boolean; trigger_summary: string | null;
  created_at: string;
}

export const alertsApi = {
  listRules: () => request<{ rules: AlertRule[]; total: number }>('/alert-rules'),
  createRule: (data: Partial<AlertRule> & { tracked_product_id?: string | null; condition_type: string }) =>
    request<AlertRule>('/alert-rules', { method: 'POST', body: JSON.stringify(data) }),
  updateRule: (id: string, data: Partial<AlertRule>) =>
    request<AlertRule>(`/alert-rules/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteRule: (id: string) => request<void>(`/alert-rules/${id}`, { method: 'DELETE' }),
  toggleRule: (id: string) => request<AlertRule>(`/alert-rules/${id}/toggle`, { method: 'PATCH' }),
  listAlerts: (page = 1) => request<{ alerts: Alert[]; total: number }>(`/alerts?page=${page}`),
  unreadCount: () => request<{ unread_count: number }>('/alerts/unread-count'),
  sendTestNotification: (
    channel: 'email' | 'telegram',
    overrides?: { telegram_chat_id?: string | null; telegram_bot_token?: string | null; notification_email?: string | null }
  ) =>
    request<{ success: boolean; message: string }>('/alerts/test-notification', {
      method: 'POST',
      body: JSON.stringify({ channel, ...overrides }),
    }),
};

// ─── Billing & Subscriptions ─────────────────────────────────────────────────

export interface Plan {
  id: string;
  name: string;
  slug?: string;
  price_usd: number | null;
  stripe_price_id?: string | null;
  max_stores: number;
  max_tracked_products: number;
  poll_interval_mins: number;
  max_priority_products?: number;
  is_active: boolean;
  is_public?: boolean;
  features?: Record<string, any>;
}

export interface SubscriptionPlanInfo {
  id: string;
  name: string;
  slug: string;
  price_usd: number;
  max_stores: number;
  max_tracked_products: number;
  poll_interval_mins: number;
  max_priority_products: number;
  features?: Record<string, any>;
}

export interface Subscription {
  id: string;
  plan_id: string;
  plan: SubscriptionPlanInfo | null;
  status: 'active' | 'trialing' | 'past_due' | 'canceled' | string;
  status_label: string;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  current_period_end: string | null;
  created_at: string;
  /** True when subscription is managed directly in DB (no Stripe) */
  is_direct: boolean;
}

export interface Entitlements {
  plan_name: string;
  plan_slug: string;
  plan_id: string;
  max_stores: number;
  current_stores: number;
  paused_stores?: number;
  max_tracked_products: number;
  current_tracked_products: number;
  paused_tracked_products?: number;
  poll_interval_mins: number;
  subscription_status: string;
  is_over_limit?: boolean;
  current_period_end?: string | null;
}

export interface UserUsageSummary {
  plan_id: string; plan_name: string; plan_slug: string; price_usd: number;
  max_stores: number; current_stores: number; paused_stores?: number;
  max_tracked_products: number; current_tracked_products: number;
  paused_tracked_products?: number; min_poll_interval_mins: number;
  max_priority_products: number; current_priority_products: number;
  is_over_limit?: boolean;
  features: Record<string, any>;
}

export const billingApi = {
  plans: () => request<Plan[]>('/billing/plans'),
  getUsage: () => request<UserUsageSummary>('/billing/usage'),
  subscription: () => request<Subscription | null>('/billing/subscription'),
  entitlements: () => request<Entitlements>('/billing/entitlements'),
  checkout: (planId: string, successUrl: string, cancelUrl: string) =>
    request<{ checkout_url: string }>('/billing/checkout', {
      method: 'POST',
      body: JSON.stringify({ plan_id: planId, success_url: successUrl, cancel_url: cancelUrl }),
    }),
  downgrade: (planId: string) =>
    request<Subscription>('/billing/downgrade', {
      method: 'POST',
      body: JSON.stringify({ plan_id: planId }),
    }),
  extend: (months = 1, planId?: string) =>
    request<{ message: string; months_added: number; new_period_end: string; subscription: Subscription }>('/billing/extend', {
      method: 'POST',
      body: JSON.stringify({ months, plan_id: planId }),
    }),
  cancel: () =>
    request<{ message: string; current_period_end: string | null }>('/billing/cancel', {
      method: 'POST',
    }),
  portal: (returnUrl: string) =>
    request<{ portal_url: string }>('/billing/portal', {
      method: 'POST', body: JSON.stringify({ return_url: returnUrl }),
    }),
  verifySession: (sessionId: string) =>
    request<{ message: string; plan_slug: string; plan_name: string; access_token?: string; refresh_token?: string }>('/billing/verify-session', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId }),
    }),
};

export interface PermissionItem {
  code: string;
  name: string;
  category: string;
  description: string;
}

export interface RoleItem {
  id: string;
  slug: string;
  name: string;
  description: string;
  is_system: boolean;
  permissions: string[];
}

export interface RoleCreateRequest {
  slug: string;
  name: string;
  description?: string;
  permissions?: string[];
}

export interface AdminUser {
  id: string;
  email: string;
  full_name: string | null;
  phone_number: string | null;
  is_active: boolean;
  is_superuser: boolean;
  role_slug: string;
  role_name: string;
  custom_permissions: string[];
  permissions: string[];
  created_at: string;
  plan_name: string;
  plan_slug: string | null;
  plan_id: string | null;
  subscription_status: string;
}

export const adminApi = {
  // Plans
  listPlans: () => request<Plan[]>('/billing/admin/plans'),
  createPlan: (data: Partial<Plan>) =>
    request<Plan>('/billing/admin/plans', { method: 'POST', body: JSON.stringify(data) }),
  updatePlan: (id: string, data: Partial<Plan>) =>
    request<Plan>(`/billing/admin/plans/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  assignUserPlan: (userId: string, planId: string, note?: string) =>
    request<Subscription>(`/billing/admin/users/${userId}/subscription`, {
      method: 'PUT',
      body: JSON.stringify({ plan_id: planId, note: note ?? null }),
    }),
  // Users
  listUsers: () => request<AdminUser[]>('/auth/admin/users'),
  updateUser: (
    userId: string,
    data: {
      full_name?: string | null;
      email?: string;
      phone_number?: string | null;
      is_active?: boolean;
      role_slug?: string;
      custom_permissions?: string[];
      plan_id?: string;
    }
  ) =>
    request<AdminUser>(`/auth/admin/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  toggleUserStatus: (userId: string) =>
    request<{ id: string; email: string; is_active: boolean; created_at: string }>(
      `/auth/admin/users/${userId}/status`,
      { method: 'PATCH' }
    ),
  updateUserRole: (userId: string, roleSlug: string, customPermissions?: string[]) =>
    request<AdminUser>(`/auth/admin/users/${userId}/role`, {
      method: 'PATCH',
      body: JSON.stringify({ role_slug: roleSlug, custom_permissions: customPermissions }),
    }),
  // RBAC Matrix & Roles
  listPermissions: () => request<PermissionItem[]>('/auth/admin/permissions'),
  listRoles: () => request<RoleItem[]>('/auth/admin/roles'),
  createRole: (data: RoleCreateRequest) =>
    request<RoleItem>('/auth/admin/roles', { method: 'POST', body: JSON.stringify(data) }),
  updateRoleMatrix: (roleId: string, permissions: string[]) =>
    request<RoleItem>(`/auth/admin/roles/${roleId}/matrix`, {
      method: 'PUT',
      body: JSON.stringify({ permissions }),
    }),
  deleteRole: (roleId: string) =>
    request<void>(`/auth/admin/roles/${roleId}`, { method: 'DELETE' }),
};

// ─── Settings ─────────────────────────────────────────────────────────────────

export interface UserSettings {
  user_id: string;
  discovery_concurrency: number;
  discovery_min_delay: number;
  discovery_max_delay: number;
  tracking_concurrency: number;
  tracking_min_delay: number;
  tracking_max_delay: number;
  default_tracking_interval_minutes?: number;
  preferred_check_hour?: number;
  updated_at: string;
}

export const settingsApi = {
  get: () => request<UserSettings>('/settings'),
  update: (data: {
    discovery_concurrency?: number;
    discovery_min_delay?: number;
    discovery_max_delay?: number;
    tracking_concurrency?: number;
    tracking_min_delay?: number;
    tracking_max_delay?: number;
    default_tracking_interval_minutes?: number;
    preferred_check_hour?: number;
  }) =>
    request<UserSettings>('/settings', {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
};

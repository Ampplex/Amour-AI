import { API_CONFIG } from '../constants/authConfig';

export interface AdminUserAccount {
  id: string;
  namespace: string;
  email: string;
  username: string | null;
  name: string;
  given_name: string;
  family_name: string;
  picture: string;
  auth_provider: 'google' | 'local' | string;
  google_sub: string;
  verified_email: boolean;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  created_at: string;
  updated_at: string;
  last_login: string | null;
  personas_count: number;
  likes_count: number;
}

export interface AdminUserStats {
  total_users: number;
  active_users: number;
  verified_users: number;
  staff_users: number;
  google_users: number;
  local_users: number;
}

export interface AdminUserFilterParams {
  search?: string;
  auth_provider?: 'all' | 'google' | 'local' | string;
  is_active?: 'all' | 'true' | 'false' | string;
  is_staff?: 'all' | 'true' | 'false' | string;
  verified_email?: 'all' | 'true' | 'false' | string;
}

const CANDIDATE_URLS = [
  'http://127.0.0.1:8000/api',
  'http://192.168.1.4:8000/api',
  API_CONFIG.baseUrl,
  'http://10.104.217.217:8000/api',
  'http://192.168.1.2:8000/api',
];

async function fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs = 10000): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(id);
    return res;
  } catch (e) {
    clearTimeout(id);
    throw e;
  }
}

async function tryAdminServerFetch(path: string, options: RequestInit = {}, adminUserId?: string): Promise<Response> {
  const headers = {
    'Content-Type': 'application/json',
    ...(adminUserId ? { 'x-admin-user-id': adminUserId } : {}),
    ...(options.headers || {}),
  };

  let lastError: any = null;

  for (const base of CANDIDATE_URLS) {
    try {
      const url = `${base}${path}`;
      const res = await fetchWithTimeout(url, { ...options, headers }, 8000);
      if (res.ok) return res;
      if (res.status === 400 || res.status === 403 || res.status === 404) {
        return res; // Client error, return directly to handle message
      }
    } catch (e) {
      lastError = e;
    }
  }

  throw lastError || new Error('Network error: Unable to connect to backend server');
}

export async function fetchAdminUsers(
  filters?: AdminUserFilterParams,
  adminUserId?: string
): Promise<{ stats: AdminUserStats; total: number; users: AdminUserAccount[] }> {
  const queryParams = new URLSearchParams();
  if (filters?.search) queryParams.append('search', filters.search);
  if (filters?.auth_provider && filters.auth_provider !== 'all') {
    queryParams.append('auth_provider', filters.auth_provider);
  }
  if (filters?.is_active && filters.is_active !== 'all') {
    queryParams.append('is_active', filters.is_active);
  }
  if (filters?.is_staff && filters.is_staff !== 'all') {
    queryParams.append('is_staff', filters.is_staff);
  }
  if (filters?.verified_email && filters.verified_email !== 'all') {
    queryParams.append('verified_email', filters.verified_email);
  }

  const qs = queryParams.toString();
  const endpoint = `/auth/admin/users/${qs ? `?${qs}` : ''}`;
  const res = await tryAdminServerFetch(endpoint, { method: 'GET' }, adminUserId);

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Failed to fetch users (status: ${res.status})`);
  }

  const data = await res.json();
  return {
    stats: data.stats || {
      total_users: 0,
      active_users: 0,
      verified_users: 0,
      staff_users: 0,
      google_users: 0,
      local_users: 0,
    },
    total: data.total || 0,
    users: data.users || [],
  };
}

export async function fetchAdminUserDetail(
  userId: string,
  adminUserId?: string
): Promise<AdminUserAccount> {
  const res = await tryAdminServerFetch(`/auth/admin/users/${userId}/`, { method: 'GET' }, adminUserId);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || 'Failed to fetch user details');
  }
  const data = await res.json();
  return data.user;
}

export async function createAdminUser(
  userData: Partial<AdminUserAccount> & { password?: string },
  adminUserId?: string
): Promise<AdminUserAccount> {
  const res = await tryAdminServerFetch(
    '/auth/admin/users/',
    {
      method: 'POST',
      body: JSON.stringify(userData),
    },
    adminUserId
  );

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const errorMsg = data.error || (data.email ? data.email[0] : null) || JSON.stringify(data);
    throw new Error(errorMsg || 'Failed to create user');
  }
  return data.user;
}

export async function updateAdminUser(
  userId: string,
  updates: Partial<AdminUserAccount> & { password?: string },
  adminUserId?: string
): Promise<AdminUserAccount> {
  const res = await tryAdminServerFetch(
    `/auth/admin/users/${userId}/`,
    {
      method: 'PATCH',
      body: JSON.stringify(updates),
    },
    adminUserId
  );

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const errorMsg = data.error || JSON.stringify(data);
    throw new Error(errorMsg || 'Failed to update user');
  }
  return data.user;
}

export async function deleteAdminUser(userId: string, adminUserId?: string): Promise<void> {
  const res = await tryAdminServerFetch(
    `/auth/admin/users/${userId}/`,
    {
      method: 'DELETE',
    },
    adminUserId
  );

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || 'Failed to delete user');
  }
}

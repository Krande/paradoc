// REST wrappers for paradoc-serve admin endpoints (`/api/admin/*`).
//
// All fetches use credentials: 'same-origin' so the oauth2-proxy
// cookie (or whatever auth the deployment uses) rides along. When the
// server returns 401 / 403 / 503, that surfaces as an `AdminApiError`
// the UI can render — there's no token-handling layer in the frontend
// itself.

import { getRuntimeConfig } from '../transport'
import { authedFetch } from '../services/auth/oidc'

function apiBase(): string {
  return (getRuntimeConfig().apiBase || '').replace(/\/?$/, '')
}

function url(path: string): string {
  return apiBase() + path
}

export class AdminApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail || `HTTP ${status}`)
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = {
    method,
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  }
  if (body !== undefined) {
    init.headers = { ...(init.headers || {}), 'Content-Type': 'application/json' }
    init.body = JSON.stringify(body)
  }
  const res = await authedFetch(url(path), init)
  if (res.status === 204) {
    return undefined as unknown as T
  }
  const text = await res.text()
  let parsed: unknown = null
  try {
    parsed = text ? JSON.parse(text) : null
  } catch {
    parsed = text
  }
  if (!res.ok) {
    const detail =
      typeof parsed === 'object' && parsed && 'detail' in parsed
        ? String((parsed as { detail: unknown }).detail)
        : text || `HTTP ${res.status}`
    throw new AdminApiError(res.status, detail)
  }
  return parsed as T
}

// ── Types mirroring the server JSON shapes ───────────────────────────

export interface AdminProject {
  id: string
  slug: string
  name: string
  shelf_base_url: string | null
  created_at: string | null
  archived_at: string | null
  member_count: number
}

export interface AdminUser {
  id: string
  oidc_iss: string
  oidc_sub: string
  email: string | null
  display_name: string | null
  last_seen_at: string | null
}

export interface AdminMember {
  user_id: string
  role: string
  added_at: string | null
  email: string | null
  display_name: string | null
  oidc_iss: string
  oidc_sub: string
  last_seen_at: string | null
}

// ── API surface ──────────────────────────────────────────────────────

export const adminApi = {
  listUsers: () => request<{ users: AdminUser[] }>('GET', '/api/admin/users'),

  listProjects: () =>
    request<{ projects: AdminProject[] }>('GET', '/api/admin/projects'),

  createProject: (slug: string, name: string) =>
    request<AdminProject>('POST', '/api/admin/projects', { slug, name }),

  updateProject: (
    id: string,
    body: { name?: string; shelf_base_url?: string | null },
  ) => request<AdminProject>('PATCH', `/api/admin/projects/${id}`, body),

  archiveProject: (id: string) =>
    request<void>('DELETE', `/api/admin/projects/${id}`),

  listMembers: (projectId: string) =>
    request<{ members: AdminMember[] }>(
      'GET',
      `/api/admin/projects/${projectId}/members`,
    ),

  addMember: (projectId: string, userId: string, role: string) =>
    request<{ user_id: string; role: string; added: boolean }>(
      'POST',
      `/api/admin/projects/${projectId}/members`,
      { user_id: userId, role },
    ),

  removeMember: (projectId: string, userId: string) =>
    request<void>(
      'DELETE',
      `/api/admin/projects/${projectId}/members/${userId}`,
    ),
}

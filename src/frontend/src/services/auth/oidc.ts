// OIDC PKCE code-flow client. Provider-agnostic — works against
// Authentik (homelab) and Azure AD direct (enterprise); both expose
// `.well-known/openid-configuration` and a token endpoint that accepts
// the standard PKCE exchange.
//
// Ported from adapy-viewer's services/auth/oidc.ts and adapted to
// paradoc's runtime-config shape. Storage keys use a `paradoc-` prefix
// so the two SPAs don't clobber each other if a user has both open.
//
// Token storage trade-off:
//   - Access token  → in-memory only (XSS-hardens via shorter exposure)
//   - Refresh token → sessionStorage (survives reload-in-tab; gone on
//     tab-close)
//
// Closing the tab forces a fresh sign-in. A reload within the tab
// silently refreshes via the stored refresh token. We deliberately
// stay out of localStorage to avoid handing a long-lived credential
// to any future XSS.

import { getRuntimeConfig } from '../../transport'

interface DiscoveryDoc {
  authorization_endpoint: string
  token_endpoint: string
  end_session_endpoint?: string
}

interface TokenResponse {
  access_token: string
  expires_in?: number
  refresh_token?: string
  id_token?: string
  token_type?: string
}

const STORAGE_PKCE = 'paradoc-oidc-pkce'
const STORAGE_RETURN = 'paradoc-oidc-return'
const STORAGE_REFRESH = 'paradoc-oidc-refresh'
const STORAGE_STATE = 'paradoc-oidc-state'

let discovery: DiscoveryDoc | null = null
let accessToken: string | null = null
let accessTokenExpiry = 0
let refreshToken: string | null = sessionStorage.getItem(STORAGE_REFRESH)
let userClaims: Record<string, unknown> | null = null

// One inflight refresh — multiple 401s simultaneously must coalesce
// into a single refresh request.
let refreshInflight: Promise<boolean> | null = null

// Single-flight guard for signIn(). React.StrictMode double-invokes
// effects in development (and AuthGate's effect calls signIn on
// missing token), which previously raced two PKCE state values into
// sessionStorage and produced a guaranteed "state mismatch" on the
// callback. Once a signIn is in flight (we've written the state and
// started navigating), every subsequent call is a no-op until the
// page leaves.
let signInInflight = false

// Same problem on the callback side: StrictMode double-mounts
// AuthCallback, so its effect fires completeSignIn() twice. The first
// call reads-and-removes STORAGE_STATE; the second sees null and
// throws "state mismatch". Cache the in-flight promise so both effect
// runs share the same result.
let completeSignInInflight: Promise<string> | null = null

function redirectUri(): string {
  return `${window.location.origin}/auth/callback`
}

function base64url(bytes: Uint8Array): string {
  let s = ''
  for (const b of bytes) s += String.fromCharCode(b)
  return btoa(s).replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_')
}

function randomUrl(byteLen: number): string {
  const arr = new Uint8Array(byteLen)
  crypto.getRandomValues(arr)
  return base64url(arr)
}

async function sha256Bytes(s: string): Promise<Uint8Array> {
  const buf = new TextEncoder().encode(s)
  const hash = await crypto.subtle.digest('SHA-256', buf)
  return new Uint8Array(hash)
}

async function loadDiscovery(): Promise<DiscoveryDoc> {
  if (discovery) return discovery
  const issuer = getRuntimeConfig().authIssuer
  if (!issuer) throw new Error('authIssuer not configured')
  const r = await fetch(`${issuer.replace(/\/$/, '')}/.well-known/openid-configuration`)
  if (!r.ok) throw new Error(`oidc discovery failed: ${r.status}`)
  discovery = await r.json()
  return discovery!
}

function decodeJwtClaims(jwt: string): Record<string, unknown> | null {
  // We trust the access token because the *server* verifies it on
  // every request. Decoding here is purely for display (showing email
  // / name in the user menu); never used for authorization.
  try {
    const parts = jwt.split('.')
    if (parts.length < 2) return null
    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded = payload + '==='.slice(0, (4 - (payload.length % 4)) % 4)
    return JSON.parse(atob(padded))
  } catch {
    return null
  }
}

function acceptTokenResponse(body: TokenResponse): void {
  accessToken = body.access_token
  accessTokenExpiry = Date.now() + (body.expires_in ?? 300) * 1000
  if (body.refresh_token) {
    refreshToken = body.refresh_token
    sessionStorage.setItem(STORAGE_REFRESH, refreshToken)
  }
  // Prefer id_token for user claims; fall back to access token, which
  // Authentik also populates with email/name.
  userClaims = decodeJwtClaims(body.id_token || body.access_token)
}

function clearTokens(): void {
  accessToken = null
  accessTokenExpiry = 0
  refreshToken = null
  userClaims = null
  sessionStorage.removeItem(STORAGE_REFRESH)
}

export function isAuthEnabled(): boolean {
  return !!getRuntimeConfig().authEnabled
}

export function isSignedIn(): boolean {
  if (!accessToken) return false
  // 30s skew so we don't hand out an about-to-expire token to a
  // request that takes more than zero ms to ship.
  return Date.now() < accessTokenExpiry - 30_000
}

export function getAccessToken(): string | null {
  return isSignedIn() ? accessToken : null
}

export function getUser(): { sub?: string; email?: string; name?: string } {
  const c = userClaims || {}
  return {
    sub: typeof c.sub === 'string' ? c.sub : undefined,
    email:
      (typeof c.email === 'string' ? c.email : undefined) ||
      (typeof c.preferred_username === 'string' ? (c.preferred_username as string) : undefined),
    name:
      (typeof c.name === 'string' ? c.name : undefined) ||
      (typeof c.preferred_username === 'string' ? (c.preferred_username as string) : undefined),
  }
}

/** Kick off the authorize redirect. Caller is the AuthGate UI. */
export async function signIn(returnUrl?: string): Promise<void> {
  if (signInInflight) return
  signInInflight = true
  const d = await loadDiscovery()
  const cfg = getRuntimeConfig()
  const verifier = randomUrl(32)
  const challenge = base64url(await sha256Bytes(verifier))
  const state = randomUrl(16)
  sessionStorage.setItem(STORAGE_PKCE, verifier)
  sessionStorage.setItem(STORAGE_STATE, state)
  sessionStorage.setItem(
    STORAGE_RETURN,
    returnUrl || window.location.pathname + window.location.search,
  )
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: cfg.authClientId || '',
    redirect_uri: redirectUri(),
    // offline_access asks the IdP for a refresh_token; without it,
    // reload-in-tab forces a full re-authorize round-trip.
    scope: 'openid profile email offline_access',
    code_challenge: challenge,
    code_challenge_method: 'S256',
    state,
  })
  const aud = cfg.authAudience
  if (aud && aud !== cfg.authClientId) {
    // Auth0 / some Azure AD configurations need this so the issued
    // access token carries the right `aud` claim. Authentik ignores
    // unknown params; safe to always send when set.
    params.set('audience', aud)
  }
  window.location.assign(`${d.authorization_endpoint}?${params}`)
}

/** Handle the redirect-back URL. Returns the original return path. */
export async function completeSignIn(): Promise<string> {
  if (completeSignInInflight) return completeSignInInflight
  completeSignInInflight = (async () => {
    const url = new URL(window.location.href)
    const code = url.searchParams.get('code')
    const state = url.searchParams.get('state')
    const expectedState = sessionStorage.getItem(STORAGE_STATE)
    sessionStorage.removeItem(STORAGE_STATE)
    if (!code) throw new Error('no auth code in callback URL')
    if (!expectedState || state !== expectedState) {
      throw new Error('state mismatch — possible CSRF, refusing to sign in')
    }
    const verifier = sessionStorage.getItem(STORAGE_PKCE)
    sessionStorage.removeItem(STORAGE_PKCE)
    if (!verifier) throw new Error('no PKCE verifier (sessionStorage cleared?)')
    const d = await loadDiscovery()
    const cfg = getRuntimeConfig()
    const params = new URLSearchParams({
      grant_type: 'authorization_code',
      code,
      redirect_uri: redirectUri(),
      client_id: cfg.authClientId || '',
      code_verifier: verifier,
    })
    const r = await fetch(d.token_endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params.toString(),
    })
    if (!r.ok) {
      throw new Error(`token exchange failed: ${r.status} ${await r.text()}`)
    }
    acceptTokenResponse(await r.json())
    const ret = sessionStorage.getItem(STORAGE_RETURN) || '/'
    sessionStorage.removeItem(STORAGE_RETURN)
    return ret
  })()
  return completeSignInInflight
}

/** Refresh the access token using the stored refresh token. Returns
 *  whether a usable token is now available. */
export async function refreshAccessToken(): Promise<boolean> {
  if (!refreshToken) return false
  if (refreshInflight) return refreshInflight
  refreshInflight = (async () => {
    try {
      const d = await loadDiscovery()
      const r = await fetch(d.token_endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          grant_type: 'refresh_token',
          refresh_token: refreshToken!,
          client_id: getRuntimeConfig().authClientId || '',
        }).toString(),
      })
      if (!r.ok) {
        clearTokens()
        return false
      }
      acceptTokenResponse(await r.json())
      return true
    } catch {
      clearTokens()
      return false
    } finally {
      refreshInflight = null
    }
  })()
  return refreshInflight
}

/** Top-level sign-out: clears local state and redirects via the IdP's
 *  end-session endpoint when available, else just to /. */
export async function signOut(): Promise<void> {
  clearTokens()
  try {
    const d = await loadDiscovery()
    if (d.end_session_endpoint) {
      window.location.assign(d.end_session_endpoint)
      return
    }
  } catch {
    /* discovery may fail offline — just go home */
  }
  window.location.assign('/')
}

/** Best-effort warm-up on app boot: if a refresh token is stashed in
 *  sessionStorage, swap it for an access token before first render so
 *  the user doesn't see a flicker through the auth gate. */
export async function bootstrap(): Promise<void> {
  if (!isAuthEnabled()) return
  if (refreshToken && !isSignedIn()) {
    await refreshAccessToken()
  }
}

/** Fetch wrapper that attaches the bearer token and refresh-then-retry
 *  on 401. Used by all paradoc API call sites that don't roll their
 *  own request flow. When auth is disabled, behaves like plain fetch. */
export async function authedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  if (!isAuthEnabled()) {
    return fetch(input, init)
  }
  const withAuth = (token: string | null): RequestInit => {
    const headers = new Headers((init && init.headers) || undefined)
    if (token) headers.set('Authorization', `Bearer ${token}`)
    return { ...(init || {}), headers }
  }
  let token = getAccessToken()
  let resp = await fetch(input, withAuth(token))
  if (resp.status !== 401) return resp
  // One refresh-then-retry; if that still 401s, force a fresh sign-in.
  const refreshed = await refreshAccessToken()
  if (!refreshed) {
    void signIn()
    return resp
  }
  token = getAccessToken()
  resp = await fetch(input, withAuth(token))
  if (resp.status === 401) {
    void signIn()
  }
  return resp
}

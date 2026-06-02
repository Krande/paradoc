import React from 'react'
import { bootstrap, isAuthEnabled, isSignedIn, signIn } from '../../services/auth/oidc'

// Gates the app render behind a verified bearer token. When auth is
// disabled (PARADOC_AUTH_ENABLED unset/false), this is a transparent
// pass-through — useful for offline-bundled SPAs and dev runs.
//
// On boot it attempts a silent token refresh from a stashed refresh
// token (sessionStorage); if that succeeds the user lands on the app
// without seeing the sign-in prompt. If no token is available, the
// gate immediately redirects through the IdP via signIn() — matching
// adapy-viewer's behavior so paradoc.krande.no doesn't ever show a
// "Could not load document list" 401 to a fresh visitor.

export const AuthGate: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const enabled = isAuthEnabled()
  const [ready, setReady] = React.useState(!enabled)
  const [signedIn, setSignedIn] = React.useState(!enabled || isSignedIn())

  React.useEffect(() => {
    if (!enabled) {
      setReady(true)
      setSignedIn(true)
      return
    }
    let cancelled = false
    bootstrap()
      .catch(() => { /* refresh failed → fall through to signIn */ })
      .finally(() => {
        if (cancelled) return
        if (isSignedIn()) {
          setSignedIn(true)
          setReady(true)
        } else {
          // No token, no refresh — kick straight to the IdP. The
          // redirect happens via window.location.assign so the
          // component unmounts mid-render; nothing else to do.
          void signIn()
        }
      })
    return () => { cancelled = true }
  }, [enabled])

  if (!enabled || signedIn) return <>{children}</>
  if (!ready) {
    return (
      <div className="flex h-screen w-screen items-center justify-center text-gray-500 text-sm">
        Signing in…
      </div>
    )
  }
  // Unreachable: when ready && !signedIn we've already called signIn()
  // which redirects. Render a fallback in case the redirect is slow.
  return (
    <div className="flex h-screen w-screen items-center justify-center text-gray-500 text-sm">
      Redirecting to sign-in…
    </div>
  )
}

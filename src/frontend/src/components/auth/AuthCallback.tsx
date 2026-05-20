import React from 'react'
import { useNavigate } from 'react-router-dom'
import { completeSignIn } from '../../services/auth/oidc'

// Minimal landing component for the OIDC redirect_uri. Exchanges the
// auth code for an access token, then navigates back to the user's
// original entry path (stashed in sessionStorage before signIn).
//
// Authentik must have this URL in the provider's redirect_uris list:
//   https://paradoc.krande.no/auth/callback
//   http://localhost:8000/auth/callback   (for local dev)

export const AuthCallback: React.FC = () => {
  const navigate = useNavigate()
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let cancelled = false
    completeSignIn()
      .then((returnTo) => {
        if (cancelled) return
        navigate(returnTo, { replace: true })
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : String(err))
      })
    return () => { cancelled = true }
  }, [navigate])

  return (
    <div className="flex h-screen w-screen items-center justify-center text-gray-500 text-sm">
      {error ? (
        <div className="max-w-md space-y-3 p-6 bg-red-50 border border-red-200 rounded">
          <div className="text-red-800 font-medium">Sign-in failed</div>
          <div className="text-xs font-mono break-all">{error}</div>
          <button
            className="text-sm text-blue-700 hover:text-blue-900 hover:underline"
            onClick={() => navigate('/', { replace: true })}
          >
            ← Back to home
          </button>
        </div>
      ) : (
        <div>Completing sign-in…</div>
      )}
    </div>
  )
}

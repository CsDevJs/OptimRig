import { ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'

import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'

/** Hidden page (no menu link): the email of every account, for administrators only. */
export function AdminPage() {
  const { user, loading } = useAuth()
  const [emails, setEmails] = useState<string[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!user) return
    api.adminEmails()
      .then((r) => setEmails(r.emails))
      .catch((e: Error) => setError(e.message))
  }, [user])

  if (!loading && !user) return <Navigate to="/autentificare" replace />
  if (!user) return null

  return (
    <section className="space-y-6">
      <div className="slate-glow-card glow rounded-2xl p-5">
        <h1 className="text-lg font-extrabold text-white flex items-center gap-2">
          <ShieldCheck size={18} className="text-violet-300" /> Conturi create
        </h1>
        {emails && <p className="text-xs text-slate-300">{emails.length} {emails.length === 1 ? 'cont' : 'conturi'}</p>}
      </div>
      {error && <p className="text-sm text-red-300">{error}</p>}
      {!error && !emails && <p className="text-sm text-slate-400">Se încarcă…</p>}
      {emails && (
        <ul className="modern-sleek-card rounded-2xl divide-y divide-slate-800">
          {emails.map((email) => (
            <li key={email} className="px-5 py-3 text-sm font-mono text-slate-200 break-all">{email}</li>
          ))}
        </ul>
      )}
    </section>
  )
}

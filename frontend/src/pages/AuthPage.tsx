import { Check, Circle, Lock } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { useToast } from '../context/ToastContext'

const CRITERIA = [
  { test: (p: string) => p.length >= 8, label: 'Minim 8 caractere (obligatoriu)' },
  { test: (p: string) => /[A-Z]/.test(p), label: 'Cel puțin o literă mare (A–Z)' },
  { test: (p: string) => /[0-9]/.test(p), label: 'Cel puțin o cifră (0–9)' },
]

export function AuthPage() {
  const { user, login, register } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [registerMode, setRegisterMode] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/cont" replace />

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await (registerMode ? register(email, password) : login(email, password))
      toast({ title: 'Succes', message: registerMode ? 'Contul a fost creat.' : 'Autentificare reușită!', tone: 'ok' })
      navigate('/cont')
    } catch (err) {
      const message = (err as Error).message
      setError(message === 'Wrong login or password' ? 'Email sau parolă greșită.'
        : message === 'Email already registered' ? 'Există deja un cont cu acest email.' : message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="max-w-md mx-auto py-8">
      <div className="modern-sleek-card rounded-3xl p-6 sm:p-8 space-y-6">
        <div className="text-center space-y-2">
          <div className="w-12 h-12 mx-auto rounded-2xl bg-gradient-to-tr from-violet-500/30 to-sky-400/30 border border-violet-400/50 flex items-center justify-center">
            <Lock size={18} className="text-violet-200" />
          </div>
          <h2 className="text-xl font-extrabold text-white tracking-tight">{registerMode ? 'Creare cont nou' : 'Autentificare în cont'}</h2>
          <p className="text-xs text-slate-400">
            {registerMode ? 'Cu un cont îți salvezi build-urile și urmărești cum se schimbă prețurile.' : 'Introdu datele pentru a accesa dashboard-ul personal.'}
          </p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <label className="block space-y-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block">Adresă email</span>
            <input type="email" required autoComplete="email" value={email}
              onChange={(e) => setEmail(e.target.value)} placeholder="nume@exemplu.com"
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-violet-400" />
          </label>
          <label className="block space-y-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block">Parolă</span>
            <input type="password" required minLength={8} maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)}
              autoComplete={registerMode ? 'new-password' : 'current-password'} placeholder="••••••••"
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-violet-400" />
          </label>
          {registerMode && (
            <div className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800 space-y-1 text-[10px]">
              <p className="font-bold text-slate-300">Criterii parolă securizată:</p>
              {CRITERIA.map((c) => {
                const ok = c.test(password)
                return (
                  <div key={c.label} className={`flex items-center gap-1.5 ${ok ? 'text-emerald-300 font-medium' : 'text-slate-500'}`}>
                    {ok ? <Check size={10} /> : <Circle size={6} className="fill-current" />} {c.label}
                  </div>
                )
              })}
            </div>
          )}
          {error && <div className="p-2.5 rounded-xl bg-red-950/50 border border-red-500/50 text-red-200 text-xs">{error}</div>}
          <button type="submit" disabled={busy}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-sky-400 via-violet-400 to-violet-300 text-slate-950 font-bold text-xs shadow-lg transition hover:scale-[1.02] disabled:opacity-60">
            {registerMode ? 'Creează contul' : 'Conectare în cont'}
          </button>
        </form>

        <div className="text-center pt-2 border-t border-slate-800/80">
          <p className="text-xs text-slate-400">
            {registerMode ? 'Ai deja cont? ' : 'Nu ai cont? '}
            <button type="button" onClick={() => { setRegisterMode((v) => !v); setError(null) }} className="text-violet-300 font-bold hover:underline">
              {registerMode ? 'Autentifică-te' : 'Înregistrează-te'}
            </button>
          </p>
        </div>
      </div>
    </section>
  )
}

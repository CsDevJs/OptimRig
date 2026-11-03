import { Archive, Cpu, FolderOpen, Globe, Layers, Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { api } from '../api/client'
import type { Build, BuildSummary, Selection } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { useBuilder } from '../builder/BuilderContext'
import { useCurrency } from '../context/CurrencyContext'
import { useToast } from '../context/ToastContext'
import { componentName } from '../lib/catalog'

export function AccountPage() {
  const { user, loading } = useAuth()
  const { replace } = useBuilder()
  const { code, format } = useCurrency()
  const toast = useToast()
  const navigate = useNavigate()
  const [builds, setBuilds] = useState<BuildSummary[] | null>(null)
  const [latest, setLatest] = useState<Build | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!user) return
    api.builds.list()
      .then((list) => {
        setBuilds(list)
        if (list[0]) api.builds.get(list[0].id).then(setLatest).catch(() => undefined)
      })
      .catch((e: Error) => setError(e.message))
  }, [user])

  if (!loading && !user) return <Navigate to="/autentificare" replace />
  if (!user) return null

  const open = async (summary: BuildSummary) => {
    try {
      const build = await api.builds.get(summary.id)
      replace(Object.fromEntries(build.items.map((i) => [i.category, i.component.id])) as Selection, { id: build.id, name: build.name })
      toast({ title: 'Încărcat', message: `„${build.name}” e deschis în Manual.`, tone: 'ok' })
      navigate('/manual')
    } catch (e) {
      toast({ title: 'Eroare', message: (e as Error).message, tone: 'error' })
    }
  }

  const remove = async (summary: BuildSummary) => {
    if (!window.confirm(`Ștergi „${summary.name}”? Acțiunea nu poate fi anulată.`)) return
    try {
      await api.builds.remove(summary.id)
      setBuilds((list) => list?.filter((b) => b.id !== summary.id) ?? null)
      toast({ title: 'Șters', message: `„${summary.name}” a fost șters.`, tone: 'ok' })
    } catch (e) {
      toast({ title: 'Eroare', message: (e as Error).message, tone: 'error' })
    }
  }

  const gpu = latest?.items.find((i) => i.category === 'gpu')?.component
  const stats = [
    { label: 'Build-uri salvate', value: builds?.length ?? '…', icon: Layers, cls: 'bg-violet-500/20 border-violet-400/30 text-violet-300' },
    { label: 'Monedă preferată', value: code, icon: Globe, cls: 'bg-sky-500/20 border-sky-400/30 text-sky-300' },
    { label: 'Placa video din ultimul build', value: gpu ? componentName(gpu) : 'Niciun build salvat', icon: Cpu, cls: 'bg-pink-500/20 border-pink-400/30 text-pink-300', small: true },
  ]

  return (
    <section className="space-y-6">
      <div className="modern-sleek-card glow rounded-2xl p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-violet-500/30 to-sky-500/30 border border-violet-400/50 flex items-center justify-center text-2xl font-extrabold text-white">
            {user.email.charAt(0).toUpperCase()}
          </div>
          <div>
            <span className="px-2 py-0.5 rounded-full bg-violet-400/15 border border-violet-400/30 text-violet-200 text-[10px] font-semibold">Cont activ</span>
            <h2 className="text-xl font-extrabold text-white mt-1">{user.email.split('@')[0]}</h2>
            <p className="text-xs text-slate-400">{user.email}</p>
          </div>
        </div>
        <Link to="/manual" onClick={() => replace({})}
          className="px-4 py-2 rounded-xl bg-violet-400/20 hover:bg-violet-400/30 border border-violet-400/40 text-violet-200 text-xs font-bold transition flex items-center gap-2 w-fit">
          <Plus size={14} /> Creează build nou
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {stats.map(({ label, value, icon: Icon, cls, small }) => (
          <div key={label} className="slate-glow-card glow rounded-2xl p-4 flex items-center gap-4 min-w-0">
            <div className={`w-12 h-12 rounded-xl border flex items-center justify-center shrink-0 ${cls}`}><Icon size={18} /></div>
            <div className="min-w-0">
              <span className="text-[11px] text-slate-400 block">{label}</span>
              <span className={`font-extrabold text-white block truncate ${small ? 'text-xs text-pink-300' : 'text-xl font-mono'}`}>{value}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="slate-glow-card rounded-2xl p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h3 className="text-sm font-extrabold text-white flex items-center gap-2"><Archive size={15} className="text-violet-300" /> Build-urile mele salvate</h3>
          <span className="text-xs text-slate-400">Prețul de la momentul salvării</span>
        </div>
        {error && <p className="text-xs text-red-300">{error}</p>}
        {builds?.length === 0 && (
          <p className="text-xs text-slate-500 italic py-4 text-center">Nu ai salvat încă niciun build. Folosește configuratorul manual pentru a salva primul tău PC!</p>
        )}
        <div className="space-y-2">
          {builds?.map((b) => (
            <div key={b.id} className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <h4 className="text-xs font-bold text-white truncate">{b.name}</h4>
                <p className="text-[10px] text-slate-400">{b.component_count}/8 piese · actualizat {new Date(b.updated_at).toLocaleDateString('ro-MD')}</p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="font-mono text-xs font-bold text-violet-300">{format(b.saved_total_mdl)}</span>
                <button type="button" onClick={() => open(b)}
                  className="px-2.5 py-1 rounded-lg bg-violet-400/20 text-violet-200 text-[10px] font-bold hover:bg-violet-400/30 transition flex items-center gap-1">
                  <FolderOpen size={11} /> Încarcă
                </button>
                <button type="button" onClick={() => remove(b)} aria-label={`Șterge ${b.name}`}
                  className="p-1.5 rounded-lg bg-slate-950 text-slate-400 hover:text-pink-300 border border-slate-800 transition">
                  <Trash2 size={11} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

import { Eraser } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api/client'
import { slotCategory, type Selection, type Slot } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { useBuilder } from '../builder/BuilderContext'
import { CategoryRow } from '../components/CategoryRow'
import { ManualSummary } from '../components/ManualSummary'
import { useToast } from '../context/ToastContext'
import { ORDER } from '../lib/catalog'

const AUTO_KEY = 'pc-configurator-auto-compat'

export function ManualPage() {
  const builder = useBuilder()
  const { catalog, catalogError, byId, specs, selection, compatibility, plan, build } = builder
  const { user } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [open, setOpen] = useState<Slot | null>(null)
  const [auto, setAuto] = useState(() => {
    try {
      return localStorage.getItem(AUTO_KEY) !== 'off'
    } catch {
      return true
    }
  })

  // AC-3 on the server for the open row: which parts still fit everything else that's picked.
  const others = useMemo<Selection>(() => {
    if (!open) return {}
    const { [open]: _current, ...rest } = selection
    return rest
  }, [open, selection])
  const othersKey = `${open}:${JSON.stringify(others)}`
  const needsFilter = auto && open !== null && Object.keys(others).length > 0
  const [filtered, setFiltered] = useState<{ key: string; ids: Set<number> | null } | null>(null)
  useEffect(() => {
    if (!needsFilter || !open) return
    let active = true
    api.filter(others)
      .then((r) => active && setFiltered({ key: othersKey, ids: new Set((r.domains[open] ?? []).filter((id): id is number => id !== null)) }))
      .catch(() => active && setFiltered({ key: othersKey, ids: null }))
    return () => {
      active = false
    }
  }, [needsFilter, open, others, othersKey])
  const allowed = needsFilter && filtered?.key === othersKey ? filtered.ids : null
  const loadingAllowed = needsFilter && filtered?.key !== othersKey

  const severity = useMemo(() => {
    const worst = new Map<number, 'error' | 'warning'>()
    for (const issue of compatibility?.issues ?? []) {
      for (const id of issue.component_ids) if (issue.severity === 'error' || !worst.has(id)) worst.set(id, issue.severity)
    }
    return worst
  }, [compatibility])

  const psuWatts = selection.psu ? Number(specs.get(selection.psu)?.wattage ?? 0) || null : null
  const closeRow = useCallback(() => setOpen(null), [])

  const toggleAuto = () => {
    setAuto((v) => {
      try {
        localStorage.setItem(AUTO_KEY, v ? 'off' : 'on')
      } catch {
        // ignore
      }
      return !v
    })
  }

  const save = async (name: string, asNew: boolean) => {
    if (!user) {
      toast({ title: 'Autentificare necesară', message: 'Intră în cont pentru a salva build-ul.', tone: 'error' })
      navigate('/autentificare')
      return
    }
    try {
      const saved = build && !asNew
        ? await api.builds.update(build.id, name, selection)
        : await api.builds.create(name, selection)
      builder.setBuild({ id: saved.id, name: saved.name })
      toast({ title: 'Salvat cu succes', message: `„${saved.name}” a fost salvat în cont.`, tone: 'ok' })
      navigate('/cont')
    } catch (error) {
      toast({ title: 'Salvare eșuată', message: (error as Error).message, tone: 'error' })
    }
  }

  if (catalogError) {
    return <div className="p-4 rounded-xl bg-red-950/50 border border-red-500/50 text-red-200 text-sm">Catalogul nu s-a putut încărca: {catalogError}</div>
  }

  return (
    <section className="space-y-4">
      <div className="slate-glow-card glow rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-extrabold text-white">{build ? build.name : 'Configurator manual'}</h2>
          <p className="text-xs text-slate-300">
            {build ? 'Editezi un build salvat. Modificările se salvează când apeși „Salvează modificările”.'
              : 'Alege componentele cu verificare automată de compatibilitate (AC-3).'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-slate-200 cursor-pointer hover:border-slate-500 transition">
            <input type="checkbox" checked={auto} onChange={toggleAuto} className="accent-violet-400" />
            Compatibilitate auto
          </label>
          {Object.keys(selection).length > 0 && (
            <button type="button" onClick={() => builder.replace({})}
              className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-slate-300 hover:text-white hover:border-slate-500 transition flex items-center gap-1.5">
              <Eraser size={13} /> {build ? 'Build nou' : 'Golește'}
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
        <div className="lg:col-span-8 space-y-3">
          {ORDER.map((category) => {
            const id = selection[category]
            if (!catalog && id) {
              return <div key={category} className="slate-glow-card rounded-xl p-4"><span className="skeleton w-2/3" /></div>
            }
            return (
              <CategoryRow
                key={category}
                category={category}
                options={(catalog ?? []).filter((c) => c.category === slotCategory(category))}
                allowed={allowed}
                loadingAllowed={open === category && loadingAllowed}
                selected={id ? byId.get(id) ?? null : null}
                specs={specs}
                severity={id ? severity.get(id) ?? null : null}
                open={open === category}
                onToggle={() => setOpen((o) => (o === category ? null : category))}
                onClose={closeRow}
                onPick={(pick) => { builder.choose(category, pick); setOpen(null) }}
                onClear={() => { builder.remove(category); setOpen(null) }}
              />
            )
          })}
        </div>
        <div className="lg:col-span-4 lg:sticky lg:top-24">
          <ManualSummary
            key={build?.id ?? 'new'}
            selection={selection}
            byId={byId}
            compatibility={compatibility}
            plan={plan}
            psuWatts={psuWatts}
            checking={builder.checking}
            buildName={build?.name ?? null}
            loggedIn={!!user}
            onSave={save}
          />
        </div>
      </div>
    </section>
  )
}

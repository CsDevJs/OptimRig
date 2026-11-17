import { Eraser, Plus } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api/client'
import { slotCategory, type Selection, type Slot } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { useBuilder } from '../builder/BuilderContext'
import { CategoryRow } from '../components/CategoryRow'
import { ManualSummary } from '../components/ManualSummary'
import { useToast } from '../context/ToastContext'
import { MULTI_SLOTS, ORDER } from '../lib/catalog'

const AUTO_KEY = 'pc-configurator-auto-compat'

type Group = keyof typeof MULTI_SLOTS
const GROUPS = Object.keys(MULTI_SLOTS) as Group[]
const groupOf = (slot: Slot): Group | null => GROUPS.find((g) => (MULTI_SLOTS[g] as readonly Slot[]).includes(slot)) ?? null
const ADD_LABEL: Record<Group, string> = { ram: 'Adaugă memorie RAM', storage: 'Adaugă stocare' }

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

  // Extra RAM kits and drives: rows the user added (possibly still empty), and at least
  // every one that holds a part, e.g. from a loaded build.
  const [added, setAdded] = useState<Record<Group, number>>({ ram: 0, storage: 0 })
  const extras = (g: Group) => {
    const filled = MULTI_SLOTS[g].reduce((last, slot, i) => (selection[slot] ? i : last), 0)
    return Math.max(added[g], filled)
  }
  const visible = ORDER.filter((slot) => {
    const g = groupOf(slot)
    return !g || (MULTI_SLOTS[g] as readonly Slot[]).indexOf(slot) <= extras(g)
  })
  const addRow = (g: Group) => {
    const next = extras(g) + 1
    setAdded((a) => ({ ...a, [g]: next }))
    setOpen(MULTI_SLOTS[g][next])
  }
  // Taking a row out moves the kits or drives below it up one row, so the rows stay numbered 2, 3, 4.
  const removeRow = (slot: Slot) => {
    const g = groupOf(slot)!
    const slots = MULTI_SLOTS[g]
    const next: Selection = { ...selection }
    for (let i = slots.indexOf(slot as never); i < slots.length; i++) {
      const below = selection[slots[i + 1]]
      if (below) next[slots[i]] = below
      else delete next[slots[i]]
    }
    builder.replace(next, build)
    setAdded((a) => ({ ...a, [g]: extras(g) - 1 }))
    setOpen(null)
  }

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
            <button type="button" onClick={() => { builder.replace({}); setAdded({ ram: 0, storage: 0 }) }}
              className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-slate-300 hover:text-white hover:border-slate-500 transition flex items-center gap-1.5">
              <Eraser size={13} /> {build ? 'Build nou' : 'Golește'}
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
        <div className="lg:col-span-8 space-y-3">
          {visible.map((category, index) => {
            const id = selection[category]
            const g = groupOf(category)
            const last = g !== null && category === MULTI_SLOTS[g][extras(g)]
            // Only once the first kit or drive is chosen, and while there is room for another.
            const addButton = last && !!selection[MULTI_SLOTS[g][0]] && extras(g) < MULTI_SLOTS[g].length - 1 && (
              <button type="button" onClick={() => addRow(g)}
                className="px-3 py-1.5 rounded-lg bg-violet-500/80 hover:bg-violet-400 text-white text-xs font-bold transition flex items-center gap-1.5 shadow-md">
                <Plus size={13} /> {ADD_LABEL[g]}
              </button>
            )
            if (!catalog && id) {
              return (
                <div key={category} className="space-y-2">
                  <div className="slate-glow-card rounded-xl p-4"><span className="skeleton w-2/3" /></div>
                  {addButton}
                </div>
              )
            }
            return (
              <div key={category} className="space-y-2">
                <CategoryRow
                  category={category}
                  number={index + 1}
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
                  onRemove={g && category !== MULTI_SLOTS[g][0] ? () => removeRow(category) : undefined}
                />
                {addButton}
              </div>
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

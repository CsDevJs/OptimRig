import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api } from '../api/client'
import type { Category, CompatibilityResult, Component, PurchasePlan, Selection, SpecValue } from '../api/types'

type Specs = Record<string, SpecValue> | null
const SELECTION_KEY = 'pc-configurator-selection'
const BUILD_KEY = 'pc-configurator-loaded-build'

function read<T>(key: string, fallback: T): T {
  try {
    const value = localStorage.getItem(key)
    return value ? (JSON.parse(value) as T) : fallback
  } catch {
    return fallback
  }
}

function write(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Storage blocked: nothing is remembered across reloads.
  }
}

export interface LoadedBuild {
  id: number
  name: string
}

/** Catalog, the user's current picks, and the server's verdicts on them, shared by all pages. */
function useBuilderState() {
  const [catalog, setCatalog] = useState<Component[] | null>(null)
  const [catalogError, setCatalogError] = useState<string | null>(null)
  const [specs, setSpecs] = useState<Map<number, Specs>>(new Map())
  const [storedSelection, setSelection] = useState<Selection>(() => read(SELECTION_KEY, {}))
  const [build, setBuildState] = useState<LoadedBuild | null>(() => read(BUILD_KEY, null))

  useEffect(() => {
    api.components()
      .then((page) => {
        setCatalog(page.items)
        // Specs are only on the detail endpoint; 48 small requests to our own API, once.
        Promise.all(page.items.map((c) => api.component(c.id).then((d) => [c.id, d.specs] as const).catch(() => [c.id, null] as const)))
          .then((entries) => setSpecs(new Map(entries)))
      })
      .catch((error: Error) => setCatalogError(error.message))
  }, [])

  const byId = useMemo(() => new Map((catalog ?? []).map((c) => [c.id, c])), [catalog])

  // Ignore selections whose component no longer exists (e.g. after a reseed).
  const selection = useMemo<Selection>(() => {
    if (!catalog) return storedSelection
    const kept = Object.entries(storedSelection).filter(([, id]) => byId.has(id as number))
    return kept.length === Object.keys(storedSelection).length ? storedSelection : Object.fromEntries(kept)
  }, [catalog, byId, storedSelection])
  const isEmpty = Object.keys(selection).length === 0

  useEffect(() => {
    write(SELECTION_KEY, selection)
  }, [selection])

  // Answers are tagged with the selection they belong to, so a slow reply never shows for newer picks.
  const [checked, setChecked] = useState<{ key: string; compatibility: CompatibilityResult | null; plan: PurchasePlan | null } | null>(null)
  const key = JSON.stringify(selection)
  useEffect(() => {
    if (isEmpty) return
    let current = true
    Promise.all([api.check(selection), api.plan(selection)])
      .then(([compatibility, plan]) => current && setChecked({ key, compatibility, plan }))
      .catch(() => current && setChecked({ key, compatibility: null, plan: null }))
    return () => {
      current = false
    }
  }, [key, isEmpty, selection])

  const setBuild = useCallback((next: LoadedBuild | null) => {
    setBuildState(next)
    write(BUILD_KEY, next)
  }, [])

  const choose = useCallback((category: Category, id: number) => setSelection((s) => ({ ...s, [category]: id })), [])
  const remove = useCallback((category: Category) => setSelection(({ [category]: _removed, ...rest }) => rest), [])
  const replace = useCallback((next: Selection, loaded: LoadedBuild | null = null) => {
    setSelection(next)
    setBuild(loaded)
  }, [setBuild])

  return {
    catalog, catalogError, byId, specs,
    selection, choose, remove, replace,
    build, setBuild,
    compatibility: isEmpty ? null : (checked?.compatibility ?? null),
    plan: isEmpty ? null : (checked?.plan ?? null),
    checking: !isEmpty && checked?.key !== key,
  }
}

export type Builder = ReturnType<typeof useBuilderState>
const BuilderContext = createContext<Builder | null>(null)

export function BuilderProvider({ children }: { children: ReactNode }) {
  const state = useBuilderState()
  return <BuilderContext.Provider value={state}>{children}</BuilderContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useBuilder(): Builder {
  const context = useContext(BuilderContext)
  if (!context) throw new Error('useBuilder must be used inside <BuilderProvider>')
  return context
}

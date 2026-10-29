import { useEffect, useMemo, useState } from 'react'

import { api } from '../api/client'
import type { CompatibilityResult, Component, Selection } from '../api/types'
import { cheapestOffer } from '../lib/catalog'
import { TEMPLATES, templateSelection, type Template } from '../lib/templates'
import { useBuilder } from './BuilderContext'

export interface TemplateStats {
  template: Template
  selection: Selection
  /** Sum of each part's cheapest in-stock price (what the purchase plan would pay), in MDL. */
  total: number
  missingStock: number
  cpu: Component
  gpu: Component
  compatibility: CompatibilityResult | null
}

/** Templates resolved against the live catalog, with live prices and a server compatibility check. */
export function useTemplates(): TemplateStats[] | null {
  const { catalog, byId } = useBuilder()
  const [checks, setChecks] = useState<Record<string, CompatibilityResult>>({})

  const resolved = useMemo(() => {
    if (!catalog) return null
    return TEMPLATES.flatMap((template) => {
      const selection = templateSelection(template, catalog)
      if (!selection) return []
      const parts = Object.values(selection).map((id) => byId.get(id as number)!)
      const offers = parts.map(cheapestOffer)
      return [{
        template, selection,
        total: offers.reduce((sum, o) => sum + (o ? Number(o.price_mdl) : 0), 0),
        missingStock: offers.filter((o) => !o).length,
        cpu: byId.get(selection.cpu!)!,
        gpu: byId.get(selection.gpu!)!,
      }]
    })
  }, [catalog, byId])

  useEffect(() => {
    if (!resolved) return
    let active = true
    Promise.all(resolved.map((r) => api.check(r.selection).then((c) => [r.template.id, c] as const).catch(() => null)))
      .then((results) => active && setChecks(Object.fromEntries(results.filter((r) => r !== null))))
    return () => {
      active = false
    }
  }, [resolved])

  return resolved?.map((r) => ({ ...r, compatibility: checks[r.template.id] ?? null })) ?? null
}

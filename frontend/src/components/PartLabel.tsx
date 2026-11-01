import type { Category, Component, SpecValue } from '../api/types'
import { componentName, specSummary, TIER_LABEL } from '../lib/catalog'

/** How a component is named everywhere in the builder: bold name, tier badge, one line of key specs. */
export function PartLabel({ category, component, specs }: {
  category: Category
  component: Component
  specs: Record<string, SpecValue> | null | undefined
}) {
  return (
    <span className="flex flex-col min-w-0">
      <span className="part-name text-[13px]" title={componentName(component)}>
        {componentName(component)}
        <span className={`tier-badge tier-${component.tier}`}>{TIER_LABEL[component.tier]}</span>
      </span>
      <span className="part-specs">{specs === undefined ? 'Se încarcă specificațiile…' : specSummary(category, specs)}</span>
    </span>
  )
}

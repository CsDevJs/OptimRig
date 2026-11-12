// Shapes returned by the FastAPI backend (see backend/app/*schemas.py).
// Decimal fields (prices, scores) arrive as strings to keep their precision.

export const CATEGORIES = ['cpu', 'motherboard', 'ram', 'gpu', 'storage', 'psu', 'case', 'cooler'] as const
export type Category = (typeof CATEGORIES)[number]
export type Tier = 'low' | 'mid' | 'high'
export type Availability = 'in_stock' | 'on_order' | 'out_of_stock'

/** A place in a build: one per category, plus an optional second drive. */
export type Slot = Category | 'storage2'
/** The component category a slot takes its parts from. */
export const slotCategory = (slot: Slot): Category => (slot === 'storage2' ? 'storage' : slot)

/** One chosen component ID per slot. */
export type Selection = Partial<Record<Slot, number>>

export interface Store {
  id: number
  slug: string
  name: string
  website: string
}

export interface Offer {
  id: number
  store: Store
  price_mdl: string
  regular_price_mdl: string | null
  on_sale: boolean
  availability: Availability
  stock_qty: number | null
  url: string
  checked_on: string
  last_check_status: 'ok' | 'failed' | 'page_gone' | null
}

export interface Component {
  id: number
  slug: string
  category: Category
  tier: Tier
  brand: string
  model: string
  perf_score: string | null
  perf_source: string | null
  power_draw_w: number
  release_year: number | null
  offers: Offer[]
}

export type SpecValue = string | number | boolean | string[] | null
export interface ComponentDetail extends Component {
  specs: Record<string, SpecValue> | null
}

export interface ComponentPage {
  items: ComponentDetail[]
  total: number
  limit: number
  offset: number
}

export interface CompatibilityIssue {
  code: string
  severity: 'error' | 'warning'
  component_ids: number[]
  message: string
}

export interface CompatibilityResult {
  status: 'compatible' | 'incompatible' | 'incomplete' | 'undetermined'
  missing_categories: Category[]
  issues: CompatibilityIssue[]
  checked_rules: string[]
  estimated_power_w: number
  recommended_psu_w: number
  limitations: string[]
}

export interface FilterResult {
  status: 'arc_consistent' | 'inconsistent'
  domains: Partial<Record<Slot, (number | null)[]>>
  removed: Partial<Record<Slot, number[]>>
  empty_categories: Slot[]
}

export interface PurchasePlan {
  status: 'complete' | 'partial'
  items: {
    category: Slot
    component_id: number
    component_name: string
    store: Store
    price_mdl: string
    url: string
  }[]
  unplanned: { category: Slot; component_id: number; reason: 'no_offer_in_stock' }[]
  stores: { store: Store; part_count: number; subtotal_mdl: string }[]
  total_mdl: string
}

export interface User {
  id: number
  email: string
  created_at: string
}

export interface Token {
  access_token: string
  token_type: 'bearer'
  expires_in: number
}

export interface BuildSummary {
  id: number
  name: string
  created_at: string
  updated_at: string
  component_count: number
  saved_total_mdl: string
}

export interface Build extends BuildSummary {
  items: {
    category: Slot
    component: Component
    saved_price_mdl: string | null
    saved_store: Store | null
    current_price_mdl: string | null
    current_store: Store | null
  }[]
  current_total_mdl: string
  unpriced_categories: Slot[]
  compatibility: CompatibilityResult
}

export type Purpose = 'gaming' | 'office' | 'workstation' | 'editing'

/** One TOPSIS-ranked build from POST /recommendations. */
export interface RankedBuild {
  rank: number
  /** null: no separate GPU or cooler, or no second drive. */
  components: Record<Slot, number | null>
  price_mdl: string
  performance: number
  power_w: number
  distance_best: number
  distance_worst: number
  closeness: number
}

export interface Recommendations {
  weights: { price: number; performance: number; power: number }
  performance_mix: { cpu: number; gpu: number }
  /** True: the purpose's own rules found nothing in the range, so these are entry-level builds. */
  entry_level: boolean
  /** Compatible builds priced in the chosen range that were ranked. */
  alternatives: number
  builds: RankedBuild[]
}

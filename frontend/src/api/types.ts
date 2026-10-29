// Shapes returned by the FastAPI backend (see backend/app/*schemas.py).
// Decimal fields (prices, scores) arrive as strings to keep their precision.

export const CATEGORIES = ['cpu', 'motherboard', 'ram', 'gpu', 'storage', 'psu', 'case', 'cooler'] as const
export type Category = (typeof CATEGORIES)[number]
export type Tier = 'low' | 'mid' | 'high'
export type Availability = 'in_stock' | 'on_order' | 'out_of_stock'

/** One chosen component ID per category. */
export type Selection = Partial<Record<Category, number>>

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
  items: Component[]
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
  domains: Partial<Record<Category, (number | null)[]>>
  removed: Partial<Record<Category, number[]>>
  empty_categories: Category[]
}

export interface PurchasePlan {
  status: 'complete' | 'partial'
  items: {
    category: Category
    component_id: number
    component_name: string
    store: Store
    price_mdl: string
    url: string
  }[]
  unplanned: { category: Category; component_id: number; reason: 'no_offer_in_stock' }[]
  stores: { store: Store; part_count: number; subtotal_mdl: string }[]
  total_mdl: string
}

export interface AiAnswer {
  text: string
  model: string
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
    category: Category
    component: Component
    saved_price_mdl: string | null
    saved_store: Store | null
    current_price_mdl: string | null
    current_store: Store | null
  }[]
  current_total_mdl: string
  unpriced_categories: Category[]
  compatibility: CompatibilityResult
}

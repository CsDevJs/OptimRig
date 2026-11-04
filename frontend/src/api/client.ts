import type {
  Build, BuildSummary, CompatibilityResult, ComponentDetail, ComponentPage, FilterResult,
  Purpose, PurchasePlan, Recommendations, Selection, Store, Token, User,
} from './types'

// In development Vite forwards /api to FastAPI (see vite.config.ts).
const BASE = import.meta.env.VITE_API_BASE ?? '/api'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

let authToken: string | null = null
export function setAuthToken(token: string | null) {
  authToken = token
}

/** FastAPI errors: {detail: "text"} | {detail: {message}} | {detail: [{msg, loc}]} (422). */
function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0] as { msg?: string; loc?: unknown[] }
    const field = first.loc?.at(-1)
    return field && typeof field === 'string' ? `${field}: ${first.msg}` : (first.msg ?? 'Cerere invalidă')
  }
  if (detail && typeof detail === 'object' && 'message' in detail) return String(detail.message)
  return status >= 500 ? 'Serverul a avut o problemă. Încearcă din nou peste un moment.' : `Cererea a eșuat (${status})`
}

async function request<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (init.body !== undefined) headers['Content-Type'] = 'application/json'
  if (authToken) headers.Authorization = `Bearer ${authToken}`

  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      method: init.method ?? 'GET',
      headers,
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    })
  } catch {
    throw new ApiError(0, 'Serverul nu răspunde. Rulează backend-ul pe portul 8000?')
  }
  if (response.status === 204) return undefined as T
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, errorMessage(body, response.status))
  return body as T
}

const selectionBody = (components: Selection) => ({ components })

export const api = {
  /** The whole catalog, with specs, 1000 components per request. */
  components: async () => {
    const items: ComponentPage['items'] = []
    for (;;) {
      const page = await request<ComponentPage>(`/components?limit=1000&offset=${items.length}`)
      items.push(...page.items)
      if (!page.items.length || items.length >= page.total) return items
    }
  },
  component: (id: number) => request<ComponentDetail>(`/components/${id}`),
  stores: () => request<Store[]>('/stores'),

  check: (selection: Selection) =>
    request<CompatibilityResult>('/compatibility/check', { method: 'POST', body: selectionBody(selection) }),
  filter: (selection: Selection) =>
    request<FilterResult>('/compatibility/filter', { method: 'POST', body: selectionBody(selection) }),
  plan: (selection: Selection) =>
    request<PurchasePlan>('/purchase/plan', { method: 'POST', body: selectionBody(selection) }),
  recommend: (budget_mdl: number, purpose: Purpose, cpu_brand: 'AMD' | 'Intel' | null) =>
    request<Recommendations>('/recommendations', { method: 'POST', body: { budget_mdl, purpose, cpu_brand } }),

  register: (email: string, password: string) =>
    request<User>('/auth/register', { method: 'POST', body: { email, password } }),
  /** `login` is the email. */
  login: (login: string, password: string) =>
    request<Token>('/auth/login', { method: 'POST', body: { login, password } }),
  me: () => request<User>('/auth/me'),

  builds: {
    list: () => request<BuildSummary[]>('/builds'),
    get: (id: number) => request<Build>(`/builds/${id}`),
    create: (name: string, components: Selection) =>
      request<Build>('/builds', { method: 'POST', body: { name, components } }),
    update: (id: number, name: string, components: Selection) =>
      request<Build>(`/builds/${id}`, { method: 'PUT', body: { name, components } }),
    remove: (id: number) => request<void>(`/builds/${id}`, { method: 'DELETE' }),
  },
}

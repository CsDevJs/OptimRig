import type { Category, Component, Selection, Tier } from '../api/types'

/** Ready-made builds from our own catalog (checked with /compatibility/check).
 * Prices and compatibility are always read live; nothing here is invented. */
export interface Template {
  id: string
  title: string
  usage: string
  tier: Tier
  brand: 'AMD' | 'Intel'
  parts: Record<Category, string>
}

export const TEMPLATES: Template[] = [
  {
    id: 'amd-start', title: 'Start eSports AM4', usage: 'Gaming 1080p', tier: 'low', brand: 'AMD',
    parts: {
      cpu: 'amd-ryzen-5-5500', cooler: 'deepcool-ag400-led', motherboard: 'gigabyte-b550m-ds3h-r2',
      ram: 'kingston-kf432c16bbk2-16', gpu: 'gigabyte-rtx-5050-windforce-oc-8g', storage: 'kingston-nv3-1tb',
      psu: 'be-quiet-system-power-11-650w', case: 'deepcool-cc560-v2-black',
    },
  },
  {
    id: 'intel-start', title: 'Buget Intel Compact', usage: 'Gaming 1080p & Office', tier: 'low', brand: 'Intel',
    parts: {
      cpu: 'intel-core-i3-12100f', cooler: 'deepcool-ag400-led', motherboard: 'gigabyte-b760m-h-ddr4',
      ram: 'kingston-kf432c16bbk2-16', gpu: 'gigabyte-rx-9060-xt-gaming-oc-8g', storage: 'kingston-a400-480gb',
      psu: 'cougar-atlas-750', case: 'deepcool-ch360-white',
    },
  },
  {
    id: 'amd-mid', title: 'Mid-Range AM5 1440p', usage: 'Gaming 1440p', tier: 'mid', brand: 'AMD',
    parts: {
      cpu: 'amd-ryzen-5-7600', cooler: 'deepcool-ak500s-digital-se', motherboard: 'gigabyte-b650m-d3hp',
      ram: 'kingston-kf560c36bbe2ak2-32', gpu: 'gigabyte-rx-9060-xt-gaming-oc-16g', storage: 'samsung-990-evo-plus-1tb',
      psu: 'cougar-gex-pro-750', case: 'deepcool-cc560-v2-black',
    },
  },
  {
    id: 'intel-mid', title: 'Intel Gaming & Streaming', usage: 'Gaming 1440p & Streaming', tier: 'mid', brand: 'Intel',
    parts: {
      cpu: 'intel-core-i5-14400f', cooler: 'deepcool-ak620-digital', motherboard: 'asus-tuf-gaming-b760-plus-wifi',
      ram: 'kingston-kf556c36bbek2-16', gpu: 'asus-dual-rtx-5060-ti-o16g', storage: 'kingston-nv3-2tb',
      psu: 'cougar-gex-pro-750', case: 'be-quiet-pure-base-501-lx-white',
    },
  },
  {
    id: 'amd-high', title: 'AM5 X3D High-End', usage: 'Gaming 1440p / 4K', tier: 'high', brand: 'AMD',
    parts: {
      cpu: 'amd-ryzen-7-9800x3d', cooler: 'deepcool-le360-pro-black', motherboard: 'gigabyte-x870e-aorus-elite-wifi7',
      ram: 'kingston-kf568c34bbeak2-32', gpu: 'gigabyte-rtx-5070-ti-windforce-oc-16g', storage: 'samsung-990-pro-2tb',
      psu: 'asus-rog-strix-850w-platinum', case: 'be-quiet-light-base-600-lx-white',
    },
  },
  {
    id: 'intel-high', title: 'Workstation Intel 64 GB', usage: 'Productivitate & Gaming 4K', tier: 'high', brand: 'Intel',
    parts: {
      cpu: 'intel-core-ultra-7-265k', cooler: 'arctic-liquid-freezer-iii-pro-360', motherboard: 'asus-tuf-gaming-z890-plus-wifi',
      ram: 'kingston-kf560c30bbeak2-64', gpu: 'gigabyte-rx-9070-xt-gaming-oc-16g', storage: 'samsung-990-pro-4tb',
      psu: 'be-quiet-pure-power-13-m-1000w', case: 'be-quiet-shadow-base-800-fx-white',
    },
  },
]

/** Template slugs -> component IDs in the live catalog; null if a part is missing from it. */
export function templateSelection(template: Template, catalog: Component[]): Selection | null {
  const bySlug = new Map(catalog.map((c) => [c.slug, c.id]))
  const selection: Selection = {}
  for (const [category, slug] of Object.entries(template.parts) as [Category, string][]) {
    const id = bySlug.get(slug)
    if (id === undefined) return null
    selection[category] = id
  }
  return selection
}

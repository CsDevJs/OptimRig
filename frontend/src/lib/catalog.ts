import {
  Box, CircuitBoard, Cpu, Fan, Gpu, HardDrive, MemoryStick, Zap, type LucideIcon,
} from 'lucide-react'

import type { Category, Component, Offer, Slot, SpecValue } from '../api/types'

/** Slot order and labels follow the design's manual configurator. */
export const ORDER: Slot[] = ['cpu', 'cooler', 'motherboard', 'ram', 'gpu', 'storage', 'storage2', 'psu', 'case']

export const CATEGORY_INFO: Record<Slot, { title: string; short: string; icon: LucideIcon; accent: string }> = {
  cpu: { title: 'Procesor', short: 'CPU', icon: Cpu, accent: 'text-violet-300' },
  cooler: { title: 'Cooler', short: 'cooler', icon: Fan, accent: 'text-sky-300' },
  motherboard: { title: 'Placă de bază', short: 'placă de bază', icon: CircuitBoard, accent: 'text-emerald-300' },
  ram: { title: 'Memorie RAM', short: 'RAM', icon: MemoryStick, accent: 'text-amber-300' },
  gpu: { title: 'Placă video', short: 'GPU', icon: Gpu, accent: 'text-pink-300' },
  storage: { title: 'Stocare', short: 'stocare', icon: HardDrive, accent: 'text-sky-300' },
  storage2: { title: 'Stocare 2 (opțional)', short: 'a doua unitate', icon: HardDrive, accent: 'text-sky-300' },
  psu: { title: 'Sursă', short: 'sursă', icon: Zap, accent: 'text-amber-300' },
  case: { title: 'Carcasă', short: 'carcasă', icon: Box, accent: 'text-violet-300' },
}

export const TIER_LABEL = { low: 'Buget', mid: 'Mediu', high: 'High-End' } as const

/** Cheapest offer that can be bought now; ties go to the lower store ID, like the backend. */
export function cheapestOffer(component: Component): Offer | null {
  const buyable = component.offers.filter((o) => o.availability === 'in_stock')
  if (!buyable.length) return null
  return buyable.reduce((best, o) =>
    Number(o.price_mdl) < Number(best.price_mdl)
    || (Number(o.price_mdl) === Number(best.price_mdl) && o.store.id < best.store.id) ? o : best)
}

export function componentName(component: Pick<Component, 'brand' | 'model'>): string {
  return `${component.brand} ${component.model}`
}

const gb = (value: SpecValue) => {
  const n = Number(value)
  return n >= 1000 ? `${n / 1000} TB` : `${n} GB`
}

/** One line of the specs that matter for choosing, e.g. "AM5 · 6C/12T · până la 5.1 GHz". */
export function specSummary(category: Category, s: Record<string, SpecValue> | null | undefined): string {
  if (!s) return ''
  switch (category) {
    case 'cpu':
      return `${s.socket} · ${s.cores}C/${s.threads}T · până la ${s.boost_clock_ghz} GHz · ${s.tdp_w} W`
    case 'motherboard':
      return `${s.socket} · ${s.chipset} · ${s.form_factor} · ${s.memory_type}${s.wifi ? ' · Wi-Fi' : ''}`
    case 'ram':
      return `${s.memory_type}-${s.speed_mts} · ${s.capacity_gb} GB (${s.modules}×) · CL${s.cas_latency}`
    case 'gpu':
      return `${s.vram_gb} GB · ${s.length_mm} mm lungime · ${s.tdp_w} W`
    case 'storage':
      return `${gb(s.capacity_gb)} · ${s.interface}${s.read_mbps ? ` · ${s.read_mbps} MB/s` : ''}`
    case 'psu':
      return `${s.wattage} W · ${s.efficiency} · ${s.modular === 'none' ? 'nemodulară' : s.modular === 'full' ? 'complet modulară' : 'semi-modulară'}`
    case 'case':
      return `${(s.supported_board_form_factors as string[]).join(' / ')} · GPU ≤ ${s.max_gpu_length_mm} mm · cooler ≤ ${s.max_cooler_height_mm} mm`
    case 'cooler':
      return s.cooler_type === 'aio'
        ? `Lichid AIO · radiator ${s.radiator_mm} mm${s.max_tdp_w ? ` · ${s.max_tdp_w} W` : ''}`
        : `Aer · ${s.height_mm} mm înălțime${s.max_tdp_w ? ` · ${s.max_tdp_w} W` : ''}`
  }
}

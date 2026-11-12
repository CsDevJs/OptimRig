import { Cpu, Gauge, Gpu, HardDrive, MemoryStick, Zap } from 'lucide-react'

import type { RankedBuild } from '../api/types'
import { useBuilder } from '../builder/BuilderContext'
import { useCurrency } from '../context/CurrencyContext'
import { componentName } from '../lib/catalog'

const size = (gb: number) => (gb >= 1000 ? `${gb / 1000} TB` : `${gb} GB`)

/** A build ranked by TOPSIS: its criteria values and its closeness to the ideal solution. */
export function RankedBuildCard({ build, onLoad }: { build: RankedBuild; onLoad: () => void }) {
  const { byId, specs } = useBuilder()
  const { format } = useCurrency()
  const cpu = build.components.cpu === null ? undefined : byId.get(build.components.cpu)
  const gpu = build.components.gpu === null ? undefined : byId.get(build.components.gpu)
  // Variants can differ in RAM and storage size too, so both are shown.
  const ramGb = build.components.ram ? Number(specs.get(build.components.ram)?.capacity_gb ?? 0) : 0
  const drives = [build.components.storage, build.components.storage2]
    .filter((id): id is number => id != null)
    .map((id) => {
      const s = specs.get(id)
      return s ? `${size(Number(s.capacity_gb))} ${s.storage_type === 'hdd' ? 'HDD' : 'SSD'}` : '…'
    })
  return (
    <article className="modern-sleek-card glow rounded-2xl p-4 flex flex-col justify-between gap-3">
      <div className="space-y-3">
        <div className="flex items-center justify-end gap-2">
          <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-slate-900 border border-slate-700 text-violet-200"
            title={`D+ = ${build.distance_best.toFixed(4)}, D- = ${build.distance_worst.toFixed(4)}`}>
            Scor TOPSIS {build.closeness.toFixed(3)}
          </span>
        </div>
        <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800">
          <span className="text-[9px] text-slate-400 block">Preț azi (cel mai mic)</span>
          <span className="text-lg font-extrabold font-mono text-white">{format(Number(build.price_mdl))}</span>
        </div>
        <div className="text-[11px] text-slate-300 space-y-1">
          <div className="flex items-center gap-1.5 truncate"><Cpu size={12} className="text-violet-300 shrink-0" /> {cpu ? componentName(cpu) : '—'}</div>
          <div className="flex items-center gap-1.5 truncate"><Gpu size={12} className="text-pink-300 shrink-0" /> {gpu ? componentName(gpu) : 'Grafică integrată'}</div>
          <div className="flex items-center gap-1.5 truncate"><MemoryStick size={12} className="text-pink-300 shrink-0" /> {ramGb ? `${ramGb} GB RAM` : '—'}</div>
          <div className="flex items-center gap-1.5 truncate"><HardDrive size={12} className="text-sky-300 shrink-0" /> {drives.join(' + ') || '—'}</div>
        </div>
        <div className="grid grid-cols-2 gap-2 text-[11px]">
          <div className="flex items-center gap-1.5 text-slate-300"><Gauge size={12} className="text-sky-300 shrink-0" /> Performanță {build.performance.toFixed(1)}</div>
          <div className="flex items-center gap-1.5 text-slate-300"><Zap size={12} className="text-violet-300 shrink-0" /> Consum ~{build.power_w} W</div>
        </div>
      </div>
      <button type="button" onClick={onLoad}
        className="w-full py-2 px-3 rounded-xl bg-violet-400/20 hover:bg-violet-400/30 border border-violet-400/40 text-violet-200 font-bold text-xs transition hover:scale-[1.02]">
        Personalizează în Manual
      </button>
    </article>
  )
}

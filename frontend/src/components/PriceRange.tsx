import { useState, type KeyboardEvent } from 'react'

import { useCurrency } from '../context/CurrencyContext'
import { convertFromMdl, convertToMdl, CURRENCIES } from '../lib/currencies'

interface Props {
  /** Slider ends and step, in MDL. */
  min: number
  max: number
  step: number
  low: number
  high: number
  onChange: (low: number, high: number) => void
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

/** A price range: two slider handles and two boxes to type the ends, shown in the active currency. */
export function PriceRange({ min, max, step, low, high, onChange }: Props) {
  const { code } = useCurrency()
  const pct = (v: number) => ((clamp(v, min, max) - min) / (max - min)) * 100
  return (
    <div className="space-y-4">
      <div className="relative h-5">
        <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1.5 rounded-full bg-slate-800" />
        <div className="absolute top-1/2 -translate-y-1/2 h-1.5 rounded-full bg-violet-400"
          style={{ left: `${pct(low)}%`, right: `${100 - pct(high)}%` }} />
        <input type="range" aria-label="Preț minim" min={min} max={max} step={step} value={low}
          onChange={(e) => onChange(Math.min(Number(e.target.value), high - step), high)}
          className="dual-range absolute inset-0 w-full" />
        <input type="range" aria-label="Preț maxim" min={min} max={max} step={step} value={high}
          onChange={(e) => onChange(low, Math.max(Number(e.target.value), low + step))}
          className="dual-range absolute inset-0 w-full" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <AmountBox label="Minim" mdl={low} code={code}
          onCommit={(v) => {
            const x = clamp(v, min, max)
            onChange(Math.min(x, high), Math.max(x, high))
          }} />
        <AmountBox label="Maxim" mdl={high} code={code}
          onCommit={(v) => {
            const x = clamp(v, min, max)
            onChange(Math.min(x, low), Math.max(x, low))
          }} />
      </div>
    </div>
  )
}

/** An amount typed in the active currency; applied (in MDL) on Enter or when the box loses focus. */
function AmountBox({ label, mdl, code, onCommit }: {
  label: string
  mdl: number
  code: string
  onCommit: (mdl: number) => void
}) {
  const shown = String(Math.round(convertFromMdl(mdl, code)))
  // The text being typed; null shows the current value.
  const [draft, setDraft] = useState<string | null>(null)
  const commit = () => {
    if (draft === null) return
    const amount = Number(draft.replace(/[\s,]/g, ''))
    setDraft(null)
    if (draft.trim() && Number.isFinite(amount)) onCommit(Math.round(convertToMdl(amount, code)))
  }
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') e.currentTarget.blur()
    if (e.key === 'Escape') {
      setDraft(null)
      e.currentTarget.blur()
    }
  }
  return (
    <label className="block">
      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{label}</span>
      <span className="mt-1 flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 focus-within:border-violet-400/60">
        <input type="text" inputMode="numeric" value={draft ?? shown} aria-label={`Preț ${label.toLowerCase()}`}
          onChange={(e) => setDraft(e.target.value)} onBlur={commit} onKeyDown={onKey}
          className="w-full min-w-0 bg-transparent font-mono text-sm font-bold text-white outline-none" />
        <span className="text-xs text-slate-400 shrink-0">{CURRENCIES[code]?.symbol}</span>
      </span>
    </label>
  )
}

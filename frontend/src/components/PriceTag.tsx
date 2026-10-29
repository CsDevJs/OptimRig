import type { Offer } from '../api/types'
import { useCurrency } from '../context/CurrencyContext'

/** Cheapest in-stock price, with the crossed-out regular price and a % badge during a sale. */
export function PriceTag({ offer, size = 'sm' }: { offer: Offer | null; size?: 'sm' | 'lg' }) {
  const { format } = useCurrency()
  if (!offer) return <span className="text-[11px] text-slate-400">Stoc epuizat</span>
  const regular = offer.regular_price_mdl ? Number(offer.regular_price_mdl) : null
  const price = Number(offer.price_mdl)
  const discount = regular && regular > price ? Math.round((1 - price / regular) * 100) : null
  return (
    <span className="inline-flex items-baseline justify-end gap-1.5 flex-wrap">
      {discount !== null && (
        <>
          <s className="text-[10px] text-slate-400 font-mono">{format(regular)}</s>
          <span className="px-1.5 rounded-full bg-pink-500 text-white text-[10px] font-bold">−{discount}%</span>
        </>
      )}
      <span className={`font-mono font-bold text-violet-300 ${size === 'lg' ? 'text-base' : 'text-xs'}`}>{format(price)}</span>
    </span>
  )
}

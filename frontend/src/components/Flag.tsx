import { useState } from 'react'

import { CURRENCIES } from '../lib/currencies'

/** Small country flag for a currency (from flagcdn.com), falling back to the currency code. */
export function Flag({ code }: { code: string }) {
  const [failed, setFailed] = useState(false)
  const iso = CURRENCIES[code]?.iso ?? 'md'
  return (
    <span className="country-flag-box">
      {failed
        ? code.slice(0, 2)
        : <img src={`https://flagcdn.com/20x15/${iso}.png`} alt="" loading="lazy" onError={() => setFailed(true)} />}
    </span>
  )
}

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

import { convertFromMdl, CURRENCIES, groupThousands } from '../lib/currencies'

interface CurrencyState {
  code: string
  setCode: (code: string) => void
  /** Format a price stored in MDL in the active currency, e.g. "3 799 lei" or "195 €". */
  format: (mdl: string | number | null | undefined) => string
}

const CurrencyContext = createContext<CurrencyState | null>(null)
const KEY = 'pc-configurator-currency'

function stored(): string {
  try {
    const code = localStorage.getItem(KEY)
    return code && CURRENCIES[code] ? code : 'MDL'
  } catch {
    return 'MDL'
  }
}

export function CurrencyProvider({ children }: { children: ReactNode }) {
  const [code, setCodeState] = useState(stored)

  const setCode = useCallback((next: string) => {
    if (!CURRENCIES[next]) return
    setCodeState(next)
    try {
      localStorage.setItem(KEY, next)
    } catch {
      // Storage blocked: the choice lasts for this visit only.
    }
  }, [])

  const format = useCallback((mdl: string | number | null | undefined) => {
    if (mdl === null || mdl === undefined) return '—'
    return `${groupThousands(convertFromMdl(Number(mdl), code))} ${CURRENCIES[code].symbol}`
  }, [code])

  const value = useMemo(() => ({ code, setCode, format }), [code, setCode, format])
  return <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useCurrency(): CurrencyState {
  const context = useContext(CurrencyContext)
  if (!context) throw new Error('useCurrency must be used inside <CurrencyProvider>')
  return context
}

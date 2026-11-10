import { Check, ChevronDown, CircleUser, Globe, Layers, LogOut, Search, UserCog, Users, WandSparkles, Wrench } from 'lucide-react'
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { useCurrency } from '../context/CurrencyContext'
import { useToast } from '../context/ToastContext'
import { CURRENCIES, CURRENCY_CODES } from '../lib/currencies'
import { HOVER_COLORS, HOVER_HEX, hov } from '../lib/hover'
import { Flag } from './Flag'
import { Logo } from './Logo'

const TABS = [
  { to: '/', label: 'Smart', icon: WandSparkles, color: 'text-violet-300' },
  { to: '/manual', label: 'Manual', icon: Wrench, color: 'text-sky-300' },
  { to: '/sabloane', label: 'Șabloane', icon: Layers, color: 'text-white' },
  { to: '/exchange', label: 'Exchange', icon: Globe, color: 'text-pink-300' },
  { to: '/fondatori', label: 'Fondatori', icon: Users, color: 'text-violet-300' },
]

function NavTabs() {
  const { pathname } = useLocation()
  const container = useRef<HTMLElement>(null)
  const [pill, setPill] = useState<{ left: number; width: number; color: string } | null>(null)

  // At rest the pill is the accent blue; hovering a tab tints it with that tab's own colour.
  const moveTo = useCallback((el: HTMLElement | null, color = '#7797ff') => {
    setPill(el ? { left: el.offsetLeft, width: el.offsetWidth, color } : null)
  }, [])
  const restore = useCallback(() => {
    moveTo(container.current?.querySelector<HTMLElement>('.nav-tab-item.active') ?? null)
  }, [moveTo])

  useLayoutEffect(() => {
    restore()
  }, [pathname, restore])
  // Tabs change width after fonts load, on window resize, and when the account buttons appear.
  useEffect(() => {
    if (!container.current) return
    const observer = new ResizeObserver(restore)
    observer.observe(container.current)
    container.current.querySelectorAll('.nav-tab-item').forEach((tab) => observer.observe(tab))
    return () => observer.disconnect()
  }, [restore])

  return (
    <nav ref={container} className="nav-tabs-container overflow-x-auto max-w-full [scrollbar-width:none]" onMouseLeave={restore} aria-label="Secțiuni">
      <span className="nav-sliding-pill" style={{ width: pill?.width ?? 0, transform: `translateX(${pill?.left ?? 0}px)`, opacity: pill ? 1 : 0, '--hc': pill?.color } as CSSProperties} />
      {TABS.map(({ to, label, icon: Icon, color }, i) => (
        <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => `nav-tab-item shrink-0${isActive ? ' active' : ''}`}
          onMouseEnter={(e) => moveTo(e.currentTarget, HOVER_HEX[HOVER_COLORS[i % HOVER_COLORS.length]])}>
          {/* Between lg and xl the one-row header is tight once logged in; labels alone fit. */}
          <Icon size={13} className={`${color} lg:max-xl:hidden`} /> {label}
        </NavLink>
      ))}
    </nav>
  )
}

function CurrencyMenu() {
  const { code, setCode } = useCurrency()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => !box.current?.contains(event.target as Node) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const q = query.toLowerCase()
  const codes = CURRENCY_CODES.filter((c) => !q || c.toLowerCase().includes(q) || CURRENCIES[c].label.toLowerCase().includes(q))

  return (
    <div ref={box} className="relative shrink-0">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-label="Alege moneda"
        className="px-3 py-2 rounded-xl bg-slate-950 border border-violet-400/40 flex items-center justify-between gap-2.5 min-w-[110px] hov hov-gold hover:scale-[1.03]">
        <span className="flex items-center gap-2"><Flag code={code} /><span className="text-xs font-mono font-bold text-violet-300">{code}</span></span>
        <ChevronDown size={12} className={`text-violet-300 transition-transform duration-300 ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="liquid-glass-dropdown rounded-2xl p-3 space-y-2.5 !left-auto right-0 w-[280px]">
          <div className="text-[11px] font-bold text-violet-200 uppercase tracking-wider pb-1.5 border-b border-slate-800">Valute mondiale (A–Z)</div>
          <label className="relative block">
            <Search size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Caută..."
              className="w-full pl-8 pr-2.5 py-2 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-violet-400" />
          </label>
          <div className="max-h-60 overflow-y-auto space-y-1 pr-1 text-xs">
            {codes.map((c) => (
              <button key={c} type="button"
                onClick={() => { setCode(c); setOpen(false); toast({ title: 'Monedă schimbată', message: `Monedă activă: ${c}`, tone: 'ok' }) }}
                className={`w-full px-2.5 py-1.5 rounded-xl flex items-center justify-between text-left ${hov(codes.indexOf(c))} ${c === code ? 'bg-violet-400/25 text-white' : 'text-slate-300'}`}>
                <span className="flex items-center gap-2 min-w-0">
                  <Flag code={c} /><span className="font-mono font-bold text-violet-300">{c}</span><span className="truncate">{CURRENCIES[c].label}</span>
                </span>
                {c === code && <Check size={13} className="text-violet-300 shrink-0" />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function AccountButtons() {
  const { user, loading, logout } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  if (loading) return <div className="w-[120px]" />
  if (!user) {
    return (
      <Link to="/autentificare"
        className="px-3.5 py-2 rounded-xl bg-violet-500/15 border border-violet-400/50 text-violet-200 text-xs font-bold hov hov-green hover:scale-105 flex items-center gap-2">
        <CircleUser size={15} className="text-violet-300" /> Autentificare
      </Link>
    )
  }
  return (
    <div className="flex items-center gap-2">
      <Link to="/cont" className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900 border border-violet-400/40 text-xs hov hov-green">
        <UserCog size={14} className="text-violet-300" />
        <span className="font-bold text-white truncate max-w-[160px]">{user.email}</span>
      </Link>
      <button type="button" title="Deconectare" aria-label="Deconectare"
        onClick={() => { logout(); navigate('/'); toast({ title: 'Deconectat', message: 'Ai ieșit din cont.', tone: 'ok' }) }}
        className="p-2 rounded-xl bg-slate-900 text-slate-400 border border-slate-700 hov hov-gold">
        <LogOut size={13} />
      </button>
    </div>
  )
}

export function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-slate-800/80 bg-[#0a1026]">
      <div className="max-w-7xl mx-auto px-4 py-2.5 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
        <Logo />
        <NavTabs />
        <div className="flex items-center gap-2">
          <CurrencyMenu />
          <AccountButtons />
        </div>
      </div>
    </header>
  )
}

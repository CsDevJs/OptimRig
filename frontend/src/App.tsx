import { useEffect } from 'react'
import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router-dom'

import { AuthProvider } from './auth/AuthContext'
import { BuilderProvider } from './builder/BuilderContext'
import { GlowTracker } from './components/GlowTracker'
import { Header } from './components/Header'
import { CurrencyProvider } from './context/CurrencyContext'
import { ToastProvider } from './context/ToastContext'
import { AccountPage } from './pages/AccountPage'
import { AuthPage } from './pages/AuthPage'
import { ExchangePage } from './pages/ExchangePage'
import { FoundersPage } from './pages/FoundersPage'
import { ManualPage } from './pages/ManualPage'
import { SmartPage } from './pages/SmartPage'
import { TemplatesPage } from './pages/TemplatesPage'

function ScrollToTop() {
  const { pathname } = useLocation()
  // Braces matter: newer browsers return a Promise from scrollTo, and an effect may only return a cleanup function.
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [pathname])
  return null
}

export default function App() {
  return (
    <AuthProvider>
      <CurrencyProvider>
        <ToastProvider>
          <BuilderProvider>
            <BrowserRouter basename={import.meta.env.BASE_URL}>
              <ScrollToTop />
              <GlowTracker />
              <Header />
              <main className="flex-grow max-w-7xl w-full mx-auto px-4 py-8">
                <Routes>
                  <Route path="/" element={<SmartPage />} />
                  <Route path="/manual" element={<ManualPage />} />
                  <Route path="/sabloane" element={<TemplatesPage />} />
                  <Route path="/exchange" element={<ExchangePage />} />
                  <Route path="/fondatori" element={<FoundersPage />} />
                  <Route path="/autentificare" element={<AuthPage />} />
                  <Route path="/cont" element={<AccountPage />} />
                  <Route path="*" element={
                    <div className="text-center py-16 space-y-3">
                      <h1 className="text-2xl font-extrabold text-white">Pagina nu există</h1>
                      <Link to="/" className="text-violet-300 font-bold hover:underline">Înapoi la configurator</Link>
                    </div>
                  } />
                </Routes>
              </main>
              <footer className="border-t border-slate-800/80 bg-[#0a1026] mt-10 py-5">
                <p className="max-w-7xl mx-auto px-4 text-center text-xs text-slate-400">
                  Sistem de configurare și optimizare a asamblării calculatoarelor • Prețuri din Xstore, NeoComputer, Darwin, Ultra și PrimePC
                </p>
              </footer>
            </BrowserRouter>
          </BuilderProvider>
        </ToastProvider>
      </CurrencyProvider>
    </AuthProvider>
  )
}

import { CircleAlert, CircleCheck } from 'lucide-react'
import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'

interface Toast {
  title: string
  message: string
  tone: 'ok' | 'error'
}

const ToastContext = createContext<((toast: Toast) => void) | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<Toast | null>(null)
  const timer = useRef<number | undefined>(undefined)

  const show = useCallback((next: Toast) => {
    setToast(next)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setToast(null), 3000)
  }, [])

  return (
    <ToastContext.Provider value={show}>
      {children}
      {toast && (
        <div className="fixed bottom-4 right-4 z-[100]" role="status" aria-live="polite">
          <div className="slate-glow-card px-4 py-3 rounded-2xl flex items-center gap-2.5 border border-violet-400/40 bg-slate-900/95 text-xs shadow-2xl">
            {toast.tone === 'ok'
              ? <CircleCheck size={16} className="text-emerald-300 shrink-0" />
              : <CircleAlert size={16} className="text-red-400 shrink-0" />}
            <div>
              <p className="font-bold text-white">{toast.title}</p>
              <p className="text-slate-300 text-[11px]">{toast.message}</p>
            </div>
          </div>
        </div>
      )}
    </ToastContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast() {
  const show = useContext(ToastContext)
  if (!show) throw new Error('useToast must be used inside <ToastProvider>')
  return show
}

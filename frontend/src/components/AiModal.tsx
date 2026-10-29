import { LoaderCircle, Sparkles, X } from 'lucide-react'
import { useEffect, useState } from 'react'

import { ApiError } from '../api/client'
import type { AiAnswer } from '../api/types'

interface Props {
  title: string
  loadingText: string
  /** Called once when the dialog opens. */
  ask: () => Promise<AiAnswer>
  onClose: () => void
}

export function AiModal({ title, loadingText, ask, onClose }: Props) {
  const [answer, setAnswer] = useState<AiAnswer | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    ask()
      .then((a) => active && setAnswer(a))
      .catch((e: unknown) => {
        if (!active) return
        if (e instanceof ApiError && e.status === 503) {
          setError('AI-ul nu este configurat pe server încă. Adaugă GEMINI_API_KEY în backend/.env și repornește backend-ul.')
        } else if (e instanceof ApiError && e.status === 502) {
          setError('Serviciul Gemini AI nu răspunde momentan. Încearcă din nou mai târziu.')
        } else {
          setError((e as Error).message)
        }
      })
    return () => {
      active = false
    }
  }, [ask])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-[90] bg-black/80 backdrop-blur-md flex items-center justify-center p-4" onClick={onClose}>
      <div role="dialog" aria-label={title} onClick={(e) => e.stopPropagation()}
        className="modern-sleek-card rounded-3xl max-w-2xl w-full p-6 space-y-4 border border-violet-400/40 bg-slate-950/95">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-emerald-400/30 to-violet-500/30 border border-emerald-400/50 flex items-center justify-center">
              <Sparkles size={15} className="text-emerald-300" />
            </div>
            <h3 className="text-base font-extrabold text-white">{title}</h3>
          </div>
          <button type="button" onClick={onClose} aria-label="Închide"
            className="w-8 h-8 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center border border-slate-700">
            <X size={16} />
          </button>
        </div>
        <div className="space-y-3 text-sm text-slate-200 max-h-[60vh] overflow-y-auto pr-2 leading-relaxed">
          {!answer && !error && (
            <div className="flex items-center justify-center py-10 gap-2 text-emerald-300">
              <LoaderCircle size={18} className="animate-spin" /> <span>{loadingText}</span>
            </div>
          )}
          {error && <div className="p-4 rounded-2xl bg-red-950/50 border border-red-500/50 text-red-200">{error}</div>}
          {answer && (
            <div className="p-4 rounded-2xl bg-slate-900 border border-emerald-400/30 whitespace-pre-line">
              {answer.text}
              <p className="mt-3 text-[10px] text-slate-500">Generat de {answer.model}. Verifică informațiile importante.</p>
            </div>
          )}
        </div>
        <div className="pt-3 border-t border-slate-800 flex justify-end">
          <button type="button" onClick={onClose}
            className="px-4 py-2 rounded-xl bg-violet-400/20 hover:bg-violet-400/30 border border-violet-400/40 text-violet-200 text-xs font-bold transition">
            Închide
          </button>
        </div>
      </div>
    </div>
  )
}

import { Camera, Code, ShieldHalf, Upload } from 'lucide-react'
import { useRef, useState, type ChangeEvent } from 'react'

import { useToast } from '../context/ToastContext'

const FOUNDERS = [
  { name: 'Buza Alin', role: 'Front-End Developer & UI/UX Specialist', ring: 'border-violet-400/60', text: 'text-violet-300' },
  { name: 'Grosu Vladislav', role: 'Database Developer & Architecture Lead', ring: 'border-sky-400/60', text: 'text-sky-300' },
  { name: 'Borta Adrian', role: 'Back-End Developer & Security Architect', ring: 'border-emerald-400/60', text: 'text-emerald-300' },
]

const TECH = [
  ['React + TypeScript', 'bg-violet-400/15 border-violet-400/30 text-violet-200'],
  ['Vite & Tailwind CSS', 'bg-sky-400/15 border-sky-400/30 text-sky-200'],
  ['FastAPI (Python)', 'bg-emerald-400/15 border-emerald-400/30 text-emerald-200'],
  ['PostgreSQL', 'bg-violet-400/15 border-violet-400/30 text-violet-200'],
  ['AC-3 · TOPSIS · Min-Cost Max-Flow', 'bg-sky-400/15 border-sky-400/30 text-sky-200'],
  ['Gemini AI API', 'bg-pink-400/15 border-pink-400/30 text-pink-200'],
]

function photoKey(index: number) {
  return `founderPhoto_${index}`
}

function FounderCard({ index, name, role, ring, text }: (typeof FOUNDERS)[number] & { index: number }) {
  const toast = useToast()
  const input = useRef<HTMLInputElement>(null)
  const [photo, setPhoto] = useState<string | null>(() => {
    try {
      return localStorage.getItem(photoKey(index))
    } catch {
      return null
    }
  })

  const onFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      const url = String(reader.result)
      setPhoto(url)
      try {
        localStorage.setItem(photoKey(index), url)
        toast({ title: 'Poză actualizată', message: 'Fotografia a fost salvată în acest browser.', tone: 'ok' })
      } catch {
        toast({ title: 'Poza nu s-a salvat', message: 'Imaginea e prea mare pentru stocarea browserului.', tone: 'error' })
      }
    }
    reader.readAsDataURL(file)
  }

  const initials = name.split(' ').map((w) => w[0]).join('')
  return (
    <div className="modern-sleek-card glow rounded-2xl p-6 text-center space-y-4 flex flex-col justify-between">
      <div className="space-y-4">
        <button type="button" onClick={() => input.current?.click()} title={`Schimbă poza lui ${name}`}
          className="relative w-32 h-32 mx-auto group block">
          <span className={`w-full h-full rounded-2xl overflow-hidden border-2 ${ring} bg-slate-900 flex items-center justify-center`}>
            {photo
              ? <img src={photo} alt={name} className="w-full h-full object-cover object-top transition duration-300 group-hover:scale-105" />
              : <span className={`text-4xl font-extrabold ${text}`}>{initials}</span>}
          </span>
          <span className="absolute inset-0 rounded-2xl bg-black/55 opacity-0 group-hover:opacity-100 transition flex flex-col items-center justify-center text-white text-[10px] font-bold gap-1">
            <Upload size={14} className={text} /> Schimbă poza
          </span>
        </button>
        <input ref={input} type="file" accept="image/*" className="hidden" onChange={onFile} />
        <div>
          <h3 className="text-base font-extrabold text-white">{name}</h3>
          <p className={`text-xs font-medium ${text}`}>{role}</p>
        </div>
      </div>
      <p className="text-xs text-slate-400 pt-3 border-t border-slate-800">Student UTM • Securitate Informațională (Anul II)</p>
    </div>
  )
}

export function FoundersPage() {
  return (
    <section className="space-y-6">
      <div className="slate-glow-card glow rounded-2xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-extrabold text-white">Fondatorii site-ului & echipa UTM</h2>
          <p className="text-xs text-slate-300">Studenți UTM, Securitate Informațională (Anul II)</p>
        </div>
        <span className="text-[11px] text-violet-300 bg-violet-500/10 border border-violet-400/30 px-3 py-1.5 rounded-xl font-medium flex items-center gap-1.5 w-fit">
          <Camera size={12} /> Apasă pe un avatar pentru a încărca o fotografie
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {FOUNDERS.map((f, i) => <FounderCard key={f.name} index={i} {...f} />)}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4">
        <div className="slate-glow-card glow rounded-2xl p-6 space-y-3">
          <h3 className="text-sm font-extrabold text-white flex items-center gap-2"><ShieldHalf size={15} className="text-violet-300" /> Despre proiectul academic</h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            Platformă dezvoltată la Universitatea Tehnică a Moldovei (UTM) pentru configurarea și optimizarea asamblării
            calculatoarelor: verificarea compatibilității componentelor (AC-3), clasarea configurațiilor (TOPSIS) și alegerea
            magazinelor cu costul total minim (Min-Cost Max-Flow), cu prețuri reale din magazinele din Moldova.
          </p>
        </div>
        <div className="slate-glow-card glow rounded-2xl p-6 space-y-3">
          <h3 className="text-sm font-extrabold text-white flex items-center gap-2"><Code size={15} className="text-sky-300" /> Tehnologii utilizate</h3>
          <div className="flex flex-wrap gap-2 pt-1">
            {TECH.map(([label, cls]) => <span key={label} className={`px-2.5 py-1 rounded-lg border text-xs font-mono font-bold ${cls}`}>{label}</span>)}
          </div>
        </div>
      </div>
    </section>
  )
}

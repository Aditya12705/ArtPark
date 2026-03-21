import { useState, useRef, useEffect } from 'react'
import * as pdfjs from 'pdfjs-dist'
import mammoth from 'mammoth'

// PDF Worker configuration
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@5.5.207/build/pdf.worker.min.mjs`

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? '/api' : 'http://localhost:8000')

const STAGES = [
  'Extracting skills...',
  'Computing skill gaps...',
  'Building your pathway...',
]

function FileDropZone({ title, value, onChange, placeholder }) {
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef(null)

  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = async (e) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    handleFile(file)
  }

  const handleFileChange = (e) => {
    const file = e.target.files[0]
    handleFile(file)
  }

  const handleFile = async (file) => {
    if (!file) return
    
    const fileType = file.name.split('.').pop().toLowerCase()
    let extractedText = ""

    try {
      if (fileType === 'pdf') {
        extractedText = await extractTextFromPDF(file)
      } else if (fileType === 'docx' || fileType === 'doc') {
        extractedText = await extractTextFromDOCX(file)
      } else {
        extractedText = await file.text()
      }
      onChange(extractedText)
    } catch (err) {
      console.error("Extraction failed:", err)
      alert("Failed to extract text from file. Please ensure it's not password protected.")
    }
  }

  const extractTextFromPDF = async (file) => {
    const arrayBuffer = await file.arrayBuffer()
    const loadingTask = pdfjs.getDocument({ data: arrayBuffer })
    const pdf = await loadingTask.promise
    let fullText = ""

    for (let i = 1; i <= pdf.numPages; i++) {
      const page = await pdf.getPage(i)
      const textContent = await page.getTextContent()
      const pageText = textContent.items.map(item => item.str).join(' ')
      fullText += pageText + "\n"
    }
    return fullText
  }

  const extractTextFromDOCX = async (file) => {
    const arrayBuffer = await file.arrayBuffer()
    const result = await mammoth.extractRawText({ arrayBuffer })
    return result.value
  }

  return (
    <div className="neo-card flex flex-col h-full overflow-hidden">
      <div className="px-6 py-5 border-b-2 border-white/5 bg-[#1a1a1e] flex justify-between items-center">
        <h2 className="text-sm font-black uppercase tracking-[0.2em] text-white/50">{title}</h2>
        <button 
          onClick={() => fileInputRef.current?.click()}
          className="text-xs font-bold text-[#bfff00] hover:underline"
        >
          SELECT_FILE
        </button>
        <input 
          type="file" 
          ref={fileInputRef} 
          onChange={handleFileChange} 
          accept=".txt,.pdf,.docx,.doc" 
          className="hidden" 
        />
      </div>

      <div 
        className={`flex-grow p-6 relative transition-all ${isDragging ? 'bg-[#bfff00]/5' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full h-full min-h-[350px] resize-none outline-none text-white font-mono text-sm bg-transparent placeholder-white/10 leading-relaxed"
        />
        <div className="absolute bottom-4 right-4 text-[10px] font-mono text-white/20 uppercase">
          Input_Buffer_Active
        </div>
      </div>
    </div>
  )
}

export default function UploadPage({ onComplete }) {
  const [resume, setResume] = useState('')
  const [jd, setJd] = useState('')
  
  const [loading, setLoading] = useState(false)
  const [stageIndex, setStageIndex] = useState(0)
  const [error, setError] = useState(null)
  const [maxHours, setMaxHours] = useState(40)

  const canSubmit = resume.trim().length > 20 && jd.trim().length > 20

  const handleGenerate = async () => {
    if (!canSubmit) return
    setLoading(true)
    setError(null)
    setStageIndex(0)

    try {
      const parseRes = await fetch(`${API_BASE_URL}/parse/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resume_text: resume, jd_text: jd })
      })
      if (!parseRes.ok) {
        const errData = await parseRes.json()
        throw new Error(errData.detail || `Extraction failed (${parseRes.status})`)
      }
      const parseData = await parseRes.json()
      setStageIndex(1)

      const gapRes = await fetch(`${API_BASE_URL}/gap/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate_skills: parseData.candidate_skills,
          required_skills: parseData.required_skills
        })
      })
      if (!gapRes.ok) {
        throw new Error(`Gap analysis failed (${gapRes.status})`)
      }
      const gapData = await gapRes.json()
      setStageIndex(2)

      const pathRes = await fetch(`${API_BASE_URL}/pathway/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          gaps: gapData.gaps,
          already_competent: gapData.already_competent,
          max_courses: 15,
          max_hours: maxHours,
          learner_level: 'beginner'
        })
      })
      if (!pathRes.ok) {
        throw new Error(`Synthesis failed (${pathRes.status})`)
      }
      const pathData = await pathRes.json()
      onComplete({ parseData, gapData, pathwayData: pathData })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-16">
      <div className="mb-16">
        <div className="inline-block px-3 py-1 bg-[#ff5f00]/10 border border-[#ff5f00]/30 text-[#ff5f00] text-[10px] font-black uppercase tracking-widest mb-4">
          System_Status: Operational
        </div>
        <h2 className="text-6xl font-black text-white mb-6 tracking-tighter uppercase italic leading-[0.9]">
          Engineered <br/>for <span className="text-[#bfff00]">Mastery</span>
        </h2>
        <p className="text-xl text-white/40 max-w-xl font-medium">
          Upload tactical data to initialize pathway synthesis. <br/>
          Zero noise. Pure performance.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 mb-16">
        <FileDropZone 
          title="Source_Resume"
          value={resume}
          onChange={setResume}
          placeholder="PASTE_RESUME_CONTENT_HERE..."
        />
        <FileDropZone 
          title="Target_JD"
          value={jd}
          onChange={setJd}
          placeholder="PASTE_JOB_DESCRIPTION_HERE..."
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-12 items-end">
        <div className="lg:col-span-1">
          <div className="neo-card p-8 bg-black">
             <div className="flex justify-between items-center mb-6">
                <label className="text-[10px] font-black text-white/30 uppercase tracking-[0.3em]">Max_Duration_Limit</label>
                <span className="text-2xl font-black text-[#ff5f00] font-mono whitespace-nowrap">
                  {maxHours} HR
                </span>
              </div>
              <input
                type="range"
                min="5"
                max="200"
                step="5"
                value={maxHours}
                onChange={(e) => setMaxHours(parseInt(e.target.value))}
                className="w-full h-8 bg-transparent accent-[#ff5f00] cursor-crosshair mb-2"
              />
              <div className="flex justify-between text-[8px] font-mono text-white/20 uppercase mb-1">
                <span>Min_Cap (5h)</span>
                <span>Max_Cap (200h)</span>
              </div>
              <div className="text-center text-[9px] font-mono text-[#ff5f00]/50 uppercase tracking-widest">
                ≈ {Math.ceil(maxHours / 8)} week{Math.ceil(maxHours / 8) !== 1 ? 's' : ''} at 8hr/week
              </div>
          </div>
        </div>

        <div className="lg:col-span-2">
            {loading ? (
              <div className="neo-card bg-[#bfff00] p-8 flex items-center justify-between shadow-[8px_8px_0px_#000]">
                <div className="flex items-center gap-6">
                  <div className="w-12 h-12 border-4 border-black border-t-transparent animate-spin rounded-full"></div>
                  <div>
                    <h3 className="text-black font-black uppercase text-xl">{STAGES[stageIndex]}</h3>
                    <p className="text-black/60 font-bold text-sm tracking-tight italic">SYNTESIZING_FLUID_PATHWAY...</p>
                  </div>
                </div>
                <div className="text-4xl font-black text-black">
                  {Math.round(((stageIndex + 1) / STAGES.length) * 100)}%
                </div>
              </div>
            ) : (
              <button
                onClick={handleGenerate}
                disabled={!canSubmit}
                className={`w-full py-8 neo-button text-3xl italic ${!canSubmit ? 'opacity-20 cursor-not-allowed grayscale' : ''}`}
              >
                INITIALIZE_SYNTHESIS
              </button>
            )}
        </div>
      </div>

      {error && (
        <div className="mt-12 p-6 bg-red-950/20 border-2 border-red-500/30 text-red-500 font-mono text-sm leading-relaxed">
          <span className="font-black mr-2">[ERROR_CRITICAL]</span> {error}
        </div>
      )}
    </div>
  )
}

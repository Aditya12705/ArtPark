import { useState, useRef } from 'react'

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
    if (file.type === 'application/pdf') {
       // Since frontend PDF parsing needs a library, we'll try to extract text 
       // or alert the user to use the text area.
       onChange(`[PDF Uploaded: ${file.name}]\nPlease paste the raw text here instead for best results.`)
    } else {
       const text = await file.text()
       onChange(text)
    }
  }

  return (
    <div className="flex flex-col h-full bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-100 bg-slate-50 flex justify-between items-center">
        <h2 className="font-semibold text-slate-800">{title}</h2>
        <button 
          onClick={() => fileInputRef.current?.click()}
          className="text-sm text-blue-600 hover:text-blue-800 font-medium"
        >
          Browse file
        </button>
        <input 
          type="file" 
          ref={fileInputRef} 
          onChange={handleFileChange} 
          accept=".pdf,.txt" 
          className="hidden" 
        />
      </div>

      <div 
        className={`flex-grow p-4 relative transition-colors ${isDragging ? 'bg-blue-50/50' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {isDragging && (
          <div className="absolute inset-0 z-10 border-2 border-dashed border-blue-400 rounded-lg m-4 bg-blue-50/50 flex items-center justify-center">
            <p className="text-blue-600 font-medium text-lg">Drop file here</p>
          </div>
        )}
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={`Paste text here, or drag and drop a .txt file...\n\n${placeholder}`}
          className="w-full h-full min-h-[400px] resize-none outline-none text-slate-700 bg-transparent placeholder-slate-400"
        />
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

  const canSubmit = resume.trim().length > 50 && jd.trim().length > 50

  const handleGenerate = async () => {
    if (!canSubmit) return
    
    setLoading(true)
    setError(null)
    setStageIndex(0)

    try {
      // Step 1: Parse
      const parseRes = await fetch('http://localhost:8000/parse/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resume_text: resume, jd_text: jd })
      })
      const parseData = await parseRes.json()
      if (!parseRes.ok) throw new Error(parseData.detail || 'Extracting skills failed.')

      setStageIndex(1)

      // Step 2: Gap
      const gapRes = await fetch('http://localhost:8000/gap/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate_skills: parseData.candidate_skills,
          required_skills: parseData.required_skills
        })
      })
      const gapData = await gapRes.json()
      if (!gapRes.ok) throw new Error(gapData.detail || 'Gap analysis failed.')

      setStageIndex(2)

      // Step 3: Pathway
      const pathRes = await fetch('http://localhost:8000/pathway/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          gaps: gapData.gaps,
          already_competent: gapData.already_competent,
          max_courses: 10,
          learner_level: 'beginner'
        })
      })
      const pathData = await pathRes.json()
      if (!pathRes.ok) throw new Error(pathData.detail || 'Pathway generation failed.')

      // Done
      onComplete({
        parseData,
        gapData,
        pathwayData: pathData
      })

    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      
      <div className="text-center mb-10">
        <h2 className="text-3xl font-extrabold text-slate-900 mb-3 tracking-tight">
          Design your perfect learning journey
        </h2>
        <p className="text-lg text-slate-600 max-w-2xl mx-auto">
          Upload your resume and the target job description. PathForge will identify your skill gaps and build a personalised, ready-to-execute training pathway.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
        <FileDropZone 
          title="1. Your Resume"
          value={resume}
          onChange={setResume}
          placeholder="e.g. Senior Software Engineer with 5 years experience in React, Python, and AWS..."
        />
        <FileDropZone 
          title="2. Target Job Description"
          value={jd}
          onChange={setJd}
          placeholder="e.g. We are looking for a Data Engineer proficient in Python, SQL, Airflow, and Snowflake..."
        />
      </div>

      {error && (
        <div className="mb-8 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
          <svg className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <h3 className="text-red-800 font-medium text-sm">Action failed</h3>
            <p className="text-red-700 text-sm mt-1">{error}</p>
          </div>
        </div>
      )}

      <div className="flex flex-col items-center justify-center">
        {loading ? (
          <div className="bg-white px-8 py-6 rounded-2xl shadow-sm border border-slate-200 w-full max-w-md flex flex-col items-center">
            <div className="relative w-16 h-16 mb-4">
              <div className="absolute inset-0 rounded-full border-4 border-slate-100"></div>
              <div className="absolute inset-0 rounded-full border-4 border-blue-600 border-t-transparent animate-spin"></div>
            </div>
            <p className="font-semibold text-slate-800 mb-1">{STAGES[stageIndex]}</p>
            <p className="text-sm text-slate-500">This usually takes about {stageIndex === 0 ? '15' : '5'} seconds.</p>
            
            <div className="w-full bg-slate-100 h-1.5 rounded-full mt-5 overflow-hidden">
              <div 
                className="bg-blue-600 h-full rounded-full transition-all duration-500 ease-out"
                style={{ width: `${((stageIndex + 1) / STAGES.length) * 100}%` }}
              ></div>
            </div>
          </div>
        ) : (
          <button
            onClick={handleGenerate}
            disabled={!canSubmit}
            className={`
              px-8 py-4 rounded-xl font-bold text-lg shadow-sm transition-all
              ${canSubmit 
                ? 'bg-blue-600 hover:bg-blue-700 text-white hover:shadow-md transform hover:-translate-y-0.5' 
                : 'bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200'}
            `}
          >
            Generate my learning pathway
          </button>
        )}
      </div>

    </div>
  )
}

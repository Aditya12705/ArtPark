import { useState } from 'react';
import ReasoningTracePanel from './ReasoningTracePanel';

export default function PathwayPage({ data }) {
  if (!data || !data.pathwayData || !data.gapData) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-16 text-white text-center">
        <h2 className="text-4xl font-black uppercase mb-4">Error: Missing Data</h2>
        <p className="text-white/40">The pathway generation failed or returned incomplete data.</p>
      </div>
    )
  }

  const { pathwayData, gapData, parseData } = data
  const { pathway = [], estimated_total_hours = 0, reasoning_traces = {}, pathway_summary = "" } = pathwayData
  const { gaps = {} } = gapData

  // Extraction confidence from the parse step (0.0–1.0)
  const extractionConfidence = parseData?.extraction_confidence ?? null

  // Efficiency metrics
  const totalGapCount = Object.keys(gaps).length
  const skippedCount = (pathwayData.skipped_courses || []).length

  // A meaningful baseline: if there were NO skipping, every gap would need ~8h of training.
  // Savings = how many hours we *avoided* by skipping already-competent courses.
  const skippedHoursAvoided = skippedCount * 8
  const baselineHours = estimated_total_hours + skippedHoursAvoided
  const savingsPct = baselineHours > 0
    ? Math.round((skippedHoursAvoided / baselineHours) * 100)
    : 0

  const [selectedSkill, setSelectedSkill] = useState(null)
  const [selectedCourse, setSelectedCourse] = useState(null)

  const toggleSkill = (skill) => {
    setSelectedSkill(prev => prev === skill ? null : skill)
  }

  const openTrace = (course) => {
    setSelectedCourse(course)
  }

  const closeTrace = () => {
    setSelectedCourse(null)
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-16">

      {/* Reasoning Trace Drawer */}
      <ReasoningTracePanel
        course={selectedCourse}
        gaps={gaps}
        pathway={pathway}
        onClose={closeTrace}
        onSelectCourse={openTrace}
      />

      {/* Header section */}
      <div className="mb-12">
        <div className="flex items-center gap-4 mb-6">
           <div className="px-4 py-2 border-2 border-[#bfff00] text-[#bfff00] font-black text-xs uppercase tracking-widest">
             Synthesis_Report
           </div>
           <div className="h-[2px] flex-grow bg-white/10"></div>
           {/* Extraction confidence badge */}
           {extractionConfidence !== null && (
             <div className={`px-3 py-1 border text-[10px] font-black uppercase tracking-widest ${
               extractionConfidence >= 0.8 ? 'border-[#bfff00]/40 text-[#bfff00] bg-[#bfff00]/5' :
               extractionConfidence >= 0.6 ? 'border-yellow-500/40 text-yellow-400 bg-yellow-500/5' :
               'border-red-500/40 text-red-400 bg-red-500/5'
             }`}>
               Extraction_Confidence: {Math.round(extractionConfidence * 100)}%
             </div>
           )}
        </div>
        <h2 className="text-4xl sm:text-6xl font-black text-white italic tracking-tighter uppercase leading-none mb-8">
          The <span className="text-[#ff5f00]">Tactical</span> Feed
        </h2>
        <div className="neo-card p-6 sm:p-10 bg-black/40 text-xl sm:text-2xl font-medium leading-relaxed border-l-8 border-l-[#bfff00]">
          {pathway_summary || "Your personalised training pathway is ready."}
        </div>
      </div>

      {/* EFFICIENCY METRICS — 4-card grid */}
      <div className="mb-10 grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="neo-card p-6 bg-black flex flex-col items-center justify-center">
          <div className="text-[9px] font-black text-white/30 uppercase tracking-[0.3em] mb-2">Gaps_Identified</div>
          <div className="text-4xl font-black text-[#bfff00]">{totalGapCount}</div>
          <div className="text-[9px] text-white/30 mt-1 uppercase font-mono">skill deficits</div>
        </div>
        <div className="neo-card p-6 bg-black flex flex-col items-center justify-center">
          <div className="text-[9px] font-black text-white/30 uppercase tracking-[0.3em] mb-2">Pathway_Hours</div>
          <div className="text-4xl font-black text-[#ff5f00]">{estimated_total_hours}h</div>
          <div className="text-[9px] text-white/30 mt-1 uppercase font-mono">optimised duration</div>
        </div>
        <div className="neo-card p-6 bg-black flex flex-col items-center justify-center">
          <div className="text-[9px] font-black text-white/30 uppercase tracking-[0.3em] mb-2">Courses_Skipped</div>
          <div className="text-4xl font-black text-white">{skippedCount}</div>
          <div className="text-[9px] text-white/30 mt-1 uppercase font-mono">already competent</div>
        </div>
        <div className="neo-card p-6 bg-black flex flex-col items-center justify-center">
          <div className="text-[9px] font-black text-white/30 uppercase tracking-[0.3em] mb-2">Training_Saved</div>
          <div className={`text-4xl font-black ${savingsPct > 0 ? 'text-[#bfff00]' : 'text-white/40'}`}>
            {savingsPct > 0 ? `${savingsPct}%` : '—'}
          </div>
          <div className="text-[9px] text-white/30 mt-1 uppercase font-mono">vs. one-size-fits-all</div>
        </div>
      </div>

      {/* TACTICAL LEGEND */}
      <div className="mb-16 border border-white/10 p-8 bg-[#1a1a1e]/50 flex flex-wrap gap-12 items-start">
        <div className="max-w-xs">
          <h4 className="text-[#bfff00] font-black text-xs uppercase tracking-widest mb-4">Status_Key</h4>
          <div className="space-y-4 text-xs text-white/60 leading-relaxed uppercase font-black">
            <div className="flex gap-3 items-center">
              <div className="w-4 h-4 bg-[#bfff00]"></div>
              <span>CURRENT_SKILL_LEVEL</span>
            </div>
            <div className="flex gap-3 items-center">
              <div className="w-4 h-4 bg-[#ff00ff]/20 border border-[#ff00ff]/40"></div>
              <span>REQUIRED_GAP_DISTANCE</span>
            </div>
            <div className="flex gap-3 items-center">
              <div className="w-4 h-4 bg-white/5 border border-white/5"></div>
              <span>UNREQUIRED_LEVEL_CAPACITY</span>
            </div>
          </div>
        </div>
        
        <div className="flex-grow max-w-sm">
          <h4 className="text-[#ff5f00] font-black text-xs uppercase tracking-widest mb-4">Metric_Definitions</h4>
          <div className="space-y-2 text-[10px] text-white/40 leading-relaxed font-mono">
            <p><span className="text-white">Δ (DELTA):</span> The intensity of the skill gap. A higher Delta means more training needed to reach the target seniority.</p>
            <p><span className="text-white">LEVEL:</span> Beginner, Intermediate, or Advanced. Matches the course depth to your current capacity.</p>
            <p><span className="text-white">OPTIMISED_PATH:</span> Only the <span className="text-[#bfff00]">Minimal Effective Sequence</span> is shown. One course often addresses multiple gaps for maximum efficiency.</p>
          </div>
        </div>

        <div className="max-w-xs">
          <h4 className="text-white font-black text-xs uppercase tracking-widest mb-4">Interactivity</h4>
          <div className="text-[10px] text-white/40 font-mono italic space-y-2">
            <p>"Click any <span className="text-[#bfff00]">[GAP_ANALYSIS]</span> card to highlight the courses that address that specific deficit."</p>
            <p>"Click any <span className="text-[#ff5f00]">[COURSE]</span> card to open the AI reasoning trace and skill level breakdown."</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-16">
        {/* Left: Skill Gaps */}
        <div className="lg:col-span-1">
          <h3 className="text-sm font-black uppercase tracking-[0.4em] text-white/30 mb-8 border-b border-white/10 pb-4">
            Gap_Analysis_Delta
          </h3>
          <div className="space-y-6">
            {Object.entries(gaps).map(([skill, detail]) => {
              const isCovered = pathway.some(c => (c.skills_addressed || []).includes(skill));
              
              return (
                <div 
                  key={skill} 
                  className={`neo-card p-6 transition-all cursor-pointer ${
                    selectedSkill === skill ? 'border-[#bfff00] bg-[#bfff00]/10 ring-4 ring-[#bfff00]/10' : 'bg-[#1a1a1e]'
                  }`}
                  onClick={() => toggleSkill(skill)}
                >
                  <div className="flex justify-between items-start mb-4">
                    <div className="flex flex-col">
                      <span className="font-black text-white uppercase tracking-tight text-lg leading-none mb-2">
                        {skill.replace(/_/g, ' ')}
                      </span>
                      <span className={`text-[9px] font-black uppercase tracking-widest px-2 py-0.5 w-fit ${
                        isCovered ? 'bg-[#bfff00] text-black' : 'bg-red-500 text-white'
                      }`}>
                        {isCovered ? 'TARGET_COVERED' : 'UNADDRESSED_GAP'}
                      </span>
                    </div>
                    <span className="font-mono text-[#ff00ff] text-sm">Δ{detail.delta}</span>
                  </div>
                  
                  <div className="flex gap-1 h-3">
                     {[1,2,3,4,5].map(step => (
                       <div 
                         key={step}
                         className={`flex-grow border border-white/5 relative group/bar ${
                           step <= detail.current ? 'bg-[#bfff00]' : 
                           step <= detail.required ? 'bg-[#ff00ff]/20 border-[#ff00ff]/40' : 
                           'bg-white/5'
                         }`}
                       >
                         <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover/bar:block bg-black text-[8px] p-1 whitespace-nowrap border border-white/10 z-50">
                            {step <= detail.current ? 'CURRENT' : step <= detail.required ? 'TARGET' : 'MAX'}
                         </div>
                       </div>
                     ))}
                  </div>
                  <div className="flex justify-between mt-2 text-[10px] font-mono text-white/20 uppercase">
                    <span>Lv.{detail.current}</span>
                    <span>Lv.{detail.required}</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Right: Pathway */}
        <div className="lg:col-span-2">
          <h3 className="text-sm font-black uppercase tracking-[0.4em] text-white/30 mb-8 border-b border-white/10 pb-4">
            Deployment_Sequence
          </h3>
          <div className="space-y-8 relative">
            <div className="absolute left-[39px] top-0 bottom-0 w-1 bg-gradient-to-b from-[#bfff00] via-[#ff5f00] to-transparent opacity-20"></div>
            
            {pathway.map((course, idx) => {
              const isMatched = selectedSkill && (course.skills_addressed || []).includes(selectedSkill)
              
              return (
                <div 
                  key={course.course_id} 
                  className={`flex gap-8 group cursor-pointer transition-all duration-500 ${
                    selectedSkill && !isMatched ? 'opacity-20 translate-x-4 grayscale' : 'opacity-100'
                  } ${isMatched ? 'scale-[1.02]' : ''}`}
                >
                  <div
                    className="flex-shrink-0 w-20 h-20 bg-black border-4 border-white/10 flex items-center justify-center relative z-10 transition-colors group-hover:border-[#bfff00]"
                    onClick={() => window.open(course.url, '_blank')}
                  >
                    <span className="text-3xl font-black text-white/20 group-hover:text-[#bfff00] transition-colors">
                      {String(idx + 1).padStart(2, '0')}
                    </span>
                  </div>
                  
                  <div className="flex-grow pt-2">
                    <div className={`neo-card p-8 transition-all duration-500 ${
                      isMatched ? 'border-[#bfff00] shadow-[0_0_30px_rgba(191,255,0,0.2)] bg-[#1a1a1e]' : 'bg-[#111114]'
                    }`}>
                      <div className="flex justify-between items-start mb-6">
                        <h4 className="text-2xl font-black text-white uppercase tracking-tighter leading-none">
                          {course.title}
                        </h4>
                        <div className="flex flex-col items-end gap-1">
                          {course.provider === 'AI DISCOVERY' && (
                            <div className="px-3 py-1 bg-yellow-500/10 border border-yellow-500/40 text-[10px] font-black text-yellow-400 uppercase tracking-wider">
                              ⚠ AI_SUGGESTED
                            </div>
                          )}
                          <div className="px-3 py-1 bg-white/5 border border-white/10 text-[10px] font-mono text-white/40">
                            {course.provider === 'AI DISCOVERY' ? 'DYNAMIC DISCOVERY' : (course.provider || "INTERNAL")}
                          </div>
                          <div className="px-3 py-1 bg-white/5 border border-white/10 text-[10px] font-mono text-white/40 uppercase">
                            EST: {course.duration_hours}H
                          </div>
                        </div>
                      </div>

                      {/* AI Suggested disclaimer */}
                      {course.provider === 'AI DISCOVERY' && (
                        <div className="mb-4 px-3 py-2 bg-yellow-500/5 border border-yellow-500/20 text-yellow-400/70 text-[10px] font-mono leading-relaxed">
                          This resource falls outside the curated catalog and was AI-suggested to bridge an uncovered gap. Please verify before use.
                        </div>
                      )}

                      <div className="p-4 bg-black/40 border-l-4 border-l-[#ff5f00] text-white/60 font-mono text-sm leading-relaxed mb-6 italic">
                        {course.reasoning || "Strategic choice to address your primary skill gaps."}
                      </div>

                      <div className="flex flex-wrap gap-2">
                        {(course.skills_addressed || []).map(skill => (
                          <span key={skill} className="px-2 py-1 bg-[#bfff00]/5 border border-[#bfff00]/20 text-[#bfff00] text-[10px] font-black uppercase tracking-widest">
                            {skill}
                          </span>
                        ))}
                        <span className={`ml-auto px-2 py-1 border text-[10px] font-black uppercase tracking-widest ${
                          course.cognitive_load === 'high' ? 'border-red-500/40 text-red-500' : 'border-blue-500/40 text-blue-500'
                        }`}>
                          LOAD: {course.cognitive_load}
                        </span>
                      </div>

                      <div className="mt-8 pt-6 border-t border-white/5 flex gap-3 justify-end">
                        {/* Reasoning Trace button */}
                        <button
                          onClick={() => openTrace(course)}
                          className="px-5 py-2 bg-transparent border border-[#ff5f00]/50 text-[#ff5f00] font-black text-xs uppercase tracking-tighter hover:bg-[#ff5f00]/10 transition-all"
                        >
                          WHY_THIS? →
                        </button>
                        <button
                          onClick={() => window.open(course.url, '_blank')}
                          className="px-6 py-2 bg-[#bfff00] text-black font-black text-xs uppercase tracking-tighter shadow-[4px_4px_0px_#ffffff20] hover:shadow-[4px_4px_0px_#ff5f00] transition-all"
                        >
                          START_LEARNING →
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}

            {/* Empty state */}
            {pathway.length === 0 && (
              <div className="neo-card p-16 text-center bg-[#1a1a1e]">
                <div className="text-6xl mb-6">🎯</div>
                <h3 className="text-2xl font-black text-[#bfff00] uppercase mb-3">Fully Qualified</h3>
                <p className="text-white/40 font-mono text-sm">No skill gaps detected. The candidate already meets all requirements for this role.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

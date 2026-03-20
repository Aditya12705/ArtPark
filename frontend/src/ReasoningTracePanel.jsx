import React, { useEffect, useState } from 'react'
import { X, Clock, Target, ArrowRight, CheckCircle2, ChevronRight } from 'lucide-react'

export default function ReasoningTracePanel({ course, gaps, pathway, onClose, onSelectCourse }) {
  // Local state to track completion of courses (persists while panel component is mounted)
  const [completedMap, setCompletedMap] = useState({})
  
  // Handle Escape key to close
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const [activeCourse, setActiveCourse] = useState(course)

  useEffect(() => {
    if (course) setActiveCourse(course)
  }, [course])

  const displayCourse = course || activeCourse

  const isCompleted = completedMap[displayCourse?.course_id] || false
  const toggleComplete = () => {
    if (displayCourse) {
      setCompletedMap(prev => ({ ...prev, [displayCourse.course_id]: !prev[displayCourse.course_id] }))
    }
  }

  // Find prerequisites
  const currentIndex = pathway.findIndex(c => c.course_id === displayCourse?.course_id)
  const immediatePrereq = currentIndex > 0 ? pathway[currentIndex - 1] : null

  return (
    <>
      {/* Backdrop for click-outside dismissal */}
      <div 
        className={`fixed inset-0 z-40 bg-slate-900/20 backdrop-blur-[1px] transition-opacity duration-300 ${course ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={onClose}
      />

      {/* Slide-in Drawer */}
      <div className={`fixed top-0 right-0 h-full w-full sm:w-[420px] bg-white shadow-2xl z-50 transform transition-transform duration-300 ease-in-out border-l border-slate-200 flex flex-col ${course ? 'translate-x-0' : 'translate-x-full'}`}>
        
        {/* Header */}
        <div className="px-6 py-5 border-b border-slate-100 flex justify-between items-start bg-slate-50/50">
          <div>
            <h2 className="text-xl font-extrabold text-slate-900 leading-tight mb-2 pr-4">{displayCourse?.title}</h2>
            <div className="flex gap-3 text-sm font-semibold">
              <span className="bg-white border border-slate-200 text-slate-600 px-2 py-1 rounded-md flex items-center gap-1.5 shadow-sm">
                <Clock className="w-4 h-4 text-slate-400" />
                {displayCourse?.duration_hours}h
              </span>
              <span className="bg-white border border-slate-200 text-blue-700 px-2 py-1 rounded-md flex items-center gap-1.5 capitalize shadow-sm">
                <Target className="w-4 h-4 text-blue-400" />
                {displayCourse?.level}
              </span>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 hover:bg-slate-100 p-1.5 rounded-md transition-colors flex-shrink-0">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="p-6 overflow-y-auto flex-grow flex flex-col gap-8">
          
          {/* Why this course? (Reasoning Trace) */}
          <section>
            <h3 className="text-xs font-extrabold text-slate-400 uppercase tracking-widest mb-3">
              Why this course?
            </h3>
            <div className="bg-blue-50 border-l-4 border-blue-500 rounded-r-lg p-4 text-blue-900 text-sm leading-relaxed shadow-sm">
              <span className="font-semibold block mb-1">AI Reasoning Trace:</span>
              {displayCourse?.reasoning || "Addresses key gaps matching your career trajectory."}
            </div>
          </section>

          {/* Skills this course teaches */}
          <section>
            <h3 className="text-xs font-extrabold text-slate-400 uppercase tracking-widest mb-3">
              Skills you'll level up
            </h3>
            <div className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
              {displayCourse?.skills_addressed?.map(skill => {
                const gap = gaps[skill] || { current: 0, required: 1 }
                const skillName = skill.replace(/_/g, ' ')
                return (
                  <div key={skill} className="flex flex-wrap items-center justify-between py-3 px-4 border-b border-slate-100 last:border-0 bg-slate-50/30 hover:bg-slate-50 transition-colors">
                    <span className="font-bold text-slate-700 capitalize text-sm">{skillName}</span>
                    <div className="flex items-center gap-2 text-sm font-semibold">
                      <span className="text-slate-500 bg-white border border-slate-200 px-2 py-0.5 rounded shadow-sm">
                        Lvl {gap.current}
                      </span>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                      <span className="text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded shadow-sm">
                        Lvl {gap.required}
                      </span>
                    </div>
                  </div>
                )
              })}
              {!displayCourse?.skills_addressed?.length && (
                <div className="py-3 px-4 text-sm text-slate-500 italic">Core foundational concepts.</div>
              )}
            </div>
          </section>

          {/* Prerequisites */}
          {immediatePrereq && (
            <section>
              <h3 className="text-xs font-extrabold text-slate-400 uppercase tracking-widest mb-3">
                Required Prerequisite
              </h3>
              <p className="text-sm text-slate-500 mb-2">Complete this first:</p>
              <button 
                onClick={() => onSelectCourse(immediatePrereq)}
                className="w-full relative group bg-white border border-slate-200 rounded-lg p-3 hover:border-blue-400 hover:shadow-md transition-all text-left flex items-start justify-between gap-3"
              >
                <div>
                  <h4 className="font-bold text-slate-800 text-sm group-hover:text-blue-700 transition-colors">
                    {immediatePrereq.title}
                  </h4>
                  <p className="text-xs text-slate-500 mt-1 line-clamp-1">{immediatePrereq.skills_addressed?.join(', ').replace(/_/g, ' ')}</p>
                </div>
                <ChevronRight className="w-5 h-5 text-slate-400 group-hover:text-blue-500 flex-shrink-0 mt-1" />
              </button>
            </section>
          )}

        </div>

        {/* Footer Action */}
        <div className="p-6 border-t border-slate-100 bg-white">
          <button
            onClick={toggleComplete}
            className={`
              w-full py-3.5 rounded-xl font-bold flex items-center justify-center gap-2 transition-all shadow-sm
              ${isCompleted 
                ? 'bg-green-50 text-green-700 border border-green-200 hover:bg-green-100' 
                : 'bg-slate-800 text-white hover:bg-slate-900'}
            `}
          >
            {isCompleted ? (
              <>
                <CheckCircle2 className="w-5 h-5" />
                Completed
              </>
            ) : (
              'Mark as Complete'
            )}
          </button>
        </div>

      </div>
    </>
  )
}

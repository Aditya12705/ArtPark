import React, { useState, useMemo } from 'react'
import ReasoningTracePanel from './ReasoningTracePanel'
import {
  ReactFlow,
  Controls,
  Background,
  Handle,
  Position,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Legend
} from 'recharts'
import { Clock, BookCheck, Sparkles, X, ChevronRight, CheckCircle2 } from 'lucide-react'

// Custom node type for React Flow
const CourseNode = ({ data }) => {
  const { course, isSkipped } = data
  
  const levelColors = {
    beginner: 'bg-green-100 text-green-800 border-green-200',
    intermediate: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    advanced: 'bg-red-100 text-red-800 border-red-200',
    competent: 'bg-slate-200 text-slate-700 border-slate-300'
  }
  const levelClass = levelColors[course.level?.toLowerCase()] || levelColors.beginner

  return (
    <div className={`
      relative px-4 py-3 shadow-md rounded-xl border-2 w-72 bg-white transition-all
      ${isSkipped ? 'opacity-60 border-slate-200 bg-slate-50' : 'border-blue-400 hover:border-blue-600 hover:shadow-lg hover:-translate-y-1 cursor-pointer'}
    `}>
      <Handle type="target" position={Position.Top} className="w-3 h-3 bg-blue-300 border-none" />
      
      <div className="flex justify-between items-start mb-2 gap-2">
        <h3 className="font-bold text-slate-800 text-sm leading-snug">{course.title}</h3>
        {isSkipped && (
          <span className="shrink-0 bg-slate-200 text-slate-600 text-[10px] font-bold px-1.5 py-0.5 rounded flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" /> Done
          </span>
        )}
      </div>

      <div className="flex items-center justify-between">
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider border ${levelClass}`}>
          {course.level || 'Competent'}
        </span>
        {!isSkipped && (
          <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-2 py-1 rounded-md">
            {course.duration_hours}h
          </span>
        )}
      </div>

      <Handle type="source" position={Position.Bottom} className="w-3 h-3 bg-blue-300 border-none" />
    </div>
  )
}

const nodeTypes = { courseNode: CourseNode }

export default function PathwayPage({ data }) {
  const { parseData, gapData, pathwayData } = data
  const { pathway = [], skipped_courses = [], estimated_total_hours = 0 } = pathwayData
  const { gaps = {} } = gapData || {}
  const { raw_resume_skills = [] } = parseData || {}

  const [selectedCourse, setSelectedCourse] = useState(null)

  // 1. Prepare React Flow layout (Vertical linear progression to simulate DAG)
  const { nodes, edges } = useMemo(() => {
    const newNodes = []
    const newEdges = []
    let yPos = 50

    // Add Skipped Courses First
    skipped_courses.forEach((sc, idx) => {
      newNodes.push({
        id: `skip-${sc}`,
        type: 'courseNode',
        position: { x: window.innerWidth < 768 ? 20 : 100, y: yPos },
        data: { 
          course: { course_id: sc, title: sc.replace(/_/g, ' '), level: 'competent', duration_hours: 0 },
          isSkipped: true 
        },
        draggable: false
      })
      yPos += 120
    })

    // Add Pathway Courses
    if (skipped_courses.length > 0) yPos += 40 // visual gap between skipped and active

    pathway.forEach((course) => {
      newNodes.push({
        id: course.course_id,
        type: 'courseNode',
        position: { x: window.innerWidth < 768 ? 20 : 100, y: yPos },
        data: { course, isSkipped: false }
      })
      yPos += 140
    })

    // Link them all sequentially via edges
    for (let i = 0; i < newNodes.length - 1; i++) {
       newEdges.push({
         id: `e-${newNodes[i].id}-${newNodes[i+1].id}`,
         source: newNodes[i].id,
         target: newNodes[i+1].id,
         animated: true,
         style: { stroke: '#cbd5e1', strokeWidth: 2 }
       })
    }

    return { nodes: newNodes, edges: newEdges }
  }, [pathway, skipped_courses])

  // 2. Prepare Recharts data
  const chartData = useMemo(() => {
    return Object.entries(gaps)
      .map(([id, gap]) => ({
        skill: id.replace(/_/g, ' ').slice(0, 15) + (id.length > 15 ? '...' : ''),
        current: gap.current,
        delta: gap.delta,
        required: gap.required
      }))
      .sort((a, b) => b.delta - a.delta) // largest gaps first
  }, [gaps])

  const onNodeClick = (event, node) => {
    if (!node.data.isSkipped) {
      setSelectedCourse(node.data.course)
    }
  }

  // Calculate Mock Saved Hours (assuming 5h average for skipped courses)
  const savedHours = skipped_courses.length * 5

  return (
    <div className="flex flex-col lg:flex-row h-[calc(100vh-64px)] w-full bg-slate-50 relative overflow-hidden">
      
      {/* SVG Defs for striped chart pattern */}
      <svg width="0" height="0">
        <defs>
          <pattern id="stripe" patternUnits="userSpaceOnUse" width="4" height="4" patternTransform="rotate(45)">
            <rect width="2" height="4" fill="#60a5fa" />
            <rect x="2" width="2" height="4" fill="#bfdbfe" />
          </pattern>
        </defs>
      </svg>

      {/* LEFT PANEL : 60% : React Flow Roadmap */}
      <div className="w-full lg:w-[60%] h-[50vh] lg:h-full border-b lg:border-b-0 lg:border-r border-slate-200 relative bg-white overflow-hidden">
        <div className="absolute top-4 left-4 z-10 bg-white/90 backdrop-blur-sm px-4 py-2 rounded-lg shadow-sm border border-slate-200 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-blue-600" />
          <h2 className="font-bold text-slate-800">Learning Roadmap</h2>
        </div>
        
        <ReactFlow 
          nodes={nodes} 
          edges={edges} 
          nodeTypes={nodeTypes}
          onNodeClick={onNodeClick}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.5}
        >
          <Background color="#cbd5e1" gap={16} />
          <Controls className="bg-white shadow-md border-slate-200" />
        </ReactFlow>

        <ReasoningTracePanel 
          course={selectedCourse} 
          gaps={gaps} 
          pathway={pathway} 
          onClose={() => setSelectedCourse(null)} 
          onSelectCourse={setSelectedCourse} 
        />
      </div>

      {/* RIGHT PANEL : 40% : Data Summary */}
      <div className="w-full lg:w-[40%] h-[50vh] lg:h-full overflow-y-auto bg-slate-50 p-6 flex flex-col gap-6">
        
        <div>
          <h2 className="text-xl font-extrabold text-slate-900 mb-1">Target Role Gap Analysis</h2>
          <p className="text-sm text-slate-500 mb-6">Visual breakdown of your current abilities vs required targets.</p>
          
          <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200">
            <h3 className="text-sm font-bold text-slate-700 mb-4 flex items-center gap-2">
              <ChevronRight className="w-4 h-4 text-blue-500" />
              Proficiency Deltas
            </h3>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                  <XAxis type="number" domain={[0, 5]} ticks={[1,2,3,4,5]} fontSize={11} stroke="#94a3b8" />
                  <YAxis type="category" dataKey="skill" width={100} fontSize={11} stroke="#64748b" fontWeight="600" />
                  <RechartsTooltip 
                    cursor={{ fill: '#f1f5f9' }}
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                  />
                  <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                  <Bar dataKey="current" name="Current Level" stackId="a" fill="#3b82f6" radius={[0, 0, 0, 0]} barSize={20} />
                  <Bar dataKey="delta" name="Gap to Fill" stackId="a" fill="url(#stripe)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200">
            <div className="flex items-center gap-2 mb-2 text-blue-600">
              <Clock className="w-5 h-5" />
              <h4 className="font-bold text-sm">Est. Training Time</h4>
            </div>
            <p className="text-3xl font-extrabold text-slate-800">{estimated_total_hours}<span className="text-base font-medium text-slate-500 ml-1">hours</span></p>
          </div>
          
          <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200">
            <div className="flex items-center gap-2 mb-2 text-green-600">
              <BookCheck className="w-5 h-5" />
              <h4 className="font-bold text-sm">Modules Skipped</h4>
            </div>
            <p className="text-3xl font-extrabold text-slate-800">{skipped_courses.length}</p>
            <p className="text-xs text-green-600 font-semibold mt-1 bg-green-50 inline-block px-1.5 py-0.5 rounded">
              Saved ~{savedHours}h
            </p>
          </div>
        </div>

        <div className="bg-slate-800 p-5 rounded-2xl shadow-sm text-white mt-auto">
          <h3 className="text-sm font-bold text-slate-300 mb-3 uppercase tracking-wider">Your Baseline Profile</h3>
          <div className="flex flex-wrap gap-2">
            {raw_resume_skills.map((skill, i) => (
              <span key={i} className="bg-slate-700 text-slate-200 text-xs px-2.5 py-1 rounded border border-slate-600">
                {skill}
              </span>
            ))}
            {raw_resume_skills.length === 0 && (
              <span className="text-slate-400 text-sm italic">No valid foundational skills extracted from resume.</span>
            )}
          </div>
        </div>

      </div>
    </div>
  )
}

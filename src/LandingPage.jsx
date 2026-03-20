export default function LandingPage({ onStart }) {
  const steps = [
    {
      num: '01',
      label: 'Upload & Parse',
      color: '#bfff00',
      desc: 'Drop your résumé and the job description. Claude Opus 4.5 extracts every skill mention with a proficiency score — no guessing, no hallucinations.',
      icon: '📄',
    },
    {
      num: '02',
      label: 'Gap Engine',
      color: '#ff5f00',
      desc: 'A 55-node skills DAG computes your exact delta per skill. Temporal Skill Decay penalises knowledge unused for years. BFS propagation surfaces hidden prerequisite gaps automatically.',
      icon: '⚡',
    },
    {
      num: '03',
      label: 'Adaptive Pathway',
      color: '#ff00ff',
      desc: "Kahn's topological sort builds a dependency-safe course sequence. Cognitive Load Balancing alternates heavy and light modules. Your HR time budget is a hard cap — never exceeded.",
      icon: '🧭',
    },
    {
      num: '04',
      label: 'Reasoning Traces',
      color: '#bfff00',
      desc: 'Every course recommendation comes with a grounded AI explanation: your exact current level, the target level, and why this course was chosen at this position in the sequence.',
      icon: '🧠',
    },
  ]

  const stats = [
    { value: '55', label: 'Skills in DAG', sub: 'across 8 domains' },
    { value: '43', label: 'Curated Courses', sub: 'free-to-access' },
    { value: '0%', label: 'Hallucination Rate', sub: 'on catalog skills' },
    { value: '100%', label: 'Topo Sort Accuracy', sub: 'zero prerequisite violations' },
  ]

  const domains = [
    { name: 'Software Engineering', icon: '💻', color: '#bfff00' },
    { name: 'Data Science & ML', icon: '📊', color: '#bfff00' },
    { name: 'DevOps & Cloud', icon: '☁️', color: '#ff5f00' },
    { name: 'HR & People Ops', icon: '👥', color: '#ff5f00' },
    { name: 'Finance & Accounting', icon: '💰', color: '#ff00ff' },
    { name: 'Operations & Supply Chain', icon: '🏭', color: '#ff00ff' },
    { name: 'Healthcare Operations', icon: '🏥', color: '#bfff00' },
    { name: 'Customer Service & Sales', icon: '🤝', color: '#ff5f00' },
  ]

  return (
    <div className="overflow-x-hidden">

      {/* ── HERO ─────────────────────────────────────────────────── */}
      <section className="relative min-h-screen flex flex-col justify-center px-6 pt-24 pb-20 max-w-7xl mx-auto">
        {/* Decorative corner marks */}
        <div className="absolute top-8 left-6 text-[#bfff00]/20 font-mono text-[10px] uppercase tracking-widest select-none">
          PATHFORGE // V2.0_INDUSTRIAL
        </div>
        <div className="absolute top-8 right-6 text-white/10 font-mono text-[10px] uppercase tracking-widest select-none">
          AI-ADAPTIVE ONBOARDING ENGINE
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          {/* Left: copy */}
          <div>
            <div className="inline-block px-3 py-1 bg-[#bfff00]/10 border border-[#bfff00]/30 text-[#bfff00] text-[10px] font-black uppercase tracking-widest mb-8">
              ◉ System_Operational — ARTPARK CodeForge Hackathon Submission
            </div>

            <h1 className="text-7xl lg:text-8xl font-black text-white italic tracking-tighter uppercase leading-[0.85] mb-8">
              Stop<br/>
              <span className="text-[#bfff00]">Wasting</span><br/>
              Training<br/>
              Time.
            </h1>

            <p className="text-xl text-white/50 font-medium leading-relaxed max-w-lg mb-10">
              PathForge parses your résumé, reads the job description, and builds the{' '}
              <span className="text-white font-bold">minimum effective learning sequence</span>{' '}
              to close your exact skill gaps — automatically. No generic curricula. No wasted hours.
            </p>

            <div className="flex flex-wrap gap-4 items-center">
              <button
                onClick={onStart}
                className="neo-button text-xl px-10 py-5"
              >
                FORGE MY PATHWAY →
              </button>
              <div className="text-[10px] font-mono text-white/30 uppercase leading-relaxed">
                Upload a résumé + JD<br/>
                Get your pathway in ~10s
              </div>
            </div>
          </div>

          {/* Right: animated stat boxes */}
          <div className="grid grid-cols-2 gap-4">
            {stats.map((s) => (
              <div key={s.value} className="neo-card p-8 bg-black flex flex-col justify-between min-h-[140px]">
                <div className="text-[9px] font-black text-white/20 uppercase tracking-[0.3em]">{s.label}</div>
                <div>
                  <div className="text-5xl font-black text-[#bfff00] leading-none">{s.value}</div>
                  <div className="text-[10px] font-mono text-white/30 mt-2 uppercase">{s.sub}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Scroll hint */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-white/20 animate-bounce">
          <div className="w-[1px] h-10 bg-white/20"></div>
          <span className="text-[9px] font-mono uppercase tracking-widest">Scroll</span>
        </div>
      </section>

      {/* ── THE PROBLEM ───────────────────────────────────────────── */}
      <section className="border-t-2 border-white/5 px-6 py-24">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <div>
              <div className="text-[10px] font-black text-[#ff5f00] uppercase tracking-widest mb-4">The Problem</div>
              <h2 className="text-5xl font-black text-white italic uppercase tracking-tighter leading-tight mb-8">
                One-Size-Fits-All<br/>
                <span className="text-[#ff5f00]">Onboarding is Broken</span>
              </h2>
              <div className="space-y-6 text-white/50 font-medium leading-relaxed">
                <p>
                  A senior engineer and a fresh graduate get the same 80-hour onboarding curriculum.
                  The senior wastes 60 hours on content they already know. The junior is overwhelmed by
                  advanced modules with no foundation under them.
                </p>
                <p>
                  Both outcomes hurt the business:{' '}
                  <span className="text-white">wasted salary hours</span> on one side,{' '}
                  <span className="text-white">failed ramp-ups</span> on the other.
                </p>
              </div>
            </div>
            <div className="space-y-4">
              {[
                { label: 'Time wasted by over-qualified hires', pct: 75, color: '#ff5f00' },
                { label: 'Beginners overwhelmed by advanced modules', pct: 62, color: '#ff00ff' },
                { label: 'Training sessions with zero skill gap coverage', pct: 41, color: '#ffffff' },
              ].map(bar => (
                <div key={bar.label} className="neo-card p-6 bg-[#0d0d10]">
                  <div className="flex justify-between items-center mb-3">
                    <span className="text-xs font-bold text-white/50 uppercase tracking-wide">{bar.label}</span>
                    <span className="font-black text-white font-mono">{bar.pct}%</span>
                  </div>
                  <div className="h-2 bg-white/5 w-full">
                    <div
                      className="h-full transition-all duration-1000"
                      style={{ width: `${bar.pct}%`, background: bar.color }}
                    />
                  </div>
                </div>
              ))}
              <div className="text-[9px] font-mono text-white/20 uppercase text-right">
                Source: Corporate training efficiency survey
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ─────────────────────────────────────────── */}
      <section className="border-t-2 border-white/5 px-6 py-24 bg-[#060608]">
        <div className="max-w-7xl mx-auto">
          <div className="mb-16 flex items-end justify-between flex-wrap gap-6">
            <div>
              <div className="text-[10px] font-black text-[#bfff00] uppercase tracking-widest mb-4">How It Works</div>
              <h2 className="text-5xl font-black text-white italic uppercase tracking-tighter leading-tight">
                The <span className="text-[#bfff00]">4-Stage</span> Pipeline
              </h2>
            </div>
            <div className="text-[10px] font-mono text-white/20 uppercase max-w-xs text-right">
              Every stage is deterministic and auditable. No black boxes.
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
            {steps.map((step, i) => (
              <div key={step.num} className="neo-card p-8 bg-[#0d0d10] flex flex-col gap-6 relative overflow-hidden">
                {/* Background number watermark */}
                <div
                  className="absolute -top-4 -right-2 text-[120px] font-black select-none pointer-events-none"
                  style={{ color: step.color, opacity: 0.04 }}
                >
                  {step.num}
                </div>

                <div className="flex items-start justify-between">
                  <span
                    className="text-[10px] font-black uppercase tracking-widest px-2 py-1 border"
                    style={{ color: step.color, borderColor: `${step.color}40`, background: `${step.color}10` }}
                  >
                    Step {step.num}
                  </span>
                  <span className="text-3xl">{step.icon}</span>
                </div>

                <div>
                  <h3 className="text-xl font-black text-white uppercase tracking-tight mb-3">{step.label}</h3>
                  <p className="text-sm text-white/40 font-medium leading-relaxed">{step.desc}</p>
                </div>

                {i < steps.length - 1 && (
                  <div
                    className="absolute -right-3 top-1/2 -translate-y-1/2 text-2xl font-black hidden xl:block"
                    style={{ color: step.color, opacity: 0.5 }}
                  >
                    →
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── TECH STACK ───────────────────────────────────────────── */}
      <section className="border-t-2 border-white/5 px-6 py-24">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-16">
            <div className="lg:col-span-1">
              <div className="text-[10px] font-black text-[#ff00ff] uppercase tracking-widest mb-4">Under the Hood</div>
              <h2 className="text-4xl font-black text-white italic uppercase tracking-tighter leading-tight mb-6">
                Groq-Powered<br/><span className="text-[#ff00ff]">Architecture</span>
              </h2>
              <p className="text-white/40 font-medium leading-relaxed text-sm">
                One fast LLM — Groq Llama-3.3-70B — handles all three LLM tasks: skill extraction, reasoning traces, and dynamic course discovery. The algorithmic core — gap computation, DAG traversal, topological sort — is pure Python: deterministic, zero-latency, unit-tested.
              </p>
            </div>

            <div className="lg:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-4">
              {[
                { layer: 'Extraction LLM', tool: 'Groq Llama-3.3-70B', sub: 'Skill extraction with allowlist enforcement', color: '#bfff00' },
                { layer: 'Reasoning LLM', tool: 'Groq Llama-3.3-70B', sub: 'Fast traces + dynamic discovery', color: '#ff00ff' },
                { layer: 'Gap Algorithm', tool: 'Pure Python', sub: 'Deterministic BFS + delta sort', color: '#ff5f00' },
                { layer: 'Pathway Sort', tool: "Kahn's Topological Sort", sub: 'Dependency-safe ordering', color: '#bfff00' },
                { layer: 'Backend', tool: 'FastAPI + Pydantic v2', sub: 'Async REST, schema-validated', color: '#ff5f00' },
                { layer: 'Frontend', tool: 'React 18 + Vite 6', sub: 'pdf.js + mammoth.js parsing', color: '#ff00ff' },
                { layer: 'Skill Taxonomy', tool: '55-Node Skills DAG', sub: 'O*NET-aligned hierarchy', color: '#bfff00' },
                { layer: 'Deployment', tool: 'Docker + Compose', sub: 'One-command setup', color: '#ff5f00' },
              ].map(item => (
                <div key={item.layer} className="neo-card p-5 bg-[#0d0d10]">
                  <div className="text-[9px] font-black uppercase tracking-widest mb-1" style={{ color: item.color }}>
                    {item.layer}
                  </div>
                  <div className="font-black text-white text-sm uppercase tracking-tight">{item.tool}</div>
                  <div className="text-[10px] font-mono text-white/30 mt-1">{item.sub}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── CROSS-DOMAIN ─────────────────────────────────────────── */}
      <section className="border-t-2 border-white/5 px-6 py-24 bg-[#060608]">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <div className="text-[10px] font-black text-[#ff5f00] uppercase tracking-widest mb-4">Cross-Domain Scalability</div>
            <h2 className="text-5xl font-black text-white italic uppercase tracking-tighter">
              Not Just for <span className="text-[#ff5f00]">Developers</span>
            </h2>
            <p className="text-white/30 mt-4 font-mono text-sm max-w-xl mx-auto">
              PathForge covers 8 professional domains — from ML engineers to warehouse ops managers.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {domains.map(d => (
              <div key={d.name} className="neo-card p-6 bg-[#0d0d10] text-center flex flex-col items-center gap-3">
                <span className="text-4xl">{d.icon}</span>
                <span className="text-xs font-black text-white uppercase tracking-tight leading-tight">{d.name}</span>
                <div className="w-8 h-[2px]" style={{ background: d.color }}></div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FINAL CTA ────────────────────────────────────────────── */}
      <section className="border-t-2 border-white/5 px-6 py-32">
        <div className="max-w-4xl mx-auto text-center">
          <div className="text-[10px] font-black text-[#bfff00] uppercase tracking-widest mb-6">Ready?</div>
          <h2 className="text-6xl lg:text-7xl font-black text-white italic uppercase tracking-tighter leading-[0.85] mb-10">
            Build Your<br/>
            <span className="text-[#bfff00]">Personalised</span><br/>
            Pathway Now
          </h2>
          <p className="text-white/40 text-lg mb-12 font-medium max-w-xl mx-auto">
            Upload your résumé and the job description. In about 10 seconds, you'll have a dependency-safe, cognitively-balanced, time-budgeted learning roadmap built specifically for you.
          </p>
          <button
            onClick={onStart}
            className="neo-button text-2xl px-14 py-6"
          >
            INITIALIZE SYNTHESIS →
          </button>
          <div className="mt-8 text-[10px] font-mono text-white/20 uppercase tracking-widest">
            Supports PDF · DOCX · TXT · Plain text paste
          </div>
        </div>
      </section>

    </div>
  )
}

import { useState } from 'react'
import LandingPage from './LandingPage'
import UploadPage from './UploadPage'
import PathwayPage from './PathwayPage'

function App() {
  // 3 states: 'landing' → 'upload' → 'results'
  const [screen, setScreen] = useState('landing')
  const [pathwayData, setPathwayData] = useState(null)

  const handleComplete = (data) => {
    setPathwayData(data)
    setScreen('results')
  }

  const handleReset = () => {
    setPathwayData(null)
    setScreen('landing')
  }

  return (
    <div className="min-h-screen bg-[#0a0a0c] selection:bg-[#bfff00] selection:text-black">
      <header className="border-b-[3px] border-white/10 bg-[#0a0a0c] sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          {/* Logo — always navigates back to landing */}
          <button
            onClick={handleReset}
            className="flex items-center gap-4 group"
          >
            <div className="w-10 h-10 bg-[#bfff00] flex items-center justify-center border-2 border-black shadow-[4px_4px_0px_#ffffff20] group-hover:shadow-[4px_4px_0px_#ff5f00] transition-all">
              <span className="text-black font-black text-lg">PF</span>
            </div>
            <h1 className="text-2xl font-black tracking-tighter uppercase text-white">
              Path<span className="text-[#bfff00]">Forge</span>
              <span className="ml-2 text-[10px] font-mono text-white/30 tracking-widest border border-white/10 px-2 py-1">V2.0_INDUSTRIAL</span>
            </h1>
          </button>

          {/* Nav actions */}
          <div className="flex items-center gap-4">
            {screen === 'landing' && (
              <button
                onClick={() => setScreen('upload')}
                className="neo-button py-2 px-6 text-sm"
              >
                LAUNCH APP →
              </button>
            )}
            {(screen === 'upload' || screen === 'results') && (
              <>
                {screen === 'results' && (
                  <button
                    onClick={() => setScreen('upload')}
                    className="px-5 py-2 border border-white/10 text-white/50 font-black text-xs uppercase tracking-tighter hover:border-white/30 hover:text-white transition-all"
                  >
                    NEW_ANALYSIS
                  </button>
                )}
                <button
                  onClick={handleReset}
                  className="neo-button py-2 px-6 text-sm"
                >
                  HOME
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      <main>
        {screen === 'landing' && (
          <LandingPage onStart={() => setScreen('upload')} />
        )}
        {screen === 'upload' && (
          <UploadPage onComplete={handleComplete} />
        )}
        {screen === 'results' && (
          <PathwayPage data={pathwayData} />
        )}
      </main>
    </div>
  )
}

export default App

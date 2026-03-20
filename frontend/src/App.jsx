import { useState } from 'react'
import UploadPage from './UploadPage'
import PathwayPage from './PathwayPage'

function App() {
  const [pathwayData, setPathwayData] = useState(null)

  return (
    <div className="min-h-screen">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded bg-blue-600 flex items-center justify-center">
              <span className="text-white font-bold text-sm">PF</span>
            </div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-blue-700 to-indigo-600 bg-clip-text text-transparent">
              PathForge
            </h1>
          </div>
          {pathwayData && (
            <button
              onClick={() => setPathwayData(null)}
              className="text-sm text-slate-500 hover:text-slate-900 font-medium"
            >
              Start Over
            </button>
          )}
        </div>
      </header>

      <main>
        {!pathwayData ? (
          <UploadPage onComplete={setPathwayData} />
        ) : (
          <PathwayPage data={pathwayData} />
        )}
      </main>
    </div>
  )
}

export default App

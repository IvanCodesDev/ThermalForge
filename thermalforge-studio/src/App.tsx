import { useEffect, useReducer, useState } from 'react'
import { AppShell } from './components/AppShell'
import { ConstraintsPage } from './pages/ConstraintsPage'
import { DashboardPage } from './pages/DashboardPage'
import { HardwarePage } from './pages/HardwarePage'
import { ReportPage } from './pages/ReportPage'
import { ResultsPage } from './pages/ResultsPage'
import { ScenarioPage } from './pages/ScenarioPage'
import { StructuresPage } from './pages/StructuresPage'
import {
  createDefaultProjectState,
  loadProjectState,
  projectReducer,
  saveProjectState,
} from './state/projectState'
import type { StepId } from './state/projectState'
import './App.css'

function App() {
  const [state, dispatch] = useReducer(
    projectReducer,
    createDefaultProjectState(),
    () =>
      typeof window === 'undefined'
        ? createDefaultProjectState()
        : loadProjectState(window.localStorage),
  )
  const [savedAt, setSavedAt] = useState('草稿已加载')

  useEffect(() => {
    saveProjectState(window.localStorage, state)
    setSavedAt(
      new Date().toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
      }),
    )
  }, [state])

  const navigate = (step: StepId) => {
    dispatch({ type: 'setStep', step })
    const content = document.getElementById('main-content')
    if (content) {
      content.scrollTop = 0
    }
  }

  const pageProps = { state, dispatch, onNavigate: navigate }

  const renderPage = () => {
    switch (state.currentStep) {
      case 'dashboard':
        return <DashboardPage {...pageProps} />
      case 'scenario':
        return <ScenarioPage {...pageProps} />
      case 'hardware':
        return <HardwarePage {...pageProps} />
      case 'constraints':
        return <ConstraintsPage {...pageProps} />
      case 'structures':
        return <StructuresPage {...pageProps} />
      case 'results':
        return <ResultsPage {...pageProps} />
      case 'report':
        return <ReportPage {...pageProps} />
    }
  }

  return (
    <AppShell
      currentStep={state.currentStep}
      savedAt={savedAt}
      onNavigate={navigate}
    >
      {renderPage()}
    </AppShell>
  )
}

export default App

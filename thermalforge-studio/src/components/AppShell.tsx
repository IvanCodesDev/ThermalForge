import {
  BarChart3,
  Box,
  ChevronDown,
  CloudCheck,
  Cpu,
  FileText,
  Hexagon,
  LayoutDashboard,
  PanelsTopLeft,
  SlidersHorizontal,
} from 'lucide-react'
import type { ReactNode } from 'react'
import type { StepId } from '../state/projectState'

interface AppShellProps {
  currentStep: StepId
  savedAt: string
  onNavigate: (step: StepId) => void
  children: ReactNode
}

const STEP_NAVIGATION = [
  {
    id: 'dashboard',
    label: '项目总览',
    icon: LayoutDashboard,
  },
  {
    id: 'scenario',
    label: '场景预选',
    icon: PanelsTopLeft,
  },
  {
    id: 'hardware',
    label: '硬件热源',
    icon: Cpu,
  },
  {
    id: 'constraints',
    label: '安装约束',
    icon: SlidersHorizontal,
  },
  {
    id: 'structures',
    label: '结构生成',
    icon: Box,
  },
  {
    id: 'results',
    label: '性能对比',
    icon: BarChart3,
  },
  {
    id: 'report',
    label: '报告导出',
    icon: FileText,
  },
] satisfies ReadonlyArray<{
  id: StepId
  label: string
  icon: typeof LayoutDashboard
}>

export function AppShell({
  currentStep,
  savedAt,
  onNavigate,
  children,
}: AppShellProps) {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>

      <header className="app-header">
        <div className="brand">
          <button
            className="brand-home"
            type="button"
            onClick={() => onNavigate('dashboard')}
            aria-label="返回项目总览"
          >
            <Hexagon aria-hidden="true" />
          </button>
          <div>
            <h1>ThermalForge Studio</h1>
            <small>Robot Thermal Intelligence</small>
          </div>
        </div>

        <nav className="capsule-navigation" aria-label="项目工作流">
          {STEP_NAVIGATION.map((step, index) => {
            const Icon = step.icon
            const active = currentStep === step.id

            return (
              <button
                key={step.id}
                type="button"
                className={active ? 'nav-step is-active' : 'nav-step'}
                aria-current={active ? 'step' : undefined}
                onClick={() => onNavigate(step.id)}
              >
                <Icon aria-hidden="true" />
                <span>{step.label}</span>
                <small>{String(index + 1).padStart(2, '0')}</small>
              </button>
            )
          })}
        </nav>

        <div className="profile-pill">
          <span className="profile-avatar">TF</span>
          <span className="profile-copy">
            <strong>演示项目</strong>
            <small>
              <CloudCheck aria-hidden="true" />
              {savedAt}
            </small>
          </span>
          <ChevronDown aria-hidden="true" />
        </div>
      </header>

      <main id="main-content" className="app-content" tabIndex={-1}>
        {children}
      </main>

      <div className="bottom-ambient-glow" aria-hidden="true" />
    </div>
  )
}

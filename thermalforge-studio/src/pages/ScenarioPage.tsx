import {
  Bot,
  Check,
  Grab,
  Route,
  ShieldPlus,
  Trophy,
} from 'lucide-react'
import { PageHeader } from '../components/PageHeader'
import { WorkflowFooter } from '../components/WorkflowFooter'
import { SCENARIOS } from '../data/content'
import type { WorkflowPageProps } from '../types'

const SCENARIO_ICONS = {
  'humanoid-rescue': ShieldPlus,
  'quadruped-patrol': Route,
  'robotic-arm': Grab,
  'university-team': Trophy,
} as const

export function ScenarioPage({
  state,
  dispatch,
  onNavigate,
}: WorkflowPageProps) {
  return (
    <div className="page">
      <PageHeader
        eyebrow="Mission profile · 02"
        title="选择任务场景"
        description="先定义机器人所处的任务冲突，系统将据此预设负载、持续时间与重点关注的热风险。"
        aside={
          <div className="selection-summary">
            <Bot aria-hidden="true" />
            <span>
              当前场景
              <strong>
                {SCENARIOS.find((item) => item.id === state.scenarioId)?.title}
              </strong>
            </span>
          </div>
        }
      />

      <section className="scenario-grid" aria-label="可选任务场景">
        {SCENARIOS.map((scenario, index) => {
          const selected = state.scenarioId === scenario.id
          const Icon =
            SCENARIO_ICONS[scenario.id as keyof typeof SCENARIO_ICONS]

          return (
            <button
              key={scenario.id}
              type="button"
              className={
                selected ? 'scenario-card is-selected' : 'scenario-card'
              }
              aria-pressed={selected}
              onClick={() =>
                dispatch({
                  type: 'selectScenario',
                  scenarioId: scenario.id,
                })
              }
            >
              <div className="glow-bg" aria-hidden="true" />
              <div className="scenario-card-top">
                <span className="scenario-index">
                  {String(index + 1).padStart(2, '0')}
                </span>
                {scenario.id === 'humanoid-rescue' ? (
                  <span className="recommended-chip">路演推荐</span>
                ) : (
                  <span className="scenario-code">{scenario.code}</span>
                )}
              </div>

              <span className="scenario-icon">
                <Icon aria-hidden="true" />
              </span>
              <h3>{scenario.title}</h3>
              <p>{scenario.description}</p>

              <div className="scenario-problems">
                <span>典型问题</span>
                <ul>
                  {scenario.problems.map((problem) => (
                    <li key={problem}>
                      <i aria-hidden="true" />
                      {problem}
                    </li>
                  ))}
                </ul>
              </div>

              <span className="selection-indicator">
                <Check aria-hidden="true" />
                <span className="selection-label">
                  {selected ? '已选中' : '选择场景'}
                </span>
              </span>
            </button>
          )
        })}
      </section>

      <aside className="context-tip">
        <ShieldPlus aria-hidden="true" />
        <div>
          <strong>为什么默认选择救援任务？</strong>
          <p>
            负重、爬坡和持续站立会同时放大热积累与任务中断风险，冲突最清晰，也最适合在路演中展示诊断前后的量化差异。
          </p>
        </div>
      </aside>

      <WorkflowFooter
        previousLabel="返回项目总览"
        nextLabel="配置硬件与热源"
        onPrevious={() => onNavigate('dashboard')}
        onNext={() => onNavigate('hardware')}
      />
    </div>
  )
}

import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Check,
  GripVertical,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import { WorkflowFooter } from '../components/WorkflowFooter'
import { CONSTRAINTS, OPTIMIZATION_GOALS } from '../data/content'
import type { WorkflowPageProps } from '../types'

export function ConstraintsPage({
  state,
  dispatch,
  onNavigate,
}: WorkflowPageProps) {
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null)

  return (
    <div className="page">
      <PageHeader
        eyebrow="Engineering constraints · 04"
        title="设置安装约束与优化目标"
        description="系统只在明确的安全、维护和运动边界内生成结构，避免把热设计退化为简单堆叠散热片。"
        aside={
          <div className="constraint-count">
            <ShieldCheck aria-hidden="true" />
            <span>
              已启用约束
              <strong>{state.constraints.length} 项</strong>
            </span>
          </div>
        }
      />

      <div className="constraint-layout">
        <section className="form-panel constraint-panel">
          <div className="glow-bg" aria-hidden="true" />
          <div className="panel-heading">
            <span className="panel-step">01</span>
            <div>
              <h3>安装约束</h3>
              <p>点击开关启用或取消工程限制</p>
            </div>
          </div>

          <div className="constraint-grid">
            {CONSTRAINTS.map((constraint) => {
              const selected = state.constraints.includes(constraint.id)
              return (
                <button
                  key={constraint.id}
                  type="button"
                  role="switch"
                  aria-checked={selected}
                  className={
                    selected ? 'constraint-switch is-active' : 'constraint-switch'
                  }
                  onClick={() =>
                    dispatch({
                      type: 'toggleConstraint',
                      constraintId: constraint.id,
                    })
                  }
                >
                  <span className="switch-control">
                    <i>
                      <Check aria-hidden="true" />
                    </i>
                  </span>
                  <span>{constraint.label}</span>
                </button>
              )
            })}
          </div>

          <div className="weight-limit-card">
            <span>
              <strong>质量预算</strong>
              <small>推荐范围：原关节质量的 5%–10%</small>
            </span>
            <div>
              <b>≤ 8%</b>
              <i>
                <span style={{ width: '68%' }} />
              </i>
            </div>
          </div>
        </section>

        <section className="form-panel goal-panel">
          <div className="glow-bg" aria-hidden="true" />
          <div className="panel-heading">
            <span className="panel-step">02</span>
            <div>
              <h3>优化目标优先级</h3>
              <p>拖拽排序，也可使用右侧上下按钮</p>
            </div>
          </div>

          <ol className="goal-list">
            {state.optimizationGoals.map((goalId, index) => {
              const goal = OPTIMIZATION_GOALS.find(
                (item) => item.id === goalId,
              )
              if (!goal) {
                return null
              }

              return (
                <li
                  key={goal.id}
                  className={
                    draggedIndex === index ? 'goal-row is-dragging' : 'goal-row'
                  }
                  draggable
                  onDragStart={() => setDraggedIndex(index)}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={() => {
                    if (draggedIndex !== null) {
                      dispatch({
                        type: 'moveGoal',
                        fromIndex: draggedIndex,
                        toIndex: index,
                      })
                    }
                    setDraggedIndex(null)
                  }}
                  onDragEnd={() => setDraggedIndex(null)}
                >
                  <GripVertical aria-hidden="true" />
                  <span className="goal-rank">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <span className="goal-name">{goal.label}</span>
                  <span className="goal-priority">
                    {index === 0 ? '最高优先' : index < 4 ? '核心' : '次要'}
                  </span>
                  <span className="goal-move-actions">
                    <button
                      type="button"
                      disabled={index === 0}
                      aria-label={`上移${goal.label}`}
                      onClick={() =>
                        dispatch({
                          type: 'moveGoal',
                          fromIndex: index,
                          toIndex: index - 1,
                        })
                      }
                    >
                      <ArrowUp aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      disabled={index === state.optimizationGoals.length - 1}
                      aria-label={`下移${goal.label}`}
                      onClick={() =>
                        dispatch({
                          type: 'moveGoal',
                          fromIndex: index,
                          toIndex: index + 1,
                        })
                      }
                    >
                      <ArrowDown aria-hidden="true" />
                    </button>
                  </span>
                </li>
              )
            })}
          </ol>
        </section>
      </div>

      <aside className="system-recommendation">
        <span className="recommendation-icon">
          <Sparkles aria-hidden="true" />
        </span>
        <div>
          <span className="section-kicker">System constraint insight</span>
          <h3>当前约束下的结构建议</h3>
          <p>
            系统优先推荐可逆导热桥、导热内衬和低矮叶脉热扩散结构。它们可以避开线束与轴承座，并保持结构可拆卸。
          </p>
        </div>
        <div className="not-recommended">
          <AlertTriangle aria-hidden="true" />
          <span>
            <strong>暂不推荐微通道液冷</strong>
            维护与可靠性风险较高
          </span>
        </div>
      </aside>

      <WorkflowFooter
        previousLabel="返回硬件热源"
        nextLabel="生成候选结构"
        onPrevious={() => onNavigate('hardware')}
        onNext={() => onNavigate('structures')}
      />
    </div>
  )
}

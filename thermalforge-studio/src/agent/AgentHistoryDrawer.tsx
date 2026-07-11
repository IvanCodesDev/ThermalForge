import { X } from 'lucide-react'
import { useState } from 'react'
import type { TaskImageManifest } from '../api'
import type { ViewerManifest } from '../model/viewerManifest'
import type { AgentMessage } from './agentTypes'
import { MOCK_STAGES } from './mockPipeline'
import { toDisplayTaskImages } from './taskImages'
import {
  collectTaskEvidence,
  serializeTaskResults,
  type TaskResultBundle,
} from './taskResults'

interface AgentHistoryDrawerProps {
  isOpen: boolean
  messages: AgentMessage[]
  currentStageId: string
  results: TaskResultBundle | null
  resultsError: string | null
  resultsLoading: boolean
  imageManifest: TaskImageManifest | null
  imagesError: string | null
  imagesLoading: boolean
  viewerManifest: ViewerManifest | null
  onRetryResults: () => void
  onRetryImages: () => void
  onClose: () => void
}

export function AgentHistoryDrawer({
  isOpen,
  messages,
  currentStageId,
  results,
  resultsError,
  resultsLoading,
  imageManifest,
  imagesError,
  imagesLoading,
  viewerManifest,
  onRetryResults,
  onRetryImages,
  onClose,
}: AgentHistoryDrawerProps) {
  const [activeTab, setActiveTab] = useState<
    'conversation' | 'evidence' | 'images' | 'output'
  >('conversation')
  const design = results?.thermalDesign
  const evidence = results ? collectTaskEvidence(results) : []
  const images = toDisplayTaskImages(imageManifest)

  if (!isOpen) {
    return null
  }

  return (
    <section
      className="history-drawer"
      role="dialog"
      aria-label="完整对话"
      aria-modal="false"
    >
      <div className="history-drawer-header">
        <div>
          <span className="eyebrow">SESSION TRACE</span>
          <h2>完整过程</h2>
        </div>
        <button type="button" aria-label="关闭完整对话" onClick={onClose}>
          <X aria-hidden="true" />
        </button>
      </div>

      <nav className="history-tabs" aria-label="过程视图">
        {[
          ['conversation', '对话'],
          ['evidence', '设计依据'],
          ['images', '概念图'],
          ['output', '后端输出'],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            aria-pressed={activeTab === id}
            onClick={() =>
              setActiveTab(
                id as 'conversation' | 'evidence' | 'images' | 'output',
              )
            }
          >
            {label}
          </button>
        ))}
      </nav>

      {activeTab === 'conversation' ? (
        <div className="history-content">
          <ol className="stage-rail" aria-label="生成阶段">
            {MOCK_STAGES.map((stage) => {
              const currentIndex = MOCK_STAGES.findIndex(
                (candidate) => candidate.id === currentStageId,
              )
              const stageIndex = MOCK_STAGES.indexOf(stage)
              const state =
                stage.id === currentStageId
                  ? 'current'
                  : stageIndex < currentIndex
                    ? 'complete'
                    : 'pending'

              return (
                <li className={`is-${state}`} key={stage.id}>
                  <span aria-hidden="true" />
                  {stage.label}
                </li>
              )
            })}
          </ol>

          <div className="history-messages">
            {messages.map((message) => (
              <article
                className={`history-message is-${message.role}`}
                key={message.id}
              >
                <span>
                  {message.role === 'agent' ? 'THERMALFORGE' : '你'}
                </span>
                <p>{message.content}</p>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      {activeTab === 'evidence' ? (
        <div className="history-evidence">
          {results ? (
            <>
              {design ? (
                <>
                  <div className="evidence-heading">
                    <span className="eyebrow">SELECTED SOLUTION</span>
                    <h3>{design.selected_solution.title}</h3>
                    <p>{design.rationale}</p>
                  </div>

                  <dl className="evidence-metrics">
                    <div>
                      <dt>基线峰值</dt>
                      <dd>{design.baseline_max_temperature_c} °C</dd>
                    </div>
                    <div>
                      <dt>方案峰值</dt>
                      <dd>{design.selected_solution.max_temperature_c} °C</dd>
                    </div>
                    <div>
                      <dt>热点改善</dt>
                      <dd>{design.selected_solution.hotspot_reduction_c} °C</dd>
                    </div>
                  </dl>

                  <section>
                    <h4>热传递路径</h4>
                    <p>{design.heat_transfer_path.join(' → ')}</p>
                  </section>

                  <section>
                    <h4>推荐材料</h4>
                    <ul>
                      {design.material_recommendations.map((material) => (
                        <li key={material}>{material}</li>
                      ))}
                    </ul>
                  </section>
                </>
              ) : null}

              {evidence.length > 0 ? (
                <section>
                  <h4>原始证据</h4>
                  <ul className="evidence-quotes">
                    {evidence.map((item) => (
                      <li key={item.id}>
                        <strong>{item.label}</strong>
                        <q>{item.quote}</q>
                        <span>{item.source}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}

              {(results.engineeringBrief?.assumptions?.length ?? 0) > 0 ? (
                <section>
                  <h4>工程假设</h4>
                  <ul>
                    {results.engineeringBrief?.assumptions?.map((assumption) => (
                      <li key={`${assumption.statement}:${assumption.reason}`}>
                        <strong>
                          {assumption.statement} · {assumption.impact}
                        </strong>
                        <span>{assumption.reason}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}

              {(results.thermalAnalysis?.warnings.length ?? 0) > 0 ? (
                <section>
                  <h4>分析警告</h4>
                  <ul>
                    {results.thermalAnalysis?.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                </section>
              ) : null}

              {design ? (
                <section>
                  <h4>风险与验证</h4>
                  <ul>
                    {design.risks.map((risk) => (
                      <li key={`${risk.source}:${risk.description}`}>
                        <strong>{risk.description}</strong>
                        <span>
                          影响：{risk.impact ?? '未标注'} · 来源：
                          {risk.source ?? '未标注'} ·{' '}
                          {risk.recommended_action}
                        </span>
                      </li>
                    ))}
                    {design.unverified_items.map((item) => (
                      <li key={item}>
                        <strong>{item}</strong>
                        <span>需要后续工程验证</span>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}

              {resultsError ? (
                <div className="history-load-error" role="alert">
                  <span>部分结果加载失败：{resultsError}</span>
                  <button
                    type="button"
                    onClick={onRetryResults}
                    disabled={resultsLoading}
                  >
                    {resultsLoading ? '正在重试…' : '重新加载结果'}
                  </button>
                </div>
              ) : null}

              {(viewerManifest?.notices ?? []).map((notice) => (
                <p className="evidence-notice" key={notice}>
                  {notice}
                </p>
              ))}
            </>
          ) : (
            <div className="history-empty">
              <p>
                {resultsError
                  ? `结果加载失败：${resultsError}`
                  : resultsLoading
                    ? '正在加载工程依据…'
                    : '热分析完成后将在这里显示可追溯的设计依据。'}
              </p>
              {resultsError ? (
                <button
                  type="button"
                  onClick={onRetryResults}
                  disabled={resultsLoading}
                >
                  {resultsLoading ? '正在重试…' : '重新加载结果'}
                </button>
              ) : null}
            </div>
          )}
        </div>
      ) : null}

      {activeTab === 'images' ? (
        <div className="history-images">
          <div className="evidence-heading">
            <span className="eyebrow">GPT Image 2 · 六视图</span>
            <h3>热设计概念图</h3>
            <p>
              {imageManifest?.notice ??
                '生成后将在这里显示母图、四个正交视图与肘关节剖面图。'}
            </p>
          </div>

          {images.length > 0 ? (
            <div className="concept-image-grid">
              {images.map((image) => (
                <figure key={image.artifact_id}>
                  <img
                    src={image.resolvedUrl}
                    alt={image.label}
                    loading="lazy"
                  />
                  <figcaption>
                    <strong>{image.label}</strong>
                    <span>
                      {image.provider_model ?? image.provider ?? '图像模型'}
                    </span>
                  </figcaption>
                </figure>
              ))}
            </div>
          ) : (
            <div className="history-empty">
              <p>
                {imagesError
                  ? `概念图加载失败：${imagesError}`
                  : imagesLoading
                    ? '正在加载六视图概念图…'
                    : '概念图生成完成后将在这里显示。'}
              </p>
            </div>
          )}

          {imagesError ? (
            <div className="history-load-error" role="alert">
              <span>概念图加载失败：{imagesError}</span>
              <button
                type="button"
                onClick={onRetryImages}
                disabled={imagesLoading}
              >
                {imagesLoading ? '正在重试…' : '重新加载概念图'}
              </button>
            </div>
          ) : null}
        </div>
      ) : null}

      {activeTab === 'output' ? (
        <div className="history-output">
          {results ? (
            <>
              {resultsError ? (
                <div className="history-load-error" role="alert">
                  <span>部分结果加载失败：{resultsError}</span>
                  <button
                    type="button"
                    onClick={onRetryResults}
                    disabled={resultsLoading}
                  >
                    {resultsLoading ? '正在重试…' : '重新加载结果'}
                  </button>
                </div>
              ) : null}
              <pre>{serializeTaskResults(results, viewerManifest)}</pre>
            </>
          ) : (
            <div className="history-empty">
              <p>
                {resultsError
                  ? `结果加载失败：${resultsError}`
                  : resultsLoading
                    ? '正在加载后端输出…'
                    : '热分析完成后将在这里显示脱敏后的后端输出。'}
              </p>
              {resultsError ? (
                <button
                  type="button"
                  onClick={onRetryResults}
                  disabled={resultsLoading}
                >
                  {resultsLoading ? '正在重试…' : '重新加载结果'}
                </button>
              ) : null}
            </div>
          )}
        </div>
      ) : null}
    </section>
  )
}

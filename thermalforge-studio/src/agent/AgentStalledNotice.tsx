import { useEffect, useState } from 'react'

export const STALLED_TASK_THRESHOLD_MS = 30_000

interface AgentStalledNoticeProps {
  active: boolean
  progressKey: string
  checking: boolean
  onCheck: () => void
  onCancel: () => void
}

export function AgentStalledNotice({
  active,
  progressKey,
  checking,
  onCheck,
  onCancel,
}: AgentStalledNoticeProps) {
  const [stalled, setStalled] = useState(false)
  const [restartKey, setRestartKey] = useState(0)

  useEffect(() => {
    setStalled(false)
    if (!active) {
      return
    }

    const timer = window.setTimeout(
      () => setStalled(true),
      STALLED_TASK_THRESHOLD_MS,
    )
    return () => window.clearTimeout(timer)
  }, [active, progressKey, restartKey])

  if (!active || !stalled) {
    return null
  }

  return (
    <section className="stalled-task-notice" role="alert">
      <div>
        <strong>这个阶段超过 30 秒没有收到新进展。</strong>
        <span>任务与已上传文件仍然保留，可以重新检查或安全停止。</span>
      </div>
      <div className="stalled-task-actions">
        <button
          type="button"
          disabled={checking}
          aria-label="重新检查任务状态"
          onClick={() => {
            setStalled(false)
            setRestartKey((value) => value + 1)
            onCheck()
          }}
        >
          {checking ? '检查中…' : '重新检查'}
        </button>
        <button
          type="button"
          aria-label="停止无进展任务"
          onClick={onCancel}
        >
          停止任务
        </button>
      </div>
    </section>
  )
}

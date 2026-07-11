import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  AgentStalledNotice,
  STALLED_TASK_THRESHOLD_MS,
} from './AgentStalledNotice'

describe('AgentStalledNotice', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('offers status refresh and cancellation after progress stops', async () => {
    const onCheck = vi.fn()
    const onCancel = vi.fn()
    const { rerender } = render(
      <AgentStalledNotice
        active
        progressKey="task-1:parsing:1"
        checking={false}
        onCheck={onCheck}
        onCancel={onCancel}
      />,
    )

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    await act(() => vi.advanceTimersByTimeAsync(STALLED_TASK_THRESHOLD_MS))
    expect(screen.getByRole('alert')).toHaveTextContent('没有收到新进展')

    fireEvent.click(screen.getByRole('button', { name: '重新检查任务状态' }))
    expect(onCheck).toHaveBeenCalledOnce()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()

    rerender(
      <AgentStalledNotice
        active
        progressKey="task-1:thermal_analysis:2"
        checking={false}
        onCheck={onCheck}
        onCancel={onCancel}
      />,
    )
    await act(() => vi.advanceTimersByTimeAsync(STALLED_TASK_THRESHOLD_MS))
    fireEvent.click(screen.getByRole('button', { name: '停止无进展任务' }))
    expect(onCancel).toHaveBeenCalledOnce()
  })
})

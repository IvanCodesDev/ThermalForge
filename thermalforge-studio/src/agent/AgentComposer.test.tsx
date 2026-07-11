import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AgentComposer } from './AgentComposer'
import { MAX_FILE_SIZE } from './agentFiles'
import type { AgentFile } from './agentTypes'

const baseProps = {
  prompt: '原始设计目标',
  files: [] as AgentFile[],
  status: 'idle' as const,
  inputError: null,
  onPromptChange: vi.fn(),
  onFilesChange: vi.fn(),
  onStart: vi.fn(),
  onCancel: vi.fn(),
}

describe('AgentComposer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('uses an independent answer field while clarification is required', async () => {
    const onAnswerChange = vi.fn()
    const onClarificationSubmit = vi.fn()
    const user = userEvent.setup()
    render(
      <AgentComposer
        {...baseProps}
        clarificationQuestion="允许的最高壳体温度是多少？"
        clarificationAnswer=""
        onClarificationAnswerChange={onAnswerChange}
        onClarificationSubmit={onClarificationSubmit}
      />,
    )

    expect(screen.getByText('允许的最高壳体温度是多少？')).toBeVisible()
    const answer = screen.getByRole('textbox', { name: '补充信息' })
    fireEvent.change(answer, { target: { value: '最高 70 摄氏度' } })
    await user.click(screen.getByRole('button', { name: '提交补充信息' }))

    expect(onAnswerChange).toHaveBeenCalledWith('最高 70 摄氏度')
    expect(baseProps.onPromptChange).not.toHaveBeenCalled()
    expect(onClarificationSubmit).toHaveBeenCalledOnce()
  })

  it('labels the ready-state primary action as a new design', () => {
    render(<AgentComposer {...baseProps} status="ready" />)

    expect(
      screen.getByRole('button', { name: '新建设计' }),
    ).toBeInTheDocument()
  })

  it('labels a failed task action as a retry', () => {
    render(<AgentComposer {...baseProps} status="error" />)

    expect(
      screen.getByRole('button', { name: '重试生成' }),
    ).toBeInTheDocument()
  })

  it('disables the stop action while cancellation is in flight', () => {
    render(
      <AgentComposer
        {...baseProps}
        status="running"
        cancelRequested
      />,
    )

    expect(screen.getByRole('button', { name: '停止生成' })).toBeDisabled()
  })

  it('replaces restored metadata with a newly selected File', async () => {
    const selected = new File(['thermal input'], 'joint-spec.pdf', {
      type: 'application/pdf',
      lastModified: 1234,
    })
    const restored: AgentFile = {
      id: `${selected.name}-${selected.size}-${selected.lastModified}`,
      name: selected.name,
      size: selected.size,
      type: selected.type,
      lastModified: selected.lastModified,
      status: 'failed',
      error: '请重新选择此文件后再上传。',
    }
    const onFilesChange = vi.fn()
    const user = userEvent.setup()
    render(
      <AgentComposer
        {...baseProps}
        files={[restored]}
        onFilesChange={onFilesChange}
      />,
    )

    await user.upload(screen.getByLabelText('上传工程文档'), selected)

    const nextFiles = onFilesChange.mock.calls[0]?.[0] as AgentFile[]
    expect(nextFiles).toHaveLength(1)
    expect(nextFiles[0]).toMatchObject({ status: 'pending', file: selected })
  })

  it('highlights the composer while a workspace file drag is active', () => {
    render(<AgentComposer {...baseProps} isDropActive />)

    expect(screen.getByRole('form', { name: '设计请求输入' })).toHaveAttribute(
      'data-drop-active',
      'true',
    )
  })

  it('rejects an oversized selection without replacing attachments', async () => {
    const onFilesChange = vi.fn()
    const user = userEvent.setup()
    const oversized = new File(['spec'], 'joint-spec.pdf', {
      type: 'application/pdf',
    })
    Object.defineProperty(oversized, 'size', { value: MAX_FILE_SIZE + 1 })
    render(<AgentComposer {...baseProps} onFilesChange={onFilesChange} />)

    await user.upload(screen.getByLabelText('上传工程文档'), oversized)

    expect(screen.getByRole('alert')).toHaveTextContent(
      'joint-spec.pdf 不受支持或超过 20MB',
    )
    expect(onFilesChange).not.toHaveBeenCalled()
  })
})

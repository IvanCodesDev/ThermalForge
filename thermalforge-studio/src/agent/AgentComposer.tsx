import { FileText, Paperclip, Send, Square, X } from 'lucide-react'
import { useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import type { AgentFile, AgentStatus } from './agentTypes'
import { dedupeAgentFiles } from './agentReducer'
import { FILE_INPUT_ACCEPT, selectAgentFiles } from './agentFiles'

interface AgentComposerProps {
  prompt: string
  files: AgentFile[]
  status: AgentStatus
  submitting?: boolean
  cancelRequested?: boolean
  attachmentsLocked?: boolean
  isDropActive?: boolean
  clarificationQuestion?: string | null
  clarificationAnswer?: string
  inputError: string | null
  onPromptChange: (prompt: string) => void
  onClarificationAnswerChange?: (answer: string) => void
  onFilesChange: (files: AgentFile[]) => void
  onStart: () => void
  onClarificationSubmit?: () => void
  onCancel: () => void
}

function getPrimaryActionLabel(
  status: AgentStatus,
  hasClarification: boolean,
): string {
  if (hasClarification) {
    return '提交补充信息'
  }
  if (status === 'cancelled') {
    return '继续生成'
  }
  if (status === 'error') {
    return '重试生成'
  }
  if (status === 'ready') {
    return '新建设计'
  }
  return '开始生成'
}

export function AgentComposer({
  prompt,
  files,
  status,
  submitting = false,
  cancelRequested = false,
  attachmentsLocked = false,
  isDropActive = false,
  clarificationQuestion = null,
  clarificationAnswer = '',
  inputError,
  onPromptChange,
  onClarificationAnswerChange,
  onFilesChange,
  onStart,
  onClarificationSubmit,
  onCancel,
}: AgentComposerProps) {
  const [fileError, setFileError] = useState<string | null>(null)
  const isRunning = status === 'running'
  const isBusy = isRunning || submitting
  const attachmentsDisabled = isBusy || attachmentsLocked
  const hasClarification = Boolean(clarificationQuestion)

  const addFiles = (selectedFiles: File[]) => {
    if (selectedFiles.length === 0) {
      return
    }

    const selection = selectAgentFiles(selectedFiles)
    if (selection.error !== null) {
      setFileError(selection.error)
      return
    }

    setFileError(null)
    onFilesChange(dedupeAgentFiles([...files, ...selection.files]))
  }

  const handleFiles = (event: ChangeEvent<HTMLInputElement>) => {
    addFiles(Array.from(event.target.files ?? []))
    event.target.value = ''
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (hasClarification) {
      onClarificationSubmit?.()
      return
    }
    onStart()
  }

  const removeFile = (fileId: string) => {
    onFilesChange(files.filter((file) => file.id !== fileId))
  }

  return (
    <form
      className="agent-composer"
      aria-label="设计请求输入"
      data-drop-active={isDropActive}
      onSubmit={handleSubmit}
    >
      {clarificationQuestion ? (
        <p className="composer-clarification-question">
          {clarificationQuestion}
        </p>
      ) : null}

      {files.length > 0 ? (
        <div className="composer-files" aria-label="已选择的工程文档">
          {files.map((file) => (
            <span
              className={`composer-file is-${file.status}`}
              data-status={file.status}
              key={file.id}
              title={file.error}
            >
              <FileText aria-hidden="true" />
              <span>{file.name}</span>
              <button
                type="button"
                aria-label={`移除 ${file.name}`}
                onClick={() => removeFile(file.id)}
                disabled={
                  isBusy || attachmentsLocked || file.status === 'uploaded'
                }
              >
                <X aria-hidden="true" />
              </button>
            </span>
          ))}
        </div>
      ) : null}

      <div className="composer-main">
        <label className="file-trigger">
          <Paperclip aria-hidden="true" />
          <input
            type="file"
            aria-label="上传工程文档"
            accept={FILE_INPUT_ACCEPT}
            multiple
            onChange={handleFiles}
            disabled={attachmentsDisabled}
          />
        </label>

        <label
          className="sr-only"
          htmlFor={hasClarification ? 'clarification-answer' : 'design-prompt'}
        >
          {hasClarification ? '补充信息' : '设计目标'}
        </label>
        <textarea
          id={hasClarification ? 'clarification-answer' : 'design-prompt'}
          value={hasClarification ? clarificationAnswer : prompt}
          onChange={(event) =>
            hasClarification
              ? onClarificationAnswerChange?.(event.target.value)
              : onPromptChange(event.target.value)
          }
          placeholder={
            hasClarification
              ? '填写缺失的工程参数或约束…'
              : '描述热问题、安装限制或期望的结构方向…'
          }
          rows={1}
          disabled={isBusy}
        />

        {isRunning ? (
          <button
            className="composer-submit is-stop"
            type="button"
            aria-label="停止生成"
            onClick={onCancel}
            disabled={cancelRequested}
          >
            <Square aria-hidden="true" />
          </button>
        ) : (
          <button
            className="composer-submit"
            type="submit"
            aria-label={getPrimaryActionLabel(status, hasClarification)}
            disabled={submitting}
          >
            <Send aria-hidden="true" />
          </button>
        )}
      </div>

      {fileError || inputError ? (
        <p className="composer-error" role="alert">
          {fileError ?? inputError}
        </p>
      ) : null}
    </form>
  )
}

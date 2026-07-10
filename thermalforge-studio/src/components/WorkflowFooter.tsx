import { ArrowLeft, ArrowRight, CheckCircle2 } from 'lucide-react'

interface WorkflowFooterProps {
  previousLabel?: string
  nextLabel?: string
  onPrevious?: () => void
  onNext?: () => void
}

export function WorkflowFooter({
  previousLabel,
  nextLabel,
  onPrevious,
  onNext,
}: WorkflowFooterProps) {
  return (
    <footer className="workflow-footer">
      <div className="autosave-message" role="status">
        <CheckCircle2 aria-hidden="true" />
        所有选择已自动保存
      </div>

      <div className="workflow-actions">
        {previousLabel && onPrevious ? (
          <button
            className="button button-secondary"
            type="button"
            onClick={onPrevious}
          >
            <ArrowLeft aria-hidden="true" />
            {previousLabel}
          </button>
        ) : null}
        {nextLabel && onNext ? (
          <button
            className="button button-primary"
            type="button"
            onClick={onNext}
          >
            {nextLabel}
            <ArrowRight aria-hidden="true" />
          </button>
        ) : null}
      </div>
    </footer>
  )
}

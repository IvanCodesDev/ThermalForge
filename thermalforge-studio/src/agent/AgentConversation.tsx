import { ChevronUp } from 'lucide-react'
import type { AgentMessage } from './agentTypes'

interface AgentConversationProps {
  messages: AgentMessage[]
  onOpenHistory: () => void
}

export function AgentConversation({
  messages,
  onOpenHistory,
}: AgentConversationProps) {
  return (
    <section
      className="agent-conversation"
      role="log"
      aria-label="最近对话"
      aria-live="polite"
    >
      <button
        className="conversation-history-trigger"
        type="button"
        onClick={onOpenHistory}
      >
        <ChevronUp aria-hidden="true" />
        查看全部对话
      </button>

      <div className="recent-message-list">
        {messages.map((message) => (
          <article
            className={`agent-message is-${message.role}`}
            key={message.id}
          >
            <span className="message-role">
              {message.role === 'agent' ? 'THERMALFORGE' : '你'}
            </span>
            <p>{message.content}</p>
          </article>
        ))}
      </div>
    </section>
  )
}

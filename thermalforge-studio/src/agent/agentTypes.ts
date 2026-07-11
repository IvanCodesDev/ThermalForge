export type AgentStage =
  | 'idle'
  | 'reading'
  | 'briefing'
  | 'thermal'
  | 'multiview'
  | 'modeling'
  | 'ready'

export type AgentStatus = 'idle' | 'running' | 'ready' | 'cancelled' | 'error'

export type AttachmentStatus =
  | 'pending'
  | 'uploading'
  | 'uploaded'
  | 'failed'

export type AgentConnection =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'disconnected'
  | 'error'

export type BackendTaskStatus =
  | 'created'
  | 'uploaded'
  | 'parsing'
  | 'awaiting_input'
  | 'briefing'
  | 'thermal_analysis'
  | 'concept_imaging'
  | 'multiview_imaging'
  | 'multiview_review'
  | 'modeling'
  | 'model_review'
  | 'ready'
  | 'failed'
  | 'cancelled'

export type MessageRole = 'agent' | 'user'

export type ModelPart = string

export interface AgentFile {
  id: string
  name: string
  size: number
  type: string
  lastModified: number
  file?: File
  status: AttachmentStatus
  artifactId?: string
  error?: string
}

export interface AgentMessage {
  id: string
  role: MessageRole
  content: string
  stage?: AgentStage
  sequence: number
}

export interface AgentState {
  status: AgentStatus
  backendStatus: BackendTaskStatus | null
  stage: AgentStage
  progress: number
  submitting: boolean
  startRequested: boolean
  cancelRequested: boolean
  connection: AgentConnection
  taskId: string | null
  projectId: string | null
  idempotencyKey: string | null
  lastEventId: number | null
  clarificationQuestion: string | null
  clarificationAnswer: string
  prompt: string
  files: AgentFile[]
  messages: AgentMessage[]
  messageSequence: number
  inputError: string | null
  isHistoryOpen: boolean
  isExploded: boolean
  selectedPart: ModelPart | null
}

export type AgentAction =
  | { type: 'SET_PROMPT'; prompt: string }
  | { type: 'ADD_FILES'; files: AgentFile[] }
  | { type: 'SET_FILES'; files: AgentFile[] }
  | { type: 'REMOVE_FILE'; fileId: string }
  | { type: 'START' }
  | { type: 'UPLOAD_STARTED'; fileId: string }
  | { type: 'UPLOAD_SUCCEEDED'; fileId: string; artifactId: string }
  | { type: 'UPLOAD_FAILED'; fileId: string; error: string }
  | {
      type: 'SUBMIT_STARTED'
      projectId: string
      idempotencyKey: string
    }
  | {
      type: 'TASK_CREATED'
      taskId: string
      projectId: string
      idempotencyKey: string
    }
  | { type: 'SUBMIT_FAILED'; error: string }
  | { type: 'INPUT_ERROR'; error: string }
  | { type: 'TASK_STARTED'; status: BackendTaskStatus }
  | { type: 'CONNECTION_CHANGED'; connection: AgentConnection }
  | {
      type: 'TASK_STATUS_RECEIVED'
      status: BackendTaskStatus
      lastEventId?: number
      message?: string
    }
  | { type: 'SET_CLARIFICATION_ANSWER'; answer: string }
  | { type: 'CLARIFICATION_RECEIVED'; question: string }
  | { type: 'CLARIFICATION_SUBMIT_STARTED' }
  | { type: 'CLARIFICATION_SUBMITTED' }
  | { type: 'CANCEL_REQUESTED' }
  | { type: 'CANCEL_CONFIRMED'; restartSubmission: boolean }
  | { type: 'CANCEL_FAILED'; error: string }
  | { type: 'CANCEL' }
  | { type: 'TOGGLE_HISTORY' }
  | { type: 'CLOSE_HISTORY' }
  | { type: 'TOGGLE_EXPLODED' }
  | { type: 'SELECT_PART'; part: ModelPart | null }
  | { type: 'RESET' }

export interface MockStage {
  id: Exclude<AgentStage, 'idle'>
  label: string
  message: string
  progress: number
  durationMs: number
}

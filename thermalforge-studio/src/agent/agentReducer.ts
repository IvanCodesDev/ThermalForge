import type {
  AgentAction,
  AgentFile,
  AgentMessage,
  AgentStage,
  AgentState,
  AgentStatus,
  BackendTaskStatus,
  MessageRole,
} from './agentTypes'

export const AGENT_STORAGE_KEY = 'thermalforge.agent-session.v2'

const WELCOME_MESSAGE =
  '把工程文档交给我，再描述你想解决的热问题。我会把方案直接生成到中央模型。'

interface StorageReader {
  getItem: (key: string) => string | null
}

interface StorageWriter {
  setItem: (key: string, value: string) => void
}

interface MappedTaskStatus {
  status: AgentStatus
  stage: AgentStage
  progress: number
}

const BACKEND_TASK_STATUSES: readonly BackendTaskStatus[] = [
  'created',
  'uploaded',
  'parsing',
  'awaiting_input',
  'briefing',
  'thermal_analysis',
  'concept_imaging',
  'multiview_imaging',
  'multiview_review',
  'modeling',
  'model_review',
  'ready',
  'failed',
  'cancelled',
]

export function isBackendTaskStatus(
  value: unknown,
): value is BackendTaskStatus {
  return (
    typeof value === 'string' &&
    BACKEND_TASK_STATUSES.includes(value as BackendTaskStatus)
  )
}

export function createInitialAgentState(): AgentState {
  return {
    status: 'idle',
    backendStatus: null,
    stage: 'idle',
    progress: 0,
    submitting: false,
    startRequested: false,
    cancelRequested: false,
    connection: 'idle',
    taskId: null,
    projectId: null,
    idempotencyKey: null,
    lastEventId: null,
    clarificationQuestion: null,
    clarificationAnswer: '',
    prompt: '',
    files: [],
    messages: [
      {
        id: 'message-1',
        role: 'agent',
        content: WELCOME_MESSAGE,
        sequence: 1,
      },
    ],
    messageSequence: 1,
    inputError: null,
    isHistoryOpen: false,
    isExploded: false,
    selectedPart: null,
  }
}

function appendMessage(
  state: AgentState,
  role: MessageRole,
  content: string,
  stage?: AgentStage,
): AgentState {
  const sequence = state.messageSequence + 1
  const message: AgentMessage = {
    id: `message-${sequence}`,
    role,
    content,
    stage,
    sequence,
  }

  return {
    ...state,
    messages: [...state.messages, message],
    messageSequence: sequence,
  }
}

function getFileIdentity(file: AgentFile): string {
  return `${file.name}\u0000${file.size}\u0000${file.lastModified}`
}

export function dedupeAgentFiles(files: AgentFile[]): AgentFile[] {
  const result: AgentFile[] = []
  const identityIndexes = new Map<string, number>()

  for (const file of files) {
    const identity = getFileIdentity(file)
    const existingIndex = identityIndexes.get(identity)
    if (existingIndex === undefined) {
      identityIndexes.set(identity, result.length)
      result.push(file)
      continue
    }

    const existing = result[existingIndex]
    if (existing.status === 'uploaded' && existing.artifactId) {
      continue
    }
    if (file.file || !existing.file) {
      result[existingIndex] = file
    }
  }

  return result
}

function updateFile(
  state: AgentState,
  fileId: string,
  update: (file: AgentFile) => AgentFile,
): AgentState {
  if (!state.files.some((file) => file.id === fileId)) {
    return state
  }

  return {
    ...state,
    files: state.files.map((file) =>
      file.id === fileId ? update(file) : file,
    ),
  }
}

function buildUserRequest(state: AgentState): string {
  const fileSummary =
    state.files.length > 0
      ? `已上传：${state.files.map((file) => file.name).join('、')}`
      : ''
  const promptSummary = state.prompt.trim()

  return [fileSummary, promptSummary].filter(Boolean).join('\n')
}

function startSubmission(state: AgentState): AgentState {
  if (state.files.length === 0) {
    return {
      ...state,
      inputError: '请先上传至少一份工程文档，再开始生成。',
    }
  }

  if (state.submitting) {
    return state
  }

  const nextState: AgentState = {
    ...state,
    status: 'running',
    backendStatus: state.taskId ? state.backendStatus : null,
    stage: 'reading',
    progress: 2,
    submitting: true,
    cancelRequested: false,
    inputError: null,
    isHistoryOpen: false,
    isExploded: false,
    selectedPart: null,
  }

  return appendMessage(nextState, 'user', buildUserRequest(state))
}

export function mapBackendTaskStatus(
  status: BackendTaskStatus,
  currentStage: AgentStage = 'idle',
  currentProgress = 0,
): MappedTaskStatus {
  switch (status) {
    case 'created':
      return { status: 'running', stage: 'reading', progress: 4 }
    case 'uploaded':
      return { status: 'running', stage: 'reading', progress: 10 }
    case 'parsing':
      return { status: 'running', stage: 'reading', progress: 18 }
    case 'awaiting_input':
      return { status: 'idle', stage: 'briefing', progress: 28 }
    case 'briefing':
      return { status: 'running', stage: 'briefing', progress: 34 }
    case 'thermal_analysis':
      return { status: 'running', stage: 'thermal', progress: 52 }
    case 'concept_imaging':
      return { status: 'running', stage: 'multiview', progress: 60 }
    case 'multiview_imaging':
      return { status: 'running', stage: 'multiview', progress: 70 }
    case 'multiview_review':
      return { status: 'running', stage: 'multiview', progress: 78 }
    case 'modeling':
      return { status: 'running', stage: 'modeling', progress: 88 }
    case 'model_review':
      return { status: 'running', stage: 'modeling', progress: 95 }
    case 'ready':
      return { status: 'ready', stage: 'ready', progress: 100 }
    case 'failed':
      return {
        status: 'error',
        stage: currentStage,
        progress: currentProgress,
      }
    case 'cancelled':
      return {
        status: 'cancelled',
        stage: currentStage,
        progress: currentProgress,
      }
  }
}

function impliesStartRequested(status: BackendTaskStatus): boolean {
  return !['created', 'uploaded', 'failed', 'cancelled'].includes(status)
}

export function agentReducer(
  state: AgentState,
  action: AgentAction,
): AgentState {
  switch (action.type) {
    case 'SET_PROMPT':
      return {
        ...state,
        prompt: action.prompt,
        inputError: null,
      }
    case 'ADD_FILES':
      return {
        ...state,
        files: dedupeAgentFiles([...state.files, ...action.files]),
        inputError: null,
      }
    case 'SET_FILES':
      return {
        ...state,
        files: dedupeAgentFiles(action.files),
        inputError: null,
      }
    case 'REMOVE_FILE':
      return {
        ...state,
        files: state.files.filter((file) => file.id !== action.fileId),
      }
    case 'START':
      return startSubmission(state)
    case 'SUBMIT_STARTED':
      return startSubmission({
        ...state,
        projectId: action.projectId,
        idempotencyKey: action.idempotencyKey,
      })
    case 'TASK_CREATED':
      return {
        ...state,
        status: 'running',
        backendStatus: 'created',
        stage: 'reading',
        progress: Math.max(state.progress, 4),
        submitting: true,
        startRequested: false,
        taskId: action.taskId,
        projectId: action.projectId,
        idempotencyKey: action.idempotencyKey,
        inputError: null,
      }
    case 'UPLOAD_STARTED':
      return updateFile(state, action.fileId, (file) => ({
        ...file,
        status: 'uploading',
        artifactId: undefined,
        error: undefined,
      }))
    case 'UPLOAD_SUCCEEDED':
      return updateFile(state, action.fileId, (file) => ({
        ...file,
        status: 'uploaded',
        artifactId: action.artifactId,
        error: undefined,
      }))
    case 'UPLOAD_FAILED':
      return updateFile(state, action.fileId, (file) => ({
        ...file,
        status: 'failed',
        artifactId: undefined,
        error: action.error,
      }))
    case 'SUBMIT_FAILED':
      return appendMessage(
        {
          ...state,
          status: 'error',
          submitting: false,
          inputError: action.error,
        },
        'agent',
        action.error,
        state.stage,
      )
    case 'INPUT_ERROR':
      return {
        ...state,
        inputError: action.error,
      }
    case 'TASK_STARTED': {
      const mapped = mapBackendTaskStatus(
        action.status,
        state.stage,
        state.progress,
      )
      return {
        ...state,
        ...mapped,
        backendStatus: action.status,
        submitting: false,
        startRequested: true,
        cancelRequested: false,
        inputError: null,
      }
    }
    case 'CONNECTION_CHANGED':
      return {
        ...state,
        connection: action.connection,
      }
    case 'TASK_STATUS_RECEIVED': {
      if (
        action.lastEventId !== undefined &&
        state.lastEventId !== null &&
        action.lastEventId <= state.lastEventId
      ) {
        return state
      }

      const mapped = mapBackendTaskStatus(
        action.status,
        state.stage,
        state.progress,
      )
      const startRequested =
        state.startRequested || impliesStartRequested(action.status)
      const mappedForSubmission =
        !startRequested && !state.submitting
          ? { ...mapped, status: 'idle' as const }
          : mapped
      let nextState: AgentState = {
        ...state,
        ...mappedForSubmission,
        backendStatus: action.status,
        submitting: startRequested ? false : state.submitting,
        startRequested,
        lastEventId: action.lastEventId ?? state.lastEventId,
        inputError: action.status === 'failed' ? state.inputError : null,
      }

      if (action.message?.trim()) {
        nextState = appendMessage(
          nextState,
          'agent',
          action.message.trim(),
          mappedForSubmission.stage,
        )
      }
      return nextState
    }
    case 'SET_CLARIFICATION_ANSWER':
      return {
        ...state,
        clarificationAnswer: action.answer,
        inputError: null,
      }
    case 'CLARIFICATION_RECEIVED': {
      const nextState: AgentState = {
        ...state,
        status: 'idle',
        backendStatus: 'awaiting_input',
        stage: 'briefing',
        progress: Math.max(state.progress, 28),
        submitting: false,
        startRequested: true,
        clarificationQuestion: action.question,
        clarificationAnswer:
          state.clarificationQuestion === action.question
            ? state.clarificationAnswer
            : '',
        inputError: null,
      }
      return state.clarificationQuestion === action.question
        ? nextState
        : appendMessage(nextState, 'agent', action.question, 'briefing')
    }
    case 'CLARIFICATION_SUBMIT_STARTED':
      if (!state.clarificationAnswer.trim()) {
        return {
          ...state,
          inputError: '请填写补充信息后再提交。',
        }
      }
      return {
        ...state,
        submitting: true,
        inputError: null,
      }
    case 'CLARIFICATION_SUBMITTED': {
      const answer = state.clarificationAnswer.trim()
      const nextState: AgentState = {
        ...state,
        status: 'running',
        backendStatus: 'briefing',
        stage: 'briefing',
        progress: Math.max(state.progress, 34),
        submitting: false,
        clarificationQuestion: null,
        clarificationAnswer: '',
        inputError: null,
      }
      return answer
        ? appendMessage(nextState, 'user', answer, 'briefing')
        : nextState
    }
    case 'CANCEL':
    case 'CANCEL_REQUESTED':
      if (state.status !== 'running' && !state.submitting) {
        return state
      }
      return {
        ...state,
        submitting: false,
        cancelRequested: true,
        inputError: null,
      }
    case 'CANCEL_CONFIRMED': {
      if (action.restartSubmission) {
        return {
          ...state,
          status: 'idle',
          backendStatus: null,
          stage: 'idle',
          progress: 0,
          submitting: false,
          startRequested: false,
          cancelRequested: false,
          connection: 'idle',
          taskId: null,
          idempotencyKey: null,
          lastEventId: null,
          files: state.files.map((file) =>
            file.file
              ? {
                  ...file,
                  status: 'pending',
                  artifactId: undefined,
                  error: undefined,
                }
              : {
                  ...file,
                  status: 'failed',
                  artifactId: undefined,
                  error: '请重新选择此文件后再上传。',
                },
          ),
          inputError: null,
        }
      }

      return appendMessage(
        {
          ...state,
          status: 'cancelled',
          backendStatus: 'cancelled',
          submitting: false,
          cancelRequested: false,
          connection: 'disconnected',
        },
        'agent',
        '生成已暂停，现有资料和阶段结果都已保留，可以随时继续。',
        state.stage,
      )
    }
    case 'CANCEL_FAILED':
      return appendMessage(
        {
          ...state,
          status: state.startRequested ? state.status : 'idle',
          submitting: false,
          cancelRequested: false,
          files: state.startRequested
            ? state.files
            : state.files.map((file) =>
                file.status === 'uploading'
                  ? {
                      ...file,
                      status: file.file ? 'pending' : 'failed',
                      error: file.file
                        ? undefined
                        : '请重新选择此文件后再上传。',
                    }
                  : file,
              ),
          inputError: action.error,
        },
        'agent',
        action.error,
        state.stage,
      )
    case 'TOGGLE_HISTORY':
      return {
        ...state,
        isHistoryOpen: !state.isHistoryOpen,
      }
    case 'CLOSE_HISTORY':
      return {
        ...state,
        isHistoryOpen: false,
      }
    case 'TOGGLE_EXPLODED':
      return {
        ...state,
        isExploded: !state.isExploded,
        selectedPart: state.isExploded ? null : state.selectedPart,
      }
    case 'SELECT_PART':
      return {
        ...state,
        selectedPart: action.part,
      }
    case 'RESET':
      return createInitialAgentState()
  }
}

export function getLatestMessages(
  state: AgentState,
  count = 2,
): AgentMessage[] {
  return state.messages.slice(-count)
}

function isAgentStage(value: unknown): value is AgentStage {
  return (
    typeof value === 'string' &&
    [
      'idle',
      'reading',
      'briefing',
      'thermal',
      'multiview',
      'modeling',
      'ready',
    ].includes(value)
  )
}

function isStoredAgentState(value: unknown): value is AgentState {
  if (!value || typeof value !== 'object') {
    return false
  }

  const state = value as Partial<AgentState>
  return (
    typeof state.status === 'string' &&
    isAgentStage(state.stage) &&
    typeof state.progress === 'number' &&
    typeof state.prompt === 'string' &&
    Array.isArray(state.files) &&
    Array.isArray(state.messages) &&
    typeof state.messageSequence === 'number'
  )
}

function isStoredFile(value: unknown): value is AgentFile {
  if (!value || typeof value !== 'object') {
    return false
  }

  const file = value as Partial<AgentFile>
  return (
    typeof file.id === 'string' &&
    typeof file.name === 'string' &&
    typeof file.size === 'number' &&
    typeof file.type === 'string' &&
    typeof file.lastModified === 'number' &&
    typeof file.status === 'string' &&
    ['pending', 'uploading', 'uploaded', 'failed'].includes(file.status)
  )
}

export function loadAgentState(storage: StorageReader): AgentState {
  try {
    const storedValue = storage.getItem(AGENT_STORAGE_KEY)
    if (!storedValue) {
      return createInitialAgentState()
    }

    const parsedState: unknown = JSON.parse(storedValue)
    if (!isStoredAgentState(parsedState)) {
      return createInitialAgentState()
    }

    const initialState = createInitialAgentState()
    const storedFiles = parsedState.files.filter(isStoredFile)
    const files = storedFiles.map((file) => {
      if (file.status === 'uploaded' && typeof file.artifactId === 'string') {
        return {
          ...file,
          file: undefined,
        }
      }

      return {
        ...file,
        file: undefined,
        status: 'failed' as const,
        artifactId: undefined,
        error: '请重新选择此文件后再上传。',
      }
    })
    const storedBackendStatus = isBackendTaskStatus(parsedState.backendStatus)
      ? parsedState.backendStatus
      : null
    const startRequested =
      parsedState.startRequested === true ||
      (parsedState.startRequested === undefined &&
        storedBackendStatus !== null &&
        impliesStartRequested(storedBackendStatus))
    const hasCreatedTask = typeof parsedState.taskId === 'string'
    const canStartCreatedTask = hasCreatedTask && !startRequested
    const needsReselection = files.some((file) => file.status === 'failed')

    return {
      ...initialState,
      ...parsedState,
      status: canStartCreatedTask ? 'idle' : parsedState.status,
      backendStatus: storedBackendStatus,
      files,
      submitting: false,
      startRequested,
      cancelRequested: false,
      connection:
        hasCreatedTask && startRequested ? 'disconnected' : 'idle',
      clarificationQuestion:
        typeof parsedState.clarificationQuestion === 'string'
          ? parsedState.clarificationQuestion
          : null,
      clarificationAnswer:
        typeof parsedState.clarificationAnswer === 'string'
          ? parsedState.clarificationAnswer
          : '',
      inputError: needsReselection
        ? '部分附件需要重新选择后才能继续。'
        : parsedState.inputError,
      isHistoryOpen: false,
      selectedPart: null,
    }
  } catch {
    return createInitialAgentState()
  }
}

function toStoredAgentFile(file: AgentFile): Omit<AgentFile, 'file'> {
  return {
    id: file.id,
    name: file.name,
    size: file.size,
    type: file.type,
    lastModified: file.lastModified,
    status: file.status,
    artifactId: file.artifactId,
    error: file.error,
  }
}

export function saveAgentState(
  storage: StorageWriter,
  state: AgentState,
): void {
  const storedState = {
    ...state,
    files: state.files.map(toStoredAgentFile),
  }
  storage.setItem(AGENT_STORAGE_KEY, JSON.stringify(storedState))
}

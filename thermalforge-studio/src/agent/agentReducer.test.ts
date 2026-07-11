import { describe, expect, it } from 'vitest'
import {
  agentReducer,
  createInitialAgentState,
  getLatestMessages,
  loadAgentState,
  mapBackendTaskStatus,
  saveAgentState,
} from './agentReducer'
import type { AgentFile } from './agentTypes'

function createAgentFile(
  name = 'joint-spec.pdf',
  status: AgentFile['status'] = 'pending',
): AgentFile {
  const file = new File(['thermal input'], name, {
    type: 'application/pdf',
    lastModified: 1234,
  })
  return {
    id: `${file.name}-${file.size}-${file.lastModified}`,
    name: file.name,
    size: file.size,
    type: file.type,
    lastModified: file.lastModified,
    file,
    status,
  }
}

describe('agentReducer', () => {
  it('creates an idle session with transport state ready to connect', () => {
    const state = createInitialAgentState()

    expect(state).toMatchObject({
      status: 'idle',
      backendStatus: null,
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
    })
    expect(state.messages).toHaveLength(1)
  })

  it('requires a source document even when a prompt is present', () => {
    const prompted = agentReducer(createInitialAgentState(), {
      type: 'SET_PROMPT',
      prompt: '降低机器人膝关节热点温度。',
    })
    const state = agentReducer(prompted, { type: 'START' })

    expect(state.status).toBe('idle')
    expect(state.submitting).toBe(false)
    expect(state.inputError).toMatch(/上传.*工程文档/)
  })

  it('deduplicates files while preferring a newly selected browser File', () => {
    const file = createAgentFile()
    const first = agentReducer(createInitialAgentState(), {
      type: 'ADD_FILES',
      files: [file],
    })
    const replacement = createAgentFile()
    const duplicate = agentReducer(first, {
      type: 'ADD_FILES',
      files: [replacement],
    })

    expect(duplicate.files).toHaveLength(1)
    expect(duplicate.files[0]?.file).toBe(replacement.file)
    expect(duplicate.files[0]?.status).toBe('pending')
  })

  it('does not replace an uploaded artifact when the same file is selected again', () => {
    const uploaded = {
      ...createAgentFile('uploaded.pdf', 'uploaded'),
      artifactId: 'artifact-1',
      file: undefined,
    }
    const state = agentReducer(createInitialAgentState(), {
      type: 'SET_FILES',
      files: [uploaded, createAgentFile('uploaded.pdf')],
    })

    expect(state.files).toHaveLength(1)
    expect(state.files[0]).toMatchObject({
      status: 'uploaded',
      artifactId: 'artifact-1',
    })
  })

  it('starts submission from a document and records task identity', () => {
    const withFile = agentReducer(createInitialAgentState(), {
      type: 'ADD_FILES',
      files: [createAgentFile()],
    })
    const submitting = agentReducer(withFile, {
      type: 'SUBMIT_STARTED',
      projectId: 'project-1',
      idempotencyKey: 'request-1',
    })
    const created = agentReducer(submitting, {
      type: 'TASK_CREATED',
      taskId: 'task-1',
      projectId: 'project-1',
      idempotencyKey: 'request-1',
    })

    expect(submitting).toMatchObject({
      status: 'running',
      stage: 'reading',
      submitting: true,
    })
    expect(submitting.messages.at(-1)?.content).toContain('joint-spec.pdf')
    expect(created).toMatchObject({
      backendStatus: 'created',
      submitting: true,
      startRequested: false,
      taskId: 'task-1',
      projectId: 'project-1',
      idempotencyKey: 'request-1',
    })

    const uploadedSnapshot = agentReducer(created, {
      type: 'TASK_STATUS_RECEIVED',
      status: 'uploaded',
    })
    expect(uploadedSnapshot.submitting).toBe(true)
    expect(uploadedSnapshot.startRequested).toBe(false)

    const started = agentReducer(uploadedSnapshot, {
      type: 'TASK_STARTED',
      status: 'parsing',
    })
    expect(started).toMatchObject({
      submitting: false,
      startRequested: true,
      backendStatus: 'parsing',
    })
  })

  it('tracks attachment upload success and failure independently', () => {
    const firstFile = createAgentFile('first.pdf')
    const secondFile = createAgentFile('second.pdf')
    let state = agentReducer(createInitialAgentState(), {
      type: 'ADD_FILES',
      files: [firstFile, secondFile],
    })
    state = agentReducer(state, {
      type: 'UPLOAD_STARTED',
      fileId: firstFile.id,
    })
    state = agentReducer(state, {
      type: 'UPLOAD_SUCCEEDED',
      fileId: firstFile.id,
      artifactId: 'artifact-1',
    })
    state = agentReducer(state, {
      type: 'UPLOAD_FAILED',
      fileId: secondFile.id,
      error: '上传失败',
    })

    expect(state.files[0]).toMatchObject({
      status: 'uploaded',
      artifactId: 'artifact-1',
    })
    expect(state.files[1]).toMatchObject({
      status: 'failed',
      error: '上传失败',
    })
  })

  it('maps backend task states and ignores replayed SSE event ids', () => {
    let state = agentReducer(createInitialAgentState(), {
      type: 'TASK_STATUS_RECEIVED',
      status: 'thermal_analysis',
      lastEventId: 7,
      message: '正在分析热路径',
    })
    const replayed = agentReducer(state, {
      type: 'TASK_STATUS_RECEIVED',
      status: 'ready',
      lastEventId: 7,
      message: '不应重复应用',
    })

    expect(state).toMatchObject({
      backendStatus: 'thermal_analysis',
      stage: 'thermal',
      progress: 52,
      lastEventId: 7,
    })
    expect(replayed).toBe(state)
    expect(getLatestMessages(state, 1)[0]?.content).toBe('正在分析热路径')
  })

  it('keeps concept_imaging distinct from a completed model', () => {
    expect(mapBackendTaskStatus('concept_imaging')).toEqual({
      status: 'running',
      stage: 'multiview',
      progress: 60,
    })
  })

  it('persists every attachment metadata record and never serializes File', () => {
    const pending = createAgentFile('pending.pdf')
    const uploaded = {
      ...createAgentFile('uploaded.pdf', 'uploaded'),
      artifactId: 'artifact-2',
    }
    const state = agentReducer(createInitialAgentState(), {
      type: 'SET_FILES',
      files: [pending, uploaded],
    })
    let serialized = ''

    saveAgentState(
      {
        setItem: (_key, value) => {
          serialized = value
        },
      },
      state,
    )

    const stored = JSON.parse(serialized) as {
      files: Array<Record<string, unknown>>
    }
    expect(stored.files).toHaveLength(2)
    expect(stored.files[0]).toMatchObject({
      name: 'pending.pdf',
      status: 'pending',
    })
    expect(stored.files[1]).toMatchObject({
      name: 'uploaded.pdf',
      artifactId: 'artifact-2',
      status: 'uploaded',
    })
    expect(stored.files.every((file) => !('file' in file))).toBe(true)
  })

  it('restores non-uploaded attachments as failed and leaves a pre-start task startable', () => {
    const uploaded = {
      ...createAgentFile('uploaded.pdf', 'uploaded'),
      artifactId: 'artifact-3',
      file: undefined,
    }
    const pending = createAgentFile('pending.pdf')
    const storedState = {
      ...createInitialAgentState(),
      taskId: 'task-3',
      backendStatus: 'uploaded',
      status: 'running',
      submitting: true,
      connection: 'connected',
      files: [uploaded, pending],
    }

    const restored = loadAgentState({
      getItem: () => JSON.stringify(storedState),
    })

    expect(restored.files).toHaveLength(2)
    expect(restored.files[0]).toMatchObject({
      artifactId: 'artifact-3',
      file: undefined,
    })
    expect(restored.files[1]).toMatchObject({
      status: 'failed',
      file: undefined,
      error: expect.stringMatching(/重新选择/),
    })
    expect(restored.status).toBe('idle')
    expect(restored.submitting).toBe(false)
    expect(restored.startRequested).toBe(false)
    expect(restored.connection).toBe('idle')
    expect(restored.inputError).toMatch(/重新选择/)
  })

  it('does not mark cancellation complete until the server confirms it', () => {
    const file = createAgentFile()
    let state = agentReducer(createInitialAgentState(), {
      type: 'ADD_FILES',
      files: [file],
    })
    state = agentReducer(state, { type: 'START' })
    state = agentReducer(state, {
      type: 'TASK_CREATED',
      taskId: 'task-cancel',
      projectId: 'project-1',
      idempotencyKey: 'cancel-key',
    })

    const requested = agentReducer(state, { type: 'CANCEL_REQUESTED' })
    expect(requested).toMatchObject({
      status: 'running',
      backendStatus: 'created',
      cancelRequested: true,
    })

    const confirmed = agentReducer(requested, {
      type: 'CANCEL_CONFIRMED',
      restartSubmission: true,
    })
    expect(confirmed).toMatchObject({
      status: 'idle',
      backendStatus: null,
      taskId: null,
      idempotencyKey: null,
      cancelRequested: false,
    })
    expect(confirmed.files[0]).toMatchObject({
      status: 'pending',
      artifactId: undefined,
    })
  })

  it('returns an interrupted pre-start upload to a startable state when cancel fails', () => {
    const file = createAgentFile()
    let state = agentReducer(createInitialAgentState(), {
      type: 'ADD_FILES',
      files: [file],
    })
    state = agentReducer(state, { type: 'START' })
    state = agentReducer(state, {
      type: 'UPLOAD_STARTED',
      fileId: file.id,
    })
    state = agentReducer(state, { type: 'CANCEL_REQUESTED' })
    state = agentReducer(state, {
      type: 'CANCEL_FAILED',
      error: '取消请求失败',
    })

    expect(state).toMatchObject({
      status: 'idle',
      cancelRequested: false,
      inputError: '取消请求失败',
    })
    expect(state.files[0]).toMatchObject({ status: 'pending' })
  })

  it('keeps clarification answers separate from the original prompt', () => {
    let state = agentReducer(createInitialAgentState(), {
      type: 'SET_PROMPT',
      prompt: '原始热设计目标',
    })
    state = agentReducer(state, {
      type: 'CLARIFICATION_RECEIVED',
      question: '允许的最高壳体温度是多少？',
    })
    state = agentReducer(state, {
      type: 'SET_CLARIFICATION_ANSWER',
      answer: '最高 70 摄氏度',
    })
    state = agentReducer(state, {
      type: 'CLARIFICATION_SUBMIT_STARTED',
    })
    state = agentReducer(state, { type: 'CLARIFICATION_SUBMITTED' })

    expect(state.prompt).toBe('原始热设计目标')
    expect(state.clarificationQuestion).toBeNull()
    expect(state.clarificationAnswer).toBe('')
    expect(state.messages.at(-1)?.content).toBe('最高 70 摄氏度')
  })

  it('does not duplicate the same clarification after reconnecting', () => {
    const first = agentReducer(createInitialAgentState(), {
      type: 'CLARIFICATION_RECEIVED',
      question: '允许的最高壳体温度是多少？',
    })
    const replayed = agentReducer(first, {
      type: 'CLARIFICATION_RECEIVED',
      question: '允许的最高壳体温度是多少？',
    })

    expect(replayed.messages).toHaveLength(first.messages.length)
  })

  it('falls back to a clean session when saved state is corrupt', () => {
    expect(
      loadAgentState({ getItem: () => '{broken-json' }),
    ).toEqual(createInitialAgentState())
  })

  it('tracks exploded and selected-part states independently', () => {
    const exploded = agentReducer(createInitialAgentState(), {
      type: 'TOGGLE_EXPLODED',
    })
    const selected = agentReducer(exploded, {
      type: 'SELECT_PART',
      part: 'thermal-shell',
    })

    expect(selected.isExploded).toBe(true)
    expect(selected.selectedPart).toBe('thermal-shell')
  })
})

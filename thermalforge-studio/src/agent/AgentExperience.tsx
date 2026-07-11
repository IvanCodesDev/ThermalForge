import { CloudUpload, Hexagon, Plus } from 'lucide-react'
import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useReducer,
  useRef,
  useState,
} from 'react'
import type { DragEvent } from 'react'
import {
  ApiError,
  answerClarification,
  cancelTask,
  createIdempotencyKey,
  createProject,
  createTask,
  getClarification,
  getEngineeringBrief,
  getTaskImageManifest,
  getTask,
  getThermalAnalysis,
  getThermalDesign,
  getViewerLibrary,
  getViewerManifest,
  retryTask,
  startTask,
  streamTaskEvents,
  uploadDocument,
} from '../api'
import type { TaskImageManifest, TaskStreamEvent } from '../api'
import { PartDetailSheet } from '../model/PartDetailSheet'
import { DEFAULT_VIEWER_MANIFEST } from '../model/viewerManifest'
import {
  fromBackendViewerLibrary,
  fromBackendViewerManifest,
} from '../model/viewerManifest'
import {
  agentReducer,
  createInitialAgentState,
  getLatestMessages,
  loadAgentState,
  saveAgentState,
} from './agentReducer'
import { AgentComposer } from './AgentComposer'
import { selectAgentFiles } from './agentFiles'
import { AgentConversation } from './AgentConversation'
import { ResultShowcase } from './ResultShowcase'
import { AgentHistoryDrawer } from './AgentHistoryDrawer'
import { AgentStalledNotice } from './AgentStalledNotice'
import type { BackendTaskStatus } from './agentTypes'
import { getMockStage, MOCK_STAGES } from './mockPipeline'
import type { TaskResultBundle } from './taskResults'

const ModelStage = lazy(async () => {
  const module = await import('../model/ModelStage')
  return { default: module.ModelStage }
})

const STATUS_LABELS = {
  idle: '等待输入',
  running: '生成中',
  ready: '设计已就绪',
  cancelled: '生成已暂停',
  error: '需要处理',
} as const

const CONNECTION_LABELS = {
  connecting: '正在连接',
  reconnecting: '正在重连',
  error: '连接异常',
} as const

const TERMINAL_STATUSES = new Set<BackendTaskStatus>([
  'ready',
  'failed',
  'cancelled',
])
const RESULT_AVAILABLE_STATUSES = new Set<BackendTaskStatus>([
  'concept_imaging',
  'multiview_imaging',
  'multiview_review',
  'modeling',
  'model_review',
  'ready',
])
const IMAGE_AVAILABLE_STATUSES = new Set<BackendTaskStatus>([
  'multiview_review',
  'modeling',
  'model_review',
  'ready',
])

const EVENT_MESSAGES: Partial<Record<string, string>> = {
  'task.started': '工程资料已提交，正在进入分析队列。',
  'document.parsing.started': '正在解析工程资料并建立可追溯的输入。',
  'document.parsed': '资料解析完成，正在整理热源与工程约束。',
  'engineering_brief.clarification_required': '工程输入还缺少关键参数，请补充确认后继续。',
  'engineering_brief.clarification_answered': '补充信息已收到，正在更新工程约束。',
  'engineering_brief.completed': '工程约束已建立，正在执行筛选级热分析。',
  'thermal_design.completed': '筛选级热设计已完成，正在生成 GPT Image 2 母图。',
  'concept_image.completed': '母图已生成，正在保持同一设计身份生成其余视图。',
  'multiview_images.completed': '六视图概念图已生成，正在执行完整性检查。',
  'multiview.reviewed': '六视图完整性检查通过，正在关联三维概念网格。',
  'model.reference_associated': '整体与分件概念网格已关联，正在完成模型审查。',
  'document.parsing.failed': '工程资料解析失败，请检查文件后重试。',
  'engineering_brief.failed': '工程约束生成失败，可以保留现有资料后重试。',
  'thermal_design.failed': '热设计计算失败，可以从当前阶段重试。',
}

function eventSequence(event: TaskStreamEvent): number | undefined {
  const sequence = Number(event.id)
  return Number.isSafeInteger(sequence) && sequence >= 0 ? sequence : undefined
}

function userFacingError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'source_document_required') {
      return '请至少上传一份工程文档后再启动分析。'
    }
    if (error.code === 'task_already_started') {
      return '任务已经开始处理，不能再追加工程资料。'
    }
    if (error.kind === 'network') {
      return '暂时无法连接 ThermalForge 服务，请检查服务状态后重试。'
    }
    if (error.kind === 'aborted') {
      return '本次请求已取消。'
    }
    return error.message
  }
  return error instanceof Error ? error.message : '请求失败，请稍后重试。'
}

export function AgentExperience() {
  const [state, dispatch] = useReducer(
    agentReducer,
    undefined,
    () =>
      typeof window === 'undefined'
        ? createInitialAgentState()
        : loadAgentState(window.localStorage),
  )
  const [viewerManifest, setViewerManifest] = useState(
    DEFAULT_VIEWER_MANIFEST,
  )
  const [viewerLibraryManifest, setViewerLibraryManifest] = useState(
    DEFAULT_VIEWER_MANIFEST,
  )
  const [taskResults, setTaskResults] = useState<TaskResultBundle | null>(null)
  const [taskResultsError, setTaskResultsError] = useState<string | null>(null)
  const [taskResultsLoading, setTaskResultsLoading] = useState(false)
  const [taskResultsReload, setTaskResultsReload] = useState(0)
  const [taskImageManifest, setTaskImageManifest] =
    useState<TaskImageManifest | null>(null)
  const [taskImagesError, setTaskImagesError] = useState<string | null>(null)
  const [taskImagesLoading, setTaskImagesLoading] = useState(false)
  const [taskImagesReload, setTaskImagesReload] = useState(0)
  const [viewerManifestStatus, setViewerManifestStatus] = useState<
    'idle' | 'loading' | 'ready' | 'error'
  >('idle')
  const [viewerManifestError, setViewerManifestError] = useState<string | null>(
    null,
  )
  const [viewerManifestReload, setViewerManifestReload] = useState(0)
  const [trackingGeneration, setTrackingGeneration] = useState(0)
  const [checkingTask, setCheckingTask] = useState(false)
  const [isFileDragging, setIsFileDragging] = useState(false)
  const fileDragDepth = useRef(0)
  const submissionController = useRef<AbortController | null>(null)
  const statusCheckController = useRef<AbortController | null>(null)
  const taskTrackingController = useRef<AbortController | null>(null)
  const activeTaskId = useRef(state.taskId)
  const lastEventId = useRef(state.lastEventId)
  const handleSelectPart = useCallback(
    (part: string | null) => dispatch({ type: 'SELECT_PART', part }),
    [],
  )

  const currentStage = getMockStage(state.stage)
  const currentStageIndex = MOCK_STAGES.findIndex(
    (stage) => stage.id === state.stage,
  )
  const isGeneratingConceptImages = state.backendStatus === 'concept_imaging'
  const expectsTaskModel =
    state.backendStatus !== null &&
    RESULT_AVAILABLE_STATUSES.has(state.backendStatus)
  const hasCompleteTaskResults = Boolean(
    taskResults?.engineeringBrief &&
      taskResults.thermalAnalysis &&
      taskResults.thermalDesign,
  )
  const taskViewerManifest =
    expectsTaskModel && viewerManifestStatus === 'ready'
      ? viewerManifest
      : null
  const displayedViewerManifest = expectsTaskModel
    ? taskViewerManifest
    : viewerLibraryManifest
  const hasTerminalBackendStatus =
    state.backendStatus !== null && TERMINAL_STATUSES.has(state.backendStatus)
  const connectionLabel =
    state.connection === 'connecting' ||
    state.connection === 'reconnecting' ||
    state.connection === 'error'
      ? CONNECTION_LABELS[state.connection]
      : null
  const statusLabel = state.cancelRequested
    ? '正在停止'
    : state.submitting
      ? '正在提交'
      : connectionLabel
        ? connectionLabel
        : isGeneratingConceptImages
          ? '正在生成概念图'
          : STATUS_LABELS[state.status]
  const statusClass =
    state.connection === 'error'
      ? 'error'
      : state.submitting || state.cancelRequested || connectionLabel
        ? 'running'
        : state.status
  const stageLabel = isGeneratingConceptImages
    ? '正在生成六视图概念图'
    : (currentStage?.label ?? '等待工程输入')

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    try {
      saveAgentState(window.localStorage, state)
    } catch {
      // The active session remains usable when browser storage is unavailable.
    }
  }, [state])

  useEffect(() => {
    lastEventId.current = state.lastEventId
  }, [state.lastEventId])

  useEffect(() => {
    activeTaskId.current = state.taskId
  }, [state.taskId])

  useEffect(
    () => () => {
      const submission = submissionController.current
      const statusCheck = statusCheckController.current
      const taskTracking = taskTrackingController.current
      submissionController.current = null
      statusCheckController.current = null
      taskTrackingController.current = null
      submission?.abort()
      statusCheck?.abort()
      taskTracking?.abort()
    },
    [],
  )

  useEffect(() => {
    const controller = new AbortController()
    void getViewerLibrary({ signal: controller.signal })
      .then((library) => {
        const manifest = fromBackendViewerLibrary(library)
        if (manifest) {
          setViewerLibraryManifest(manifest)
        }
      })
      .catch(() => {
        // The bundled Wall-E asset remains an explicit offline fallback.
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    setViewerManifest(DEFAULT_VIEWER_MANIFEST)
    setViewerManifestStatus('idle')
    setViewerManifestError(null)
    setTaskResults(null)
    setTaskResultsError(null)
    setTaskResultsLoading(false)
    setTaskImageManifest(null)
    setTaskImagesError(null)
    setTaskImagesLoading(false)
  }, [state.taskId])

  useEffect(() => {
    if (
      !state.taskId ||
      !state.backendStatus ||
      !RESULT_AVAILABLE_STATUSES.has(state.backendStatus) ||
      hasCompleteTaskResults
    ) {
      return
    }

    const controller = new AbortController()
    const options = { signal: controller.signal }
    setTaskResultsLoading(true)
    void Promise.allSettled([
      getEngineeringBrief(state.taskId, options),
      getThermalAnalysis(state.taskId, options),
      getThermalDesign(state.taskId, options),
    ])
      .then(([engineeringBrief, thermalAnalysis, thermalDesign]) => {
        if (controller.signal.aborted) {
          return
        }
        const loaded: TaskResultBundle = {}
        const errors: string[] = []
        if (engineeringBrief.status === 'fulfilled') {
          loaded.engineeringBrief = engineeringBrief.value
        } else {
          errors.push(userFacingError(engineeringBrief.reason))
        }
        if (thermalAnalysis.status === 'fulfilled') {
          loaded.thermalAnalysis = thermalAnalysis.value
        } else {
          errors.push(userFacingError(thermalAnalysis.reason))
        }
        if (thermalDesign.status === 'fulfilled') {
          loaded.thermalDesign = thermalDesign.value
        } else {
          errors.push(userFacingError(thermalDesign.reason))
        }
        if (Object.keys(loaded).length > 0) {
          setTaskResults((current) => ({ ...current, ...loaded }))
        }
        setTaskResultsError(
          errors.length > 0 ? [...new Set(errors)].join('；') : null,
        )
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setTaskResultsLoading(false)
        }
      })

    return () => controller.abort()
  }, [
    hasCompleteTaskResults,
    state.backendStatus,
    state.taskId,
    taskResultsReload,
  ])

  useEffect(() => {
    if (
      !state.taskId ||
      !state.backendStatus ||
      !IMAGE_AVAILABLE_STATUSES.has(state.backendStatus)
    ) {
      return
    }

    const controller = new AbortController()
    setTaskImagesLoading(true)
    setTaskImagesError(null)
    void getTaskImageManifest(state.taskId, { signal: controller.signal })
      .then((manifest) => {
        if (!controller.signal.aborted) {
          setTaskImageManifest(manifest)
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setTaskImagesError(userFacingError(error))
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setTaskImagesLoading(false)
        }
      })
    return () => controller.abort()
  }, [state.backendStatus, state.taskId, taskImagesReload])

  useEffect(() => {
    if (
      !state.taskId ||
      !state.backendStatus ||
      ![
        'concept_imaging',
        'multiview_imaging',
        'multiview_review',
        'modeling',
        'model_review',
        'ready',
      ].includes(state.backendStatus)
    ) {
      return
    }

    const controller = new AbortController()
    setViewerManifestStatus('loading')
    setViewerManifestError(null)
    void getViewerManifest(state.taskId, { signal: controller.signal })
      .then((manifest) => {
        setViewerManifest(fromBackendViewerManifest(manifest))
        setViewerManifestStatus('ready')
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        const message =
          error instanceof ApiError && error.code === 'viewer_model_not_found'
            ? '任务模型尚未生成，请稍后重新加载。'
            : `模型清单加载失败：${userFacingError(error)}`
        setViewerManifestStatus('error')
        setViewerManifestError(message)
      })

    return () => controller.abort()
  }, [state.backendStatus, state.taskId, viewerManifestReload])

  useEffect(() => {
    if (
      !state.taskId ||
      !state.startRequested ||
      hasTerminalBackendStatus
    ) {
      return
    }

    const taskId = state.taskId
    const controller = new AbortController()
    taskTrackingController.current?.abort()
    taskTrackingController.current = controller

    const followTask = async () => {
      dispatch({ type: 'CONNECTION_CHANGED', connection: 'connecting' })
      try {
        const snapshot = await getTask(taskId, { signal: controller.signal })
        dispatch({ type: 'TASK_STATUS_RECEIVED', status: snapshot.status })
        if (snapshot.status === 'awaiting_input') {
          const clarification = await getClarification(taskId, {
            signal: controller.signal,
          })
          dispatch({
            type: 'CLARIFICATION_RECEIVED',
            question: clarification.question,
          })
        }
        if (TERMINAL_STATUSES.has(snapshot.status)) {
          dispatch({ type: 'CONNECTION_CHANGED', connection: 'disconnected' })
          return
        }
        for await (const event of streamTaskEvents(taskId, {
          lastEventId: lastEventId.current ?? undefined,
          onConnectionChange: (connection) => {
            if (!controller.signal.aborted) {
              dispatch({ type: 'CONNECTION_CHANGED', connection })
            }
          },
          signal: controller.signal,
        })) {
          const currentTask = await getTask(taskId, {
            signal: controller.signal,
          })
          dispatch({
            type: 'TASK_STATUS_RECEIVED',
            status: currentTask.status,
            lastEventId: eventSequence(event),
            message: EVENT_MESSAGES[event.type],
          })
          if (currentTask.status === 'awaiting_input') {
            const clarification = await getClarification(taskId, {
              signal: controller.signal,
            })
            dispatch({
              type: 'CLARIFICATION_RECEIVED',
              question: clarification.question,
            })
          }
          if (TERMINAL_STATUSES.has(currentTask.status)) {
            break
          }
        }
        if (!controller.signal.aborted) {
          dispatch({ type: 'CONNECTION_CHANGED', connection: 'disconnected' })
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          dispatch({ type: 'CONNECTION_CHANGED', connection: 'error' })
          dispatch({ type: 'INPUT_ERROR', error: userFacingError(error) })
        }
      }
    }

    void followTask()
    return () => {
      if (taskTrackingController.current === controller) {
        taskTrackingController.current = null
      }
      controller.abort()
    }
  }, [
    hasTerminalBackendStatus,
    state.startRequested,
    state.status,
    state.taskId,
    trackingGeneration,
  ])

  const handleStart = async () => {
    if (state.files.length === 0 || state.submitting) {
      dispatch({ type: 'START' })
      return
    }

    const controller = new AbortController()
    submissionController.current?.abort()
    submissionController.current = controller
    dispatch({ type: 'START' })

    try {
      if (
        state.taskId &&
        state.startRequested &&
        (state.backendStatus === 'failed' ||
          state.backendStatus === 'cancelled' ||
          state.status === 'cancelled')
      ) {
        const retried = await retryTask(state.taskId, {
          signal: controller.signal,
        })
        dispatch({ type: 'TASK_STARTED', status: retried.status })
        return
      }

      if (state.backendStatus === 'ready') {
        throw new Error('当前任务已经完成，请使用“新建设计”开始新的任务。')
      }

      if (state.backendStatus === 'awaiting_input') {
        dispatch({
          type: 'INPUT_ERROR',
          error: '正在读取需要补充的工程信息，请稍候。',
        })
        return
      }

      const idempotencyKey =
        state.idempotencyKey ?? createIdempotencyKey()
      let projectId = state.projectId
      if (!projectId) {
        const project = await createProject('机器人关节热增强', {
          signal: controller.signal,
        })
        projectId = project.id
      }
      dispatch({ type: 'SUBMIT_STARTED', projectId, idempotencyKey })

      let taskId = state.taskId
      if (!taskId) {
        const task = await createTask(
          projectId,
          { idempotencyKey, prompt: state.prompt.trim() },
          { signal: controller.signal },
        )
        taskId = task.id
        activeTaskId.current = taskId
        dispatch({
          type: 'TASK_CREATED',
          taskId,
          projectId,
          idempotencyKey,
        })
      }

      for (const file of state.files) {
        if (file.status === 'uploaded') {
          continue
        }
        if (!file.file) {
          throw new Error(`${file.name} 需要重新选择后才能上传。`)
        }

        dispatch({ type: 'UPLOAD_STARTED', fileId: file.id })
        try {
          const artifact = await uploadDocument(taskId, file.file, {
            signal: controller.signal,
          })
          dispatch({
            type: 'UPLOAD_SUCCEEDED',
            fileId: file.id,
            artifactId: artifact.id,
          })
        } catch (error) {
          if (!controller.signal.aborted) {
            const message = userFacingError(error)
            dispatch({ type: 'UPLOAD_FAILED', fileId: file.id, error: message })
          }
          throw error
        }
      }

      const started = await startTask(taskId, { signal: controller.signal })
      dispatch({ type: 'TASK_STARTED', status: started.status })
    } catch (error) {
      if (!controller.signal.aborted) {
        dispatch({ type: 'SUBMIT_FAILED', error: userFacingError(error) })
      }
    } finally {
      if (submissionController.current === controller) {
        submissionController.current = null
      }
    }
  }

  const handleClarificationSubmit = async () => {
    const answer = state.clarificationAnswer.trim()
    if (!state.taskId || !answer || state.submitting) {
      dispatch({ type: 'CLARIFICATION_SUBMIT_STARTED' })
      return
    }

    const controller = new AbortController()
    submissionController.current?.abort()
    submissionController.current = controller
    dispatch({ type: 'CLARIFICATION_SUBMIT_STARTED' })

    try {
      await answerClarification(state.taskId, answer, {
        signal: controller.signal,
      })
      dispatch({ type: 'CLARIFICATION_SUBMITTED' })
    } catch (error) {
      if (!controller.signal.aborted) {
        dispatch({ type: 'SUBMIT_FAILED', error: userFacingError(error) })
      }
    } finally {
      if (submissionController.current === controller) {
        submissionController.current = null
      }
    }
  }

  const handleCancel = async () => {
    const taskId = activeTaskId.current
    const restartSubmission = !state.startRequested
    submissionController.current?.abort()
    dispatch({ type: 'CANCEL_REQUESTED' })
    if (!taskId) {
      dispatch({ type: 'CANCEL_CONFIRMED', restartSubmission: true })
      return
    }

    try {
      await cancelTask(taskId)
      if (restartSubmission) {
        activeTaskId.current = null
      }
      dispatch({ type: 'CANCEL_CONFIRMED', restartSubmission })
    } catch (error) {
      dispatch({ type: 'CANCEL_FAILED', error: userFacingError(error) })
    }
  }

  const handleCheckTask = async () => {
    const taskId = activeTaskId.current
    if (!taskId || checkingTask) {
      return
    }

    const controller = new AbortController()
    statusCheckController.current?.abort()
    statusCheckController.current = controller
    taskTrackingController.current?.abort()
    setCheckingTask(true)
    let shouldResumeTracking = true
    try {
      const snapshot = await getTask(taskId, { signal: controller.signal })
      dispatch({ type: 'TASK_STATUS_RECEIVED', status: snapshot.status })
      if (snapshot.status === 'awaiting_input') {
        const clarification = await getClarification(taskId, {
          signal: controller.signal,
        })
        dispatch({
          type: 'CLARIFICATION_RECEIVED',
          question: clarification.question,
        })
      }
      dispatch({
        type: 'CONNECTION_CHANGED',
        connection: TERMINAL_STATUSES.has(snapshot.status)
          ? 'disconnected'
          : 'connected',
      })
      shouldResumeTracking = !TERMINAL_STATUSES.has(snapshot.status)
    } catch (error) {
      if (!controller.signal.aborted) {
        dispatch({ type: 'CONNECTION_CHANGED', connection: 'error' })
        dispatch({ type: 'INPUT_ERROR', error: userFacingError(error) })
      }
    } finally {
      if (statusCheckController.current === controller) {
        statusCheckController.current = null
        setCheckingTask(false)
      }
      if (shouldResumeTracking && !controller.signal.aborted) {
        setTrackingGeneration((generation) => generation + 1)
      }
    }
  }

  const canAttachFiles =
    !state.startRequested && !state.submitting && state.status !== 'running'

  const dragContainsFiles = (event: DragEvent<HTMLDivElement>) =>
    Array.from(event.dataTransfer.types).includes('Files')

  const handleFileDragEnter = (event: DragEvent<HTMLDivElement>) => {
    if (!dragContainsFiles(event)) {
      return
    }
    event.preventDefault()
    if (!canAttachFiles) {
      return
    }
    fileDragDepth.current += 1
    setIsFileDragging(true)
  }

  const handleFileDragOver = (event: DragEvent<HTMLDivElement>) => {
    if (!dragContainsFiles(event)) {
      return
    }
    event.preventDefault()
    event.dataTransfer.dropEffect = canAttachFiles ? 'copy' : 'none'
  }

  const handleFileDragLeave = (event: DragEvent<HTMLDivElement>) => {
    if (!dragContainsFiles(event)) {
      return
    }
    event.preventDefault()
    fileDragDepth.current = Math.max(0, fileDragDepth.current - 1)
    if (fileDragDepth.current === 0) {
      setIsFileDragging(false)
    }
  }

  const handleFileDrop = (event: DragEvent<HTMLDivElement>) => {
    if (!dragContainsFiles(event)) {
      return
    }
    event.preventDefault()
    fileDragDepth.current = 0
    setIsFileDragging(false)
    if (!canAttachFiles) {
      return
    }

    const dropped = Array.from(event.dataTransfer.files)
    if (dropped.length === 0) {
      return
    }

    const selection = selectAgentFiles(dropped)
    if (selection.error !== null) {
      dispatch({ type: 'INPUT_ERROR', error: selection.error })
      return
    }
    dispatch({ type: 'ADD_FILES', files: selection.files })
  }

  const handleReset = async () => {
    submissionController.current?.abort()
    const taskId = activeTaskId.current
    if (
      taskId &&
      state.backendStatus &&
      !TERMINAL_STATUSES.has(state.backendStatus)
    ) {
      try {
        await cancelTask(taskId)
      } catch (error) {
        dispatch({ type: 'SUBMIT_FAILED', error: userFacingError(error) })
        return
      }
    }
    activeTaskId.current = null
    dispatch({ type: 'RESET' })
  }

  return (
    <div
      className="agent-app"
      data-drop-active={isFileDragging}
      onDragEnter={handleFileDragEnter}
      onDragOver={handleFileDragOver}
      onDragLeave={handleFileDragLeave}
      onDrop={handleFileDrop}
    >
      <a className="skip-link" href="#agent-main">
        跳到主要内容
      </a>

      <header className="agent-header">
        <div className="agent-brand">
          <span className="brand-mark" aria-hidden="true">
            <Hexagon />
          </span>
          <div>
            <h1>ThermalForge</h1>
            <span>THERMAL DESIGN AGENT</span>
          </div>
        </div>

        <div className="project-identity" aria-label="当前设计">
          <span>{state.taskId ? `TASK ${state.taskId.slice(0, 8)}` : 'NEW STUDY'}</span>
          <strong>机器人关节热增强</strong>
        </div>

        <div className="header-actions">
          <span className={`session-status is-${statusClass}`} role="status">
            <i aria-hidden="true" />
            {statusLabel}
          </span>
          {state.status !== 'idle' || state.taskId ? (
            <button
              className="new-session-button"
              type="button"
              onClick={() => void handleReset()}
            >
              <Plus aria-hidden="true" />
              <span>新建设计</span>
            </button>
          ) : null}
        </div>
      </header>

      <main id="agent-main" className="agent-main">
        <div className="stage-readout" aria-live="polite">
          <span>
            {currentStageIndex >= 0
              ? String(currentStageIndex + 1).padStart(2, '0')
              : '00'}
          </span>
          <strong>{stageLabel}</strong>
          <span>{state.progress}%</span>
        </div>

        <Suspense
          fallback={
            <section
              className="model-stage model-stage-loading"
              aria-label="三维关节模型"
            >
              <span aria-hidden="true" />
              <p>正在初始化三维场景</p>
            </section>
          }
        >
          {displayedViewerManifest ? (
            <ModelStage
              manifest={displayedViewerManifest}
              isExploded={state.isExploded}
              selectedPart={state.selectedPart}
              onToggleExploded={() => dispatch({ type: 'TOGGLE_EXPLODED' })}
              onSelectPart={handleSelectPart}
            />
          ) : (
            <section
              className="model-stage model-stage-unavailable"
              aria-label="任务三维模型"
              role={viewerManifestStatus === 'error' ? 'alert' : 'status'}
            >
              <div>
                <span className="eyebrow">TASK MODEL</span>
                <p>
                  {viewerManifestError ?? '正在加载任务模型与分件清单…'}
                </p>
                {viewerManifestStatus === 'error' ? (
                  <button
                    type="button"
                    onClick={() =>
                      setViewerManifestReload((version) => version + 1)
                    }
                  >
                    重新加载模型
                  </button>
                ) : null}
              </div>
            </section>
          )}
        </Suspense>

        {state.status === 'ready' ? <ResultShowcase /> : null}

        <div className="agent-dialogue-layer">
          <AgentConversation
            messages={getLatestMessages(state)}
            onOpenHistory={() => dispatch({ type: 'TOGGLE_HISTORY' })}
          />

          <AgentStalledNotice
            active={
              state.status === 'running' &&
              state.startRequested &&
              !state.submitting &&
              !state.cancelRequested &&
              !hasTerminalBackendStatus
            }
            progressKey={`${state.taskId ?? 'none'}:${state.backendStatus ?? 'none'}:${state.lastEventId ?? 'none'}:${state.progress}`}
            checking={checkingTask}
            onCheck={() => void handleCheckTask()}
            onCancel={() => void handleCancel()}
          />

          <div
            className="stage-progress"
            role="progressbar"
            aria-label="生成进度"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={state.progress}
          >
            <span style={{ width: `${state.progress}%` }} />
          </div>

          <AgentComposer
            prompt={state.prompt}
            files={state.files}
            status={state.status}
            submitting={state.submitting}
            cancelRequested={state.cancelRequested}
            attachmentsLocked={state.startRequested}
            isDropActive={isFileDragging}
            clarificationQuestion={state.clarificationQuestion}
            clarificationAnswer={state.clarificationAnswer}
            inputError={state.inputError}
            onPromptChange={(prompt) =>
              dispatch({ type: 'SET_PROMPT', prompt })
            }
            onFilesChange={(files) => dispatch({ type: 'SET_FILES', files })}
            onClarificationAnswerChange={(answer) =>
              dispatch({ type: 'SET_CLARIFICATION_ANSWER', answer })
            }
            onStart={() =>
              state.status === 'ready'
                ? void handleReset()
                : void handleStart()
            }
            onClarificationSubmit={() => void handleClarificationSubmit()}
            onCancel={() => void handleCancel()}
          />
        </div>

        <AgentHistoryDrawer
          isOpen={state.isHistoryOpen}
          messages={state.messages}
          currentStageId={state.stage}
          results={taskResults}
          resultsError={taskResultsError}
          resultsLoading={taskResultsLoading}
          imageManifest={taskImageManifest}
          imagesError={taskImagesError}
          imagesLoading={taskImagesLoading}
          viewerManifest={taskViewerManifest}
          onRetryResults={() =>
            setTaskResultsReload((version) => version + 1)
          }
          onRetryImages={() =>
            setTaskImagesReload((version) => version + 1)
          }
          onClose={() => dispatch({ type: 'CLOSE_HISTORY' })}
        />

        {displayedViewerManifest ? (
          <PartDetailSheet
            manifest={displayedViewerManifest}
            part={state.selectedPart}
            onClose={() => handleSelectPart(null)}
          />
        ) : null}
      </main>

      {isFileDragging ? (
        <div className="file-drop-overlay" aria-hidden="true">
          <div className="file-drop-overlay-card">
            <CloudUpload aria-hidden="true" />
            <strong>松开即可上传工程资料</strong>
            <span>支持 PDF、DOCX、TXT、Markdown、PNG、JPG、WebP，单个 ≤ 20MB</span>
          </div>
        </div>
      ) : null}
    </div>
  )
}

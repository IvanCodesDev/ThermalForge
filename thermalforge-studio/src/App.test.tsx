import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const apiMocks = vi.hoisted(() => ({
  answerClarification: vi.fn(),
  cancelTask: vi.fn(),
  createIdempotencyKey: vi.fn(),
  createProject: vi.fn(),
  createTask: vi.fn(),
  getClarification: vi.fn(),
  getEngineeringBrief: vi.fn(),
  getTaskImageManifest: vi.fn(),
  getTask: vi.fn(),
  getThermalAnalysis: vi.fn(),
  getThermalDesign: vi.fn(),
  getViewerLibrary: vi.fn(),
  getViewerManifest: vi.fn(),
  retryTask: vi.fn(),
  startTask: vi.fn(),
  streamTaskEvents: vi.fn(),
  uploadDocument: vi.fn(),
}))

vi.mock('./api', async (importOriginal) => {
  const original = await importOriginal<typeof import('./api')>()
  return { ...original, ...apiMocks }
})

vi.mock('./model/ModelStage', () => ({
  ModelStage: ({
    manifest,
    isExploded,
    onToggleExploded,
  }: {
    manifest: { name: string; variants?: Array<{ id: string; label: string }> }
    isExploded: boolean
    onToggleExploded: () => void
  }) => (
    <section aria-label="三维关节模型">
      <span>{manifest.name}</span>
      {manifest.variants?.map((variant) => (
        <span key={variant.id}>{variant.label}</span>
      ))}
      <button type="button" onClick={onToggleExploded}>
        {isExploded ? '合并模型' : '爆炸模型'}
      </button>
    </section>
  ),
}))

const PROJECT = {
  id: 'project-1',
  name: '机器人关节热增强',
  created_at: '2026-07-11T00:00:00Z',
}

const UPLOADED_TASK = {
  id: 'task-1',
  project_id: PROJECT.id,
  status: 'uploaded',
  stage: 'uploaded',
  prompt: '降低机器人关节热点温度',
  idempotency_key: 'request-1',
  created_at: '2026-07-11T00:00:00Z',
  updated_at: '2026-07-11T00:00:01Z',
}

const ARTIFACT = {
  id: 'artifact-1',
  task_id: UPLOADED_TASK.id,
  kind: 'source_document',
  version: 1,
  mime_type: 'text/plain',
  sha256: 'abc',
  size_bytes: 12,
  storage_uri: 'local://requirements.txt',
  metadata: {},
  quality_status: 'approved',
  created_at: '2026-07-11T00:00:01Z',
}

const CLARIFICATION = {
  id: 'clarification-1',
  task_id: UPLOADED_TASK.id,
  field_key: 'maximum_temperature_c',
  question: '允许的最高壳体温度是多少？',
  answer: null,
  created_at: '2026-07-11T00:00:02Z',
  answered_at: null,
}

const VIEWER_MANIFEST = {
  schema_version: '1.0' as const,
  task_id: UPLOADED_TASK.id,
  asset: {
    artifact_id: 'model-1',
    kind: 'normalized_model' as const,
    url: `/v1/tasks/${UPLOADED_TASK.id}/models/model-1/content`,
    format: 'glb' as const,
    mime_type: 'model/gltf-binary',
    sha256: '1234567890abcdef',
    size_bytes: 4096,
    transform: {
      translation: [0, 0, 0] as [number, number, number],
      rotation: [0, 0, 0, 1] as [number, number, number, number],
      scale: [1, 1, 1] as [number, number, number],
    },
  },
}

const VIEWER_LIBRARY = {
  schema_version: '1.0' as const,
  models: [
    {
      id: 'foc-segmented',
      label: 'FOC 机械臂 · 分件参考',
      description: 'Bang 分件概念网格',
      asset: {
        artifact_id: 'foc-segmented',
        kind: 'normalized_model' as const,
        url: '/v1/viewer-library/foc-segmented/content',
        format: 'glb' as const,
        mime_type: 'model/gltf-binary',
        sha256: 'aaa',
        size_bytes: 4096,
      },
      supports_explosion: true,
      parts: [],
      notices: ['概念网格，不是可制造 CAD。'],
    },
    {
      id: 'foc-whole',
      label: 'FOC 机械臂 · 整体参考',
      description: '整体概念网格',
      asset: {
        artifact_id: 'foc-whole',
        kind: 'raw_model' as const,
        url: '/v1/viewer-library/foc-whole/content',
        format: 'glb' as const,
        mime_type: 'model/gltf-binary',
        sha256: 'bbb',
        size_bytes: 8192,
      },
      supports_explosion: false,
      parts: [],
      notices: ['概念网格，不是可制造 CAD。'],
    },
    {
      id: 'hyper3d-original',
      label: 'Hyper3D 机械臂 · 原始概念',
      description: 'Hyper3D 原始概念网格',
      asset: {
        artifact_id: 'hyper3d-original',
        kind: 'raw_model' as const,
        url: '/v1/viewer-library/hyper3d-original/content',
        format: 'glb' as const,
        mime_type: 'model/gltf-binary',
        sha256: 'ccc',
        size_bytes: 12288,
      },
      supports_explosion: false,
      parts: [],
      notices: ['概念网格，不是可制造 CAD。'],
    },
  ],
}

const TASK_IMAGE_MANIFEST = {
  schema_version: '1.0' as const,
  task_id: UPLOADED_TASK.id,
  images: [
    'mother_three_quarter',
    'front',
    'left',
    'rear',
    'top',
    'elbow_section',
  ].map((viewId, index) => ({
    artifact_id: `image-${index + 1}`,
    kind: index === 0 ? ('concept_image' as const) : ('multiview_image' as const),
    view_id: viewId,
    url: `/v1/tasks/${UPLOADED_TASK.id}/images/image-${index + 1}/content`,
    mime_type: 'image/png' as const,
    sha256: `${index}`.repeat(64),
    size_bytes: 4096,
    provider: 'openai_compatible',
    provider_model: 'gpt-image-2',
  })),
  notice: '概念图用于方案沟通，不是 CAD、CFD、FEA 或制造验证结果。',
}

const ENGINEERING_BRIEF = {
  project_title: '机器人关节热增强',
  heat_sources: [{ name: '电机', power_w: 120 }],
  overall_confidence: 1,
}

const THERMAL_ANALYSIS = {
  source: 'engineering-estimate',
  baseline: {
    maxTemperatureC: 96,
    timeToLimitMinutes: 18,
  },
  riskLevel: 'High',
  warnings: ['筛选结果尚未经过样机校准'],
}

const THERMAL_DESIGN = {
  selected_solution: {
    title: '叶脉扩散外壳',
    max_temperature_c: 72,
    hotspot_reduction_c: 24,
  },
  rationale: '降低热点并保持原厂安装孔位。',
  heat_transfer_path: ['电机', '导热环', '扩散外壳', '环境空气'],
  material_recommendations: ['6061-T6 铝合金'],
  assumptions: [],
  risks: [
    {
      description: '接触热阻尚未实测',
      recommended_action: '完成样机温升复测',
    },
  ],
  unverified_items: ['动态干涉'],
  requires_human_confirmation: true,
}

async function* waitForAbort(
  _taskId: string,
  options: {
    onConnectionChange?: (state: 'connected') => void
    signal?: AbortSignal
  } = {},
) {
  options.onConnectionChange?.('connected')
  await new Promise<void>((resolve) => {
    if (options.signal?.aborted) {
      resolve()
      return
    }
    options.signal?.addEventListener('abort', () => resolve(), { once: true })
  })
  if (!options.signal?.aborted) {
    yield { id: '', type: 'keepalive', payload: null }
  }
}

async function submitDocumentRequest(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(
    screen.getByLabelText('上传工程文档'),
    new File(['Power 120 W'], 'requirements.txt', { type: 'text/plain' }),
  )
  await user.type(
    screen.getByRole('textbox', { name: '设计目标' }),
    '降低机器人关节热点温度',
  )
  await user.click(screen.getByRole('button', { name: '开始生成' }))
}

describe('ThermalForge Agent experience', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    apiMocks.createIdempotencyKey.mockReturnValue('request-1')
    apiMocks.createProject.mockResolvedValue(PROJECT)
    apiMocks.createTask.mockResolvedValue({
      ...UPLOADED_TASK,
      status: 'created',
      stage: 'created',
    })
    apiMocks.uploadDocument.mockResolvedValue(ARTIFACT)
    apiMocks.startTask.mockResolvedValue(UPLOADED_TASK)
    apiMocks.getTask.mockResolvedValue(UPLOADED_TASK)
    apiMocks.getClarification.mockResolvedValue(CLARIFICATION)
    apiMocks.getEngineeringBrief.mockResolvedValue(ENGINEERING_BRIEF)
    apiMocks.getTaskImageManifest.mockResolvedValue(TASK_IMAGE_MANIFEST)
    apiMocks.getThermalAnalysis.mockResolvedValue(THERMAL_ANALYSIS)
    apiMocks.getThermalDesign.mockResolvedValue(THERMAL_DESIGN)
    apiMocks.getViewerLibrary.mockResolvedValue(VIEWER_LIBRARY)
    apiMocks.getViewerManifest.mockResolvedValue(VIEWER_MANIFEST)
    apiMocks.answerClarification.mockResolvedValue({
      ...CLARIFICATION,
      answer: '最高 70 摄氏度',
      answered_at: '2026-07-11T00:00:03Z',
    })
    apiMocks.cancelTask.mockResolvedValue({
      ...UPLOADED_TASK,
      status: 'cancelled',
      stage: 'cancelled',
    })
    apiMocks.retryTask.mockResolvedValue(UPLOADED_TASK)
    apiMocks.streamTaskEvents.mockImplementation(waitForAbort)
  })

  it('opens on the model-first Agent screen', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { name: 'ThermalForge' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('region', { name: '三维关节模型' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('textbox', { name: '设计目标' }),
    ).toBeInTheDocument()
  })

  it('loads the distinct curated models instead of leaving Wall-E as default', async () => {
    render(<App />)

    expect(await screen.findByText('案例模型库')).toBeInTheDocument()
    expect(screen.getByText('FOC 机械臂 · 分件参考')).toBeInTheDocument()
    expect(screen.getByText('FOC 机械臂 · 整体参考')).toBeInTheDocument()
    expect(screen.getByText('Hyper3D 机械臂 · 原始概念')).toBeInTheDocument()
    expect(apiMocks.getViewerLibrary).toHaveBeenCalledOnce()
  })

  it('attaches an engineering file dropped anywhere on the workspace', () => {
    render(<App />)

    const workspace = screen.getByRole('main')
    const dropped = new File(['Power 120 W'], 'foc-case.md', {
      type: 'text/markdown',
      lastModified: 5678,
    })

    fireEvent.dragEnter(workspace, {
      dataTransfer: { files: [dropped], types: ['Files'] },
    })
    expect(screen.getByText('松开即可上传工程资料')).toBeInTheDocument()

    fireEvent.drop(workspace, {
      dataTransfer: { files: [dropped], types: ['Files'] },
    })

    expect(screen.getByText('foc-case.md')).toBeInTheDocument()
    expect(screen.queryByText('松开即可上传工程资料')).not.toBeInTheDocument()
  })

  it('rejects an unsupported file dropped on the workspace', () => {
    render(<App />)

    fireEvent.drop(screen.getByRole('main'), {
      dataTransfer: {
        files: [new File(['binary'], 'unsafe.exe')],
        types: ['Files'],
      },
    })

    expect(screen.getByRole('alert')).toHaveTextContent(
      'unsafe.exe 不受支持或超过 20MB',
    )
    expect(screen.queryByText('unsafe.exe')).not.toBeInTheDocument()
  })

  it('requires a source document before creating a backend task', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.type(
      screen.getByRole('textbox', { name: '设计目标' }),
      '降低机器人关节热点温度',
    )
    await user.click(screen.getByRole('button', { name: '开始生成' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('至少一份工程文档')
    expect(apiMocks.createProject).not.toHaveBeenCalled()
  })

  it('creates, uploads, and explicitly starts in the required order', async () => {
    const user = userEvent.setup()
    render(<App />)

    await submitDocumentRequest(user)
    await waitFor(() => expect(apiMocks.startTask).toHaveBeenCalledWith(
      UPLOADED_TASK.id,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    ))

    const calls = [
      apiMocks.createProject,
      apiMocks.createTask,
      apiMocks.uploadDocument,
      apiMocks.startTask,
    ].map((mock) => mock.mock.invocationCallOrder[0])
    expect(calls).toEqual([...calls].sort((left, right) => left - right))
    expect(apiMocks.createTask).toHaveBeenCalledWith(
      PROJECT.id,
      {
        idempotencyKey: 'request-1',
        prompt: '降低机器人关节热点温度',
      },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(apiMocks.uploadDocument.mock.calls[0]?.[1]).toBeInstanceOf(File)
    expect(screen.getByText('requirements.txt').closest('.composer-file')).toHaveAttribute(
      'data-status',
      'uploaded',
    )
    expect(screen.getByRole('button', { name: '停止生成' })).toBeInTheDocument()
  })

  it('records real SSE milestones in the history', async () => {
    apiMocks.streamTaskEvents.mockImplementation(async function* () {
      yield {
        id: '4',
        type: 'engineering_brief.completed',
        payload: { status: 'thermal_analysis' },
      }
    })
    const user = userEvent.setup()
    render(<App />)

    await submitDocumentRequest(user)
    await screen.findByText('工程约束已建立，正在执行筛选级热分析。')
    await user.click(screen.getByRole('button', { name: '查看全部对话' }))

    const history = screen.getByRole('dialog', { name: '完整对话' })
    expect(within(history).getByText(/工程约束已建立/)).toBeInTheDocument()
  })

  it('replaces the local model with the approved backend task model', async () => {
    apiMocks.getTask.mockResolvedValue({
      ...UPLOADED_TASK,
      status: 'ready',
      stage: 'ready',
    })
    const user = userEvent.setup()
    render(<App />)

    expect(screen.getByText('Wall-E CAD 装配')).toBeInTheDocument()
    await submitDocumentRequest(user)

    expect(
      await screen.findByText('任务工程模型 · GLB'),
    ).toBeInTheDocument()
    expect(apiMocks.getViewerManifest).toHaveBeenCalledWith(
      UPLOADED_TASK.id,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('shows the deliverable media showcase when the task is ready', async () => {
    apiMocks.getTask.mockResolvedValue({
      ...UPLOADED_TASK,
      status: 'ready',
      stage: 'ready',
    })
    const user = userEvent.setup()
    render(<App />)

    await submitDocumentRequest(user)

    const showcase = await screen.findByRole('region', { name: '成果展示' })
    expect(
      within(showcase).getByAltText('机器人关节热增强外壳样机实物照片'),
    ).toBeInTheDocument()
    expect(within(showcase).getByText('样机实物')).toBeInTheDocument()
    expect(within(showcase).getByText('装配演示')).toBeInTheDocument()
  })

  it('loads task evidence and sanitized backend output for a ready task', async () => {
    apiMocks.getTask.mockResolvedValue({
      ...UPLOADED_TASK,
      status: 'ready',
      stage: 'ready',
    })
    const user = userEvent.setup()
    render(<App />)

    await submitDocumentRequest(user)
    await waitFor(() =>
      expect(apiMocks.getThermalDesign).toHaveBeenCalledWith(
        UPLOADED_TASK.id,
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    )
    await user.click(screen.getByRole('button', { name: '查看全部对话' }))
    const history = screen.getByRole('dialog', { name: '完整对话' })

    await user.click(
      within(history).getByRole('button', { name: '设计依据' }),
    )
    expect(within(history).getByText('叶脉扩散外壳')).toBeInTheDocument()
    expect(
      within(history).getByText('电机 → 导热环 → 扩散外壳 → 环境空气'),
    ).toBeInTheDocument()
    expect(within(history).getByText('接触热阻尚未实测')).toBeInTheDocument()

    await user.click(
      within(history).getByRole('button', { name: '概念图' }),
    )
    expect(
      within(history).getByRole('img', { name: '母图三季度视角' }),
    ).toHaveAttribute(
      'src',
      expect.stringContaining('/images/image-1/content'),
    )
    expect(within(history).getAllByRole('img')).toHaveLength(6)
    expect(within(history).getByText('GPT Image 2 · 六视图')).toBeInTheDocument()

    await user.click(
      within(history).getByRole('button', { name: '后端输出' }),
    )
    expect(
      within(history).getByText(/"project_title": "机器人关节热增强"/),
    ).toBeInTheDocument()
    expect(within(history).queryByText(/api_key/i)).not.toBeInTheDocument()
  })

  it('loads the current clarification and posts an independent answer', async () => {
    let backendStatus = 'uploaded'
    apiMocks.getTask.mockImplementation(async () => ({
      ...UPLOADED_TASK,
      status: backendStatus,
      stage: backendStatus,
    }))
    apiMocks.answerClarification.mockImplementationOnce(async () => {
      backendStatus = 'briefing'
      return {
        ...CLARIFICATION,
        answer: '最高 70 摄氏度',
        answered_at: '2026-07-11T00:00:03Z',
      }
    })
    apiMocks.streamTaskEvents
      .mockImplementationOnce(async function* () {
        backendStatus = 'awaiting_input'
        yield {
          id: '4',
          type: 'engineering_brief.clarification_required',
          payload: { status: 'awaiting_input' },
        }
      })
      .mockImplementation(waitForAbort)
    const user = userEvent.setup()
    render(<App />)

    await submitDocumentRequest(user)

    expect((await screen.findAllByText(CLARIFICATION.question)).length).toBeGreaterThan(0)
    expect(apiMocks.getClarification).toHaveBeenCalledWith(
      UPLOADED_TASK.id,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )

    await user.type(
      screen.getByRole('textbox', { name: '补充信息' }),
      '最高 70 摄氏度',
    )
    await user.click(screen.getByRole('button', { name: '提交补充信息' }))

    await waitFor(() =>
      expect(apiMocks.answerClarification).toHaveBeenCalledWith(
        UPLOADED_TASK.id,
        '最高 70 摄氏度',
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    )
    expect(
      screen.queryByRole('textbox', { name: '补充信息' }),
    ).not.toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: '设计目标' })).toHaveValue(
      '降低机器人关节热点温度',
    )
  })

  it('rebuilds a cancelled in-flight submission before uploading again', async () => {
    const secondTask = {
      ...UPLOADED_TASK,
      id: 'task-2',
      idempotency_key: 'request-2',
    }
    apiMocks.createIdempotencyKey
      .mockReturnValueOnce('request-1')
      .mockReturnValueOnce('request-2')
    apiMocks.createTask
      .mockResolvedValueOnce({
        ...UPLOADED_TASK,
        status: 'created',
        stage: 'created',
      })
      .mockResolvedValueOnce({
        ...secondTask,
        status: 'created',
        stage: 'created',
      })
    apiMocks.uploadDocument
      .mockImplementationOnce(
        (
          _taskId: string,
          _file: File,
          options: { signal?: AbortSignal } = {},
        ) =>
          new Promise((_resolve, reject) => {
            const abort = () =>
              reject(new DOMException('The upload was cancelled.', 'AbortError'))
            if (options.signal?.aborted) {
              abort()
              return
            }
            options.signal?.addEventListener('abort', abort, { once: true })
          }),
      )
      .mockResolvedValueOnce({
        ...ARTIFACT,
        id: 'artifact-2',
        task_id: secondTask.id,
      })
    apiMocks.startTask.mockResolvedValueOnce(secondTask)
    const user = userEvent.setup()
    render(<App />)

    await submitDocumentRequest(user)
    await waitFor(() => expect(apiMocks.uploadDocument).toHaveBeenCalledTimes(1))
    await user.click(screen.getByRole('button', { name: '停止生成' }))

    await waitFor(() =>
      expect(apiMocks.cancelTask).toHaveBeenCalledWith(UPLOADED_TASK.id),
    )
    expect(apiMocks.retryTask).not.toHaveBeenCalled()
    await user.click(await screen.findByRole('button', { name: '开始生成' }))

    await waitFor(() => expect(apiMocks.createTask).toHaveBeenCalledTimes(2))
    expect(apiMocks.createTask).toHaveBeenLastCalledWith(
      PROJECT.id,
      expect.objectContaining({ idempotencyKey: 'request-2' }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    await waitFor(() =>
      expect(apiMocks.uploadDocument).toHaveBeenLastCalledWith(
        secondTask.id,
        expect.any(File),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    )
    await waitFor(() =>
      expect(apiMocks.startTask).toHaveBeenCalledWith(
        secondTask.id,
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    )
    expect(apiMocks.retryTask).not.toHaveBeenCalled()
  })

  it('keeps the task running when cancellation is not confirmed', async () => {
    apiMocks.cancelTask.mockRejectedValueOnce(new Error('取消服务不可用'))
    const user = userEvent.setup()
    render(<App />)

    await submitDocumentRequest(user)
    await waitFor(() => expect(apiMocks.startTask).toHaveBeenCalled())
    await screen.findByRole('button', { name: '停止生成' })
    await user.click(screen.getByRole('button', { name: '停止生成' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('取消服务不可用')
    expect(screen.queryByText('生成已暂停')).not.toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('生成中')
    expect(screen.getByRole('button', { name: '停止生成' })).toBeEnabled()
  })

  it('waits for retry confirmation before resuming task tracking', async () => {
    let resolveRetry:
      | ((task: typeof UPLOADED_TASK) => void)
      | undefined
    apiMocks.retryTask.mockImplementationOnce(
      () =>
        new Promise<typeof UPLOADED_TASK>((resolve) => {
          resolveRetry = resolve
        }),
    )
    const user = userEvent.setup()
    render(<App />)

    await submitDocumentRequest(user)
    await waitFor(() => expect(apiMocks.getTask).toHaveBeenCalled())
    await user.click(await screen.findByRole('button', { name: '停止生成' }))
    await screen.findByRole('button', { name: '继续生成' })

    const getTaskCallsBeforeRetry = apiMocks.getTask.mock.calls.length
    const streamCallsBeforeRetry = apiMocks.streamTaskEvents.mock.calls.length
    await user.click(screen.getByRole('button', { name: '继续生成' }))
    await waitFor(() =>
      expect(apiMocks.retryTask).toHaveBeenCalledWith(
        UPLOADED_TASK.id,
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    )

    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(apiMocks.getTask).toHaveBeenCalledTimes(getTaskCallsBeforeRetry)
    expect(apiMocks.streamTaskEvents).toHaveBeenCalledTimes(
      streamCallsBeforeRetry,
    )

    expect(resolveRetry).toBeDefined()
    resolveRetry?.(UPLOADED_TASK)
    await waitFor(() =>
      expect(apiMocks.getTask.mock.calls.length).toBeGreaterThan(
        getTaskCallsBeforeRetry,
      ),
    )
    await waitFor(() =>
      expect(apiMocks.streamTaskEvents.mock.calls.length).toBeGreaterThan(
        streamCallsBeforeRetry,
      ),
    )
  })

  it('does not let a historical terminal event override the latest task snapshot', async () => {
    apiMocks.getTask.mockResolvedValue({
      ...UPLOADED_TASK,
      status: 'thermal_analysis',
      stage: 'thermal_analysis',
    })
    apiMocks.streamTaskEvents.mockImplementation(async function* () {
      yield {
        id: '4',
        type: 'task.cancelled',
        payload: { status: 'cancelled' },
      }
      yield {
        id: '5',
        type: 'engineering_brief.completed',
        payload: { status: 'thermal_analysis' },
      }
    })
    const user = userEvent.setup()
    render(<App />)

    await submitDocumentRequest(user)

    expect(
      await screen.findByText('工程约束已建立，正在执行筛选级热分析。'),
    ).toBeInTheDocument()
    expect(screen.queryByText('生成已暂停')).not.toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('生成中')
    expect(screen.getByText('52%')).toBeInTheDocument()
  })

  it('cancels the backend task without discarding the request', async () => {
    const user = userEvent.setup()
    render(<App />)

    await submitDocumentRequest(user)
    await waitFor(() => expect(apiMocks.startTask).toHaveBeenCalled())
    await screen.findByRole('button', { name: '停止生成' })
    await user.click(screen.getByRole('button', { name: '停止生成' }))

    await waitFor(() =>
      expect(apiMocks.cancelTask).toHaveBeenCalledWith(UPLOADED_TASK.id),
    )
    expect(screen.getByText('生成已暂停')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: '设计目标' })).toHaveValue(
      '降低机器人关节热点温度',
    )
  })
})

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  ApiError,
  answerClarification,
  createTask,
  getClarification,
  startTask,
  streamTaskEvents,
  uploadDocument,
} from '.'

const encoder = new TextEncoder()

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
    status,
  })
}

function eventResponse(chunks: Array<string>): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk))
      }
      controller.close()
    },
  })
  return new Response(stream, {
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('workflow API', () => {
  it('uses the generated task SDK contract and caller-provided idempotency key', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({
        created_at: '2026-07-11T00:00:00Z',
        id: 'task-1',
        idempotency_key: 'request-1',
        project_id: 'project-1',
        prompt: 'Cool a robot joint',
        stage: 'created',
        status: 'created',
        updated_at: '2026-07-11T00:00:00Z',
      }, 201),
    )
    vi.stubGlobal('fetch', fetchMock)

    const task = await createTask('project-1', {
      idempotencyKey: 'request-1',
      prompt: 'Cool a robot joint',
    })

    expect(task.id).toBe('task-1')
    const request = fetchMock.mock.calls[0]?.[0]
    expect(request).toBeInstanceOf(Request)
    expect((request as Request).url).toContain('/v1/projects/project-1/tasks')
    expect((request as Request).headers.get('Idempotency-Key')).toBe('request-1')
  })

  it('uploads multipart files without setting a JSON content type', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({
        created_at: '2026-07-11T00:00:00Z',
        id: 'artifact-1',
        kind: 'source_document',
        metadata: {},
        mime_type: 'text/plain',
        quality_status: 'pending',
        sha256: 'abc',
        size_bytes: 4,
        storage_uri: 'local://source.txt',
        task_id: 'task-1',
        version: 1,
      }, 201),
    )
    vi.stubGlobal('fetch', fetchMock)

    await uploadDocument('task-1', new File(['test'], 'input.txt'))

    const request = fetchMock.mock.calls[0]?.[0] as Request
    expect(request.body).not.toBeNull()
    expect(request.headers.get('Content-Type')).toContain('multipart/form-data; boundary=')
  })

  it('normalizes domain errors from the generated SDK', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>().mockResolvedValue(
        jsonResponse({
          code: 'source_document_required',
          message: 'Upload a source document first.',
          retryable: false,
          trace_id: 'trace-1',
        }, 409),
      ),
    )

    const error = await startTask('task-1').catch((reason: unknown) => reason)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      code: 'source_document_required',
      message: 'Upload a source document first.',
      retryable: false,
      status: 409,
      traceId: 'trace-1',
    })
  })

  it('loads and answers the current clarification through the generated contract', async () => {
    const clarification = {
      answer: null,
      answered_at: null,
      created_at: '2026-07-11T00:00:00Z',
      field_key: 'ambient_temperature',
      id: 'clarification-1',
      question: '最高环境温度是多少？',
      task_id: 'task-1',
    }
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(clarification))
      .mockResolvedValueOnce(
        jsonResponse({
          ...clarification,
          answer: '45 摄氏度',
          answered_at: '2026-07-11T00:01:00Z',
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    await expect(getClarification('task-1')).resolves.toMatchObject({
      id: 'clarification-1',
      question: '最高环境温度是多少？',
    })
    await expect(
      answerClarification('task-1', '45 摄氏度'),
    ).resolves.toMatchObject({ answer: '45 摄氏度' })

    const answerRequest = fetchMock.mock.calls[1]?.[0] as Request
    expect(answerRequest.method).toBe('POST')
    await expect(answerRequest.clone().json()).resolves.toEqual({
      answer: '45 摄氏度',
    })
  })

})

describe('task event stream', () => {
  it('parses chunked events, reconnects from Last-Event-ID, and filters duplicates', async () => {
    const requests: Array<RequestInit | undefined> = []
    const connectionChanges: Array<string> = []
    const fetchMock = vi.fn<typeof fetch>(async (_input, init) => {
      requests.push(init)
      if (requests.length === 1) {
        return eventResponse([
          ': keepalive\r',
          '\nid: 1\r\nevent: stage.started\r\ndata: {"stage":',
          '\r\ndata: "briefing"}\r\n\r\nid: 2\nevent: stage.completed\ndata: {"ok":true}\n\n',
        ])
      }
      return eventResponse([
        'id: 2\nevent: stage.completed\ndata: {"ok":true}\n\n',
        'id: 3\nevent: task.ready\ndata: {"artifactId":"result-1"}\n\n',
      ])
    })
    const controller = new AbortController()
    const events = streamTaskEvents('task/with spaces', {
      fetch: fetchMock,
      onConnectionChange: (state) => connectionChanges.push(state),
      retryDelayMs: 0,
      signal: controller.signal,
    })

    await expect(events.next()).resolves.toMatchObject({
      value: { id: '1', payload: { stage: 'briefing' }, type: 'stage.started' },
    })
    await expect(events.next()).resolves.toMatchObject({
      value: { id: '2', payload: { ok: true }, type: 'stage.completed' },
    })
    await expect(events.next()).resolves.toMatchObject({
      value: {
        id: '3',
        payload: { artifactId: 'result-1' },
        type: 'task.ready',
      },
    })
    controller.abort()
    await expect(events.next()).resolves.toMatchObject({ done: true })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(new Headers(requests[1]?.headers).get('Last-Event-ID')).toBe('2')
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      '/v1/tasks/task%2Fwith%20spaces/events',
    )
    expect(connectionChanges).toEqual([
      'connected',
      'reconnecting',
      'connected',
    ])
  })

  it('does not reconnect non-retryable HTTP errors', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({
        code: 'task_not_found',
        message: 'Task was not found.',
        retryable: false,
      }, 404),
    )
    const events = streamTaskEvents('missing', { fetch: fetchMock, retryDelayMs: 0 })

    const error = await events.next().catch((reason: unknown) => reason)

    expect(error).toMatchObject({ code: 'task_not_found', status: 404 })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

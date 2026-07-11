import { ApiError, apiErrorFromResponse, toApiError } from './errors'
import { API_BASE_URL } from './workflow'

export interface TaskStreamEvent<TPayload = unknown> {
  id: string
  payload: TPayload
  type: string
}

export interface TaskEventStreamOptions {
  fetch?: typeof fetch
  lastEventId?: number | string
  maxRetries?: number
  maxRetryDelayMs?: number
  onConnectionChange?: (state: TaskEventConnectionState) => void
  retryDelayMs?: number
  signal?: AbortSignal
}

export type TaskEventConnectionState = 'connected' | 'reconnecting'

interface SseFrame {
  event?: TaskStreamEvent
  retry?: number
}

const DEFAULT_RETRY_DELAY_MS = 1_000
const DEFAULT_MAX_RETRY_DELAY_MS = 30_000
const REMEMBERED_EVENT_IDS = 2_048

function parsePayload(raw: string): unknown {
  try {
    return JSON.parse(raw)
  } catch {
    return raw
  }
}

async function* parseEventStream(
  stream: ReadableStream<Uint8Array>,
  initialLastEventId: string | undefined,
  signal: AbortSignal | undefined,
): AsyncGenerator<SseFrame> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let completed = false
  let dataLines: Array<string> = []
  let eventType = ''
  let eventId = initialLastEventId
  let retry: number | undefined
  let blockTouched = false

  const finishBlock = (): SseFrame | undefined => {
    if (!blockTouched) {
      return undefined
    }

    const frame: SseFrame = { retry }
    if (dataLines.length > 0) {
      frame.event = {
        id: eventId ?? '',
        payload: parsePayload(dataLines.join('\n')),
        type: eventType || 'message',
      }
    }

    dataLines = []
    eventType = ''
    retry = undefined
    blockTouched = false
    return frame
  }

  const consumeLine = (line: string): SseFrame | undefined => {
    if (line === '') {
      return finishBlock()
    }
    if (line.startsWith(':')) {
      return undefined
    }

    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) {
      value = value.slice(1)
    }

    if (field === 'data') {
      dataLines.push(value)
      blockTouched = true
    } else if (field === 'event') {
      eventType = value
      blockTouched = true
    } else if (field === 'id' && !value.includes('\0')) {
      eventId = value
      blockTouched = true
    } else if (field === 'retry' && /^\d+$/.test(value)) {
      retry = Number(value)
      blockTouched = true
    }
    return undefined
  }

  const abortReader = () => {
    void reader.cancel()
  }
  signal?.addEventListener('abort', abortReader, { once: true })

  try {
    while (!signal?.aborted) {
      const result = await reader.read()
      if (result.done) {
        completed = true
        buffer += decoder.decode()
      } else {
        buffer += decoder.decode(result.value, { stream: true })
      }

      while (buffer.length > 0) {
        const delimiter = buffer.search(/[\r\n]/)
        if (delimiter === -1) {
          if (!completed) {
            break
          }
          const frame = consumeLine(buffer)
          buffer = ''
          if (frame) {
            yield frame
          }
          break
        }

        const delimiterChar = buffer[delimiter]
        if (delimiterChar === '\r' && delimiter === buffer.length - 1 && !completed) {
          break
        }
        const delimiterLength =
          delimiterChar === '\r' && buffer[delimiter + 1] === '\n' ? 2 : 1
        const line = buffer.slice(0, delimiter)
        buffer = buffer.slice(delimiter + delimiterLength)
        const frame = consumeLine(line)
        if (frame) {
          yield frame
        }
      }

      if (completed) {
        const finalFrame = consumeLine('')
        if (finalFrame) {
          yield finalFrame
        }
        return
      }
    }
  } finally {
    signal?.removeEventListener('abort', abortReader)
    if (!completed) {
      await reader.cancel().catch(() => undefined)
    }
    reader.releaseLock()
  }
}

function rememberEventId(
  id: string,
  seenIds: Set<string>,
  idOrder: Array<string>,
): boolean {
  if (!id) {
    return true
  }
  if (seenIds.has(id)) {
    return false
  }

  seenIds.add(id)
  idOrder.push(id)
  if (idOrder.length > REMEMBERED_EVENT_IDS) {
    const expiredId = idOrder.shift()
    if (expiredId !== undefined) {
      seenIds.delete(expiredId)
    }
  }
  return true
}

function waitForRetry(delayMs: number, signal: AbortSignal | undefined): Promise<void> {
  if (delayMs <= 0 || signal?.aborted) {
    return Promise.resolve()
  }

  return new Promise((resolve) => {
    const timeout = globalThis.setTimeout(finish, delayMs)

    function finish() {
      globalThis.clearTimeout(timeout)
      signal?.removeEventListener('abort', finish)
      resolve()
    }

    signal?.addEventListener('abort', finish, { once: true })
  })
}

export async function* streamTaskEvents(
  taskId: string,
  options: TaskEventStreamOptions = {},
): AsyncGenerator<TaskStreamEvent> {
  const signal = options.signal
  const fetchRequest = options.fetch ?? globalThis.fetch
  const maxRetries = options.maxRetries ?? Number.POSITIVE_INFINITY
  const maxRetryDelay = Math.max(
    0,
    options.maxRetryDelayMs ?? DEFAULT_MAX_RETRY_DELAY_MS,
  )
  let retryDelay = Math.max(0, options.retryDelayMs ?? DEFAULT_RETRY_DELAY_MS)
  let failures = 0
  let lastEventId =
    options.lastEventId === undefined ? undefined : String(options.lastEventId)
  const seenIds = new Set<string>()
  const idOrder: Array<string> = []

  if (lastEventId) {
    seenIds.add(lastEventId)
    idOrder.push(lastEventId)
  }

  const url = `${API_BASE_URL}/v1/tasks/${encodeURIComponent(taskId)}/events`

  while (!signal?.aborted) {
    const headers = new Headers({ Accept: 'text/event-stream' })
    if (lastEventId) {
      headers.set('Last-Event-ID', lastEventId)
    }

    try {
      const response = await fetchRequest(url, {
        cache: 'no-store',
        credentials: 'same-origin',
        headers,
        signal,
      })
      if (!response.ok) {
        throw await apiErrorFromResponse(response)
      }
      if (!response.body) {
        throw new ApiError('The task event response did not contain a stream.', {
          kind: 'stream',
        })
      }

      options.onConnectionChange?.('connected')

      for await (const frame of parseEventStream(response.body, lastEventId, signal)) {
        if (signal?.aborted) {
          return
        }
        if (frame.retry !== undefined) {
          retryDelay = frame.retry
        }
        if (!frame.event) {
          continue
        }

        if (frame.event.id) {
          lastEventId = frame.event.id
        }
        if (!rememberEventId(frame.event.id, seenIds, idOrder)) {
          continue
        }

        failures = 0
        yield frame.event
        if (signal?.aborted) {
          return
        }
      }

      if (signal?.aborted) {
        return
      }
      throw new ApiError('The task event stream closed unexpectedly.', {
        code: 'event_stream_closed',
        kind: 'stream',
      })
    } catch (error) {
      if (signal?.aborted) {
        return
      }

      const apiError = toApiError(error, undefined, 'Unable to stream task events.')
      if (!apiError.retryable) {
        throw apiError
      }

      failures += 1
      if (failures > maxRetries) {
        throw apiError
      }

      options.onConnectionChange?.('reconnecting')
      const backoff = Math.min(
        retryDelay * 2 ** Math.max(0, failures - 1),
        maxRetryDelay,
      )
      await waitForRetry(backoff, signal)
    }
  }
}

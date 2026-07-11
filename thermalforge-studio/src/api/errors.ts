export type ApiErrorKind =
  | 'aborted'
  | 'http'
  | 'invalid_response'
  | 'network'
  | 'stream'

export interface ApiErrorOptions {
  cause?: unknown
  code?: string
  details?: unknown
  kind: ApiErrorKind
  retryable?: boolean
  stage?: string | null
  status?: number
  traceId?: string | null
}

interface ErrorBody {
  code?: unknown
  detail?: unknown
  details?: unknown
  message?: unknown
  retryable?: unknown
  stage?: unknown
  trace_id?: unknown
}

export class ApiError extends Error {
  readonly code: string
  readonly details?: unknown
  readonly kind: ApiErrorKind
  readonly retryable: boolean
  readonly stage: string | null
  readonly status?: number
  readonly traceId: string | null

  constructor(message: string, options: ApiErrorOptions) {
    super(message, options.cause === undefined ? undefined : { cause: options.cause })
    this.name = 'ApiError'
    this.code = options.code ?? defaultCode(options.kind, options.status)
    this.details = options.details
    this.kind = options.kind
    this.retryable = options.retryable ?? defaultRetryable(options.kind, options.status)
    this.stage = options.stage ?? null
    this.status = options.status
    this.traceId = options.traceId ?? null
  }
}

function defaultCode(kind: ApiErrorKind, status?: number): string {
  if (kind === 'http' && status !== undefined) {
    return `http_${status}`
  }
  return kind === 'aborted' ? 'request_aborted' : `${kind}_error`
}

function defaultRetryable(kind: ApiErrorKind, status?: number): boolean {
  if (kind === 'network' || kind === 'stream') {
    return true
  }
  return status === 408 || status === 425 || status === 429 || (status ?? 0) >= 500
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isAbortError(error: unknown): boolean {
  return isRecord(error) && error.name === 'AbortError'
}

function stringValue(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 ? value : undefined
}

function validationMessage(details: unknown): string | undefined {
  if (!Array.isArray(details)) {
    return undefined
  }

  const messages = details.flatMap((item) => {
    if (!isRecord(item) || typeof item.msg !== 'string') {
      return []
    }
    const location = Array.isArray(item.loc) ? item.loc.join('.') : ''
    return [location ? `${location}: ${item.msg}` : item.msg]
  })

  return messages.length > 0 ? messages.join('; ') : undefined
}

export function toApiError(
  error: unknown,
  response?: Response,
  fallbackMessage = 'The API request failed.',
): ApiError {
  if (error instanceof ApiError) {
    return error
  }

  if (isAbortError(error)) {
    return new ApiError('The request was cancelled.', {
      cause: error,
      kind: 'aborted',
      retryable: false,
    })
  }

  const body: ErrorBody = isRecord(error) ? error : {}
  const details = body.details ?? body.detail
  const message =
    stringValue(body.message) ??
    (typeof body.detail === 'string' ? body.detail : undefined) ??
    validationMessage(details) ??
    (error instanceof Error ? error.message : undefined) ??
    (typeof error === 'string' && error.length > 0 ? error : undefined) ??
    fallbackMessage
  const status = response?.status
  const kind: ApiErrorKind = status === undefined ? 'network' : 'http'

  return new ApiError(message, {
    cause: error,
    code: stringValue(body.code),
    details,
    kind,
    retryable: typeof body.retryable === 'boolean' ? body.retryable : undefined,
    stage: typeof body.stage === 'string' ? body.stage : null,
    status,
    traceId:
      stringValue(body.trace_id) ?? response?.headers.get('X-Request-ID') ?? null,
  })
}

export async function apiErrorFromResponse(response: Response): Promise<ApiError> {
  let body: unknown
  try {
    const text = await response.text()
    if (text.length > 0) {
      try {
        body = JSON.parse(text)
      } catch {
        body = text
      }
    }
  } catch {
    body = undefined
  }

  return toApiError(
    body,
    response,
    `The API request failed with status ${response.status}.`,
  )
}

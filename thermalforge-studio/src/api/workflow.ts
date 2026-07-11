import {
  answerClarificationV1TasksTaskIdClarificationPost as answerClarificationRequest,
  cancelTaskV1TasksTaskIdCancelPost as cancelTaskRequest,
  createProjectV1ProjectsPost as createProjectRequest,
  createTaskV1ProjectsProjectIdTasksPost as createTaskRequest,
  getClarificationV1TasksTaskIdClarificationGet as getClarificationRequest,
  getEngineeringBriefV1TasksTaskIdEngineeringBriefGet as getEngineeringBriefRequest,
  getTaskImageManifestV1TasksTaskIdImageManifestGet as getTaskImageManifestRequest,
  getTaskV1TasksTaskIdGet as getTaskRequest,
  getThermalAnalysisV1TasksTaskIdThermalAnalysisGet as getThermalAnalysisRequest,
  getThermalDesignV1TasksTaskIdThermalDesignGet as getThermalDesignRequest,
  getViewerLibraryV1ViewerLibraryGet as getViewerLibraryRequest,
  getViewerManifestV1TasksTaskIdViewerManifestGet as getViewerManifestRequest,
  retryTaskV1TasksTaskIdRetryPost as retryTaskRequest,
  startTaskV1TasksTaskIdStartPost as startTaskRequest,
  uploadDocumentV1TasksTaskIdDocumentsPost as uploadDocumentRequest,
} from './generated'
import { client as generatedClient } from './generated/client.gen'
import type {
  ArtifactRead,
  ClarificationRead,
  EngineeringBrief,
  ProjectRead,
  TaskImageManifest,
  TaskRead,
  ThermalAnalysisResult,
  ThermalDesignSpec,
  ViewerLibrary,
  ViewerManifest,
} from './generated'
import { ApiError, toApiError } from './errors'

export interface ApiRequestOptions {
  signal?: AbortSignal
}

export interface CreateTaskInput {
  idempotencyKey?: string
  prompt?: string
}

interface SdkResult<T> {
  data: T | undefined
  error: unknown
  response?: Response
}

const configuredBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')
const sameOriginBaseUrl =
  typeof window !== 'undefined' && window.location.origin !== 'null'
    ? window.location.origin
    : ''

export const API_BASE_URL = configuredBaseUrl || sameOriginBaseUrl

if (API_BASE_URL) {
  generatedClient.setConfig({ baseUrl: API_BASE_URL })
}

export function createIdempotencyKey(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return globalThis.crypto.randomUUID()
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

async function execute<T>(
  operation: string,
  request: () => Promise<SdkResult<T>>,
): Promise<T> {
  let result: SdkResult<T>
  try {
    result = await request()
  } catch (error) {
    throw toApiError(error, undefined, `Unable to ${operation}.`)
  }

  if (result.error !== undefined) {
    throw toApiError(result.error, result.response, `Unable to ${operation}.`)
  }
  if (result.data === undefined) {
    throw new ApiError(`The API returned no data while trying to ${operation}.`, {
      kind: 'invalid_response',
      retryable: false,
      status: result.response?.status,
    })
  }
  return result.data
}

export function createProject(
  name: string,
  options: ApiRequestOptions = {},
): Promise<ProjectRead> {
  return execute('create the project', () =>
    createProjectRequest({
      body: { name },
      signal: options.signal,
    }),
  )
}

export function createTask(
  projectId: string,
  input: CreateTaskInput = {},
  options: ApiRequestOptions = {},
): Promise<TaskRead> {
  return execute('create the task', () =>
    createTaskRequest({
      body: { prompt: input.prompt ?? '' },
      headers: {
        'Idempotency-Key': input.idempotencyKey ?? createIdempotencyKey(),
      },
      path: { project_id: projectId },
      signal: options.signal,
    }),
  )
}

export function uploadDocument(
  taskId: string,
  file: File | Blob,
  options: ApiRequestOptions = {},
): Promise<ArtifactRead> {
  return execute('upload the document', () =>
    uploadDocumentRequest({
      body: { file },
      path: { task_id: taskId },
      signal: options.signal,
    }),
  )
}

export function getTask(
  taskId: string,
  options: ApiRequestOptions = {},
): Promise<TaskRead> {
  return execute('load the task', () =>
    getTaskRequest({ path: { task_id: taskId }, signal: options.signal }),
  )
}

export function getViewerManifest(
  taskId: string,
  options: ApiRequestOptions = {},
): Promise<ViewerManifest> {
  return execute('load the viewer manifest', () =>
    getViewerManifestRequest({
      path: { task_id: taskId },
      signal: options.signal,
    }),
  )
}

export function getViewerLibrary(
  options: ApiRequestOptions = {},
): Promise<ViewerLibrary> {
  return execute('load the viewer library', () =>
    getViewerLibraryRequest({ signal: options.signal }),
  )
}

export function getEngineeringBrief(
  taskId: string,
  options: ApiRequestOptions = {},
): Promise<EngineeringBrief> {
  return execute('load the engineering brief', () =>
    getEngineeringBriefRequest({
      path: { task_id: taskId },
      signal: options.signal,
    }),
  )
}

export function getTaskImageManifest(
  taskId: string,
  options: ApiRequestOptions = {},
): Promise<TaskImageManifest> {
  return execute('load the task images', () =>
    getTaskImageManifestRequest({
      path: { task_id: taskId },
      signal: options.signal,
    }),
  )
}

export function getThermalAnalysis(
  taskId: string,
  options: ApiRequestOptions = {},
): Promise<ThermalAnalysisResult> {
  return execute('load the thermal analysis', () =>
    getThermalAnalysisRequest({
      path: { task_id: taskId },
      signal: options.signal,
    }),
  )
}

export function getThermalDesign(
  taskId: string,
  options: ApiRequestOptions = {},
): Promise<ThermalDesignSpec> {
  return execute('load the thermal design', () =>
    getThermalDesignRequest({
      path: { task_id: taskId },
      signal: options.signal,
    }),
  )
}

export function getClarification(
  taskId: string,
  options: ApiRequestOptions = {},
): Promise<ClarificationRead> {
  return execute('load the clarification', () =>
    getClarificationRequest({
      path: { task_id: taskId },
      signal: options.signal,
    }),
  )
}

export function answerClarification(
  taskId: string,
  answer: string,
  options: ApiRequestOptions = {},
): Promise<ClarificationRead> {
  return execute('answer the clarification', () =>
    answerClarificationRequest({
      body: { answer },
      path: { task_id: taskId },
      signal: options.signal,
    }),
  )
}

export function startTask(
  taskId: string,
  options: ApiRequestOptions = {},
): Promise<TaskRead> {
  return execute('start the task', () =>
    startTaskRequest({ path: { task_id: taskId }, signal: options.signal }),
  )
}

export function cancelTask(
  taskId: string,
  options: ApiRequestOptions = {},
): Promise<TaskRead> {
  return execute('cancel the task', () =>
    cancelTaskRequest({ path: { task_id: taskId }, signal: options.signal }),
  )
}

export function retryTask(
  taskId: string,
  options: ApiRequestOptions = {},
): Promise<TaskRead> {
  return execute('retry the task', () =>
    retryTaskRequest({ path: { task_id: taskId }, signal: options.signal }),
  )
}

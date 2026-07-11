import type { AgentFile } from './agentTypes'

export const MAX_FILE_SIZE = 20 * 1024 * 1024

export const ACCEPTED_EXTENSIONS = [
  '.pdf',
  '.docx',
  '.txt',
  '.md',
  '.png',
  '.jpg',
  '.jpeg',
  '.webp',
] as const

export const FILE_INPUT_ACCEPT =
  '.pdf,.docx,.txt,.md,image/png,image/jpeg,image/webp'

export type AgentFileSelection =
  | { files: AgentFile[]; error: null }
  | { files: null; error: string }

export function isAcceptedFile(file: File): boolean {
  const lowerName = file.name.toLowerCase()
  return ACCEPTED_EXTENSIONS.some((extension) => lowerName.endsWith(extension))
}

export function toAgentFile(file: File): AgentFile {
  return {
    id: `${file.name}-${file.size}-${file.lastModified}`,
    name: file.name,
    size: file.size,
    type: file.type,
    lastModified: file.lastModified,
    file,
    status: 'pending',
  }
}

export function selectAgentFiles(candidates: File[]): AgentFileSelection {
  const invalidFile = candidates.find(
    (file) => !isAcceptedFile(file) || file.size > MAX_FILE_SIZE,
  )

  if (invalidFile) {
    return {
      files: null,
      error: `${invalidFile.name} 不受支持或超过 20MB，请更换工程资料。`,
    }
  }

  return { files: candidates.map(toAgentFile), error: null }
}

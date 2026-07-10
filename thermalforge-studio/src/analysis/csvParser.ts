import type { MeasurementPoint } from './types'

const REQUIRED_COLUMNS = ['time_s', 'temperature_c', 'power_w'] as const
const MAX_MEASUREMENT_ROWS = 5_000

function parseNumericCell(
  value: string | undefined,
  column: string,
  rowNumber: number,
): number {
  const parsed = Number(value?.trim())
  if (!Number.isFinite(parsed)) {
    throw new Error(`第 ${rowNumber} 行的 ${column} 不是有效数字`)
  }
  return parsed
}

export function parseMeasurementCsv(csvText: string): MeasurementPoint[] {
  const lines = csvText
    .replace(/^\uFEFF/, '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)

  const headers = lines[0]!.split(',').map((header) =>
    header.trim().toLowerCase(),
  )
  const indexes = Object.fromEntries(
    REQUIRED_COLUMNS.map((column) => [column, headers.indexOf(column)]),
  ) as Record<(typeof REQUIRED_COLUMNS)[number], number>

  for (const column of REQUIRED_COLUMNS) {
    if (indexes[column] < 0) {
      throw new Error(`CSV 缺少必需列：${column}`)
    }
  }
  if (lines.length < 4) {
    throw new Error('CSV 至少需要表头和 3 行测量数据')
  }
  if (lines.length - 1 > MAX_MEASUREMENT_ROWS) {
    throw new Error(`CSV 最多支持 ${MAX_MEASUREMENT_ROWS} 行测量数据`)
  }

  const points = lines.slice(1).map((line, index) => {
    const cells = line.split(',')
    const rowNumber = index + 2
    const point = {
      timeS: parseNumericCell(cells[indexes.time_s], 'time_s', rowNumber),
      temperatureC: parseNumericCell(
        cells[indexes.temperature_c],
        'temperature_c',
        rowNumber,
      ),
      powerW: parseNumericCell(cells[indexes.power_w], 'power_w', rowNumber),
    }

    if (point.timeS < 0) {
      throw new Error(`第 ${rowNumber} 行的 time_s 不能小于 0`)
    }
    if (point.temperatureC < -100 || point.temperatureC > 500) {
      throw new Error(`第 ${rowNumber} 行的 temperature_c 超出合理范围`)
    }
    if (point.powerW < 0 || point.powerW > 1_000_000) {
      throw new Error(`第 ${rowNumber} 行的 power_w 超出合理范围`)
    }

    return point
  })

  for (let index = 1; index < points.length; index += 1) {
    if (points[index]!.timeS <= points[index - 1]!.timeS) {
      throw new Error('CSV 时间必须严格递增，不能重复或倒序')
    }
  }

  const firstTimeS = points[0]!.timeS
  return points.map((point) => ({
    ...point,
    timeS: point.timeS - firstTimeS,
  }))
}

export function createMeasurementCsvTemplate(): string {
  return [
    'time_s,temperature_c,power_w',
    '0,30.0,80',
    '60,38.5,80',
    '120,47.2,82',
    '180,55.8,81',
    '240,63.1,80',
    '300,69.0,79',
  ].join('\n')
}

import { describe, expect, it } from 'vitest'
import {
  createMeasurementCsvTemplate,
  parseMeasurementCsv,
} from './csvParser'

describe('measurement CSV parser', () => {
  it('parses the documented time, temperature and power columns', () => {
    const points = parseMeasurementCsv(
      '\uFEFFtime_s,temperature_c,power_w\n0,30,80\n60,41.5,82\n120,53,79',
    )

    expect(points).toEqual([
      { timeS: 0, temperatureC: 30, powerW: 80 },
      { timeS: 60, temperatureC: 41.5, powerW: 82 },
      { timeS: 120, temperatureC: 53, powerW: 79 },
    ])
  })

  it('rejects missing columns and non-monotonic timestamps', () => {
    expect(() =>
      parseMeasurementCsv('time_s,temperature_c\n0,30\n60,40'),
    ).toThrow(/power_w/)

    expect(() =>
      parseMeasurementCsv(
        'time_s,temperature_c,power_w\n0,30,80\n60,40,80\n30,45,80',
      ),
    ).toThrow(/时间必须严格递增/)
  })

  it('provides a downloadable template with the same schema', () => {
    const template = createMeasurementCsvTemplate()

    expect(template).toContain('time_s,temperature_c,power_w')
    expect(template.trim().split('\n').length).toBeGreaterThan(3)
  })

  it('normalizes absolute timestamps to elapsed seconds', () => {
    const points = parseMeasurementCsv(
      'time_s,temperature_c,power_w\n100,30,80\n160,40,80\n220,50,80',
    )

    expect(points.map((point) => point.timeS)).toEqual([0, 60, 120])
  })
})

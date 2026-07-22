import { describe, expect, it } from 'vitest'
import { parseApiDate } from './dates'

describe('parseApiDate', () => {
  it('parses a timestamp that already has a timezone designator', () => {
    const result = parseApiDate('2026-07-22T19:53:03.555030Z')
    expect(result.toISOString()).toBe('2026-07-22T19:53:03.555Z')
  })

  it('treats a timestamp without a timezone designator as UTC', () => {
    const result = parseApiDate('2026-07-22T19:53:03.555030')
    expect(result.toISOString()).toBe('2026-07-22T19:53:03.555Z')
  })

  it('produces the same instant for both formats', () => {
    const withZone = parseApiDate('2026-07-22T19:53:03.555030Z')
    const withoutZone = parseApiDate('2026-07-22T19:53:03.555030')
    expect(withoutZone.getTime()).toBe(withZone.getTime())
  })
})

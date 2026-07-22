import { describe, expect, it } from 'vitest'
import { formatEUR, formatPercent } from './format'

const NBSP = String.fromCharCode(160)

describe('formatEUR', () => {
  it('formats a euro amount using Spanish comma decimals', () => {
    expect(formatEUR(990)).toBe(`990,00${NBSP}€`)
  })

  it('formats zero', () => {
    expect(formatEUR(0)).toBe(`0,00${NBSP}€`)
  })
})

describe('formatPercent', () => {
  it('formats a percentage with one decimal place using a comma', () => {
    expect(formatPercent(66.666)).toBe('66,7%')
  })

  it('formats a negative percentage', () => {
    expect(formatPercent(-5.25)).toBe('-5,3%')
  })
})

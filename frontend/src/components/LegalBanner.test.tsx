import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LegalBanner, LEGAL_DISCLAIMER } from './LegalBanner'

describe('LegalBanner', () => {
  it('renders the exact legal disclaimer text', () => {
    render(<LegalBanner />)
    expect(screen.getByText(LEGAL_DISCLAIMER)).toBeInTheDocument()
  })

  it('uses the exact required wording', () => {
    expect(LEGAL_DISCLAIMER).toBe(
      'Simulación educativa, no es asesoramiento financiero. Capital ficticio.'
    )
  })
})

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App scaffold', () => {
  it('renders the default Vite + React starter content', () => {
    render(<App />)
    expect(screen.getByText(/get started/i)).toBeInTheDocument()
  })
})

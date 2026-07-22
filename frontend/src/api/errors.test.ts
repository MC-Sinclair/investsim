import { describe, expect, it } from 'vitest'
import { toApiError } from './errors'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('toApiError', () => {
  it('uses detail directly when it is a string', async () => {
    const response = jsonResponse(404, { detail: 'Simbolo desconocido: NOPE' })
    const error = await toApiError(response)
    expect(error.status).toBe(404)
    expect(error.message).toBe('Simbolo desconocido: NOPE')
  })

  it('joins the msg fields when detail is a FastAPI validation array', async () => {
    const response = jsonResponse(422, {
      detail: [{ type: 'missing', loc: ['body', 'amount'], msg: 'Field required' }],
    })
    const error = await toApiError(response)
    expect(error.status).toBe(422)
    expect(error.message).toBe('Field required')
  })

  it('joins multiple validation errors with a separator', async () => {
    const response = jsonResponse(422, {
      detail: [
        { type: 'missing', loc: ['body', 'amount'], msg: 'Field required' },
        { type: 'missing', loc: ['body', 'symbol'], msg: 'Field required' },
      ],
    })
    const error = await toApiError(response)
    expect(error.message).toBe('Field required; Field required')
  })

  it('falls back to a generic message when there is no detail', async () => {
    const response = new Response('not json', { status: 500 })
    const error = await toApiError(response)
    expect(error.status).toBe(500)
    expect(error.message).toBe('Error 500 al llamar a la API')
  })
})

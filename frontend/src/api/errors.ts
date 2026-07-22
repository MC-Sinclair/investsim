export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

interface ValidationDetailItem {
  msg: string
}

function isValidationDetailArray(detail: unknown): detail is ValidationDetailItem[] {
  return (
    Array.isArray(detail) &&
    detail.every(
      (item) => typeof item === 'object' && item !== null && typeof (item as { msg?: unknown }).msg === 'string'
    )
  )
}

export async function toApiError(response: Response): Promise<ApiError> {
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    body = null
  }

  const detail = (body as { detail?: unknown } | null)?.detail

  if (typeof detail === 'string') {
    return new ApiError(response.status, detail)
  }

  if (isValidationDetailArray(detail)) {
    return new ApiError(response.status, detail.map((item) => item.msg).join('; '))
  }

  return new ApiError(response.status, `Error ${response.status} al llamar a la API`)
}

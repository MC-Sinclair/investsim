const HAS_TIMEZONE = /[zZ]|[+-]\d{2}:\d{2}$/

export function parseApiDate(value: string): Date {
  return new Date(HAS_TIMEZONE.test(value) ? value : `${value}Z`)
}

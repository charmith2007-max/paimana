export function formatMonth(value: string | null | undefined): string {
  if (!value) return '—'

  const iso = value.trim()
  const monthOnly = /^(\d{4})-(\d{2})$/.exec(iso)
  if (monthOnly) {
    const year = Number(monthOnly[1])
    const month = Number(monthOnly[2])
    return new Date(year, month - 1, 1).toLocaleDateString('en-IN', {
      month: 'short',
      year: 'numeric',
    })
  }

  const parsed = new Date(iso)
  if (Number.isNaN(parsed.getTime())) return iso

  return parsed.toLocaleDateString('en-IN', {
    month: 'short',
    year: 'numeric',
  })
}

export function displayText(value: string | null | undefined, fallback = '—'): string {
  const trimmed = value?.trim()
  return trimmed ? trimmed : fallback
}

export function formatOptionalNumber(
  value: number | null | undefined,
  suffix = '',
  digits?: number,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  const rendered =
    digits === undefined ? String(value) : value.toLocaleString('en-IN', {
      maximumFractionDigits: digits,
      minimumFractionDigits: digits,
    })
  return suffix ? `${rendered}${suffix}` : rendered
}

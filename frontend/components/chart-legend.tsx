export function ChartLegend({
  items,
}: {
  items: { label: string; color: string; dashed?: boolean }[]
}) {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1.5 text-xs text-muted-foreground">
          {item.dashed ? (
            <span
              aria-hidden
              className="h-0 w-3.5 border-t-2 border-dashed"
              style={{ borderColor: item.color }}
            />
          ) : (
            <span
              aria-hidden
              className="size-2.5 rounded-sm"
              style={{ background: item.color }}
            />
          )}
          {item.label}
        </li>
      ))}
    </ul>
  )
}

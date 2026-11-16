export function ChartTooltipContent({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-border/50 bg-card/95 px-4 py-3 shadow-elev backdrop-blur-sm">
      <p className="mb-1 text-xs font-medium text-muted-foreground">{label}</p>
      {payload.map((entry: any, i: number) => (
        <p key={i} className="text-sm font-semibold text-foreground" style={{ color: entry.color }}>
          {typeof entry.value === "number"
            ? entry.value.toLocaleString("fr-FR")
            : entry.value}
        </p>
      ))}
    </div>
  );
}

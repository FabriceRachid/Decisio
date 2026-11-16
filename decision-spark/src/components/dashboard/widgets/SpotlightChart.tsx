import { Inbox, LineChart, BarChart3 } from "lucide-react";
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, LabelList, ResponsiveContainer } from "recharts";
import { Card } from "@/components/AppShell";
import type { WidgetData } from "@/types/dashboard";
import { chartColors, formatCompact, getChartData, getDisplayTitle, isTimeWidget, hasBreakdown } from "@/lib/dashboard-utils";
import { WidgetHeader } from "./WidgetHeader";

export function SpotlightChart({ widget, onRemove }: { widget: WidgetData; onRemove: () => void }) {
  const chartData = getChartData(widget);
  const isTimeline = isTimeWidget(widget);
  const title = isTimeline ? "Tendance principale" : "Analyse principale";
  const hasValidBreakdown = hasBreakdown(widget) && chartData.length > 0;
  const isEmpty = !hasValidBreakdown || chartData.every((d) => d.value === 0);

  if (isEmpty) {
    return (
      <Card className="group flex min-h-[380px] flex-col overflow-hidden rounded-xl border border-dashed border-border/40 p-0">
        <WidgetHeader
          title={`${title} · ${getDisplayTitle(widget)}`}
          icon={<Inbox className="h-4 w-4 text-muted-foreground" />}
          onRemove={onRemove}
          alwaysShowRemove
        />
        <div className="flex flex-1 flex-col items-center justify-center gap-2 px-5 py-8">
          <Inbox className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm font-medium text-muted-foreground">Aucune donnée</p>
          <p className="text-xs text-muted-foreground/60 text-center">
            La colonne "{widget.payload?.group_by?.[0] || 'date'}" n'a pas été trouvée dans les données.
          </p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="group flex min-h-[380px] flex-col overflow-hidden rounded-xl border-border/70 p-0">
      <WidgetHeader
        title={`${title} · ${getDisplayTitle(widget)}`}
        icon={isTimeline ? <LineChart className="h-4 w-4" /> : <BarChart3 className="h-4 w-4" />}
        onRemove={onRemove}
      />
      <div className="flex flex-1 flex-col px-4 pb-4 pt-3">
        <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="rounded-full bg-primary/10 px-2.5 py-1 font-semibold text-primary-strong">
            {widget.payload?.group_by?.[0] || "Dimension"}
          </span>
        </div>
        <div className="min-h-[280px] flex-1">
          <ResponsiveContainer>
            {isTimeline ? (
              <AreaChart data={chartData} margin={{ top: 14, right: 18, left: -8, bottom: 8 }}>
                <defs>
                  <linearGradient id={`spotlight-fill-${widget.id}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={chartColors[0]} stopOpacity={0.28} />
                    <stop offset="100%" stopColor={chartColors[0]} stopOpacity={0.03} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="name" stroke="var(--color-muted-foreground)" fontSize={11} tickLine={false} axisLine={false} dy={8} />
                <YAxis stroke="var(--color-muted-foreground)" fontSize={11} tickLine={false} axisLine={false} width={44} />
                <Tooltip content={<ChartTooltipContent />} />
                <Area type="monotone" dataKey="value" stroke={chartColors[0]} strokeWidth={2.5} fill={`url(#spotlight-fill-${widget.id})`} activeDot={{ r: 5, strokeWidth: 0 }} />
              </AreaChart>
            ) : (
              <BarChart data={chartData.slice(0, 10)} layout="vertical" margin={{ top: 8, right: 24, left: 12, bottom: 8 }}>
                <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" horizontal={false} />
                <XAxis type="number" stroke="var(--color-muted-foreground)" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis dataKey="name" type="category" stroke="var(--color-muted-foreground)" fontSize={11} tickLine={false} axisLine={false} width={92} />
                <Tooltip content={<ChartTooltipContent />} />
                <Bar dataKey="value" radius={[0, 6, 6, 0]} fill={chartColors[0]} maxBarSize={28}>
                  <LabelList dataKey="value" position="right" fontSize={11} fill="var(--color-muted-foreground)" formatter={(v: number) => formatCompact(v)} />
                </Bar>
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      </div>
    </Card>
  );
}

function ChartTooltipContent({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-border/50 bg-card/95 px-4 py-3 shadow-elev backdrop-blur-sm">
      <p className="mb-1 text-xs font-medium text-muted-foreground">{label}</p>
      {payload.map((entry: any, i: number) => (
        <p key={i} className="text-sm font-semibold text-foreground" style={{ color: entry.color }}>
          {typeof entry.value === "number" ? entry.value.toLocaleString("fr-FR") : entry.value}
        </p>
      ))}
    </div>
  );
}

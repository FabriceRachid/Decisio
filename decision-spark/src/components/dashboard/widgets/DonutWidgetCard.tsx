import { ChartPie } from "lucide-react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { Card } from "@/components/AppShell";
import type { WidgetData } from "@/types/dashboard";
import { chartColors, formatCompact, getChartData, getDisplayTitle } from "@/lib/dashboard-utils";
import { WidgetHeader } from "./WidgetHeader";
import { ChartTooltipContent } from "./ChartTooltipContent";

interface DonutWidgetCardProps {
  widget: WidgetData;
  onRemove: () => void;
  chartTypeOverride?: string;
  onChartTypeChange?: (type: string) => void;
  onAnalyseIA?: (widget: WidgetData) => void;
}

export function DonutWidgetCard({ widget, onRemove, chartTypeOverride, onChartTypeChange, onAnalyseIA }: DonutWidgetCardProps) {
  const chartData = getChartData(widget)
    .sort((a, b) => b.value - a.value)
    .slice(0, 7);
  const total = chartData.reduce((sum, row) => sum + row.value, 0);

  return (
    <Card className="group relative flex h-full flex-col overflow-hidden rounded-xl border-border/60 p-0 shadow-card transition-all duration-200 hover:shadow-widget-hover">
      <WidgetHeader
        title={getDisplayTitle(widget)}
        icon={<ChartPie className="h-4 w-4" />}
        onRemove={onRemove}
        currentChartType={chartTypeOverride || "donut"}
        onChartTypeChange={onChartTypeChange}
        onAnalyseIA={onAnalyseIA ? () => onAnalyseIA(widget) : undefined}
      />
      <div className="grid flex-1 items-center gap-2 px-4 py-4 sm:grid-cols-[180px_1fr]">
        <div className="relative h-44">
          <ResponsiveContainer>
            <PieChart>
              <Pie data={chartData} cx="50%" cy="50%" innerRadius={54} outerRadius={76} paddingAngle={2} dataKey="value">
                {chartData.map((_, index) => (
                  <Cell key={index} fill={chartColors[index % chartColors.length]} stroke="var(--color-card)" strokeWidth={2} />
                ))}
              </Pie>
              <Tooltip content={<ChartTooltipContent />} />
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 grid place-items-center">
            <div className="text-center">
              <div className="text-xl font-bold tracking-tight text-foreground">{formatCompact(total)}</div>
              <div className="text-[10px] font-semibold uppercase text-muted-foreground">Total</div>
            </div>
          </div>
        </div>
        <div className="min-w-0 space-y-2">
          {chartData.map((row, index) => (
            <div key={row.name} className="flex items-center gap-2 text-xs">
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: chartColors[index % chartColors.length] }} />
              <span className="min-w-0 flex-1 truncate font-medium text-foreground">{row.name}</span>
              <span className="shrink-0 tabular-nums text-muted-foreground">
                {total > 0 ? `${Math.round((row.value / total) * 100)}%` : "0%"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

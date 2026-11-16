import { ChartPie } from "lucide-react";
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, Tooltip, ResponsiveContainer } from "recharts";
import { Card } from "@/components/AppShell";
import type { WidgetData } from "@/types/dashboard";
import { chartColors, getChartData, getDisplayTitle } from "@/lib/dashboard-utils";
import { WidgetHeader } from "./WidgetHeader";
import { WidgetFooter } from "./WidgetFooter";
import { ChartTooltipContent } from "./ChartTooltipContent";

interface RadarWidgetCardProps {
  widget: WidgetData;
  onRemove: () => void;
  chartTypeOverride?: string;
  onChartTypeChange?: (type: string) => void;
  onAnalyseIA?: (widget: WidgetData) => void;
}

export function RadarWidgetCard({ widget, onRemove, chartTypeOverride, onChartTypeChange, onAnalyseIA }: RadarWidgetCardProps) {
  const chartData = getChartData(widget)
    .sort((a, b) => b.value - a.value)
    .slice(0, 7)
    .map((row) => ({ ...row, value: Math.max(row.value, 0) }));

  return (
    <Card className="group flex flex-col overflow-hidden rounded-xl border-border/60 p-0 shadow-card">
      <WidgetHeader
        title={getDisplayTitle(widget, "Comparaison")}
        icon={<ChartPie className="h-4 w-4" />}
        onRemove={onRemove}
        currentChartType={chartTypeOverride || "radar"}
        onChartTypeChange={onChartTypeChange}
        onAnalyseIA={onAnalyseIA ? () => onAnalyseIA(widget) : undefined}
      />
      <div className="flex-1 px-3 py-3">
        <div className="h-56">
          <ResponsiveContainer>
            <RadarChart data={chartData} outerRadius="72%">
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis dataKey="name" tick={{ fontSize: 10, fill: "var(--color-muted-foreground)" }} />
              <Radar dataKey="value" stroke={chartColors[3]} fill={chartColors[3]} fillOpacity={0.25} strokeWidth={2} />
              <Tooltip content={<ChartTooltipContent />} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <WidgetFooter rows={widget.payload?.rows_processed} quality={widget.payload?.data_quality_score} />
    </Card>
  );
}

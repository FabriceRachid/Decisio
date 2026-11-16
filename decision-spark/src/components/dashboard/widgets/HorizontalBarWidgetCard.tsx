import { BarChart3 } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, LabelList, ResponsiveContainer } from "recharts";
import { Card } from "@/components/AppShell";
import type { WidgetData } from "@/types/dashboard";
import { chartColors, formatCompact, getChartData, getDisplayTitle } from "@/lib/dashboard-utils";
import { WidgetHeader } from "./WidgetHeader";
import { WidgetFooter } from "./WidgetFooter";
import { ChartTooltipContent } from "./ChartTooltipContent";

interface HorizontalBarWidgetCardProps {
  widget: WidgetData;
  onRemove: () => void;
  chartTypeOverride?: string;
  onChartTypeChange?: (type: string) => void;
  onAnalyseIA?: (widget: WidgetData) => void;
}

export function HorizontalBarWidgetCard({ widget, onRemove, chartTypeOverride, onChartTypeChange, onAnalyseIA }: HorizontalBarWidgetCardProps) {
  const chartData = getChartData(widget).sort((a, b) => b.value - a.value).slice(0, 8);

  return (
    <Card className="group relative flex h-full flex-col overflow-hidden rounded-xl border-border/60 p-0 shadow-card transition-all duration-200 hover:shadow-widget-hover">
      <WidgetHeader
        title={getDisplayTitle(widget, "Classement")}
        icon={<BarChart3 className="h-4 w-4" />}
        onRemove={onRemove}
        currentChartType={chartTypeOverride || "horizontal"}
        onChartTypeChange={onChartTypeChange}
        onAnalyseIA={onAnalyseIA ? () => onAnalyseIA(widget) : undefined}
      />
      <div className="flex-1 px-4 py-3">
        <div className="h-56">
          <ResponsiveContainer>
            <BarChart data={chartData} layout="vertical" margin={{ top: 8, right: 24, left: 10, bottom: 8 }}>
              <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" horizontal={false} />
              <XAxis type="number" stroke="var(--color-muted-foreground)" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis dataKey="name" type="category" stroke="var(--color-muted-foreground)" fontSize={11} tickLine={false} axisLine={false} width={88} />
              <Tooltip content={<ChartTooltipContent />} />
              <Bar dataKey="value" radius={[0, 6, 6, 0]} fill={chartColors[0]} maxBarSize={24}>
                <LabelList dataKey="value" position="right" fontSize={10} fill="var(--color-muted-foreground)" formatter={(v: number) => formatCompact(v)} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <WidgetFooter rows={widget.payload?.rows_processed} quality={widget.payload?.data_quality_score} />
    </Card>
  );
}

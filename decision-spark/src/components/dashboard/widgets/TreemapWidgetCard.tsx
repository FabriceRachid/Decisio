import { Table2 } from "lucide-react";
import { Treemap, ResponsiveContainer } from "recharts";
import { Card } from "@/components/AppShell";
import type { WidgetData } from "@/types/dashboard";
import { chartColors, formatCompact, getChartData, getDisplayTitle } from "@/lib/dashboard-utils";
import { WidgetHeader } from "./WidgetHeader";
import { WidgetFooter } from "./WidgetFooter";

interface TreemapWidgetCardProps {
  widget: WidgetData;
  onRemove: () => void;
  chartTypeOverride?: string;
  onChartTypeChange?: (type: string) => void;
  onAnalyseIA?: (widget: WidgetData) => void;
}

function TreemapTile(props: any) {
  const { x, y, width, height, name, value, index } = props;
  if (width < 28 || height < 24) return null;
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} rx={6} ry={6}
        fill={chartColors[index % chartColors.length]} opacity={0.88}
        stroke="var(--color-card)" strokeWidth={3} />
      <text x={x + 8} y={y + 17} fill="white" fontSize={11} fontWeight={700}>
        {String(name).slice(0, 18)}
      </text>
      {height > 44 && (
        <text x={x + 8} y={y + 34} fill="white" fontSize={10} opacity={0.86}>
          {formatCompact(Number(value))}
        </text>
      )}
    </g>
  );
}

export function TreemapWidgetCard({ widget, onRemove, chartTypeOverride, onChartTypeChange, onAnalyseIA }: TreemapWidgetCardProps) {
  const chartData = getChartData(widget).sort((a, b) => b.value - a.value).slice(0, 10);

  return (
    <Card className="group flex flex-col overflow-hidden rounded-xl border-border/60 p-0 shadow-card">
      <WidgetHeader
        title={getDisplayTitle(widget, "Poids relatif")}
        icon={<Table2 className="h-4 w-4" />}
        onRemove={onRemove}
        currentChartType={chartTypeOverride || "treemap"}
        onChartTypeChange={onChartTypeChange}
        onAnalyseIA={onAnalyseIA ? () => onAnalyseIA(widget) : undefined}
      />
      <div className="flex-1 p-4">
        <div className="h-56">
          <ResponsiveContainer>
            <Treemap data={chartData} dataKey="value" nameKey="name" aspectRatio={1.45} content={<TreemapTile />} />
          </ResponsiveContainer>
        </div>
      </div>
      <WidgetFooter rows={widget.payload?.rows_processed} quality={widget.payload?.data_quality_score} />
    </Card>
  );
}

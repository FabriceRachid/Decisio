import { useMemo } from "react";
import { Calculator, Inbox } from "lucide-react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Card } from "@/components/AppShell";
import type { WidgetData } from "@/types/dashboard";
import { chartColors, hasBreakdown, isGeoWidget, getChartVariant, getDisplayTitle } from "@/lib/dashboard-utils";
import { WidgetHeader } from "./WidgetHeader";
import { ChartTooltipContent } from "./ChartTooltipContent";
import { WorldMapCard } from "./WorldMapCard";
import { HorizontalBarWidgetCard } from "./HorizontalBarWidgetCard";
import { DonutWidgetCard } from "./DonutWidgetCard";
import { RadarWidgetCard } from "./RadarWidgetCard";
import { TreemapWidgetCard } from "./TreemapWidgetCard";

interface WidgetCardProps {
  widget: WidgetData;
  onRemove: () => void;
  variantIndex?: number;
  chartTypeOverride?: string;
  onChartTypeChange?: (widgetId: number, type: string) => void;
  onAnalyseIA?: (widget: WidgetData) => void;
}

export function WidgetCard({ widget, onRemove, variantIndex = 0, chartTypeOverride, onChartTypeChange, onAnalyseIA }: WidgetCardProps) {
  const { payload, title } = widget;
  const hasError = payload?.error;
  const widgetHasBreakdown = hasBreakdown(widget);

  const chartData = useMemo(() => {
    if (!widgetHasBreakdown) return [];
    const breakdown = widget.payload?.breakdown || [];
    const groupKey = widget.payload?.group_by?.[0];
    return breakdown
      .map((row) => {
        const label = groupKey ? String(row[groupKey] ?? "") : String(row.name ?? row.label ?? "");
        return { name: label || "Non défini", value: Number(row.value || 0) };
      })
      .filter((row) => Number.isFinite(row.value));
  }, [widget, widgetHasBreakdown]);

  const handleChartTypeChange = (type: string) => {
    onChartTypeChange?.(widget.id, type);
  };

  const handleAnalyseIA = () => {
    onAnalyseIA?.(widget);
  };

  if (hasError) {
    return (
      <Card className="group relative flex h-full flex-col overflow-hidden rounded-xl border-border/60 p-0 shadow-card transition-all duration-200 hover:shadow-widget-hover">
        <WidgetHeader
          title={title}
          icon={<Calculator className="h-4 w-4" />}
          onRemove={onRemove}
          onAnalyseIA={handleAnalyseIA}
        />
        <div className="flex flex-1 items-center justify-center px-5 py-8">
          <div className="text-sm text-destructive">{payload.error}</div>
        </div>
      </Card>
    );
  }

  const isEmpty = (
    !widgetHasBreakdown && (payload?.value === undefined || payload?.value === null || payload?.value === 0) && !payload?.formatted_value
  ) || (
    widgetHasBreakdown && chartData.length === 0
  );

  if (isEmpty) {
    return (
      <Card className="group flex h-full flex-col overflow-hidden rounded-xl border border-dashed border-border/40 p-0">
        <WidgetHeader
          title={title}
          icon={<Inbox className="h-4 w-4 text-muted-foreground" />}
          onRemove={onRemove}
          alwaysShowRemove
          onAnalyseIA={handleAnalyseIA}
        />
        <div className="flex flex-1 flex-col items-center justify-center gap-2 px-5 py-8">
          <Inbox className="h-8 w-8 text-muted-foreground/40" />
          <p className="text-sm font-medium text-muted-foreground">Aucune donnée</p>
        </div>
      </Card>
    );
  }

  if ((isGeoWidget(widget) || widget.type === "world_map") && widgetHasBreakdown && !chartTypeOverride) {
    return <WorldMapCard widget={widget} onRemove={onRemove} />;
  }

  const variant = chartTypeOverride || getChartVariant(widget, variantIndex);

  // --- Horizontal bar ---
  if (widgetHasBreakdown && variant === "horizontal") return <HorizontalBarWidgetCard widget={widget} onRemove={onRemove} chartTypeOverride={chartTypeOverride} onChartTypeChange={handleChartTypeChange} onAnalyseIA={handleAnalyseIA} />;
  // --- Donut ---
  if (widgetHasBreakdown && variant === "donut") return <DonutWidgetCard widget={widget} onRemove={onRemove} chartTypeOverride={chartTypeOverride} onChartTypeChange={handleChartTypeChange} onAnalyseIA={handleAnalyseIA} />;
  // --- Radar ---
  if (widgetHasBreakdown && variant === "radar") return <RadarWidgetCard widget={widget} onRemove={onRemove} chartTypeOverride={chartTypeOverride} onChartTypeChange={handleChartTypeChange} onAnalyseIA={handleAnalyseIA} />;
  // --- Treemap ---
  if (widgetHasBreakdown && variant === "treemap") return <TreemapWidgetCard widget={widget} onRemove={onRemove} chartTypeOverride={chartTypeOverride} onChartTypeChange={handleChartTypeChange} onAnalyseIA={handleAnalyseIA} />;

  // --- Line chart (with dots) ---
  if (widgetHasBreakdown && variant === "line") {
    return (
      <Card className="group relative flex h-full flex-col overflow-hidden rounded-xl border-border/60 p-0 shadow-card transition-all duration-200 hover:shadow-widget-hover">
        <WidgetHeader
          title={getDisplayTitle(widget)}
          icon={<Calculator className="h-4 w-4" />}
          onRemove={onRemove}
          currentChartType={variant}
          onChartTypeChange={handleChartTypeChange}
          onAnalyseIA={handleAnalyseIA}
        />
        <div className="flex-1 px-1 pt-2">
          <ResponsiveContainer>
            <LineChart data={chartData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="name" stroke="var(--color-muted-foreground)" fontSize={11} tickLine={false} axisLine={false} dy={6} />
              <YAxis
                stroke="var(--color-muted-foreground)"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                width={50}
                tickFormatter={(v: number) => {
                  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(0)}M`;
                  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
                  return String(v);
                }}
              />
              <Tooltip content={<ChartTooltipContent />} />
              <Line
                type="monotone"
                dataKey="value"
                stroke={chartColors[0]}
                strokeWidth={2.5}
                dot={{ r: 4, fill: chartColors[0], strokeWidth: 0 }}
                activeDot={{ r: 6, strokeWidth: 0, fill: chartColors[0] }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>
    );
  }

  // --- Vertical bar ---
  if (widgetHasBreakdown && variant === "vertical") {
    return (
      <Card className="group relative flex h-full flex-col overflow-hidden rounded-xl border-border/60 p-0 shadow-card transition-all duration-200 hover:shadow-widget-hover">
        <WidgetHeader
          title={getDisplayTitle(widget)}
          icon={<Calculator className="h-4 w-4" />}
          onRemove={onRemove}
          currentChartType={variant}
          onChartTypeChange={handleChartTypeChange}
          onAnalyseIA={handleAnalyseIA}
        />
        <div className="flex-1 px-1 pt-2">
          <ResponsiveContainer>
            <BarChart data={chartData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id={`vbar-${widget.id}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={chartColors[0]} stopOpacity={0.9} />
                  <stop offset="100%" stopColor={chartColors[0]} stopOpacity={0.5} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="name" stroke="var(--color-muted-foreground)" fontSize={11} tickLine={false} axisLine={false} dy={6} />
              <YAxis
                stroke="var(--color-muted-foreground)"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                width={50}
                tickFormatter={(v: number) => {
                  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(0)}M`;
                  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
                  return String(v);
                }}
              />
              <Tooltip content={<ChartTooltipContent />} />
              <Bar dataKey="value" fill={`url(#vbar-${widget.id})`} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    );
  }

  // --- Area / Trend ---
  if (widgetHasBreakdown && (variant === "trend" || variant === "area")) {
    return (
      <Card className="group relative flex h-full flex-col overflow-hidden rounded-xl border-border/60 p-0 shadow-card transition-all duration-200 hover:shadow-widget-hover">
        <WidgetHeader
          title={getDisplayTitle(widget)}
          icon={<Calculator className="h-4 w-4" />}
          onRemove={onRemove}
          currentChartType={variant}
          onChartTypeChange={handleChartTypeChange}
          onAnalyseIA={handleAnalyseIA}
        />
        <div className="flex-1 px-1 pt-2">
          <ResponsiveContainer>
            <AreaChart data={chartData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id={`wcard-fill-${widget.id}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={chartColors[0]} stopOpacity={0.25} />
                  <stop offset="100%" stopColor={chartColors[0]} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="name" stroke="var(--color-muted-foreground)" fontSize={11} tickLine={false} axisLine={false} dy={6} />
              <YAxis
                stroke="var(--color-muted-foreground)"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                width={50}
                tickFormatter={(v: number) => {
                  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(0)}M`;
                  if (Math.abs(v) >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
                  return String(v);
                }}
              />
              <Tooltip content={<ChartTooltipContent />} />
              <Area type="monotone" dataKey="value" stroke={chartColors[0]} strokeWidth={2.5} fill={`url(#wcard-fill-${widget.id})`} dot={false} activeDot={{ r: 4, strokeWidth: 0 }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>
    );
  }

  // --- KPI single value (no breakdown) ---
  return (
    <Card className="group relative flex h-full flex-col overflow-hidden rounded-xl border-border/60 p-0 shadow-card transition-all duration-200 hover:shadow-widget-hover">
      <WidgetHeader
        title={widget.title}
        icon={<Calculator className="h-4 w-4" />}
        onRemove={onRemove}
        onAnalyseIA={handleAnalyseIA}
      />
      <div className="flex flex-1 items-center justify-center px-5 py-5">
        <div className="text-center">
          <div className="font-display text-3xl font-semibold tracking-tight text-foreground">
            {payload?.formatted_value ||
              Number(payload?.value || 0).toLocaleString("fr-FR", { maximumFractionDigits: 0 })}
          </div>
          <div className="mt-1.5 text-xs text-muted-foreground">
            {payload?.aggregation || "somme"}
            {payload?.measure ? ` · ${payload.measure}` : ""}
          </div>
        </div>
      </div>
    </Card>
  );
}



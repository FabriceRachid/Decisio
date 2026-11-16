import { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line,
  PieChart, Pie, Cell,
  AreaChart, Area,
} from "recharts";
import type { PivotData } from "@/types/pivot";

type ChartType = "bar" | "line" | "area" | "donut";

type PivotChartProps = {
  data: PivotData;
  chartType: ChartType;
};

const COLORS = ["#1a3a5c", "#c9a84c", "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"];

export function PivotChart({ data, chartType }: PivotChartProps) {
  const chartData = useMemo(() => {
    if (!data.pivot || !data.row_headers || data.row_headers.length === 0) return [];

    return data.row_headers
      .filter((h) => h.toUpperCase() !== "TOTAL")
      .map((header, idx) => {
        const row = data.pivot[idx];
        if (!row) return null;
        const total = row.reduce((sum: number, v: number) => sum + (typeof v === "number" ? v : 0), 0);
        return { name: header, total };
      })
      .filter(Boolean);
  }, [data]);

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-sm text-muted-foreground">
        Pas assez de données pour un graphique
      </div>
    );
  }

  const maxValue = Math.max(...chartData.map((d) => d?.total || 0));

  const commonProps = {
    data: chartData,
    margin: { top: 10, right: 20, left: 10, bottom: 20 },
  };

  const axisProps = {
    tick: { fontSize: 11, fill: "#6b7280" },
    stroke: "#e5e7eb",
  };

  const tooltipProps = {
    contentStyle: {
      backgroundColor: "#fff",
      border: "1px solid #e5e7eb",
      borderRadius: "8px",
      fontSize: "12px",
    },
  };

  if (chartType === "bar") {
    return (
      <ResponsiveContainer width="100%" height={350}>
        <BarChart {...commonProps} layout="vertical" barSize={20}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" horizontal={false} />
          <XAxis type="number" {...axisProps} tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)} />
          <YAxis type="category" dataKey="name" width={120} {...axisProps} />
          <Tooltip {...tooltipProps} formatter={(value: number) => new Intl.NumberFormat("fr-FR").format(value)} />
          <Bar dataKey="total" fill="#1a3a5c" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (chartType === "line") {
    return (
      <ResponsiveContainer width="100%" height={350}>
        <LineChart {...commonProps}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="name" {...axisProps} />
          <YAxis {...axisProps} tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)} />
          <Tooltip {...tooltipProps} formatter={(value: number) => new Intl.NumberFormat("fr-FR").format(value)} />
          <Line type="monotone" dataKey="total" stroke="#c9a84c" strokeWidth={2.5} dot={{ r: 4, fill: "#c9a84c" }} activeDot={{ r: 6 }} />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (chartType === "area") {
    return (
      <ResponsiveContainer width="100%" height={350}>
        <AreaChart {...commonProps}>
          <defs>
            <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1a3a5c" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#1a3a5c" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
          <XAxis dataKey="name" {...axisProps} />
          <YAxis {...axisProps} tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)} />
          <Tooltip {...tooltipProps} formatter={(value: number) => new Intl.NumberFormat("fr-FR").format(value)} />
          <Area type="monotone" dataKey="total" stroke="#1a3a5c" strokeWidth={2} fill="url(#areaGrad)" />
        </AreaChart>
      </ResponsiveContainer>
    );
  }

  if (chartType === "donut") {
    const total = chartData.reduce((sum, d) => sum + (d?.total || 0), 0);
    return (
      <ResponsiveContainer width="100%" height={350}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={80}
            outerRadius={130}
            paddingAngle={2}
            dataKey="total"
            nameKey="name"
          >
            {chartData.map((_, idx) => (
              <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            {...tooltipProps}
            formatter={(value: number, name: string) => {
              const pct = total > 0 ? ((value / total) * 100).toFixed(1) : "0";
              return [`${new Intl.NumberFormat("fr-FR").format(value)} (${pct}%)`, name];
            }}
          />
          <Legend
            verticalAlign="bottom"
            height={36}
            formatter={(value: string) => value.length > 20 ? `${value.substring(0, 20)}…` : value}
          />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  return null;
}

export default PivotChart;

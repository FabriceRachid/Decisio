import { useState } from "react";
import { Trash2, BarChart3, LineChart, PieChart, AreaChart, Bot, Radar, Table2, BarChart2 } from "lucide-react";
import { cn } from "@/lib/utils";

const CHART_TYPES = [
  { value: "horizontal", label: "Barres horizontales", icon: BarChart3 },
  { value: "vertical", label: "Barres verticales", icon: BarChart2 },
  { value: "line", label: "Courbe avec points", icon: LineChart },
  { value: "trend", label: "Tendance (aire)", icon: AreaChart },
  { value: "donut", label: "Camembert", icon: PieChart },
  { value: "radar", label: "Radar", icon: Radar },
  { value: "treemap", label: "Treemap", icon: Table2 },
] as const;

interface WidgetHeaderProps {
  title: string;
  icon: React.ReactNode;
  onRemove: () => void;
  alwaysShowRemove?: boolean;
  currentChartType?: string;
  onChartTypeChange?: (type: string) => void;
  onAnalyseIA?: () => void;
}

export function WidgetHeader({
  title,
  icon,
  onRemove,
  alwaysShowRemove,
  currentChartType,
  onChartTypeChange,
  onAnalyseIA,
}: WidgetHeaderProps) {
  const [chartMenuOpen, setChartMenuOpen] = useState(false);

  return (
    <div className="flex items-center justify-between border-b border-border/50 px-4 py-2.5">
      <div className="flex items-center gap-2 min-w-0">
        <span className="shrink-0 text-primary-strong">{icon}</span>
        <h3 className="truncate text-sm font-semibold text-foreground">{title}</h3>
      </div>
      <div className="flex items-center gap-1">
        {onChartTypeChange && (
          <div className="relative">
            <button
              onClick={() => setChartMenuOpen(!chartMenuOpen)}
              className={cn(
                "shrink-0 rounded-lg p-1.5 transition-all",
                "text-primary-strong/70 hover:bg-gold/10 hover:text-primary-strong",
              )}
              title="Changer le graphique"
            >
              <BarChart3 className="h-4 w-4" />
            </button>
            {chartMenuOpen && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setChartMenuOpen(false)} />
                <div className="absolute right-0 top-full z-50 mt-1 w-52 rounded-xl border border-gold/20 bg-card shadow-elev py-1.5">
                  <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-primary-strong/60">Type de graphique</div>
                  {CHART_TYPES.map((ct) => (
                    <button
                      key={ct.value}
                      onClick={() => {
                        onChartTypeChange(ct.value);
                        setChartMenuOpen(false);
                      }}
                      className={cn(
                        "flex w-full items-center gap-2.5 px-3 py-2 text-xs font-medium transition-colors",
                        currentChartType === ct.value
                          ? "bg-gold/10 text-primary-strong"
                          : "text-foreground hover:bg-muted",
                      )}
                    >
                      <ct.icon className="h-4 w-4" />
                      {ct.label}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
        {onAnalyseIA && (
          <button
            onClick={onAnalyseIA}
            className="shrink-0 rounded-lg p-1.5 transition-all text-blue-500/80 hover:bg-blue-500/10 hover:text-blue-500"
            title="Analyser avec l'IA"
          >
            <Bot className="h-4 w-4" />
          </button>
        )}
        <button
          onClick={onRemove}
          className={cn(
            "shrink-0 rounded-lg p-1.5 transition-all",
            "text-muted-foreground hover:bg-destructive/10 hover:text-destructive",
            alwaysShowRemove ? "opacity-100" : "opacity-60 hover:opacity-100",
          )}
          title="Retirer"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

import {
  TrendingUp, TrendingDown, DollarSign, ShoppingCart, Package,
  Users, Hash, BarChart3, Activity, Trash2, Bot,
} from "lucide-react";
import { Card } from "@/components/AppShell";
import { cn } from "@/lib/utils";
import type { WidgetData } from "@/types/dashboard";
import { prettifyField } from "@/lib/dashboard-utils";

const ICON_MAP: Record<string, typeof TrendingUp> = {
  dollar: DollarSign,
  'shopping-cart': ShoppingCart,
  package: Package,
  users: Users,
  hash: Hash,
  trend: Activity,
  bar: BarChart3,
};

function getIcon(widget: WidgetData) {
  const measure = (widget.payload?.measure || "").toLowerCase();
  const semantic = widget.payload?.semantic_type || "";

  if (semantic === "kpi") {
    if (/montant|amount|sales|revenue|ca|total/i.test(measure)) return DollarSign;
    if (/quantite|quantity|qty|units|stock/i.test(measure)) return Package;
    if (/client|customer/i.test(measure)) return Users;
    if (/nombre|count|nb_/i.test(measure)) return Hash;
    if (/order|commande/i.test(measure)) return ShoppingCart;
  }

  for (const [key, Icon] of Object.entries(ICON_MAP)) {
    if (measure.includes(key)) return Icon;
  }

  return TrendingUp;
}

function getVariation(widget: WidgetData): { value: number; isPositive: boolean } | null {
  const payload = widget.payload;
  if (payload?.value === undefined || payload?.value === null) return null;

  const breakdown = payload.breakdown || [];
  if (breakdown.length < 2) return null;

  const sorted = [...breakdown]
    .sort((a, b) => {
      const aVal = Number(a.value || 0);
      const bVal = Number(b.value || 0);
      return aVal - bVal;
    });

  const last = Number(sorted[sorted.length - 1]?.value || 0);
  const prev = Number(sorted[sorted.length - 2]?.value || 0);

  if (prev === 0) return null;
  const change = ((last - prev) / Math.abs(prev)) * 100;

  return {
    value: Math.round(change * 10) / 10,
    isPositive: change >= 0,
  };
}

function formatValue(widget: WidgetData): string {
  const val = widget.payload?.value;
  if (val === undefined || val === null) return "0";

  const absVal = Math.abs(val);
  if (absVal >= 1_000_000) {
    return `${(val / 1_000_000).toFixed(1)}M`;
  }
  if (absVal >= 1_000) {
    return `${(val / 1_000).toFixed(1)}K`;
  }
  return val.toLocaleString("fr-FR", { maximumFractionDigits: 0 });
}

type KpiCardProps = {
  widget: WidgetData;
  index: number;
  onRemove?: () => void;
  onAnalyseIA?: (widget: WidgetData) => void;
};

export function KpiCard({ widget, index, onRemove, onAnalyseIA }: KpiCardProps) {
  const Icon = getIcon(widget);
  const variation = getVariation(widget);
  const title = prettifyField(widget.payload?.measure || widget.title);

  const accents = [
    "from-amber-500/20 via-amber-500/5 to-transparent before:bg-amber-500/10",
    "from-blue-500/20 via-blue-500/5 to-transparent before:bg-blue-500/10",
    "from-emerald-500/20 via-emerald-500/5 to-transparent before:bg-emerald-500/10",
    "from-violet-500/20 via-violet-500/5 to-transparent before:bg-violet-500/10",
  ];
  const accent = accents[index % accents.length];
  const iconColors = [
    "text-amber-600 bg-amber-50",
    "text-blue-600 bg-blue-50",
    "text-emerald-600 bg-emerald-50",
    "text-violet-600 bg-violet-50",
  ];
  const iconColor = iconColors[index % iconColors.length];

  return (
    <Card className="group relative flex h-full flex-col overflow-hidden rounded-xl border-border/60 p-0 shadow-sm transition-all duration-200 hover:shadow-md">
      <div className={`absolute inset-0 bg-gradient-to-br ${accent} opacity-60`} />
      <div className="relative flex min-h-[150px] flex-col justify-between p-5">
        {/* Toolbar — visible on hover */}
        {(onRemove || onAnalyseIA) && (
          <div className="absolute right-2 top-2 z-10 flex items-center gap-0.5 rounded-lg bg-background/80 p-0.5 shadow-sm opacity-0 backdrop-blur-xs transition-opacity group-hover:opacity-100">
            {onAnalyseIA && (
              <button
                onClick={() => onAnalyseIA(widget)}
                className="rounded-md p-1.5 text-blue-500/70 transition-colors hover:bg-blue-500/10 hover:text-blue-500"
                title="Analyser avec l'IA"
              >
                <Bot className="h-3.5 w-3.5" />
              </button>
            )}
            {onRemove && (
              <button
                onClick={onRemove}
                className="rounded-md p-1.5 text-muted-foreground/70 transition-colors hover:bg-destructive/10 hover:text-destructive"
                title="Supprimer"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        )}

        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
              {title}
            </p>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-display text-4xl font-bold tracking-tight text-foreground">
                {formatValue(widget)}
              </span>
            </div>
          </div>
          <div className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl ${iconColor}`}>
            <Icon className="h-5 w-5" />
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between gap-2 border-t border-border/40 pt-3">
          <span className="inline-flex items-center gap-1.5 rounded-md bg-muted/50 px-2 py-1 text-xs font-semibold text-muted-foreground">
            {widget.payload?.aggregation === "sum" ? "Total" :
             widget.payload?.aggregation === "mean" ? "Moyenne" :
             widget.payload?.aggregation === "count" ? "Nombre" :
             widget.payload?.aggregation || ""}
          </span>
          {variation && (
            <span className={cn(
              "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold",
              variation.isPositive ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700",
            )}>
              {variation.isPositive ? (
                <TrendingUp className="h-3.5 w-3.5" />
              ) : (
                <TrendingDown className="h-3.5 w-3.5" />
              )}
              {variation.isPositive ? "+" : ""}{variation.value}%
            </span>
          )}
        </div>
      </div>
    </Card>
  );
}

import type { ChartDatum, WidgetData } from "@/types/dashboard";

export const PERIOD_PRESETS = [
  { label: "30 derniers jours", value: "30d", days: 30 },
  { label: "Ce mois", value: "month", days: 0 },
  { label: "Ce trimestre", value: "quarter", days: 0 },
  { label: "Cette année", value: "year", days: 0 },
];

export function getPeriodDates(preset: string): { start: string; end: string } {
  const now = new Date();
  const end = now.toISOString().split("T")[0];
  if (preset === "30d") {
    const start = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString().split("T")[0];
    return { start, end };
  }
  if (preset === "month") {
    const start = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split("T")[0];
    return { start, end };
  }
  if (preset === "quarter") {
    const q = Math.floor(now.getMonth() / 3);
    const start = new Date(now.getFullYear(), q * 3, 1).toISOString().split("T")[0];
    return { start, end };
  }
  if (preset === "year") {
    const start = new Date(now.getFullYear(), 0, 1).toISOString().split("T")[0];
    return { start, end };
  }
  return { start: "", end: "" };
}

export const DOMAIN_LABELS: Record<string, string> = {
  sales: "Ventes",
  customers: "Clients",
  inventory: "Stock",
  finance: "Finance",
  products: "Produits",
  geography: "Géographie",
  generic: "Générique",
};

export const AGG_LABELS: Record<string, string> = {
  sum: "Total",
  mean: "Moyenne",
  count: "Nombre",
  min: "Minimum",
  max: "Maximum",
  median: "Médiane",
};

export const FILTER_FIELD_MAP: Record<string, string> = {
  regions: "region",
  produits: "produit",
  categories: "categorie",
  vendeurs: "vendeur",
  clients: "client",
};

export const chartColors = [
  "var(--color-chart-1)",
  "var(--color-chart-2)",
  "var(--color-chart-3)",
  "var(--color-chart-4)",
  "var(--color-chart-5)",
  "var(--color-chart-6)",
  "var(--color-chart-7)",
  "var(--color-chart-8)",
];

export const GEO_KEYWORDS = [
  "country", "countries", "pays", "nation", "region", "geo", "geography", "geographie",
  "ville", "city", "state",
];

export const TIME_KEYWORDS = [
  "date", "month", "mois", "year", "annee", "année", "quarter", "trimestre",
  "week", "semaine", "jour", "day",
];

export const SHARE_KEYWORDS = [
  "part", "share", "segment", "category", "categorie", "catégorie",
  "mode", "type", "produit", "product", "channel", "canal",
];

export const COUNTRY_COORDS: Record<string, [number, number]> = {
  burkinafaso: [-1.6, 12.2], burkina: [-1.6, 12.2],
  france: [2.2, 46.2], germany: [10.4, 51.2], allemagne: [10.4, 51.2],
  england: [-1.5, 52.3], royaumeuni: [-3.4, 55.4], unitedkingdom: [-3.4, 55.4],
  italy: [12.6, 42.9], italie: [12.6, 42.9],
  spain: [-3.7, 40.4], espagne: [-3.7, 40.4],
  usa: [-98.6, 39.8], us: [-98.6, 39.8], unitedstates: [-98.6, 39.8],
  unitedstatesofamerica: [-98.6, 39.8], etatsunis: [-98.6, 39.8],
  canada: [-106.3, 56.1], brazil: [-51.9, -14.2], bresil: [-51.9, -14.2],
  india: [78.9, 20.6], inde: [78.9, 20.6],
  china: [104.2, 35.9], chine: [104.2, 35.9],
  japan: [138.3, 36.2], japon: [138.3, 36.2],
  australia: [133.8, -25.3], australie: [133.8, -25.3],
  southafrica: [24.0, -29.0], afriquedusud: [24.0, -29.0],
  nigeria: [8.7, 9.1], senegal: [-14.5, 14.5],
  mali: [-4.0, 17.6], coteivoire: [-5.5, 7.5], cotedivoire: [-5.5, 7.5],
  ivorycoast: [-5.5, 7.5], ghana: [-1.0, 7.9],
  kenya: [37.9, 0.0], morocco: [-7.1, 31.8], maroc: [-7.1, 31.8],
  egypt: [30.8, 26.8], egypte: [30.8, 26.8],
  netherlands: [5.3, 52.1], paysbas: [5.3, 52.1],
  belgium: [4.5, 50.5], belgique: [4.5, 50.5],
  switzerland: [8.2, 46.8], suisse: [8.2, 46.8],
  turkey: [35.2, 39.0], turquie: [35.2, 39.0],
  russia: [90.0, 61.5], russie: [90.0, 61.5], russianfederation: [90.0, 61.5],
  mexico: [-102.6, 23.6], mexique: [-102.6, 23.6],
  argentina: [-63.6, -38.4], argentine: [-63.6, -38.4],
  colombia: [-74.3, 4.6], colombie: [-74.3, 4.6],
  peru: [-75.0, -9.2], perou: [-75.0, -9.2],
  chile: [-71.5, -35.7], chili: [-71.5, -35.7],
  algeria: [1.7, 28.0], algerie: [1.7, 28.0],
  tunisia: [9.5, 33.9], tunisie: [9.5, 33.9],
  ethiopia: [40.5, 9.1], ethiopie: [40.5, 9.1],
  cameroon: [12.3, 5.7], cameroun: [12.3, 5.7],
  benin: [2.3, 9.3], togo: [0.8, 8.6], niger: [8.1, 17.6],
  rwanda: [29.9, -1.9], uganda: [32.3, 1.4], ouganda: [32.3, 1.4],
  tanzania: [34.9, -6.4], tanzanie: [34.9, -6.4],
  uae: [54.3, 23.4], unitedarabemirates: [54.3, 23.4], emiratsarabesunis: [54.3, 23.4],
  saudiarabia: [45.1, 23.9], arabiesaoudite: [45.1, 23.9],
  qatar: [51.2, 25.3], singapore: [103.8, 1.35], singapour: [103.8, 1.35],
  indonesia: [113.9, -0.8], indonesie: [113.9, -0.8],
  malaysia: [101.9, 4.2], malaisie: [101.9, 4.2],
  thailand: [100.9, 15.8], thailande: [100.9, 15.8],
  vietnam: [108.3, 14.1], southkorea: [127.8, 35.9],
  koreasouth: [127.8, 35.9], republicofkorea: [127.8, 35.9], coreedusud: [127.8, 35.9],
};

export function normalizeKey(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]/gi, "")
    .toLowerCase();
}

export function getChartData(widget: WidgetData): ChartDatum[] {
  const breakdown = widget.payload?.breakdown || [];
  const groupKey = widget.payload?.group_by?.[0];
  return breakdown
    .map((row, index) => {
      let label = "";
      if (groupKey && row[groupKey] !== undefined && row[groupKey] !== null) {
        label = String(row[groupKey]);
      } else if (row.name !== undefined) {
        label = String(row.name);
      } else if (row.label !== undefined) {
        label = String(row.label);
      } else {
        const keys = Object.keys(row).filter((k) => k !== "value");
        label = keys.length > 0 ? String(row[keys[0]]) : `Item ${index + 1}`;
      }
      return { name: label || "Non défini", value: Number(row.value || 0) };
    })
    .filter((row) => Number.isFinite(row.value));
}

export function prettifyField(value?: string) {
  if (!value) return "";
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function getDimensionLabel(widget: WidgetData) {
  return prettifyField(widget.payload?.group_by?.[0]) || "Dimension";
}

export function getMeasureLabel(widget: WidgetData) {
  return prettifyField(widget.payload?.measure) || prettifyField(widget.payload?.nom_kpi) || "Valeur";
}

export function hasBreakdown(widget: WidgetData) {
  return Boolean(widget.payload?.breakdown?.length);
}

export function isGeoWidget(widget: WidgetData) {
  const fields = [widget.title, widget.payload?.group_by?.join(" ") || ""].join(" ");
  const normalized = normalizeKey(fields);
  const data = getChartData(widget);
  return (
    GEO_KEYWORDS.some((keyword) => normalized.includes(normalizeKey(keyword))) ||
    data.some((row) => COUNTRY_COORDS[normalizeKey(row.name)])
  );
}

export function isTimeWidget(widget: WidgetData) {
  const fields = [widget.title, widget.payload?.group_by?.join(" ") || ""].join(" ");
  const normalized = normalizeKey(fields);
  const data = getChartData(widget);
  return (
    widget.type === "line_chart" ||
    widget.type === "area_chart" ||
    TIME_KEYWORDS.some((keyword) => normalized.includes(normalizeKey(keyword))) ||
    data.some((row) => /^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|20\d{2})/i.test(row.name))
  );
}

export function isShareWidget(widget: WidgetData) {
  const fields = [widget.title, widget.payload?.group_by?.join(" ") || ""].join(" ");
  const normalized = normalizeKey(fields);
  const data = getChartData(widget);
  return (
    widget.type === "pie_chart" ||
    SHARE_KEYWORDS.some((keyword) => normalized.includes(normalizeKey(keyword))) ||
    (data.length > 2 && data.length <= 8)
  );
}

export function getChartVariant(widget: WidgetData, index = 0) {
  const semantic = widget.payload?.semantic_type || "";
  if (isGeoWidget(widget) || semantic === "geo") return "map";
  if (isTimeWidget(widget) || semantic === "trend") return "trend";
  if (semantic === "category") return "donut";
  if (semantic === "ranking") return "horizontal";
  if (isShareWidget(widget)) return "donut";

  const typeMap: Record<string, string> = {
    bar_chart: "horizontal",
    line_chart: "line",
    area_chart: "trend",
    pie_chart: "donut",
  };
  if (widget.type && typeMap[widget.type]) return typeMap[widget.type];

  return "horizontal";
}

export function getDisplayTitle(widget: WidgetData, fallbackPrefix?: string) {
  if (!hasBreakdown(widget)) return prettifyField(widget.payload?.nom_kpi || widget.title);

  if (widget.title) return widget.title;

  const dimension = getDimensionLabel(widget);
  const measure = getMeasureLabel(widget);
  if (isGeoWidget(widget)) return `${measure} par zone géographique`;
  if (isTimeWidget(widget)) return `${measure} dans le temps`;
  if (isShareWidget(widget)) return `Répartition de ${measure} par ${dimension}`;
  return fallbackPrefix ? `${fallbackPrefix} · ${dimension}` : `${measure} par ${dimension}`;
}

export function formatCompact(value?: number) {
  if (value === undefined || !Number.isFinite(value)) return "—";
  return Intl.NumberFormat("fr-FR", {
    notation: "compact",
    maximumFractionDigits: value >= 100 ? 0 : 1,
  }).format(value);
}

export function getWidgetValue(widget: WidgetData) {
  if (widget.payload?.formatted_value) return widget.payload.formatted_value;
  return formatCompact(Number(widget.payload?.value || 0));
}

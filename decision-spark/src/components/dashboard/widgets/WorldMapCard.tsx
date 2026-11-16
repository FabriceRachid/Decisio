import { useMemo, useState, useRef, useCallback, useEffect } from "react";
import { Globe2, ZoomIn, ZoomOut, Maximize2 } from "lucide-react";
import { geoEqualEarth, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import worldAtlas from "world-atlas/countries-110m.json";
import { Card } from "@/components/AppShell";
import type { WidgetData } from "@/types/dashboard";
import { chartColors, COUNTRY_COORDS, formatCompact, getChartData, getDisplayTitle, normalizeKey } from "@/lib/dashboard-utils";
import { WidgetHeader } from "./WidgetHeader";
import { WidgetFooter } from "./WidgetFooter";
import { cn } from "@/lib/utils";

const worldCountries = (feature(
  worldAtlas as any,
  (worldAtlas as any).objects.countries,
) as any).features as any[];

const ZOOM_MIN = 0.8;
const ZOOM_MAX = 6;
const ZOOM_STEP = 0.3;

// Color palette for choropleth
const HEAT_COLORS = [
  "oklch(0.92 0.02 250)",   // very light blue (low)
  "oklch(0.82 0.06 240)",   // light blue
  "oklch(0.72 0.10 230)",   // medium blue
  "oklch(0.62 0.14 220)",   // blue
  "oklch(0.55 0.16 210)",   // strong blue
  "oklch(0.48 0.15 200)",   // dark blue
  "oklch(0.42 0.14 180)",   // teal
  "oklch(0.52 0.16 155)",   // green
  "oklch(0.60 0.17 130)",   // bright green
  "oklch(0.70 0.15 85)",    // yellow-green
  "oklch(0.75 0.16 65)",    // gold
  "oklch(0.68 0.18 45)",    // orange
  "oklch(0.58 0.20 25)",    // red-orange
  "oklch(0.50 0.22 15)",    // red
  "oklch(0.42 0.20 10)",    // dark red (high)
];

function getHeatColor(value: number, maxValue: number): string {
  const ratio = Math.min(value / maxValue, 1);
  const idx = Math.floor(ratio * (HEAT_COLORS.length - 1));
  return HEAT_COLORS[idx];
}

function getHeatColorHex(value: number, maxValue: number): string {
  // Return a simple hex for the sidebar/legend
  const ratio = Math.min(value / maxValue, 1);
  if (ratio < 0.15) return "#93c5fd";
  if (ratio < 0.3) return "#60a5fa";
  if (ratio < 0.45) return "#3b82f6";
  if (ratio < 0.6) return "#2563eb";
  if (ratio < 0.75) return "#f59e0b";
  if (ratio < 0.9) return "#f97316";
  return "#ef4444";
}

export function WorldMapCard({ widget, onRemove, className = "" }: { widget: WidgetData; onRemove: () => void; className?: string }) {
  const allData = useMemo(() => getChartData(widget).sort((a, b) => b.value - a.value), [widget]);
  const maxValue = Math.max(...allData.map((row) => row.value), 1);

  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [hovered, setHovered] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const dragging = useRef(false);
  const lastMouse = useRef({ x: 0, y: 0 });
  const [fitted, setFitted] = useState(false);

  const baseWidth = 800;
  const baseHeight = 440;

  const map = useMemo(() => {
    const projection = geoEqualEarth().fitSize([baseWidth, baseHeight], { type: "Sphere" });
    const path = geoPath(projection);
    return { width: baseWidth, height: baseHeight, path, projection, project: (coords: [number, number]) => projection(coords) };
  }, []);

  // Auto-fit: zoom to bounding box of countries with data
  useEffect(() => {
    if (fitted || allData.length === 0) return;
    const points: [number, number][] = [];
    allData.forEach((row) => {
      const coords = COUNTRY_COORDS[normalizeKey(row.name)];
      if (coords) {
        const projected = map.project(coords);
        if (projected) points.push(projected);
      }
    });
    if (points.length < 2) { setFitted(true); return; }

    const xs = points.map((p) => p[0]);
    const ys = points.map((p) => p[1]);
    const minX = Math.min(...xs) - 40;
    const maxX = Math.max(...xs) + 40;
    const minY = Math.min(...ys) - 40;
    const maxY = Math.max(...ys) + 40;
    const dataW = maxX - minX;
    const dataH = maxY - minY;
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;

    const zoomX = map.width / dataW;
    const zoomY = map.height / dataH;
    const newZoom = Math.min(zoomX, zoomY, 3.5);

    setZoom(newZoom);
    setPan({ x: map.width / 2 - cx * newZoom, y: map.height / 2 - cy * newZoom });
    setFitted(true);
  }, [allData, map, fitted]);

  const viewBox = `${-pan.x / zoom} ${-pan.y / zoom} ${map.width / zoom} ${map.height / zoom}`;

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
    setZoom((z) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z + delta)));
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    dragging.current = true;
    lastMouse.current = { x: e.clientX, y: e.clientY };
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging.current) return;
    const dx = e.clientX - lastMouse.current.x;
    const dy = e.clientY - lastMouse.current.y;
    lastMouse.current = { x: e.clientX, y: e.clientY };
    setPan((p) => ({ x: p.x + dx / zoom, y: p.y + dy / zoom }));
  }, [zoom]);

  const handleMouseUp = useCallback(() => {
    dragging.current = false;
  }, []);

  const resetView = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

  // Match data to country
  const dataByCountry = useMemo(() => {
    const m = new Map<string, { value: number; name: string }>();
    allData.forEach((row) => {
      m.set(normalizeKey(row.name), { value: row.value, name: row.name });
    });
    return m;
  }, [allData]);

  return (
    <Card className={cn("group relative flex h-full flex-col overflow-hidden rounded-xl border-border/70 p-0 transition-all duration-200 hover:shadow-widget-hover", className)}>
      <WidgetHeader
        title={getDisplayTitle(widget)}
        icon={<Globe2 className="h-4 w-4" />}
        onRemove={onRemove}
      />
      <div className="grid flex-1 gap-0 p-4 lg:grid-cols-[1fr_260px]">
        {/* Map area */}
        <div className="relative min-h-[320px] overflow-hidden rounded-xl border border-border/60 bg-gradient-to-br from-[oklch(0.97_0.008_250)] to-[oklch(0.93_0.012_252)]">
          {/* Zoom controls */}
          <div className="absolute right-2 top-2 z-10 flex flex-col gap-1">
            <button onClick={() => setZoom((z) => Math.min(ZOOM_MAX, z + ZOOM_STEP))} className="grid h-8 w-8 place-items-center rounded-lg bg-card/95 border border-border/60 shadow-md hover:bg-card hover:shadow-lg transition" title="Zoom avant">
              <ZoomIn className="h-4 w-4 text-foreground" />
            </button>
            <button onClick={() => setZoom((z) => Math.max(ZOOM_MIN, z - ZOOM_STEP))} className="grid h-8 w-8 place-items-center rounded-lg bg-card/95 border border-border/60 shadow-md hover:bg-card hover:shadow-lg transition" title="Zoom arrière">
              <ZoomOut className="h-4 w-4 text-foreground" />
            </button>
            <button onClick={resetView} className="grid h-8 w-8 place-items-center rounded-lg bg-card/95 border border-border/60 shadow-md hover:bg-card hover:shadow-lg transition" title="Vue complète">
              <Maximize2 className="h-4 w-4 text-foreground" />
            </button>
            <div className="text-center text-[10px] font-bold text-muted-foreground/60 tabular-nums">{Math.round(zoom * 100)}%</div>
          </div>

          {/* Color legend */}
          <div className="absolute left-2 bottom-2 z-10 rounded-lg bg-card/95 border border-border/60 px-3 py-2 shadow-md">
            <div className="text-[9px] font-bold uppercase tracking-wide text-muted-foreground mb-1.5">Valeur</div>
            <div className="flex items-center gap-0.5">
              {HEAT_COLORS.filter((_, i) => i % 2 === 0).map((c, i) => (
                <div key={i} className="h-3 w-5 rounded-sm" style={{ backgroundColor: c }} />
              ))}
            </div>
            <div className="flex justify-between mt-1 text-[8px] text-muted-foreground">
              <span>0</span>
              <span>{formatCompact(maxValue)}</span>
            </div>
          </div>

          <svg
            ref={svgRef}
            viewBox={viewBox}
            className="absolute inset-0 h-full w-full"
            style={{ cursor: dragging.current ? "grabbing" : "grab" }}
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          >
            {/* Ocean */}
            <rect x={-map.width} y={-map.height} width={map.width * 3} height={map.height * 3} fill="oklch(0.96 0.008 250)" />

            {/* Countries - choropleth */}
            {worldCountries.map((country: any, index: number) => {
              const countryName = String(country.properties?.name || "").toLowerCase();
              const match = dataByCountry.get(normalizeKey(countryName));
              const hasData = !!match;
              const isHovered = hovered === match?.name;

              return (
                <path
                  key={country.id || index}
                  d={map.path(country) || ""}
                  fill={hasData ? getHeatColor(match!.value, maxValue) : "oklch(0.90 0.012 260)"}
                  stroke={hasData ? "white" : "oklch(0.96 0.005 250)"}
                  strokeWidth={hasData ? 1.5 : 0.4}
                  opacity={hasData ? (isHovered ? 1 : 0.88) : 0.5}
                  className={cn("transition-all duration-150", hasData && "cursor-pointer")}
                  style={isHovered ? { filter: "brightness(1.1) drop-shadow(0 1px 3px rgba(0,0,0,0.2))" } : undefined}
                  onMouseEnter={() => hasData && setHovered(match!.name)}
                  onMouseLeave={() => setHovered(null)}
                />
              );
            })}

            {/* Data labels - only show when zoomed in enough */}
            {zoom >= 1.5 && allData.map((row, index) => {
              const coords = COUNTRY_COORDS[normalizeKey(row.name)];
              if (!coords) return null;
              const projected = map.project(coords);
              if (!projected) return null;
              const [x, y] = projected;
              const isHovered = hovered === row.name;
              const fontSize = Math.min(Math.max(8 / zoom, 6), 14);
              return (
                <g
                  key={row.name}
                  onMouseEnter={() => setHovered(row.name)}
                  onMouseLeave={() => setHovered(null)}
                  style={{ cursor: "pointer" }}
                >
                  {/* Shadow for readability */}
                  <text x={x + 0.5} y={y + 0.5} fontSize={fontSize} fill="white" fontWeight="800" textAnchor="middle" opacity={0.7}>
                    {row.name}
                  </text>
                  <text x={x} y={y} fontSize={fontSize} fill="oklch(0.15 0.04 260)" fontWeight="800" textAnchor="middle">
                    {row.name}
                  </text>
                  {isHovered && (
                    <text x={x} y={y + fontSize + 2} fontSize={fontSize * 0.85} fill="oklch(0.3 0.04 260)" fontWeight="700" textAnchor="middle">
                      {formatCompact(row.value)}
                    </text>
                  )}
                </g>
              );
            })}

            {/* Bubbles - only when zoomed out */}
            {zoom < 1.5 && allData.slice(0, 10).map((row, index) => {
              const coords = COUNTRY_COORDS[normalizeKey(row.name)];
              if (!coords) return null;
              const projected = map.project(coords);
              if (!projected) return null;
              const [x, y] = projected;
              const radius = 3 + (row.value / maxValue) * 8;
              const isHovered = hovered === row.name;
              return (
                <g
                  key={row.name}
                  onMouseEnter={() => setHovered(row.name)}
                  onMouseLeave={() => setHovered(null)}
                  style={{ cursor: "pointer" }}
                >
                  <circle cx={x} cy={y} r={radius + 4} fill={HEAT_COLORS[Math.floor((row.value / maxValue) * (HEAT_COLORS.length - 1))]} opacity={isHovered ? 0.3 : 0.12} />
                  <circle cx={x} cy={y} r={radius} fill={HEAT_COLORS[Math.floor((row.value / maxValue) * (HEAT_COLORS.length - 1))]} opacity={0.9} stroke="white" strokeWidth={1.2} />
                  <circle cx={x} cy={y} r={radius * 0.3} fill="white" opacity={0.5} />
                </g>
              );
            })}
          </svg>

          {/* Tooltip */}
          {hovered && (() => {
            const row = allData.find((r) => r.name === hovered);
            if (!row) return null;
            const idx = allData.indexOf(row);
            const pct = ((row.value / maxValue) * 100).toFixed(1);
            return (
              <div className="absolute bottom-3 left-3 z-10 rounded-xl border border-border/60 bg-card px-4 py-3 shadow-elev">
                <div className="flex items-center gap-2">
                  <span className="h-3 w-3 rounded-full" style={{ backgroundColor: getHeatColorHex(row.value, maxValue) }} />
                  <span className="text-sm font-bold text-foreground">{row.name}</span>
                </div>
                <div className="mt-1 text-lg font-bold tabular-nums text-foreground">{row.value.toLocaleString("fr-FR")}</div>
                <div className="text-xs text-muted-foreground">{pct}% du max · Rang #{idx + 1} sur {allData.length}</div>
              </div>
            );
          })()}
        </div>

        {/* Sidebar */}
        <div className="flex flex-col min-h-0 pl-3">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
              {allData.length} pays
            </p>
          </div>
          <div className="flex-1 space-y-0.5 overflow-y-auto min-h-0 max-h-[340px] pr-1">
            {allData.map((row, index) => {
              const pct = ((row.value / maxValue) * 100).toFixed(0);
              const isActive = hovered === row.name;
              return (
                <div
                  key={row.name}
                  className={cn(
                    "flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs transition-all cursor-pointer",
                    isActive ? "bg-primary/10 shadow-sm" : "hover:bg-secondary/70"
                  )}
                  onMouseEnter={() => setHovered(row.name)}
                  onMouseLeave={() => setHovered(null)}
                >
                  <span
                    className="grid h-5 w-5 shrink-0 place-items-center rounded-md text-[10px] font-bold text-white"
                    style={{ backgroundColor: getHeatColorHex(row.value, maxValue) }}
                  >
                    {index + 1}
                  </span>
                  <span className="min-w-0 flex-1 truncate font-medium text-foreground">{row.name}</span>
                  <span className="shrink-0 tabular-nums text-muted-foreground text-[11px]">{formatCompact(row.value)}</span>
                  <div className="w-12 shrink-0">
                    <div className="h-1.5 rounded-full bg-border/40 overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: getHeatColorHex(row.value, maxValue) }} />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <WidgetFooter rows={widget.payload?.rows_processed} quality={widget.payload?.data_quality_score} />
    </Card>
  );
}

import { useState, useEffect } from "react";
import {
  ArrowLeftRight,
  CheckCircle2,
  XCircle,
  Minus,
  Loader2,
  AlertTriangle,
} from "lucide-react";
import { apiClient } from "@/lib/api";

interface ComparisonRow {
  row_number: number;
  before: Record<string, any>;
  after: Record<string, any>;
  status: "kept" | "modified" | "removed";
  changes: Array<{ column: string; action: string; before?: any; after?: any }>;
}

interface ComparisonData {
  rows?: Record<string, any>[];
  before_columns?: string[];
  after_columns?: string[];
  summary?: Record<string, any>;
  changes_by_type?: Record<string, number>;
  [key: string]: any;
}

interface DataComparisonProps {
  jobId: number;
  onClose?: () => void;
}

const STATUS_CONFIG = {
  kept: {
    label: "Inchangée",
    icon: Minus,
    color: "text-muted-foreground bg-muted border-border",
    dot: "bg-muted-foreground",
  },
  modified: {
    label: "Modifiée",
    icon: ArrowLeftRight,
    color: "text-amber-700 bg-amber-50 border-amber-200",
    dot: "bg-amber-500",
  },
  removed: {
    label: "Supprimée",
    icon: XCircle,
    color: "text-rose-700 bg-rose-50 border-rose-200",
    dot: "bg-rose-500",
  },
};

export function DataComparison({ jobId, onClose }: DataComparisonProps) {
  const [data, setData] = useState<ComparisonData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRow, setSelectedRow] = useState<number | null>(null);

  useEffect(() => {
    loadComparison();
  }, [jobId]);

  async function loadComparison() {
    setLoading(true);
    setError(null);
    try {
      const result = await apiClient.getCleaningComparison(jobId);
      setData(result);
    } catch (err: any) {
      setError(err.message || "Erreur lors du chargement de la comparaison");
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-[var(--primary)]" />
        <span className="ml-3 text-lg text-muted-foreground">
          Chargement de la comparaison...
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-rose-200 bg-rose-50 p-8 text-center">
        <AlertTriangle className="mx-auto h-10 w-10 text-rose-500" />
        <p className="mt-3 text-rose-700 font-medium">{error}</p>
        <button
          onClick={loadComparison}
          className="mt-4 px-4 py-2 rounded-full bg-rose-100 text-rose-700 hover:bg-rose-200 transition text-sm font-medium"
        >
          Reessayer
        </button>
      </div>
    );
  }

  if (!data) return null;

  const selectedRowData = data.rows?.find((r: any) => r.row_number === selectedRow);

  return (
    <div className="space-y-6">
      {/* Summary Header */}
      <div className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-[var(--shadow-card)]">
        <div className="flex items-center gap-4 mb-6">
          <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-amber-500 to-amber-600 flex items-center justify-center shadow-lg">
            <ArrowLeftRight className="h-7 w-7 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-foreground">
              Comparaison Avant / Apres
            </h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Visualisez chaque modification apportee par le nettoyage
            </p>
          </div>
        </div>

        {/* Stats row */}
        {data.summary && (
          <div className="grid grid-cols-5 gap-3">
            <StatBox
              label="Avant"
              value={data.summary.total_rows_before ?? 0}
              color="text-amber-700 bg-amber-50 border-amber-200"
            />
            <StatBox
              label="Apres"
              value={data.summary.total_rows_after ?? 0}
              color="text-emerald-700 bg-emerald-50 border-emerald-200"
            />
            <StatBox
              label="Modifiees"
              value={data.summary.rows_affected ?? 0}
              color="text-blue-700 bg-blue-50 border-blue-200"
            />
            <StatBox
              label="Colonnes +/-"
              value={`${(data.summary.columns_added ?? 0) > 0 ? "+" : ""}${data.summary.columns_added ?? 0}${(data.summary.columns_removed ?? 0) > 0 ? ` / -${data.summary.columns_removed}` : ""}`}
              color="text-violet-700 bg-violet-50 border-violet-200"
            />
            <StatBox
              label="Renommees"
              value={data.summary.columns_renamed ?? 0}
              color="text-primary-strong bg-primary/10 border-primary/20"
            />
          </div>
        )}

        {/* Changes breakdown */}
        {data.changes_by_type && Object.keys(data.changes_by_type).length > 0 && (
          <div className="mt-5 flex flex-wrap gap-2">
            {Object.entries(data.changes_by_type).map(([type, count]) => (
              <span
                key={type}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-muted border border-border text-xs font-medium text-muted-foreground"
              >
                {type.replace(/_/g, " ")}
                <span className="px-1.5 py-0.5 rounded-full bg-[var(--primary)]/10 text-[var(--primary)] font-bold">
                  {count}
                </span>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Table */}
      <div className="rounded-2xl border border-[var(--border)] bg-white shadow-[var(--shadow-card)] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] bg-muted/50">
                <th className="px-4 py-3 text-left font-semibold text-foreground w-16">
                  Ligne
                </th>
                <th className="px-4 py-3 text-left font-semibold text-foreground w-24">
                  Statut
                </th>
                <th className="px-4 py-3 text-left font-semibold text-foreground">
                  Donnees
                </th>
                <th className="px-4 py-3 text-left font-semibold text-foreground w-32">
                  Modifications
                </th>
              </tr>
            </thead>
            <tbody>
              {(data.rows || []).slice(0, 50).map((row: any) => {
                const config = STATUS_CONFIG[row.status as keyof typeof STATUS_CONFIG] || STATUS_CONFIG.kept;
                const StatusIcon = config.icon;

                return (
                  <tr
                    key={row.row_number}
                    className={`border-b border-[var(--border)] hover:bg-muted/30 cursor-pointer transition-colors ${
                      selectedRow === row.row_number ? "bg-[var(--primary)]/5" : ""
                    }`}
                    onClick={() =>
                      setSelectedRow(selectedRow === row.row_number ? null : row.row_number)
                    }
                  >
                    <td className="px-4 py-3 font-mono text-muted-foreground">
                      {row.row_number}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium ${config.color}`}
                      >
                        <StatusIcon className="h-3 w-3" />
                        {config.label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(row.before)
                          .slice(0, 4)
                          .map(([key, val]) => (
                            <span
                              key={key}
                              className="px-2 py-0.5 rounded bg-muted text-xs text-muted-foreground"
                            >
                              <span className="font-medium">{key}:</span>{" "}
                              {String(val ?? "").slice(0, 20)}
                            </span>
                          ))}
                        {Object.keys(row.before).length > 4 && (
                          <span className="px-2 py-0.5 rounded bg-muted text-xs text-muted-foreground">
                            +{Object.keys(row.before).length - 4}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {row.changes.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {row.changes.slice(0, 2).map((change: any, i: number) => (
                            <span
                              key={i}
                              className="px-2 py-0.5 rounded bg-amber-50 border border-amber-200 text-xs text-amber-700"
                            >
                              {change.column}: {change.action}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {(data.rows || []).length > 50 && (
          <div className="px-4 py-3 border-t border-[var(--border)] text-center text-xs text-muted-foreground">
            Affichage de 50 / {(data.rows || []).length} lignes
          </div>
        )}
      </div>

      {/* Selected row detail */}
      {selectedRowData && (
        <div className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-[var(--shadow-card)]">
          <h3 className="font-semibold text-foreground mb-4">
            Detail ligne {selectedRowData.row_number}
          </h3>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <h4 className="text-xs uppercase tracking-wider text-amber-600 font-semibold mb-2">
                Avant
              </h4>
              <div className="rounded-xl bg-amber-50 border border-amber-200 p-4">
                {Object.entries(selectedRowData.before).map(([key, val]) => (
                  <div key={key} className="flex justify-between py-1 border-b border-amber-100 last:border-0">
                    <span className="text-xs font-medium text-amber-700">{key}</span>
                    <span className="text-xs text-amber-900 font-mono">{String(val ?? "—")}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h4 className="text-xs uppercase tracking-wider text-emerald-600 font-semibold mb-2">
                Apres
              </h4>
              <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-4">
                {Object.entries(selectedRowData.after).map(([key, val]) => {
                  const change = selectedRowData.changes.find((c: any) => c.column === key);
                  const isChanged = !!change;

                  return (
                    <div
                      key={key}
                      className={`flex justify-between py-1 border-b last:border-0 ${
                        isChanged
                          ? "border-emerald-300 bg-emerald-100/50 -mx-1 px-1 rounded"
                          : "border-emerald-100"
                      }`}
                    >
                      <span className="text-xs font-medium text-emerald-700">{key}</span>
                      <span className="text-xs text-emerald-900 font-mono">{String(val ?? "—")}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Close button */}
      {onClose && (
        <div className="flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2.5 rounded-full border border-[var(--border)] text-muted-foreground hover:bg-muted transition-colors text-sm font-medium"
          >
            Fermer
          </button>
        </div>
      )}
    </div>
  );
}

function StatBox({
  label,
  value,
  color,
}: {
  label: string;
  value: number | string;
  color: string;
}) {
  return (
    <div className={`rounded-xl border p-4 ${color}`}>
      <p className="text-[10px] uppercase tracking-wider font-semibold opacity-80">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  );
}

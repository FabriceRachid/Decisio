import { useState, useEffect } from "react";
import {
  FileSearch,
  CheckCircle2,
  AlertTriangle,
  Columns,
  Rows3,
  ArrowDownUp,
  Loader2,
  ChevronDown,
  ChevronUp,
  Eye,
  Zap,
  Scissors,
  Expand,
} from "lucide-react";
import { apiClient } from "@/lib/api";

interface RulePreview {
  rule_type: string;
  name: string;
  description: string;
  impact: {
    type: string;
    detail: string;
  };
  priority: number;
}

interface PlanSummary {
  subtables_count: number;
  renames_count: number;
  ambiguities_count: number;
  cell_transforms_count: number;
  confidence: number;
  [key: string]: any;
}

interface RuleReviewProps {
  sourceId: number;
  reconstructionPlan: Record<string, any>;
  onExecuteComplete?: (result: any) => void;
  onCancel?: () => void;
}

const IMPACT_ICONS: Record<string, typeof Rows3> = {
  row_reduction: Rows3,
  column_rename: Columns,
  row_removal: Rows3,
  column_removal: Columns,
  flagging: AlertTriangle,
  column_split: Scissors,
  value_correction: CheckCircle2,
  row_explosion: Expand,
  unpivot: ArrowDownUp,
};

const IMPACT_COLORS: Record<string, string> = {
  row_reduction: "text-amber-600 bg-amber-50 border-amber-200",
  column_rename: "text-blue-600 bg-blue-50 border-blue-200",
  row_removal: "text-rose-600 bg-rose-50 border-rose-200",
  column_removal: "text-rose-600 bg-rose-50 border-rose-200",
  flagging: "text-violet-600 bg-violet-50 border-violet-200",
  column_split: "text-teal-600 bg-teal-50 border-teal-200",
  value_correction: "text-emerald-600 bg-emerald-50 border-emerald-200",
  row_explosion: "text-orange-600 bg-orange-50 border-orange-200",
  unpivot: "text-indigo-600 bg-indigo-50 border-indigo-200",
};

export function RuleReview({
  sourceId,
  reconstructionPlan,
  onExecuteComplete,
  onCancel,
}: RuleReviewProps) {
  const [rules, setRules] = useState<RulePreview[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedRule, setExpandedRule] = useState<number | null>(null);
  const [executionResult, setExecutionResult] = useState<any>(null);

  useEffect(() => {
    loadPreview();
  }, [sourceId, reconstructionPlan]);

  async function loadPreview() {
    setLoading(true);
    setError(null);
    try {
      const result = await apiClient.previewPlanRules(sourceId, reconstructionPlan);
      setRules(result.rules);
      setSummary(result.plan_summary);
    } catch (err: any) {
      setError(err.message || "Erreur lors du chargement de l'apercu");
    } finally {
      setLoading(false);
    }
  }

  async function handleApplyAndExecute() {
    setExecuting(true);
    setError(null);
    try {
      const result = await apiClient.applyPlan(sourceId, reconstructionPlan, true);
      setExecutionResult(result);
      onExecuteComplete?.(result);
    } catch (err: any) {
      setError(err.message || "Erreur lors de l'application du nettoyage");
    } finally {
      setExecuting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-8 w-8 animate-spin text-[var(--primary)]" />
        <span className="ml-3 text-lg text-muted-foreground">
          Analyse du plan de restructuration...
        </span>
      </div>
    );
  }

  if (error && !rules.length) {
    return (
      <div className="rounded-2xl border border-rose-200 bg-rose-50 p-8 text-center">
        <AlertTriangle className="mx-auto h-10 w-10 text-rose-500" />
        <p className="mt-3 text-rose-700 font-medium">{error}</p>
        <button
          onClick={loadPreview}
          className="mt-4 px-4 py-2 rounded-full bg-rose-100 text-rose-700 hover:bg-rose-200 transition text-sm font-medium"
        >
          Reessayer
        </button>
      </div>
    );
  }

  if (executionResult) {
    return (
      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-8">
        <div className="flex items-center gap-3 mb-4">
          <div className="h-12 w-12 rounded-full bg-emerald-100 flex items-center justify-center">
            <CheckCircle2 className="h-6 w-6 text-emerald-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-emerald-900">
              Nettoyage execute avec succes
            </h3>
            <p className="text-sm text-emerald-700">
              {executionResult.summary?.rows_affected || 0} ligne(s) traitee(s)
            </p>
          </div>
        </div>
        {executionResult.summary && (
          <div className="grid grid-cols-3 gap-4 mt-6">
            <div className="rounded-xl bg-white p-4 border border-emerald-100">
              <p className="text-xs uppercase tracking-wider text-emerald-600 font-medium">
                Lignes traitees
              </p>
              <p className="text-2xl font-bold text-emerald-900 mt-1">
                {executionResult.summary.rows_processed || 0}
              </p>
            </div>
            <div className="rounded-xl bg-white p-4 border border-emerald-100">
              <p className="text-xs uppercase tracking-wider text-emerald-600 font-medium">
                Lignes affectees
              </p>
              <p className="text-2xl font-bold text-emerald-900 mt-1">
                {executionResult.summary.rows_affected || 0}
              </p>
            </div>
            <div className="rounded-xl bg-white p-4 border border-emerald-100">
              <p className="text-xs uppercase tracking-wider text-emerald-600 font-medium">
                Lignes ignorees
              </p>
              <p className="text-2xl font-bold text-emerald-900 mt-1">
                {executionResult.summary.rows_skipped || 0}
              </p>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-2xl border border-[var(--border)] bg-white p-6 shadow-[var(--shadow-card)]">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-[var(--primary)] to-[var(--primary)]/80 flex items-center justify-center shadow-lg">
              <FileSearch className="h-7 w-7 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-foreground">
                Apercu des regles de nettoyage
              </h2>
              <p className="text-sm text-muted-foreground mt-0.5">
                {rules.length} regle(s) seront appliquees pour restructurer vos donnees
              </p>
            </div>
          </div>
          {summary && (
            <div className="flex items-center gap-2">
              {reconstructionPlan.type_transformation && reconstructionPlan.type_transformation !== "flat" && (
                <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                  reconstructionPlan.type_transformation === "unpivot"
                    ? "bg-indigo-50 text-indigo-700 border border-indigo-200"
                    : reconstructionPlan.type_transformation === "mixed"
                    ? "bg-amber-50 text-amber-700 border border-amber-200"
                    : "bg-teal-50 text-teal-700 border border-teal-200"
                }`}>
                  {reconstructionPlan.type_transformation === "unpivot" && "Pivot / Crosstab"}
                  {reconstructionPlan.type_transformation === "cell_level" && "Niveau cellulaire"}
                  {reconstructionPlan.type_transformation === "mixed" && "Mixte (pivot + cellulaire)"}
                </span>
              )}
              <span className="px-3 py-1 rounded-full bg-[var(--primary)]/10 text-[var(--primary)] text-xs font-semibold">
                Confiance: {Math.round(summary.confidence * 100)}%
              </span>
            </div>
          )}
        </div>

        {reconstructionPlan.mapping_pivot && (
          <div className="mt-4 p-3 rounded-lg bg-indigo-50/50 border border-indigo-200">
            <div className="flex items-center gap-2 mb-2">
              <ArrowDownUp className="h-4 w-4 text-indigo-600" />
              <span className="text-sm font-semibold text-indigo-800">Depivotage (crosstab → format long)</span>
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <span className="font-medium text-indigo-700">Colonnes identifiantes:</span>
                <div className="mt-1 flex flex-wrap gap-1">
                  {reconstructionPlan.mapping_pivot.colonnes_identifiantes?.map((c: string) => (
                    <span key={c} className="px-2 py-0.5 rounded bg-white border border-indigo-200 text-indigo-700">{c}</span>
                  ))}
                </div>
              </div>
              <div>
                <span className="font-medium text-indigo-700">Colonnes de valeurs:</span>
                <span className="ml-1 text-indigo-500">({reconstructionPlan.mapping_pivot.colonnes_valeurs?.length} colonnes)</span>
              </div>
              <div>
                <span className="font-medium text-indigo-700">Nouvelle colonne dimension:</span>
                <span className="ml-1 text-indigo-600">{reconstructionPlan.mapping_pivot.nom_nouvelle_colonne_dimension}</span>
              </div>
              <div>
                <span className="font-medium text-indigo-700">Nouvelle colonne valeur:</span>
                <span className="ml-1 text-indigo-600">{reconstructionPlan.mapping_pivot.nom_nouvelle_colonne_valeur}</span>
              </div>
            </div>
          </div>
        )}

        {/* Summary pills */}
        {summary && (
          <div className="flex flex-wrap gap-2 mt-5">
            {summary.subtables_count > 1 && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 text-xs font-medium">
                <Rows3 className="h-3.5 w-3.5" />
                {summary.subtables_count} sous-tables detectees
              </span>
            )}
            {summary.renames_count > 0 && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 text-xs font-medium">
                <Columns className="h-3.5 w-3.5" />
                {summary.renames_count} colonne(s) a renommer
              </span>
            )}
            {summary.ambiguities_count > 0 && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-violet-50 text-violet-700 border border-violet-200 text-xs font-medium">
                <AlertTriangle className="h-3.5 w-3.5" />
                {summary.ambiguities_count} anomalie(s)
              </span>
            )}
            {summary.cell_transforms_count > 0 && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-teal-50 text-teal-700 border border-teal-200 text-xs font-medium">
                <Scissors className="h-3.5 w-3.5" />
                {summary.cell_transforms_count} transformation(s) cellulaire(s)
              </span>
            )}
            {reconstructionPlan.type_transformation === "unpivot" && reconstructionPlan.mapping_pivot && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 text-xs font-medium">
                <ArrowDownUp className="h-3.5 w-3.5" />
                {reconstructionPlan.mapping_pivot.colonnes_valeurs?.length} colonnes → format long
              </span>
            )}
          </div>
        )}
      </div>

      {/* Rules list */}
      <div className="space-y-3">
        {rules.map((rule, index) => {
          const Icon = IMPACT_ICONS[rule.impact.type] || Zap;
          const colorClass = IMPACT_COLORS[rule.impact.type] || "text-gray-600 bg-gray-50 border-gray-200";
          const isExpanded = expandedRule === index;

          return (
            <div
              key={index}
              className="rounded-2xl border border-[var(--border)] bg-white overflow-hidden shadow-[var(--shadow-card)] hover:shadow-[var(--shadow-elev)] transition-shadow"
            >
              <button
                onClick={() => setExpandedRule(isExpanded ? null : index)}
                className="w-full flex items-center gap-4 p-5 text-left hover:bg-muted/30 transition-colors"
              >
                <div className={`h-10 w-10 rounded-xl flex items-center justify-center border ${colorClass}`}>
                  <Icon className="h-5 w-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-foreground">{rule.name}</span>
                    <span className="px-2 py-0.5 rounded-full bg-muted text-muted-foreground text-[10px] font-bold uppercase tracking-wider">
                      P{rule.priority}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground mt-0.5 truncate">
                    {rule.description}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`px-2.5 py-1 rounded-lg text-xs font-medium border ${colorClass}`}>
                    {rule.impact.detail}
                  </span>
                  {isExpanded ? (
                    <ChevronUp className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>
              </button>

              {isExpanded && (
                <div className="px-5 pb-5 pt-0 border-t border-[var(--border)]">
                  <div className="mt-4 rounded-xl bg-muted/50 p-4">
                    <h4 className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-2">
                      Details de la regle
                    </h4>
                    <p className="text-sm text-foreground">{rule.description}</p>
                    <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
                      <Eye className="h-3.5 w-3.5" />
                      <span>Type: {rule.rule_type}</span>
                      <span className="mx-1">•</span>
                      <span>Priorite: {rule.priority}/10</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Error banner */}
      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 text-rose-500 shrink-0" />
          <p className="text-sm text-rose-700">{error}</p>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center justify-end rounded-2xl border border-[var(--border)] bg-white p-5 shadow-[var(--shadow-card)]">
        <button
          onClick={onCancel}
          className="px-5 py-2.5 rounded-full border border-[var(--border)] text-muted-foreground hover:bg-muted transition-colors text-sm font-medium"
        >
          Annuler
        </button>
      </div>
    </div>
  );
}

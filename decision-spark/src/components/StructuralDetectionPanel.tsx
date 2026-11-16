import { useState, useEffect, useCallback } from "react";
import {
  Brain,
  Search,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader2,
  Eye,
  ChevronDown,
  ChevronUp,
  Layers,
  FileSpreadsheet,
  Sparkles,
  UserCheck,
} from "lucide-react";
import { toast } from "@/lib/toast";

interface StructuralFingerprint {
  total_rows: number;
  total_cols: number;
  merged_cells: Array<{ start_row: number; start_col: number; end_row: number; end_col: number }>;
  blank_rows: number[];
  blank_cols: number[];
  header_candidates: Array<{ row_index: number; fill_ratio: number; score: number }>;
  subtables: Array<{
    start_row: number;
    end_row: number;
    start_col: number;
    end_col: number;
    header_row: number | null;
    column_names: string[];
    confidence: number;
  }>;
  column_types: Record<string, string>;
  confidence: number;
  issues: string[];
}

interface ReconstructionSubtable {
  index: number;
  start_row: number;
  end_row: number;
  start_col: number;
  end_col: number;
  header_row: number | null;
  column_names: string[];
  action: string;
}

interface ReconstructionPlan {
  subtables: ReconstructionSubtable[];
  header_adjustments: Array<Record<string, unknown>>;
  column_renames: Record<string, string>;
  unresolved_zones: Array<Record<string, unknown>>;
  ambiguities: string[];
  confidence: number;
  source: string;
}

interface ValidationGate {
  gate: string;
  passed: boolean;
  message: string;
  details: Record<string, unknown>;
}

interface ValidationReport {
  all_passed: boolean;
  gates: ValidationGate[];
  confidence_modifier: number;
  requires_human_review: boolean;
  failure_reasons: string[];
}

interface StructuralDetectResult {
  run_id: number;
  snapshot_id: number;
  method_used: string;
  status: string;
  confidence_score: number;
  structural_fingerprint: StructuralFingerprint;
  reconstruction_plan: ReconstructionPlan | null;
  validation_report: ValidationReport | null;
  requires_human_review: boolean;
  correction_examples_used: number[];
  llm_model: string;
  llm_tokens_used: number;
  llm_duration_ms: number;
  duration_ms: number;
  error: string | null;
}

interface StructuralDetectionPanelProps {
  sourceId: number;
  sourceName: string;
  onReconstructionApplied?: (plan: ReconstructionPlan) => void;
}

const GATE_LABELS: Record<string, string> = {
  confidence_score: "Score de confiance",
  subtable_structure: "Structure sous-tableaux",
  column_continuity: "Continuite colonnes",
  unresolved_zones: "Zones non resolues",
  header_alignment: "Alignement en-tetes",
  subtable_count: "Nombre sous-tableaux",
  row_count_consistency: "Cohrence lignes",
};

export function StructuralDetectionPanel({
  sourceId,
  sourceName,
  onReconstructionApplied,
}: StructuralDetectionPanelProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<StructuralDetectResult | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [validating, setValidating] = useState(false);
  const [showPlan, setShowPlan] = useState(false);

  const detectStructure = useCallback(async (forceLlm = false) => {
    setLoading(true);
    try {
      const response = await fetch(
        `/api/nettoyage/structure/sources/${sourceId}/structural-detect/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${localStorage.getItem("access_token")}`,
          },
          body: JSON.stringify({ sheet_name: "", force_llm: forceLlm }),
        }
      );

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error || "Echec de la detection");
      }

      const data: StructuralDetectResult = await response.json();
      setResult(data);

      if (data.status === "awaiting_review") {
        toast("Fichier necessitant une revision humaine", { variant: "info" });
      } else if (data.method_used === "llm") {
        toast(`Detection LLM terminee (confiance: ${(data.confidence_score * 100).toFixed(0)}%)`, { variant: "success" });
      } else {
        toast(`Detection heuristique terminee (confiance: ${(data.confidence_score * 100).toFixed(0)}%)`, { variant: "success" });
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : "Erreur de detection", { variant: "error" });
    } finally {
      setLoading(false);
    }
  }, [sourceId]);

  const validateReconstruction = async (correctionType: string, description: string) => {
    if (!result) return;
    setValidating(true);
    try {
      const response = await fetch(
        `/api/nettoyage/structure/structural-runs/${result.run_id}/validate/`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${localStorage.getItem("access_token")}`,
          },
          body: JSON.stringify({
            correction_type: correctionType,
            description,
            apply_plan: true,
          }),
        }
      );

      if (!response.ok) throw new Error("Echec de la validation");

      toast("Validation enregistree — ajoutee a la memoire de corrections", { variant: "success" });

      if (result.reconstruction_plan && onReconstructionApplied) {
        onReconstructionApplied(result.reconstruction_plan);
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : "Erreur de validation", { variant: "error" });
    } finally {
      setValidating(false);
    }
  };

  const toggleSection = (key: string) => {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const fp = result?.structural_fingerprint;
  const plan = result?.reconstruction_plan;
  const validation = result?.validation_report;

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-100 rounded-lg">
            <Brain className="w-5 h-5 text-purple-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">Detection Intelligente de Structure</h3>
            <p className="text-sm text-gray-500">{sourceName}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => detectStructure(false)}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 text-sm font-medium"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            Detecter
          </button>
          {result && result.confidence_score < 0.8 && (
            <button
              onClick={() => detectStructure(true)}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 disabled:opacity-50 text-sm font-medium"
            >
              <Sparkles className="w-4 h-4" />
              Forcer LLM
            </button>
          )}
        </div>
      </div>

      {/* Results */}
      {result && (
        <div className="p-6 space-y-4">
          {/* Status Bar */}
          <div className="flex flex-wrap gap-3">
            <StatusBadge
              icon={result.method_used === "llm" ? <Sparkles className="w-4 h-4" /> : <Search className="w-4 h-4" />}
              label={result.method_used === "llm" ? "LLM" : "Heuristique"}
              color={result.method_used === "llm" ? "purple" : "blue"}
            />
            <StatusBadge
              icon={
                result.confidence_score >= 0.8 ? (
                  <CheckCircle2 className="w-4 h-4" />
                ) : result.confidence_score >= 0.5 ? (
                  <AlertTriangle className="w-4 h-4" />
                ) : (
                  <XCircle className="w-4 h-4" />
                )
              }
              label={`Confiance: ${(result.confidence_score * 100).toFixed(0)}%`}
              color={
                result.confidence_score >= 0.8
                  ? "green"
                  : result.confidence_score >= 0.5
                  ? "yellow"
                  : "red"
              }
            />
            {result.requires_human_review && (
              <StatusBadge icon={<UserCheck className="w-4 h-4" />} label="Revision requise" color="orange" />
            )}
            <StatusBadge
              icon={<FileSpreadsheet className="w-4 h-4" />}
              label={`${plan?.subtables?.length || 0} sous-tableau(x)`}
              color="gray"
            />
          </div>

          {/* Structural Fingerprint */}
          {fp && (
            <CollapsibleSection
              title="Empreinte Structurelle"
              icon={<Layers className="w-4 h-4" />}
              expanded={expanded.fingerprint}
              onToggle={() => toggleSection("fingerprint")}
            >
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <StatCard label="Lignes" value={fp.total_rows} />
                <StatCard label="Colonnes" value={fp.total_cols} />
                <StatCard label="Cellules fusionnees" value={fp.merged_cells.length} warn={fp.merged_cells.length > 0} />
                <StatCard label="Lignes vides" value={fp.blank_rows.length} warn={fp.blank_rows.length > 3} />
              </div>

              {fp.issues.length > 0 && (
                <div className="mt-3 space-y-1">
                  {fp.issues.map((issue, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm text-orange-700 bg-orange-50 px-3 py-1.5 rounded">
                      <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                      {issue}
                    </div>
                  ))}
                </div>
              )}

              {fp.header_candidates.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs font-medium text-gray-500 mb-1">Candidates en-tete:</p>
                  {fp.header_candidates.slice(0, 3).map((h, i) => (
                    <div key={i} className="text-sm text-gray-600">
                      Ligne {h.row_index} — score: {(h.score * 100).toFixed(0)}%, remplissage: {(h.fill_ratio * 100).toFixed(0)}%
                    </div>
                  ))}
                </div>
              )}
            </CollapsibleSection>
          )}

          {/* Reconstruction Plan */}
          {plan && (
            <CollapsibleSection
              title="Plan de Reconstruction"
              icon={<Brain className="w-4 h-4" />}
              expanded={showPlan}
              onToggle={() => setShowPlan(!showPlan)}
            >
              <div className="space-y-3">
                {plan.subtables.map((st, i) => (
                  <div key={i} className="bg-gray-50 rounded-lg p-3 border border-gray-200">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-sm">Sous-tableau {i + 1}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        st.action === "keep" ? "bg-green-100 text-green-700" :
                        st.action === "drop" ? "bg-red-100 text-red-700" :
                        "bg-blue-100 text-blue-700"
                      }`}>
                        {st.action}
                      </span>
                    </div>
                    <div className="text-xs text-gray-500 space-y-0.5">
                      <div>Lignes {st.start_row} — {st.end_row} | Colonnes {st.start_col} — {st.end_col}</div>
                      <div>En-tete: ligne {st.header_row ?? "auto"}</div>
                      <div>Colonnes: {st.column_names.join(", ")}</div>
                    </div>
                  </div>
                ))}

                {plan.ambiguities.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-orange-600">Ambiguites:</p>
                    {plan.ambiguities.map((a, i) => (
                      <div key={i} className="text-sm text-orange-600 bg-orange-50 px-3 py-1 rounded">{a}</div>
                    ))}
                  </div>
                )}
              </div>
            </CollapsibleSection>
          )}

          {/* Validation Gates */}
          {validation && (
            <CollapsibleSection
              title={`Portes de Validation ${validation.all_passed ? "(Passees)" : "(Echecs)"}`}
              icon={validation.all_passed ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
              expanded={expanded.gates}
              onToggle={() => toggleSection("gates")}
            >
              <div className="space-y-2">
                {validation.gates.map((gate, i) => (
                  <div
                    key={i}
                    className={`flex items-center justify-between px-3 py-2 rounded text-sm ${
                      gate.passed ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      {gate.passed ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                      <span className="font-medium">{GATE_LABELS[gate.gate] || gate.gate}</span>
                    </div>
                    <span className="text-xs">{gate.message}</span>
                  </div>
                ))}
              </div>
            </CollapsibleSection>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2 border-t border-gray-100">
            <button
              onClick={() => validateReconstruction("structural", "Auto-validation de la detection")}
              disabled={validating}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm font-medium"
            >
              {validating ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
              Valider et Appliquer
            </button>
            <button
              onClick={() => {
                if (result) {
                  const desc = prompt("Decrivez la correction a apporter:");
                  if (desc) validateReconstruction("structural", desc);
                }
              }}
              disabled={validating}
              className="flex items-center gap-2 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50 text-sm"
            >
              <Eye className="w-4 h-4" />
              Corriger Manuellement
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusBadge({
  icon,
  label,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  color: "green" | "yellow" | "red" | "blue" | "purple" | "orange" | "gray";
}) {
  const colors = {
    green: "bg-green-100 text-green-700",
    yellow: "bg-yellow-100 text-yellow-700",
    red: "bg-red-100 text-red-700",
    blue: "bg-blue-100 text-blue-700",
    purple: "bg-purple-100 text-purple-700",
    orange: "bg-orange-100 text-orange-700",
    gray: "bg-gray-100 text-gray-700",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${colors[color]}`}>
      {icon}
      {label}
    </span>
  );
}

function StatCard({ label, value, warn }: { label: string; value: number; warn?: boolean }) {
  return (
    <div className={`p-3 rounded-lg ${warn ? "bg-orange-50 border border-orange-200" : "bg-gray-50 border border-gray-200"}`}>
      <div className={`text-lg font-bold ${warn ? "text-orange-700" : "text-gray-900"}`}>{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}

function CollapsibleSection({
  title,
  icon,
  expanded,
  onToggle,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 text-sm font-medium text-gray-700"
      >
        <div className="flex items-center gap-2">
          {icon}
          {title}
        </div>
        {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>
      {expanded && <div className="p-4">{children}</div>}
    </div>
  );
}

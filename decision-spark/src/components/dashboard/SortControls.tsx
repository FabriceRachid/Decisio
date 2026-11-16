import { ArrowUpDown, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

type SortOption = {
  value: string;
  label: string;
};

const SORT_OPTIONS: SortOption[] = [
  { value: "default", label: "Ordre par défaut" },
  { value: "value_desc", label: "Valeur (décroissant)" },
  { value: "value_asc", label: "Valeur (croissant)" },
  { value: "title_asc", label: "Nom (A-Z)" },
  { value: "title_desc", label: "Nom (Z-A)" },
  { value: "type", label: "Type de widget" },
];

type SortControlsProps = {
  value: string;
  onChange: (value: string) => void;
  totalWidgets: number;
};

export function SortControls({ value, onChange, totalWidgets }: SortControlsProps) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <ArrowUpDown className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">Trier</span>
      </div>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="appearance-none rounded-lg border border-border/60 bg-card px-2.5 py-1.5 pr-7 text-xs font-medium text-foreground outline-none hover:border-primary/40 focus:border-primary"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-1.5 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" />
      </div>
      <span className="text-xs text-muted-foreground">({totalWidgets} widgets)</span>
    </div>
  );
}

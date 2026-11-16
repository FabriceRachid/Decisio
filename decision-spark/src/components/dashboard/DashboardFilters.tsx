import { Filter } from "lucide-react";
import { cn } from "@/lib/utils";

type DashboardFiltersProps = {
  availableFilters: Record<string, string[]>;
  selectedFilters: Record<string, string[]>;
  showFilters: boolean;
  hasActiveFilters: boolean;
  onToggleFilter: (field: string, value: string) => void;
  onToggleShow: () => void;
  onClearAll: () => void;
};

const labelMap: Record<string, string> = {
  regions: "Région",
  produits: "Produit",
  categories: "Catégorie",
  vendeurs: "Vendeur",
};

export function DashboardFilters({
  availableFilters, selectedFilters, showFilters, hasActiveFilters,
  onToggleFilter, onToggleShow, onClearAll,
}: DashboardFiltersProps) {
  return (
    <div className="rounded-xl border border-border/60 bg-card shadow-card">
      <div className="flex items-center justify-between px-4 py-2.5">
        <button
          onClick={onToggleShow}
          className={cn(
            "inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition",
            hasActiveFilters
              ? "bg-primary/10 text-primary-strong"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Filter className="h-4 w-4" />
          Filtres
          {hasActiveFilters && (
            <span className="grid h-5 w-5 place-items-center rounded-full bg-primary text-[11px] font-bold text-primary-foreground">
              {Object.keys(selectedFilters).length}
            </span>
          )}
        </button>
        {hasActiveFilters && (
          <button onClick={onClearAll} className="text-xs font-medium text-destructive hover:underline">
            Tout effacer
          </button>
        )}
      </div>
      {showFilters && (
        <div className="border-t border-border/50 px-4 py-3">
          <div className="flex flex-wrap gap-4">
            {(Object.entries(availableFilters) as [string, string[]][]).map(([field, options]) => {
              if (!Array.isArray(options) || options.length === 0) return null;
              const label = labelMap[field] || field;
              const selected = selectedFilters[field] || [];
              return (
                <div key={field} className="min-w-[180px]">
                  <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {label}
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    {options.slice(0, 20).map((option) => {
                      const isSelected = selected.includes(option);
                      return (
                        <button
                          key={option}
                          onClick={() => onToggleFilter(field, option)}
                          className={cn(
                            "rounded-full px-2.5 py-1 text-xs font-medium transition",
                            isSelected
                              ? "bg-primary text-primary-foreground"
                              : "bg-secondary text-muted-foreground hover:bg-secondary/80",
                          )}
                        >
                          {option}
                        </button>
                      );
                    })}
                    {options.length > 20 && (
                      <span className="px-2 py-1 text-xs text-muted-foreground">+{options.length - 20}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

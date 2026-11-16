import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export type StepperStep<K extends string> = {
  key: K;
  label: string;
  description?: string;
};

/**
 * Indicateur d'étapes d'un flux guidé. Les étapes déjà franchies sont cliquables
 * si `onStepClick` est fourni ; l'étape courante est annoncée via `aria-current`.
 */
export function Stepper<K extends string>({
  steps,
  current,
  onStepClick,
  label = "Étapes",
  className,
}: {
  steps: StepperStep<K>[];
  current: K;
  onStepClick?: (key: K) => void;
  label?: string;
  className?: string;
}) {
  const currentIndex = Math.max(
    0,
    steps.findIndex((s) => s.key === current),
  );

  return (
    <nav aria-label={label} className={className}>
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-2">
        {steps.map((step, i) => {
          const done = i < currentIndex;
          const active = i === currentIndex;
          const clickable = done && !!onStepClick;
          const inner = (
            <>
              <span
                className={cn(
                  "grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-semibold transition",
                  active && "bg-primary text-primary-foreground shadow-sm",
                  done && "bg-emerald-600 text-white",
                  !active && !done && "border border-border bg-card text-muted-foreground",
                )}
              >
                {done ? <Check className="h-3.5 w-3.5" aria-hidden /> : i + 1}
              </span>
              <span className="min-w-0 text-left">
                <span
                  className={cn(
                    "block text-sm leading-tight",
                    active ? "font-semibold text-foreground" : "text-muted-foreground",
                  )}
                >
                  {step.label}
                </span>
                {step.description && (
                  <span className="hidden text-xs text-muted-foreground sm:block">
                    {step.description}
                  </span>
                )}
              </span>
            </>
          );
          return (
            <li key={step.key} className="flex items-center gap-2">
              {clickable ? (
                <button
                  type="button"
                  onClick={() => onStepClick(step.key)}
                  className="flex items-center gap-2 rounded-lg px-1 py-0.5 transition hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {inner}
                </button>
              ) : (
                <span
                  className="flex items-center gap-2 px-1 py-0.5"
                  aria-current={active ? "step" : undefined}
                >
                  {inner}
                </span>
              )}
              {i < steps.length - 1 && (
                <span
                  aria-hidden
                  className={cn("mx-1 h-px w-6 sm:w-10", done ? "bg-emerald-600" : "bg-border")}
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

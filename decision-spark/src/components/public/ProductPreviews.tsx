import {
  Bot,
  Check,
  FileSpreadsheet,
  LayoutDashboard,
  MessageSquareText,
  Upload,
} from "lucide-react";
import type { ReactNode } from "react";

/**
 * Aperçus du produit pour le site public.
 * Ce sont des illustrations construites en code avec des données d'exemple.
 * Pour afficher de vraies captures, passer `image` à <ProductFrame>.
 */

export function ProductFrame({
  title,
  image,
  imageAlt,
  children,
}: {
  title: string;
  image?: string;
  imageAlt?: string;
  children?: ReactNode;
}) {
  return (
    <figure className="overflow-hidden rounded-2xl border border-night-line bg-night-elevated shadow-2xl shadow-black/40">
      <div className="flex items-center gap-3 border-b border-night-line px-4 py-3">
        <div className="flex gap-1.5" aria-hidden>
          <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
          <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
          <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
        </div>
        <span className="truncate text-xs text-ink-subtle">{title}</span>
      </div>
      {image ? (
        <img src={image} alt={imageAlt ?? title} className="block w-full" loading="lazy" />
      ) : (
        children
      )}
    </figure>
  );
}

function ExampleBadge() {
  return (
    <span className="rounded-full border border-white/15 px-2 py-0.5 text-[11px] text-ink-subtle">
      Données d'exemple
    </span>
  );
}

const bars = [38, 46, 41, 58, 52, 67, 61, 74, 69, 82, 77, 90];

export function DashboardPreview() {
  return (
    <ProductFrame title="Tableau de bord — Ventes 2024">
      <div className="grid sm:grid-cols-[170px_1fr]">
        <aside className="hidden border-r border-night-line p-4 sm:block" aria-hidden>
          <ul className="space-y-1 text-xs text-ink-subtle">
            {[
              { Icon: LayoutDashboard, label: "Tableau de bord", active: true },
              { Icon: Upload, label: "Importer", active: false },
              { Icon: MessageSquareText, label: "Assistant IA", active: false },
            ].map(({ Icon, label, active }) => (
              <li
                key={label}
                className={`flex items-center gap-2 rounded-lg px-2.5 py-2 ${
                  active ? "bg-white/[0.07] text-ink" : ""
                }`}
              >
                <Icon className="h-3.5 w-3.5" /> {label}
              </li>
            ))}
          </ul>
        </aside>
        <div className="p-5">
          <div className="flex items-center justify-between gap-3">
            <p className="font-brand text-sm font-semibold text-ink">Vue d'ensemble</p>
            <ExampleBadge />
          </div>
          <div className="mt-4 grid grid-cols-3 gap-3">
            {[
              ["Chiffre d'affaires", "12,4 M", "+8,2 %"],
              ["Commandes", "1 284", "+3,1 %"],
              ["Panier moyen", "9 650", "+4,9 %"],
            ].map(([label, value, delta]) => (
              <div key={label} className="rounded-xl border border-night-line bg-night p-3">
                <p className="truncate text-[11px] text-ink-subtle">{label}</p>
                <p className="mt-1 font-brand text-lg font-bold text-ink">{value}</p>
                <p className="text-[11px] font-medium text-emerald-400">{delta}</p>
              </div>
            ))}
          </div>
          <div className="mt-3 rounded-xl border border-night-line bg-night p-4">
            <p className="text-xs text-ink-muted">Évolution mensuelle (FCFA)</p>
            <div className="mt-4 flex h-28 items-end gap-1.5" aria-hidden>
              {bars.map((h, i) => (
                <div
                  key={i}
                  className={`flex-1 rounded-t ${i === bars.length - 1 ? "bg-cta" : "bg-data/60"}`}
                  style={{ height: `${h}%` }}
                />
              ))}
            </div>
          </div>
          <div className="mt-3 flex items-start gap-3 rounded-xl border border-amber-400/25 bg-amber-400/[0.07] p-3">
            <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-amber-400" />
            <p className="text-xs text-ink-muted">
              <span className="font-semibold text-ink">Anomalie détectée :</span> ventes de la
              région Centre inférieures de 22 % à la moyenne habituelle.
            </p>
          </div>
        </div>
      </div>
    </ProductFrame>
  );
}

export function CleaningPreview() {
  const rows = [
    ["  ouagadougou", "Ouagadougou"],
    ["OUAGA", "Ouagadougou"],
    ["12/03/24", "2024-03-12"],
    ["1 200,00 F", "1200"],
  ];
  return (
    <ProductFrame title="Nettoyage — clients.xlsx">
      <div className="p-5">
        <div className="flex items-center gap-2 text-xs text-ink-muted">
          <FileSpreadsheet className="h-4 w-4 text-data" /> 4 corrections proposées
        </div>
        <table className="mt-4 w-full text-left text-xs">
          <thead className="text-ink-subtle">
            <tr>
              <th className="pb-2 font-medium">Avant</th>
              <th className="pb-2 font-medium">Après</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-night-line">
            {rows.map(([before, after]) => (
              <tr key={before}>
                <td className="py-2 font-mono text-rose-300/90 line-through decoration-rose-300/40">
                  {before}
                </td>
                <td className="py-2 font-mono text-emerald-300">{after}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="mt-4 flex flex-wrap gap-2">
          {["3 doublons fusionnés", "Dates harmonisées", "Montants convertis"].map((t) => (
            <span
              key={t}
              className="inline-flex items-center gap-1 rounded-full bg-emerald-400/10 px-2.5 py-1 text-[11px] text-emerald-300"
            >
              <Check className="h-3 w-3" /> {t}
            </span>
          ))}
        </div>
      </div>
    </ProductFrame>
  );
}

export function ChatPreview() {
  return (
    <ProductFrame title="Assistant IA — source « Ventes 2024 »">
      <div className="space-y-3 p-5 text-xs">
        <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-data/20 px-3.5 py-2.5 text-ink">
          Quelle catégorie a le plus progressé ce mois-ci ?
        </div>
        <div className="flex max-w-[92%] gap-2">
          <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-cta/15">
            <Bot className="h-3.5 w-3.5 text-cta" />
          </span>
          <div className="rounded-2xl rounded-tl-md border border-night-line bg-night px-3.5 py-2.5 leading-relaxed text-ink-muted">
            La catégorie <span className="font-semibold text-ink">Boissons</span> progresse le plus
            : <span className="font-semibold text-emerald-400">+14 %</span> par rapport au mois
            précédent, portée par la région Ouest.
          </div>
        </div>
        <div className="pt-1">
          <ExampleBadge />
        </div>
      </div>
    </ProductFrame>
  );
}

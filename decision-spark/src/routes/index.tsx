import { createFileRoute, Link } from "@tanstack/react-router";
import {
  AlertTriangle,
  BarChart3,
  Bot,
  Building2,
  ChevronDown,
  Factory,
  FileSpreadsheet,
  Files,
  GitMerge,
  LockKeyhole,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Timer,
  Truck,
  Upload,
  Users,
} from "lucide-react";
import {
  CtaArrow,
  PublicFooter,
  PublicHeader,
  ctaClass,
  secondaryClass,
} from "@/components/public/PublicShell";
import {
  ChatPreview,
  CleaningPreview,
  DashboardPreview,
} from "@/components/public/ProductPreviews";

export const Route = createFileRoute("/")({
  component: Landing,
  head: () => ({
    meta: [
      { title: "DécisioBI — Transformez vos fichiers Excel en décisions claires" },
      {
        name: "description",
        content:
          "DécisioBI nettoie vos fichiers Excel et CSV, calcule vos indicateurs et répond à vos questions en français. Pensé pour les PME.",
      },
    ],
  }),
});

const pains = [
  {
    icon: Files,
    title: "Des fichiers partout",
    body: "Ventes, stocks, clients : chaque service a son tableur, et personne n'a la même version.",
  },
  {
    icon: AlertTriangle,
    title: "Des données peu fiables",
    body: "Doublons, dates mal saisies, cellules fusionnées : les erreurs faussent les totaux.",
  },
  {
    icon: Timer,
    title: "Pas le temps d'analyser",
    body: "Le dirigeant veut une réponse, pas un tableau croisé dynamique à construire.",
  },
];

const features = [
  {
    icon: GitMerge,
    title: "Des données nettoyées automatiquement",
    body: "DécisioBI repère la structure de vos fichiers, harmonise les formats, fusionne les doublons et vous signale les conflits à arbitrer.",
    points: [
      "Excel multi-feuilles et CSV",
      "Tableaux mal formatés reconstruits",
      "Conflits signalés",
    ],
  },
  {
    icon: BarChart3,
    title: "Vos indicateurs, à jour et lisibles",
    body: "Les KPI sont calculés à partir de vos sources et présentés dans des tableaux de bord que vous pouvez personnaliser.",
    points: [
      "Tableaux de bord personnalisables",
      "Détection d'anomalies",
      "Rapports PDF programmés",
    ],
  },
  {
    icon: Bot,
    title: "Un assistant qui répond en français",
    body: "Posez votre question comme à un collègue. L'assistant s'appuie sur la source sélectionnée et cite les indicateurs utilisés.",
    points: [
      "Questions en langage courant",
      "Réponses liées à vos données",
      "Historique des échanges",
    ],
  },
];

const steps = [
  {
    number: "1",
    icon: Upload,
    title: "Importez votre fichier",
    body: "Glissez un fichier Excel ou CSV. DécisioBI détecte sa structure et propose les corrections.",
    preview: <CleaningPreview />,
  },
  {
    number: "2",
    icon: BarChart3,
    title: "Consultez vos indicateurs",
    body: "Vos KPI et leurs évolutions apparaissent dans le tableau de bord, avec les anomalies mises en évidence.",
    preview: <DashboardPreview />,
  },
  {
    number: "3",
    icon: Bot,
    title: "Posez vos questions",
    body: "Interrogez l'assistant sur la source choisie pour comprendre ce qui se passe et décider.",
    preview: <ChatPreview />,
  },
];

const sectors = [
  {
    icon: ShoppingBag,
    title: "Commerce et distribution",
    body: "Ventes par produit et par point de vente, ruptures, panier moyen.",
  },
  {
    icon: Building2,
    title: "Services",
    body: "Facturation, suivi des clients, activité par collaborateur.",
  },
  {
    icon: Factory,
    title: "Industrie et production",
    body: "Volumes produits, coûts, écarts par rapport aux objectifs.",
  },
  {
    icon: Truck,
    title: "Logistique",
    body: "Livraisons, délais, performance par zone ou par transporteur.",
  },
];

const trustPoints = [
  {
    icon: LockKeyhole,
    title: "Accès contrôlé",
    body: "Connexion obligatoire et droits définis par rôle pour chaque utilisateur.",
  },
  {
    icon: ShieldCheck,
    title: "Échanges chiffrés",
    body: "Toutes les communications passent par HTTPS ; les mots de passe sont hachés.",
  },
  {
    icon: Users,
    title: "Traçabilité",
    body: "Les actions importantes sont enregistrées dans un journal d'activité.",
  },
  {
    icon: Sparkles,
    title: "IA transparente",
    body: "Nous indiquons précisément quelles données sont envoyées au modèle d'IA.",
  },
];

const faqs = [
  {
    q: "Quels fichiers puis-je importer ?",
    a: "Des fichiers Excel (y compris avec plusieurs feuilles) et CSV. DécisioBI sait traiter des tableaux imparfaits : lignes vides, en-têtes décalés, cellules fusionnées.",
  },
  {
    q: "Faut-il des compétences techniques ?",
    a: "Non. Si vous savez ouvrir un fichier Excel, vous savez utiliser DécisioBI. Les corrections sont proposées automatiquement et vous gardez la main pour les valider.",
  },
  {
    q: "Où vont mes données quand j'utilise l'assistant ?",
    a: "Pour répondre, l'assistant envoie à notre fournisseur de modèle d'IA votre question et un contexte limité (noms de colonnes, quelques lignes d'exemple, valeurs des indicateurs). Le détail figure dans notre politique de confidentialité.",
    link: { to: "/confidentialite" as const, hash: "ia", label: "Voir le détail" },
  },
  {
    q: "Plusieurs personnes de mon entreprise peuvent-elles l'utiliser ?",
    a: "Oui. Le créateur de l'espace en devient l'administrateur : il invite ses collaborateurs et choisit le rôle de chacun.",
  },
  {
    q: "Puis-je supprimer mes données ?",
    a: "Oui. Vous pouvez supprimer une source importée à tout moment depuis votre espace. Chaque source a aussi une durée de conservation configurable.",
  },
  {
    q: "Les réponses de l'IA sont-elles fiables ?",
    a: "L'assistant s'appuie sur vos données, mais il peut se tromper. Ses réponses sont une aide à la décision : vérifiez les chiffres importants dans le tableau de bord.",
  },
];

function SectionHeading({
  eyebrow,
  title,
  body,
}: {
  eyebrow: string;
  title: string;
  body?: string;
}) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <p className="text-sm font-semibold text-data">{eyebrow}</p>
      <h2 className="mt-3 font-brand text-3xl font-bold tracking-tight text-ink md:text-4xl">
        {title}
      </h2>
      {body && <p className="mt-4 text-base leading-relaxed text-ink-muted">{body}</p>}
    </div>
  );
}

function Landing() {
  return (
    <div className="min-h-screen bg-night text-ink">
      {/* Hero */}
      <div className="bg-public-hero">
        <PublicHeader />
        <section className="mx-auto max-w-6xl px-6 pb-20 pt-12 md:pt-20">
          <div className="mx-auto max-w-3xl text-center">
            <p className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-xs text-ink-muted">
              <FileSpreadsheet className="h-3.5 w-3.5 text-data" />
              Pensé pour les PME · Excel et CSV · Assistant en français
            </p>
            <h1 className="mt-7 font-brand text-4xl font-extrabold leading-[1.08] tracking-tight text-ink sm:text-5xl md:text-6xl">
              Transformez vos données dispersées en{" "}
              <span className="text-cta">décisions claires.</span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-ink-muted">
              DécisioBI nettoie vos fichiers Excel et CSV, calcule vos indicateurs et répond à vos
              questions en français. Sans compétence technique.
            </p>
            <div className="mt-9 flex flex-col justify-center gap-3 sm:flex-row">
              <Link to="/register" className={`${ctaClass} px-7 py-3.5 text-base`}>
                Créer mon espace <CtaArrow />
              </Link>
              <a href="#parcours" className={`${secondaryClass} px-7 py-3.5 text-base`}>
                Voir comment ça marche
              </a>
            </div>
            <p className="mt-4 text-sm text-ink-subtle">
              Il suffit d'un fichier Excel ou CSV pour commencer.
            </p>
          </div>
          <div className="mx-auto mt-16 max-w-4xl">
            <DashboardPreview />
          </div>
        </section>
      </div>

      {/* Problème */}
      <section className="border-y border-night-line bg-night-elevated/50">
        <div className="mx-auto grid max-w-6xl gap-8 px-6 py-14 md:grid-cols-3">
          {pains.map(({ icon: Icon, title, body }) => (
            <div key={title} className="flex gap-4">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/5">
                <Icon className="h-5 w-5 text-ink-muted" />
              </span>
              <div>
                <h3 className="font-brand text-base font-bold text-ink">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">{body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Fonctionnalités */}
      <section id="fonctionnalites" className="scroll-mt-6 px-6 py-24">
        <SectionHeading
          eyebrow="Fonctionnalités"
          title="De la donnée brute à la bonne décision."
          body="Trois briques qui travaillent ensemble pour que vous passiez moins de temps sur vos tableurs et plus sur vos décisions."
        />
        <div className="mx-auto mt-14 grid max-w-6xl gap-5 md:grid-cols-3">
          {features.map(({ icon: Icon, title, body, points }) => (
            <article
              key={title}
              className="flex flex-col rounded-2xl border border-night-line bg-night-elevated p-7"
            >
              <span className="grid h-11 w-11 place-items-center rounded-xl bg-data/15">
                <Icon className="h-5 w-5 text-data" />
              </span>
              <h3 className="mt-6 font-brand text-xl font-bold text-ink">{title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-ink-muted">{body}</p>
              <ul className="mt-6 space-y-2 border-t border-night-line pt-5 text-sm text-ink-muted">
                {points.map((p) => (
                  <li key={p} className="flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-data" /> {p}
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>

      {/* Comment ça marche */}
      <section
        id="parcours"
        className="scroll-mt-6 border-t border-night-line bg-night-elevated/40 px-6 py-24"
      >
        <SectionHeading
          eyebrow="Comment ça marche"
          title="Trois étapes, de votre fichier à votre réponse."
        />
        <div className="mx-auto mt-16 max-w-6xl space-y-20">
          {steps.map(({ number, icon: Icon, title, body, preview }, i) => (
            <div key={number} className="grid items-center gap-10 lg:grid-cols-2 lg:gap-16">
              <div className={i % 2 === 1 ? "lg:order-2" : ""}>
                <div className="flex items-center gap-3">
                  <span className="grid h-9 w-9 place-items-center rounded-full bg-cta font-brand text-sm font-bold text-cta-foreground">
                    {number}
                  </span>
                  <Icon className="h-5 w-5 text-ink-subtle" />
                </div>
                <h3 className="mt-5 font-brand text-2xl font-bold text-ink md:text-3xl">{title}</h3>
                <p className="mt-4 max-w-md text-base leading-relaxed text-ink-muted">{body}</p>
              </div>
              <div className={i % 2 === 1 ? "lg:order-1" : ""}>{preview}</div>
            </div>
          ))}
        </div>
        <p className="mx-auto mt-16 max-w-2xl text-center text-sm text-ink-subtle">
          Les aperçus ci-dessus utilisent des données d'exemple. Vos résultats dépendent des
          fichiers que vous importez.
        </p>
      </section>

      {/* Secteurs */}
      <section className="px-6 py-24">
        <SectionHeading
          eyebrow="Pour qui ?"
          title="Pour les PME qui pilotent encore sur tableur."
          body="Quel que soit votre secteur, si vos chiffres vivent dans des fichiers Excel, DécisioBI les rend lisibles."
        />
        <div className="mx-auto mt-14 grid max-w-6xl gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {sectors.map(({ icon: Icon, title, body }) => (
            <div key={title} className="rounded-2xl border border-night-line p-6">
              <Icon className="h-6 w-6 text-data" />
              <h3 className="mt-5 font-brand text-base font-bold text-ink">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-muted">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Confiance */}
      <section className="px-6 pb-24">
        <div className="mx-auto max-w-6xl rounded-3xl border border-night-line bg-night-elevated p-8 md:p-12">
          <div className="grid gap-12 lg:grid-cols-[0.9fr_1.1fr]">
            <div>
              <p className="text-sm font-semibold text-data">Sécurité et confiance</p>
              <h2 className="mt-3 font-brand text-3xl font-bold tracking-tight text-ink">
                Vos données d'entreprise méritent de la transparence.
              </h2>
              <p className="mt-4 leading-relaxed text-ink-muted">
                Nous expliquons ce que fait le service, où sont traitées vos données et ce qui est
                envoyé à l'IA. Pas de promesse chiffrée invérifiable.
              </p>
              <Link
                to="/securite"
                className="mt-7 inline-flex items-center gap-2 text-sm font-semibold text-data transition hover:text-ink"
              >
                Lire notre page sécurité <CtaArrow />
              </Link>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {trustPoints.map(({ icon: Icon, title, body }) => (
                <div key={title} className="rounded-2xl border border-night-line bg-night p-5">
                  <Icon className="h-5 w-5 text-emerald-400" />
                  <h3 className="mt-4 font-brand text-sm font-bold text-ink">{title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">{body}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="scroll-mt-6 border-t border-night-line px-6 py-24">
        <SectionHeading eyebrow="FAQ" title="Les questions qu'on nous pose." />
        <div className="mx-auto mt-12 max-w-3xl divide-y divide-night-line rounded-2xl border border-night-line">
          {faqs.map(({ q, a, link }) => (
            <details key={q} className="group px-6 [&_summary::-webkit-details-marker]:hidden">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-5 font-brand text-base font-semibold text-ink">
                {q}
                <ChevronDown className="h-5 w-5 shrink-0 text-ink-subtle transition group-open:rotate-180" />
              </summary>
              <p className="pb-5 text-sm leading-relaxed text-ink-muted">
                {a}{" "}
                {link && (
                  <Link
                    to={link.to}
                    hash={link.hash}
                    className="font-medium text-data hover:underline"
                  >
                    {link.label}
                  </Link>
                )}
              </p>
            </details>
          ))}
        </div>
      </section>

      {/* CTA final */}
      <section className="px-6 pb-24">
        <div className="mx-auto max-w-4xl rounded-3xl border border-cta/25 bg-gradient-to-b from-cta/10 to-transparent px-8 py-14 text-center">
          <Sparkles className="mx-auto h-7 w-7 text-cta" />
          <h2 className="mt-5 font-brand text-3xl font-bold tracking-tight text-ink md:text-4xl">
            Commencez avec le fichier que vous connaissez le mieux.
          </h2>
          <p className="mx-auto mt-4 max-w-xl leading-relaxed text-ink-muted">
            Importez-le, comparez les résultats à votre lecture du terrain, puis posez vos questions
            à l'assistant.
          </p>
          <Link to="/register" className={`${ctaClass} mt-8 px-8 py-4 text-base`}>
            Créer mon espace <CtaArrow />
          </Link>
        </div>
      </section>

      <PublicFooter />
    </div>
  );
}

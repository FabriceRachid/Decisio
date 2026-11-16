import { createFileRoute, Link } from "@tanstack/react-router";
import {
  Bot,
  Database,
  Eye,
  FileClock,
  KeyRound,
  LockKeyhole,
  Mail,
  ScrollText,
  Trash2,
  UserCog,
} from "lucide-react";
import type { ReactNode } from "react";
import { CtaArrow, PublicFooter, PublicHeader, ctaClass } from "@/components/public/PublicShell";
import { LegalValue } from "@/components/LegalLayout";
import { LEGAL_PUBLISHER, SUBPROCESSORS } from "@/lib/legal";

export const Route = createFileRoute("/securite")({
  component: SecuritePage,
  head: () => ({
    meta: [
      { title: "Sécurité — DécisioBI" },
      {
        name: "description",
        content:
          "Comment DécisioBI protège vos données : accès par rôle, chiffrement, journal d'activité, transparence sur l'IA et hébergement.",
      },
    ],
  }),
});

const roles = [
  { name: "Administrateur", body: "Gère l'espace, invite les utilisateurs et attribue les rôles." },
  { name: "Analyste", body: "Importe et prépare les données, construit les tableaux de bord." },
  {
    name: "Lecteur",
    body: "Consulte les tableaux de bord et les résultats, sans modifier les données.",
  },
];

function Block({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof LockKeyhole;
  title: string;
  children: ReactNode;
}) {
  return (
    <article className="rounded-2xl border border-night-line bg-night-elevated p-7">
      <span className="grid h-11 w-11 place-items-center rounded-xl bg-emerald-400/10">
        <Icon className="h-5 w-5 text-emerald-400" />
      </span>
      <h2 className="mt-5 font-brand text-xl font-bold text-ink">{title}</h2>
      <div className="mt-3 space-y-3 text-sm leading-relaxed text-ink-muted">{children}</div>
    </article>
  );
}

function SecuritePage() {
  return (
    <div className="min-h-screen bg-night text-ink">
      <div className="bg-public-hero">
        <PublicHeader />
        <section className="mx-auto max-w-3xl px-6 pb-20 pt-12 text-center md:pt-16">
          <p className="text-sm font-semibold text-data">Sécurité</p>
          <h1 className="mt-4 font-brand text-4xl font-extrabold tracking-tight text-ink md:text-5xl">
            Ce que nous faisons pour protéger vos données.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-ink-muted">
            Des explications simples sur les accès, le chiffrement, la traçabilité et l'intelligence
            artificielle. Sans jargon, et sans promesse que nous ne pourrions pas tenir.
          </p>
        </section>
      </div>

      <section className="mx-auto max-w-6xl px-6 py-20">
        <div className="grid gap-5 md:grid-cols-2">
          <Block icon={UserCog} title="Chacun voit ce qu'il doit voir">
            <p>
              Chaque espace appartient à une entreprise. L'accès passe par une connexion
              personnelle, et chaque utilisateur reçoit un rôle qui limite ce qu'il peut faire :
            </p>
            <ul className="space-y-2">
              {roles.map((r) => (
                <li key={r.name} className="rounded-xl border border-night-line bg-night px-4 py-3">
                  <span className="font-semibold text-ink">{r.name}</span> — {r.body}
                </li>
              ))}
            </ul>
          </Block>

          <Block icon={LockKeyhole} title="Chiffrement et mots de passe">
            <p>
              Toutes les communications entre votre navigateur et DécisioBI passent par une
              connexion chiffrée (HTTPS).
            </p>
            <p>
              Les mots de passe ne sont jamais stockés en clair : ils sont hachés avant
              enregistrement. Personne, y compris notre équipe, ne peut les relire.
            </p>
          </Block>

          <Block icon={KeyRound} title="Sessions limitées dans le temps">
            <p>
              Une session de connexion expire automatiquement au bout d'une heure et se renouvelle
              tant que vous utilisez le service, dans la limite de 7 jours. Chaque renouvellement
              invalide l'ancien jeton.
            </p>
            <p>La réinitialisation d'un mot de passe passe par un lien personnel à usage unique.</p>
          </Block>

          <Block icon={ScrollText} title="Journal d'activité">
            <p>
              Les actions importantes (imports, exports, modifications, connexions) sont
              enregistrées avec leur auteur, leur date et l'adresse IP d'origine. En cas de doute,
              un administrateur peut retracer ce qui s'est passé.
            </p>
          </Block>

          <Block icon={Bot} title="Ce que voit l'intelligence artificielle">
            <p>
              L'assistant utilise un modèle d'IA fourni par{" "}
              <strong className="text-ink">Groq</strong> (États-Unis). Pour vous répondre, il reçoit
              votre question et un contexte limité : noms et types de colonnes, quelques lignes
              d'exemple et les valeurs des indicateurs de la source choisie.
            </p>
            <p>
              Votre mot de passe et votre adresse e-mail ne sont jamais transmis. Évitez toutefois
              d'importer des données sensibles qui ne sont pas utiles à l'analyse.
            </p>
            <Link
              to="/confidentialite"
              hash="ia"
              className="inline-flex items-center gap-1 font-medium text-data hover:underline"
            >
              Détail des données envoyées
            </Link>
          </Block>

          <Block icon={Trash2} title="Vous gardez le contrôle">
            <p>
              Vos fichiers restent votre propriété. Vous pouvez supprimer une source importée à tout
              moment, et chaque source a une durée de conservation configurable (90 jours par
              défaut).
            </p>
            <p>
              Pour exercer vos droits sur vos données personnelles, écrivez à{" "}
              <LegalValue value={LEGAL_PUBLISHER.privacyEmail} />.
            </p>
          </Block>
        </div>
      </section>

      <section className="border-t border-night-line bg-night-elevated/40 px-6 py-20">
        <div className="mx-auto max-w-6xl">
          <div className="flex items-center gap-3">
            <Database className="h-5 w-5 text-data" />
            <h2 className="font-brand text-2xl font-bold text-ink">Où sont traitées vos données</h2>
          </div>
          <p className="mt-3 max-w-2xl text-ink-muted">
            DécisioBI s'appuie sur des prestataires reconnus. Voici la liste complète, avec le rôle
            de chacun.
          </p>
          <div className="mt-8 overflow-x-auto rounded-2xl border border-night-line">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="bg-night-elevated text-xs uppercase tracking-wider text-ink-subtle">
                <tr>
                  <th className="px-5 py-3 font-semibold">Prestataire</th>
                  <th className="px-5 py-3 font-semibold">Rôle</th>
                  <th className="px-5 py-3 font-semibold">Localisation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-night-line">
                {SUBPROCESSORS.map((s) => (
                  <tr key={s.name}>
                    <td className="px-5 py-4 font-semibold text-ink">{s.name}</td>
                    <td className="px-5 py-4 text-ink-muted">{s.role}</td>
                    <td className="px-5 py-4 text-ink-muted">
                      <LegalValue value={s.location} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="px-6 py-20">
        <div className="mx-auto grid max-w-6xl gap-5 md:grid-cols-3">
          {[
            {
              icon: Eye,
              title: "Pas de pistage",
              body: "Ni cookie publicitaire, ni outil de mesure d'audience sur DécisioBI.",
            },
            {
              icon: FileClock,
              title: "Pas de revente",
              body: "Vos données ne sont ni vendues, ni utilisées à des fins publicitaires.",
            },
            {
              icon: Mail,
              title: "Signaler un problème",
              body: (
                <>
                  Une faille ou un comportement suspect ? Écrivez à{" "}
                  <LegalValue value={LEGAL_PUBLISHER.contactEmail} />.
                </>
              ),
            },
          ].map(({ icon: Icon, title, body }) => (
            <div key={title} className="rounded-2xl border border-night-line p-6">
              <Icon className="h-5 w-5 text-data" />
              <h3 className="mt-4 font-brand text-base font-bold text-ink">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-muted">{body}</p>
            </div>
          ))}
        </div>

        <div className="mx-auto mt-16 max-w-3xl text-center">
          <h2 className="font-brand text-3xl font-bold tracking-tight text-ink">
            Une question avant de vous lancer ?
          </h2>
          <p className="mt-4 text-ink-muted">
            Consultez notre{" "}
            <Link to="/confidentialite" className="text-data hover:underline">
              politique de confidentialité
            </Link>{" "}
            et nos{" "}
            <Link to="/cgu" className="text-data hover:underline">
              conditions d'utilisation
            </Link>
            , ou créez votre espace pour essayer avec un fichier de test.
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

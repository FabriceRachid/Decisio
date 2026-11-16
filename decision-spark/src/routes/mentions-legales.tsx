import { createFileRoute, Link } from "@tanstack/react-router";
import { LegalLayout, LegalList, LegalSection, LegalValue } from "@/components/LegalLayout";
import { LEGAL_PUBLISHER, SUBPROCESSORS } from "@/lib/legal";

export const Route = createFileRoute("/mentions-legales")({
  component: MentionsLegalesPage,
  head: () => ({ meta: [{ title: "Mentions légales — DécisioBI" }] }),
});

const sections = [
  { id: "editeur", title: "Éditeur" },
  { id: "publication", title: "Directeur de la publication" },
  { id: "hebergement", title: "Hébergement" },
  { id: "propriete", title: "Propriété intellectuelle" },
  { id: "donnees", title: "Données personnelles" },
  { id: "contact", title: "Contact" },
];

function MentionsLegalesPage() {
  const p = LEGAL_PUBLISHER;
  const hosts = SUBPROCESSORS.filter((s) => s.isHost);

  return (
    <LegalLayout
      eyebrow="Informations légales"
      title="Mentions légales"
      intro="Qui édite DécisioBI, où le service est hébergé et comment nous contacter."
      sections={sections}
    >
      <LegalSection id="editeur" title="Éditeur">
        <p>
          Le service {p.productName}, accessible à l'adresse <LegalValue value={p.website} />, est
          édité par :
        </p>
        <LegalList
          items={[
            <>
              <strong>Raison sociale :</strong> <LegalValue value={p.companyName} />
            </>,
            <>
              <strong>Forme juridique :</strong> <LegalValue value={p.legalForm} />
            </>,
            <>
              <strong>Immatriculation :</strong> <LegalValue value={p.registration} />
            </>,
            <>
              <strong>Siège social :</strong> <LegalValue value={p.address} />
            </>,
            <>
              <strong>E-mail :</strong> <LegalValue value={p.contactEmail} />
            </>,
          ]}
        />
      </LegalSection>

      <LegalSection id="publication" title="Directeur de la publication">
        <p>
          <LegalValue value={p.publicationDirector} />
        </p>
      </LegalSection>

      <LegalSection id="hebergement" title="Hébergement">
        <p>Le service s'appuie sur les hébergeurs suivants :</p>
        <div className="grid gap-3 sm:grid-cols-3">
          {hosts.map((h) => (
            <div key={h.name} className="rounded-xl border border-border bg-card p-4 shadow-card">
              <p className="font-semibold text-foreground">{h.name}</p>
              <p className="mt-1 text-sm text-muted-foreground">{h.role}</p>
              <p className="mt-3 text-xs text-muted-foreground">
                Localisation : <LegalValue value={h.location} />
              </p>
              <a
                href={h.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-block text-xs text-primary hover:underline"
              >
                {h.url.replace("https://", "")}
              </a>
            </div>
          ))}
        </div>
        <p>
          La liste complète des prestataires techniques, y compris le fournisseur d'intelligence
          artificielle et le service d'envoi d'e-mails, figure dans la{" "}
          <Link
            to="/confidentialite"
            hash="sous-traitants"
            className="text-primary hover:underline"
          >
            politique de confidentialité
          </Link>
          .
        </p>
      </LegalSection>

      <LegalSection id="propriete" title="Propriété intellectuelle">
        <p>
          La marque {p.productName}, son logo, l'interface, les textes et le code du service sont
          protégés par le droit de la propriété intellectuelle. Toute reproduction ou réutilisation
          sans autorisation écrite de l'éditeur est interdite.
        </p>
        <p>
          Les fichiers et données que vous importez restent votre propriété. Les conditions de leur
          utilisation sont décrites dans les{" "}
          <Link to="/cgu" className="text-primary hover:underline">
            conditions d'utilisation
          </Link>
          .
        </p>
      </LegalSection>

      <LegalSection id="donnees" title="Données personnelles">
        <p>
          Les traitements de données personnelles réalisés dans le cadre du service, leurs
          finalités, les destinataires et vos droits sont détaillés dans la{" "}
          <Link to="/confidentialite" className="text-primary hover:underline">
            politique de confidentialité
          </Link>
          .
        </p>
      </LegalSection>

      <LegalSection id="contact" title="Contact">
        <p>
          Pour toute question sur le service : <LegalValue value={p.contactEmail} />.
          <br />
          Pour toute question sur vos données personnelles : <LegalValue value={p.privacyEmail} />.
        </p>
      </LegalSection>
    </LegalLayout>
  );
}

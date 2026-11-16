import { createFileRoute, Link } from "@tanstack/react-router";
import { LegalLayout, LegalList, LegalSection, LegalValue } from "@/components/LegalLayout";
import { LEGAL_PUBLISHER } from "@/lib/legal";

export const Route = createFileRoute("/cgu")({
  component: CguPage,
  head: () => ({ meta: [{ title: "Conditions générales d'utilisation — DécisioBI" }] }),
});

const sections = [
  { id: "objet", title: "Objet" },
  { id: "acces", title: "Accès et compte" },
  { id: "roles", title: "Espace entreprise et rôles" },
  { id: "donnees", title: "Vos données" },
  { id: "ia", title: "Assistant IA et résultats" },
  { id: "usage", title: "Usages interdits" },
  { id: "disponibilite", title: "Disponibilité" },
  { id: "responsabilite", title: "Responsabilité" },
  { id: "resiliation", title: "Suspension et résiliation" },
  { id: "evolution", title: "Évolution des conditions" },
  { id: "droit", title: "Droit applicable" },
];

function CguPage() {
  const p = LEGAL_PUBLISHER;

  return (
    <LegalLayout
      eyebrow="Règles d'utilisation"
      title="Conditions générales d'utilisation"
      intro="Les règles qui encadrent l'utilisation de DécisioBI par votre entreprise et vos collaborateurs."
      sections={sections}
    >
      <LegalSection id="objet" title="Objet">
        <p>
          Les présentes conditions encadrent l'accès et l'utilisation du service {p.productName},
          édité par <LegalValue value={p.companyName} /> (voir les{" "}
          <Link to="/mentions-legales" className="text-primary hover:underline">
            mentions légales
          </Link>
          ). {p.productName} permet d'importer des fichiers Excel et CSV, de nettoyer et structurer
          leurs données, de suivre des indicateurs dans des tableaux de bord et d'interroger un
          assistant IA sur ces données.
        </p>
        <p>
          La création d'un espace vaut acceptation des présentes conditions et de la{" "}
          <Link to="/confidentialite" className="text-primary hover:underline">
            politique de confidentialité
          </Link>
          .
        </p>
      </LegalSection>

      <LegalSection id="acces" title="Accès et compte">
        <LegalList
          items={[
            "Le service est destiné aux professionnels. La personne qui crée un espace déclare être habilitée à engager l'entreprise concernée.",
            "Les informations fournies à l'inscription doivent être exactes et tenues à jour.",
            "Vos identifiants sont personnels et confidentiels. Toute action réalisée avec votre compte est réputée effectuée par vous.",
            "Signalez sans délai toute utilisation non autorisée de votre compte.",
          ]}
        />
      </LegalSection>

      <LegalSection id="roles" title="Espace entreprise et rôles">
        <p>
          Le premier compte créé devient administrateur de l'espace. L'administrateur invite les
          autres utilisateurs, leur attribue un rôle et définit ainsi les fonctions et données
          auxquelles ils ont accès. L'entreprise est responsable des accès qu'elle accorde et de
          leur retrait lorsqu'un collaborateur quitte l'organisation.
        </p>
      </LegalSection>

      <LegalSection id="donnees" title="Vos données">
        <LegalList
          items={[
            <>
              Les fichiers et données que vous importez restent votre propriété. Vous nous accordez
              uniquement le droit de les traiter pour fournir le service.
            </>,
            <>
              Vous garantissez disposer des droits et autorisations nécessaires sur ces données,
              notamment lorsqu'elles contiennent des données personnelles de tiers (clients,
              salariés, fournisseurs).
            </>,
            <>
              Certaines données sont transmises à des prestataires techniques, dont le fournisseur
              du modèle d'IA, dans les conditions décrites dans la{" "}
              <Link to="/confidentialite" hash="ia" className="text-primary hover:underline">
                politique de confidentialité
              </Link>
              .
            </>,
            <>
              Vous pouvez supprimer à tout moment une source importée depuis votre espace. Il vous
              appartient de conserver une copie de vos fichiers d'origine.
            </>,
          ]}
        />
      </LegalSection>

      <LegalSection id="ia" title="Assistant IA et résultats">
        <p>
          Les indicateurs, analyses, détections d'anomalies et réponses de l'assistant sont produits
          automatiquement à partir des données importées. Ils dépendent de la qualité et de la
          structure de ces données, et les réponses de l'IA peuvent être incomplètes ou erronées.
        </p>
        <p>
          Ces résultats constituent une aide à la décision et ne remplacent ni l'avis d'un
          professionnel (expert-comptable, juriste, conseiller financier), ni votre propre
          vérification. Toute décision prise sur la base de ces résultats relève de votre seule
          responsabilité.
        </p>
      </LegalSection>

      <LegalSection id="usage" title="Usages interdits">
        <p>Il est interdit notamment :</p>
        <LegalList
          items={[
            "d'importer des contenus illicites ou des données que vous n'êtes pas autorisé à traiter ;",
            "de tenter d'accéder aux espaces ou aux données d'autres organisations ;",
            "de perturber le service (surcharge volontaire, injection de code, contournement des contrôles d'accès) ;",
            "d'extraire ou de copier le service, son code ou son interface de manière automatisée ;",
            "d'utiliser l'assistant IA pour produire des contenus illicites ou trompeurs.",
          ]}
        />
      </LegalSection>

      <LegalSection id="disponibilite" title="Disponibilité">
        <p>
          Nous faisons nos meilleurs efforts pour que le service soit accessible en continu, sans
          garantie de disponibilité permanente. Des interruptions peuvent survenir pour maintenance,
          mise à jour ou en cas d'incident chez nos prestataires. Les fonctionnalités peuvent
          évoluer.
        </p>
      </LegalSection>

      <LegalSection id="responsabilite" title="Responsabilité">
        <p>
          L'éditeur est tenu d'une obligation de moyens. Sa responsabilité ne peut être engagée pour
          les dommages indirects (perte de chiffre d'affaires, de données ou d'opportunité), ni pour
          les conséquences de décisions prises sur la base des résultats du service, ni en cas
          d'utilisation non conforme aux présentes conditions.
        </p>
      </LegalSection>

      <LegalSection id="resiliation" title="Suspension et résiliation">
        <p>
          Vous pouvez cesser d'utiliser le service et demander la fermeture de votre espace à tout
          moment en écrivant à <LegalValue value={p.contactEmail} />. L'éditeur peut suspendre ou
          fermer un compte en cas de manquement grave aux présentes conditions, après en avoir
          informé l'utilisateur sauf urgence. À la fermeture de l'espace, les données associées sont
          supprimées selon les durées indiquées dans la politique de confidentialité.
        </p>
      </LegalSection>

      <LegalSection id="evolution" title="Évolution des conditions">
        <p>
          Ces conditions peuvent être modifiées. Les administrateurs des espaces sont informés des
          modifications importantes. La poursuite de l'utilisation du service après leur entrée en
          vigueur vaut acceptation.
        </p>
      </LegalSection>

      <LegalSection id="droit" title="Droit applicable">
        <p>
          <LegalValue value={p.governingLaw} />. En cas de litige, les parties recherchent d'abord
          une solution amiable. Contact : <LegalValue value={p.contactEmail} />.
        </p>
      </LegalSection>
    </LegalLayout>
  );
}

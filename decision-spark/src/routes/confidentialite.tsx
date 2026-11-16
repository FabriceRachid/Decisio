import { createFileRoute, Link } from "@tanstack/react-router";
import { Bot } from "lucide-react";
import { LegalLayout, LegalList, LegalSection, LegalValue } from "@/components/LegalLayout";
import { LEGAL_PUBLISHER, SUBPROCESSORS } from "@/lib/legal";

export const Route = createFileRoute("/confidentialite")({
  component: ConfidentialitePage,
  head: () => ({
    meta: [
      { title: "Politique de confidentialité — DécisioBI" },
      {
        name: "description",
        content:
          "Données collectées par DécisioBI, finalités, prestataires (dont le fournisseur d'IA), durées de conservation et droits des utilisateurs.",
      },
    ],
  }),
});

const sections = [
  { id: "responsable", title: "Responsable du traitement" },
  { id: "donnees", title: "Données traitées" },
  { id: "finalites", title: "Finalités et bases légales" },
  { id: "ia", title: "Assistant IA et fournisseur de modèle" },
  { id: "sous-traitants", title: "Destinataires et prestataires" },
  { id: "transferts", title: "Transferts internationaux" },
  { id: "conservation", title: "Durées de conservation" },
  { id: "navigateur", title: "Stockage dans le navigateur" },
  { id: "securite", title: "Sécurité" },
  { id: "droits", title: "Vos droits" },
  { id: "modifications", title: "Modifications" },
];

function ConfidentialitePage() {
  const p = LEGAL_PUBLISHER;

  return (
    <LegalLayout
      eyebrow="Vos données"
      title="Politique de confidentialité"
      intro="Ce que DécisioBI collecte, pourquoi, avec qui ces données sont partagées — y compris le fournisseur du modèle d'intelligence artificielle — et comment exercer vos droits."
      sections={sections}
    >
      <LegalSection id="responsable" title="Responsable du traitement">
        <p>
          Pour les données de compte et d'utilisation du service, le responsable du traitement est{" "}
          <LegalValue value={p.companyName} />, <LegalValue value={p.address} />.
        </p>
        <p>
          Pour les données contenues dans les fichiers que vous importez (par exemple des listes de
          clients ou de salariés), votre organisation reste responsable du traitement. DécisioBI
          agit alors comme sous-traitant : nous traitons ces données uniquement pour fournir le
          service, selon vos instructions.
        </p>
        <p>
          Contact pour toute question relative aux données personnelles :{" "}
          <LegalValue value={p.privacyEmail} />.
        </p>
      </LegalSection>

      <LegalSection id="donnees" title="Données traitées">
        <LegalList
          items={[
            <>
              <strong>Compte et organisation :</strong> nom d'utilisateur, nom complet, adresse
              e-mail, mot de passe (stocké sous forme hachée, jamais en clair), rôle ; nom, secteur,
              taille et pays de l'entreprise.
            </>,
            <>
              <strong>Profil (facultatif) :</strong> téléphone, service, fuseau horaire, langue,
              préférences d'affichage et de notification, paramètres de double authentification.
            </>,
            <>
              <strong>Données importées :</strong> fichiers Excel et CSV, leur contenu, ainsi que
              les résultats produits par le service (données nettoyées, indicateurs, anomalies,
              conflits, tableaux de bord, rapports PDF).
            </>,
            <>
              <strong>Assistant IA :</strong> questions posées, historique des conversations et
              réponses générées.
            </>,
            <>
              <strong>Journal d'activité et sécurité :</strong> actions effectuées dans l'espace
              (import, export, modification…), date et heure, adresse IP, type de navigateur,
              dernière adresse IP de connexion.
            </>,
            <>
              <strong>Destinataires de rapports :</strong> adresses e-mail que vous saisissez pour
              l'envoi programmé de rapports.
            </>,
          ]}
        />
      </LegalSection>

      <LegalSection id="finalites" title="Finalités et bases légales">
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted text-xs uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-semibold">Finalité</th>
                <th className="px-4 py-3 font-semibold">Base légale</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {[
                ["Créer et gérer votre compte et votre espace entreprise", "Exécution du contrat"],
                [
                  "Importer, nettoyer et analyser vos fichiers ; calculer les indicateurs",
                  "Exécution du contrat",
                ],
                ["Répondre à vos questions via l'assistant IA", "Exécution du contrat"],
                [
                  "Envoyer les e-mails de service (réinitialisation, invitations, rapports)",
                  "Exécution du contrat",
                ],
                [
                  "Journaliser les actions et sécuriser l'accès (détection d'abus, audit)",
                  "Intérêt légitime : sécurité du service",
                ],
                [
                  "Répondre aux demandes des autorités lorsque la loi l'impose",
                  "Obligation légale",
                ],
              ].map(([purpose, basis]) => (
                <tr key={purpose}>
                  <td className="px-4 py-3 align-top">{purpose}</td>
                  <td className="px-4 py-3 align-top text-muted-foreground">{basis}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>
          Nous n'utilisons pas vos données à des fins publicitaires, nous ne les vendons pas et nous
          ne réalisons pas de profilage commercial.
        </p>
      </LegalSection>

      <LegalSection id="ia" title="Assistant IA et fournisseur de modèle">
        <div className="flex gap-3 rounded-xl border border-primary/20 bg-primary/5 p-4">
          <Bot className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
          <p className="text-sm">
            Les fonctions d'IA de DécisioBI reposent sur un modèle de langage hébergé par{" "}
            <strong>Groq, Inc.</strong> (États-Unis). Les traitements ci-dessous impliquent donc
            l'envoi de données à ce prestataire.
          </p>
        </div>
        <p>Données envoyées au fournisseur de modèle :</p>
        <LegalList
          items={[
            <>
              <strong>Assistant (chatbot) :</strong> votre question, des extraits des derniers
              messages de la conversation, et le contexte de la source sélectionnée — noms et types
              de colonnes, quelques lignes d'exemple, valeurs et évolutions des indicateurs,
              alertes, anomalies et conflits récents.
            </>,
            <>
              <strong>Interprétation des indicateurs :</strong> valeurs, ventilations et historiques
              des KPI concernés.
            </>,
            <>
              <strong>Détection de structure des fichiers :</strong> dimensions du fichier, un
              échantillon de cellules et la position des cellules fusionnées, afin de reconstruire
              les tableaux mal formatés.
            </>,
          ]}
        />
        <p>
          Ne sont pas inclus dans ces envois : votre mot de passe, votre adresse e-mail et vos
          informations de compte. En revanche, si les lignes d'exemple de vos fichiers contiennent
          des données personnelles (noms de clients, contacts…), celles-ci peuvent être transmises.
        </p>
        <p>
          Les conditions dans lesquelles Groq traite et conserve ces données sont fixées par ses
          propres politiques, consultables sur{" "}
          <a
            href="https://groq.com/privacy-policy/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            groq.com
          </a>
          . Les réponses de l'assistant sont générées automatiquement et peuvent contenir des
          erreurs : vérifiez-les avant toute décision.
        </p>
        <p>
          <strong>Recommandation :</strong> évitez d'importer des données sensibles (santé, données
          bancaires, pièces d'identité, opinions…) ou retirez les colonnes nominatives lorsqu'elles
          ne sont pas nécessaires à l'analyse.
        </p>
      </LegalSection>

      <LegalSection id="sous-traitants" title="Destinataires et prestataires">
        <p>
          Vos données sont accessibles aux membres de votre espace selon leur rôle, aux personnes
          habilitées de l'éditeur pour le support et la maintenance, et aux prestataires techniques
          suivants :
        </p>
        <div className="space-y-3">
          {SUBPROCESSORS.map((s) => (
            <div key={s.name} className="rounded-xl border border-border bg-card p-4 shadow-card">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="font-semibold text-foreground">{s.name}</p>
                <span className="text-xs text-muted-foreground">
                  <LegalValue value={s.location} />
                </span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">{s.role}</p>
              <p className="mt-2 text-sm">
                <span className="font-medium text-foreground">Données concernées : </span>
                {s.data}
              </p>
            </div>
          ))}
        </div>
      </LegalSection>

      <LegalSection id="transferts" title="Transferts internationaux">
        <p>
          Certains prestataires, notamment Groq et Vercel, sont établis aux États-Unis. Vos données
          peuvent donc être traitées hors de votre pays. Ces transferts sont encadrés par les
          garanties contractuelles proposées par ces prestataires (par exemple des clauses
          contractuelles types). Vous pouvez obtenir des informations sur ces garanties en nous
          écrivant à <LegalValue value={p.privacyEmail} />.
        </p>
      </LegalSection>

      <LegalSection id="conservation" title="Durées de conservation">
        <LegalList
          items={[
            <>
              <strong>Compte :</strong> pendant toute la durée d'utilisation du service, puis
              suppression dans un délai raisonnable après la fermeture du compte.
            </>,
            <>
              <strong>Sources importées :</strong> selon la durée de conservation définie pour
              chaque source (90 jours par défaut, modifiable lors de l'import). Vous pouvez
              supprimer une source à tout moment depuis votre espace.
            </>,
            <>
              <strong>Conversations avec l'assistant :</strong> tant qu'elles ne sont pas supprimées
              ou que le compte est actif.
            </>,
            <>
              <strong>Journaux d'activité :</strong> le temps nécessaire à la sécurité et à l'audit
              du service.
            </>,
          ]}
        />
      </LegalSection>

      <LegalSection id="navigateur" title="Stockage dans le navigateur">
        <p>
          DécisioBI n'utilise ni cookie publicitaire, ni outil de mesure d'audience. Le stockage
          local du navigateur sert uniquement au fonctionnement du service :
        </p>
        <LegalList
          items={[
            "jetons de session permettant de rester connecté (supprimés à la déconnexion) ;",
            "préférences d'affichage, comme la dernière source sélectionnée dans le tableau de bord.",
          ]}
        />
      </LegalSection>

      <LegalSection id="securite" title="Sécurité">
        <p>
          Les échanges avec le service sont chiffrés (HTTPS). Les mots de passe sont stockés sous
          forme hachée. L'accès à un espace nécessite une authentification, les sessions expirent
          automatiquement et les fonctions disponibles dépendent du rôle attribué à chaque
          utilisateur. Les actions sensibles sont enregistrées dans un journal d'activité.
        </p>
        <p>
          Aucun système n'est infaillible. En cas de violation de données susceptible de vous
          affecter, nous vous en informerons dans les conditions prévues par la réglementation.
        </p>
      </LegalSection>

      <LegalSection id="droits" title="Vos droits">
        <p>
          Conformément à la réglementation applicable en matière de protection des données
          personnelles, vous disposez des droits suivants :
        </p>
        <LegalList
          items={[
            "accès à vos données et obtention d'une copie ;",
            "rectification des données inexactes ;",
            "effacement de vos données ;",
            "limitation du traitement et opposition aux traitements fondés sur l'intérêt légitime ;",
            "portabilité des données que vous nous avez fournies.",
          ]}
        />
        <p>
          Pour exercer ces droits, écrivez à <LegalValue value={p.privacyEmail} />. Nous répondons
          dans un délai d'un mois. Si les données concernées figurent dans un fichier importé par
          une organisation, nous transmettons la demande à cette organisation.
        </p>
        <p>
          Vous pouvez également introduire une réclamation auprès de l'autorité de protection des
          données compétente : <LegalValue value={p.supervisoryAuthority} />.
        </p>
      </LegalSection>

      <LegalSection id="modifications" title="Modifications">
        <p>
          Cette politique peut évoluer, notamment en cas de changement de prestataire. La date de
          dernière mise à jour figure en haut de page. En cas de modification importante, les
          administrateurs des espaces seront informés par e-mail. Voir aussi les{" "}
          <Link to="/cgu" className="text-primary hover:underline">
            conditions d'utilisation
          </Link>{" "}
          et les{" "}
          <Link to="/mentions-legales" className="text-primary hover:underline">
            mentions légales
          </Link>
          .
        </p>
      </LegalSection>
    </LegalLayout>
  );
}

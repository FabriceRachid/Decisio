/**
 * Informations légales centralisées pour les pages Mentions légales,
 * Politique de confidentialité et CGU.
 *
 * Les valeurs entre crochets sont des champs à compléter avant mise en
 * production. Tant qu'il en reste, les pages légales affichent un bandeau
 * « document en cours de finalisation ».
 */

export const LEGAL_PLACEHOLDER_PATTERN = /^\[.*\]$/;

export const isLegalPlaceholder = (value: string) => LEGAL_PLACEHOLDER_PATTERN.test(value);

export const LEGAL_LAST_UPDATED = "[Date de mise à jour à compléter]";

export const LEGAL_PUBLISHER = {
  productName: "DécisioBI",
  companyName: "[Raison sociale de l'éditeur à compléter]",
  legalForm: "[Forme juridique et capital social à compléter]",
  registration: "[N° d'immatriculation (RCCM, IFU, SIREN…) à compléter]",
  address: "[Adresse du siège social à compléter]",
  publicationDirector: "[Nom du directeur de la publication à compléter]",
  contactEmail: "[Adresse e-mail de contact à compléter]",
  privacyEmail: "[Adresse e-mail dédiée aux données personnelles à compléter]",
  website: "[URL du site à compléter]",
  /** Droit applicable aux CGU et juridiction compétente. */
  governingLaw: "[Droit applicable et tribunaux compétents à compléter]",
  /** Autorité de protection des données compétente pour l'éditeur. */
  supervisoryAuthority: "[Autorité de contrôle compétente à compléter]",
};

export type Subprocessor = {
  name: string;
  role: string;
  location: string;
  data: string;
  url: string;
  /** Hébergeur à citer dans les mentions légales. */
  isHost?: boolean;
};

/**
 * Prestataires techniques qui traitent des données pour le compte de
 * DécisioBI. À tenir à jour à chaque changement d'infrastructure.
 */
export const SUBPROCESSORS: Subprocessor[] = [
  {
    name: "Vercel Inc.",
    role: "Hébergement de l'interface web (frontend)",
    location: "États-Unis (réseau de diffusion mondial)",
    data: "Journaux techniques de connexion (adresse IP, navigateur, pages demandées).",
    url: "https://vercel.com",
    isHost: true,
  },
  {
    name: "Render Services, Inc.",
    role: "Hébergement de l'API, des traitements en arrière-plan et des fichiers importés",
    location: "[Région d'hébergement Render à compléter]",
    data: "Ensemble des données du service : comptes, fichiers importés, résultats d'analyse, journaux d'activité.",
    url: "https://render.com",
    isHost: true,
  },
  {
    name: "Neon (PostgreSQL managé)",
    role: "Base de données",
    location: "[Région d'hébergement Neon à compléter]",
    data: "Comptes, organisations, données nettoyées, indicateurs, historiques de l'assistant, journaux d'activité.",
    url: "https://neon.tech",
    isHost: true,
  },
  {
    name: "Groq, Inc.",
    role: "Fournisseur du modèle d'IA (assistant, interprétation des KPI, détection de structure des fichiers)",
    location: "États-Unis",
    data: "Questions posées, extraits de la conversation, contexte de la source sélectionnée (noms et types de colonnes, quelques lignes d'exemple, valeurs d'indicateurs, alertes et anomalies), échantillon structurel des fichiers à reconstruire.",
    url: "https://groq.com",
  },
  {
    name: "Brevo (Sendinblue SAS)",
    role: "Envoi des e-mails transactionnels",
    location: "France / Union européenne",
    data: "Adresse e-mail et nom des destinataires, contenu des e-mails (réinitialisation de mot de passe, invitations, notifications) et rapports PDF joints.",
    url: "https://www.brevo.com",
  },
];

export const LEGAL_LINKS = [
  { to: "/mentions-legales", label: "Mentions légales" },
  { to: "/confidentialite", label: "Politique de confidentialité" },
  { to: "/cgu", label: "Conditions d'utilisation" },
] as const;

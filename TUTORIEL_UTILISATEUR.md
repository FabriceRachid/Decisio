# Guide Complet DecisioBI — Pilotez. Decidez.

---

## Table des matieres

1. [Qu'est-ce que DecisioBI ?](#1-quest-ce-que-decisobi)
2. [Creer votre espace](#2-creer-votre-espace)
3. [Se connecter](#3-se-connecter)
4. [Le Dashboard](#4-le-dashboard)
5. [Importer des donnees](#5-importer-des-donnees)
6. [Lier les feuilles entre elles](#6-lier-les-feuilles-entre-elles)
7. [Nettoyer les donnees](#7-nettoyer-les-donnees)
8. [Valider le resultat](#8-valider-le-resultat)
9. [Detecter et resoudre les conflits](#9-detecter-et-resoudre-les-conflits)
10. [Detecter les anomalies](#10-detecter-les-anomalies)
11. [Generer des rapports PDF](#11-generer-des-rapports-pdf)
12. [Utiliser l'assistant IA](#12-utiliser-lassistant-ia)
13. [Gerer les utilisateurs](#13-gerer-les-utilisateurs)
14. [Parametrer son profil](#14-parametrer-son-profil)
15. [Creer des alertes](#15-creer-des-alertes)
16. [Apercu du parcours complet](#16-apercu-du-parcours-complet)

---

## 1. Qu'est-ce que DecisioBI ?

DecisioBI est une plateforme de **prise de decision basee sur les donnees**. Elle fait trois choses principales :

- **Importe et nettoie** vos fichiers Excel, CSV ou JSON automatiquement
- **Analyse** vos donnees avec des KPIs, des graphiques et de l'intelligence artificielle
- **Alerte** quand quelque chose d'inhabituel se produit dans vos donnees

**Ce qu'on vous promet :**
- Vous chargez un fichier → DecisioBI le comprend, le nettoie, et vous dit ce qu'il y a dedans
- Pas besoin d'etre data analyste pour comprendre vos propres donnees

---

## 2. Creer votre espace

1. Allez sur la page d'accueil de DecisioBI
2. Cliquez sur **"Creer un espace"** ou **"Creer un espace entreprise"**
3. Remplissez le formulaire en 3 etapes :

**Etape 1 — Entreprise :**
- Nom de l'entreprise
- Secteur d'activite (Commerce, Industrie, Services, etc.)
- Taille de l'entreprise
- Pays

**Etape 2 — Administrateur :**
- Nom d'utilisateur
- Nom complet
- Adresse email professionnelle
- Mot de passe (8 caracteres minimum)

**Etape 3 — Validation :**
- Verifiez les informations
- Acceptez les conditions d'utilisation
- Cliquez sur **"Creer mon espace"**

> **A savoir :** Le premier compte cree devient automatiquement **Administrateur**. C'est lui qui pourra inviter les autres membres de l'equipe.

---

## 3. Se connecter

1. Allez sur la page de connexion
2. Saisissez votre **nom d'utilisateur** et votre **mot de passe**
3. Cochez **"Rester connecte"** si vous ne voulez pas vous reconnecter a chaque fois
4. Cliquez sur **"Se connecter"**

> **Mot de passe oublie ?** Cliquez sur "Mot de passe oublie ?", saisissez votre email, et suivez le lien recu par email pour creer un nouveau mot de passe.

---

## 4. Le Dashboard

Le Dashboard est votre **tableau de bord principal**. Il se genere automatiquement quand vous importez des donnees.

### Ce que vous voyez

- **Un message de bienvenue** personnalise avec votre nom
- **Des cartes KPI** : des valeurs numeriques importantes (chiffre d'affaires, nombre de clients, etc.)
- **Des graphiques** : barres, lignes, donuts, treemaps, cartes geographiques
- **Des filtres** pour explorer les donnees

### Ce que vous pouvez faire

- **Selectionner une source** dans le menu deroulant en haut pour voir les KPIs d'un fichier specifique
- **Cliquer sur un KPI** pour voir le detail
- **Changer le type de graphique** en cliquant sur l'icone de parametre d'un widget
- **Ajouter un KPI** via le panneau d'analyse rapide (choisir une mesure et une dimension)
- **Exporter en PDF** en cliquant sur le bouton d'export en haut a droite

### Le bouton "Analyse IA"

Chaque widget a un bouton **"Analyse IA"**. En cliquant dessus, vous envoyez le contenu du widget a l'assistant IA qui vous explique ce qu'il signifie en francais.

---

## 5. Importer des donnees

C'est le point de depart. Cliquez sur **"Importer donnees"** dans le menu a gauche.

### Etape 1 — Selection

- **Choisissez un fichier** : Glissez-deposez ou cliquez pour selectionner (.xlsx, .xls, .csv, .json)
- **Voir l'historique** : Vos imports precedents sont affiches avec leur etat (Termine, En cours, Echoue)
- **Reprendre un import** : Cliquez sur un import existant pour reprendre la ou vous en etes

### Etape 2 — Apercu

- **Voyez vos donnees** : Les premieres lignes du fichier s'affichent
- **Verifiez les colonnes** : Noms, types detects, nombre de lignes
- **Pour les fichiers multi-feuilles** : Naviguez entre les onglets
- Cliquez sur **"Lancer l'import reel"** pour passer a l'etape suivante

> **Qui peut importer ?** Seuls les **Admins** et les **Analystes** peuvent importer. Les **Lecteurs** voient la page en lecture seule.

### Ce qui se passe apres

Le systeme enregistre vos donnees et prepare l'etape suivante. Votre fichier est pret a etre nettoye.

---

## 6. Lier les feuilles entre elles

**Quand ?** Uniquement pour les fichiers Excel qui contiennent **plusieurs onglets** (feuilles).

**Pourquoi ?** Si vous avez un fichier avec un onglet "Commandes" et un onglet "Clients", vous devez indiquer quelles colonnes partagent le meme identifiant pour pouvoir croiser les donnees.

### Comment faire

1. Le systeme **detecte automatiquement** les liens potentiels entre vos feuilles
2. Vous voyez une liste de **suggestions** avec un score de confiance
3. **Acceptez** une suggestion ou **creez un lien manuellement** :
   - Choisissez la feuille source et la colonne
   - Choisissez la feuille cible et la colonne correspondante
4. Cliquez sur **"Apercu des donnees croisees"** pour voir le resultat

### Types de jointure

| Type | Signification |
|------|---------------|
| Plusieurs → Un | Plusieurs lignes d'une feuille pointent vers une seule ligne de l'autre (cle etrangere vers cle primaire) |
| Un → Un | Correspondance exacte 1 pour 1 |
| Plusieurs ↔ Plusieurs | Plusieurs lignes d'un cote correspondent a plusieurs lignes de l'autre |

> **Sans lien ?** Pas de probleme. Passez directement a l'etape suivante.

---

## 7. Nettoyer les donnees

C'est l'etape la plus intelligente. DecisioBI **analyse automatiquement** la structure de votre fichier et propose des regles de nettoyage.

### Ce que le systeme detecte

- **Lignes vides** : Lignes entierement vides ou remplies d'espaces
- **Colonnes vides** : Colonnes avec plus de 60% de valeurs manquantes
- **Doublons** : Lignes identiques
- **Headers cassés** : En-tetes mal positionnes
- **Cellules fusionnees** : Excel avec des cellules mergees
- **Crosstab / Tableau croise** : Formats larges a convertir en format long (unpivot)
- **Types melanges** : Une colonne contenant du texte et des nombres

### Ce que vous voyez

1. **Colonnes quasi-vides** : Une liste de colonnes avec peu de donnees. Vous choisissez : garder ou supprimer.
2. **Colonnes non mappees** : Des colonnes sans usage evident. Vous choisissez.
3. **Lignes eparses** : Des lignes avec trop de valeurs manquantes.
4. **Regle nettoyage** : La liste des transformations qui seront appliquees.

### Le bouton "Appliquer le nettoyage"

Une fois vos choix faits, cliquez sur **"Appliquer le nettoyage"**. Le systeme applique toutes les regles en une fois.

> **Confiance :** Chaque detection a un score de confiance (ex: 85%). Plus c'est eleve, plus le systeme est sur de sa detection.

---

## 8. Valider le resultat

Avant de passer a l'analyse, vous **verifiez** que le nettoyage est correct.

### Ce que vous voyez

- **Avant nettoyage** : Combien de lignes, combien de colonnes
- **Apres nettoyage** : Le nouveau nombre de lignes et colonnes
- **Lignes affectees** : Combien de lignes ont ete modifiees
- **Pourcentage de validation** : Score de qualite du resultat

### Comment valider

1. Verifiez les donnees cote a cote
2. Ajoutez des **notes de validation** si besoin
3. Cliquez sur **"Valider"**

> **Important :** Tant que vous n'avez pas valide, le fichier ne passe pas aux modules suivants (Conflits, Dashboard). C'est une securite.

---

## 9. Detecter et resoudre les conflits

Apres validation, le systeme **detecte automatiquement** les incoherences dans vos donnees. C'est le module **Conflits**.

### Qu'est-ce qu'un conflit ?

Selon la **norme ISO 8000** (norme internationale pour la qualite des donnees), un conflit est une incoherence qui compromet l'integrite des donnees. DecisioBI en detecte 4 types :

| Type | Qu'est-ce que c'est | Dimension ISO 8000 |
|------|---------------------|---------------------|
| Doublons | Enregistrements identiques (detectes par hash MD5) | Unicite |
| Valeurs manquantes | Champs absents dans plus de 20% des lignes | Completude |
| Types melanges | Une colonne contenant texte et nombres | Coherence |
| Formats incoherents | Emails, telephones, dates mal formates | Validite |

### Comment resoudre un conflit

**Etape 1 — Prendre en charge :**
1. Cliquez sur un conflit pour le voir en detail
2. Lisez la description et les colonnes concernees
3. Cliquez sur **"Demarrer le traitement"**

**Etape 2 — Resoudre :**
- **Recommandation du systeme** : Le systeme propose une methode de resolution
- **Decision manuelle** : Vous choisissez vous-meme la valeur a retenir
- **Resoudre avec la recommandation** : Appliquez directement la suggestion

> **Guidance IA :** Cliquez sur "Voir la guidance" pour obtenir des etapes detaillees et une analyse d'impact avant de resoudre.

### Severites

- **Critique** : Action urgente requise
- **Elevee** : A traiter rapidement
- **Moyenne** : A surveiller
- **Faible** : Informationnel

---

## 10. Detecter les anomalies

Le module **Anomalies** detecte les **valeurs statistiquement inhabituelles** dans vos donnees en utilisant l'algorithme **Isolation Forest**.

### Qu'est-ce qu'une anomalie ?

Selon la reference academique **Chandola, Banerjee & Kumar (2009)** — *Anomaly Detection: A Survey*, ACM Computing Surveys :

> Une anomalie est un ensemble de donnees qui ne se conforme pas au comportement attendu.

**Exemples concrets :**
- **Point aberrant** : Un montant de 500 000 EUR dans une colonne dont la moyenne est de 50 000 EUR
- **Anomalie contextuelle** : 3 000 commandes en janvier alors que la moyenne de janvier des annees precedentes est de 800

### Comment lancer une detection

1. Allez dans **"Anomalies"** dans le menu
2. Cliquez sur **"Detecter des anomalies"**
3. **Selectionnez une source** de donnees
4. **Selectionnez les colonnes numeriques** a analyser (boutons)
5. Cliquez sur **"Lancer la detection"**

### Ce que vous obtenez

- Une **liste d'anomalies** avec leur severite (Critique, Eleve, Moyen, Faible)
- Pour chaque anomalie :
  - Les **colonnes impliquees** et leur score de contribution
  - Une **explication automatisee** en francais
  - Les **actions** : Ignorer (faux positif), Affecter a quelqu'un, Marquer resolu

> **Faux positif ?** C'est normal. L'algorithme n'est pas parfait. Vous pouvez marquer une anomalie comme "Ignoree".

---

## 11. Generer des rapports PDF

Le module **Rapports** permet de creer des rapports PDF programmes.

### Creer un rapport

1. Cliquez sur **"Nouveau rapport"**
2. Donnez un **nom** au rapport
3. Choisissez la **source de donnees**
4. Choisissez la **frequence** :
   - Toutes les heures
   - Tous les jours
   - Toutes les semaines
   - Tous les mois
5. (Optionnel) Ajoutez des **destinataires email**
6. Cliquez sur **"Creer"**

### Executer un rapport maintenant

Dans l'onglet **"Mes rapports"**, cliquez sur **"Executer"** a cote d'un rapport pour le generer immediatement.

### Telecharger un PDF

Dans l'onglet **"Historique des PDF"**, cliquez sur **"Telecharger"** a cote d'un rapport genere.

### Contenu du PDF

Le rapport contient :
- Le **logo** et la **couleur de marque** de votre entreprise (configurables dans le profil)
- Les **KPIs** de la source selectionnee
- Des **graphiques** automatiques
- Un **resume des anomalies** detectees
- Un **resume des conflits**

---

## 12. Utiliser l'assistant IA

L'assistant IA est un chatbot alimente par **Llama 3.3 70B** qui analyse vos donnees en francais.

### Comment l'utiliser

1. Cliquez sur **"Assistant IA"** dans le menu
2. **Selectionnez une source** de donnees (en haut a droite)
3. **Posez votre question** dans la zone de texte
4. Appuyez sur **Entree** ou cliquez sur le bouton d'envoi

### Questions suggerees

- "Qu'est-ce que contiennent mes donnees ?"
- "Quels KPI necessitent une attention ?"
- "Analyse les tendances recentes"
- "Y a-t-il des anomalies ou signaux faibles ?"
- "Quelles sont les donnees les plus propres ?"

### Analyser un widget du Dashboard

1. Allez sur le **Dashboard**
2. Cliquez sur **"Analyse IA"** d'un widget
3. Le contenu du widget est envoye a l'assistant
4. L'assistant vous explique ce qu'il signifie

### Exporter une conversation

Cliquez sur **"Exporter"** pour sauvegarder votre conversation en fichier texte.

---

## 13. Gerer les utilisateurs

**Qui ?** Seuls les **Admins** ont acces a cette page.

### Creer un utilisateur

1. Cliquez sur **"Creer un membre"**
2. Remplissez : Nom complet, Nom d'utilisateur, Email, Mot de passe
3. Choisissez le **role** :
   - **Admin** : Acces total, gere les utilisateurs
   - **Analyste** : Peut importer, nettoyer, analyser
   - **Lecture** : Ne peut que consulter
4. Cliquez sur **"Creer"**

### Modifier un utilisateur

1. Cliquez sur **"Modifier"** a cote d'un utilisateur
2. Changez les informations souhaitees
3. Cliquez sur **"Enregistrer"**

### Supprimer un utilisateur

1. Cliquez sur **"Supprimer"** a cote d'un utilisateur
2. Confirmez la suppression

### Voir qui est en ligne

La page affiche en temps reel qui est connecte (refresh automatique toutes les 5 secondes).

---

## 14. Parametrer son profil

Cliquez sur votre **avatar** dans le menu a gauche, puis sur votre **nom**.

### Onglet Informations

- Nom complet, Email, Telephone, Departement
- Langue (Francais / English)
- Fuseau horaire

### Onglet Securite

- **Changer le mot de passe** : Saisissez l'ancien et le nouveau
- **Authentification a deux facteurs (2FA)** : Activer/desactiver
- **Zone dangereuse** : Supprimer votre compte (irreversible)

### Onglet Notifications

Activez ou desactivez les notifications pour :
- Anomalies detectees par l'IA
- Conflits de donnees
- Nouveau rapport
- Activite de l'equipe
- Rapport hebdomadaire par email

### Onglet Entreprise (Admin uniquement)

- **Nom de l'entreprise**
- **Logo** : Uploadez un fichier PNG, JPG ou SVG pour apparaitre sur les rapports PDF
- **Couleur de marque** : Choisissez une couleur qui sera utilisee dans les rapports

---

## 15. Creer des alertes

Le systeme d'alertes vous notifie quand un seuil est depasse ou qu'une anomalie est detectee.

### Creer une alerte

1. Allez dans **"Alertes"** dans le menu
2. Cliquez sur **"Nouvelle alerte"**
3. Remplissez :
   - **KPI** : L'indicateur a surveiller
   - **Type** : Depassement de seuil, Detection anomalie, Rapport programme
   - **Severite** : Info, Warning, Critical
   - **Condition** : La regle de declenchement (ex: value < 1000000)
   - **Destinataires** : Emails separes par des virgules
4. Cliquez sur **"Creer"**

### Notifications

- La **cloche de notification** dans le sidebar affiche les alertes non lues
- Vous recevez un **email** si des destinataires sont configures

---

## 16. Apercu du parcours complet

Voici le flux complet d'un utilisateur typique :

```
1. Creer un espace (ou se connecter)
       ↓
2. Importer un fichier Excel/CSV
       ↓
3. Voir l'apercu des donnees
       ↓
4. Lier les feuilles (si multi-feuilles)
       ↓
5. Nettoyer les donnees (automatique + choix)
       ↓
6. Valider le resultat
       ↓
7. Detecter les conflits → Les resoudre
       ↓
8. Voir le Dashboard (KPIs, graphiques)
       ↓
9. Detecter les anomalies → Les investiguer
       ↓
10. Generer des rapports PDF
       ↓
11. Poser des questions a l'assistant IA
       ↓
12. Creer des alertes pour etre notifie
```

---

## Roles et permissions

| Action | Admin | Analyste | Lecteur |
|--------|-------|----------|---------|
| Voir le Dashboard | Oui | Oui | Oui |
| Importer des donnees | Oui | Oui | Non |
| Nettoyer des donnees | Oui | Oui | Non |
| Voir les Conflits | Oui | Oui | Oui |
| Resoudre les Conflits | Oui | Oui | Non |
| Detecter les Anomalies | Oui | Oui | Oui |
| Utiliser l'Assistant IA | Oui | Oui | Oui |
| Generer des Rapports | Oui | Oui | Oui |
| Creer des Alertes | Oui | Oui | Oui |
| Gerer les Utilisateurs | Oui | Non | Non |
| Modifier le Profil Entreprise | Oui | Non | Non |

---

## Questions frequentes

**Q : Mon fichier Excel a plusieurs onglets, comment les croiser ?**
R : A l'etape 3 (Relations), le systeme detecte automatiquement les liens potentiels. Vous pouvez aussi les creer manuellement.

**Q : Le nettoyage a supprime des colonnes que je voulais garder. Comment revenir en arriere ?**
R : A l'etape 4, vous pouvez modifier les choix de suppression avant d'appliquer. Une fois applique, vous devez relancer le nettoyage.

**Q : Une anomalie est detectee mais c'est normal dans mon metier. Que faire ?**
R : Cliquez sur "Ignorer" pour la marquer comme faux positif. Elle n'apparaitra plus dans les anomalies actives.

**Q : Je ne vois pas "Importer donnees" dans le menu.**
R : Vous etes probablement en role "Lecture". Demandez a votre admin de changer votre role en "Analyste".

**Q : Comment exporter le Dashboard en PDF ?**
R : Cliquez sur le bouton d'export en haut a droite du Dashboard.

**Q : L'assistant IA ne repond pas.**
R : Verifiez votre connexion internet. L'assistant utilise un modele IA externe (Llama 3.3 70B) qui necessite une connexion.

**Q : Comment changer la couleur des rapports PDF ?**
R : Allez dans votre Profil > onglet Entreprise > Couleur de marque (admin uniquement).

---

*DecisioBI — 2026. Tous droits reserves.*

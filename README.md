# Decisio

Decisio est une plateforme d'aide a la decision pour analyser, nettoyer et exploiter des donnees metier dans une seule application. Le depot combine un backend Django et un frontend React/Vite pour couvrir le cycle complet: ingestion, nettoyage, consolidation, visualisation et interaction utilisateur.

## Vue D'ensemble

- Backend: API Django avec base PostgreSQL, authentification, traitement metier et integration Celery.
- Frontend: application React 19 avec TanStack Start, Vite, TypeScript et composants UI modernes.
- Objectif: fournir des tableaux de bord, des analyses, des alertes et des vues operationnelles autour des donnees importees.

## Fonctionnalites Principales

- Authentification et gestion des utilisateurs.
- Import de donnees et parcours de nettoyage.
- Tableaux de bord avec indicateurs, graphiques et widgets.
- Analyse pivot et exploration des donnees.
- Detection d'anomalies et resolution de conflits.
- Notifications et pages de suivi.
- Chatbot / assistance contextuelle selon la configuration du projet.

## Structure Du Depot

- `backend/`: projet Django, API, tests, scripts et documentation backend.
- `decision-spark/`: frontend React/Vite.
- `README.md`: vue d'ensemble et instructions de demarrage.
- `*.md` a la racine: guides et documents de livraison.

## Prerequis

- Python 3.12 ou plus recent.
- Node.js 20 ou plus recent.
- PostgreSQL 15 ou plus recent pour l'environnement de developpement complet.
- Redis si vous executez les taches Celery.

## Configuration

### Backend

Copiez `backend/.env.example` vers `backend/.env`, puis adaptez les valeurs:

- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `CORS_ALLOWED_ORIGINS`
- `FRONTEND_BASE_URL`
- `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`
- `OPENAI_API_KEY`, `OPENAI_KPI_MODEL`

### Frontend

Copiez `decision-spark/.env.example` vers `decision-spark/.env` si vous devez pointer vers une API distante:

- `VITE_API_BASE_URL`
- `VITE_API_VERSION`

En local, laisser `VITE_API_BASE_URL` vide permet au serveur de dev de proxifier les appels API vers le backend.

## Installation Locale

### 1. Cloner le depot

```bash
git clone https://github.com/FabriceRachid/Decisio.git
cd Decisio
```

### 2. Backend Django

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Le backend est generalement expose sur `http://127.0.0.1:8000`.

### 3. Frontend React / Vite

Dans un autre terminal:

```bash
cd decision-spark
npm install
npm run dev
```

Le frontend est expose a l'URL affichee par Vite au demarrage.

## Commandes Utiles

### Backend

```bash
python manage.py test
pytest
python manage.py makemigrations
python manage.py migrate
```

Si Celery est active dans votre environnement:

```bash
celery -A decisiobi worker -l info
celery -A decisiobi beat -l info
```

### Frontend

```bash
npm run build
npm run lint
npm run preview
```

## Qualite Et Tests

- Le backend utilise `pytest` et des tests Django.
- Le frontend dispose de tests avec Vitest et Testing Library.
- Les rapports de couverture, caches de test et artefacts de build sont ignores via `.gitignore`.

## Deploiement

Checklist minimale avant mise en production:

1. Renseigner les variables d'environnement de production.
2. Executer les migrations.
3. Collecter les fichiers statiques si necessaire.
4. Construire le frontend avec `npm run build`.
5. Demarrer le backend, les workers Celery et le frontend ou le serveur statique selon votre architecture.

## Documentation Supplementaire

- `backend/` contient plusieurs guides de reference et de test.
- Les fichiers `DEPLOYMENT_CHECKLIST.md`, `IMPLEMENTATION_COMPLETE.md` et les autres documents racine servent de memo technique pour les livraisons.

## Notes De Maintenance

- Les images, diagrammes generes, caches Python, caches Vite, artefacts de couverture et medias locaux sont ignores pour garder le depot propre.
- Si vous ajoutez de nouveaux artefacts de generation, pensez a les declarer dans `.gitignore`.

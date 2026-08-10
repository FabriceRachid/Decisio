# Guide de deploiement DecisioBI

---

## Architecture de production

```
Frontend (Vercel)  -->  Backend API (Render)  -->  PostgreSQL (Neon)
                                |
                                v
                          Redis (Render)
                          Celery Worker
```

**Services necessaires :**

| Service | Pourquoi | Gratuit ? |
|---------|----------|-----------|
| Frontend | Interface utilisateur | Oui (Vercel) |
| Backend | API Django | Oui (Render free tier) |
| PostgreSQL | Base de donnees | Oui (Neon free tier) |
| Redis | Celery broker | Oui (Render free tier) |

---

## AVANT DE COMMENCER

1. Un compte **GitHub** avec votre code
2. Un compte **Render** (render.com)
3. Un compte **Vercel** (vercel.com)
4. Un compte **Neon** (neon.tech) — PostgreSQL gratuit avec pgvector
5. Une cle **GROQ_API_KEY** (groq.com) — gratuit

---

## ETAPE 1 — Base de donnees PostgreSQL (Neon)

Neon supporte nativement **pgvector** (necessaire pour la detection structurelle).

1. Creez un compte sur **neon.tech**
2. Creez un nouveau projet :
   - Nom : `decisio-db`
   - Region : la plus proche de vos users
   - PostgreSQL version : **16** (ou superieure)
3. Dans le dashboard, allez dans **Connection Details**
4. Copiez l'**URI de connexion** — elle ressemble a :
   ```
   postgresql://neondb_owner:xxxx@ep-xxxx.us-east-2.aws.neon.tech/decisio_db?sslmode=require
   ```
5. Activez l'extension **pgvector** :
   - Allez dans l'onglet **SQL Editor** du dashboard Neon
   - Executez :
     ```sql
     CREATE EXTENSION IF NOT EXISTS vector;
     ```

> **Alternative :** Supabase (supabase.com) supporte aussi pgvector.

---

## ETAPE 2 — Backend sur Render

### 2.1 Creer un repo GitHub separe pour le backend

Le backend doit etre dans son propre repo pour Render :

```bash
mkdir decisio-backend
cp -r backend/* decisio-backend/
cd decisio-backend
git init
git add .
git commit -m "Initial backend"
git remote add origin https://github.com/VOTRE_USER/decisio-backend.git
git push -u origin main
```

### 2.2 Fichiers de deploiement

Creez ces fichiers dans la racine du repo `decisio-backend` :

**`render.yaml`** :

```yaml
services:
  - type: web
    name: decisio-backend
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt && python manage.py migrate && python manage.py install_pgvector && python manage.py collectstatic --noinput
    startCommand: gunicorn decisiobi.wsgi:application --bind 0.0.0.0:$PORT
    envVars:
      - key: SECRET_KEY
        generateValue: true
      - key: DEBUG
        value: "False"
      - key: ALLOWED_HOSTS
        value: "decisio-backend.onrender.com"
      - key: CORS_ALLOWED_ORIGINS
        value: "https://VOTRE-frontend.vercel.app"
      - key: DB_NAME
        sync: false
      - key: DB_USER
        sync: false
      - key: DB_PASSWORD
        sync: false
      - key: DB_HOST
        sync: false
      - key: DB_PORT
        value: "5432"
      - key: GROQ_API_KEY
        sync: false
      - key: FRONTEND_BASE_URL
        value: "https://VOTRE-frontend.vercel.app"

  - type: worker
    name: decisio-celery-worker
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: celery -A decisiobi worker -l info --concurrency=2
    envVars:
      - key: CELERY_BROKER_URL
        fromService:
          name: decisio-redis
          property: connectionString
      - key: CELERY_RESULT_BACKEND
        fromService:
          name: decisio-redis
          property: connectionString

  - type: cron
    name: decisio-celery-beat
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: celery -A decisiobi beat -l info
    envVars:
      - key: CELERY_BROKER_URL
        fromService:
          name: decisio-redis
          property: connectionString

  - type: redis
    name: decisio-redis
    plan: free
    ipAllowList: []
```

**`runtime.txt`** :

```
python-3.12.13
```

### 2.3 Variables d'environnement sur Render

Dans le dashboard Render, allez dans **Environment** du service web :

| Cle | Valeur |
|-----|--------|
| `SECRET_KEY` | `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `decisio-backend.onrender.com` |
| `CORS_ALLOWED_ORIGINS` | `https://VOTRE-frontend.vercel.app` |
| `DB_NAME` | `decisio_db` |
| `DB_USER` | `neondb_owner` (votre user Neon) |
| `DB_PASSWORD` | `xxxx` (mot de passe Neon) |
| `DB_HOST` | `ep-xxxx.us-east-2.aws.neon.tech` |
| `DB_PORT` | `5432` |
| `GROQ_API_KEY` | `gsk_xxxx` |
| `FRONTEND_BASE_URL` | `https://VOTRE-frontend.vercel.app` |
| `EMAIL_HOST_USER` | `votre-email@gmail.com` |
| `EMAIL_HOST_PASSWORD` | `xxxx` (mot de passe application Gmail) |

### 2.4 Premier demarrage

Apres le premier deploiement, allez dans le **Shell** du service Render :

```bash
python manage.py migrate
python manage.py install_pgvector
python manage.py createsuperuser
```

Suivez les instructions pour creer votre compte admin.

---

## ETAPE 3 — Frontend sur Vercel

### 3.1 Creer un repo GitHub separe pour le frontend

```bash
mkdir decisio-frontend
cp -r decision-spark/* decisio-frontend/
cd decisio-frontend
git init
git add .
git commit -m "Initial frontend"
git remote add origin https://github.com/VOTRE_USER/decisio-frontend.git
git push -u origin main
```

### 3.2 Configurer le build pour Vercel

Le frontend utilise TanStack Start + Cloudflare Workers. Pour Vercel, il faut adapter `vite.config.ts` :

**Option A — Build statique (recommande) :**

Remplacez le contenu de `vite.config.ts` par :

```typescript
import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [
    tailwindcss(),
    react(),
    tsconfigPaths(),
  ],
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_API_BASE_URL || "http://localhost:8000",
        changeOrigin: true,
      },
      "/media": {
        target: process.env.VITE_API_BASE_URL || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

**Option B — Garder le SSR Cloudflare :**

Deployez sur **Cloudflare Pages** au lieu de Vercel (le projet est deja configure pour).

### 3.3 Variables d'environnement Vercel

Dans le dashboard Vercel, allez dans **Settings > Environment Variables** :

| Cle | Valeur |
|-----|--------|
| `VITE_API_BASE_URL` | `https://decisio-backend.onrender.com` |

### 3.4 Deploiement Vercel

1. Allez sur **vercel.com**
2. Cliquez **"Add New Project"**
3. Importez votre repo GitHub `decisio-frontend`
4. Configuration :
   - **Framework Preset** : Vite
   - **Build Command** : `npm run build`
   - **Output Directory** : `dist`
   - **Install Command** : `npm install`
5. Ajoutez la variable `VITE_API_BASE_URL`
6. Cliquez **"Deploy"**

### 3.5 Verifier

1. Vercel vous donne une URL (ex: `decisio-frontend.vercel.app`)
2. Allez sur cette URL
3. Verifiez que la page de connexion s'affiche
4. Connectez-vous avec le compte admin cree sur Render
5. Verifiez que le Dashboard se charge

---

## ETAPE 4 — Mise a jour du backend

Retournez sur Render et mettez a jour :

| Variable | Nouvelle valeur |
|----------|-----------------|
| `ALLOWED_HOSTS` | `decisio-backend.onrender.com` |
| `CORS_ALLOWED_ORIGINS` | `https://decisio-frontend.vercel.app` |
| `FRONTEND_BASE_URL` | `https://decisio-frontend.vercel.app` |

Puis **redeploy** le service.

---

## ETAPE 5 — Emails (optionnel)

Pour les emails de reinitialisation de mot de passe :

1. Activez la **verification en 2 etapes** sur Gmail
2. Creez un **mot de passe d'application** dans les parametres Google
3. Sur Render :
   - `EMAIL_HOST_USER` : `votre-email@gmail.com`
   - `EMAIL_HOST_PASSWORD` : le mot de passe d'application

---

## Checklist de deploiement

### Backend (Render)
- [ ] Repo GitHub cree avec le code backend
- [ ] `render.yaml` ajoute
- [ ] `runtime.txt` avec Python 3.12
- [ ] Service web cree sur Render
- [ ] Variables d'environnement configurees
- [ ] PostgreSQL (Neon) cree avec pgvector active
- [ ] Redis cree sur Render
- [ ] Celery worker cree
- [ ] Celery beat cree
- [ ] `python manage.py migrate` execute
- [ ] `python manage.py install_pgvector` execute
- [ ] `python manage.py createsuperuser` execute
- [ ] API accessible sur `https://decisio-backend.onrender.com/api/`

### Frontend (Vercel)
- [ ] Repo GitHub cree avec le code frontend
- [ ] `vite.config.ts` adapte pour Vercel
- [ ] Variable `VITE_API_BASE_URL` configuree
- [ ] Projet cree sur Vercel
- [ ] Build reussi
- [ ] Page de connexion accessible
- [ ] Connexion fonctionne

### Post-deploiement
- [ ] `ALLOWED_HOSTS` mis a jour
- [ ] `CORS_ALLOWED_ORIGINS` mis a jour
- [ ] `FRONTEND_BASE_URL` mis a jour
- [ ] Test de connexion
- [ ] Test d'import de fichier
- [ ] Test de nettoyage
- [ ] Test de detection d'anomalies

---

## Problemes frequents

**Q : Le frontend affiche "Erreur reseau"**
R : Verifiez que `VITE_API_BASE_URL` pointe vers le bon backend et que `CORS_ALLOWED_ORIGINS` contient l'URL du frontend.

**Q : Le backend ne demarre pas sur Render**
R : Verifiez les logs dans le dashboard Render. Les causes courantes : variable d'environnement manquante, migration non executee, pgvector non active.

**Q : Les images/media ne s'affichent pas**
R : En production, les media files doivent etre servis par un stockage externe (S3, Cloudflare R2). En free tier, le service media de Django est desactive en production.

**Q : Le Celery ne fonctionne pas**
R : Verifiez que le Redis est bien cree et que `CELERY_BROKER_URL` est correct. Le worker doit etre un service separate sur Render.

**Q : La detection structurelle ne marche pas**
R : Verifiez que pgvector est active sur Neon (`CREATE EXTENSION IF NOT EXISTS vector;`) et que `GROQ_API_KEY` est configure.

---

*DecisioBI — 2026. Guide de deploiement.*

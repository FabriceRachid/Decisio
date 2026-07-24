# PostgreSQL Setup Guide for Decisio

## 📋 What You Need to Do:

### Step 1: Install PostgreSQL (if not already installed)

**Windows:**
1. Download from: https://www.postgresql.org/download/windows/
2. Run installer (PostgreSQL 15 or higher recommended)
3. During installation:
   - Set password for `postgres` superuser (remember this!)
   - Keep default port: 5432
   - Install pgAdmin 4 (optional but useful)

### Step 2: Create Database and User

**Option A: Using pgAdmin (GUI)**
1. Open pgAdmin 4
2. Connect to PostgreSQL (use postgres user)
3. Right-click "Databases" → Create → Database
   - Name: `decisio_db`
4. Right-click "Login/Group Roles" → Create → Login/Group Role
   - Name: `decisio_user`
   - Password: choose a secure password
   - Privileges tab: Check "Can login?"
5. Right-click your new database → Properties → Access Privileges
   - Grant all privileges to `decisio_user`

**Option B: Using SQL Shell (psql)**
```bash
# Open Command Prompt and run:
psql -U postgres

# Then in psql:
CREATE DATABASE decisio_db;
CREATE USER decisio_user WITH PASSWORD 'your_secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE decisio_db TO decisio_user;
\q
```

### Step 3: Update .env File

Edit `backend\.env` with your actual credentials:
```env
DB_NAME=decisio_db
DB_USER=decisio_user
DB_PASSWORD=YOUR_ACTUAL_PASSWORD_HERE
DB_HOST=localhost
DB_PORT=5432
```

### Step 4: Test Connection

In the backend folder, run:
```powershell
python manage.py check
python manage.py migrate
```

If everything works, you should see successful migration output!

---

## 🔧 Current Configuration Status:

✅ Django settings configured for PostgreSQL
✅ Environment variables setup (.env)
✅ Requirements.txt updated
✅ CORS middleware configured for frontend access
⏳ **Waiting for:** PostgreSQL installation & database creation

---

## 📁 Files Modified:

- `backend/.env` - Environment variables
- `backend/requirements.txt` - Dependencies
- `backend/decisiobi/settings.py` - Django configuration

---

## 🚀 Next Steps After DB Setup:

1. Run migrations: `python manage.py migrate`
2. Create superuser: `python manage.py createsuperuser`
3. Start server: `python manage.py runserver`

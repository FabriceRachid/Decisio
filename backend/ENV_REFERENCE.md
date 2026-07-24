# Quick Reference: Environment Variables Configuration

## 🔐 Current .env Setup (backend/.env)

```env
# PostgreSQL Database Configuration
DB_NAME=decisio_db
DB_USER=decisio_user
DB_PASSWORD=your_secure_password_here  # ← CHANGE THIS!
DB_HOST=localhost
DB_PORT=5432

# Django Secret Key
SECRET_KEY=django-insecure-sb_)27k)##w^jge9fg0npb)=c9x5o22l1#cg1=24u9f!l^=ntl

# Debug Mode
DEBUG=True

# Allowed Hosts
ALLOWED_HOSTS=localhost,127.0.0.1
```

---

## ⚠️ IMPORTANT: Before Going to Production

1. **Change DB_PASSWORD** to a strong, unique password
2. **Generate new SECRET_KEY**: Run this in Python shell:
   ```python
   from django.core.management.utils import get_random_secret_key
   print(get_random_secret_key())
   ```
3. **Set DEBUG=False** in production
4. **Update ALLOWED_HOSTS** with your actual domain/IP

---

## 📦 Dependencies Installed (requirements.txt)

✅ Django 6.0+
✅ djangorestframework (API)
✅ django-cors-headers (CORS)
✅ psycopg2-binary (PostgreSQL adapter)
✅ python-dotenv (Environment variables)

---

## 🎯 What's Configured in settings.py

### 1. Environment Variables Loading
```python
from dotenv import load_dotenv
load_dotenv()  # Loads variables from .env
```

### 2. PostgreSQL Database
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
    }
}
```

### 3. Security Settings
- SECRET_KEY from environment
- DEBUG mode from environment
- ALLOWED_HOSTS from environment

### 4. CORS Configuration
- Allows frontend access from localhost:3000 and :5173
- `CORS_ALLOW_ALL_ORIGINS = DEBUG` for development

### 5. Static & Media Files
- STATIC_URL, STATIC_ROOT, STATICFILES_DIRS
- MEDIA_URL, MEDIA_ROOT

### 6. Default Field Type
- `DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'`

---

## ✅ Next Steps

1. Install PostgreSQL
2. Create database and user
3. Update `.env` with actual password
4. Run: `python manage.py migrate`
5. Run: `python manage.py createsuperuser`
6. Start: `python manage.py runserver`

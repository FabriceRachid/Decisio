# M9 Authentication Quick Start Guide

> Status note: this file is retained for backward compatibility.
> Use `M9_AUTHENTICATION_REFERENCE.md` for the current endpoint list and tested flows.

## ✅ **What's Been Implemented**

Your Django backend now has a **complete authentication system** with:

### **Core Features:**
- ✅ JWT Token Authentication (Access + Refresh)
- ✅ Role-Based Access Control (Admin, Analyst, Viewer)
- ✅ User Registration & Login APIs
- ✅ Profile Management
- ✅ Password Change
- ✅ API Token Management
- ✅ Admin User Controls

---

## 🚀 **Quick Start (3 Steps)**

### **Step 1: Start Django Server**

```bash
cd backend
python manage.py runserver
```

Server runs at: `http://localhost:8000`

---

### **Step 2: Create Your First User**

**Option A: Via API (Recommended)**

Use Postman or the test script:
```bash
python test_auth_api.py
```

**Option B: Via Django Shell**

```bash
python manage.py createsuperuser
# Username: admin
# Email: admin@decisio.com
# Password: ********
```

Then set role via Django shell:
```bash
python manage.py shell

>>> from django.contrib.auth.models import User
>>> user = User.objects.get(username='admin')
>>> user.profile.role = 'admin'
>>> user.profile.save()
>>> exit()
```

---

### **Step 3: Test Authentication**

**Using Postman/Thunder Client:**

1. **Register User**
   ```
   POST http://localhost:8000/api/auth/register/
   
   Body (JSON):
   {
     "username": "testuser",
     "email": "test@example.com",
     "password": "SecurePass123",
     "password_confirm": "SecurePass123"
   }
   ```

2. **Login**
   ```
   POST http://localhost:8000/api/auth/login/
   
   Body (JSON):
   {
     "username": "testuser",
     "password": "SecurePass123"
   }
   
   Response includes:
   - access_token (valid 60 min)
   - refresh_token (valid 7 days)
   ```

3. **Access Protected Endpoint**
   ```
   GET http://localhost:8000/api/auth/profile/
   
   Headers:
   Authorization: Bearer <access_token_here>
   ```

---

## 📡 **API Endpoints Cheat Sheet**

### **Public Endpoints (No Auth)**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/register/` | POST | Create new account |
| `/api/auth/login/` | POST | Login |
| `/api/auth/token/` | POST | Get JWT tokens |
| `/api/auth/token/refresh/` | POST | Refresh access token |

### **Authenticated Endpoints**
| Endpoint | Method | Permission |
|----------|--------|------------|
| `/api/auth/profile/` | GET/PUT | Any authenticated user |
| `/api/auth/change-password/` | POST | Any authenticated user |
| `/api/auth/status/` | GET | Any authenticated user |
| `/api/auth/tokens/` | GET/POST | Any authenticated user |
| `/api/auth/tokens/<id>/revoke/` | POST | Token owner |

### **Admin Only**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/auth/admin/users/` | GET | List all users |
| `/api/auth/admin/users/<id>/` | GET/PUT/DELETE | Manage specific user |
| `/api/auth/admin/users/<id>/update-role/` | POST | Change user role |

---

## 🔑 **JWT Token Usage**

### **How to Use Tokens:**

```javascript
// Frontend example (React/Vue)

// 1. Store tokens after login
localStorage.setItem('access_token', response.access_token);
localStorage.setItem('refresh_token', response.refresh_token);

// 2. Add to API requests
const apiCall = async () => {
  const token = localStorage.getItem('access_token');
  
  const response = await fetch('/api/kpi/1/', {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  
  return response.json();
};

// 3. Handle token expiration
if (response.status === 401) {
  // Token expired - refresh it
  const newToken = await refreshAccessToken();
  // Retry original request
}
```

---

## 🛡️ **RBAC Permission Examples**

### **Protecting Your Module Endpoints:**

```python
from apps.authentication.permissions import IsAdminRole, CanWriteData

# Example: KPI endpoint protection
class KPIListView(generics.ListAPIView):
    """List KPIs"""
    permission_classes = [CanWriteData]  # Viewers, Analysts, Admins
    
class KPICreateView(generics.CreateAPIView):
    """Create new KPI"""
    permission_classes = [IsAnalystRole]  # Only Analysts + Admins
    
class KPIDeleteView(generics.DestroyAPIView):
    """Delete KPI"""
    permission_classes = [IsAdminRole]  # Only Admins
```

---

## 🧪 **Testing Commands**

### **Run Unit Tests:**
```bash
python manage.py test apps.authentication
```

### **Run API Test Script:**
```bash
pip install requests
python test_auth_api.py
```

### **Manual cURL Test:**
```bash
# Register
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@test.com","password":"test123","password_confirm":"test123"}'

# Login
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}'

# Get Profile
curl -X GET http://localhost:8000/api/auth/profile/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

---

## 📁 **Files Created**

```
backend/
├── apps/authentication/
│   ├── models.py          ← UserProfile, AuthToken
│   ├── serializers.py     ← API data converters
│   ├── views.py           ← API endpoints logic
│   ├── permissions.py     ← RBAC rules
│   ├── urls.py            ← URL routing
│   ├── signals.py         ← Auto-create profiles
│   ├── tests.py           ← Unit tests
│   └── README.md          ← Module docs
│
├── decisiobi/settings.py  ← JWT + REST config
├── decisiobi/urls.py      ← Main URL routing
│
├── test_auth_api.py       ← API test script
├── M9_AUTHENTICATION_GUIDE.md  ← Detailed guide
└── AUTH_QUICKSTART.md     ← This file
```

---

## ⚙️ **Configuration Reference**

### **JWT Settings (`settings.py`):**
```python
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
}
```

### **REST Framework Settings:**
```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
```

---

## 🐛 **Troubleshooting**

### **Issue: "Token has expired"**
**Solution:** Use `/api/auth/token/refresh/` endpoint with refresh token

### **Issue: "Authentication credentials not provided"**
**Solution:** Add `Authorization: Bearer <token>` header to request

### **Issue: "User has no profile"**
**Solution:** Run migrations and ensure signals.py is working

### **Issue: CORS error from frontend**
**Solution:** Add frontend URL to `CORS_ALLOWED_ORIGINS` in settings.py

---

## 📊 **Database Schema**

### **Authentication Tables:**

**auth_user** (Django default)
```
- id (PK)
- username
- email
- password (hashed)
- first_name
- last_name
- is_active
- date_joined
- last_login
```

**authentication_userprofile** (Custom)
```
- id (PK)
- user_id (FK → auth_user)
- role (viewer/analyst/admin)
- department
- phone_number
- timezone
- language
- mfa_enabled
```

**authentication_authtoken** (API tokens)
```
- id (PK)
- user_id (FK → auth_user)
- token_hash (SHA256)
- token_prefix (first 8 chars)
- name
- scopes (JSON array)
- rate_limit
- created_at
- expires_at
- last_used_at
```

---

## 🎯 **Next Steps**

### **For Backend Development:**
1. ✅ Test all authentication endpoints
2. ✅ Create sample users with different roles
3. ✅ Implement password reset flow
4. ✅ Add activity logging for security events

### **For Frontend Integration:**
1. ✅ Create login/register pages
2. ✅ Store JWT tokens securely
3. ✅ Add token to API requests
4. ✅ Handle token refresh automatically
5. ✅ Implement role-based UI (hide/show features)

### **For Production:**
1. ✅ Enable HTTPS only
2. ✅ Set secure cookie flags
3. ✅ Configure rate limiting
4. ✅ Set up monitoring/alerting
5. ✅ Regular security audits

---

## 📚 **Additional Resources**

- **Full Guide:** `M9_AUTHENTICATION_GUIDE.md`
- **Module Docs:** `apps/authentication/README.md`
- **Test Suite:** `test_auth_api.py`
- **JWT Spec:** https://jwt.io/
- **DRF Docs:** https://www.django-rest-framework.org/

---

## ✨ **Summary**

You now have a **production-ready authentication system** that includes:

✅ Secure JWT tokens (60-min access, 7-day refresh)  
✅ Three-tier RBAC (Admin, Analyst, Viewer)  
✅ Complete API endpoints (register, login, profile, tokens)  
✅ Admin user management tools  
✅ API token generation with scopes  
✅ Comprehensive documentation  
✅ Automated test suite  

**🎊 Ready to integrate with your frontend!**

---

**Need help?** Check:
- `M9_AUTHENTICATION_GUIDE.md` for detailed explanations
- `apps/authentication/README.md` for API reference
- `test_auth_api.py` for working examples

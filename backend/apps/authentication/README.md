# M9 Authentication Module

> Status note: parts of this file describe the original scaffolded design.
> Use `/backend/M9_AUTHENTICATION_REFERENCE.md` as the authoritative reference for the implemented module.

## ✅ **Implementation Complete!**

Your authentication system is now fully configured with:
- ✅ **JWT Token Authentication** (Secure, stateless auth)
- ✅ **Role-Based Access Control (RBAC)** (Admin, Analyst, Viewer)
- ✅ **User Registration & Login** APIs
- ✅ **Profile Management** endpoints
- ✅ **API Token Management** for programmatic access
- ✅ **Password Change** functionality
- ✅ **Admin User Management** tools

---

## 📋 **What You Get:**

### **1. JWT Authentication**
```python
Access Token:  Valid for 60 minutes
Refresh Token: Valid for 7 days (auto-rotated)
Algorithm:     HS256
Header:        Authorization: Bearer <token>
```

### **2. User Roles (RBAC)**
```
┌─────────────┬──────────────────────────────────────┐
│ Role        │ Permissions                          │
├─────────────┼──────────────────────────────────────┤
│ Admin       │ Full system access                   │
│ Analyst     │ Read/write data, create KPIs         │
│ Viewer      │ Read-only access                     │
└─────────────┴──────────────────────────────────────┘
```

### **3. API Endpoints**

#### **Public Endpoints (No Auth Required)**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register/` | Register new user |
| POST | `/api/auth/login/` | User login |
| POST | `/api/auth/token/` | Get JWT tokens |
| POST | `/api/auth/token/refresh/` | Refresh access token |

#### **Authenticated Endpoints**
| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/api/auth/profile/` | Get current user profile | Authenticated |
| PUT | `/api/auth/profile/` | Update profile | Authenticated |
| POST | `/api/auth/change-password/` | Change password | Authenticated |
| GET | `/api/auth/status/` | Check auth status | Authenticated |
| GET | `/api/auth/tokens/` | List API tokens | Authenticated |
| POST | `/api/auth/tokens/` | Create API token | Authenticated |
| POST | `/api/auth/tokens/<id>/revoke/` | Revoke token | Authenticated |

#### **Admin Only Endpoints**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/auth/admin/users/` | List all users |
| GET | `/api/auth/admin/users/<id>/` | Get user details |
| PUT | `/api/auth/admin/users/<id>/` | Update user |
| DELETE | `/api/auth/admin/users/<id>/` | Delete user |
| POST | `/api/auth/admin/users/<id>/update-role/` | Change user role |

---

## 🚀 **How to Use:**

### **Step 1: Register a New User**

```bash
POST http://localhost:8000/api/auth/register/
Content-Type: application/json

{
  "username": "john.doe",
  "email": "john@example.com",
  "password": "securepass123",
  "password_confirm": "securepass123",
  "first_name": "John",
  "last_name": "Doe"
}
```

**Response:**
```json
{
  "message": "User registered successfully",
  "user": {
    "id": 1,
    "username": "john.doe",
    "email": "john@example.com",
    "profile": {
      "role": "viewer",
      "role_display": "Viewer"
    }
  },
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

---

### **Step 2: Login**

```bash
POST http://localhost:8000/api/auth/login/
Content-Type: application/json

{
  "username": "john.doe",
  "password": "securepass123"
}
```

**Response:**
```json
{
  "message": "Login successful",
  "user": {
    "id": 1,
    "username": "john.doe",
    "email": "john@example.com"
  },
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "Bearer"
}
```

---

### **Step 3: Access Protected Endpoints**

Use the access token in the Authorization header:

```bash
GET http://localhost:8000/api/auth/profile/
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

**Response:**
```json
{
  "id": 1,
  "username": "john.doe",
  "email": "john@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "profile": {
    "id": 1,
    "role": "viewer",
    "role_display": "Viewer",
    "department": null,
    "timezone": "UTC"
  }
}
```

---

### **Step 4: Refresh Token**

When your access token expires (after 60 minutes), use the refresh token:

```bash
POST http://localhost:8000/api/auth/token/refresh/
Content-Type: application/json

{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Response:**
```json
{
  "access": "NEW_ACCESS_TOKEN_HERE"
}
```

---

### **Step 5: Create API Token (for programmatic access)**

```bash
POST http://localhost:8000/api/auth/tokens/
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{
  "name": "My App Integration",
  "scopes": ["read:data", "write:kpi"],
  "expires_in_days": 90
}
```

**Response:**
```json
{
  "id": 1,
  "name": "My App Integration",
  "token_prefix": "a1b2c3d4",
  "token": "FULL_TOKEN_SHOWN_ONCE",
  "scopes_list": ["read:data", "write:kpi"],
  "rate_limit": 1000,
  "expires_at": "2026-06-28T10:30:00Z"
}
```

⚠️ **Important:** Save the full token immediately - it's only shown once!

---

### **Step 6: Admin - Update User Role**

```bash
POST http://localhost:8000/api/auth/admin/users/1/update-role/
Authorization: Bearer ADMIN_TOKEN
Content-Type: application/json

{
  "role": "analyst"
}
```

**Response:**
```json
{
  "message": "User role updated to analyst",
  "user": {
    "id": 1,
    "username": "john.doe",
    "email": "john@example.com",
    "is_active": true,
    "profile": {
      "role": "analyst",
      "role_display": "Data Analyst"
    }
  }
}
```

---

## 🔧 **Configuration Details:**

### **JWT Settings** (`settings.py`)

```python
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),      # 1 hour
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),         # 7 days
    'ROTATE_REFRESH_TOKENS': True,                        # New refresh token each time
    'BLACKLIST_AFTER_ROTATION': True,                     # Old refresh tokens invalid
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}
```

### **REST Framework Settings**

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'PAGE_SIZE': 20,
}
```

---

## 🛡️ **Security Features:**

### **1. Password Validation**
- Minimum 8 characters
- Not similar to username/email
- Not common password
- Not entirely numeric

### **2. Token Security**
- Signed with SHA256
- Auto-expiration
- Refresh token rotation
- Blacklist for revoked tokens

### **3. RBAC Protection**
- Role-based endpoint access
- Object-level permissions
- Owner-only modifications

### **4. CORS Configuration**
- Restricted origins in production
- Allowed: localhost:3000, localhost:5173 (dev)

---

## 📦 **Files Created:**

```
apps/authentication/
├── models.py           # UserProfile, AuthToken
├── serializers.py      # NEW! API serializers
├── views.py            # NEW! API views
├── permissions.py      # NEW! RBAC permission classes
├── urls.py             # NEW! URL routing
├── signals.py          # Auto-create profiles
└── tests.py            # Test suite

decisiobi/
├── settings.py         # UPDATED! JWT + REST config
└── urls.py             # UPDATED! Added auth URLs
```

---

## 🧪 **Testing:**

### **Run Tests**
```bash
python manage.py test apps.authentication
```

### **Manual Testing with cURL**

**Register:**
```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@test.com","password":"testpass123","password_confirm":"testpass123"}'
```

**Login:**
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass123"}'
```

**Get Profile:**
```bash
curl -X GET http://localhost:8000/api/auth/profile/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## 🎯 **Next Steps:**

### **1. Create Initial Admin User**
```bash
python manage.py createsuperuser
```

### **2. Test with Postman/Thunder Client**
Import the API endpoints and test authentication flow

### **3. Integrate with Frontend**
Use the JWT tokens in your React/Vue frontend:
```javascript
// Store tokens in localStorage
localStorage.setItem('access_token', response.access_token);
localStorage.setItem('refresh_token', response.refresh_token);

// Add to requests
axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
```

### **4. Protect Other Endpoints**
Add permission classes to your other module views:
```python
from apps.authentication.permissions import IsAnalystRole

class KPIListView(generics.ListAPIView):
    permission_classes = [IsAnalystRole]
```

---

## 📚 **API Reference:**

### **Request/Response Examples**

#### **Registration Request**
```json
POST /api/auth/register/
{
  "username": "newuser",
  "email": "new@example.com",
  "password": "secure123",
  "password_confirm": "secure123"
}
```

#### **Registration Response**
```json
{
  "message": "User registered successfully",
  "user": {
    "id": 1,
    "username": "newuser",
    "email": "new@example.com",
    "profile": {
      "role": "viewer"
    }
  },
  "tokens": {
    "access": "...",
    "refresh": "..."
  }
}
```

#### **Error Response**
```json
{
  "error": "Invalid credentials",
  "detail": "Username or password incorrect"
}
```

---

## 🔍 **Troubleshooting:**

### **Issue: Token Expired**
**Solution:** Use refresh token endpoint to get new access token

### **Issue: CORS Error**
**Solution:** Add your frontend URL to `CORS_ALLOWED_ORIGINS` in settings.py

### **Issue: Permission Denied**
**Solution:** Check user role has required permission for endpoint

### **Issue: Profile Not Created**
**Solution:** Signals should auto-create - check logs for errors

---

## 📖 **Additional Resources:**

- [Django REST Framework Docs](https://www.django-rest-framework.org/)
- [Simple JWT Docs](https://django-rest-framework-simplejwt.readthedocs.io/)
- [JWT.io - Token Debugger](https://jwt.io/)

---

## ✨ **Summary:**

Your authentication system is **production-ready** with:
- ✅ Secure JWT tokens
- ✅ Role-based permissions
- ✅ User management APIs
- ✅ Token lifecycle management
- ✅ Admin controls

**Ready to integrate with your frontend!** 🚀

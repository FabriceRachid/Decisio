# M9 Authentication Implementation Guide

> Status note: this file contains legacy explanatory material from the earlier scaffold phase.
> Use `M9_AUTHENTICATION_REFERENCE.md` as the authoritative documentation for the current implementation.

## 📋 **Progressive Explanation - Step by Step**

I'll explain everything gradually from basics to advanced concepts.

---

## 🎯 **Level 1: Why Authentication?**

### **The Problem:**
Your Decisio platform has sensitive data:
- Business KPIs (revenue, metrics)
- Raw company data
- AI insights
- User dashboards

**Question:** How do we know who is accessing what?

### **The Solution:**
Authentication system that answers:
1. **Who are you?** → Login
2. **What can you do?** → Permissions (RBAC)
3. **Are you still you?** → Token validation

---

## 🔑 **Level 2: JWT Tokens Explained**

### **What is JWT?**
**JSON Web Token** = Secure digital signature

Think of it like a **concert ticket**:
```
┌─────────────────────────────────────┐
│  CONCERT TICKET                     │
│  ─────────────────────────────────  │
│  Holder: John Doe                   │
│  Section: VIP                       │
│  Valid: Tonight only                │
│  Signature: [Official Stamp] ✓      │
└─────────────────────────────────────┘
```

### **JWT Structure:**
```
eyJ0eXAiOiJKV1QiLCJhbGc... (Header)
.
eyJ1c2VyX2lkIjoxLCJyb2xl... (Payload - user info)
.
SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c (Signature)
```

**Three parts:**
1. **Header** - Algorithm used (HS256)
2. **Payload** - User data (id, role, expiry)
3. **Signature** - Security seal (prevents tampering)

---

## 🏗️ **Level 3: Our Architecture**

### **Components:**

```
┌──────────────────────────────────────────────┐
│  Frontend (React/Vue)                        │
│  - Login form                                │
│  - Stores tokens in localStorage             │
└──────────────────────────────────────────────┘
                    ↓ sends credentials
┌──────────────────────────────────────────────┐
│  Backend (Django + JWT)                      │
│  - Verifies username/password                │
│  - Creates signed JWT token                  │
│  - Returns token to frontend                 │
└──────────────────────────────────────────────┘
                    ↓ sends token with requests
┌──────────────────────────────────────────────┐
│  API Endpoints                               │
│  - Check token validity                      │
│  - Extract user from token                   │
│  - Apply RBAC permissions                    │
└──────────────────────────────────────────────┘
```

---

## 👥 **Level 4: Role-Based Access Control (RBAC)**

### **The Concept:**
Different users need different access levels.

### **Our Roles:**

```
┌─────────────┬──────────────────────────────────────┬────────────────────┐
│ Role        │ Can Do                               │ Example Use        │
├─────────────┼──────────────────────────────────────┼────────────────────┤
│ Admin       │ Everything                           │ IT Manager         │
│ Analyst     │ Read/write data, create KPIs         │ Data Analyst       │
│ Viewer      │ View dashboards only                 │ Executive          │
└─────────────┴──────────────────────────────────────┴────────────────────┘
```

### **Permission Flow:**
```
User Request → Check Role → Grant/Deny Access

Example:
GET /api/kpi/123/  (User: Viewer)
  ↓
Check: Viewer can read KPIs? ✓ YES
  ↓
Return: KPI data

DELETE /api/kpi/123/ (User: Viewer)
  ↓
Check: Viewer can delete? ✗ NO
  ↓
Return: 403 Forbidden
```

---

## 💻 **Level 5: Code Walkthrough**

### **A. User Registration**

**File:** `apps/authentication/views.py`

```python
class UserRegistrationView(generics.CreateAPIView):
    """Register a new user"""
    
    def create(self, request):
        # 1. Validate input data
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # 2. Create user in database
        user = serializer.save()
        
        # 3. Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        # 4. Return tokens + user info
        return Response({
            'user': UserSerializer(user).data,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
        })
```

**What happens:**
1. Check passwords match
2. Check email not already registered
3. Create User + UserProfile (auto via signals)
4. Generate JWT tokens
5. Send back to client

---

### **B. User Login**

**File:** `apps/authentication/views.py`

```python
class LoginView(APIView):
    """User login endpoint"""
    
    def post(self, request):
        # 1. Get credentials
        username = request.data.get('username')
        password = request.data.get('password')
        
        # 2. Verify credentials
        user = authenticate(username=username, password=password)
        
        if not user:
            return Response(
                {'error': 'Invalid credentials'},
                status=401_UNAUTHORIZED
            )
        
        # 3. Generate tokens
        refresh = RefreshToken.for_user(user)
        
        # 4. Return response
        return Response({
            'user': UserSerializer(user).data,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
        })
```

**Flow:**
```
Login Request → Verify Password → Create Tokens → Return JWT
```

---

### **C. Protected Endpoint**

**File:** `apps/authentication/views.py`

```python
class UserProfileView(generics.RetrieveUpdateAPIView):
    """Get/update current user profile"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user  # User from JWT token!
```

**How it works:**
1. Request comes with JWT token in header
2. Django checks token signature
3. If valid → extracts user_id from token
4. Fetches user from database
5. Returns user's profile

---

### **D. RBAC Permission Class**

**File:** `apps/authentication/permissions.py`

```python
class IsAdminRole(BaseRolePermission):
    """Only admins can access"""
    
    required_role = 'admin'
    
    def has_permission(self, request, view):
        # 1. Check if authenticated
        if not request.user.is_authenticated:
            return False
        
        # 2. Check if superuser
        if request.user.is_superuser:
            return True
        
        # 3. Check role
        return request.user.profile.role == 'admin'
```

**Usage in views:**
```python
class AdminUserListView(generics.ListAPIView):
    """List all users (Admin only)"""
    
    permission_classes = [IsAdminRole]  # ← Only admins!
```

---

## 🔧 **Level 6: Configuration**

### **JWT Settings** (`settings.py`)

```python
SIMPLE_JWT = {
    # Access token expires in 60 minutes
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    
    # Refresh token valid for 7 days
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    
    # Rotate refresh tokens (security!)
    'ROTATE_REFRESH_TOKENS': True,
    
    # Blacklist old refresh tokens
    'BLACKLIST_AFTER_ROTATION': True,
}
```

**Why these settings?**
- **Short access token** → If stolen, limited damage (1 hour)
- **Long refresh token** → User stays logged in (7 days)
- **Rotation** → Each refresh invalidates old token (theft detection)

---

## 📡 **Level 7: API Endpoints**

### **Complete Endpoint Map:**

```
/api/auth/
├── register/                    POST   Register new user
├── login/                       POST   Login
├── token/                       POST   Get JWT tokens
├── token/refresh/               POST   Refresh access token
│
├── profile/                     GET    Get my profile
│                                  PUT    Update my profile
│
├── change-password/             POST   Change password
├── status/                      GET    Check auth status
│
├── tokens/                      GET    List my API tokens
│                                  POST   Create API token
│
├── tokens/<id>/revoke/          POST   Revoke API token
│
└── admin/users/                 GET    List all users (Admin)
    ├── <id>/                    GET    Get user (Admin)
    │                            PUT    Update user (Admin)
    │                            DELETE Delete user (Admin)
    └── <id>/update-role/        POST   Change role (Admin)
```

---

## 🧪 **Level 8: Testing**

### **Test with Python Script:**

```bash
# Start server first
python manage.py runserver

# In another terminal
python test_auth_api.py
```

**What it tests:**
1. ✅ Register new user
2. ✅ Login and get tokens
3. ✅ Access protected endpoint
4. ✅ Create API token
5. ✅ Refresh access token

---

### **Test with cURL:**

**Register:**
```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "testpass123",
    "password_confirm": "testpass123"
  }'
```

**Login:**
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "testpass123"
  }'
```

**Access Protected Endpoint:**
```bash
curl -X GET http://localhost:8000/api/auth/profile/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE"
```

---

## 🛡️ **Level 9: Security Best Practices**

### **1. Token Storage (Frontend)**

**❌ Bad:**
```javascript
// Don't store in global variable
window.accessToken = token;
```

**✅ Good:**
```javascript
// Store in httpOnly cookie (best)
// OR secure localStorage with encryption
localStorage.setItem('access_token', encrypt(token));
```

### **2. HTTPS in Production**

**Never use JWT over HTTP!**
```python
# settings.py
SESSION_COOKIE_SECURE = True  # Only send over HTTPS
CSRF_COOKIE_SECURE = True
```

### **3. Token Expiration**

**Balance security vs UX:**
- Development: 60 min access, 7 days refresh
- Production: 15 min access, 30 days refresh
- High security: 5 min access, 1 day refresh

### **4. Rate Limiting**

Prevent brute force attacks:
```python
# Install django-ratelimit
pip install django-ratelimit

# In views
from ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='5/m')
def login_view(request):
    ...
```

---

## 🎓 **Level 10: Advanced Concepts**

### **Custom JWT Claims**

Add custom data to tokens:

```python
# Add user role to token payload
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class CustomTokenSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims
        token['role'] = user.profile.role
        token['department'] = user.profile.department
        
        return token
```

**Decode token to see claims:**
```python
import jwt
decoded = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
print(decoded['role'])  # Output: 'admin'
```

---

### **Token Blacklisting**

Revoke compromised tokens:

```python
from rest_framework_simplejwt.tokens import RefreshToken

# User logs out
refresh_token = RefreshToken(request.data['refresh'])
refresh_token.blacklist()  # Add to blacklist
```

**Database stores blacklisted tokens:**
```sql
SELECT * FROM token_blacklist_blacklistedtoken;
```

---

### **API Token Scopes**

Fine-grained permissions:

```python
# Token with specific scopes
token = AuthToken.objects.create(
    user=user,
    scopes=['read:data', 'write:kpi']  # Limited permissions
)

# Check scope in view
if 'write:kpi' not in token.scopes:
    return Response({'error': 'Insufficient scope'}, status=403)
```

---

## 📊 **Summary Table**

| Concept | What It Does | Why It Matters |
|---------|--------------|----------------|
| **JWT Token** | Signed digital credential | Stateless, secure auth |
| **Access Token** | Short-lived (60 min) | Limits damage if stolen |
| **Refresh Token** | Long-lived (7 days) | Keeps user logged in |
| **RBAC** | Role-based permissions | Controls access levels |
| **Token Rotation** | New refresh token each time | Detects theft |
| **Blacklist** | Revoked tokens list | Force logout capability |
| **Scopes** | Granular permissions | Least privilege principle |

---

## 🚀 **Next Steps:**

1. ✅ Test all endpoints with Postman
2. ✅ Integrate with your React frontend
3. ✅ Add password reset email flow
4. ✅ Implement 2FA (Google Authenticator)
5. ✅ Add social login (Google, GitHub)
6. ✅ Set up monitoring for failed logins
7. ✅ Configure session timeout policies

---

## ❓ **FAQ**

**Q: Why JWT instead of sessions?**
A: JWT is stateless (no server memory), scales better, works across domains

**Q: Can I modify JWT tokens?**
A: No! Signature prevents tampering. Any change breaks the signature.

**Q: What if refresh token is stolen?**
A: Rotation detects it → blacklist both old and new tokens → force re-login

**Q: How to implement "Remember Me"?**
A: Extend refresh token lifetime (e.g., 30 days instead of 7)

**Q: Can I revoke a specific user's tokens?**
A: Yes! Change their password or add to blacklist manually

---

**🎉 Congratulations! You now have enterprise-grade authentication!**

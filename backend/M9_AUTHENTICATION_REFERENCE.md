# M9 Authentication Reference

This document describes the authentication module as it is currently implemented and tested in the `decisio` Conda environment.

## Scope

M9 currently includes:

- JWT login with access and refresh tokens
- refresh-token rotation with blacklist support
- logout and logout-all flows
- role-based access control with `admin`, `analyst`, and `viewer`
- nested profile read/update
- password change with security metadata updates
- password reset request/confirm flow
- personal API tokens for programmatic access
- admin user management endpoints
- failed-login lockout tracking

## Environment

Use the `decisio` environment:

```powershell
conda activate decisio
cd d:\Decisio\backend
```

If `conda run` is unreliable in your shell, use the environment interpreter directly:

```powershell
& "C:\Users\HP 2025\miniconda3\envs\decisio\python.exe" manage.py check
```

## Main Files

- `apps/authentication/models.py`
- `apps/authentication/serializers.py`
- `apps/authentication/views.py`
- `apps/authentication/permissions.py`
- `apps/authentication/authentication.py`
- `apps/authentication/urls.py`
- `apps/authentication/tests.py`
- `test_auth_api.py`
- `decisiobi/settings.py`

## Authentication Modes

### JWT

Use:

```http
Authorization: Bearer <access-token>
```

Configured in `SIMPLE_JWT` with:

- access lifetime: 60 minutes
- refresh lifetime: 7 days
- refresh rotation: enabled
- blacklist after rotation: enabled

### API Token

Use either:

```http
Authorization: Token <raw-api-token>
```

or:

```http
X-API-Token: <raw-api-token>
```

API tokens are hashed in the database and the raw token is only returned once at creation time.

## Roles

- `viewer`: read-only access where allowed
- `analyst`: read/write business data
- `admin`: full application access

Superusers bypass role restrictions.

## Endpoints

### Public

- `POST /api/auth/register/`
- `POST /api/auth/login/`
- `POST /api/auth/token/`
- `POST /api/auth/token/refresh/`
- `POST /api/auth/password-reset/request/`
- `POST /api/auth/password-reset/confirm/`

### Authenticated

- `GET /api/auth/profile/`
- `PUT /api/auth/profile/`
- `POST /api/auth/change-password/`
- `POST /api/auth/logout/`
- `POST /api/auth/logout-all/`
- `GET /api/auth/status/`
- `GET /api/auth/tokens/`
- `POST /api/auth/tokens/`
- `POST /api/auth/tokens/<id>/revoke/`

### Admin only

- `GET /api/auth/admin/users/`
- `GET /api/auth/admin/users/<id>/`
- `PUT /api/auth/admin/users/<id>/`
- `DELETE /api/auth/admin/users/<id>/`
- `POST /api/auth/admin/users/<id>/update-role/`

## Tested Flows

### Automated tests

Run:

```powershell
& "C:\Users\HP 2025\miniconda3\envs\decisio\python.exe" manage.py test apps.authentication
```

Covered scenarios:

- login returns JWT tokens
- API token creation and validation
- invalid token request handling
- nested profile update
- password change metadata updates
- refresh-token blacklist on logout
- failed-login lockout
- password reset flow
- API-token auth access

### Live smoke test

Run the Django server and the script:

```powershell
& "C:\Users\HP 2025\miniconda3\envs\decisio\python.exe" manage.py runserver
& "C:\Users\HP 2025\miniconda3\envs\decisio\python.exe" test_auth_api.py
```

The script currently verifies:

- registration
- login
- profile access
- auth status
- API token creation/listing
- refresh token flow
- logout
- password reset
- login with the reset password

## Security Behavior

### Failed login lockout

- failed attempts are tracked on `UserProfile`
- after 5 failed attempts, the account is locked for 15 minutes
- successful login resets the failure counter

### Password rotation metadata

After password change or password reset:

- `last_password_change` is updated
- `password_expires_at` is set to 90 days from change
- failed-login counters are reset on password reset

### Refresh-token revocation

- rotated refresh tokens are blacklisted
- `POST /api/auth/logout/` blacklists a single refresh token
- `POST /api/auth/logout-all/` blacklists all outstanding refresh tokens for the current user

## Example Requests

### Register

```http
POST /api/auth/register/
Content-Type: application/json

{
  "username": "john",
  "email": "john@example.com",
  "password": "SecurePass123!",
  "password_confirm": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe"
}
```

### Login

```http
POST /api/auth/login/
Content-Type: application/json

{
  "username": "john",
  "password": "SecurePass123!"
}
```

### Create API token

```http
POST /api/auth/tokens/
Authorization: Bearer <access-token>
Content-Type: application/json

{
  "name": "ERP integration",
  "scopes": ["read:data", "write:kpi"],
  "expires_in_days": 30,
  "rate_limit": 1000
}
```

### Reset password

```http
POST /api/auth/password-reset/request/
Content-Type: application/json

{
  "email": "john@example.com"
}
```

The development implementation returns `reset_uid` and `reset_token` directly in the response. In production that should be replaced by email delivery.

## Gaps Remaining

M9 is strong enough for development and integration, but these are still open if you want stricter production hardening:

- email delivery for password reset instead of returning reset tokens in the response
- MFA implementation for the existing profile fields
- endpoint-level throttling or rate limiting
- audit logging of authentication events
- production secret/cookie/HTTPS hardening in deployment settings

## Recommended Next Integration Steps

- apply M9 permissions to M1 through M8 endpoints as they are implemented
- create at least one admin user and one analyst user for real UI testing
- move frontend login and token refresh logic onto these endpoints

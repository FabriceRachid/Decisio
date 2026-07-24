import hashlib

from rest_framework import authentication, exceptions
from django.core.cache import cache
from django.utils import timezone

from apps.authentication.models import AuthToken


class APITokenAuthentication(authentication.BaseAuthentication):
    """
    Authenticate requests with a raw API token.

    Supported headers:
    - Authorization: Token <raw-token>
    - X-API-Token: <raw-token>
    """

    keyword = 'Token'

    def authenticate(self, request):
        raw_token = self._get_raw_token(request)
        if not raw_token:
            return None

        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        token = (
            AuthToken.objects
            .select_related('user', 'user__profile')
            .filter(token_hash=token_hash, is_active=True)
            .first()
        )

        if not token:
            raise exceptions.AuthenticationFailed('Invalid API token')

        if token.is_expired:
            token.revoke('Expired token')
            raise exceptions.AuthenticationFailed('API token has expired')

        user = token.user
        if not user.is_active:
            raise exceptions.AuthenticationFailed('User inactive or deleted')

        if token.ip_whitelist:
            client_ip = self._get_client_ip(request)
            if client_ip not in token.ip_whitelist:
                raise exceptions.AuthenticationFailed('API token not allowed from this IP')

        self._enforce_rate_limit(token)
        token.register_usage()
        request.auth = token
        request.api_token_scopes = token.scopes
        return (user, token)

    def authenticate_header(self, request):
        return self.keyword

    def _get_raw_token(self, request):
        auth = authentication.get_authorization_header(request).split()
        if auth and auth[0].decode().lower() == self.keyword.lower() and len(auth) == 2:
            return auth[1].decode()

        header_token = request.headers.get('X-API-Token')
        if header_token:
            return header_token.strip()

        return None

    def _get_client_ip(self, request):
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def _enforce_rate_limit(self, token):
        """Apply a simple per-token hourly rate limit."""
        if not token.rate_limit:
            return

        current_hour = timezone.now().strftime('%Y%m%d%H')
        cache_key = f'auth_token_rate_limit:{token.id}:{current_hour}'
        current_count = cache.get(cache_key, 0)

        if current_count >= token.rate_limit:
            raise exceptions.AuthenticationFailed('API token rate limit exceeded')

        cache.set(cache_key, current_count + 1, timeout=3600)

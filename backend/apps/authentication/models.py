from datetime import timedelta

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class Organization(models.Model):
    """
    Lightweight tenant/workspace model.
    Each public registration creates one organization and assigns its founder.
    """

    name = models.CharField(max_length=255)
    sector = models.CharField(max_length=120, blank=True, null=True)
    size = models.CharField(max_length=50, blank=True, null=True)
    country = models.CharField(max_length=120, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='organizations_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'auth_organization'
        verbose_name = 'Organization'
        verbose_name_plural = 'Organizations'
        ordering = ['name']


class UserProfile(models.Model):
    """
    Extended user profile that links to Django's built-in User model.
    Stores business-specific information like role, department, etc.
    """
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('analyst', 'Data Analyst'),
        ('viewer', 'Viewer'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')
    department = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    avatar_url = models.URLField(max_length=500, blank=True, null=True)
    is_email_verified = models.BooleanField(default=False)
    last_password_change = models.DateTimeField(null=True, blank=True)
    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret_key = models.CharField(max_length=100, blank=True, null=True)
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    password_expires_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    MAX_FAILED_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15
    
    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

    @property
    def is_locked(self):
        return bool(self.locked_until and self.locked_until > timezone.now())

    def register_failed_login(self):
        """Increment failed login attempts and lock the profile if threshold is reached."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= self.MAX_FAILED_LOGIN_ATTEMPTS:
            self.locked_until = timezone.now() + timedelta(minutes=self.LOCKOUT_DURATION_MINUTES)
        self.save(update_fields=['failed_login_attempts', 'locked_until', 'updated_at'])

    def reset_login_failures(self):
        """Clear lockout state after a successful login."""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save(update_fields=['failed_login_attempts', 'locked_until', 'updated_at'])

    def mark_password_changed(self):
        """Track password rotation metadata."""
        now = timezone.now()
        self.last_password_change = now
        self.password_expires_at = now + timedelta(days=90)
        self.save(update_fields=['last_password_change', 'password_expires_at', 'updated_at'])
    
    class Meta:
        db_table = 'auth_userprofile'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Automatically create/update UserProfile when User is created/updated."""
    if created:
        UserProfile.objects.create(user=instance)
    else:
        # Update profile if user exists
        try:
            instance.profile.save()
        except UserProfile.DoesNotExist:
            UserProfile.objects.create(user=instance)


class AuthToken(models.Model):
    """
    API authentication tokens for programmatic access.
    Supports multiple tokens per user with different scopes and expiration.
    """
    TOKEN_SCOPES = [
        ('read:data', 'Read Data'),
        ('write:data', 'Write Data'),
        ('read:kpi', 'Read KPIs'),
        ('write:kpi', 'Write KPIs'),
        ('admin', 'Full Admin Access'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_tokens')
    token_hash = models.CharField(max_length=64, unique=True)
    token_prefix = models.CharField(max_length=8, help_text="First 8 chars for identification")
    name = models.CharField(max_length=100, help_text="User-friendly name (e.g., 'Mobile App Token')")
    scopes = models.JSONField(default=list, help_text="List of permission scopes")
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    ip_whitelist = models.JSONField(default=list, blank=True, help_text="Allowed IP addresses")
    rate_limit = models.IntegerField(default=1000, help_text="Requests per hour")
    created_by_ip = models.GenericIPAddressField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.TextField(blank=True, null=True)
    usage_count = models.BigIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.token_prefix}...)"

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())

    def revoke(self, reason=''):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.revoked_reason = reason or self.revoked_reason
        self.save(update_fields=['is_active', 'revoked_at', 'revoked_reason'])

    def register_usage(self):
        self.usage_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['usage_count', 'last_used_at'])
    
    class Meta:
        db_table = 'auth_authtoken'
        verbose_name = 'API Token'
        verbose_name_plural = 'API Tokens'
        ordering = ['-created_at']

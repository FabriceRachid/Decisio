"""
Serializers for Authentication Module
Handles user registration, login, profile management, and token operations
"""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from django.contrib.auth.models import User
from apps.authentication.models import UserProfile, AuthToken, Organization
from apps.authentication.notification_models import UserNotification


class UserProfileSerializer(serializers.ModelSerializer):
    """Serialize UserProfile for API responses"""
    
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    organization_id = serializers.IntegerField(source='organization.id', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    organization_logo = serializers.SerializerMethodField()
    organization_brand_color = serializers.CharField(source='organization.brand_color', read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'id', 'role', 'role_display', 'organization_id', 'organization_name',
            'organization_logo', 'organization_brand_color',
            'department', 'phone_number', 'avatar_url', 'timezone', 'language',
            'mfa_enabled', 'is_email_verified', 'last_password_change',
            'failed_login_attempts', 'locked_until', 'password_expires_at'
        ]
        read_only_fields = [
            'id', 'role', 'role_display', 'is_email_verified', 'last_password_change',
            'failed_login_attempts', 'locked_until', 'password_expires_at'
        ]

    def get_organization_logo(self, obj):
        org = obj.organization
        if org and org.logo:
            request = self.context.get('request')
            url = org.logo.url
            if request is not None:
                return request.build_absolute_uri(url)
            return url
        return None


class UserSerializer(serializers.ModelSerializer):
    """Serialize User with nested profile"""
    
    profile = UserProfileSerializer(required=False)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 
            'last_name', 'date_joined', 'last_login', 'profile'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if profile_data:
            profile = instance.profile
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        return instance


class AdminUserProfileSerializer(UserProfileSerializer):
    """Admin variant with writable role field."""

    class Meta(UserProfileSerializer.Meta):
        read_only_fields = [
            'id', 'role_display', 'organization_id', 'organization_name',
            'is_email_verified', 'last_password_change',
            'failed_login_attempts', 'locked_until', 'password_expires_at'
        ]


class OrganizationSerializer(serializers.ModelSerializer):
    """Serialize Organization branding for the current tenant."""

    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'sector', 'size', 'country',
            'logo', 'logo_url', 'brand_color',
        ]

    def get_logo_url(self, obj):
        if obj.logo:
            request = self.context.get('request')
            url = obj.logo.url
            if request is not None:
                return request.build_absolute_uri(url)
            return url
        return None


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serialize user registration data"""
    
    password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})
    company_name = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=255)
    company_sector = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=120)
    company_size = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=50)
    company_country = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=120)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm', 'first_name', 'last_name',
            'company_name', 'company_sector', 'company_size', 'company_country',
        ]
    
    def validate(self, attrs):
        # Check passwords match
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords do not match"})

        # Check username uniqueness
        username = attrs.get('username')
        if username and User.objects.filter(username=username).exists():
            raise serializers.ValidationError({"username": "Username already exists"})
        
        # Check email uniqueness
        email = attrs.get('email')
        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "Email already registered"})

        validate_password(attrs['password'])
        
        return attrs
    
    def create(self, validated_data):
        # Remove password_confirm from data
        validated_data.pop('password_confirm')
        company_name = (validated_data.pop('company_name', '') or '').strip()
        company_sector = (validated_data.pop('company_sector', '') or '').strip()
        company_size = (validated_data.pop('company_size', '') or '').strip()
        company_country = (validated_data.pop('company_country', '') or '').strip()
        
        # Create user
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )

        organization_label = company_name or f"Espace {user.username}"
        organization = Organization.objects.create(
            name=organization_label,
            sector=company_sector or None,
            size=company_size or None,
            country=company_country or None,
            created_by=user,
        )

        user.profile.role = 'admin'
        user.profile.organization = organization
        user.profile.save(update_fields=['role', 'organization', 'updated_at'])
        
        return user


class ChangePasswordSerializer(serializers.Serializer):
    """Serialize password change request"""
    
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(required=True, write_only=True, min_length=8)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "New passwords do not match"})
        validate_password(attrs['new_password'], self.context['request'].user if self.context.get('request') else None)
        return attrs


class AuthTokenSerializer(serializers.ModelSerializer):
    """Serialize API tokens"""
    
    scopes_list = serializers.ListField(source='scopes', read_only=True)
    
    class Meta:
        model = AuthToken
        fields = [
            'id', 'name', 'token_prefix', 'scopes_list',
            'rate_limit', 'created_at', 'expires_at',
            'last_used_at', 'is_active'
        ]
        read_only_fields = ['id', 'token_prefix', 'created_at', 'last_used_at']


class TokenCreateSerializer(serializers.Serializer):
    """Request token creation"""
    
    name = serializers.CharField(required=True, max_length=100)
    scopes = serializers.ListField(
        child=serializers.CharField(),
        default=['read:data']
    )
    expires_in_days = serializers.IntegerField(default=30, min_value=1, max_value=365)
    rate_limit = serializers.IntegerField(default=1000, min_value=1, max_value=100000)

    def validate_scopes(self, value):
        valid_scopes = {scope for scope, _ in AuthToken.TOKEN_SCOPES}
        invalid_scopes = sorted(set(value) - valid_scopes)
        if invalid_scopes:
            raise serializers.ValidationError(f"Invalid scopes: {', '.join(invalid_scopes)}")
        return value


class LogoutSerializer(serializers.Serializer):
    """Payload for logging out and blacklisting a refresh token."""

    refresh_token = serializers.CharField(required=True)


class PasswordResetRequestSerializer(serializers.Serializer):
    """Request a password reset link."""

    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Confirm a password reset with a reset token."""

    uid = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8, write_only=True)
    new_password_confirm = serializers.CharField(required=True, min_length=8, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "New passwords do not match"})
        validate_password(attrs['new_password'])
        return attrs


class AdminUserSerializer(serializers.ModelSerializer):
    """Admin view of user with full details"""
    
    profile = AdminUserProfileSerializer()
    is_superuser = serializers.BooleanField(read_only=True)
    is_staff = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'is_staff', 'is_superuser', 'date_joined',
            'last_login', 'profile'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']
    
    def update(self, instance, validated_data):
        # Handle nested profile update
        profile_data = validated_data.pop('profile', None)
        
        if profile_data:
            profile = instance.profile
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()
        
        return super().update(instance, validated_data)


class AdminUserCreateSerializer(serializers.ModelSerializer):
    """Admin creation serializer for creating team members."""

    password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES, default='viewer')

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name', 'role']

    def validate(self, attrs):
        username = attrs.get('username')
        if username and User.objects.filter(username=username).exists():
            raise serializers.ValidationError({"username": "Username already exists"})

        email = attrs.get('email')
        if email and User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "Email already registered"})

        validate_password(attrs['password'])
        return attrs

    def create(self, validated_data):
        role = validated_data.pop('role', 'viewer')
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data, password=password)
        user._raw_password = password
        user.profile.role = role
        request = self.context.get('request')
        organization = getattr(getattr(request.user, 'profile', None), 'organization', None) if request else None
        user.profile.organization = organization
        user.profile.save(update_fields=['role', 'organization', 'updated_at'])
        return user


class UserNotificationListSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source='notification_type', read_only=True)

    class Meta:
        model = UserNotification
        fields = [
            'id', 'notification_type', 'type', 'title', 'message',
            'progress_percent', 'is_read', 'created_at',
        ]


class UserNotificationDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserNotification
        fields = '__all__'

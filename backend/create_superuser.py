import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'decisiobi.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = 'admin'
email = 'admin@decisiobi.com'
password = 'Decisio2026!'

if User.objects.filter(username=username).exists():
    print(f'User "{username}" already exists, updating password...')
    u = User.objects.get(username=username)
    u.set_password(password)
    u.is_staff = True
    u.is_superuser = True
    u.save()
    print(f'Password updated for "{username}".')
else:
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f'Superuser "{username}" created successfully.')

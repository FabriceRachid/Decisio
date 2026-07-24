"""
Generate a new Django SECRET_KEY
Run this script to get a secure random secret key
"""

from django.core.management.utils import get_random_secret_key

print("=" * 70)
print("🔐 Django Secret Key Generator")
print("=" * 70)
print()

new_key = get_random_secret_key()

print("✅ Here's your new SECRET_KEY:\n")
print("-" * 70)
print(new_key)
print("-" * 70)
print()

print("📝 To use it:")
print("   1. Copy the key above")
print("   2. Open backend\\.env")
print("   3. Replace the SECRET_KEY value:")
print(f"      SECRET_KEY={new_key}")
print()

print("⚠️  IMPORTANT:")
print("   - Keep this key SECRET!")
print("   - Never commit it to version control")
print("   - Use a different key in production")
print("   - If compromised, generate a new one immediately")
print()

print("=" * 70)

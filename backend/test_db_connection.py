"""
Test PostgreSQL Connection Script
Run this to verify your database connection is working
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 50)
print("Testing PostgreSQL Connection")
print("=" * 50)
print()

# Get connection parameters
db_config = {
    'DB_NAME': os.getenv('DB_NAME', 'Not set'),
    'DB_USER': os.getenv('DB_USER', 'Not set'),
    'DB_PASSWORD': os.getenv('DB_PASSWORD', 'Not set'),
    'DB_HOST': os.getenv('DB_HOST', 'Not set'),
    'DB_PORT': os.getenv('DB_PORT', 'Not set'),
}

print("📋 Configuration from .env:")
for key, value in db_config.items():
    if key == 'DB_PASSWORD':
        print(f"   {key}: {'*' * len(value) if value else 'Not set'}")
    else:
        print(f"   {key}: {value}")
print()

try:
    import psycopg2
    print("✅ psycopg2 is installed")
    
    # Try to connect
    print("\n🔌 Attempting to connect to PostgreSQL...")
    conn = psycopg2.connect(
        host=db_config['DB_HOST'],
        port=db_config['DB_PORT'],
        database=db_config['DB_NAME'],
        user=db_config['DB_USER'],
        password=db_config['DB_PASSWORD']
    )
    
    print("✅ SUCCESS! Connected to PostgreSQL!")
    
    # Get database info
    cur = conn.cursor()
    cur.execute("SELECT version();")
    db_version = cur.fetchone()
    print(f"\n📊 Database Version: {db_version[0][:50]}...")
    
    cur.close()
    conn.close()
    
    print("\n🎉 Everything is working perfectly!")
    print("\nNext steps:")
    print("   1. Run: python manage.py migrate")
    print("   2. Run: python manage.py createsuperuser")
    print("   3. Run: python manage.py runserver")
    
except psycopg2.OperationalError as e:
    print("❌ CONNECTION FAILED!")
    print(f"\nError: {e}")
    print("\n💡 Troubleshooting:")
    print("   1. Check if PostgreSQL service is running")
    print("   2. Verify database name exists")
    print("   3. Check username and password")
    print("   4. Ensure host and port are correct")
    print("\nCommon fixes:")
    print("   - Run: net start postgresql-x64-15 (or your version)")
    print("   - Check SETUP_POSTGRESQL.md for setup instructions")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nMake sure you've:")
    print("   1. Installed PostgreSQL")
    print("   2. Created the database and user")
    print("   3. Updated .env with correct credentials")

print("\n" + "=" * 50)

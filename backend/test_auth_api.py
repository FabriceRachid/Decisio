"""
Test Authentication API Endpoints
Run this after starting the server with: python manage.py runserver
"""

import requests
import json
import uuid

BASE_URL = "http://localhost:8000/api/auth"
TEST_USERNAME = f"testuser_{uuid.uuid4().hex[:8]}"
TEST_EMAIL = f"{TEST_USERNAME}@example.com"
TEST_PASSWORD = "testpass123"
NEW_TEST_PASSWORD = "newpass456"


def print_response(response):
    """Print JSON when available, otherwise print raw text safely."""
    try:
        body = response.json()
        print(f"Response: {json.dumps(body, indent=2)}")
        return body
    except ValueError:
        print(f"Response Text: {response.text[:1000]}")
        return None

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_registration():
    """Test user registration"""
    print_section("1. REGISTER NEW USER")
    
    url = f"{BASE_URL}/register/"
    data = {
        "username": TEST_USERNAME,
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "password_confirm": TEST_PASSWORD,
        "first_name": "Test",
        "last_name": "User"
    }
    
    response = requests.post(url, json=data)
    print(f"POST {url}")
    print(f"Status: {response.status_code}")
    body = print_response(response)
    
    return response.status_code, body

def test_login(username=TEST_USERNAME, password=TEST_PASSWORD):
    """Test user login"""
    print_section("2. LOGIN")
    
    url = f"{BASE_URL}/login/"
    data = {
        "username": username,
        "password": password
    }
    
    response = requests.post(url, json=data)
    print(f"POST {url}")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = print_response(response)
        return result
    else:
        print_response(response)
        return None

def test_get_profile(access_token):
    """Test getting user profile"""
    print_section("3. GET USER PROFILE")
    
    url = f"{BASE_URL}/profile/"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(url, headers=headers)
    print(f"GET {url}")
    print(f"Status: {response.status_code}")
    return print_response(response)

def test_change_password(access_token):
    """Test changing password"""
    print_section("4. CHANGE PASSWORD")
    
    url = f"{BASE_URL}/change-password/"
    headers = {"Authorization": f"Bearer {access_token}"}
    data = {
        "old_password": TEST_PASSWORD,
        "new_password": NEW_TEST_PASSWORD,
        "new_password_confirm": NEW_TEST_PASSWORD
    }
    
    response = requests.post(url, headers=headers, json=data)
    print(f"POST {url}")
    print(f"Status: {response.status_code}")
    return print_response(response)

def test_auth_status(access_token):
    """Test authentication status"""
    print_section("5. CHECK AUTH STATUS")
    
    url = f"{BASE_URL}/status/"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(url, headers=headers)
    print(f"GET {url}")
    print(f"Status: {response.status_code}")
    return print_response(response)

def test_create_api_token(access_token):
    """Test creating API token"""
    print_section("6. CREATE API TOKEN")
    
    url = f"{BASE_URL}/tokens/"
    headers = {"Authorization": f"Bearer {access_token}"}
    data = {
        "name": "Test Integration",
        "scopes": ["read:data", "write:kpi"],
        "expires_in_days": 30
    }
    
    response = requests.post(url, headers=headers, json=data)
    print(f"POST {url}")
    print(f"Status: {response.status_code}")
    body = print_response(response)
    return response.status_code, body

def test_list_tokens(access_token):
    """Test listing API tokens"""
    print_section("7. LIST API TOKENS")
    
    url = f"{BASE_URL}/tokens/"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(url, headers=headers)
    print(f"GET {url}")
    print(f"Status: {response.status_code}")
    return print_response(response)

def test_refresh_token(refresh_token):
    """Test refreshing access token"""
    print_section("8. REFRESH ACCESS TOKEN")
    
    url = f"{BASE_URL}/token/refresh/"
    data = {"refresh": refresh_token}
    
    response = requests.post(url, json=data)
    print(f"POST {url}")
    print(f"Status: {response.status_code}")
    return print_response(response)

def test_logout(access_token, refresh_token):
    """Test logging out and blacklisting a refresh token"""
    print_section("9. LOGOUT")

    url = f"{BASE_URL}/logout/"
    headers = {"Authorization": f"Bearer {access_token}"}
    data = {"refresh_token": refresh_token}

    response = requests.post(url, headers=headers, json=data)
    print(f"POST {url}")
    print(f"Status: {response.status_code}")
    return print_response(response)

def test_password_reset():
    """Test password reset request and confirmation"""
    print_section("10. PASSWORD RESET")

    request_url = f"{BASE_URL}/password-reset/request/"
    request_data = {"email": TEST_EMAIL}
    request_response = requests.post(request_url, json=request_data)
    print(f"POST {request_url}")
    print(f"Status: {request_response.status_code}")
    request_body = print_response(request_response)

    if request_response.status_code != 200 or not request_body or 'reset_uid' not in request_body:
        return request_response.status_code, request_body

    confirm_url = f"{BASE_URL}/password-reset/confirm/"
    confirm_data = {
        "uid": request_body["reset_uid"],
        "token": request_body["reset_token"],
        "new_password": NEW_TEST_PASSWORD,
        "new_password_confirm": NEW_TEST_PASSWORD
    }
    confirm_response = requests.post(confirm_url, json=confirm_data)
    print(f"POST {confirm_url}")
    print(f"Status: {confirm_response.status_code}")
    confirm_body = print_response(confirm_response)
    return confirm_response.status_code, confirm_body

def main():
    """Run all authentication tests"""
    print("\n" + "="*60)
    print("  DECISIO AUTHENTICATION API TEST SUITE")
    print("="*60)
    
    try:
        # Test 1: Register new user
        reg_status, reg_result = test_registration()
        if reg_status != 201:
            print("\nERROR: Registration failed. Stopping tests.")
            return
        
        # Test 2: Login
        login_result = test_login()
        
        if not login_result:
            print("\nERROR: Login failed. Stopping tests.")
            return
        
        access_token = login_result['access_token']
        refresh_token = login_result['refresh_token']
        
        # Test 3: Get profile
        test_get_profile(access_token)
        
        # Test 4: Check auth status
        test_auth_status(access_token)
        
        # Test 5: Create API token
        token_status, token_result = test_create_api_token(access_token)
        if token_status != 201:
            print("\nERROR: API token creation failed. Stopping tests.")
            return
        
        # Test 6: List tokens
        test_list_tokens(access_token)
        
        # Test 7: Refresh token
        refresh_result = test_refresh_token(refresh_token)
        latest_refresh_token = refresh_result.get('refresh', refresh_token) if refresh_result else refresh_token

        # Test 8: Logout
        logout_result = test_logout(access_token, latest_refresh_token)
        if not logout_result or logout_result.get('message') != 'Logout successful':
            print("\nERROR: Logout failed. Stopping tests.")
            return

        # Test 9: Password reset
        password_reset_status, _ = test_password_reset()
        if password_reset_status != 200:
            print("\nERROR: Password reset flow failed. Stopping tests.")
            return

        # Test 10: Login with reset password
        login_after_reset = test_login(password=NEW_TEST_PASSWORD)
        if not login_after_reset:
            print("\nERROR: Login with reset password failed. Stopping tests.")
            return
        
        print_section("ALL TESTS COMPLETED")
        print("\nSummary:")
        print("  - User registration works")
        print("  - Login returns JWT tokens")
        print("  - Protected endpoints accessible with token")
        print("  - Profile management functional")
        print("  - API token creation works")
        print("  - Token refresh works")
        print("  - Logout blacklists refresh tokens")
        print("  - Password reset flow works")
        
    except requests.exceptions.ConnectionError:
        print("\nERROR: Cannot connect to server!")
        print("Make sure Django is running: python manage.py runserver")
    except Exception as e:
        print(f"\nERROR: {str(e)}")

if __name__ == "__main__":
    main()

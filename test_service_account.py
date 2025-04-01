#!/usr/bin/env python3
"""
Service Account Authentication Test Script

This script tests authentication with a Google service account for various scopes
to help identify which permissions are properly configured.

Usage:
python test_service_account.py --service-account your-key.json --admin-email admin@domain.com
"""

import os
import sys
import json
import argparse
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.errors import HttpError

def test_scope(credentials, scope_name, api_name, api_version, test_function):
    """Test a specific API scope."""
    print(f"\n----- Testing {scope_name} -----")
    try:
        # Create service with specific credentials
        service = build(api_name, api_version, credentials=credentials)
        
        # Run the test function
        result = test_function(service)
        print(f"✅ SUCCESS: {result}")
        return True
    except HttpError as e:
        print(f"❌ ERROR: {e}")
        return False
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {type(e).__name__}: {e}")
        return False

def test_directory_users(service):
    """Test Directory API users listing."""
    response = service.users().list(domain='primary', maxResults=1).execute()
    users = response.get('users', [])
    return f"Successfully listed {len(users)} users"

def test_drive_about(service):
    """Test Drive API basic access."""
    response = service.about().get(fields="user,kind").execute()
    return f"Successfully accessed Drive API as {response.get('user', {}).get('emailAddress')}"

def test_drive_files(service):
    """Test Drive API files listing."""
    response = service.files().list(pageSize=10, fields="files(id,name)").execute()
    files = response.get('files', [])
    return f"Successfully listed {len(files)} files"

def test_drive_teamdrives(service):
    """Test Drive API team drives listing."""
    try:
        # Try the newer 'drives' method first (v3 API)
        response = service.drives().list(pageSize=10, fields="drives(id,name)").execute()
        drives = response.get('drives', [])
        return f"Successfully listed {len(drives)} shared drives"
    except HttpError as e:
        if "not found" in str(e).lower():
            # Fallback to older teamdrives method
            response = service.teamdrives().list(pageSize=10, fields="teamDrives(id,name)").execute()
            drives = response.get('teamDrives', [])
            return f"Successfully listed {len(drives)} team drives (using legacy endpoint)"
        raise

def get_service_account_info(service_account_file):
    """Get service account information from the key file."""
    with open(service_account_file, 'r') as f:
        data = json.load(f)
    return {
        'client_email': data.get('client_email', 'Unknown'),
        'client_id': data.get('client_id', 'Unknown'),
        'project_id': data.get('project_id', 'Unknown')
    }

def main():
    parser = argparse.ArgumentParser(description='Test Google Service Account Authentication')
    parser.add_argument('--service-account', required=True, help='Path to service account JSON key file')
    parser.add_argument('--admin-email', required=True, help='Admin email for domain-wide delegation')
    args = parser.parse_args()
    
    # Get service account info
    sa_info = get_service_account_info(args.service_account)
    
    print("===== SERVICE ACCOUNT AUTHENTICATION TEST =====")
    print(f"Service Account: {sa_info['client_email']}")
    print(f"Client ID: {sa_info['client_id']}")
    print(f"Project ID: {sa_info['project_id']}")
    print(f"Admin Email: {args.admin_email}")
    print("==============================================")
    
    # Define the scopes to test
    test_scenarios = [
        {
            'name': "Admin Directory API (Users)",
            'scope': 'https://www.googleapis.com/auth/admin.directory.user.readonly',
            'api_name': 'admin',
            'api_version': 'directory_v1',
            'test_func': test_directory_users
        },
        {
            'name': "Drive API Basic Access",
            'scope': 'https://www.googleapis.com/auth/drive.metadata.readonly',
            'api_name': 'drive',
            'api_version': 'v3',
            'test_func': test_drive_about
        },
        {
            'name': "Drive API Files",
            'scope': 'https://www.googleapis.com/auth/drive.readonly',
            'api_name': 'drive',
            'api_version': 'v3',
            'test_func': test_drive_files
        },
        {
            'name': "Drive API Shared Drives",
            'scope': 'https://www.googleapis.com/auth/drive',
            'api_name': 'drive',
            'api_version': 'v3',
            'test_func': test_drive_teamdrives
        }
    ]
    
    # Run tests for each scope independently
    results = {}
    for scenario in test_scenarios:
        try:
            # Create credentials for just this scope
            creds = service_account.Credentials.from_service_account_file(
                args.service_account, 
                scopes=[scenario['scope']]
            )
            creds = creds.with_subject(args.admin_email)
            
            # Test the scope
            success = test_scope(
                creds, 
                scenario['name'], 
                scenario['api_name'], 
                scenario['api_version'], 
                scenario['test_func']
            )
            results[scenario['name']] = success
        except Exception as e:
            print(f"❌ ERROR setting up credentials: {e}")
            results[scenario['name']] = False
    
    # Summary
    print("\n===== TEST SUMMARY =====")
    all_success = True
    for name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
        if not success:
            all_success = False
    
    print("\n===== TROUBLESHOOTING GUIDANCE =====")
    if not all_success:
        print("Some tests failed. Check the following:")
        print("1. In Google Admin Console (admin.google.com):")
        print("   - Navigate to: Security > API Controls > Domain-wide Delegation")
        print("   - Ensure this client ID is listed:", sa_info['client_id'])
        print("   - Ensure ALL these scopes are added (copy the entire line):")
        print("     https://www.googleapis.com/auth/admin.directory.user.readonly,https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/drive.metadata.readonly")
        print("2. In Google Cloud Console (console.cloud.google.com):")
        print("   - Navigate to: IAM & Admin > Service Accounts")
        print("   - Ensure the service account is enabled")
        print("   - Navigate to: APIs & Services > Dashboard")
        print("   - Ensure 'Google Drive API' and 'Admin SDK' are enabled")
        print("3. In Domain Settings:")
        print("   - Ensure Shared Drives are enabled for your organization")
    else:
        print("All tests passed! Your service account is correctly configured.")
        print("If you're still having issues with Shared Drives, it's possible that:")
        print("1. There are no Shared Drives in your organization")
        print("2. The admin user doesn't have access to any Shared Drives")
        print("3. There might be organizational policies restricting access")

if __name__ == '__main__':
    main()
#!/usr/bin/env python3
"""
Alternative Google Shared Drives Lister

This simpler script attempts to list Shared Drives using a different approach.
It can help diagnose issues with Shared Drive access.

Usage:
python list_shared_drives.py 
    --service-account /path/to/service-account.json 
    --admin-email admin@yourdomain.com
"""

import os
import json
import argparse
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.errors import HttpError

def main():
    parser = argparse.ArgumentParser(description='Alternative Google Shared Drives Lister')
    parser.add_argument('--service-account', required=True, help='Path to service account JSON file')
    parser.add_argument('--admin-email', required=True, help='Admin email for domain-wide delegation')
    parser.add_argument('--output-file', default='shared_drives_list.json', help='Output JSON file path')
    
    args = parser.parse_args()
    
    # Initialize and authenticate
    try:
        # Use more scopes to ensure we have sufficient permissions
        scopes = [
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        
        # Authenticate with service account
        creds = service_account.Credentials.from_service_account_file(
            args.service_account, scopes=scopes)
        creds = creds.with_subject(args.admin_email)
        
        print(f"Authenticated as {args.admin_email}")
        print(f"Service account: {creds.service_account_email}")
        
        # Build the Drive API service
        drive_service = build('drive', 'v3', credentials=creds)
        
        # Test API access
        print("\nTesting Drive API access...")
        about = drive_service.about().get(fields="user,storageQuota").execute()
        print(f"Successfully authenticated as: {about.get('user', {}).get('emailAddress')}")
        print(f"Drive storage quota: {about.get('storageQuota', {}).get('limit', 'Unknown')} bytes")
        
        # Try to list Shared Drives
        print("\nAttempting to list Shared Drives (using drives().list API)...")
        try:
            response = drive_service.drives().list(pageSize=100, fields="nextPageToken, drives(id, name)").execute()
            drives = response.get('drives', [])
            
            if drives:
                print(f"SUCCESS! Found {len(drives)} Shared Drives:")
                for drive in drives:
                    print(f" - {drive.get('name')} (ID: {drive.get('id')})")
            else:
                print("No Shared Drives found using the drives().list API method.")
            
            # Save the results
            with open(args.output_file, 'w') as f:
                json.dump(response, f, indent=2)
                print(f"Saved results to {args.output_file}")
            
        except HttpError as e:
            print(f"ERROR accessing Shared Drives: {e}")
        
        # Alternative approach: Try using files().list with special parameters
        print("\nTrying alternative approach to find Shared Drives...")
        try:
            # This API call searches for special "drive" type files
            response = drive_service.files().list(
                q="mimeType='application/vnd.google-apps.folder' and 'me' in owners",
                spaces='drive',
                fields="files(id, name, mimeType, driveId, parents)"
            ).execute()
            
            files = response.get('files', [])
            print(f"Found {len(files)} top-level folders that may be in Shared Drives")
            
            # Identify unique driveIds, which correspond to Shared Drives
            drive_ids = set()
            for file in files:
                if 'driveId' in file:
                    drive_ids.add(file['driveId'])
            
            print(f"Found {len(drive_ids)} possible unique Shared Drive IDs")
            
            # Try to get details for each driveId
            if drive_ids:
                print("\nAttempting to get details for each Shared Drive:")
                for drive_id in drive_ids:
                    try:
                        # Get drive details
                        drive = drive_service.drives().get(driveId=drive_id, fields="id, name").execute()
                        print(f" - {drive.get('name')} (ID: {drive.get('id')})")
                    except HttpError as e:
                        print(f" - Error getting drive with ID {drive_id}: {e}")
            
        except HttpError as e:
            print(f"ERROR with alternative approach: {e}")
        
        # Additional diagnostics
        print("\nDIAGNOSTICS:")
        print("1. Verify in the Google Admin Console (admin.google.com):")
        print("   - API controls > Domain-wide delegation > Ensure service account is listed")
        print("   - API controls > Domain-wide delegation > Ensure proper scopes are authorized:")
        print("     * https://www.googleapis.com/auth/drive")
        print("     * https://www.googleapis.com/auth/drive.readonly")
        print("2. Verify that Shared Drives exist in your organization")
        print("3. Verify that the admin email has access to Shared Drives")
        print("4. In Google Cloud Console, ensure the service account has Drive API enabled")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
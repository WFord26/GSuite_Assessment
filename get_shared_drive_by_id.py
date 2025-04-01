#!/usr/bin/env python3
"""
Retrieve Google Shared Drive by ID

This script attempts to retrieve a specific Shared Drive using its ID.
This can help confirm if access to Shared Drives is working correctly.

Usage:
python get_shared_drive_by_id.py --service-account your-key.json --admin-email admin@domain.com --drive-id DRIVE_ID
"""

import json
import argparse
import sys
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.errors import HttpError

def main():
    parser = argparse.ArgumentParser(description='Retrieve Google Shared Drive by ID')
    parser.add_argument('--service-account', required=True, help='Path to service account JSON key file')
    parser.add_argument('--admin-email', required=True, help='Admin email for domain-wide delegation')
    parser.add_argument('--drive-id', required=True, help='ID of the Shared Drive to retrieve')
    args = parser.parse_args()
    
    # Authenticate with service account
    try:
        # Required scopes for Shared Drives access
        scopes = [
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        
        creds = service_account.Credentials.from_service_account_file(
            args.service_account, scopes=scopes)
        creds = creds.with_subject(args.admin_email)
        
        # Build the Drive API service
        drive_service = build('drive', 'v3', credentials=creds)
        
        print(f"Attempting to retrieve Shared Drive with ID: {args.drive_id}")
        
        # Try to get the Shared Drive by ID
        try:
            drive = drive_service.drives().get(
                driveId=args.drive_id, 
                fields="id,name,createdTime,hidden,restrictions,themeId,backgroundImageFile"
            ).execute()
            
            print("\n✅ SUCCESS! Retrieved Shared Drive details:")
            print(f"Name: {drive.get('name', 'Unknown')}")
            print(f"ID: {drive.get('id', 'Unknown')}")
            print(f"Created: {drive.get('createdTime', 'Unknown')}")
            
            if 'hidden' in drive:
                print(f"Hidden: {drive.get('hidden')}")
            
            if 'restrictions' in drive:
                print("Restrictions:")
                for k, v in drive.get('restrictions', {}).items():
                    print(f"  - {k}: {v}")
            
            # Now list the contents of this Shared Drive
            print("\nAttempting to list files in this Shared Drive...")
            results = drive_service.files().list(
                corpora="drive",
                driveId=args.drive_id,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                fields="files(id,name,mimeType,owners),nextPageToken"
            ).execute()
            
            files = results.get('files', [])
            if files:
                print(f"\n✅ SUCCESS! Found {len(files)} files in this Shared Drive:")
                for i, file in enumerate(files[:10], 1):  # Show first 10 files
                    owner = file.get('owners', [{}])[0].get('displayName', 'Unknown') if 'owners' in file else 'Unknown'
                    print(f"{i}. {file.get('name')} ({file.get('mimeType')}) - Owner: {owner}")
                
                if len(files) > 10:
                    print(f"...and {len(files) - 10} more files")
            else:
                print("\nNo files found in this Shared Drive")
        
        except HttpError as e:
            print(f"\n❌ ERROR: Could not retrieve Shared Drive with ID {args.drive_id}")
            print(f"Error details: {e}")
            
            if e.resp.status == 404:
                print("\nThis Shared Drive doesn't exist or the admin doesn't have access to it.")
                print("Possible reasons:")
                print("1. The Drive ID is incorrect")
                print("2. The Drive has been deleted")
                print("3. The admin user doesn't have access to this Drive")
                
            elif e.resp.status == 403:
                print("\nPermission denied to access this Shared Drive.")
                print("Possible reasons:")
                print("1. The service account doesn't have sufficient permissions")
                print("2. The admin user doesn't have access to this Drive")
                
            else:
                print("\nCheck if the Drive API is enabled and the service account is properly configured.")
            
            print("\nTrying to list all Shared Drives to find valid IDs...")
            try:
                response = drive_service.drives().list(
                    pageSize=50,
                    fields="drives(id,name)"
                ).execute()
                
                drives = response.get('drives', [])
                if drives:
                    print(f"\n✅ SUCCESS! Found {len(drives)} Shared Drives:")
                    for drive in drives:
                        print(f"- {drive.get('name')} (ID: {drive.get('id')})")
                else:
                    print("\nNo Shared Drives found in your organization.")
            except HttpError as list_error:
                print(f"\nCould not list Shared Drives: {list_error}")
    
    except Exception as e:
        print(f"Unexpected error: {type(e).__name__}: {e}")
        raise

if __name__ == '__main__':
    main()
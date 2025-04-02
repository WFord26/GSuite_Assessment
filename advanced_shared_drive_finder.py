#!/usr/bin/env python3
"""
Advanced Shared Drive Finder

This script uses multiple methods to attempt to locate Shared Drives in your organization,
including direct API calls, Admin SDK reports, and file metadata analysis.

Usage:
python advanced_shared_drive_finder.py 
    --service-account /path/to/service-account.json 
    --admin-email admin@yourdomain.com
    [--deep-search]
"""

import os
import json
import argparse
import time
import datetime
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.errors import HttpError

def print_section(title):
    """Print a section header for clarity."""
    print("\n" + "="*30)
    print(f"  {title}")
    print("="*30)

def test_api_access(service):
    """Test basic API connectivity."""
    try:
        about = service.about().get(fields="user,kind,storageQuota").execute()
        user_email = about.get('user', {}).get('emailAddress', 'Unknown')
        quota = about.get('storageQuota', {})
        quota_limit = quota.get('limit', 'Unknown')
        quota_usage = quota.get('usage', 'Unknown')
        
        print(f"✅ Successfully authenticated as: {user_email}")
        print(f"Drive storage quota: {int(quota_limit) / (1024**3):.2f} GB")
        print(f"Drive storage usage: {int(quota_usage) / (1024**3):.2f} GB")
        return True
    except Exception as e:
        print(f"❌ Error accessing Drive API: {e}")
        return False

def get_shared_drives_standard(drive_service):
    """Try to retrieve Shared Drives using the standard drives().list method."""
    print_section("METHOD 1: Standard Drives API")
    shared_drives = []
    page_token = None
    
    try:
        print("Attempting to list Shared Drives using drives().list API...")
        while True:
            try:
                results = drive_service.drives().list(
                    pageSize=100,
                    pageToken=page_token,
                    fields="nextPageToken, drives(id, name, createdTime, hidden)"
                ).execute()
                
                current_drives = results.get('drives', [])
                if current_drives:
                    shared_drives.extend(current_drives)
                    print(f"  Retrieved {len(current_drives)} drives in current page")
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
            
            except HttpError as e:
                print(f"  ❌ Error during retrieval: {e}")
                print("  Trying alternative parameters...")
                
                # Try with useDomainAdminAccess flag
                try:
                    results = drive_service.drives().list(
                        pageSize=100,
                        pageToken=page_token,
                        useDomainAdminAccess=True,
                        fields="nextPageToken, drives(id, name, createdTime)"
                    ).execute()
                    
                    current_drives = results.get('drives', [])
                    if current_drives:
                        shared_drives.extend(current_drives)
                        print(f"  Retrieved {len(current_drives)} drives using useDomainAdminAccess")
                    
                    page_token = results.get('nextPageToken')
                    if not page_token:
                        break
                    
                except HttpError as e2:
                    print(f"  ❌ Alternative parameters also failed: {e2}")
                    break
        
        if shared_drives:
            print(f"✅ SUCCESS! Found {len(shared_drives)} Shared Drives with standard method")
        else:
            print("❌ No Shared Drives found with standard method")
        
        return shared_drives
        
    except Exception as e:
        print(f"❌ Error listing Shared Drives: {e}")
        return []

def get_shared_drives_using_files(drive_service):
    """Try to find Shared Drives by looking for files in shared drives."""
    print_section("METHOD 2: Files in Shared Drives")
    
    try:
        print("Searching for files located in Shared Drives...")
        response = drive_service.files().list(
            # This query includes any file in a Shared Drive
            q="sharedWithMe=true or trashed=false",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
            fields="files(id,name,driveId,parents)",
            pageSize=1000
        ).execute()
        
        files = response.get('files', [])
        print(f"Found {len(files)} files in total")
        
        # Extract unique drive IDs
        drive_ids = {}
        for file in files:
            if 'driveId' in file:
                drive_id = file['driveId']
                if drive_id not in drive_ids:
                    drive_ids[drive_id] = file.get('name', 'Unknown file')
        
        print(f"Identified {len(drive_ids)} unique drive IDs from file metadata")
        
        # Try to get drive information for each ID
        shared_drives = []
        for drive_id, sample_filename in drive_ids.items():
            try:
                drive = drive_service.drives().get(
                    driveId=drive_id,
                    fields="id,name,createdTime"
                ).execute()
                shared_drives.append(drive)
                print(f"  Found Shared Drive: {drive.get('name')} (ID: {drive.get('id')})")
            except HttpError as e:
                print(f"  Could not retrieve drive with ID {drive_id} (from file: {sample_filename}): {e}")
        
        if shared_drives:
            print(f"✅ SUCCESS! Found {len(shared_drives)} Shared Drives through file analysis")
        else:
            print("❌ No Shared Drives found through file analysis")
        
        return shared_drives
    
    except Exception as e:
        print(f"❌ Error searching for files: {e}")
        return []

def get_shared_drives_admin_reports(admin_service):
    """Try to get Shared Drives information through Admin SDK reports."""
    print_section("METHOD 3: Admin SDK Reports")
    
    try:
        # Get a date 7 days ago to ensure we have data
        date = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        
        print(f"Requesting Drive activity report for date {date}...")
        results = admin_service.activities().list(
            userKey='all',
            applicationName='drive',
            maxResults=1000,
            actorIpAddress='all',
            startTime=date
        ).execute()
        
        activities = results.get('items', [])
        print(f"Found {len(activities)} Drive activities")
        
        # Look for activities related to Shared Drives
        drive_ids = {}
        for activity in activities:
            events = activity.get('events', [])
            for event in events:
                # Check if the event is related to team drives or shared drives
                parameters = event.get('parameters', [])
                for param in parameters:
                    name = param.get('name', '')
                    value = param.get('value', '')
                    
                    # Look for parameters that might contain Shared Drive IDs
                    if name in ['teamDriveId', 'teamDriveTitle', 'driveId', 'driveTitle']:
                        if value and value != 'null':
                            if name in ['teamDriveId', 'driveId']:
                                drive_ids[value] = drive_ids.get(value, 'Unknown')
                            else:  # Title parameters
                                # Find the corresponding ID parameter
                                for id_param in parameters:
                                    id_name = id_param.get('name', '')
                                    id_value = id_param.get('value', '')
                                    if id_name in ['teamDriveId', 'driveId'] and id_value:
                                        drive_ids[id_value] = value
        
        print(f"Extracted {len(drive_ids)} potential Shared Drive IDs from activity reports")
        
        # Now try to get drive details
        shared_drives = []
        drive_service = build('drive', 'v3', credentials=admin_service._http.credentials)
        
        for drive_id, name in drive_ids.items():
            try:
                drive = drive_service.drives().get(
                    driveId=drive_id,
                    fields="id,name,createdTime"
                ).execute()
                shared_drives.append(drive)
                print(f"  Found Shared Drive: {drive.get('name')} (ID: {drive.get('id')})")
            except HttpError as e:
                print(f"  Could not retrieve drive with ID {drive_id} (reported name: {name}): {e}")
        
        if shared_drives:
            print(f"✅ SUCCESS! Found {len(shared_drives)} Shared Drives through Admin reports")
        else:
            print("❌ No Shared Drives found through Admin reports")
        
        return shared_drives
    
    except Exception as e:
        print(f"❌ Error accessing Admin Reports: {e}")
        if "Request had insufficient authentication scopes" in str(e):
            print("  Admin SDK Reports require additional scopes. Add 'https://www.googleapis.com/auth/admin.reports.audit.readonly'")
        return []

def deep_search_for_files(drive_service):
    """Aggressively search for any files that might be in Shared Drives."""
    print_section("METHOD 4: Deep File Search")
    
    try:
        print("Performing deep search for files that could reveal Shared Drives...")
        # Try multiple search strategies
        search_strategies = [
            # Try to find any files in team drives
            {
                "name": "Files in any Shared Drive",
                "query": "driveId!=null"
            },
            # Files shared with the user
            {
                "name": "Files shared with you",
                "query": "sharedWithMe=true"
            },
            # Look for folders (often at the root of Shared Drives)
            {
                "name": "Folders",
                "query": "mimeType='application/vnd.google-apps.folder'"
            }
        ]
        
        drive_ids = {}
        
        for strategy in search_strategies:
            print(f"\nTrying search strategy: {strategy['name']}")
            try:
                response = drive_service.files().list(
                    q=strategy['query'],
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                    fields="files(id,name,driveId,mimeType)",
                    pageSize=1000
                ).execute()
                
                files = response.get('files', [])
                print(f"  Found {len(files)} files/folders")
                
                # Extract drive IDs
                for file in files:
                    if 'driveId' in file:
                        drive_id = file['driveId']
                        if drive_id not in drive_ids:
                            drive_ids[drive_id] = file.get('name', 'Unknown file')
                
                print(f"  Identified {len(drive_ids)} unique drive IDs so far")
                
            except HttpError as e:
                print(f"  ❌ Error with search strategy '{strategy['name']}': {e}")
        
        # Try to get drive information for each ID
        shared_drives = []
        for drive_id, sample_filename in drive_ids.items():
            try:
                drive = drive_service.drives().get(
                    driveId=drive_id,
                    fields="id,name,createdTime"
                ).execute()
                shared_drives.append(drive)
                print(f"  Found Shared Drive: {drive.get('name')} (ID: {drive.get('id')})")
            except HttpError as e:
                print(f"  Could not retrieve drive with ID {drive_id} (from file: {sample_filename}): {e}")
        
        if shared_drives:
            print(f"✅ SUCCESS! Found {len(shared_drives)} Shared Drives through deep search")
        else:
            print("❌ No Shared Drives found through deep search")
        
        return shared_drives
    
    except Exception as e:
        print(f"❌ Error in deep search: {e}")
        return []

def get_service_account_details(service_account_file):
    """Extract details from the service account key file."""
    try:
        with open(service_account_file, 'r') as f:
            data = json.load(f)
        
        return {
            'client_id': data.get('client_id', 'Unknown'),
            'client_email': data.get('client_email', 'Unknown'),
            'project_id': data.get('project_id', 'Unknown')
        }
    except Exception as e:
        print(f"Error reading service account file: {e}")
        return {
            'client_id': 'Unknown',
            'client_email': 'Unknown',
            'project_id': 'Unknown'
        }

def main():
    parser = argparse.ArgumentParser(description='Advanced Shared Drive Finder')
    parser.add_argument('--service-account', required=True, help='Path to service account JSON key file')
    parser.add_argument('--admin-email', required=True, help='Admin email for domain-wide delegation')
    parser.add_argument('--deep-search', action='store_true', help='Enable deep searching techniques (slower)')
    parser.add_argument('--output-file', default='found_shared_drives.json', help='Output file for results')
    
    args = parser.parse_args()
    
    # Get service account details
    sa_details = get_service_account_details(args.service_account)
    
    print_section("CONFIGURATION")
    print(f"Service Account: {sa_details['client_email']}")
    print(f"Client ID: {sa_details['client_id']}")
    print(f"Project ID: {sa_details['project_id']}")
    print(f"Admin Email: {args.admin_email}")
    print(f"Deep Search: {args.deep_search}")
    
    try:
        # Set up authentication with broader scopes
        scopes = [
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/drive.readonly',
            'https://www.googleapis.com/auth/admin.reports.audit.readonly',
            'https://www.googleapis.com/auth/admin.reports.usage.readonly'
        ]
        
        creds = service_account.Credentials.from_service_account_file(
            args.service_account, scopes=scopes)
        creds = creds.with_subject(args.admin_email)
        
        # Build API services
        drive_service = build('drive', 'v3', credentials=creds)
        admin_service = build('admin', 'reports_v1', credentials=creds)
        
        # Test API access
        if not test_api_access(drive_service):
            print("Unable to access Drive API. Please check your credentials and permissions.")
            return
        
        # Track all found drives
        all_drives = {}
        
        # Method 1: Standard API
        drives1 = get_shared_drives_standard(drive_service)
        for drive in drives1:
            drive_id = drive.get('id')
            if drive_id and drive_id not in all_drives:
                all_drives[drive_id] = drive
        
        # Method 2: Find files in Shared Drives
        drives2 = get_shared_drives_using_files(drive_service)
        for drive in drives2:
            drive_id = drive.get('id')
            if drive_id and drive_id not in all_drives:
                all_drives[drive_id] = drive
        
        # Method 3: Admin Reports
        try:
            drives3 = get_shared_drives_admin_reports(admin_service)
            for drive in drives3:
                drive_id = drive.get('id')
                if drive_id and drive_id not in all_drives:
                    all_drives[drive_id] = drive
        except Exception as e:
            print(f"Admin Reports method failed: {e}")
        
        # Method 4: Deep search (optional)
        if args.deep_search:
            drives4 = deep_search_for_files(drive_service)
            for drive in drives4:
                drive_id = drive.get('id')
                if drive_id and drive_id not in all_drives:
                    all_drives[drive_id] = drive
        
        # Final results
        print_section("FINAL RESULTS")
        
        if all_drives:
            print(f"TOTAL SHARED DRIVES FOUND: {len(all_drives)}")
            
            # Convert to list for output
            drives_list = list(all_drives.values())
            
            # Sort by name for easier viewing
            drives_list.sort(key=lambda x: x.get('name', '').lower())
            
            # Save to output file
            with open(args.output_file, 'w') as f:
                json.dump(drives_list, f, indent=2)
            
            print(f"Saved results to {args.output_file}")
            
            # Display first few drives
            print("\nFirst 10 Shared Drives found:")
            for i, drive in enumerate(drives_list[:10], 1):
                print(f"{i}. {drive.get('name')} (ID: {drive.get('id')})")
            
            if len(drives_list) > 10:
                print(f"...and {len(drives_list) - 10} more (see output file for complete list)")
        else:
            print("❌ No Shared Drives found with any method.")
            print("\nPossible reasons:")
            print("1. There are genuinely no Shared Drives in your organization")
            print("2. Your admin account doesn't have access to see them")
            print("3. API access to Shared Drives might be restricted by policies")
            print("4. There may be organization unit restrictions preventing visibility")
            
            # Additional diagnostic information
            print("\nTroubleshooting suggestions:")
            print("1. Check if you can see Shared Drives in web interface (drive.google.com)")
            print("2. Ensure the admin account is a super administrator with access to all organization units")
            print("3. Check Google Workspace Admin console for any API restrictions")
            print("4. Try creating a test Shared Drive in the web interface, then run this script again")
            print("5. Contact Google Workspace support if the issue persists")
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
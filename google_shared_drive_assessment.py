#!/usr/bin/env python3
"""
Google Shared Drives Exporter

This script exports information about Google Shared Drives (Team Drives) in a Google Workspace tenant,
including basic Shared Drive details and their permissions/members.

Requirements:
- Python 3.7+
- google-api-python-client
- google-auth
- pandas

Usage:
python google_shared_drives_exporter.py 
    --service-account /path/to/service-account.json 
    --admin-email admin@yourdomain.com 
    --output-dir workspace_exports
"""

import os
import json
import argparse
import time
from typing import Dict, Any, List, Tuple

import pandas as pd
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.errors import HttpError

class SharedDrivesExporter:
    def __init__(self, service_account_file: str, 
                 admin_email: str, output_dir: str = 'workspace_exports'):
        """
        Initialize Google Shared Drives Exporter.
        
        Args:
            service_account_file: Service account credentials file path
            admin_email: Admin email for domain-wide delegation
            output_dir: Directory to save exported data
        """
        self.service_account_file = service_account_file
        self.admin_email = admin_email
        self.output_dir = output_dir
        self.raw_data_dir = os.path.join(output_dir, "raw_data")
        self.creds = None
        self.drive_service = None
        
        # Create output directories
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(self.raw_data_dir, exist_ok=True)
    
    def authenticate(self):
        """Authenticate with Google Drive API."""
        try:
            # Required scopes for Shared Drives access - include more permissive scopes
            scopes = [
                'https://www.googleapis.com/auth/drive',
                'https://www.googleapis.com/auth/drive.readonly',
                'https://www.googleapis.com/auth/drive.metadata.readonly',
                # Adding admin SDK scope which may be needed for domain-wide operations
                'https://www.googleapis.com/auth/admin.directory.domain.readonly'
            ]
            
            self.creds = service_account.Credentials.from_service_account_file(
                self.service_account_file, scopes=scopes)
            self.creds = self.creds.with_subject(self.admin_email)
            print(f"Authenticated as {self.admin_email} using service account")
            print(f"Service account: {self.creds.service_account_email}")
            print(f"Scopes: {', '.join(self.creds.scopes)}")
        except Exception as e:
            print(f"Authentication error: {e}")
            raise
    
    def initialize_service(self):
        """Initialize Google Drive API service."""
        try:
            self.drive_service = build('drive', 'v3', credentials=self.creds)
            print("Drive service initialized successfully")
        except Exception as e:
            print(f"Error initializing Drive service: {e}")
            raise
    
    def export_shared_drives(self):
        """
        Export all Shared Drives in the organization to a CSV file.
        
        Returns:
            Tuple containing DataFrame with Shared Drives data and path to the CSV file
        """
        print("\nExporting Shared Drives...")
        shared_drives = []
        page_token = None
        
        # First test a basic API call to verify credentials and access
        try:
            print("Testing API access first...")
            about = self.drive_service.about().get(fields="user,storageQuota").execute()
            print(f"Successfully authenticated as: {about.get('user', {}).get('emailAddress')}")
            print(f"Drive storage quota: {about.get('storageQuota', {}).get('limit', 'Unknown')} bytes")
        except Exception as e:
            print(f"ERROR: Failed to access Drive API: {e}")
            print("This may indicate permission issues with the service account.")
            print("Please verify that:")
            print("1. The service account has domain-wide delegation enabled")
            print("2. In the Google Admin console, the API scopes have been authorized:")
            print("   - https://www.googleapis.com/auth/drive")
            print("   - https://www.googleapis.com/auth/drive.readonly")
            raise
        
        try:
            # Try using useDomainAdminAccess=True which may be needed for admin operations
            print("Attempting to list Shared Drives...")
            while True:
                try:
                    results = self.drive_service.drives().list(
                        pageSize=100,
                        pageToken=page_token,
                        useDomainAdminAccess=True,
                        fields="nextPageToken, drives(id, name, createdTime, hidden, restrictions)"
                    ).execute()
                    
                    current_drives = results.get('drives', [])
                    print(f"API returned {len(current_drives)} drives in current page")
                    
                    if not current_drives:
                        if page_token is None:
                            print("WARNING: No shared drives found. This could mean:")
                            print("- There are genuinely no Shared Drives in this domain")
                            print("- The authenticated user doesn't have access to see Shared Drives")
                            print("- There may be an issue with the API permissions")
                        break
                    
                    shared_drives.extend(current_drives)
                    print(f"Retrieved {len(shared_drives)} shared drives so far...")
                    
                    page_token = results.get('nextPageToken')
                    if not page_token:
                        break
                    
                except HttpError as e:
                    if "useDomainAdminAccess" in str(e) and e.resp.status == 400:
                        print("WARNING: useDomainAdminAccess parameter not supported, retrying without it...")
                        # Try again without the useDomainAdminAccess parameter
                        results = self.drive_service.drives().list(
                            pageSize=100,
                            pageToken=page_token,
                            fields="nextPageToken, drives(id, name, createdTime, hidden, restrictions)"
                        ).execute()
                        
                        current_drives = results.get('drives', [])
                        if not current_drives:
                            break
                        
                        shared_drives.extend(current_drives)
                        print(f"Retrieved {len(shared_drives)} shared drives so far...")
                        
                        page_token = results.get('nextPageToken')
                        if not page_token:
                            break
                    else:
                        print(f"ERROR in API call: {e}")
                        raise
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
            
            # Save the raw data
            with open(os.path.join(self.raw_data_dir, 'shared_drives_raw.json'), 'w') as f:
                json.dump(shared_drives, f, indent=2)
            
            # Prepare data for CSV export
            shared_drives_data = []
            for drive in shared_drives:
                # Extract and format restrictions
                restrictions = drive.get('restrictions', {})
                restrictions_str = '; '.join([f"{k}: {v}" for k, v in restrictions.items()])
                
                drive_data = {
                    'Drive ID': drive.get('id', ''),
                    'Drive Name': drive.get('name', ''),
                    'Created Time': drive.get('createdTime', ''),
                    'Hidden': drive.get('hidden', False),
                    'Restrictions': restrictions_str
                }
                shared_drives_data.append(drive_data)
            
            # Create DataFrame and export to CSV
            df = pd.DataFrame(shared_drives_data)
            csv_path = os.path.join(self.output_dir, 'shared_drives_export.csv')
            df.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"Exported {len(shared_drives_data)} shared drives to {csv_path}")
            
            return df, csv_path
            
        except Exception as e:
            print(f"Error exporting shared drives: {e}")
            return pd.DataFrame(), ""
    
    def export_shared_drive_permissions(self, drives_df=None):
        """
        Export all permissions for each Shared Drive to a CSV file.
        
        Args:
            drives_df: Optional DataFrame with drives data from export_shared_drives().
                       If not provided, will fetch drives first.
        
        Returns:
            Tuple containing DataFrame with permissions data and path to the CSV file
        """
        print("\nExporting Shared Drive permissions...")
        
        # If drives_df not provided, fetch drives first
        if drives_df is None or drives_df.empty:
            drives_df, _ = self.export_shared_drives()
        
        if drives_df.empty:
            print("No shared drives available to export permissions for.")
            return pd.DataFrame(), ""
        
        all_permissions = []
        
        # For progress tracking
        total_drives = len(drives_df)
        processed = 0
        
        try:
            for _, drive in drives_df.iterrows():
                drive_id = drive['Drive ID']
                drive_name = drive['Drive Name']
                
                processed += 1
                if processed % 5 == 0 or processed == total_drives:
                    print(f"Processing shared drive {processed}/{total_drives}: {drive_name}")
                
                # Get all permissions for this drive
                permissions = []
                page_token = None
                
                while True:
                    try:
                        results = self.drive_service.permissions().list(
                            fileId=drive_id,
                            supportsAllDrives=True,
                            fields="nextPageToken, permissions(id, type, emailAddress, role, displayName, domain, expirationTime, deleted, pendingOwner)",
                            pageToken=page_token
                        ).execute()
                        
                        current_permissions = results.get('permissions', [])
                        if not current_permissions:
                            break
                        
                        permissions.extend(current_permissions)
                        
                        page_token = results.get('nextPageToken')
                        if not page_token:
                            break
                        
                    except HttpError as e:
                        print(f"Error fetching permissions for drive {drive_name} ({drive_id}): {e}")
                        break
                
                # Add each permission to the all_permissions list
                for permission in permissions:
                    permission_data = {
                        'Drive ID': drive_id,
                        'Drive Name': drive_name,
                        'Permission ID': permission.get('id', ''),
                        'Type': permission.get('type', ''),
                        'Email Address': permission.get('emailAddress', ''),
                        'Role': permission.get('role', ''),
                        'Display Name': permission.get('displayName', ''),
                        'Domain': permission.get('domain', ''),
                        'Expiration Time': permission.get('expirationTime', ''),
                        'Deleted': permission.get('deleted', False),
                        'Pending Owner': permission.get('pendingOwner', False)
                    }
                    all_permissions.append(permission_data)
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
            
            # Create DataFrame and export to CSV
            df = pd.DataFrame(all_permissions)
            csv_path = os.path.join(self.output_dir, 'shared_drive_permissions_export.csv')
            df.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"Exported {len(all_permissions)} permissions for {total_drives} shared drives to {csv_path}")
            
            return df, csv_path
            
        except Exception as e:
            print(f"Error exporting shared drive permissions: {e}")
            return pd.DataFrame(), ""
    
    def export_shared_drive_storage(self, drives_df=None):
        """
        Export storage usage for each Shared Drive to a CSV file.
        This requires additional API calls to get each drive's storage information.
        
        Args:
            drives_df: Optional DataFrame with drives data from export_shared_drives().
                       If not provided, will fetch drives first.
        
        Returns:
            Tuple containing DataFrame with storage data and path to the CSV file
        """
        print("\nExporting Shared Drive storage usage...")
        
        # If drives_df not provided, fetch drives first
        if drives_df is None or drives_df.empty:
            drives_df, _ = self.export_shared_drives()
        
        if drives_df.empty:
            print("No shared drives available to export storage for.")
            return pd.DataFrame(), ""
        
        storage_data = []
        
        # For progress tracking
        total_drives = len(drives_df)
        processed = 0
        
        try:
            for _, drive in drives_df.iterrows():
                drive_id = drive['Drive ID']
                drive_name = drive['Drive Name']
                
                processed += 1
                if processed % 5 == 0 or processed == total_drives:
                    print(f"Processing shared drive storage {processed}/{total_drives}: {drive_name}")
                
                try:
                    # Query "root" folder of the shared drive to get storage information
                    file_metadata = self.drive_service.files().get(
                        fileId=drive_id,
                        supportsAllDrives=True,
                        fields="id, name, storageQuota, size, quotaBytesUsed"
                    ).execute()
                    
                    # Try to get total file count in the shared drive (this might be expensive for large drives)
                    file_count_query = self.drive_service.files().list(
                        corpora="drive",
                        driveId=drive_id,
                        includeItemsFromAllDrives=True, 
                        supportsAllDrives=True,
                        pageSize=1000,
                        q="trashed=false",
                        fields="files(id, mimeType)"
                    ).execute()
                    
                    total_files = len(file_count_query.get('files', []))
                    folder_count = sum(1 for file in file_count_query.get('files', []) if file.get('mimeType') == 'application/vnd.google-apps.folder')
                    document_count = total_files - folder_count
                    
                    # Add storage information
                    drive_storage = {
                        'Drive ID': drive_id,
                        'Drive Name': drive_name,
                        'Storage Used (bytes)': file_metadata.get('quotaBytesUsed', 0),
                        'Storage Used (MB)': int(file_metadata.get('quotaBytesUsed', 0)) / (1024 * 1024) if file_metadata.get('quotaBytesUsed') else 0,
                        'Total Files': total_files,
                        'Folder Count': folder_count,
                        'Document Count': document_count
                    }
                    storage_data.append(drive_storage)
                    
                except HttpError as e:
                    print(f"Error fetching storage for drive {drive_name} ({drive_id}): {e}")
                    # Add a placeholder with the error
                    drive_storage = {
                        'Drive ID': drive_id,
                        'Drive Name': drive_name,
                        'Storage Used (bytes)': 0,
                        'Storage Used (MB)': 0,
                        'Total Files': 0,
                        'Folder Count': 0,
                        'Document Count': 0,
                        'Error': str(e)
                    }
                    storage_data.append(drive_storage)
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
            
            # Create DataFrame and export to CSV
            df = pd.DataFrame(storage_data)
            csv_path = os.path.join(self.output_dir, 'shared_drive_storage_export.csv')
            df.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"Exported storage data for {len(storage_data)} shared drives to {csv_path}")
            
            return df, csv_path
            
        except Exception as e:
            print(f"Error exporting shared drive storage: {e}")
            return pd.DataFrame(), ""
    
    def run_all_exports(self):
        """Run all export functions and return a summary of results."""
        print("\nStarting Google Shared Drives exports...")
        
        results = {}
        
        # Export shared drives
        drives_df, drives_path = self.export_shared_drives()
        results['Shared Drives'] = {'count': len(drives_df), 'path': drives_path}
        
        # Export shared drive permissions
        permissions_df, permissions_path = self.export_shared_drive_permissions(drives_df)
        results['Shared Drive Permissions'] = {'count': len(permissions_df), 'path': permissions_path}
        
        # Export shared drive storage
        storage_df, storage_path = self.export_shared_drive_storage(drives_df)
        results['Shared Drive Storage'] = {'count': len(storage_df), 'path': storage_path}
        
        return results


def main():
    parser = argparse.ArgumentParser(description='Google Shared Drives Exporter')
    parser.add_argument('--service-account', required=True, help='Path to service account JSON file')
    parser.add_argument('--admin-email', required=True, help='Admin email for domain-wide delegation')
    parser.add_argument('--output-dir', default='workspace_exports', help='Directory to save exported data')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode with detailed output')
    parser.add_argument('--list-my-drives-only', action='store_true', 
                       help='Only list drives the admin user has direct access to (not using domain admin privileges)')
    
    args = parser.parse_args()
    
    # Initialize and run exporter
    try:
        exporter = SharedDrivesExporter(
            service_account_file=args.service_account,
            admin_email=args.admin_email,
            output_dir=args.output_dir
        )
        
        # Authenticate and initialize services
        exporter.authenticate()
        exporter.initialize_service()
        
        # Run all exports
        print(f"Starting Google Shared Drives exports...")
        results = exporter.run_all_exports()
        
        # Print summary
        print("\n----- Export Summary -----")
        for resource_type, data in results.items():
            print(f"{resource_type}: {data['count']} items exported to {data['path']}")
        
        # Calculate total storage across all shared drives
        if 'Shared Drive Storage' in results and results['Shared Drive Storage']['count'] > 0:
            try:
                storage_df = pd.read_csv(results['Shared Drive Storage']['path'])
                total_storage_mb = storage_df['Storage Used (MB)'].sum()
                total_storage_gb = total_storage_mb / 1024
                print(f"\nTotal storage used across all shared drives: {total_storage_gb:.2f} GB")
            except Exception as e:
                print(f"Could not calculate total storage: {e}")
        
    except Exception as e:
        print(f"Error in Google Shared Drives exports: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
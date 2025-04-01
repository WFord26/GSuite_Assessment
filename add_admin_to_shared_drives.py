#!/usr/bin/env python3
"""
Add Admin to All Shared Drives

This script adds a specified admin account as a manager to all Shared Drives in the organization.
Requires a service account with domain-wide delegation and a super admin account.

Usage:
python add_admin_to_shared_drives.py 
    --service-account /path/to/service-account.json 
    --admin-email admin@yourdomain.com
    [--role manager]
    [--dry-run]
"""

import os
import json
import argparse
import time
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.errors import HttpError

def get_all_shared_drives(drive_service):
    """
    Retrieves all Shared Drives in the organization.
    
    Args:
        drive_service: Authenticated Drive API service
        
    Returns:
        List of Shared Drives
    """
    print("Retrieving all Shared Drives in the organization...")
    shared_drives = []
    page_token = None
    
    while True:
        try:
            results = drive_service.drives().list(
                pageSize=100,
                pageToken=page_token,
                fields="nextPageToken, drives(id, name, createdTime, hidden)"
            ).execute()
            
            current_drives = results.get('drives', [])
            if not current_drives:
                break
            
            shared_drives.extend(current_drives)
            print(f"Retrieved {len(shared_drives)} shared drives so far...")
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
            
            # Small delay to avoid rate limiting
            time.sleep(0.5)
        
        except HttpError as e:
            print(f"Error retrieving Shared Drives: {e}")
            break
    
    return shared_drives

def check_admin_permissions(drive_service, drive_id, admin_email):
    """
    Checks if the admin already has permissions on the Shared Drive.
    
    Args:
        drive_service: Authenticated Drive API service
        drive_id: ID of the Shared Drive
        admin_email: Email address of the admin
        
    Returns:
        Tuple of (has_permissions, permission_id, current_role)
    """
    try:
        # List permissions for the drive
        permissions = drive_service.permissions().list(
            fileId=drive_id,
            supportsAllDrives=True,
            fields="permissions(id, emailAddress, role)"
        ).execute()
        
        # Check if admin already has permissions
        for permission in permissions.get('permissions', []):
            if permission.get('emailAddress', '').lower() == admin_email.lower():
                return True, permission.get('id'), permission.get('role')
        
        return False, None, None
    
    except HttpError as e:
        print(f"Error checking permissions for drive {drive_id}: {e}")
        return False, None, None

def add_admin_to_drive(drive_service, drive_id, drive_name, admin_email, role, dry_run=False):
    """
    Adds the admin to a Shared Drive with the specified role.
    
    Args:
        drive_service: Authenticated Drive API service
        drive_id: ID of the Shared Drive
        drive_name: Name of the Shared Drive (for logging)
        admin_email: Email address of the admin
        role: Role to assign to the admin
        dry_run: If True, only simulate the action without making changes
        
    Returns:
        True if successful, False otherwise
    """
    # Check if admin already has permissions
    has_permissions, permission_id, current_role = check_admin_permissions(
        drive_service, drive_id, admin_email)
    
    if has_permissions:
        if current_role == role:
            print(f"Admin {admin_email} already has {role} role on drive '{drive_name}'")
            return True
        else:
            if dry_run:
                print(f"DRY RUN: Would update {admin_email} from {current_role} to {role} on drive '{drive_name}'")
                return True
                
            try:
                # Update the permission to the desired role
                drive_service.permissions().update(
                    fileId=drive_id,
                    permissionId=permission_id,
                    supportsAllDrives=True,
                    body={'role': role}
                ).execute()
                print(f"Updated {admin_email} from {current_role} to {role} on drive '{drive_name}'")
                return True
            except HttpError as e:
                print(f"Error updating permission on drive '{drive_name}': {e}")
                return False
    else:
        if dry_run:
            print(f"DRY RUN: Would add {admin_email} as {role} to drive '{drive_name}'")
            return True
            
        try:
            # Add the admin with the specified role
            permission = {
                'type': 'user',
                'role': role,
                'emailAddress': admin_email
            }
            
            drive_service.permissions().create(
                fileId=drive_id,
                supportsAllDrives=True,
                body=permission
            ).execute()
            
            print(f"Added {admin_email} as {role} to drive '{drive_name}'")
            return True
        except HttpError as e:
            print(f"Error adding permission to drive '{drive_name}': {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description='Add Admin to All Shared Drives')
    parser.add_argument('--service-account', required=True, help='Path to service account JSON key file')
    parser.add_argument('--admin-email', required=True, help='Admin email to add to all Shared Drives')
    parser.add_argument('--role', default='manager', choices=['manager', 'organizer', 'fileOrganizer', 'writer', 'commenter', 'reader'],
                        help='Role to assign to the admin (default: manager)')
    parser.add_argument('--dry-run', action='store_true', help='Simulate the operation without making changes')
    
    args = parser.parse_args()
    
    # Print configuration
    print("===== ADD ADMIN TO ALL SHARED DRIVES =====")
    print(f"Admin to add: {args.admin_email}")
    print(f"Role to assign: {args.role}")
    print(f"Dry run: {args.dry_run}")
    print("==========================================")
    
    try:
        # Authenticate with service account
        scopes = [
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        
        creds = service_account.Credentials.from_service_account_file(
            args.service_account, scopes=scopes)
        creds = creds.with_subject(args.admin_email)
        
        # Build the Drive API service
        drive_service = build('drive', 'v3', credentials=creds)
        
        # Get all Shared Drives
        shared_drives = get_all_shared_drives(drive_service)
        
        if not shared_drives:
            print("No Shared Drives found in the organization.")
            return
        
        print(f"\nFound {len(shared_drives)} Shared Drives to process.")
        
        if args.dry_run:
            print("DRY RUN MODE: No changes will be made.")
        
        # Process each Shared Drive
        success_count = 0
        failure_count = 0
        
        for drive in shared_drives:
            drive_id = drive.get('id')
            drive_name = drive.get('name', 'Unnamed Drive')
            
            print(f"\nProcessing Shared Drive: '{drive_name}' (ID: {drive_id})")
            
            if add_admin_to_drive(
                drive_service, drive_id, drive_name, args.admin_email, args.role, args.dry_run):
                success_count += 1
            else:
                failure_count += 1
            
            # Small delay to avoid rate limiting
            time.sleep(0.5)
        
        # Print summary
        print("\n===== SUMMARY =====")
        print(f"Total Shared Drives: {len(shared_drives)}")
        print(f"Successful operations: {success_count}")
        print(f"Failed operations: {failure_count}")
        
        if args.dry_run:
            print("DRY RUN MODE: No changes were made.")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
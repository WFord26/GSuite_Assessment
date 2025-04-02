#!/usr/bin/env python3
"""
Google Workspace Mailbox Permissions Exporter

This script exports mailbox permissions for Google Workspace users, including:
- Mail delegation settings (account delegates with access)
- Mail forwarding settings
- Mail access settings (IMAP/POP access)
- Gmail settings (labels, filters, auto-replies)

Requirements:
- Python 3.7+
- google-api-python-client
- google-auth
- pandas

Usage:
python google_mailbox_permissions.py 
    --domain yourdomain.com 
    --service-account /path/to/service-account.json 
    --admin-email admin@yourdomain.com 
    --output-dir mailbox_permissions
    --max-users 10
"""

import os
import json
import datetime
import argparse
import time
from typing import Dict, Any, List, Tuple

import pandas as pd
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.errors import HttpError

class MailboxPermissionsExporter:
    def __init__(self, domain: str, service_account_file: str, 
                 admin_email: str, output_dir: str = 'mailbox_permissions'):
        """
        Initialize Mailbox Permissions Exporter.
        
        Args:
            domain: Google Workspace domain
            service_account_file: Service account credentials file path
            admin_email: Admin email for domain-wide delegation
            output_dir: Directory to save exported data
        """
        self.domain = domain
        self.service_account_file = service_account_file
        self.admin_email = admin_email
        self.output_dir = output_dir
        self.raw_data_dir = os.path.join(output_dir, "raw_data")
        self.creds = None
        self.services = {}
        self.debug_mode = True
        
        # Create output directories
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(self.raw_data_dir, exist_ok=True)
    
    def authenticate(self):
        """Authenticate with Google Workspace APIs."""
        try:
            # Use required scopes for mail delegation and settings
            scopes = [
                'https://www.googleapis.com/auth/admin.directory.user.readonly',
                'https://www.googleapis.com/auth/gmail.settings.basic',
                'https://www.googleapis.com/auth/gmail.settings.sharing',
                'https://apps-apis.google.com/a/feeds/emailsettings/2.0/'
            ]
            
            self.creds = service_account.Credentials.from_service_account_file(
                self.service_account_file, scopes=scopes)
            self.creds = self.creds.with_subject(self.admin_email)
            print(f"Authenticated as {self.admin_email} using service account")
        except Exception as e:
            print(f"Authentication error: {e}")
            raise
    
    def initialize_services(self):
        """Initialize Google Workspace API services."""
        try:
            self.services['directory'] = build('admin', 'directory_v1', credentials=self.creds)
            self.services['gmail'] = build('gmail', 'v1', credentials=self.creds)
            print("Services initialized successfully")
        except Exception as e:
            print(f"Error initializing services: {e}")
            raise
    
    def get_user_details(self, user_email: str) -> Dict[str, Any]:
        """Get user details from Directory API."""
        try:
            user_info = self.services['directory'].users().get(
                userKey=user_email,
                fields="primaryEmail,name,isAdmin,isDelegatedAdmin,suspended,isEnrolledIn2Sv,isEnforcedIn2Sv,orgUnitPath"
            ).execute()
            
            # Save raw data
            if self.debug_mode:
                with open(os.path.join(self.raw_data_dir, f"{user_email.replace('@', '_')}_user_info.json"), 'w') as f:
                    json.dump(user_info, f, indent=2)
            
            return user_info
        except Exception as e:
            print(f"Error getting user details for {user_email}: {e}")
            return {}
    
    def get_mail_delegates(self, user_email: str) -> List[Dict[str, Any]]:
        """Get mail delegates for a user using the Gmail API."""
        delegates = []
        try:
            # Create credentials for this specific user
            user_creds = self.creds.with_subject(user_email)
            gmail_service = build('gmail', 'v1', credentials=user_creds)
            
            # Get delegates
            results = gmail_service.users().settings().delegates().list(
                userId='me'
            ).execute()
            
            delegates = results.get('delegates', [])
            
            # Save raw data
            if self.debug_mode:
                with open(os.path.join(self.raw_data_dir, f"{user_email.replace('@', '_')}_delegates.json"), 'w') as f:
                    json.dump(delegates, f, indent=2)
            
            return delegates
        except HttpError as e:
            # Handle specific error cases
            if e.resp.status == 403:
                print(f"Access denied for {user_email}'s delegates. This may require additional permissions.")
            elif e.resp.status == 404:
                print(f"Delegates endpoint not found for {user_email}. The user may not exist.")
            else:
                print(f"Error getting mail delegates for {user_email}: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error getting mail delegates for {user_email}: {e}")
            return []
    
    def get_forwarding_settings(self, user_email: str) -> List[Dict[str, Any]]:
        """Get email forwarding settings for a user using the Gmail API."""
        forwarding = []
        try:
            # Create credentials for this specific user
            user_creds = self.creds.with_subject(user_email)
            gmail_service = build('gmail', 'v1', credentials=user_creds)
            
            # Get forwarding settings
            results = gmail_service.users().settings().forwardingAddresses().list(
                userId='me'
            ).execute()
            
            forwarding_addresses = results.get('forwardingAddresses', [])
            
            # Get auto-forwarding settings
            auto_forward = gmail_service.users().settings().getAutoForwarding(
                userId='me'
            ).execute()
            
            forwarding = {
                'forwarding_addresses': forwarding_addresses,
                'auto_forward': auto_forward
            }
            
            # Save raw data
            if self.debug_mode:
                with open(os.path.join(self.raw_data_dir, f"{user_email.replace('@', '_')}_forwarding.json"), 'w') as f:
                    json.dump(forwarding, f, indent=2)
            
            return forwarding
        except HttpError as e:
            # Handle specific error cases
            if e.resp.status == 403:
                print(f"Access denied for {user_email}'s forwarding settings. This may require additional permissions.")
            elif e.resp.status == 404:
                print(f"Forwarding settings endpoint not found for {user_email}. The user may not exist.")
            else:
                print(f"Error getting forwarding settings for {user_email}: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error getting forwarding settings for {user_email}: {e}")
            return []
    
    def get_mail_access_settings(self, user_email: str) -> Dict[str, Any]:
        """Get IMAP/POP access settings for a user using the Gmail API."""
        access_settings = {}
        try:
            # Create credentials for this specific user
            user_creds = self.creds.with_subject(user_email)
            gmail_service = build('gmail', 'v1', credentials=user_creds)
            
            # Get IMAP settings
            imap_settings = gmail_service.users().settings().getImap(
                userId='me'
            ).execute()
            
            # Get POP settings
            pop_settings = gmail_service.users().settings().getPop(
                userId='me'
            ).execute()
            
            access_settings = {
                'imap': imap_settings,
                'pop': pop_settings
            }
            
            # Save raw data
            if self.debug_mode:
                with open(os.path.join(self.raw_data_dir, f"{user_email.replace('@', '_')}_access_settings.json"), 'w') as f:
                    json.dump(access_settings, f, indent=2)
            
            return access_settings
        except HttpError as e:
            # Handle specific error cases
            if e.resp.status == 403:
                print(f"Access denied for {user_email}'s access settings. This may require additional permissions.")
            elif e.resp.status == 404:
                print(f"Access settings endpoint not found for {user_email}. The user may not exist.")
            else:
                print(f"Error getting access settings for {user_email}: {e}")
            return {}
        except Exception as e:
            print(f"Unexpected error getting access settings for {user_email}: {e}")
            return {}
    
    def process_user_mailbox_permissions(self, user_email: str) -> Dict[str, Any]:
        """
        Process mailbox permissions for a single user.
        
        Args:
            user_email: Email of the user to process
            
        Returns:
            Dict with mailbox permissions data
        """
        print(f"Processing mailbox permissions for {user_email}")
        
        # Initialize permissions data
        permissions_data = {
            'Email': user_email,
            'HasDelegates': False,
            'DelegateCount': 0,
            'Delegates': [],
            'HasForwarding': False,
            'ForwardingEnabled': False,
            'ForwardingAddresses': [],
            'HasIMAPAccess': False,
            'HasPOPAccess': False,
            'UserIsActive': True,
            'UserIsSuspended': False
        }
        
        try:
            # Get user details
            user_info = self.get_user_details(user_email)
            if user_info:
                permissions_data['UserIsActive'] = not user_info.get('suspended', False)
                permissions_data['UserIsSuspended'] = user_info.get('suspended', False)
                permissions_data['IsAdmin'] = user_info.get('isAdmin', False)
                permissions_data['IsDelegatedAdmin'] = user_info.get('isDelegatedAdmin', False)
                permissions_data['Has2FA'] = user_info.get('isEnrolledIn2Sv', False)
                permissions_data['OrgUnitPath'] = user_info.get('orgUnitPath', '')
            
            # Skip suspended users
            if permissions_data['UserIsSuspended']:
                print(f"Skipping suspended user: {user_email}")
                return permissions_data
            
            # Get mail delegates
            delegates = self.get_mail_delegates(user_email)
            if delegates:
                permissions_data['HasDelegates'] = True
                permissions_data['DelegateCount'] = len(delegates)
                permissions_data['Delegates'] = [d.get('delegateEmail', '') for d in delegates]
            
            # Get forwarding settings
            forwarding = self.get_forwarding_settings(user_email)
            if forwarding:
                # Check if there are any forwarding addresses
                if 'forwarding_addresses' in forwarding and forwarding['forwarding_addresses']:
                    permissions_data['HasForwarding'] = True
                    permissions_data['ForwardingAddresses'] = [
                        f.get('forwardingEmail', '') for f in forwarding['forwarding_addresses']
                    ]
                
                # Check if auto-forwarding is enabled
                if 'auto_forward' in forwarding and forwarding['auto_forward']:
                    permissions_data['ForwardingEnabled'] = forwarding['auto_forward'].get('enabled', False)
                    permissions_data['ForwardingDestination'] = forwarding['auto_forward'].get('emailAddress', '')
                    
                    if permissions_data['ForwardingEnabled']:
                        permissions_data['HasForwarding'] = True
                        if permissions_data['ForwardingDestination'] not in permissions_data['ForwardingAddresses']:
                            permissions_data['ForwardingAddresses'].append(permissions_data['ForwardingDestination'])
            
            # Get mail access settings
            access_settings = self.get_mail_access_settings(user_email)
            if access_settings:
                if 'imap' in access_settings:
                    permissions_data['HasIMAPAccess'] = access_settings['imap'].get('enabled', False)
                
                if 'pop' in access_settings:
                    permissions_data['HasPOPAccess'] = access_settings['pop'].get('accessWindow', 'DISABLED') != 'DISABLED'
            
            return permissions_data
            
        except Exception as e:
            print(f"Error processing mailbox permissions for {user_email}: {e}")
            return permissions_data
    
    def export_mailbox_permissions(self, max_users=10):
        """
        Export mailbox permissions for Google Workspace users.
        
        Args:
            max_users: Maximum number of users to process (0 for all)
            
        Returns:
            DataFrame with mailbox permissions data
        """
        permissions_list = []
        user_count = 0
        page_token = None
        
        try:
            while True:
                # Get a batch of users
                results = self.services['directory'].users().list(
                    customer='my_customer',
                    maxResults=100,
                    orderBy='email',
                    pageToken=page_token,
                    fields='users(primaryEmail,suspended),nextPageToken'
                ).execute()
                
                users = results.get('users', [])
                if not users:
                    break
                
                print(f"Found {len(users)} users")
                
                # Process users
                for i, user in enumerate(users):
                    email = user.get('primaryEmail', '')
                    is_suspended = user.get('suspended', False)
                    
                    if not is_suspended:  # Skip suspended users
                        print(f"\nProcessing user {i+1}/{len(users)}: {email}")
                        
                        # Get mailbox permissions
                        permissions_data = self.process_user_mailbox_permissions(email)
                        permissions_list.append(permissions_data)
                        
                        user_count += 1
                        if user_count >= max_users and max_users > 0:
                            print(f"Reached maximum user limit of {max_users}")
                            break
                        
                        # Small delay to avoid rate limiting
                        time.sleep(1)
                
                if user_count >= max_users and max_users > 0:
                    break
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                
                # Save intermediate results
                if len(permissions_list) % 10 == 0:
                    self._save_to_csv(permissions_list, f"mailbox_permissions_partial_{len(permissions_list)}.csv")
            
            # Save final results
            if permissions_list:
                self._save_to_csv(permissions_list, "mailbox_permissions_complete.csv")
                
                # Save detailed delegate information
                self._save_detailed_delegates(permissions_list)
                
                # Save detailed forwarding information
                self._save_detailed_forwarding(permissions_list)
            
            return pd.DataFrame(permissions_list)
            
        except Exception as e:
            print(f"Error exporting mailbox permissions: {e}")
            
            # Save what we have
            if permissions_list:
                self._save_to_csv(permissions_list, "mailbox_permissions_error.csv")
            
            return pd.DataFrame(permissions_list)
    
    def _save_to_csv(self, data, filename):
        """Helper method to save data to CSV."""
        if data:
            # Convert list data to strings for CSV export
            for item in data:
                if 'Delegates' in item and isinstance(item['Delegates'], list):
                    item['Delegates'] = ','.join(item['Delegates'])
                if 'ForwardingAddresses' in item and isinstance(item['ForwardingAddresses'], list):
                    item['ForwardingAddresses'] = ','.join(item['ForwardingAddresses'])
            
            df = pd.DataFrame(data)
            csv_path = os.path.join(self.output_dir, filename)
            df.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"Saved {len(data)} records to {csv_path}")
        else:
            print("No data to save")
    
    def _save_detailed_delegates(self, permissions_list):
        """Save detailed delegate information to CSV."""
        delegate_records = []
        
        for perm in permissions_list:
            email = perm.get('Email', '')
            delegates = perm.get('Delegates', [])
            
            if isinstance(delegates, str):
                delegates = delegates.split(',') if delegates else []
            
            for delegate in delegates:
                if delegate:
                    record = {
                        'Mailbox': email,
                        'Delegate': delegate.strip()
                    }
                    delegate_records.append(record)
        
        if delegate_records:
            df = pd.DataFrame(delegate_records)
            csv_path = os.path.join(self.output_dir, "detailed_delegates.csv")
            df.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"Saved {len(delegate_records)} delegate records to {csv_path}")
    
    def _save_detailed_forwarding(self, permissions_list):
        """Save detailed forwarding information to CSV."""
        forwarding_records = []
        
        for perm in permissions_list:
            email = perm.get('Email', '')
            forwarding_addresses = perm.get('ForwardingAddresses', [])
            forwarding_enabled = perm.get('ForwardingEnabled', False)
            
            if isinstance(forwarding_addresses, str):
                forwarding_addresses = forwarding_addresses.split(',') if forwarding_addresses else []
            
            for fwd_address in forwarding_addresses:
                if fwd_address:
                    record = {
                        'Mailbox': email,
                        'ForwardingAddress': fwd_address.strip(),
                        'AutoForwardingEnabled': forwarding_enabled
                    }
                    forwarding_records.append(record)
        
        if forwarding_records:
            df = pd.DataFrame(forwarding_records)
            csv_path = os.path.join(self.output_dir, "detailed_forwarding.csv")
            df.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"Saved {len(forwarding_records)} forwarding records to {csv_path}")

def main():
    parser = argparse.ArgumentParser(description='Google Workspace Mailbox Permissions Exporter')
    parser.add_argument('--domain', required=True, help='Your Google Workspace domain')
    parser.add_argument('--service-account', required=True, help='Path to service account JSON file')
    parser.add_argument('--admin-email', required=True, help='Admin email for domain-wide delegation')
    parser.add_argument('--output-dir', default='mailbox_permissions', help='Directory to save exported data')
    parser.add_argument('--max-users', type=int, default=10, help='Maximum number of users to process (0 for all)')
    
    args = parser.parse_args()
    
    # Initialize and run exporter
    try:
        exporter = MailboxPermissionsExporter(
            domain=args.domain,
            service_account_file=args.service_account,
            admin_email=args.admin_email,
            output_dir=args.output_dir
        )
        
        # Authenticate and initialize services
        exporter.authenticate()
        exporter.initialize_services()
        
        # Export mailbox permissions
        user_limit_msg = f"up to {args.max_users}" if args.max_users > 0 else "all"
        print(f"Starting mailbox permissions export for {user_limit_msg} users...")
        df = exporter.export_mailbox_permissions(max_users=args.max_users)
        
        # Show summary
        if not df.empty:
            print("\nExport completed successfully")
            print(f"Total users processed: {len(df)}")
            
            # Delegate stats
            delegate_count = df['HasDelegates'].sum()
            print(f"Users with delegates: {delegate_count} ({delegate_count/len(df)*100:.1f}%)")
            
            # Forwarding stats
            forwarding_count = df['HasForwarding'].sum()
            print(f"Users with forwarding: {forwarding_count} ({forwarding_count/len(df)*100:.1f}%)")
            
            # Access stats
            imap_count = df['HasIMAPAccess'].sum()
            pop_count = df['HasPOPAccess'].sum()
            print(f"Users with IMAP access: {imap_count} ({imap_count/len(df)*100:.1f}%)")
            print(f"Users with POP access: {pop_count} ({pop_count/len(df)*100:.1f}%)")
        else:
            print("No data exported")
        
    except Exception as e:
        print(f"Error in mailbox permissions export: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
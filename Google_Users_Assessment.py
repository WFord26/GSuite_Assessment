#!/usr/bin/env python3
"""
Combined Google Workspace Statistics Collector

This script collects both Gmail and Drive statistics for Google Workspace users.
It uses the Reports API to gather statistics while handling potential parameter issues.

Requirements:
- Python 3.7+
- google-api-python-client
- google-auth
- pandas

Usage:
python google_user_assessment.py 
    --domain yourdomain.com 
    --service-account /path/to/service-account.json 
    --admin-email admin@yourdomain.com 
    --output-dir workspace_stats
    --max-users 10
"""

import os
import json
import datetime
import argparse
import time
from typing import Dict, Any, List

import pandas as pd
from googleapiclient.discovery import build
from google.oauth2 import service_account

class WorkspaceStatsCollector:
    def __init__(self, domain: str, service_account_file: str, 
                 admin_email: str, output_dir: str = 'workspace_stats'):
        """
        Initialize Workspace Statistics collection tool.
        
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
            # Use minimal scopes to avoid permission issues
            scopes = [
                'https://www.googleapis.com/auth/admin.directory.user.readonly',
                'https://www.googleapis.com/auth/admin.reports.usage.readonly'
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
            self.services['reports'] = build('admin', 'reports_v1', credentials=self.creds)
            print("Services initialized successfully")
        except Exception as e:
            print(f"Error initializing services: {e}")
            raise
    
    def get_all_parameters(self, user_email: str) -> Dict[str, Any]:
        """
        Get all available parameters for a user from the Reports API.
        
        Args:
            user_email: Email of the user to check
            
        Returns:
            Dict of all parameters and their values
        """
        # Set report date to 3 days ago to ensure data availability
        report_date = (datetime.datetime.now() - datetime.timedelta(days=3)).strftime('%Y-%m-%d')
        
        try:
            # Try a general request without specifying parameters
            report = self.services['reports'].userUsageReport().get(
                userKey=user_email,
                date=report_date
            ).execute()
            
            # Save raw response for debugging
            if self.debug_mode:
                with open(os.path.join(self.raw_data_dir, f"{user_email.replace('@', '_')}_raw.json"), 'w') as f:
                    json.dump(report, f, indent=2)
            
            parameters = {}
            
            # Process all parameters in the response
            for usage_report in report.get('usageReports', []):
                # Get parameters
                for param in usage_report.get('parameters', []):
                    param_name = param.get('name', '')
                    
                    # Extract value based on type
                    if 'stringValue' in param:
                        parameters[param_name] = param['stringValue']
                    elif 'intValue' in param:
                        parameters[param_name] = int(param['intValue'])
                    elif 'boolValue' in param:
                        parameters[param_name] = param['boolValue']
                    else:
                        parameters[param_name] = None
            
            # Save the parameters to a file for analysis
            with open(os.path.join(self.raw_data_dir, f"{user_email.replace('@', '_')}_parameters.json"), 'w') as f:
                json.dump(parameters, f, indent=2)
            
            print(f"Found {len(parameters)} parameters for user {user_email}")
            return parameters
            
        except Exception as e:
            print(f"Error getting parameters for {user_email}: {e}")
            return {}
    
    def get_drive_item_count(self, parameters: Dict[str, Any]) -> int:
        """
        Extract Drive item count from parameters with special handling.
        
        Args:
            parameters: Dict of parameters from Reports API
            
        Returns:
            Total Drive item count
        """
        # Initialize count
        total_items = 0
        
        # List of possible item count parameters, in order of preference
        item_count_params = [
            'num_items',             # Total items
            'num_docs',              # Google Docs
            'num_sheets',            # Google Sheets 
            'num_slides',            # Google Slides
            'num_drawings',          # Google Drawings
            'num_forms',             # Google Forms
            'num_files',             # Regular files
            'num_folders',           # Folders
            'drive_num_items',       # Alternative parameter
            'doc_count',             # Alternative parameter
            'drive_file_count',      # Alternative parameter
            'total_doc_count'        # Alternative parameter
        ]
        
        # Look for a single comprehensive parameter first
        for param in item_count_params:
            if param in parameters:
                try:
                    value = int(parameters[param])
                    if value > 0:
                        print(f"Found item count from parameter '{param}': {value}")
                        return value
                except (ValueError, TypeError):
                    continue
        
        # If no single parameter works, try to sum the specific document type counts
        doc_type_params = [
            'drive:num_owned_google_documents_created',
            'drive:num_owned_google_spreadsheets_created', 
            'drive:num_owned_google_presentations_created',
            'drive:num_owned_google_drawings_created',
            'drive:num_owned_google_forms_created',
            'drive:num_owned_other_types_created',
            'docs:num_owned_google_documents_created',
            'docs:num_owned_google_spreadsheets_created', 
            'docs:num_owned_google_presentations_created',
            'docs:num_owned_google_drawings_created',
            'docs:num_owned_google_forms_created',
            'docs:num_owned_other_types_created'
        ]
        
        # Get counts for each document type
        type_counts = {}
        for param in doc_type_params:
            if param in parameters:
                try:
                    value = int(parameters[param])
                    type_counts[param] = value
                    total_items += value
                except (ValueError, TypeError):
                    continue
        
        # Log the breakdown if we found multiple types
        if type_counts and total_items > 0:
            print(f"Calculated item count by summing: {type_counts}")
            print(f"Total items: {total_items}")
            return total_items
        
        # As a fallback, look for any parameter with "count" or "items" in the name
        if total_items == 0:
            for param_name, param_value in parameters.items():
                if any(x in param_name.lower() for x in ['count', 'items', 'docs']):
                    try:
                        value = int(param_value)
                        if value > 0 and 'drive' in param_name.lower():
                            print(f"Found item count from fallback parameter '{param_name}': {value}")
                            return value
                    except (ValueError, TypeError):
                        continue
        
        return total_items
    
    def get_drive_storage(self, parameters: Dict[str, Any]) -> float:
        """
        Extract Drive storage from parameters.
        
        Args:
            parameters: Dict of parameters from Reports API
            
        Returns:
            Drive storage in MB
        """
        # Initialize storage
        storage_mb = 0
        
        # Check for accounts:drive_used_quota_in_mb first (based on JSON samples)
        if 'accounts:drive_used_quota_in_mb' in parameters:
            try:
                value = float(parameters['accounts:drive_used_quota_in_mb'])
                print(f"Found Drive storage from parameter 'accounts:drive_used_quota_in_mb': {value:.2f} MB")
                return value
            except (ValueError, TypeError):
                pass
        
        # List of possible storage parameters, in order of preference
        storage_params = [
            'drive_storage_bytes_used',
            'storage_quota_bytes',
            'used_quota_in_mb',
            'quota_used',
            'storage_quota_mb',
            'drive_storage_used',
            'total_storage_used'
        ]
        
        # Try each parameter
        for param in storage_params:
            if param in parameters:
                try:
                    value = float(parameters[param])
                    
                    # Convert to MB if needed
                    if 'bytes' in param.lower() or value > 1000000:
                        value = value / (1024 * 1024)
                    
                    print(f"Found Drive storage from parameter '{param}': {value:.2f} MB")
                    return value
                except (ValueError, TypeError):
                    continue
        
        # Fallback: look for any parameter with storage-related terms
        for param_name, param_value in parameters.items():
            if any(x in param_name.lower() for x in ['storage', 'quota', 'byte']):
                try:
                    value = float(param_value)
                    
                    # Convert to MB if needed
                    if 'bytes' in param_name.lower() or value > 1000000:
                        value = value / (1024 * 1024)
                    
                    if value > 0 and 'drive' in param_name.lower():
                        print(f"Found Drive storage from fallback parameter '{param_name}': {value:.2f} MB")
                        return value
                except (ValueError, TypeError):
                    continue
        
        return storage_mb
    
    def get_gmail_statistics(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract Gmail statistics from parameters.
        
        Args:
            parameters: Dict of parameters from Reports API
            
        Returns:
            Dict with Gmail statistics
        """
        # Initialize Gmail stats
        gmail_stats = {
            'Gmail_Storage_MB': 0,
            'Gmail_Emails_Received': 0,
            'Gmail_Emails_Sent': 0,
            'Gmail_Emails_Exchanged': 0,
            'Is_Gmail_Enabled': True,
            'Has_Gmail_Data': False
        }
        
        # Check if Gmail is enabled
        gmail_status_params = ['gmail:is_gmail_enabled', 'is_gmail_enabled', 'gmail_enabled', 'has_gmail']
        for param in gmail_status_params:
            if param in parameters:
                try:
                    gmail_stats['Is_Gmail_Enabled'] = bool(parameters[param])
                    print(f"Gmail enabled status from parameter '{param}': {gmail_stats['Is_Gmail_Enabled']}")
                    break
                except (ValueError, TypeError):
                    continue
        
        # Get Gmail storage
        if 'accounts:gmail_used_quota_in_mb' in parameters:
            try:
                value = float(parameters['accounts:gmail_used_quota_in_mb'])
                gmail_stats['Gmail_Storage_MB'] = value
                gmail_stats['Has_Gmail_Data'] = True
                print(f"Gmail storage from parameter 'accounts:gmail_used_quota_in_mb': {value:.2f} MB")
            except (ValueError, TypeError):
                pass
        else:
            # Try other parameter names
            gmail_storage_params = [
                'gmail_used_quota_in_mb',
                'gmail_storage_used',
                'gmail_quota_used',
                'gmail_storage_bytes_used'
            ]
            
            for param in gmail_storage_params:
                if param in parameters:
                    try:
                        value = float(parameters[param])
                        
                        # Convert to MB if needed
                        if 'bytes' in param.lower() or value > 1000000:
                            value = value / (1024 * 1024)
                        
                        gmail_stats['Gmail_Storage_MB'] = value
                        gmail_stats['Has_Gmail_Data'] = True
                        print(f"Gmail storage from parameter '{param}': {value:.2f} MB")
                        break
                    except (ValueError, TypeError):
                        continue
            
            # Fallback for Gmail storage
            if gmail_stats['Gmail_Storage_MB'] == 0:
                for param_name, param_value in parameters.items():
                    if any(x in param_name.lower() for x in ['storage', 'quota', 'byte']) and 'gmail' in param_name.lower():
                        try:
                            value = float(param_value)
                            
                            # Convert to MB if needed
                            if 'bytes' in param_name.lower() or value > 1000000:
                                value = value / (1024 * 1024)
                            
                            if value > 0:
                                gmail_stats['Gmail_Storage_MB'] = value
                                gmail_stats['Has_Gmail_Data'] = True
                                print(f"Gmail storage from fallback parameter '{param_name}': {value:.2f} MB")
                                break
                        except (ValueError, TypeError):
                            continue
        
        # Get emails sent count
        sent_params = ['gmail:num_emails_sent', 'num_emails_sent', 'emails_sent', 'sent_mail_count']
        for param in sent_params:
            if param in parameters:
                try:
                    value = int(parameters[param])
                    gmail_stats['Gmail_Emails_Sent'] = value
                    gmail_stats['Has_Gmail_Data'] = True
                    print(f"Gmail sent emails from parameter '{param}': {value}")
                    break
                except (ValueError, TypeError):
                    continue
        
        # Get emails received count
        received_params = ['gmail:num_emails_received', 'num_emails_received', 'emails_received', 'received_mail_count']
        for param in received_params:
            if param in parameters:
                try:
                    value = int(parameters[param])
                    gmail_stats['Gmail_Emails_Received'] = value
                    gmail_stats['Has_Gmail_Data'] = True
                    print(f"Gmail received emails from parameter '{param}': {value}")
                    break
                except (ValueError, TypeError):
                    continue
        
        # Get emails exchanged count (total)
        exchanged_params = ['gmail:num_emails_exchanged', 'num_emails_exchanged', 'emails_exchanged', 'total_mail_count']
        for param in exchanged_params:
            if param in parameters:
                try:
                    value = int(parameters[param])
                    gmail_stats['Gmail_Emails_Exchanged'] = value
                    gmail_stats['Has_Gmail_Data'] = True
                    print(f"Gmail exchanged emails from parameter '{param}': {value}")
                    break
                except (ValueError, TypeError):
                    continue
        
        # If we don't have exchanged count but have sent and received, calculate it
        if gmail_stats['Gmail_Emails_Exchanged'] == 0 and (gmail_stats['Gmail_Emails_Sent'] > 0 or gmail_stats['Gmail_Emails_Received'] > 0):
            gmail_stats['Gmail_Emails_Exchanged'] = gmail_stats['Gmail_Emails_Sent'] + gmail_stats['Gmail_Emails_Received']
            print(f"Calculated Gmail exchanged emails: {gmail_stats['Gmail_Emails_Exchanged']}")
        
        return gmail_stats
    
    def get_user_workspace_stats(self, user_email: str) -> Dict[str, Any]:
        """
        Get combined Gmail and Drive statistics for a user.
        
        Args:
            user_email: Email of the user to check
            
        Returns:
            Dict with combined statistics
        """
        # Initialize stats
        stats = {
            'Email': user_email,
            # Gmail stats
            'Gmail_Storage_MB': 0,
            'Gmail_Emails_Received': 0,
            'Gmail_Emails_Sent': 0,
            'Gmail_Emails_Exchanged': 0,
            'Is_Gmail_Enabled': True,
            'Has_Gmail_Data': False,
            # Drive stats
            'Drive_Storage_MB': 0,
            'Drive_Item_Count': 0,
            'Has_Drive_Data': False,
            # Combined stats
            'Total_Storage_MB': 0,
            'Parameter_Source': 'reports_api'
        }
        
        try:
            # Check if the user exists and is active
            try:
                user_info = self.services['directory'].users().get(
                    userKey=user_email
                ).execute()
                
                if user_info.get('suspended', False):
                    stats['Is_Gmail_Enabled'] = False
                    print(f"User {user_email} is suspended")
            except Exception as e:
                print(f"Could not retrieve user information: {e}")
            
            # Get all parameters for the user
            parameters = self.get_all_parameters(user_email)
            
            if parameters:
                # Get Drive statistics
                drive_storage = self.get_drive_storage(parameters)
                if drive_storage > 0:
                    stats['Drive_Storage_MB'] = drive_storage
                    stats['Has_Drive_Data'] = True
                
                drive_items = self.get_drive_item_count(parameters)
                if drive_items > 0:
                    stats['Drive_Item_Count'] = drive_items
                    stats['Has_Drive_Data'] = True
                
                # Get Gmail statistics
                gmail_stats = self.get_gmail_statistics(parameters)
                stats.update({
                    'Gmail_Storage_MB': gmail_stats['Gmail_Storage_MB'],
                    'Gmail_Emails_Received': gmail_stats['Gmail_Emails_Received'],
                    'Gmail_Emails_Sent': gmail_stats['Gmail_Emails_Sent'],
                    'Gmail_Emails_Exchanged': gmail_stats['Gmail_Emails_Exchanged'],
                    'Is_Gmail_Enabled': gmail_stats['Is_Gmail_Enabled'],
                    'Has_Gmail_Data': gmail_stats['Has_Gmail_Data']
                })
                
                # Calculate total storage
                stats['Total_Storage_MB'] = stats['Gmail_Storage_MB'] + stats['Drive_Storage_MB']
            
            return stats
            
        except Exception as e:
            print(f"Error getting workspace stats for {user_email}: {e}")
            return stats
    
    def collect_workspace_stats(self, max_users=10):
        """
        Collect workspace statistics for users.
        
        Args:
            max_users: Maximum number of users to process
            
        Returns:
            DataFrame with workspace statistics
        """
        stats_list = []
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
                    print(f"\nProcessing user {i+1}/{len(users)}: {email}")
                    
                    # Get workspace stats
                    workspace_stats = self.get_user_workspace_stats(email)
                    stats_list.append(workspace_stats)
                    
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
                if len(stats_list) % 10 == 0:
                    self._save_to_csv(stats_list, f"workspace_stats_partial_{len(stats_list)}.csv")
            
            # Save final results
            self._save_to_csv(stats_list, "workspace_stats_complete.csv")
            
            return pd.DataFrame(stats_list)
            
        except Exception as e:
            print(f"Error collecting workspace stats: {e}")
            
            # Save what we have
            if stats_list:
                self._save_to_csv(stats_list, "workspace_stats_error.csv")
            
            return pd.DataFrame(stats_list)
    
    def _save_to_csv(self, data, filename):
        """Helper method to save data to CSV."""
        if data:
            df = pd.DataFrame(data)
            csv_path = os.path.join(self.output_dir, filename)
            df.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"Saved {len(data)} records to {csv_path}")
        else:
            print("No data to save")

def main():
    parser = argparse.ArgumentParser(description='Combined Workspace Statistics Collector')
    parser.add_argument('--domain', required=True, help='Your Google Workspace domain')
    parser.add_argument('--service-account', required=True, help='Path to service account JSON file')
    parser.add_argument('--admin-email', required=True, help='Admin email for domain-wide delegation')
    parser.add_argument('--output-dir', default='workspace_stats', help='Directory to save exported data')
    parser.add_argument('--max-users', type=int, default=10, help='Maximum number of users to process (0 for all)')
    
    args = parser.parse_args()
    
    # Initialize and run collection
    try:
        collector = WorkspaceStatsCollector(
            domain=args.domain,
            service_account_file=args.service_account,
            admin_email=args.admin_email,
            output_dir=args.output_dir
        )
        
        # Authenticate and initialize services
        collector.authenticate()
        collector.initialize_services()
        
        # Collect workspace stats
        user_limit_msg = f"up to {args.max_users}" if args.max_users > 0 else "all"
        print(f"Starting workspace statistics collection for {user_limit_msg} users...")
        df = collector.collect_workspace_stats(max_users=args.max_users)
        
        # Show summary
        if not df.empty:
            print("\nCollection completed successfully")
            print(f"Total users processed: {len(df)}")
            print(f"Users with Gmail data: {df['Has_Gmail_Data'].sum()}")
            print(f"Users with Drive data: {df['Has_Drive_Data'].sum()}")
            
            # Gmail stats
            if len(df[df['Gmail_Storage_MB'] > 0]) > 0:
                print(f"\nGmail Statistics:")
                print(f"Users with Gmail storage > 0: {len(df[df['Gmail_Storage_MB'] > 0])}")
                print(f"Average Gmail storage (MB): {df['Gmail_Storage_MB'].mean():.2f}")
                print(f"Max Gmail storage (MB): {df['Gmail_Storage_MB'].max():.2f}")
                print(f"Total Gmail storage (GB): {df['Gmail_Storage_MB'].sum() / 1024:.2f}")
                
                if len(df[df['Gmail_Emails_Exchanged'] > 0]) > 0:
                    print(f"Users with Gmail activity: {len(df[df['Gmail_Emails_Exchanged'] > 0])}")
                    print(f"Total emails exchanged: {df['Gmail_Emails_Exchanged'].sum()}")
                    print(f"Average emails per user: {df['Gmail_Emails_Exchanged'].mean():.1f}")
            
            # Drive stats
            if len(df[df['Drive_Storage_MB'] > 0]) > 0:
                print(f"\nDrive Statistics:")
                print(f"Users with Drive storage > 0: {len(df[df['Drive_Storage_MB'] > 0])}")
                print(f"Average Drive storage (MB): {df['Drive_Storage_MB'].mean():.2f}")
                print(f"Max Drive storage (MB): {df['Drive_Storage_MB'].max():.2f}")
                print(f"Total Drive storage (GB): {df['Drive_Storage_MB'].sum() / 1024:.2f}")
                
                if len(df[df['Drive_Item_Count'] > 0]) > 0:
                    print(f"Users with Drive items > 0: {len(df[df['Drive_Item_Count'] > 0])}")
                    print(f"Average Drive item count: {df['Drive_Item_Count'].mean():.1f}")
                    print(f"Max Drive item count: {df['Drive_Item_Count'].max()}")
            
            # Combined stats
            if len(df[df['Total_Storage_MB'] > 0]) > 0:
                print(f"\nCombined Statistics:")
                print(f"Total storage across all users (GB): {df['Total_Storage_MB'].sum() / 1024:.2f}")
        else:
            print("No data collected")
        
    except Exception as e:
        print(f"Error in workspace statistics collection: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
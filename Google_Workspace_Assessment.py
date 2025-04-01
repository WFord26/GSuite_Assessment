#!/usr/bin/env python3
"""
Google Workspace Resource Exporter

This script exports various resources from a Google Workspace tenant including:
- Group information (basic details)
- Group memberships (detailed member lists)
- Buildings
- Rooms
- Equipment (calendar resources)

Requirements:
- Python 3.7+
- google-api-python-client
- google-auth
- pandas

Usage:
python Google_Workspace_Assessment.py 
    --domain yourdomain.com 
    --service-account /path/to/service-account.json 
    --admin-email admin@yourdomain.com 
    --output-dir workspace_exports
"""

import os
import csv
import json
import argparse
import time
from typing import Dict, Any, List, Tuple

import pandas as pd
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.errors import HttpError

class GoogleWorkspaceExporter:
    def __init__(self, domain: str, service_account_file: str, 
                 admin_email: str, output_dir: str = 'workspace_exports'):
        """
        Initialize Google Workspace Exporter.
        
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
        
        # Create output directories
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(self.raw_data_dir, exist_ok=True)
    
    def authenticate(self):
        """Authenticate with Google Workspace APIs."""
        try:
            # Use all required scopes for the exports
            scopes = [
                'https://www.googleapis.com/auth/admin.directory.user.readonly',
                'https://www.googleapis.com/auth/admin.directory.group.readonly',
                'https://www.googleapis.com/auth/admin.directory.group.member.readonly',
                'https://www.googleapis.com/auth/admin.directory.resource.calendar.readonly',
                'https://www.googleapis.com/auth/admin.directory.resource.calendar',
                'https://www.googleapis.com/auth/admin.directory.resource.calendar',
                'https://www.googleapis.com/auth/admin.directory.orgunit.readonly',
                'https://www.googleapis.com/auth/admin.directory.domain.readonly',
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
            self.services['groupssettings'] = build('groupssettings', 'v1', credentials=self.creds)
            print("Services initialized successfully")
        except Exception as e:
            print(f"Error initializing services: {e}")
            raise

    def export_groups(self):
        """
        Export all groups in the domain to a CSV file.
        
        Returns:
            Tuple containing DataFrame with groups data and path to the CSV file
        """
        print("\nExporting groups...")
        groups = []
        page_token = None
        
        try:
            while True:
                results = self.services['directory'].groups().list(
                    domain=self.domain,
                    maxResults=200,
                    pageToken=page_token,
                    fields='groups(id,email,name,description,adminCreated,directMembersCount,memberCount),nextPageToken'
                ).execute()
                
                current_groups = results.get('groups', [])
                if not current_groups:
                    break
                
                groups.extend(current_groups)
                print(f"Retrieved {len(groups)} groups so far...")
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
            
            # Save the raw data
            with open(os.path.join(self.raw_data_dir, 'groups_raw.json'), 'w') as f:
                json.dump(groups, f, indent=2)
            
            # Prepare data for CSV export
            groups_data = []
            for group in groups:
                group_data = {
                    'Group ID': group.get('id', ''),
                    'Group Email': group.get('email', ''),
                    'Group Name': group.get('name', ''),
                    'Description': group.get('description', ''),
                    'Admin Created': group.get('adminCreated', False),
                    'Direct Members Count': group.get('directMembersCount', 0),
                    'Member Count': group.get('memberCount', 0),
                }
                groups_data.append(group_data)
            
            # Create DataFrame and export to CSV
            df = pd.DataFrame(groups_data)
            csv_path = os.path.join(self.output_dir, 'groups_export.csv')
            df.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"Exported {len(groups_data)} groups to {csv_path}")
            
            return df, csv_path
            
        except Exception as e:
            print(f"Error exporting groups: {e}")
            return pd.DataFrame(), ""

    def export_group_memberships(self, groups_df=None):
        """
        Export all group memberships in the domain to a CSV file.
        
        Args:
            groups_df: Optional DataFrame with groups data from export_groups().
                       If not provided, will fetch groups first.
        
        Returns:
            Tuple containing DataFrame with memberships data and path to the CSV file
        """
        print("\nExporting group memberships...")
        
        # If groups_df not provided, fetch groups first
        if groups_df is None or groups_df.empty:
            groups_df, _ = self.export_groups()
        
        if groups_df.empty:
            print("No groups available to export memberships for.")
            return pd.DataFrame(), ""
        
        # Get all group emails
        all_memberships = []
        
        # For progress tracking
        total_groups = len(groups_df)
        processed = 0
        
        try:
            for _, group in groups_df.iterrows():
                group_email = group['Group Email']
                group_id = group['Group ID']
                group_name = group['Group Name']
                
                processed += 1
                if processed % 10 == 0 or processed == total_groups:
                    print(f"Processing group {processed}/{total_groups}: {group_email}")
                
                # Skip if no members
                if group['Member Count'] == 0:
                    continue
                
                # Get all members
                members = []
                page_token = None
                
                while True:
                    try:
                        results = self.services['directory'].members().list(
                            groupKey=group_email,
                            maxResults=200,
                            pageToken=page_token,
                            fields='members(id,email,role,type,status),nextPageToken'
                        ).execute()
                        
                        current_members = results.get('members', [])
                        if not current_members:
                            break
                        
                        members.extend(current_members)
                        
                        page_token = results.get('nextPageToken')
                        if not page_token:
                            break
                        
                    except HttpError as e:
                        if e.resp.status == 404:
                            print(f"Group not found: {group_email}")
                            break
                        else:
                            print(f"Error fetching members for group {group_email}: {e}")
                            break
                
                # Add each member to the all_memberships list
                for member in members:
                    membership = {
                        'Group ID': group_id,
                        'Group Email': group_email,
                        'Group Name': group_name,
                        'Member ID': member.get('id', ''),
                        'Member Email': member.get('email', ''),
                        'Member Role': member.get('role', ''),
                        'Member Type': member.get('type', ''),
                        'Member Status': member.get('status', '')
                    }
                    all_memberships.append(membership)
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
            
            # Create DataFrame and export to CSV
            df = pd.DataFrame(all_memberships)
            csv_path = os.path.join(self.output_dir, 'group_memberships_export.csv')
            df.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"Exported {len(all_memberships)} group memberships to {csv_path}")
            
            return df, csv_path
            
        except Exception as e:
            print(f"Error exporting group memberships: {e}")
            return pd.DataFrame(), ""

    def export_buildings(self):
        """
        Export all buildings in the domain to a CSV file.
        
        Returns:
            Tuple containing DataFrame with buildings data and path to the CSV file
        """
        print("\nExporting buildings...")
        buildings = []
        
        try:
            results = self.services['directory'].resources().buildings().list(
                customer='my_customer',
                fields='buildings(buildingId,buildingName,description,floorNames)'
            ).execute()
            
            buildings = results.get('buildings', [])
            
            # Save the raw data
            with open(os.path.join(self.raw_data_dir, 'buildings_raw.json'), 'w') as f:
                json.dump(buildings, f, indent=2)
            
            # Prepare data for CSV export
            buildings_data = []
            for building in buildings:
                # Convert floorNames list to a comma-separated string
                floor_names = ','.join(building.get('floorNames', []))
                
                building_data = {
                    'kind': building.get('kind', ''),
                    'etags': building.get('etags', ''),
                    'buildingId': building.get('buildingId', ''),
                    'buildingName': building.get('buildingName', ''),
                    'description': building.get('description', ''),
                    'floorNames': floor_names
                }
                buildings_data.append(building_data)
            
            # Create DataFrame and export to CSV
            df = pd.DataFrame(buildings_data)
            csv_path = os.path.join(self.output_dir, 'buildings_export.csv')
            df.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"Exported {len(buildings_data)} buildings to {csv_path}")
            
            return df, csv_path
            
        except Exception as e:
            print(f"Error exporting buildings: {e}")
            return pd.DataFrame(), ""

    def export_rooms(self):
        """
        Export all rooms (calendar resources) in the domain to a CSV file.
        
        Returns:
            Tuple containing DataFrame with rooms data and path to the CSV file
        """
        print("\nExporting rooms...")
        rooms = []
        
        try:
            # Get all calendar resources
            results = self.services['directory'].resources().calendars().list(
                customer='my_customer',
                fields='items(resourceId,resourceName,resourceEmail,resourceType,buildingId,floorName,capacity,featureInstances)'
            ).execute()
            
            calendar_resources = results.get('items', [])
            
            # Save the raw data
            with open(os.path.join(self.raw_data_dir, 'calendar_resources_raw.json'), 'w') as f:
                json.dump(calendar_resources, f, indent=2)
            
            # Filter for rooms and prepare data for CSV export
            rooms_data = []
            for resource in calendar_resources:
                # Only include rooms (not equipment)
                if resource.get('resourceType') in ['Conference Room', 'Meeting Space', 'Room']:
                    # Extract features
                    features = []
                    if 'featureInstances' in resource:
                        for feature in resource.get('featureInstances', []):
                            if 'feature' in feature and 'name' in feature['feature']:
                                features.append(feature['feature']['name'])
                    
                    features_str = ', '.join(features)
                    
                    room_data = {
                        'Resource ID': resource.get('resourceId', ''),
                        'Resource Name': resource.get('resourceName', ''),
                        'Email': resource.get('resourceEmail', ''),
                        'Building ID': resource.get('buildingId', ''),
                        'Floor Name': resource.get('floorName', ''),
                        'Capacity': resource.get('capacity', ''),
                        'Resource Type': resource.get('resourceType', ''),
                        'Features': features_str
                    }
                    rooms_data.append(room_data)
            
            # Create DataFrame and export to CSV
            df = pd.DataFrame(rooms_data)
            csv_path = os.path.join(self.output_dir, 'rooms_export.csv')
            df.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"Exported {len(rooms_data)} rooms to {csv_path}")
            
            return df, csv_path
            
        except Exception as e:
            print(f"Error exporting rooms: {e}")
            return pd.DataFrame(), ""

    def export_equipment(self):
        """
        Export all equipment (calendar resources) in the domain to a CSV file.
        
        Returns:
            Tuple containing DataFrame with equipment data and path to the CSV file
        """
        print("\nExporting equipment...")
        
        try:
            # Get all calendar resources
            results = self.services['directory'].resources().calendars().list(
                customer='my_customer',
                fields='items(resourceId,resourceName,resourceEmail,resourceType,featureInstances)'
            ).execute()
            
            calendar_resources = results.get('items', [])
            
            # Filter for equipment and prepare data for CSV export
            equipment_data = []
            for resource in calendar_resources:
                # Only include equipment (not rooms)
                if resource.get('resourceType') not in ['Conference Room', 'Meeting Space', 'Room']:
                    # Extract features
                    features = []
                    if 'featureInstances' in resource:
                        for feature in resource.get('featureInstances', []):
                            if 'feature' in feature and 'name' in feature['feature']:
                                features.append(feature['feature']['name'])
                    
                    features_str = ', '.join(features)
                    
                    equipment_item = {
                        'Resource ID': resource.get('resourceId', ''),
                        'Resource Name': resource.get('resourceName', ''),
                        'Email': resource.get('resourceEmail', ''),
                        'Resource Type': resource.get('resourceType', ''),
                        'Features': features_str
                    }
                    equipment_data.append(equipment_item)
            
            # Create DataFrame and export to CSV
            df = pd.DataFrame(equipment_data)
            csv_path = os.path.join(self.output_dir, 'equipment_export.csv')
            df.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"Exported {len(equipment_data)} equipment items to {csv_path}")
            
            return df, csv_path
            
        except Exception as e:
            print(f"Error exporting equipment: {e}")
            return pd.DataFrame(), ""

    def run_all_exports(self):
        """Run all export functions and return a summary of results."""
        print("\nStarting Google Workspace exports...")
        
        results = {}
        
        # Export groups
        groups_df, groups_path = self.export_groups()
        results['Groups'] = {'count': len(groups_df), 'path': groups_path}
        
        # Export group memberships
        memberships_df, memberships_path = self.export_group_memberships(groups_df)
        results['Group Memberships'] = {'count': len(memberships_df), 'path': memberships_path}
        
        # Export buildings
        buildings_df, buildings_path = self.export_buildings()
        results['Buildings'] = {'count': len(buildings_df), 'path': buildings_path}
        
        # Export rooms
        rooms_df, rooms_path = self.export_rooms()
        results['Rooms'] = {'count': len(rooms_df), 'path': rooms_path}
        
        # Export equipment
        equipment_df, equipment_path = self.export_equipment()
        results['Equipment'] = {'count': len(equipment_df), 'path': equipment_path}
        
        return results


def main():
    parser = argparse.ArgumentParser(description='Google Workspace Resource Exporter')
    parser.add_argument('--domain', required=True, help='Your Google Workspace domain')
    parser.add_argument('--service-account', required=True, help='Path to service account JSON file')
    parser.add_argument('--admin-email', required=True, help='Admin email for domain-wide delegation')
    parser.add_argument('--output-dir', default='workspace_exports', help='Directory to save exported data')
    
    args = parser.parse_args()
    
    # Initialize and run exports
    try:
        exporter = GoogleWorkspaceExporter(
            domain=args.domain,
            service_account_file=args.service_account,
            admin_email=args.admin_email,
            output_dir=args.output_dir
        )
        
        # Authenticate and initialize services
        exporter.authenticate()
        exporter.initialize_services()
        
        # Run all exports
        print(f"Starting Google Workspace exports for domain {args.domain}...")
        results = exporter.run_all_exports()
        
        # Print summary
        print("\n----- Export Summary -----")
        for resource_type, data in results.items():
            print(f"{resource_type}: {data['count']} items exported to {data['path']}")
        
    except Exception as e:
        print(f"Error in Google Workspace exports: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
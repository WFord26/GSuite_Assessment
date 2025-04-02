# Google Workspace Administration Tools

This repository contains a collection of Python scripts to help Google Workspace administrators audit, assess, and manage their organization's resources. These tools provide detailed exports and analysis capabilities beyond what's available in the Google Admin Console UI.

## Contents

- **Advanced Shared Drive Finder** - Locate all Shared Drives in your organization using multiple methods
- **Google Workspace Assessment** - Export groups, memberships, buildings, rooms, and calendar resources
- **Google Workspace Groups Export** - Export only groups and their memberships
- **Google Users Assessment** - Collect Gmail and Drive usage statistics for users
- **Google Mailbox Permissions Exporter** - Export mail delegations, forwarding, and access settings

## Prerequisites

### Python Setup

1. These scripts require Python 3.7 or newer. Check your Python version:

   ```bash
   python --version
   ```

2. If needed, download and install Python from [python.org](https://www.python.org/downloads/)

### Required Libraries

Install all required Python packages:

```bash
pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2 pandas
```

## Google Cloud Project Setup

### Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Click on the project dropdown at the top of the page
3. Click "New Project"
4. Enter a project name (e.g., "Workspace Admin Tools")
5. Click "Create"
6. Once created, select your new project from the dropdown

### Enable Required APIs

1. In your Google Cloud project, go to "APIs & Services" > "Library"
2. Search for and enable each of these APIs:
   - Admin SDK API
   - Google Drive API
   - Gmail API
   - Google Sheets API (if needed)

### Create a Service Account

1. Go to "IAM & Admin" > "Service Accounts"
2. Click "Create Service Account"
3. Enter a service account name (e.g., "workspace-admin-tools")
4. Add a description (optional)
5. Click "Create and Continue"
6. For the "Grant this service account access to project" step, you can skip by clicking "Continue"
7. For the "Grant users access to this service account" step, click "Done"
8. Find your new service account in the list, click the three dots menu, and select "Manage keys"
9. Click "Add Key" > "Create new key"
10. Select "JSON" and click "Create"
11. The key file will download automatically - keep this secure!

### Set Up Domain-Wide Delegation

1. Go to your Google Workspace Admin Console at [admin.google.com](https://admin.google.com)
2. Navigate to Security > Access and data control > API controls
3. In the "Domain-wide Delegation" section, click "Manage Domain Wide Delegation"
4. Click "Add new"
5. Enter the Client ID from your service account (found in the service account details page)
6. Add the following OAuth scopes (or copy the complete list from below):

```
https://www.googleapis.com/auth/admin.directory.user.readonly
https://www.googleapis.com/auth/admin.directory.group.readonly
https://www.googleapis.com/auth/admin.directory.group.member.readonly
https://www.googleapis.com/auth/admin.directory.resource.calendar.readonly
https://www.googleapis.com/auth/admin.directory.orgunit.readonly
https://www.googleapis.com/auth/admin.directory.domain.readonly
https://www.googleapis.com/auth/gmail.settings.basic
https://www.googleapis.com/auth/gmail.settings.sharing
https://www.googleapis.com/auth/drive
https://www.googleapis.com/auth/drive.readonly
https://www.googleapis.com/auth/admin.reports.audit.readonly
https://www.googleapis.com/auth/admin.reports.usage.readonly
https://apps-apis.google.com/a/feeds/emailsettings/2.0/
```

7. Click "Authorize"

## Complete List of Required OAuth Scopes

These are all the possible scopes you might need for the tools in this repository:

```
https://www.googleapis.com/auth/admin.directory.user.readonly
https://www.googleapis.com/auth/admin.directory.group.readonly
https://www.googleapis.com/auth/admin.directory.group.member.readonly
https://www.googleapis.com/auth/admin.directory.resource.calendar.readonly
https://www.googleapis.com/auth/admin.directory.resource.calendar
https://www.googleapis.com/auth/admin.directory.orgunit.readonly
https://www.googleapis.com/auth/admin.directory.domain.readonly
https://www.googleapis.com/auth/gmail.settings.basic
https://www.googleapis.com/auth/gmail.settings.sharing
https://www.googleapis.com/auth/drive
https://www.googleapis.com/auth/drive.readonly
https://www.googleapis.com/auth/admin.reports.audit.readonly
https://www.googleapis.com/auth/admin.reports.usage.readonly
https://apps-apis.google.com/a/feeds/emailsettings/2.0/
```

Note that each script only uses a subset of these permissions. You can review each script to determine the minimum required scopes if you prefer to limit permissions.

## Using the Scripts

### Common Parameters

All scripts require these basic parameters:
- `--domain` - Your Google Workspace domain (e.g., example.com)
- `--service-account` - Path to your service account JSON key file
- `--admin-email` - Email of an admin with appropriate permissions

### Advanced Shared Drive Finder

Locates all Shared Drives using multiple methods:

```bash
python advanced_shared_drive_finder.py --service-account /path/to/service-account.json --admin-email admin@yourdomain.com
```

Additional options:
- `--deep-search` - Enable more thorough searching (slower)
- `--output-file` - Specify custom output file (default: found_shared_drives.json)

### Google Workspace Assessment

Exports groups, memberships, buildings, rooms, and calendar resources:

```bash
python google_workspace_assessment.py --domain yourdomain.com --service-account /path/to/service-account.json --admin-email admin@yourdomain.com --output-dir workspace_exports
```

The script will create a directory with the following CSV files:
- groups_export.csv
- group_memberships_export.csv
- buildings_export.csv
- rooms_export.csv
- equipment_export.csv

### Google Workspace Groups Export

Simplified version that only exports groups and memberships:

```bash
python google_workspace_groups_export.py --domain yourdomain.com --service-account /path/to/service-account.json --admin-email admin@yourdomain.com
```

Output will be saved to:
- workspace_exports/groups_export.csv
- workspace_exports/group_memberships_export.csv

### Google Users Assessment

Collects Gmail and Drive usage statistics for users:

```bash
python google_users_assessment.py --domain yourdomain.com --service-account /path/to/service-account.json --admin-email admin@yourdomain.com --output-dir workspace_stats --max-users 10
```

Additional options:
- `--max-users` - Maximum number of users to process (0 for all)

Output includes:
- workspace_stats/workspace_stats_complete.csv - Contains Gmail and Drive usage metrics
- Raw data in JSON format for detailed analysis

### Google Mailbox Permissions Exporter

Exports mail delegation, forwarding, and access settings:

```bash
python google_mailbox_permissions.py --domain yourdomain.com --service-account /path/to/service-account.json --admin-email admin@yourdomain.com --output-dir mailbox_permissions --max-users 10
```

Additional options:
- `--max-users` - Maximum number of users to process (0 for all)

Output includes:
- mailbox_permissions/mailbox_permissions_complete.csv - Main permissions report
- mailbox_permissions/detailed_delegates.csv - Delegate relationships
- mailbox_permissions/detailed_forwarding.csv - Email forwarding settings

## Troubleshooting

### Permission Errors

If you see errors like "Request had insufficient authentication scopes":
1. Verify that you've enabled all required scopes in domain-wide delegation
2. Check that your service account has the correct OAuth scopes
3. Ensure your admin user has appropriate permissions in Google Workspace

### Rate Limiting

These scripts include delays to prevent hitting API rate limits. If you still encounter rate limit errors:
1. Increase the delay by modifying the `time.sleep()` values in the scripts
2. Run the scripts during off-peak hours
3. Process fewer users at a time using the `--max-users` parameter

### Script Crashes

If a script crashes during execution:
1. Check the error message for specific API issues
2. Many scripts save partial results, so you can often recover some data
3. For large exports, consider running with a smaller `--max-users` value

## Best Practices

- Store service account key files securely
- Use a dedicated service account for these administrative scripts
- Review the permissions needed and only grant what's necessary
- Run these scripts periodically to maintain accurate records
- Store exports securely as they may contain sensitive information

## Additional Resources

- [Google Workspace Admin SDK Documentation](https://developers.google.com/admin-sdk)
- [Google API Client Library for Python](https://github.com/googleapis/google-api-python-client)
- [Google Workspace API Scopes](https://developers.google.com/identity/protocols/oauth2/scopes)

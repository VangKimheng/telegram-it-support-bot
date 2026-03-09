#!/usr/bin/env python3
"""
Google Sheets Integration for IT Support Bot
Syncs cases to Google Sheets in real-time
"""

import sqlite3
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import time

class GoogleSheetsSyncer:
    """Syncs IT support cases to Google Sheets"""
    
    def __init__(self, credentials_file='credentials.json', spreadsheet_url=None):
        """
        Initialize Google Sheets connection
        
        Args:
            credentials_file: Path to Google service account credentials JSON
            spreadsheet_url: URL of the Google Sheet to sync to
        """
        self.credentials_file = credentials_file
        self.spreadsheet_url = spreadsheet_url
        self.db_path = 'it_support.db'
        
        # Initialize Google Sheets connection
        self.setup_google_sheets()
    
    def setup_google_sheets(self):
        """Setup Google Sheets API connection"""
        try:
            # Define scope
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Authenticate
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                self.credentials_file, scope
            )
            self.client = gspread.authorize(creds)
            
            print("✅ Google Sheets authentication successful")
        except Exception as e:
            print(f"❌ Google Sheets authentication failed: {e}")
            print("\nSetup instructions:")
            print("1. Go to https://console.cloud.google.com")
            print("2. Create a new project")
            print("3. Enable Google Sheets API")
            print("4. Create Service Account credentials")
            print("5. Download JSON key as 'credentials.json'")
            self.client = None
    
    def create_or_get_spreadsheet(self, name="IT Support Cases"):
        """Create new spreadsheet or get existing one"""
        try:
            if self.spreadsheet_url:
                # Open existing spreadsheet
                self.sheet = self.client.open_by_url(self.spreadsheet_url)
            else:
                # Create new spreadsheet
                self.sheet = self.client.create(name)
                print(f"✅ Created spreadsheet: {self.sheet.url}")
                print(f"📋 Add this URL to your config!")
            
            return self.sheet
        except Exception as e:
            print(f"❌ Error with spreadsheet: {e}")
            return None
    
    def setup_headers(self):
        """Setup spreadsheet headers"""
        try:
            # Get or create worksheets
            try:
                cases_sheet = self.sheet.worksheet("All Cases")
            except:
                cases_sheet = self.sheet.add_worksheet("All Cases", rows=1000, cols=15)
            
            # Set headers
            headers = [
                'Case ID', 'Username', 'Full Name', 'Category', 'Status',
                'IT Executive', 'Created Date', 'Closed Date', 
                'Key Finding', 'Solution', 'Support Type', 'Time Taken',
                'User ID', 'Last Updated'
            ]
            
            cases_sheet.update('A1:N1', [headers])
            
            # Format headers
            cases_sheet.format('A1:N1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.4, 'green': 0.49, 'blue': 0.92}
            })
            
            # Create Summary sheet
            try:
                summary_sheet = self.sheet.worksheet("Summary")
            except:
                summary_sheet = self.sheet.add_worksheet("Summary", rows=100, cols=5)
            
            summary_headers = ['Metric', 'Value', 'Last Updated']
            summary_sheet.update('A1:C1', [summary_headers])
            summary_sheet.format('A1:C1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.4, 'green': 0.49, 'blue': 0.92}
            })
            
            print("✅ Spreadsheet headers configured")
        except Exception as e:
            print(f"❌ Error setting up headers: {e}")
    
    def sync_all_cases(self):
        """Sync all cases from database to Google Sheets"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    case_id, username, full_name, category, status,
                    it_executive, created_at, closed_at,
                    key_finding, solution, support_type, completion_time,
                    user_id
                FROM cases
                ORDER BY case_id
            """)
            
            cases = cursor.fetchall()
            conn.close()
            
            # Get worksheet
            cases_sheet = self.sheet.worksheet("All Cases")
            
            # Prepare data
            data = []
            for case in cases:
                row = list(case) + [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                data.append(row)
            
            # Clear existing data (except headers)
            cases_sheet.clear()
            
            # Write headers
            self.setup_headers()
            
            # Write data
            if data:
                cases_sheet.update(f'A2:N{len(data)+1}', data)
            
            print(f"✅ Synced {len(data)} cases to Google Sheets")
            return True
            
        except Exception as e:
            print(f"❌ Error syncing cases: {e}")
            return False
    
    def sync_summary_stats(self):
        """Sync summary statistics to Google Sheets"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get stats
            cursor.execute("SELECT COUNT(*) FROM cases")
            total = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM cases WHERE status = 'open'")
            open_cases = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM cases WHERE status = 'closed'")
            closed = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT AVG((julianday(closed_at) - julianday(created_at)) * 24) 
                FROM cases WHERE status = 'closed'
            """)
            avg_time = cursor.fetchone()[0] or 0
            
            conn.close()
            
            # Get summary sheet
            summary_sheet = self.sheet.worksheet("Summary")
            
            # Prepare summary data
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            summary_data = [
                ['Total Cases', total, timestamp],
                ['Open Cases', open_cases, timestamp],
                ['Closed Cases', closed, timestamp],
                ['Resolution Rate (%)', round(closed/total*100, 1) if total > 0 else 0, timestamp],
                ['Avg Resolution Time (hours)', round(avg_time, 2), timestamp]
            ]
            
            # Update summary
            summary_sheet.update('A2:C6', summary_data)
            
            print("✅ Summary statistics updated")
            return True
            
        except Exception as e:
            print(f"❌ Error syncing summary: {e}")
            return False
    
    def sync_single_case(self, case_id):
        """Sync a single case (for real-time updates)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    case_id, username, full_name, category, status,
                    it_executive, created_at, closed_at,
                    key_finding, solution, support_type, completion_time,
                    user_id
                FROM cases
                WHERE case_id = ?
            """, (case_id,))
            
            case = cursor.fetchone()
            conn.close()
            
            if not case:
                print(f"⚠️  Case {case_id} not found")
                return False
            
            # Get worksheet
            cases_sheet = self.sheet.worksheet("All Cases")
            
            # Find row or append
            try:
                cell = cases_sheet.find(str(case_id))
                row_num = cell.row
            except:
                # Case doesn't exist, append
                row_num = len(cases_sheet.get_all_values()) + 1
            
            # Prepare data
            row_data = list(case) + [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            
            # Update row
            cases_sheet.update(f'A{row_num}:N{row_num}', [row_data])
            
            print(f"✅ Synced case #{case_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error syncing case: {e}")
            return False
    
    def auto_sync_loop(self, interval=60):
        """
        Continuously sync data at specified interval
        
        Args:
            interval: Seconds between syncs (default: 60)
        """
        print(f"🔄 Starting auto-sync every {interval} seconds...")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                print(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Syncing...")
                self.sync_all_cases()
                self.sync_summary_stats()
                print(f"✅ Sync complete. Next sync in {interval} seconds.")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n⏹️  Auto-sync stopped")

def main():
    """Main function for standalone usage"""
    import sys
    
    print("=" * 60)
    print("📊 Google Sheets Sync for IT Support Bot")
    print("=" * 60)
    
    # Load config
    try:
        with open('sheets_config.json', 'r') as f:
            config = json.load(f)
        credentials_file = config.get('credentials_file', 'credentials.json')
        spreadsheet_url = config.get('spreadsheet_url')
    except:
        credentials_file = 'credentials.json'
        spreadsheet_url = None
    
    # Initialize syncer
    syncer = GoogleSheetsSyncer(credentials_file, spreadsheet_url)
    
    if not syncer.client:
        print("\n⚠️  Google Sheets not configured. Exiting.")
        return
    
    # Create/get spreadsheet
    sheet = syncer.create_or_get_spreadsheet()
    if not sheet:
        print("❌ Could not access spreadsheet")
        return
    
    # Setup headers
    syncer.setup_headers()
    
    # Menu
    while True:
        print("\n" + "=" * 60)
        print("Options:")
        print("1. Sync all cases now")
        print("2. Sync summary stats")
        print("3. Auto-sync (continuous)")
        print("4. Sync single case")
        print("5. Exit")
        print("=" * 60)
        
        choice = input("Select option (1-5): ").strip()
        
        if choice == '1':
            syncer.sync_all_cases()
        elif choice == '2':
            syncer.sync_summary_stats()
        elif choice == '3':
            interval = input("Sync interval in seconds (default 60): ").strip()
            interval = int(interval) if interval.isdigit() else 60
            syncer.auto_sync_loop(interval)
        elif choice == '4':
            case_id = input("Enter case ID: ").strip()
            if case_id.isdigit():
                syncer.sync_single_case(int(case_id))
        elif choice == '5':
            print("\n👋 Goodbye!")
            break
        else:
            print("❌ Invalid option")

if __name__ == '__main__':
    main()

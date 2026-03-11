#!/usr/bin/env python3
"""
IT Support Dashboard - Web Interface
Real-time case management with analytics and reporting
"""

from flask import Flask, render_template, jsonify, request, send_file
from flask_socketio import SocketIO, emit
import sqlite3
import json
import logging
from datetime import datetime, timedelta
import pandas as pd
from io import BytesIO
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
socketio = SocketIO(app, cors_allowed_origins="*")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE = 'it_support.db'

class DashboardManager:
    """Manages dashboard data and statistics"""
    
    def __init__(self, db_path=DATABASE):
        self.db_path = db_path
    
    def get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def get_dashboard_stats(self):
        """Get overall statistics for dashboard"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Total cases
        cursor.execute("SELECT COUNT(*) FROM cases")
        total_cases = cursor.fetchone()[0]
        
        # Open cases
        cursor.execute("SELECT COUNT(*) FROM cases WHERE status = 'open'")
        open_cases = cursor.fetchone()[0]
        
        # Closed cases
        cursor.execute("SELECT COUNT(*) FROM cases WHERE status = 'closed'")
        closed_cases = cursor.fetchone()[0]
        
        # Cases today
        cursor.execute("SELECT COUNT(*) FROM cases WHERE DATE(created_at) = DATE('now')")
        today_cases = cursor.fetchone()[0]
        
        # Cases this week
        cursor.execute("""
            SELECT COUNT(*) FROM cases 
            WHERE created_at >= datetime('now', '-7 days')
        """)
        week_cases = cursor.fetchone()[0]
        
        # Average resolution time (in hours)
        cursor.execute("""
            SELECT AVG((julianday(closed_at) - julianday(created_at)) * 24) 
            FROM cases 
            WHERE status = 'closed'
        """)
        avg_time = cursor.fetchone()[0] or 0
        
        # Resolution rate
        resolution_rate = (closed_cases / total_cases * 100) if total_cases > 0 else 0
        
        conn.close()
        
        return {
            'total_cases': total_cases,
            'open_cases': open_cases,
            'closed_cases': closed_cases,
            'today_cases': today_cases,
            'week_cases': week_cases,
            'avg_resolution_time': round(avg_time, 2),
            'resolution_rate': round(resolution_rate, 1)
        }
    
    def get_category_breakdown(self):
        """Get cases by category"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                category,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open,
                SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed
            FROM cases
            GROUP BY category
        """)
        
        categories = []
        for row in cursor.fetchall():
            categories.append({
                'category': row[0],
                'total': row[1],
                'open': row[2],
                'closed': row[3]
            })
        
        conn.close()
        return categories
    
    def get_it_performance(self):
        """Get IT executive performance"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                it_executive,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open,
                SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed,
                ROUND(AVG(CASE 
                    WHEN status = 'closed' 
                    THEN (julianday(closed_at) - julianday(created_at)) * 24 
                    ELSE NULL 
                END), 2) as avg_hours
            FROM cases
            GROUP BY it_executive
        """)
        
        performance = []
        for row in cursor.fetchall():
            performance.append({
                'executive': row[0],
                'total': row[1],
                'open': row[2],
                'closed': row[3],
                'avg_hours': row[4] or 0
            })
        
        conn.close()
        return performance
    
    def get_recent_cases(self, limit=10):
        """Get recent cases"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                case_id, username, full_name, category, status, 
                created_at, it_executive
            FROM cases
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        
        cases = []
        for row in cursor.fetchall():
            cases.append({
                'case_id': row[0],
                'username': row[1],
                'full_name': row[2],
                'category': row[3],
                'status': row[4],
                'created_at': row[5],
                'it_executive': row[6]
            })
        
        conn.close()
        return cases
    
    def get_daily_stats(self, days=30):
        """Get daily statistics for charts"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as created,
                SUM(CASE WHEN DATE(closed_at) = DATE(created_at) AND status = 'closed' 
                    THEN 1 ELSE 0 END) as closed_same_day
            FROM cases
            WHERE created_at >= datetime('now', '-{} days')
            GROUP BY DATE(created_at)
            ORDER BY date
        """.format(days))
        
        daily_stats = []
        for row in cursor.fetchall():
            daily_stats.append({
                'date': row[0],
                'created': row[1],
                'closed_same_day': row[2]
            })
        
        conn.close()
        return daily_stats
    
    def get_case_details(self, case_id):
        """Get detailed case information"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get case info
        cursor.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,))
        case = cursor.fetchone()
        
        if not case:
            conn.close()
            return None
        
        # Get case messages
        cursor.execute("""
            SELECT message_type, message_text, created_at 
            FROM case_messages 
            WHERE case_id = ?
            ORDER BY created_at
        """, (case_id,))
        messages = cursor.fetchall()
        
        conn.close()
        
        return {
            'case_id': case[0],
            'user_id': case[1],
            'username': case[2],
            'full_name': case[3],
            'category': case[4],
            'status': case[5],
            'created_at': case[6],
            'closed_at': case[7],
            'it_executive': case[8],
            'key_finding': case[9],
            'solution': case[10],
            'support_type': case[11],
            'completion_time': case[12],
            'messages': [{'type': m[0], 'text': m[1], 'time': m[2]} for m in messages]
        }
    
    def export_to_excel(self):
        """Export all cases to Excel"""
        conn = self.get_connection()
        
        # Read data
        df_cases = pd.read_sql_query("""
            SELECT 
                case_id as 'Case ID',
                username as 'Username',
                full_name as 'Full Name',
                category as 'Category',
                status as 'Status',
                it_executive as 'IT Executive',
                created_at as 'Created Date',
                closed_at as 'Closed Date',
                key_finding as 'Key Finding',
                solution as 'Solution',
                support_type as 'Support Type',
                completion_time as 'Time Taken'
            FROM cases
            ORDER BY created_at DESC
        """, conn)
        
        conn.close()
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_cases.to_excel(writer, sheet_name='All Cases', index=False)
        
        output.seek(0)
        return output

dashboard = DashboardManager()

# Routes
@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/stats')
def api_stats():
    """API endpoint for dashboard statistics"""
    stats = dashboard.get_dashboard_stats()
    return jsonify(stats)

@app.route('/api/categories')
def api_categories():
    """API endpoint for category breakdown"""
    categories = dashboard.get_category_breakdown()
    return jsonify(categories)

@app.route('/api/performance')
def api_performance():
    """API endpoint for IT performance"""
    performance = dashboard.get_it_performance()
    return jsonify(performance)

@app.route('/api/recent-cases')
def api_recent_cases():
    """API endpoint for recent cases"""
    limit = request.args.get('limit', 10, type=int)
    cases = dashboard.get_recent_cases(limit)
    return jsonify(cases)

@app.route('/api/daily-stats')
def api_daily_stats():
    """API endpoint for daily statistics"""
    days = request.args.get('days', 30, type=int)
    stats = dashboard.get_daily_stats(days)
    return jsonify(stats)

@app.route('/api/case/<int:case_id>')
def api_case_details(case_id):
    """API endpoint for case details"""
    case = dashboard.get_case_details(case_id)
    if case:
        return jsonify(case)
    return jsonify({'error': 'Case not found'}), 404

@app.route('/api/export/excel')
def export_excel():
    """Export cases to Excel"""
    output = dashboard.export_to_excel()
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'IT_Support_Cases_{datetime.now().strftime("%Y%m%d")}.xlsx'
    )

@app.route('/api/alert/<int:case_id>', methods=['POST'])
def alert_case(case_id):
    """Send alert to IT staff via Telegram bot"""
    try:
        conn = dashboard.get_connection()
        cursor = conn.cursor()

        # Ensure alert tracking columns exist for older databases
        cursor.execute("PRAGMA table_info(cases)")
        case_columns = {row[1] for row in cursor.fetchall()}
        if 'alert_count' not in case_columns:
            cursor.execute("ALTER TABLE cases ADD COLUMN alert_count INTEGER DEFAULT 0")
        if 'last_alert' not in case_columns:
            cursor.execute("ALTER TABLE cases ADD COLUMN last_alert TEXT")
        conn.commit()

        # Get case details
        cursor.execute('SELECT * FROM cases WHERE case_id = ?', (case_id,))
        case = cursor.fetchone()

        if not case:
            conn.close()
            return jsonify({'error': 'Case not found'}), 404

        if case[5] == 'closed':  # status column
            conn.close()
            return jsonify({'error': 'Case already closed'}), 400

        # Increment alert count
        cursor.execute('''
            UPDATE cases
            SET alert_count = COALESCE(alert_count, 0) + 1,
                last_alert = CURRENT_TIMESTAMP
            WHERE case_id = ?
        ''', (case_id,))
        conn.commit()

        # Get updated alert count
        cursor.execute('SELECT COALESCE(alert_count, 0) FROM cases WHERE case_id = ?', (case_id,))
        alert_count = cursor.fetchone()[0]
        conn.close()

        logger.info(f"✅ Alert triggered for case #{case_id} from dashboard")

        return jsonify({
            'success': True,
            'message': f'Alert sent to {case[8]}',
            'alert_count': alert_count
        })

    except Exception as e:
        logger.error(f"❌ Error alerting case: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/cases')
def cases_page():
    """Cases management page"""
    return render_template('cases.html')

@app.route('/reports')
def reports_page():
    """Reports page"""
    return render_template('reports.html')

# WebSocket events for real-time updates
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    emit('connected', {'data': 'Connected to dashboard'})

@socketio.on('request_update')
def handle_update_request():
    """Handle update request from client"""
    stats = dashboard.get_dashboard_stats()
    emit('stats_update', stats)

def notify_new_case(case_id):
    """Notify all clients of new case"""
    case = dashboard.get_case_details(case_id)
    socketio.emit('new_case', case)

def notify_case_closed(case_id):
    """Notify all clients of closed case"""
    case = dashboard.get_case_details(case_id)
    socketio.emit('case_closed', case)

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    print("=" * 60)
    print("🌐 IT Support Dashboard Starting...")
    print("=" * 60)
    print("📊 Dashboard: http://localhost:5000")
    print("📋 Cases: http://localhost:5000/cases")
    print("📈 Reports: http://localhost:5000/reports")
    print("📥 Export: http://localhost:5000/api/export/excel")
    print("=" * 60)
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)

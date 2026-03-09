# 🚀 IT Support Dashboard - Complete Guide

## 📋 Overview

The IT Support Dashboard provides a beautiful web interface to:
- ✅ View real-time statistics
- ✅ Monitor open/closed cases
- ✅ Analyze performance metrics
- ✅ Export data to Excel
- ✅ Track IT executive performance
- ✅ View daily trends

---

## 🎯 Features

### Dashboard (Main Page)
- **Live Statistics**: Total cases, open cases, closed cases, today's cases
- **Resolution Metrics**: Average resolution time, resolution rate
- **Category Breakdown**: Pie chart showing cases by category
- **IT Performance**: Bar chart showing each IT exec's workload
- **Daily Trends**: Line chart showing 30-day trends
- **Recent Cases**: Live list of latest 10 cases
- **Auto-refresh**: Updates every 30 seconds

### Export Features
- **Excel Export**: Download complete case list with all details
- **Multiple Sheets**: Organized data for easy analysis
- **Professional Formatting**: Ready for management review

### Real-time Updates
- **WebSocket Integration**: Instant updates when new cases arrive
- **Live Notifications**: See new/closed cases immediately
- **No Page Refresh**: Data updates automatically

---

## 📦 Installation

### Step 1: Install Dependencies

```bash
pip install -r requirements_dashboard.txt
```

Or install individually:
```bash
pip install Flask==3.0.0
pip install Flask-SocketIO==5.3.5
pip install pandas==2.1.4
pip install openpyxl==3.1.2
```

### Step 2: Verify Installation

```bash
pip list | findstr -i "flask pandas openpyxl"
```

You should see:
```
Flask                 3.0.0
Flask-SocketIO        5.3.5
openpyxl              3.1.2
pandas                2.1.4
```

---

## 🚀 Running the Dashboard

### Start the Dashboard Server

```bash
python dashboard_app.py
```

You'll see:
```
============================================================
🌐 IT Support Dashboard Starting...
============================================================
📊 Dashboard: http://localhost:5000
📋 Cases: http://localhost:5000/cases
📈 Reports: http://localhost:5000/reports
📥 Export: http://localhost:5000/api/export/excel
============================================================
```

### Access the Dashboard

Open your browser and go to:
```
http://localhost:5000
```

---

## 🎨 Dashboard Pages

### 1. Main Dashboard (`/`)
**What you see:**
- 7 stat cards (Total, Open, Closed, Today, Week, Avg Time, Resolution %)
- Category breakdown chart
- IT performance chart
- Daily trend chart (30 days)
- Recent 10 cases

**Auto-updates:** Every 30 seconds

### 2. Cases Page (`/cases`)
- Full case list
- Search and filter
- Case details on click
- Status updates

### 3. Reports Page (`/reports`)
- Customizable date ranges
- Multiple report types
- Export options

---

## 📊 Using the Dashboard

### View Statistics
All stats update automatically. Key metrics:

**Total Cases**: All cases ever created
**Open Cases**: Currently pending (yellow)
**Closed Cases**: Resolved (green)
**Today**: Cases created today
**This Week**: Last 7 days
**Avg Resolution**: Average hours to close
**Resolution Rate**: % of cases closed

### Analyze Performance

**Category Chart**: Shows which issue types are most common
- Laptop issues
- Printer issues
- Software issues
- Other issues

**IT Performance Chart**: Shows workload per IT executive
- Open cases (yellow bars)
- Closed cases (green bars)

**Daily Trends**: Shows activity over time
- Blue line: Cases created
- Green line: Cases closed same day

### Export Data

Click "📊 Export to Excel" button to download:
- Complete case list
- All fields included
- Ready for analysis
- Professional formatting

---

## 🔗 Integration with Telegram Bot

### Option 1: Run Both Together (Recommended)

**Terminal 1 - Telegram Bot:**
```bash
python it_support_bot_fixed.py
```

**Terminal 2 - Dashboard:**
```bash
python dashboard_app.py
```

Both access the same database, so data syncs automatically!

### Option 2: Real-time Notifications

Modify your Telegram bot to notify the dashboard:

Add to `it_support_bot_fixed.py`:
```python
import requests

# After creating case
try:
    requests.post('http://localhost:5000/api/notify/new_case', 
                  json={'case_id': case_id})
except:
    pass  # Dashboard might not be running

# After closing case
try:
    requests.post('http://localhost:5000/api/notify/case_closed',
                  json={'case_id': case_id})
except:
    pass
```

---

## 🌐 API Endpoints

The dashboard provides REST APIs:

### GET Endpoints

```
GET /api/stats
Returns: Overall statistics

GET /api/categories
Returns: Category breakdown

GET /api/performance
Returns: IT executive performance

GET /api/recent-cases?limit=10
Returns: Recent cases

GET /api/daily-stats?days=30
Returns: Daily statistics

GET /api/case/<case_id>
Returns: Case details

GET /api/export/excel
Returns: Excel file download
```

### Example API Usage

```python
import requests

# Get statistics
response = requests.get('http://localhost:5000/api/stats')
stats = response.json()
print(f"Total cases: {stats['total_cases']}")

# Get recent cases
response = requests.get('http://localhost:5000/api/recent-cases?limit=5')
cases = response.json()
for case in cases:
    print(f"Case #{case['case_id']}: {case['status']}")
```

---

## 📱 Accessing from Other Devices

### On Local Network

Find your computer's IP address:
```bash
# Windows
ipconfig

# Look for IPv4 Address: 192.168.x.x
```

Then access from other devices:
```
http://192.168.x.x:5000
```

### Make it Public (Optional)

Use a tunneling service like ngrok:
```bash
# Install ngrok
# Download from https://ngrok.com

# Run ngrok
ngrok http 5000

# You'll get a public URL like:
# https://abc123.ngrok.io
```

---

## 🔐 Security Considerations

### Change Secret Key

In `dashboard_app.py`, change:
```python
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
```

To something secure:
```python
app.config['SECRET_KEY'] = 'your-random-secure-key-here'
```

### Add Authentication (Optional)

For production, add login:
```bash
pip install Flask-Login
```

Then implement user authentication.

### Restrict Access

Add IP whitelisting or use a VPN for remote access.

---

## 💾 Database Management

The dashboard uses the same SQLite database as the bot:
```
it_support.db
```

### Backup Database

```bash
# Create backup
copy it_support.db it_support_backup_%date%.db

# Or use sqlite3
sqlite3 it_support.db ".backup it_support_backup.db"
```

### View Database

```bash
sqlite3 it_support.db

# Run queries
SELECT * FROM cases WHERE status = 'open';
SELECT COUNT(*) FROM cases;
```

---

## 🎯 Advanced Features

### Custom Reports

Create custom queries in the dashboard:
```python
@app.route('/api/custom-report')
def custom_report():
    conn = dashboard.get_connection()
    # Your custom SQL query
    df = pd.read_sql_query("SELECT ...", conn)
    return jsonify(df.to_dict('records'))
```

### Scheduled Reports

Auto-email reports daily:
```python
# Add to dashboard_app.py
from apscheduler.schedulers.background import BackgroundScheduler
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

def send_daily_report():
    output = dashboard.export_to_excel()
    # Email logic here
    
scheduler = BackgroundScheduler()
scheduler.add_job(send_daily_report, 'cron', hour=9)
scheduler.start()
```

### Slack Integration

Send alerts to Slack:
```python
import requests

def notify_slack(message):
    webhook_url = 'YOUR_SLACK_WEBHOOK'
    requests.post(webhook_url, json={'text': message})

# Use after case creation/closure
notify_slack(f"New case #{case_id} created!")
```

---

## 📊 Excel Export Features

### What's Included

The Excel export contains:
- Case ID
- Username
- Full Name
- Category
- Status
- IT Executive
- Created Date
- Closed Date
- Key Finding
- Solution
- Support Type
- Time Taken

### Auto-formatting

- Headers are bold
- Columns auto-sized
- Professional appearance
- Ready for presentation

### Custom Export

Modify `export_to_excel()` in `dashboard_app.py`:
```python
def export_to_excel(self):
    conn = self.get_connection()
    
    # Add your custom queries
    df_summary = pd.read_sql_query("""
        SELECT category, COUNT(*) as total
        FROM cases
        GROUP BY category
    """, conn)
    
    # Add more sheets
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_cases.to_excel(writer, sheet_name='All Cases', index=False)
        df_summary.to_excel(writer, sheet_name='Summary', index=False)
    
    return output
```

---

## 🐛 Troubleshooting

### Dashboard won't start

**Error: "Port 5000 already in use"**
```bash
# Change port in dashboard_app.py
socketio.run(app, debug=True, host='0.0.0.0', port=5001)
```

**Error: "No module named 'flask'"**
```bash
pip install Flask
```

### No data showing

**Check database exists:**
```bash
dir it_support.db
```

**Check database has data:**
```bash
sqlite3 it_support.db "SELECT COUNT(*) FROM cases;"
```

### Charts not loading

**Check Chart.js loaded:**
- Open browser console (F12)
- Look for errors
- Ensure internet connection (CDN loads)

### Export not working

**Error: "No module named 'openpyxl'"**
```bash
pip install openpyxl
```

---

## 🎨 Customization

### Change Colors

Edit `dashboard.html`, find:
```css
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
```

Change to your company colors:
```css
background: linear-gradient(135deg, #your-color1 0%, #your-color2 100%);
```

### Add Company Logo

In `dashboard.html`, replace:
```html
<h1>🎯 IT Support Dashboard</h1>
```

With:
```html
<img src="/static/logo.png" style="height: 50px;">
<h1>IT Support Dashboard</h1>
```

### Change Refresh Rate

In `dashboard.html`, find:
```javascript
setInterval(loadData, 30000); // 30 seconds
```

Change to:
```javascript
setInterval(loadData, 10000); // 10 seconds
```

---

## 📈 Performance Optimization

### Database Indexing

```sql
CREATE INDEX idx_status ON cases(status);
CREATE INDEX idx_created_at ON cases(created_at);
CREATE INDEX idx_category ON cases(category);
```

### Caching

Add Redis for caching:
```bash
pip install redis flask-caching
```

```python
from flask_caching import Cache

cache = Cache(app, config={'CACHE_TYPE': 'redis'})

@cache.cached(timeout=60)
def get_dashboard_stats():
    # Stats cached for 60 seconds
```

---

## 🚀 Deployment to Production

### Option 1: Linux Server

```bash
# Install gunicorn
pip install gunicorn

# Run with gunicorn
gunicorn --worker-class eventlet -w 1 dashboard_app:app --bind 0.0.0.0:5000
```

### Option 2: Docker

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements_dashboard.txt .
RUN pip install -r requirements_dashboard.txt
COPY . .
CMD ["python", "dashboard_app.py"]
```

Run:
```bash
docker build -t it-dashboard .
docker run -p 5000:5000 it-dashboard
```

### Option 3: Cloud (Heroku, AWS, Azure)

Deploy to cloud platform for public access.

---

## 📞 Support

### Common Questions

**Q: Can I access from my phone?**
A: Yes! Open browser and go to http://your-computer-ip:5000

**Q: Does it work offline?**
A: Yes, as long as both bot and dashboard are on same machine

**Q: Can multiple people view at once?**
A: Yes! Unlimited simultaneous viewers

**Q: How often does data update?**
A: Every 30 seconds automatically, or instantly with WebSocket

**Q: Can I customize the reports?**
A: Yes! Edit the SQL queries in dashboard_app.py

---

## ✅ Quick Start Checklist

- [ ] Install requirements: `pip install -r requirements_dashboard.txt`
- [ ] Run dashboard: `python dashboard_app.py`
- [ ] Open browser: `http://localhost:5000`
- [ ] Run Telegram bot in another terminal
- [ ] Create test case in Telegram
- [ ] Watch it appear in dashboard
- [ ] Click Export to Excel
- [ ] Share dashboard URL with team

---

**You're all set! 🎉**

The dashboard is now running and will show all your IT support cases in a beautiful, real-time interface!

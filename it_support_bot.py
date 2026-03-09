#!/usr/bin/env python3
"""
IT Service Support Telegram Bot
Handles IT support tickets with automated routing and case management
"""

import logging
import sqlite3
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForumTopic
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# Configure logging FIRST
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Import Excel report generator
try:
    from excel_report_generator import ExcelReportGenerator
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False
    logger.warning("Excel report generator not available. Install: pip install pandas openpyxl")

# Conversation states
SELECTING_ISSUE, COLLECTING_INFO, WAITING_SUBMISSION, CLOSING_CASE = range(4)

# Issue categories with assigned IT executives
ISSUE_CATEGORIES = {
    'laptop': {'name': 'Laptop Issue', 'it_exec': '@IT_01', 'topic_id': None},
    'printer': {'name': 'Printer Issue', 'it_exec': '@IT_02', 'topic_id': None},
    'software': {'name': 'Software Issue', 'it_exec': '@IT_03', 'topic_id': None},
    'other': {'name': 'Other Issue', 'it_exec': '@IT_04', 'topic_id': None}
}

# Configuration (Load from config.json)
CONFIG = {}

class DatabaseManager:
    """Manages SQLite database operations for case tracking"""
    
    def __init__(self, db_path='it_support.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Cases table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cases (
                case_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                category TEXT NOT NULL,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                it_executive TEXT,
                key_finding TEXT,
                solution TEXT,
                support_type TEXT,
                completion_time TEXT
            )
        ''')
        
        # Messages table to store case details
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS case_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER,
                message_type TEXT,
                message_text TEXT,
                file_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES cases(case_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    
    def create_case(self, user_id, username, full_name, category):
        """Create a new support case"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        it_exec = ISSUE_CATEGORIES[category]['it_exec']
        
        cursor.execute('''
            INSERT INTO cases (user_id, username, full_name, category, it_executive)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, full_name, category, it_exec))
        
        case_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Created case #{case_id} for user {username}")
        return case_id
    
    def add_message_to_case(self, case_id, message_type, message_text=None, file_id=None):
        """Add a message/file to a case"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO case_messages (case_id, message_type, message_text, file_id)
            VALUES (?, ?, ?, ?)
        ''', (case_id, message_type, message_text, file_id))
        
        conn.commit()
        conn.close()
    
    def get_case(self, case_id):
        """Get case details"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM cases WHERE case_id = ?', (case_id,))
        case = cursor.fetchone()
        
        conn.close()
        return case
    
    def get_case_messages(self, case_id):
        """Get all messages for a case"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM case_messages WHERE case_id = ?', (case_id,))
        messages = cursor.fetchall()
        
        conn.close()
        return messages
    
    def close_case(self, case_id, key_finding, solution, support_type, completion_time):
        """Close a case with completion details"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE cases 
            SET status = 'closed',
                closed_at = CURRENT_TIMESTAMP,
                key_finding = ?,
                solution = ?,
                support_type = ?,
                completion_time = ?
            WHERE case_id = ?
        ''', (key_finding, solution, support_type, completion_time, case_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Closed case #{case_id}")
    
    def get_open_cases(self):
        """Get all open cases"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM cases WHERE status = "open"')
        cases = cursor.fetchall()
        
        conn.close()
        return cases

# Initialize database
db = DatabaseManager()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start command - Show issue category selection"""
    user = update.effective_user
    
    # Check if in support group
    if update.effective_chat.id != CONFIG['SUPPORT_GROUP_ID']:
        await update.message.reply_text(
            "⚠️ This bot only works in the Customer Support Group."
        )
        return ConversationHandler.END
    
    keyboard = [
        [
            InlineKeyboardButton("💻 Laptop Issue", callback_data='laptop'),
            InlineKeyboardButton("🖨️ Printer Issue", callback_data='printer')
        ],
        [
            InlineKeyboardButton("💾 Software Issue", callback_data='software'),
            InlineKeyboardButton("❓ Other Issue", callback_data='other')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 Hello {user.first_name}!\n\n"
        "Welcome to IT Support Bot. Please select the type of issue you're experiencing:",
        reply_markup=reply_markup
    )
    
    return SELECTING_ISSUE

async def issue_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle issue category selection"""
    query = update.callback_query
    await query.answer()
    
    category = query.data
    user = query.from_user
    
    # Create a new case
    case_id = db.create_case(
        user_id=user.id,
        username=user.username or user.first_name,
        full_name=user.full_name,
        category=category
    )
    
    # Store case info in context
    context.user_data['case_id'] = case_id
    context.user_data['category'] = category
    context.user_data['messages_collected'] = []
    
    category_name = ISSUE_CATEGORIES[category]['name']
    
    await query.edit_message_text(
        f"✅ Issue Type Selected: *{category_name}*\n"
        f"📋 Case ID: #{case_id}\n\n"
        "Please describe your issue and send any relevant:\n"
        "• 📝 Text descriptions\n"
        "• 📷 Photos\n"
        "• 🎥 Videos\n"
        "• 🎤 Voice messages\n"
        "• 📎 Files\n\n"
        "When you're done, type /submit to forward your case to IT support.",
        parse_mode='Markdown'
    )
    
    return COLLECTING_INFO

async def collect_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Collect user messages (text, photos, videos, voice, files)"""
    message = update.message
    case_id = context.user_data.get('case_id')
    
    if not case_id:
        await message.reply_text("⚠️ No active case. Please use /start to begin.")
        return ConversationHandler.END
    
    # Store message details
    message_data = {'message_id': message.message_id}
    
    if message.text and not message.text.startswith('/'):
        db.add_message_to_case(case_id, 'text', message_text=message.text)
        message_data['type'] = 'text'
        message_data['text'] = message.text
        
    elif message.photo:
        photo = message.photo[-1]  # Get highest resolution
        db.add_message_to_case(case_id, 'photo', file_id=photo.file_id)
        message_data['type'] = 'photo'
        message_data['file_id'] = photo.file_id
        if message.caption:
            message_data['caption'] = message.caption
            
    elif message.video:
        db.add_message_to_case(case_id, 'video', file_id=message.video.file_id)
        message_data['type'] = 'video'
        message_data['file_id'] = message.video.file_id
        if message.caption:
            message_data['caption'] = message.caption
            
    elif message.voice:
        db.add_message_to_case(case_id, 'voice', file_id=message.voice.file_id)
        message_data['type'] = 'voice'
        message_data['file_id'] = message.voice.file_id
        
    elif message.document:
        db.add_message_to_case(case_id, 'document', file_id=message.document.file_id)
        message_data['type'] = 'document'
        message_data['file_id'] = message.document.file_id
        message_data['filename'] = message.document.file_name
        if message.caption:
            message_data['caption'] = message.caption
    else:
        return COLLECTING_INFO
    
    context.user_data['messages_collected'].append(message_data)
    
    # Show acknowledgment
    await message.reply_text(
        "✅ Received! Continue adding details or type /submit when ready.",
        reply_to_message_id=message.message_id
    )
    
    return COLLECTING_INFO

async def submit_case(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Submit the case to IT group"""
    case_id = context.user_data.get('case_id')
    category = context.user_data.get('category')
    messages = context.user_data.get('messages_collected', [])
    
    if not case_id or not messages:
        await update.message.reply_text(
            "⚠️ No messages collected. Please add some details before submitting."
        )
        return COLLECTING_INFO
    
    # Get case details
    case = db.get_case(case_id)
    user_id, username, full_name, category_db = case[1], case[2], case[3], case[4]
    created_at = case[6]
    
    category_name = ISSUE_CATEGORIES[category]['name']
    it_executive = ISSUE_CATEGORIES[category]['it_exec']
    
    # Format professional message for IT group
    header_message = (
        "🆕 *NEW IT SUPPORT REQUEST*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📋 *Case ID:* #{case_id}\n"
        f"🏷️ *Category:* {category_name}\n"
        f"👤 *Reporter:* {full_name} (@{username})\n"
        f"📅 *Submitted:* {created_at}\n"
        f"👨‍💼 *Assigned to:* {it_executive}\n\n"
        f"📝 *Case Details Below:*"
    )
    
    try:
        # Get topic_id for the category (if using forum groups)
        topic_id = ISSUE_CATEGORIES[category].get('topic_id')
        
        # Send header to IT group
        if topic_id:
            header_msg = await context.bot.send_message(
                chat_id=CONFIG['IT_GROUP_ID'],
                text=header_message,
                parse_mode='Markdown',
                message_thread_id=topic_id
            )
        else:
            header_msg = await context.bot.send_message(
                chat_id=CONFIG['IT_GROUP_ID'],
                text=header_message,
                parse_mode='Markdown'
            )
        
        # Forward all collected messages
        for msg in messages:
            if msg['type'] == 'text':
                await context.bot.send_message(
                    chat_id=CONFIG['IT_GROUP_ID'],
                    text=msg['text'],
                    message_thread_id=topic_id if topic_id else None
                )
            elif msg['type'] == 'photo':
                await context.bot.send_photo(
                    chat_id=CONFIG['IT_GROUP_ID'],
                    photo=msg['file_id'],
                    caption=msg.get('caption'),
                    message_thread_id=topic_id if topic_id else None
                )
            elif msg['type'] == 'video':
                await context.bot.send_video(
                    chat_id=CONFIG['IT_GROUP_ID'],
                    video=msg['file_id'],
                    caption=msg.get('caption'),
                    message_thread_id=topic_id if topic_id else None
                )
            elif msg['type'] == 'voice':
                await context.bot.send_voice(
                    chat_id=CONFIG['IT_GROUP_ID'],
                    voice=msg['file_id'],
                    message_thread_id=topic_id if topic_id else None
                )
            elif msg['type'] == 'document':
                await context.bot.send_document(
                    chat_id=CONFIG['IT_GROUP_ID'],
                    document=msg['file_id'],
                    caption=msg.get('caption'),
                    message_thread_id=topic_id if topic_id else None
                )
        
        # Send action buttons to IT group
        keyboard = [
            [InlineKeyboardButton("✅ Close Case", callback_data=f'close_{case_id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=CONFIG['IT_GROUP_ID'],
            text=f"━━━━━━━━━━━━━━━━━━━━━━\n{it_executive} Please handle this case.",
            reply_markup=reply_markup,
            message_thread_id=topic_id if topic_id else None
        )
        
        # Confirm to user
        await update.message.reply_text(
            f"✅ *Case Submitted Successfully!*\n\n"
            f"📋 Case ID: #{case_id}\n"
            f"🏷️ Category: {category_name}\n"
            f"👨‍💼 Assigned to: {it_executive}\n\n"
            f"Your case has been forwarded to IT support. You'll be notified when it's resolved.",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error submitting case: {e}")
        await update.message.reply_text(
            "❌ Error submitting case. Please contact IT support directly."
        )
    
    # Clear context
    context.user_data.clear()
    return ConversationHandler.END

async def close_case_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """IT executive clicks to close a case"""
    query = update.callback_query
    await query.answer()
    
    # Check if in IT group
    if query.message.chat.id != CONFIG['IT_GROUP_ID']:
        await query.answer("⚠️ This can only be done in the IT group.", show_alert=True)
        return ConversationHandler.END
    
    case_id = int(query.data.split('_')[1])
    
    # Store case_id in context
    context.user_data['closing_case_id'] = case_id
    
    await query.edit_message_text(
        f"📋 *Closing Case #{case_id}*\n\n"
        "Please provide the following information:\n\n"
        "Format your response as:\n"
        "```\n"
        "Key Finding: [Your finding]\n"
        "Solution: [Solution applied]\n"
        "Support Type: [Remote/Onsite/Phone]\n"
        "Time Taken: [e.g., 30 minutes]\n"
        "```",
        parse_mode='Markdown'
    )
    
    return CLOSING_CASE

async def close_case_submit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process case closure information"""
    case_id = context.user_data.get('closing_case_id')
    message_text = update.message.text
    
    if not case_id:
        await update.message.reply_text("⚠️ No active case closure. Please try again.")
        return ConversationHandler.END
    
    # Parse the closure information
    try:
        lines = message_text.strip().split('\n')
        closure_data = {}
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                closure_data[key.strip().lower()] = value.strip()
        
        key_finding = closure_data.get('key finding', 'N/A')
        solution = closure_data.get('solution', 'N/A')
        support_type = closure_data.get('support type', 'N/A')
        time_taken = closure_data.get('time taken', 'N/A')
        
    except Exception as e:
        await update.message.reply_text(
            "❌ Invalid format. Please use the format:\n"
            "Key Finding: ...\n"
            "Solution: ...\n"
            "Support Type: ...\n"
            "Time Taken: ..."
        )
        return CLOSING_CASE
    
    # Close case in database
    db.close_case(case_id, key_finding, solution, support_type, time_taken)
    
    # Get case details
    case = db.get_case(case_id)
    username = case[2]
    full_name = case[3]
    category = case[4]
    it_executive = update.effective_user.username or update.effective_user.first_name
    
    # Get current timestamp
    closed_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Announce closure in Customer Support Group
    announcement = (
        "✅ *CASE RESOLVED*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📋 *Case ID:* #{case_id}\n"
        f"👤 *Reporter:* {full_name} (@{username})\n"
        f"🏷️ *Category:* {ISSUE_CATEGORIES[category]['name']}\n\n"
        f"🔧 *Key Finding:* {key_finding}\n"
        f"💡 *Solution:* {solution}\n"
        f"📞 *Support Type:* {support_type}\n"
        f"⏱️ *Time Taken:* {time_taken}\n\n"
        f"👨‍💼 *Resolved by:* @{it_executive}\n"
        f"🕐 *Closed at:* {closed_time}\n\n"
        "Thank you for your patience! 🙏"
    )
    
    try:
        await context.bot.send_message(
            chat_id=CONFIG['SUPPORT_GROUP_ID'],
            text=announcement,
            parse_mode='Markdown'
        )
        
        await update.message.reply_text(
            f"✅ Case #{case_id} closed successfully!\n"
            "Announcement sent to Customer Support Group."
        )
        
    except Exception as e:
        logger.error(f"Error announcing case closure: {e}")
        await update.message.reply_text(
            f"✅ Case #{case_id} closed but couldn't send announcement."
        )
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the current operation"""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Operation cancelled. Use /start to begin again."
    )
    return ConversationHandler.END

async def view_open_cases(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all open cases (IT group only)"""
    if update.effective_chat.id != CONFIG['IT_GROUP_ID']:
        return
    
    cases = db.get_open_cases()
    
    if not cases:
        await update.message.reply_text("✅ No open cases at the moment!")
        return
    
    message = "*📋 Open Cases*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for case in cases:
        case_id, user_id, username, full_name, category, status, created_at = case[:7]
        it_exec = case[7]
        category_name = ISSUE_CATEGORIES[category]['name']
        
        message += (
            f"*Case #{case_id}*\n"
            f"👤 {full_name} (@{username})\n"
            f"🏷️ {category_name}\n"
            f"👨‍💼 {it_exec}\n"
            f"📅 {created_at}\n\n"
        )
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information"""
    help_text = (
        "🤖 *IT Support Bot - Help*\n\n"
        "*For Customers (Support Group):*\n"
        "/start - Create a new support ticket\n"
        "/submit - Submit your case to IT\n"
        "/cancel - Cancel current operation\n\n"
        "*For IT Staff (IT Group):*\n"
        "/cases - View all open cases\n"
        "Click 'Close Case' button to resolve tickets\n\n"
        "*For Management:*\n"
        "/report - Generate Excel report (all cases)\n"
        "/report 30 - Generate last 30 days report\n"
        "/monthly - Generate current month report\n\n"
        "*Categories:*\n"
        "💻 Laptop Issue → IT-01\n"
        "🖨️ Printer Issue → IT-02\n"
        "💾 Software Issue → IT-03\n"
        "❓ Other Issue → IT-04"
    )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate Excel report for management"""
    # Check if in IT group or authorized
    if update.effective_chat.id != CONFIG['IT_GROUP_ID']:
        await update.message.reply_text(
            "⚠️ This command can only be used in the IT Support Group."
        )
        return
    
    if not EXCEL_AVAILABLE:
        await update.message.reply_text(
            "❌ Excel report feature not available.\n"
            "Install required packages:\n"
            "`pip install pandas openpyxl`",
            parse_mode='Markdown'
        )
        return
    
    # Send "generating" message
    status_msg = await update.message.reply_text(
        "⏳ Generating Excel report... Please wait."
    )
    
    try:
        generator = ExcelReportGenerator()
        
        # Check if days specified
        args = context.args
        if args and args[0].isdigit():
            days = int(args[0])
            filename = generator.generate_period_report(days)
            report_type = f"last {days} days"
        else:
            filename = generator.generate_full_report()
            report_type = "all cases"
        
        # Send the Excel file
        with open(filename, 'rb') as file:
            await update.message.reply_document(
                document=file,
                filename=filename,
                caption=f"📊 *IT Support Report*\n\n"
                        f"Report Type: {report_type}\n"
                        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"Total Sheets: Multiple (All Cases, Open, Closed, Summary, etc.)",
                parse_mode='Markdown'
            )
        
        # Delete status message
        await status_msg.delete()
        
        # Clean up file
        os.remove(filename)
        logger.info(f"Report generated and sent: {filename}")
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        await status_msg.edit_text(
            f"❌ Error generating report: {str(e)}"
        )

async def generate_monthly_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate monthly Excel report"""
    # Check if in IT group
    if update.effective_chat.id != CONFIG['IT_GROUP_ID']:
        await update.message.reply_text(
            "⚠️ This command can only be used in the IT Support Group."
        )
        return
    
    if not EXCEL_AVAILABLE:
        await update.message.reply_text(
            "❌ Excel report feature not available.\n"
            "Install required packages:\n"
            "`pip install pandas openpyxl`",
            parse_mode='Markdown'
        )
        return
    
    status_msg = await update.message.reply_text(
        "⏳ Generating monthly report... Please wait."
    )
    
    try:
        generator = ExcelReportGenerator()
        
        # Check if year/month specified
        args = context.args
        if len(args) >= 2:
            year = int(args[0])
            month = int(args[1])
            filename = generator.generate_monthly_report(year, month)
        else:
            filename = generator.generate_monthly_report()
            year = datetime.now().year
            month = datetime.now().month
        
        # Send the Excel file
        with open(filename, 'rb') as file:
            await update.message.reply_document(
                document=file,
                filename=filename,
                caption=f"📊 *Monthly IT Support Report*\n\n"
                        f"Period: {year}-{month:02d}\n"
                        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                parse_mode='Markdown'
            )
        
        await status_msg.delete()
        os.remove(filename)
        logger.info(f"Monthly report generated and sent: {filename}")
        
    except Exception as e:
        logger.error(f"Error generating monthly report: {e}")
        await status_msg.edit_text(
            f"❌ Error generating report: {str(e)}"
        )

def load_config(config_file='config.json'):
    """Load configuration from JSON file"""
    global CONFIG
    try:
        with open(config_file, 'r') as f:
            CONFIG = json.load(f)
        logger.info("Configuration loaded successfully")
    except FileNotFoundError:
        logger.error(f"Config file {config_file} not found!")
        raise
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in {config_file}!")
        raise

def main():
    """Start the bot"""
    # Load configuration
    load_config()
    
    # Create application
    application = Application.builder().token(CONFIG['BOT_TOKEN']).build()
    
    # Conversation handler for customer support
    support_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECTING_ISSUE: [CallbackQueryHandler(issue_selected)],
            COLLECTING_INFO: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND | 
                    filters.PHOTO | 
                    filters.VIDEO | 
                    filters.VOICE | 
                    filters.Document.ALL,
                    collect_message
                ),
                CommandHandler('submit', submit_case)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    
    # Conversation handler for case closure
    closure_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(close_case_start, pattern='^close_')],
        states={
            CLOSING_CASE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, close_case_submit)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    
    # Add handlers
    application.add_handler(support_conv_handler)
    application.add_handler(closure_conv_handler)
    application.add_handler(CommandHandler('cases', view_open_cases))
    application.add_handler(CommandHandler('report', generate_report))
    application.add_handler(CommandHandler('monthly', generate_monthly_report))
    application.add_handler(CommandHandler('help', help_command))
    
    # Start the bot
    logger.info("IT Support Bot started successfully!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

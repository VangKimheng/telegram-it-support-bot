#!/usr/bin/env python3
"""
IT Service Support Telegram Bot - With Alert Feature
Allows sending reminders to IT staff for pending cases
"""

import logging
import sqlite3
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
SELECTING_ISSUE, COLLECTING_INFO, WAITING_SUBMISSION, CLOSING_CASE = range(4)

# Issue categories
ISSUE_CATEGORIES = {
    'laptop': {'name': 'Laptop Issue', 'it_exec': '@KimhengMW', 'topic_id': 4},
    'printer': {'name': 'Printer Issue', 'it_exec': '@MabMit_MW', 'topic_id': 2},
    'software': {'name': 'Software Issue', 'it_exec': '@ReaksaMW', 'topic_id': 377},
    'other': {'name': 'Other Issue', 'it_exec': '@KimhengMW', 'topic_id': 1}
}

CONFIG = {}

class DatabaseManager:
    def __init__(self, db_path='it_support.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
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
                    completion_time TEXT,
                    alert_count INTEGER DEFAULT 0,
                    last_alert TIMESTAMP
                )
            ''')
            
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
            
            # Add alert_count and last_alert columns if they don't exist (for existing databases)
            try:
                cursor.execute('ALTER TABLE cases ADD COLUMN alert_count INTEGER DEFAULT 0')
            except:
                pass
            
            try:
                cursor.execute('ALTER TABLE cases ADD COLUMN last_alert TIMESTAMP')
            except:
                pass
            
            conn.commit()
            conn.close()
            logger.info("✅ Database initialized")
        except Exception as e:
            logger.error(f"❌ Database error: {e}")
    
    def create_case(self, user_id, username, full_name, category):
        try:
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
            
            logger.info(f"✅ Created case #{case_id}")
            return case_id
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return None
    
    def add_message_to_case(self, case_id, message_type, message_text=None, file_id=None):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO case_messages (case_id, message_type, message_text, file_id)
                VALUES (?, ?, ?, ?)
            ''', (case_id, message_type, message_text, file_id))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"❌ Error: {e}")
    
    def get_case(self, case_id):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM cases WHERE case_id = ?', (case_id,))
            case = cursor.fetchone()
            conn.close()
            return case
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return None
    
    def increment_alert_count(self, case_id):
        """Increment alert count and update last alert time"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE cases 
                SET alert_count = alert_count + 1,
                    last_alert = CURRENT_TIMESTAMP
                WHERE case_id = ?
            ''', (case_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Error incrementing alert: {e}")
            return False
    
    def close_case(self, case_id, key_finding, solution, support_type, completion_time):
        try:
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
            logger.info(f"✅ Closed case #{case_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return False
    
    def get_open_cases(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM cases WHERE status = "open"')
            cases = cursor.fetchall()
            conn.close()
            return cases
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return []

db = DatabaseManager()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    logger.info(f"🔍 /start from chat_id: {chat_id}")
    
    support_group_id = CONFIG.get('SUPPORT_GROUP_ID')
    if support_group_id and chat_id != support_group_id:
        await update.message.reply_text(
            f"⚠️ This bot only works in Customer Support Group.\n\n"
            f"Current chat ID: {chat_id}\n"
            f"Expected ID: {support_group_id}\n\n"
            f"Use /debug to see info"
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
        "Welcome to IT Support Bot. Please select your issue type:",
        reply_markup=reply_markup
    )
    
    return SELECTING_ISSUE

async def issue_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    category = query.data
    user = query.from_user
    
    case_id = db.create_case(
        user_id=user.id,
        username=user.username or user.first_name,
        full_name=user.full_name,
        category=category
    )
    
    if not case_id:
        await query.edit_message_text("❌ Error creating case. Try /start again")
        return ConversationHandler.END
    
    context.user_data['case_id'] = case_id
    context.user_data['category'] = category
    context.user_data['messages_collected'] = []
    
    category_name = ISSUE_CATEGORIES[category]['name']
    
    await query.edit_message_text(
        f"✅ Issue Selected: {category_name}\n"
        f"📋 Case ID: {case_id}\n\n"
        "Please send:\n"
        "• Text descriptions\n"
        "• Photos\n"
        "• Videos\n"
        "• Voice messages\n"
        "• Files\n\n"
        "Type /submit when done"
    )
    
    return COLLECTING_INFO

async def collect_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message
    case_id = context.user_data.get('case_id')
    
    if not case_id:
        await message.reply_text("⚠️ No active case. Use /start to begin.")
        return ConversationHandler.END
    
    message_data = {'message_id': message.message_id}
    
    try:
        if message.text and not message.text.startswith('/'):
            db.add_message_to_case(case_id, 'text', message_text=message.text)
            message_data['type'] = 'text'
            message_data['text'] = message.text
            
        elif message.photo:
            photo = message.photo[-1]
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
        
        count = len(context.user_data['messages_collected'])
        await message.reply_text(
            f"✅ Message {count} received!\n\n"
            f"Add more or type /submit when ready",
            reply_to_message_id=message.message_id
        )
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        await message.reply_text("⚠️ Error processing message. Try again.")
    
    return COLLECTING_INFO

async def submit_case(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    case_id = context.user_data.get('case_id')
    category = context.user_data.get('category')
    messages = context.user_data.get('messages_collected', [])
    
    if not case_id:
        await update.message.reply_text("⚠️ No active case. Use /start to begin.")
        return ConversationHandler.END
    
    if not messages:
        await update.message.reply_text(
            "⚠️ No messages collected.\n\n"
            "Send text, photos, or files first, then /submit"
        )
        return COLLECTING_INFO
    
    case = db.get_case(case_id)
    if not case:
        await update.message.reply_text("❌ Error retrieving case.")
        return ConversationHandler.END
    
    user_id, username, full_name, category_db = case[1], case[2], case[3], case[4]
    created_at = case[6]
    
    category_name = ISSUE_CATEGORIES[category]['name']
    it_executive = ISSUE_CATEGORIES[category]['it_exec']
    
    header_message = (
        "🆕 NEW IT SUPPORT REQUEST\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📋 Case ID: {case_id}\n"
        f"🏷️ Category: {category_name}\n"
        f"👤 Reporter: {full_name} (@{username})\n"
        f"📅 Submitted: {created_at}\n"
        f"👨‍💼 Assigned: {it_executive}\n\n"
        f"📝 Case Details Below:"
    )
    
    try:
        it_group_id = CONFIG.get('IT_GROUP_ID')
        topic_id = ISSUE_CATEGORIES[category].get('topic_id')
        
        if not it_group_id:
            await update.message.reply_text(
                "⚠️ Demo Mode: IT_GROUP_ID not configured\n\n"
                "In production, this goes to IT Support Group:\n\n" + header_message
            )
        else:
            await context.bot.send_message(
                chat_id=it_group_id,
                text=header_message,
                message_thread_id=topic_id if topic_id else None
            )
            
            for msg in messages:
                if msg['type'] == 'text':
                    await context.bot.send_message(
                        chat_id=it_group_id,
                        text=msg['text'],
                        message_thread_id=topic_id if topic_id else None
                    )
                elif msg['type'] == 'photo':
                    await context.bot.send_photo(
                        chat_id=it_group_id,
                        photo=msg['file_id'],
                        caption=msg.get('caption'),
                        message_thread_id=topic_id if topic_id else None
                    )
                elif msg['type'] == 'video':
                    await context.bot.send_video(
                        chat_id=it_group_id,
                        video=msg['file_id'],
                        caption=msg.get('caption'),
                        message_thread_id=topic_id if topic_id else None
                    )
                elif msg['type'] == 'voice':
                    await context.bot.send_voice(
                        chat_id=it_group_id,
                        voice=msg['file_id'],
                        message_thread_id=topic_id if topic_id else None
                    )
                elif msg['type'] == 'document':
                    await context.bot.send_document(
                        chat_id=it_group_id,
                        document=msg['file_id'],
                        caption=msg.get('caption'),
                        message_thread_id=topic_id if topic_id else None
                    )
            
            # Add both Alert and Close buttons
            keyboard = [
                [
                    InlineKeyboardButton("🔔 Alert IT", callback_data=f'alert_{case_id}'),
                    InlineKeyboardButton("✅ Close Case", callback_data=f'close_{case_id}')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=it_group_id,
                text=f"━━━━━━━━━━━━━━━━━━━━━━\n{it_executive} Please handle this case.",
                reply_markup=reply_markup,
                message_thread_id=topic_id if topic_id else None
            )
        
        await update.message.reply_text(
            f"✅ Case Submitted!\n\n"
            f"📋 Case ID: {case_id}\n"
            f"🏷️ Category: {category_name}\n"
            f"👨‍💼 Assigned: {it_executive}\n"
            f"📊 Messages: {len(messages)}\n\n"
            f"IT support will handle your case.\n"
            f"You'll be notified when resolved.\n\n"
            f"Use /start for new ticket"
        )
        
        logger.info(f"✅ Case {case_id} submitted")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        await update.message.reply_text(
            f"❌ Error submitting: {e}\n\n"
            "Contact IT support or try again."
        )
    
    context.user_data.clear()
    return ConversationHandler.END

async def alert_it_staff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send alert/reminder to IT staff about pending case"""
    query = update.callback_query
    await query.answer()
    
    try:
        case_id = int(query.data.split('_')[1])
        
        # Get case details
        case = db.get_case(case_id)
        if not case:
            await query.answer("❌ Case not found", show_alert=True)
            return
        
        # Check if case is already closed
        if case[5] == 'closed':  # status column
            await query.answer("⚠️ This case is already closed", show_alert=True)
            return
        
        # Increment alert count
        db.increment_alert_count(case_id)
        
        # Get updated case info
        case = db.get_case(case_id)
        username = case[2]
        full_name = case[3]
        category = case[4]
        it_executive = case[8]
        created_at = case[6]
        alert_count = case[13] if len(case) > 13 else 1
        
        category_name = ISSUE_CATEGORIES.get(category, {}).get('name', category)
        
        # Calculate time elapsed
        try:
            created_time = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
            elapsed = datetime.now() - created_time
            hours_elapsed = elapsed.total_seconds() / 3600
            time_text = f"{int(hours_elapsed)} hours" if hours_elapsed >= 1 else f"{int(hours_elapsed * 60)} minutes"
        except:
            time_text = "unknown time"
        
        # Send alert message
        alert_message = (
            f"🔔 ALERT - CASE REMINDER #{alert_count}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📋 Case ID: {case_id}\n"
            f"⏰ Time Elapsed: {time_text}\n"
            f"🏷️ Category: {category_name}\n"
            f"👤 Reporter: {full_name} (@{username})\n"
            f"👨‍💼 Assigned: {it_executive}\n\n"
            f"⚠️ This case is still PENDING!\n"
            f"Please provide an update or close the case.\n\n"
            f"Total Alerts Sent: {alert_count}"
        )
        
        topic_id = ISSUE_CATEGORIES.get(category, {}).get('topic_id')
        
        # Send alert to IT group
        await context.bot.send_message(
            chat_id=CONFIG['IT_GROUP_ID'],
            text=alert_message,
            message_thread_id=topic_id if topic_id else None
        )
        
        # Update the button message
        await query.edit_message_text(
            query.message.text + f"\n\n🔔 Alert sent! (Total: {alert_count})"
        )
        
        # Confirm to the person who clicked
        await query.answer(f"✅ Alert sent to {it_executive}", show_alert=True)
        
        logger.info(f"✅ Alert sent for case #{case_id} (Alert #{alert_count})")
        
    except Exception as e:
        logger.error(f"❌ Error sending alert: {e}")
        await query.answer("❌ Error sending alert", show_alert=True)

async def close_case_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    case_id = int(query.data.split('_')[1])
    context.user_data['closing_case_id'] = case_id
    
    await query.edit_message_text(
        f"📋 Closing Case {case_id}\n\n"
        "Send closure info in this format:\n\n"
        "Key Finding: [your finding]\n"
        "Solution: [solution applied]\n"
        "Support Type: [Remote/Onsite/Phone]\n"
        "Time Taken: [e.g., 30 minutes]\n\n"
        "Example:\n"
        "Key Finding: RAM failure\n"
        "Solution: Replaced RAM\n"
        "Support Type: Onsite\n"
        "Time Taken: 1 hour"
    )
    
    return CLOSING_CASE

async def close_case_submit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    case_id = context.user_data.get('closing_case_id')
    message_text = update.message.text
    
    if not case_id:
        await update.message.reply_text("⚠️ No active closure. Click Close Case button.")
        return ConversationHandler.END
    
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
        
        if key_finding == 'N/A' or solution == 'N/A':
            raise ValueError("Missing fields")
        
    except Exception as e:
        await update.message.reply_text(
            "❌ Invalid format. Use:\n\n"
            "Key Finding: ...\n"
            "Solution: ...\n"
            "Support Type: ...\n"
            "Time Taken: ...\n\n"
            "Try again:"
        )
        return CLOSING_CASE
    
    success = db.close_case(case_id, key_finding, solution, support_type, time_taken)
    
    if not success:
        await update.message.reply_text(f"❌ Error closing case {case_id}")
        context.user_data.clear()
        return ConversationHandler.END
    
    case = db.get_case(case_id)
    username = case[2]
    full_name = case[3]
    category = case[4]
    it_executive = update.effective_user.username or update.effective_user.first_name
    closed_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    announcement = (
        "✅ CASE RESOLVED\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📋 Case ID: {case_id}\n"
        f"👤 Reporter: {full_name} (@{username})\n"
        f"🏷️ Category: {ISSUE_CATEGORIES[category]['name']}\n\n"
        f"🔧 Finding: {key_finding}\n"
        f"💡 Solution: {solution}\n"
        f"📞 Type: {support_type}\n"
        f"⏱️ Time: {time_taken}\n\n"
        f"👨‍💼 Resolved by: @{it_executive}\n"
        f"🕐 Closed: {closed_time}\n\n"
        "Thank you! 🙏"
    )
    
    try:
        support_group_id = CONFIG.get('SUPPORT_GROUP_ID')
        
        if support_group_id:
            await context.bot.send_message(
                chat_id=support_group_id,
                text=announcement
            )
        
        await update.message.reply_text(
            f"✅ Case {case_id} Closed!\n\n"
            f"Announcement sent to Customer Group.\n\n"
            f"Summary:\n"
            f"• Finding: {key_finding}\n"
            f"• Solution: {solution}\n"
            f"• Type: {support_type}\n"
            f"• Time: {time_taken}"
        )
        
        logger.info(f"✅ Case {case_id} closed by @{it_executive}")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        await update.message.reply_text(f"✅ Case {case_id} closed but no announcement")
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled. Use /start to begin.")
    return ConversationHandler.END

async def view_open_cases(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cases = db.get_open_cases()
    
    if not cases:
        await update.message.reply_text("✅ No open cases!")
        return
    
    message = "📋 Open Cases\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for case in cases:
        case_id, user_id, username, full_name, category, status, created_at = case[:7]
        it_exec = case[8]
        alert_count = case[13] if len(case) > 13 else 0
        
        category_name = ISSUE_CATEGORIES.get(category, {}).get('name', category)
        
        alert_text = f" 🔔x{alert_count}" if alert_count > 0 else ""
        
        message += (
            f"Case {case_id}{alert_text}\n"
            f"👤 {full_name} (@{username})\n"
            f"🏷️ {category_name}\n"
            f"👨‍💼 {it_exec}\n"
            f"📅 {created_at}\n\n"
        )
    
    await update.message.reply_text(message)

async def debug_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    
    info = (
        "🔍 DEBUG INFO\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Chat:\n"
        f"• ID: {chat.id}\n"
        f"• Title: {chat.title or 'DM'}\n"
        f"• Type: {chat.type}\n\n"
        f"Config:\n"
        f"• Support: {CONFIG.get('SUPPORT_GROUP_ID', 'NOT SET')}\n"
        f"• IT Group: {CONFIG.get('IT_GROUP_ID', 'NOT SET')}\n\n"
    )
    
    if chat.id == CONFIG.get('SUPPORT_GROUP_ID'):
        info += "✅ This IS Customer Support Group"
    elif chat.id == CONFIG.get('IT_GROUP_ID'):
        info += "✅ This IS IT Support Group"
    else:
        info += f"⚠️ Update config:\n\"SUPPORT_GROUP_ID\": {chat.id}"
    
    await update.message.reply_text(info)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 IT Support Bot - Help\n\n"
        "For Customers:\n"
        "/start - Create ticket\n"
        "/submit - Submit case\n"
        "/cancel - Cancel\n\n"
        "For IT Staff:\n"
        "/cases - View open cases\n"
        "🔔 Alert IT - Send reminder for pending case\n"
        "✅ Close Case - Resolve ticket\n\n"
        "Debug:\n"
        "/debug - Show info\n\n"
        "Categories:\n"
        "💻 Laptop → @KimhengMW\n"
        "🖨️ Printer → @MabMit_MW\n"
        "💾 Software → @ReaksaMW\n"
        "❓ Other → @KimhengMW"
    )
    
    await update.message.reply_text(help_text)

def load_config(config_file='config.json'):
    global CONFIG
    try:
        with open(config_file, 'r') as f:
            CONFIG = json.load(f)
        logger.info("✅ Config loaded")
    except FileNotFoundError:
        logger.warning("⚠️  config.json not found")
        CONFIG = {}
    except json.JSONDecodeError:
        logger.error("❌ Invalid JSON")
        CONFIG = {}

def main():
    load_config()
    
    bot_token = CONFIG.get('BOT_TOKEN')
    if not bot_token or bot_token == 'YOUR_BOT_TOKEN_HERE':
        print("\n❌ ERROR: Set BOT_TOKEN in config.json!\n")
        return
    
    application = Application.builder().token(bot_token).build()
    
    support_conv = ConversationHandler(
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
    
    closure_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(close_case_start, pattern='^close_')],
        states={
            CLOSING_CASE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, close_case_submit)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    
    application.add_handler(support_conv)
    application.add_handler(closure_conv)
    application.add_handler(CallbackQueryHandler(alert_it_staff, pattern='^alert_'))
    application.add_handler(CommandHandler('cases', view_open_cases))
    application.add_handler(CommandHandler('debug', debug_info))
    application.add_handler(CommandHandler('help', help_command))
    
    print("=" * 50)
    print("✅ IT Support Bot Started!")
    print("=" * 50)
    print(f"📋 Support: {CONFIG.get('SUPPORT_GROUP_ID', 'Not set')}")
    print(f"🔧 IT Group: {CONFIG.get('IT_GROUP_ID', 'Not set')}")
    print("🔔 Alert Feature: ENABLED")
    print("=" * 50)
    
    logger.info("🚀 Bot started with alert feature!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

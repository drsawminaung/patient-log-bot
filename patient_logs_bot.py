import os
import logging
import json
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import re
import gspread
from google.oauth2.service_account import Credentials

# --- Configuration ---
# It's best practice to load sensitive data from environment variables
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8251634889:AAG2GnMk3iQLotpb59h7fmi18sZJq2BrPR4')
SHEET_KEY = os.getenv('GOOGLE_SHEET_KEY', '1bmy5cnprg5u_B8AGuibPGpfyCVouyi_ZxcVo9zbKGho')
CREDENTIALS_FILE = 'credentials.json'

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Google Sheets Setup
def get_gspread_sheet():
    """Initializes and returns the Google Sheet object."""
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"]        
        gcp_creds_json_str = os.getenv('GCP_CREDS_JSON')

        if gcp_creds_json_str:
            # Load credentials from environment variable (for deployment)
            logger.info("Loading Google credentials from environment variable.")
            creds_dict = json.loads(gcp_creds_json_str)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        else:
            # Load credentials from file (for local development)
            logger.info(f"Loading Google credentials from file: {CREDENTIALS_FILE}")
            creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)

        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_KEY).sheet1
    except FileNotFoundError:
        logger.error(f"Error: '{CREDENTIALS_FILE}' not found and GCP_CREDS_JSON is not set.")
        return None    
    except Exception as e:
        logger.error(f"An error occurred during Google Sheets authentication: {e}")
        return None

def extract_details(text):
    code_match = re.match(r'#HN\d+', text)
    name_match = re.search(r'Name: ([^\n]+)', text)
    age_match = re.search(r'Age: (\d+)', text)
    dx_match = re.search(r'Dx: ([^\n]+)', text)
    notes_match = re.search(r'Notes: ([^\n]+)', text)
    
    return [
        code_match.group(0).strip() if code_match else '',
        name_match.group(1).strip() if name_match else '',
        age_match.group(1).strip() if age_match else '',
        dx_match.group(1).strip() if dx_match else '',
        notes_match.group(1).strip() if notes_match else ''
    ]

async def handle_message(update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.startswith('#HN'):
        logger.info(f"Received log from chat ID {update.message.chat_id}")
        details = extract_details(text)
        
        # Run the blocking gspread call in a separate thread
        success = await context.application.create_task(
            context.application.run_in_thread(save_to_sheet, details)
        )
        
        if success:
            await context.bot.send_message(chat_id=update.message.chat_id, text="✅ Patient log saved to Google Sheet.")
        else:
            await context.bot.send_message(chat_id=update.message.chat_id, text="❌ Failed to save patient log. Please check the bot's logs.")

def save_to_sheet(details):
    """Appends a row to the Google Sheet. Returns True on success, False on failure."""
    try:
        sheet.append_row(details)
        logger.info(f"Successfully saved details: {details}")
        return True
    except Exception as e:
        logger.error(f"Failed to append row to Google Sheet: {e}")
        return False

if __name__ == '__main__':
    sheet = get_gspread_sheet()
    if sheet and TOKEN and SHEET_KEY:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        logger.info("Bot started and is polling for messages...")
        app.run_polling()
    else:
        logger.error("Bot could not start due to configuration errors.")

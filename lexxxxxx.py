import os
import logging
import requests
import asyncio
from telegram import Update, Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from telegram.error import BadRequest, TimedOut
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Load environment variables
TOKEN = os.getenv('TOKEN', '8100550883:AAEE6H_AYYkXNYMZwMBfqsDlgjsyFvvRGsY')  # Use environment variable or default
API_KEY = os.getenv('API_KEY', 'AIzaSyAHboTbXiBxIPSBJ_Rm18J-yWGrndDLiuE')  # Use environment variable or default
CSE_ID = os.getenv('CSE_ID', 'f453edb75011b4e35')  # Use environment variable or default
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"

# File paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DATA_FILE = os.path.join(BASE_DIR, "user_data.txt")
PHONE_DATA_FILE = os.path.join(BASE_DIR, "phone_data.txt")
LOCATION_DATA_FILE = os.path.join(BASE_DIR, "location_data.txt")
SEARCH_QUERIES_FILE = os.path.join(BASE_DIR, "search_queries.txt")

# Ensure files exist
for file_path in [USER_DATA_FILE, PHONE_DATA_FILE, LOCATION_DATA_FILE, SEARCH_QUERIES_FILE]:
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            f.write("")  # Create empty file

async def start(update: Update, context: CallbackContext) -> None:
    """Responds to the /start command"""
    user = update.effective_user
    username = user.username
    first_name = user.first_name
    last_name = user.last_name

    # Check if the user already exists in the user_data.txt file
    user_exists = False
    try:
        with open(USER_DATA_FILE, "r+") as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith(f"Username: {username},"):
                    user_exists = True
                    break

        if not user_exists:
            # If the user doesn't exist, create a new entry
            with open(USER_DATA_FILE, "a") as f:
                f.write(f"Username: {username}, First Name: {first_name}, Last Name: {last_name}\n")
    except Exception as e:
        logger.error(f"Error handling user data: {e}")

    # Create a keyboard with options to share phone number and location
    keyboard = [
        [KeyboardButton("Share my phone number", request_contact=True)],
        [KeyboardButton('Share my location', request_location=True)]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text('Hi! I am your search bot. Send me a query and I will return online sources from lex.uz.', reply_markup=reply_markup)

async def handle_contact(update: Update, context: CallbackContext) -> None:
    """Handles contact messages"""
    contact = update.effective_message.contact
    phone_number = contact.phone_number
    username = update.effective_user.username

    # Check if the user's phone number is already saved
    try:
        with open(PHONE_DATA_FILE, "r+") as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith(f"Username: {username},") and f"Phone Number: {phone_number}" in line:
                    await update.message.reply_text('Your phone number is already saved!')
                    return

        # If the phone number is not saved, save it
        with open(PHONE_DATA_FILE, "a") as f:
            f.write(f"Username: {username}, Phone Number: {phone_number}\n")
        await update.message.reply_text('Thank you for sharing your phone number!')
    except Exception as e:
        logger.error(f"Error handling contact: {e}")
        await update.message.reply_text('An error occurred while saving your phone number.')

async def handle_location(update: Update, context: CallbackContext) -> None:
    """Handles location messages"""
    location = update.effective_message.location
    user_id = update.effective_user.id
    username = update.effective_user.username
    latitude = location.latitude
    longitude = location.longitude

    # Check if the location already exists
    try:
        with open(LOCATION_DATA_FILE, "r+") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if line.startswith(f"User ID: {user_id},"):
                    lines[i] = f"User ID: {user_id}, Username: {username} Latitude: {latitude}, Longitude: {longitude}\n"
                    await update.message.reply_text('Your location is already saved!')
                    break
            else:
                lines.append(f"User ID: {user_id}, Username: {username} Latitude: {latitude}, Longitude: {longitude}\n")
                await update.message.reply_text('Thank you for sharing your location!')

            f.seek(0)
            f.writelines(lines)
            f.truncate()
    except Exception as e:
        logger.error(f"Error handling location: {e}")
        await update.message.reply_text('An error occurred while saving your location.')

async def search(update: Update, context: CallbackContext) -> None:
    """Handles user queries and returns search results"""
    query = update.message.text
    user = update.effective_user
    username = user.username

    if not query:
        await update.message.reply_text("Please enter a search query!")
        return

    # Save the search query
    try:
        temp_file = SEARCH_QUERIES_FILE + ".tmp"
        with open(SEARCH_QUERIES_FILE, "r") as f, open(temp_file, "w") as temp:
            user_exists = False
            for line in f:
                if line.startswith(f"Username: {username},"):
                    user_exists = True
                    existing_queries = line.strip().split(", ")[1:]
                    new_query = f"{existing_queries}, {query}"
                    temp.write(f"Username: {username}, {new_query}\n")
                else:
                    temp.write(line)

            if not user_exists:
                temp.write(f"Username: {username}, Query: {query}\n")

        os.replace(temp_file, SEARCH_QUERIES_FILE)
    except Exception as e:
        logger.error(f"Error saving search query: {e}")
        await update.message.reply_text('An error occurred while saving your query.')
        return

    # Perform the search
    try:
        results = perform_search(query)
        if results:
            context.user_data['query'] = query
            context.user_data['results'] = results
            context.user_data['current_page'] = 1
            await display_results(update, context)
        else:
            await update.message.reply_text('No results found for your query on lex.uz.')
    except Exception as e:
        logger.error(f"Error performing search: {e}")
        await update.message.reply_text('An error occurred while processing your query.')

def perform_search(query):
    """Performs a search using the Google Custom Search API"""
    search_url = f"https://www.googleapis.com/customsearch/v1?key={API_KEY}&cx={CSE_ID}&q={query}"
    headers = {"User-Agent": USER_AGENT}

    max_retries = 3
    retry_delay = 2  # seconds

    for attempt in range(max_retries):
        try:
            response = requests.get(search_url, headers=headers, timeout=5)
            response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
            break
        except requests.Timeout as e:
            logger.error(f"Timeout error on attempt {attempt+1}: {e}")
            time.sleep(retry_delay)
    else:
        logger.error("Maximum retries exceeded")
        return []

    search_results = response.json()
    results = []
    for result in search_results.get("items", []):
        title = result["title"]
        link = result["link"]
        snippet = result.get("snippet", "")  # Get the snippet if it exists, otherwise use an empty string
        results.append({"title": title, "link": link, "snippet": snippet})
    return results

def format_results(results, page, per_page=10):
    """Formats the search results into a Markdown string"""
    start = (page - 1) * per_page
    end = start + per_page
    formatted_results = f"Here are the results from lex.uz (Page {page}):\n\n"
    for i, result in enumerate(results[start:end], start=1):
        title = result["title"]
        link = result["link"]
        snippet = result["snippet"]
        formatted_results += f"{i}. [{title}]({link})\n{snippet}\n"
    return formatted_results

async def display_results(update: Update, context: CallbackContext):
    """Displays the search results with pagination"""
    query = context.user_data['query']
    results = context.user_data['results']
    current_page = context.user_data['current_page']

    formatted_results = format_results(results, current_page)
    keyboard = create_pagination_keyboard(current_page, len(results))
    await update.message.reply_text(formatted_results, parse_mode='Markdown', reply_markup=keyboard)

def create_pagination_keyboard(current_page, total_results, per_page=10):
    """Creates a pagination keyboard for navigating search results"""
    total_pages = (total_results + per_page - 1) // per_page
    keyboard = []

    if current_page > 1:
        keyboard.append([InlineKeyboardButton("Previous", callback_data="prev")])

    for page in range(max(1, current_page - 2), min(total_pages, current_page + 3)):
        keyboard.append([InlineKeyboardButton(str(page), callback_data=f"page_{page}")])

    if current_page < total_pages:
        keyboard.append([InlineKeyboardButton("Next", callback_data="next")])

    return InlineKeyboardMarkup(keyboard)

async def button(update: Update, context: CallbackContext) -> None:
    """Handles button presses for pagination"""
    query = update.callback_query
    await query.answer()

    if query.data == "prev":
        context.user_data['current_page'] -= 1
    elif query.data == "next":
        context.user_data['current_page'] += 1
    elif query.data.startswith("page_"):
        context.user_data['current_page'] = int(query.data.split("_")[1])

    await display_results(update, context)

def main():
    """Starts the bot"""
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    application.add_handler(CallbackQueryHandler(button))

    application.run_polling()

if __name__ == '__main__':
    main()

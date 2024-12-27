from telegram import Update, Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext
from telegram.ext import CallbackQueryHandler
import requests
from bs4 import BeautifulSoup
from telegram.ext import MessageHandler, filters
import logging
from telegram.error import BadRequest, TimedOut
import time
import asyncio
import os



# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
# Set up the bot token
TOKEN = '8100550883:AAEE6H_AYYkXNYMZwMBfqsDlgjsyFvvRGsY'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Set up the User-Agent string
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"

async def start(update: Update, context: CallbackContext) -> None:
    """Responds to the /start command"""
    user = update.effective_user
    username = user.username
    first_name = user.first_name
    last_name = user.last_name

    # Check if the user already exists in the user_data.txt file
    user_data_file = os.path.join(BASE_DIR, "user_data.txt")
    user_exists = False
    with open(user_data_file, "r+") as f:
        lines = f.readlines()
        for line in lines:
            if line.startswith(f"Username: {username},"):
                user_exists = True
                break

    if not user_exists:
        # If the user doesn't exist, create a new entry
        with open(user_data_file, "a") as f:
            f.write(f"Username: {username}, First Name: {first_name}, Last Name: {last_name}\n")

    keyboard = [[KeyboardButton("Share my phone number", request_contact=True), KeyboardButton('Share my location', request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text('Hi! I am your search bot. Send me a query and I will return online sources from lex.uz.', reply_markup=reply_markup)

async def handle_contact(update: Update, context: CallbackContext) -> None:
    """Handles contact messages"""
    contact = update.effective_message.contact
    phone_number = contact.phone_number
    username = update.effective_user.username

    # Check if the user's phone number is already saved
    phone_data = os.path.join(BASE_DIR, "phone_data.txt")
    with open(phone_data, "r+") as f:
        lines = f.readlines()
        for line in lines:
            if line.startswith(f"Username: {username},") and f"Phone Number: {phone_number}" in line:
                await update.message.reply_text('Your phone number is already saved!')
                return

    # If the phone number is not saved, save it
    with open(phone_data, "a") as f:
        f.write(f"Username: {username}, Phone Number: {phone_number}\n")

    await update.message.reply_text('Thank you for sharing your phone number!')

async def handle_location(update: Update, context: CallbackContext) -> None:
    location = update.effective_message.location
    user_id = update.effective_user.id
    username = update.effective_user.username

    latitude = location.latitude
    longitude = location.longitude

    # Check if the location already exists
    location_data = os.path.join(BASE_DIR, "location_data.txt")
    lines = []
    with open(location_data, "r+") as f:
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

async def search(update: Update, context: CallbackContext) -> None:
    """Handles user queries and returns search results"""
    query = update.message.text
    user = update.effective_user
    username = user.username

    max_retries = 3
    retry_delay = 1  # in seconds

    for attempt in range(max_retries):
        try:
            # Your code here to send the request to the Telegram API
            await update.message.reply_text('Searching...')
            # ...
            break
        except TimedOut as e:
            if attempt < max_retries - 1:
                logger.warning(f'Timed out on attempt {attempt+1}. Retrying in {retry_delay} seconds...')
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f'Timed out after {max_retries} attempts. Giving up.')
                await update.message.reply_text('Error: Timed out. Please try again later.')
                return

    if not query:  # Check if the query is empty
        await update.message.reply_text("Please enter a search query!")
        return

    # Check if the user already exists in the search_queries.txt file
    search_queries_file = os.path.join(BASE_DIR, "search_queries.txt")
    user_exists = False
    temp_file = search_queries_file + ".tmp"

    with open(search_queries_file, "r") as f, open(temp_file, "w") as temp:
        for line in f:
            if line.startswith(f"Username: {username},"):
                user_exists = True
                existing_queries = line.strip().split(", ")[1:]
                new_query = f"{existing_queries}, {query}"
                temp.write(f"Username: {username}, {new_query}\n")
            else:
                temp.write(line)

    if not user_exists:
        # If the user doesn't exist, create a new entry
        with open(temp_file, "a") as temp:
            temp.write(f"Username: {username}, Query: {query}\n")

    # Replace the original file with the temporary file
    import os
    os.replace(temp_file, search_queries_file)

    try:
        results = perform_search(query)
        if results:
            context.user_data['query'] = query
            context.user_data['results'] = results
            context.user_data['current_page'] = 1
            await display_results(update, context)
        else:
            await update.message.reply_text('No results found for your query on russian legislation.')
    except KeyError as e:
        await update.message.reply_text(f"I couldn't find any results for '{query}' on russian legislation. Sorry!")
    except BadRequest as e:
        await update.message.reply_text(f"Sorry, I couldn't process your '{query}'. Please try again!")

def perform_search(query):
    api_key = "AIzaSyAHboTbXiBxIPSBJ_Rm18J-yWGrndDLiuE"  # Your existing API key
    cse_id = "f453edb75011b4e35"  # Replace with your actual CSE ID
    search_url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cse_id}&q={query}"
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
    query = context.user_data['query']
    results = context.user_data['results']
    current_page = context.user_data['current_page']

    formatted_results = format_results(results, current_page)
    keyboard = create_pagination_keyboard(current_page, len(results))
    await update.message.reply_text(formatted_results, parse_mode='Markdown', reply_markup=keyboard)

def create_pagination_keyboard(current_page, total_results, per_page=10):
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
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    application.add_handler(CallbackQueryHandler(button))

    application.run_polling()

if __name__ == '__main__':
    main()

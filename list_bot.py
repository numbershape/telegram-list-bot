import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation handler
ITEM, PERSON, COMMENT = range(3)
CHOOSING_ACTION, SELECTING_ITEM = range(3, 5)

# Dictionary to store the list items
# Structure: {chat_id: [{item: str, person: str, comment: str}, ...]}
list_items = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Welcome to the Collaborative List Bot!\n\n"
        "Use /list to view the current list\n"
        "Use /add to add a new item\n"
        "Use /help to see all available commands"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        "Available commands:\n\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/list - View the current list\n"
        "/add - Add a new item to the list\n"
        "/remove - Remove an item from the list\n"
        "/clear - Clear the entire list"
    )
    await update.message.reply_text(help_text)

async def view_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the current list."""
    chat_id = update.effective_chat.id
    
    if chat_id not in list_items or not list_items[chat_id]:
        await update.message.reply_text("The list is empty. Use /add to add items.")
        return
    
    message = "📋 Current List:\n\n"
    for i, item in enumerate(list_items[chat_id], 1):
        message += f"{i}. Item: {item['item']}\n   Person: {item['person']}\n   Comment: {item['comment']}\n\n"
    
    await update.message.reply_text(message)

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the add item conversation."""
    await update.message.reply_text("Please enter the item name:")
    return ITEM

async def receive_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the item name and ask for the person responsible."""
    context.user_data["item"] = update.message.text
    await update.message.reply_text("Who will provide this item?")
    return PERSON

async def receive_person(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the person responsible and ask for additional comments."""
    context.user_data["person"] = update.message.text
    await update.message.reply_text("Any comments? (or type 'none' if no comments)")
    return COMMENT

async def receive_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the comment and finalize adding the item."""
    chat_id = update.effective_chat.id
    
    if chat_id not in list_items:
        list_items[chat_id] = []
    
    comment = update.message.text
    if comment.lower() == "none":
        comment = "-"
    
    new_item = {
        "item": context.user_data["item"],
        "person": context.user_data["person"],
        "comment": comment
    }
    
    list_items[chat_id].append(new_item)
    
    # Clear user data
    context.user_data.clear()
    
    await update.message.reply_text(
        f"Added: {new_item['item']} (Person: {new_item['person']})\n\n"
        "Use /list to view the updated list."
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the current conversation."""
    await update.message.reply_text("Operation cancelled.")
    context.user_data.clear()
    return ConversationHandler.END

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display items that can be removed."""
    chat_id = update.effective_chat.id
    
    if chat_id not in list_items or not list_items[chat_id]:
        await update.message.reply_text("The list is empty. Nothing to remove.")
        return ConversationHandler.END
    
    keyboard = []
    for i, item in enumerate(list_items[chat_id], 1):
        keyboard.append([InlineKeyboardButton(f"{i}. {item['item']} ({item['person']})", callback_data=f"remove_{i-1}")])
    
    keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("Select an item to remove:", reply_markup=reply_markup)
    return SELECTING_ITEM

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle button callbacks for item removal."""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    
    if query.data == "cancel":
        await query.edit_message_text("Operation cancelled.")
        return ConversationHandler.END
    
    if query.data.startswith("remove_"):
        idx = int(query.data.split("_")[1])
        if idx < len(list_items[chat_id]):
            removed_item = list_items[chat_id].pop(idx)
            await query.edit_message_text(f"Removed: {removed_item['item']} (Person: {removed_item['person']})")
        else:
            await query.edit_message_text("Error: Item not found.")
    
    return ConversationHandler.END

async def clear_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear the entire list."""
    chat_id = update.effective_chat.id
    
    keyboard = [
        [
            InlineKeyboardButton("Yes, clear it", callback_data="clear_confirm"),
            InlineKeyboardButton("No, keep it", callback_data="clear_cancel"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Are you sure you want to clear the entire list?",
        reply_markup=reply_markup
    )

async def clear_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle clear list confirmation."""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    
    if query.data == "clear_confirm":
        list_items[chat_id] = []
        await query.edit_message_text("The list has been cleared.")
    else:
        await query.edit_message_text("Clear operation cancelled. The list remains unchanged.")

def main() -> None:
    """Start the bot."""
    # Get token from environment variables
    token = os.environ.get("TELEGRAM_TOKEN")
    
    # Add a safety check (optional but recommended)
    if not token:
        raise ValueError("No TELEGRAM_TOKEN found in environment variables")
        
    # Create the Application with the token from environment variables
    application = Application.builder().token(token).build()
    
    # Add conversation handler for adding items
    add_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add_command)],
        states={
            ITEM: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.UpdateType.EDITED, receive_item)],
            PERSON: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.UpdateType.EDITED, receive_person)],
            COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.UpdateType.EDITED, receive_comment)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # Add conversation handler for removing items
    remove_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("remove", remove_command)],
        states={
            SELECTING_ITEM: [CallbackQueryHandler(button_callback)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", view_list))
    application.add_handler(CommandHandler("clear", clear_list))
    application.add_handler(CallbackQueryHandler(clear_button_callback, pattern="^clear_"))
    application.add_handler(add_conv_handler)
    application.add_handler(remove_conv_handler)
    
    # Start the Bot
    application.run_polling()

if __name__ == "__main__":
    main()
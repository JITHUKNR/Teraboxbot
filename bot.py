from pyrogram import Client, filters
import os
import threading
import re
import pymongo
from flask import Flask

# --- Render Environment Variables ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URL = os.environ.get("MONGO_URL", "") 
# ------------------------------------

app = Client("my_terabox_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- MongoDB Setup ---
mongo_client = pymongo.MongoClient(MONGO_URL)
db = mongo_client["my_magic_terabox_db"]
settings_col = db["magic_bot_settings"]

def get_settings(user_id):
    settings = settings_col.find_one({"user_id": user_id})
    if not settings:
        default_settings = {
            "user_id": user_id,
            "header": "",
            "footer": "",
            "channel": "",
            "custom_photo_id": None,
            "fake_photo_id": None,
            "enable_picture": True,
            "link_text": "🍓Video ",
            "use_experiment": True # പരീക്ഷണം ഓൺ ആക്കി വെക്കാൻ
        }
        settings_col.insert_one(default_settings)
        return default_settings
    return settings

def update_settings(user_id, key, value):
    settings_col.update_one({"user_id": user_id}, {"$set": {key: value}}, upsert=True)

# --- Dummy Web Server ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "TeraBox Lab Experiment Bot is Running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# --- Commands ---
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Welcome to TeraBox Experiment Lab! 🧪\n\nSet your photos and forward the links to test the large photo glitch.")

@app.on_message(filters.command("set_photo") & filters.private)
async def set_photo(client, message):
    if message.photo:
        file_id = message.photo.file_id
    elif message.document:
        file_id = message.document.file_id
    else:
        await message.reply_text("❌ Please send a photo with /set_photo")
        return
    update_settings(message.chat.id, "custom_photo_id", file_id)
    await message.reply_text("✅ Original Custom photo saved!")

@app.on_message(filters.command("set_fake_photo") & filters.private)
async def set_fake_photo(client, message):
    if message.photo:
        file_id = message.photo.file_id
    elif message.document:
        file_id = message.document.file_id
    else:
        await message.reply_text("❌ Please send a photo with /set_fake_photo")
        return
    update_settings(message.chat.id, "fake_photo_id", file_id)
    await message.reply_text("✅ Fake photo (Thumbnail) saved!")

@app.on_message(filters.command("enable_experiment") & filters.private)
async def enable_exp(client, message):
    update_settings(message.chat.id, "use_experiment", True)
    await message.reply_text("🧪 Experimental Large Fake Photo Mode Enabled!")

@app.on_message(filters.command("disable_experiment") & filters.private)
async def disable_exp(client, message):
    update_settings(message.chat.id, "use_experiment", False)
    await message.reply_text("⚙️ Standard Mode Enabled (Sends as normal document file).")

# --- Link Extraction & Experimental Processing ---
@app.on_message((filters.text | filters.photo) & filters.private)
async def handle_link(client, message):
    user_text = message.text or message.caption
    if not user_text:
        return
    
    urls = re.findall(r"(https?://\S*(?:terabox|terashare)\S*)", user_text, re.IGNORECASE)
    
    if urls:
        wait_msg = await message.reply_text("Running experiment... 🧪")
        settings = get_settings(message.chat.id)
        
        unique_urls = list(dict.fromkeys(urls))
        formatted_links = ""
        for index, url in enumerate(unique_urls, start=1):
            formatted_links += f"{settings['link_text']}{index}\n{url}\n\n\n"
        formatted_links = formatted_links.strip()
        
        final_caption = f"{settings.get('header', '')}{formatted_links}{settings.get('channel', '')}{settings.get('footer', '')}"
        
        try:
            if settings["custom_photo_id"]:
                doc_path = await client.download_media(settings["custom_photo_id"])
                thumb_path = await client.download_media(settings["fake_photo_id"]) if settings["fake_photo_id"] else None
                
                # --- ഇവിടെയാണ് പരീക്ഷണം നടക്കുന്നത് ---
                if settings["use_experiment"] and thumb_path:
                    try:
                        # വലിയ ഫോട്ടോയായി അയക്കാൻ ശ്രമിക്കുന്നു, ഒപ്പം തമ്പ്‌നെയിൽ ഫോഴ്സ് ചെയ്യുന്നു
                        await client.send_photo(
                            chat_id=message.chat.id,
                            photo=doc_path,
                            caption=final_caption,
                            replaces_video_thumb=thumb_path # ചില അപ്ഡേറ്റുകളിൽ വർക്കാവാൻ സാധ്യതയുള്ള പാരാമീറ്റർ
                        )
                        await wait_msg.delete()
                    except Exception as exp_error:
                        # ഒന്നാമത്തെ ട്രിക്ക് പരാജയപ്പെട്ടാൽ അടുത്ത വഴി നോക്കുന്നു
                        try:
                            await client.send_video(
                                chat_id=message.chat.id,
                                video=doc_path, # ഫോട്ടോയെ വീഡിയോ ആയി കാണിക്കാൻ നോക്കുന്നു
                                thumbnail=thumb_path,
                                caption=final_caption,
                                duration=1 # വലിയ ഫോട്ടോ ലേഔട്ട് കിട്ടാൻ വേണ്ടി
                            )
                            await wait_msg.delete()
                        except Exception as final_error:
                            # രണ്ട് പരീക്ഷണവും പരാജയപ്പെട്ടാൽ എറർ കാണിക്കും
                            await wait_msg.edit_text(f"🧪 Experiment Result: Failed.\n\nTelegram Server Error: {str(final_error)}")
                
                # പരീക്ഷണം ഓഫ് ആണെങ്കിൽ സാധാരണ പോലെ ഫയൽ ആയി അയക്കും
                else:
                    await client.send_document(
                        chat_id=message.chat.id, document=doc_path, thumbnail=thumb_path, file_name="Click_To_Open.jpg", caption=final_caption
                    )
                    await wait_msg.delete()
                
                # ഫയലുകൾ ഡിലീറ്റ് ചെയ്യുക
                if doc_path and os.path.exists(doc_path): os.remove(doc_path)
                if thumb_path and os.path.exists(thumb_path): os.remove(thumb_path)
            else:
                await wait_msg.edit_text(final_caption)
                
        except Exception as e:
            await wait_msg.edit_text(f"❌ System Error: {str(e)}")
            
    elif not user_text.startswith("/"):
        await message.reply_text("Please forward Terabox links to test.")

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    print("Experiment Bot is running...")
    app.run()

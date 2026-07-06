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
            "use_blur": True,
            "layout_mode": "large" # പുതിയ ഡ്യുവൽ മോഡ് സെറ്റിങ്സ്
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
    return "TeraBox Dual Mode Bot is Running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# --- Commands ---
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Welcome to TeraBox Dual Mode Bot! ✨\n\nUse /mode_large for big photos or /mode_magic for fake thumbnails.")

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

# --- പുതിയ ഡ്യുവൽ മോഡ് കമാൻഡുകൾ ---
@app.on_message(filters.command("mode_large") & filters.private)
async def mode_large(client, message):
    update_settings(message.chat.id, "layout_mode", "large")
    await message.reply_text("🖼 **Large Photo Mode Enabled!**\nപോസ്റ്റുകൾ വലിയ ഫോട്ടോകളായി വരും (ഫേക്ക് ഫോട്ടോ കാണിക്കില്ല, പകരം ബ്ലർ വരും).")

@app.on_message(filters.command("mode_magic") & filters.private)
async def mode_magic(client, message):
    update_settings(message.chat.id, "layout_mode", "magic")
    await message.reply_text("✨ **Magic File Mode Enabled!**\nപോസ്റ്റുകൾ ചെറിയ ഫയലുകളായി വരും, അതിൽ നിങ്ങളുടെ ഫേക്ക് ഫോട്ടോ കാണിക്കും.")

@app.on_message(filters.command("enable_blur") & filters.private)
async def enable_blur(client, message):
    update_settings(message.chat.id, "use_blur", True)
    await message.reply_text("✅ Blur enabled!")

@app.on_message(filters.command("disable_blur") & filters.private)
async def disable_blur(client, message):
    update_settings(message.chat.id, "use_blur", False)
    await message.reply_text("✅ Blur disabled!")

@app.on_message(filters.command("add_header") & filters.private)
async def add_header(client, message):
    text = message.text.replace("/add_header", "").strip()
    update_settings(message.chat.id, "header", text + "\n\n" if text else "")
    await message.reply_text("✅ Header updated.")

@app.on_message(filters.command("add_footer") & filters.private)
async def add_footer(client, message):
    text = message.text.replace("/add_footer", "").strip()
    update_settings(message.chat.id, "footer", "\n\n" + text if text else "")
    await message.reply_text("✅ Footer updated.")

@app.on_message(filters.command("channel") & filters.private)
async def set_channel(client, message):
    text = message.text.replace("/channel", "").strip()
    update_settings(message.chat.id, "channel", f"\n📢 Join: {text}" if text else "")
    await message.reply_text("✅ Channel updated.")

@app.on_message(filters.command("set_link_text") & filters.private)
async def set_link_text(client, message):
    text = message.text.replace("/set_link_text", "").strip()
    if text:
        update_settings(message.chat.id, "link_text", text + " ")
        await message.reply_text(f"✅ Link text set to: {text} 1, {text} 2, etc.")

# --- Link Extraction & Dual Mode Processing ---
@app.on_message((filters.text | filters.photo) & filters.private)
async def handle_link(client, message):
    user_text = message.text or message.caption
    if not user_text: return
    
    urls = re.findall(r"(https?://\S*(?:terabox|terashare)\S*)", user_text, re.IGNORECASE)
    
    if urls:
        wait_msg = await message.reply_text("Designing your post... 🎨")
        settings = get_settings(message.chat.id)
        
        unique_urls = list(dict.fromkeys(urls))
        formatted_links = ""
        link_prefix = settings.get('link_text', '🍓Video ')
        for index, url in enumerate(unique_urls, start=1):
            formatted_links += f"{link_prefix}{index}\n{url}\n\n\n"
        formatted_links = formatted_links.strip()
        
        final_caption = f"{settings.get('header', '')}{formatted_links}{settings.get('channel', '')}{settings.get('footer', '')}"
        
        try:
            custom_photo = settings.get("custom_photo_id")
            fake_photo = settings.get("fake_photo_id")
            
            if custom_photo and settings.get("enable_picture", True):
                doc_path = await client.download_media(custom_photo)
                
                # --- Mode 1: മാജിക് ഫയൽ മോഡ് (ചെറിയ ഫയൽ + ഫേക്ക് ഫോട്ടോ) ---
                if settings.get("layout_mode") == "magic":
                    thumb_path = await client.download_media(fake_photo) if fake_photo else None
                    if settings.get("use_blur", True) and thumb_path:
                        try:
                            await client.send_document(
                                chat_id=message.chat.id, 
                                document=doc_path, 
                                thumbnail=thumb_path, 
                                file_name="🔞_Click_To_Open_🍓.jpg", # ആകർഷകമായ പേര്
                                caption=final_caption
                            )
                        except TypeError:
                            await client.send_document(
                                chat_id=message.chat.id, document=doc_path, thumb=thumb_path, file_name="🔞_Click_To_Open_🍓.jpg", caption=final_caption
                            )
                    else:
                        await client.send_document(chat_id=message.chat.id, document=doc_path, file_name="🔞_Click_To_Open_🍓.jpg", caption=final_caption)
                    if thumb_path and os.path.exists(thumb_path): os.remove(thumb_path)
                
                # --- Mode 2: വലിയ ഫോട്ടോ മോഡ് (വലിയ സൈസ് + ഒഫീഷ്യൽ ബ്ലർ) ---
                else:
                    await client.send_photo(
                        chat_id=message.chat.id, 
                        photo=doc_path, 
                        caption=final_caption,
                        has_spoiler=settings.get("use_blur", True) # ഒഫീഷ്യൽ ടെലിഗ്രാം സ്പോയിലർ ഉപയോഗിക്കുന്നു
                    )
                
                if doc_path and os.path.exists(doc_path): os.remove(doc_path)
                await wait_msg.delete()
            else:
                await wait_msg.edit_text(final_caption)
                
        except Exception as e:
            await wait_msg.edit_text(f"❌ System Error: {str(e)}")
            
    elif not user_text.startswith("/"):
        await message.reply_text("Please forward Terabox links.")

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    print("Dual Mode Bot is running...")
    app.run()

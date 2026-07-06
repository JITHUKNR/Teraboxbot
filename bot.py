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
MONGO_URL = os.environ.get("MONGO_URL", "") # MongoDB URL ഇവിടെ നൽകണം
# ------------------------------------

app = Client("my_terabox_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- MongoDB Setup ---
mongo_client = pymongo.MongoClient(MONGO_URL)
db = mongo_client["terabox_database"]
settings_col = db["user_settings"]

# ഡാറ്റാബേസിൽ നിന്നും സെറ്റിങ്സ് എടുക്കാനുള്ള ഫംഗ്ഷൻ (യൂസർ ഐഡി അനുസരിച്ച്)
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
            "use_blur": True
        }
        settings_col.insert_one(default_settings)
        return default_settings
    return settings

# ഡാറ്റാബേസിലെ സെറ്റിങ്സ് അപ്ഡേറ്റ് ചെയ്യാനുള്ള ഫംഗ്ഷൻ
def update_settings(user_id, key, value):
    settings_col.update_one({"user_id": user_id}, {"$set": {key: value}}, upsert=True)

# --- Dummy Web Server (For UptimeRobot) ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "TeraBox MongoDB Bot is Running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)
# ------------------------------------------

# --- Commands ---
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Hello! Your custom TeraBox Magic Photo bot with MongoDB is ready.\n\nForward or paste the converted messages here.")

@app.on_message(filters.command("set_photo") & filters.private)
async def set_photo(client, message):
    if message.photo:
        file_id = message.photo.file_id
        update_settings(message.chat.id, "custom_photo_id", file_id)
        update_settings(message.chat.id, "enable_picture", True)
        await message.reply_text("✅ Original Custom photo saved permanently in Database!")
    else:
        await message.reply_text("❌ Please send a photo along with the /set_photo command.")

@app.on_message(filters.command("set_fake_photo") & filters.private)
async def set_fake_photo(client, message):
    if message.photo:
        file_id = message.photo.file_id
        update_settings(message.chat.id, "fake_photo_id", file_id)
        await message.reply_text("✅ Fake photo (Thumbnail) saved permanently in Database!")
    else:
        await message.reply_text("❌ Please send a blurred/fake photo along with the /set_fake_photo command.")

@app.on_message(filters.command("add_header") & filters.private)
async def add_header(client, message):
    text = message.text.replace("/add_header", "").strip()
    header_val = text + "\n\n" if text else ""
    update_settings(message.chat.id, "header", header_val)
    await message.reply_text(f"✅ Header set to:\n{text}" if text else "❌ Header removed.")

@app.on_message(filters.command("add_footer") & filters.private)
async def add_footer(client, message):
    text = message.text.replace("/add_footer", "").strip()
    footer_val = "\n\n" + text if text else ""
    update_settings(message.chat.id, "footer", footer_val)
    await message.reply_text(f"✅ Footer set to:\n{text}" if text else "❌ Footer removed.")

@app.on_message(filters.command("channel") & filters.private)
async def set_channel(client, message):
    text = message.text.replace("/channel", "").strip()
    channel_val = f"\n📢 Join: {text}" if text else ""
    update_settings(message.chat.id, "channel", channel_val)
    await message.reply_text(f"✅ Channel set to: {text}" if text else "❌ Channel removed.")

@app.on_message(filters.command("set_link_text") & filters.private)
async def set_link_text(client, message):
    text = message.text.replace("/set_link_text", "").strip()
    if text:
        update_settings(message.chat.id, "link_text", text + " ")
        await message.reply_text(f"✅ Link text set to: {text} 1, {text} 2, etc.")
    else:
        await message.reply_text("❌ Please provide text. Example: /set_link_text 🎬 Episode")

@app.on_message(filters.command("enable_blur") & filters.private)
async def enable_blur(client, message):
    update_settings(message.chat.id, "use_blur", True)
    await message.reply_text("✅ Magic Blur enabled!")

@app.on_message(filters.command("disable_blur") & filters.private)
async def disable_blur(client, message):
    update_settings(message.chat.id, "use_blur", False)
    await message.reply_text("✅ Magic Blur disabled!")

@app.on_message(filters.command("disable_picture") & filters.private)
async def disable_picture(client, message):
    update_settings(message.chat.id, "enable_picture", False)
    await message.reply_text("✅ Picture disabled.")

@app.on_message(filters.command("enable_picture") & filters.private)
async def enable_picture(client, message):
    update_settings(message.chat.id, "enable_picture", True)
    await message.reply_text("✅ Picture enabled.")

# --- Link Extraction & Magic Photo Formatting ---
@app.on_message((filters.text | filters.photo) & filters.private)
async def handle_link(client, message):
    user_text = message.text or message.caption
    if not user_text:
        return
    
    urls = re.findall(r"(https?://\S*(?:terabox|terashare)\S*)", user_text, re.IGNORECASE)
    
    if urls:
        wait_msg = await message.reply_text("Preparing your magic post... ✨")
        
        # ഡാറ്റാബേസിൽ നിന്നും ഈ യൂസറുടെ സെറ്റിങ്സ് എടുക്കുന്നു
        settings = get_settings(message.chat.id)
        
        unique_urls = list(dict.fromkeys(urls))
        formatted_links = ""
        for index, url in enumerate(unique_urls, start=1):
            formatted_links += f"{settings['link_text']}{index}\n{url}\n\n\n"
        formatted_links = formatted_links.strip()
        
        try:
            final_caption = f"{settings['header']}{formatted_links}{settings['channel']}{settings['footer']}"
            
            if settings["enable_picture"] and settings["custom_photo_id"]:
                
                # റീസ്റ്റാർട്ട് ആയാലും ഫയൽ മിസ്സ് ആവാതിരിക്കാൻ താൽക്കാലികമായി ഡൗൺലോഡ് ചെയ്യുന്നു
                doc_path = "original_photo.jpg"
                if not os.path.exists(doc_path):
                    await client.download_media(settings["custom_photo_id"], file_name=doc_path)
                
                if settings["fake_photo_id"] and settings["use_blur"]:
                    thumb_path = "fake_photo.jpg"
                    if not os.path.exists(thumb_path):
                        await client.download_media(settings["fake_photo_id"], file_name=thumb_path)
                    
                    try:
                        await client.send_document(
                            chat_id=message.chat.id, document=doc_path, thumbnail=thumb_path, file_name="Click_To_Open.jpg", caption=final_caption
                        )
                    except TypeError:
                        await client.send_document(
                            chat_id=message.chat.id, document=doc_path, thumb=thumb_path, file_name="Click_To_Open.jpg", caption=final_caption
                        )
                else:
                    await client.send_photo(chat_id=message.chat.id, photo=doc_path, caption=final_caption)
                
                await wait_msg.delete()
            else:
                await wait_msg.edit_text(final_caption)
                
        except Exception as e:
            await wait_msg.edit_text(f"❌ An error occurred: {str(e)}")
    elif not user_text.startswith("/"):
        await message.reply_text("Please forward a message containing Terabox links.")

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    print("Bot is running...")
    app.run()

from pyrogram import Client, filters
import os
import threading
import re
from flask import Flask

# --- Render Environment Variables ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
# ------------------------------------

app = Client("my_terabox_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# User Settings (പുതിയതായി ഫേക്ക് ഫോട്ടോ കൂടി ചേർത്തു)
USER_SETTINGS = {
    "header": "",
    "footer": "",
    "channel": "",
    "custom_photo_id": None, # ഒറിജിനൽ ഫോട്ടോ
    "fake_photo_id": None,   # പുറമെ കാണിക്കാനുള്ള ഫേക്ക് (ബ്ലർ) ഫോട്ടോ
    "enable_picture": True,
    "link_text": "🍓Video "
}

# --- Dummy Web Server (For UptimeRobot) ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "TeraBox Custom Format Bot is Running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)
# ------------------------------------------

# --- Commands ---
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Hello! Your custom TeraBox Magic Photo bot is ready.\n\nForward or paste the converted messages here.")

# 1. ഒറിജിനൽ ഫോട്ടോ സെറ്റ് ചെയ്യാൻ
@app.on_message(filters.command("set_photo") & filters.private)
async def set_photo(client, message):
    if message.photo:
        USER_SETTINGS["custom_photo_id"] = message.photo.file_id
        USER_SETTINGS["enable_picture"] = True
        await message.reply_text("✅ Original Custom photo set successfully! (ഇത് ഡൗൺലോഡ് ചെയ്യുമ്പോൾ കാണേണ്ട ഫോട്ടോയാണ്)")
    else:
        await message.reply_text("❌ Please send a photo along with the /set_photo command.")

# 2. ഫേക്ക് ഫോട്ടോ (പുറമെ കാണേണ്ടത്) സെറ്റ് ചെയ്യാൻ
@app.on_message(filters.command("set_fake_photo") & filters.private)
async def set_fake_photo(client, message):
    if message.photo:
        USER_SETTINGS["fake_photo_id"] = message.photo.file_id
        await message.reply_text("✅ Fake photo (Thumbnail) set successfully! (ഇത് പുറമെ കാണിക്കുന്ന പറ്റിക്കൽ ഫോട്ടോയാണ്)")
    else:
        await message.reply_text("❌ Please send a blurred/fake photo along with the /set_fake_photo command.")

@app.on_message(filters.command("add_header") & filters.private)
async def add_header(client, message):
    text = message.text.replace("/add_header", "").strip()
    USER_SETTINGS["header"] = text + "\n\n" if text else ""
    await message.reply_text(f"✅ Header set to:\n{text}" if text else "❌ Please provide text with the command.")

@app.on_message(filters.command("add_footer") & filters.private)
async def add_footer(client, message):
    text = message.text.replace("/add_footer", "").strip()
    USER_SETTINGS["footer"] = "\n\n" + text if text else ""
    await message.reply_text(f"✅ Footer set to:\n{text}" if text else "❌ Please provide text with the command.")

@app.on_message(filters.command("channel") & filters.private)
async def set_channel(client, message):
    text = message.text.replace("/channel", "").strip()
    if text:
        USER_SETTINGS["channel"] = f"\n📢 Join: {text}"
        await message.reply_text(f"✅ Channel set to: {text}")
    else:
        await message.reply_text("❌ Please provide a channel link or username.")

@app.on_message(filters.command("set_link_text") & filters.private)
async def set_link_text(client, message):
    text = message.text.replace("/set_link_text", "").strip()
    if text:
        USER_SETTINGS["link_text"] = text + " "
        await message.reply_text(f"✅ Link text set to: {text} 1, {text} 2, etc.")
    else:
        await message.reply_text("❌ Please provide text. Example: /set_link_text 🎬 Episode")

@app.on_message(filters.command("disable_picture") & filters.private)
async def disable_picture(client, message):
    USER_SETTINGS["enable_picture"] = False
    await message.reply_text("✅ Picture disabled. Only text will be sent.")

@app.on_message(filters.command("enable_picture") & filters.private)
async def enable_picture(client, message):
    USER_SETTINGS["enable_picture"] = True
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
        
        unique_urls = list(dict.fromkeys(urls))
        
        formatted_links = ""
        for index, url in enumerate(unique_urls, start=1):
            formatted_links += f"{USER_SETTINGS['link_text']}{index}\n{url}\n\n\n"
            
        formatted_links = formatted_links.strip()
        
        try:
            final_caption = f"{USER_SETTINGS['header']}{formatted_links}{USER_SETTINGS['channel']}{USER_SETTINGS['footer']}"
            
            if USER_SETTINGS["enable_picture"] and USER_SETTINGS["custom_photo_id"]:
                
                # മാജിക് ഫോട്ടോ വർക്ക് ചെയ്യുന്ന ഭാഗം
                if USER_SETTINGS["fake_photo_id"]:
                    await client.send_document(
                        chat_id=message.chat.id, 
                        document=USER_SETTINGS["custom_photo_id"], # ഒറിജിനൽ ഫോട്ടോ
                        thumb=USER_SETTINGS["fake_photo_id"],      # ഫേക്ക് തമ്പ്‌നെയിൽ
                        file_name="Click_To_Open.jpg",             # ഫയലിന്റെ പേര്
                        caption=final_caption
                    )
                # ഫേക്ക് ഫോട്ടോ കൊടുത്തിട്ടില്ലെങ്കിൽ സാധാരണ പോലെ പോകും
                else:
                    await client.send_photo(
                        chat_id=message.chat.id, 
                        photo=USER_SETTINGS["custom_photo_id"], 
                        caption=final_caption
                    )
                await wait_msg.delete()
            else:
                await wait_msg.edit_text(final_caption)
                
        except Exception as e:
            await wait_msg.edit_text("❌ An error occurred. Please try again.")
    elif not user_text.startswith("/"):
        await message.reply_text("Please forward a message containing Terabox links.")

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    print("Bot is running...")
    app.run()

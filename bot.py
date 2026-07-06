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

# യൂസറുടെ സെറ്റിങ്സുകൾ സേവ് ചെയ്തു വെക്കാൻ
USER_SETTINGS = {
    "header": "",
    "footer": "",
    "channel": "",
    "custom_photo_id": None,
    "enable_picture": True
}

# --- Dummy Web Server (UptimeRobot-ന് വേണ്ടി) ---
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
    await message.reply_text("ഹലോ! നിങ്ങളുടെ കസ്റ്റം TeraBox ബോട്ട് റെഡി.\n\nഒഫീഷ്യൽ ബോട്ടിൽ നിന്നും കൺവെർട്ട് ചെയ്തു കിട്ടുന്ന മെസ്സേജ് ഇങ്ങോട്ട് ഫോർവേഡ് ചെയ്യുകയോ പേസ്റ്റ് ചെയ്യുകയോ ചെയ്യുക.")

@app.on_message(filters.command("set_photo") & filters.private)
async def set_photo(client, message):
    if message.photo:
        USER_SETTINGS["custom_photo_id"] = message.photo.file_id
        USER_SETTINGS["enable_picture"] = True
        await message.reply_text("✅ കസ്റ്റം ഫോട്ടോ സെറ്റ് ചെയ്തു!")
    else:
        await message.reply_text("❌ ദയവായി ഒരു ഫോട്ടോയോടൊപ്പം /set_photo എന്ന് അയക്കുക.")

@app.on_message(filters.command("add_header") & filters.private)
async def add_header(client, message):
    text = message.text.replace("/add_header", "").strip()
    USER_SETTINGS["header"] = text + "\n\n" if text else ""
    await message.reply_text(f"✅ ഹെഡർ സെറ്റ് ചെയ്തു:\n{text}" if text else "❌ കമാൻഡിനൊപ്പം ടെക്സ്റ്റ് നൽകുക.")

@app.on_message(filters.command("add_footer") & filters.private)
async def add_footer(client, message):
    text = message.text.replace("/add_footer", "").strip()
    USER_SETTINGS["footer"] = "\n\n" + text if text else ""
    await message.reply_text(f"✅ ഫൂട്ടർ സെറ്റ് ചെയ്തു:\n{text}" if text else "❌ കമാൻഡിനൊപ്പം ടെക്സ്റ്റ് നൽകുക.")

@app.on_message(filters.command("channel") & filters.private)
async def set_channel(client, message):
    text = message.text.replace("/channel", "").strip()
    if text:
        USER_SETTINGS["channel"] = f"\n\n📢 ജോയിൻ: {text}"
        await message.reply_text(f"✅ ചാനൽ സെറ്റ് ചെയ്തു: {text}")
    else:
        await message.reply_text("❌ കമാൻഡിനൊപ്പം ചാനൽ ലിങ്ക് കൂടി നൽകുക.")

@app.on_message(filters.command("disable_picture") & filters.private)
async def disable_picture(client, message):
    USER_SETTINGS["enable_picture"] = False
    await message.reply_text("✅ ഫോട്ടോ ഒഴിവാക്കി. ഇനി ടെക്സ്റ്റ് മാത്രമേ വരൂ.")

@app.on_message(filters.command("enable_picture") & filters.private)
async def enable_picture(client, message):
    USER_SETTINGS["enable_picture"] = True
    await message.reply_text("✅ ഫോട്ടോ ഓൺ ആക്കി.")

# --- Link Extraction & Formatting (ഇവിടെയാണ് മാറ്റം വരുത്തിയത്) ---
# filters.text ന് പകരം ഫോട്ടോയും ക്യാപ്ഷനും കൂടി ഉൾപ്പെടുത്തി
@app.on_message((filters.text | filters.photo) & filters.private)
async def handle_link(client, message):
    # മെസ്സേജ് ടെക്സ്റ്റ് ആണെങ്കിലും ഫോട്ടോയുടെ ക്യാപ്ഷൻ ആണെങ്കിലും അത് വേർതിരിച്ചെടുക്കുന്നു
    user_text = message.text or message.caption
    
    if not user_text:
        return
    
    # മെസ്സേജിൽ നിന്നും Terabox/Terashare ലിങ്ക് മാത്രം യാതൊരു മാറ്റവുമില്ലാതെ വലിച്ചെടുക്കുന്നു
    url_match = re.search(r"(https?://\S*(?:terabox|terashare)\S*)", user_text, re.IGNORECASE)
    
    if url_match:
        wait_msg = await message.reply_text("ഡിസൈൻ തയ്യാറാക്കുന്നു... 🎨")
        extracted_link = url_match.group(1) 
        
        try:
            # പുതിയ ക്യാപ്ഷൻ നിർമ്മിക്കുന്നു
            final_caption = f"{USER_SETTINGS['header']}🔗 ലിങ്ക്: {extracted_link}{USER_SETTINGS['channel']}{USER_SETTINGS['footer']}"
            
            # കസ്റ്റം ഫോട്ടോ വെച്ച് അയക്കുന്നു
            if USER_SETTINGS["enable_picture"] and USER_SETTINGS["custom_photo_id"]:
                await client.send_photo(
                    chat_id=message.chat.id, 
                    photo=USER_SETTINGS["custom_photo_id"], 
                    caption=final_caption
                )
                await wait_msg.delete()
            else:
                await wait_msg.edit_text(final_caption)
                
        except Exception as e:
            await wait_msg.edit_text("❌ എറർ സംഭവിച്ചു. ദയവായി വീണ്ടും ശ്രമിക്കുക.")
    elif not user_text.startswith("/"):
        await message.reply_text("ദയവായി ഒഫീഷ്യൽ ബോട്ടിൽ നിന്നുള്ള മെസ്സേജ് (അല്ലെങ്കിൽ ലിങ്ക്) ഇങ്ങോട്ട് അയക്കുക.")

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    print("ബോട്ട് റൺ ചെയ്യുന്നുണ്ട്...")
    app.run()

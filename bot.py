from pyrogram import Client, filters
import os
from flask import Flask
import threading

# --- Render Environment Variables ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
NDUS_COOKIE = os.environ.get("NDUS_COOKIE", "")
# ------------------------------------

app = Client("my_terabox_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
USER_SETTINGS = {"header": "", "footer": "", "channel": "", "custom_photo_id": None, "enable_picture": True}

# --- Dummy Web Server (Render-നെ സ്ലീപ്പ് ആവാതെ നോക്കാൻ) ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "TeraBox Bot is Running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)
# --------------------------------------------------------

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("ഹലോ! നിങ്ങളുടെ അഡ്വാൻസ്ഡ് TeraBox Link Converter ബോട്ട് റെഡി.")

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
    await message.reply_text(f"✅ ഹെഡർ സെറ്റ് ചെയ്തു:\n{text}" if text else "❌ ടെക്സ്റ്റ് നൽകുക.")

@app.on_message(filters.command("add_footer") & filters.private)
async def add_footer(client, message):
    text = message.text.replace("/add_footer", "").strip()
    USER_SETTINGS["footer"] = "\n\n" + text if text else ""
    await message.reply_text(f"✅ ഫൂട്ടർ സെറ്റ് ചെയ്തു:\n{text}" if text else "❌ ടെക്സ്റ്റ് നൽകുക.")

@app.on_message(filters.text & filters.private)
async def handle_link(client, message):
    user_text = message.text
    if "terabox" in user_text or "terashare" in user_text:
        wait_msg = await message.reply_text("പ്രോസസ്സ് ചെയ്യുന്നു... ⏳")
        try:
            # (ഇവിടെ യഥാർത്ഥ കൺവെർഷൻ വരും. തൽക്കാലം ഡെമ്മി ലിങ്ക്)
            new_converted_link = "https://terabox.com/s/നിങ്ങളുടെ_പുതിയ_ലിങ്ക്" 
            final_caption = f"{USER_SETTINGS['header']}🔗 ലിങ്ക്: {new_converted_link}{USER_SETTINGS['channel']}{USER_SETTINGS['footer']}"
            
            if USER_SETTINGS["enable_picture"] and USER_SETTINGS["custom_photo_id"]:
                await client.send_photo(chat_id=message.chat.id, photo=USER_SETTINGS["custom_photo_id"], caption=final_caption)
                await wait_msg.delete()
            else:
                await wait_msg.edit_text(final_caption)
        except Exception as e:
            await wait_msg.edit_text("❌ എറർ സംഭവിച്ചു.")
    elif not user_text.startswith("/"):
        await message.reply_text("ദയവായി ശരിയായ TeraBox ലിങ്ക് അയക്കുക.")

if __name__ == "__main__":
    # വെബ് സെർവറും ബോട്ടുo ഒരുമിച്ച് റൺ ചെയ്യുന്നു
    threading.Thread(target=run_web).start()
    print("ബോട്ട് റൺ ചെയ്യുന്നുണ്ട്...")
    app.run()

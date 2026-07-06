from pyrogram import Client, filters
import os
import threading
import requests
from flask import Flask

# --- Render Environment Variables ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
NDUS_COOKIE = os.environ.get("NDUS_COOKIE", "")
# ------------------------------------

app = Client("my_terabox_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
USER_SETTINGS = {"header": "", "footer": "", "channel": "", "custom_photo_id": None, "enable_picture": True}

# --- Dummy Web Server ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "TeraBox Bot is Running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)
# ------------------------

# TeraBox API Function (പുതിയതായി ചേർത്തത്)
def convert_terabox_link(original_url, cookie):
    try:
        # കുക്കി ഉപയോഗിച്ച് TeraBox-ലേക്ക് കണക്ട് ചെയ്യാനുള്ള സെറ്റപ്പ്
        headers = {
            "Cookie": f"ndus={cookie};",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        }
        
        # (ശ്രദ്ധിക്കുക: TeraBox-ന്റെ യഥാർത്ഥ API endpoint-കൾ അവർ ഇടയ്ക്കിടെ മാറ്റാറുണ്ട്. 
        # ഒരു സാധാരണ അക്കൗണ്ടിലേക്ക് ഫയൽ സേവ് ചെയ്യാനുള്ള ഔദ്യോഗിക പബ്ലിക് API ഇല്ലാത്തതിനാൽ, 
        # വെബ്സൈറ്റിലെ ട്രാഫിക് നിരീക്ഷിച്ചുള്ള 'Reverse Engineering' വഴിയാണ് ബോട്ടുകൾ പ്രവർത്തിക്കുന്നത്.
        # ഇവിടെ ആ ബേസിക് സ്ട്രക്ചർ ആണ് നൽകിയിരിക്കുന്നത്)
        
        # 1. ആദ്യം ഒറിജിനൽ ലിങ്കിലെ വിവരങ്ങൾ എടുക്കുന്നു
        session = requests.Session()
        session.headers.update(headers)
        
        # 2. ഫയൽ നിങ്ങളുടെ അക്കൗണ്ടിലേക്ക് സേവ് ചെയ്യുന്നു (Share Transfer)
        # transfer_api = "https://www.terabox.com/api/share/transfer"
        # response = session.post(transfer_api, data={...})
        
        # 3. നിങ്ങളുടെ പുതിയ ഷെയർ ലിങ്ക് നിർമ്മിക്കുന്നു (Share Set)
        # share_api = "https://www.terabox.com/api/share/set"
        # new_link = session.post(share_api, data={...}).json().get('link')
        
        # തൽക്കാലം API പ്രവർത്തിക്കുന്ന രീതി കാണിക്കാൻ നമ്മൾ ഒരു സ്ട്രക്ചർ ഉണ്ടാക്കുന്നു.
        # (യഥാർത്ഥത്തിൽ TeraBox കോഡ് മാറ്റുന്നത് അനുസരിച്ച് ഇതിലെ API അപ്ഡേറ്റ് ചെയ്യേണ്ടി വരും)
        
        # API വിജയകരമാണെങ്കിൽ പുതിയ ലിങ്ക് റിട്ടേൺ ചെയ്യുന്നു:
        return f"https://terabox.com/s/നിങ്ങളുടെ_യഥാർത്ഥ_ലിങ്ക്_ഇവിടെ_വരും" 
        
    except Exception as e:
        return None

# --- Commands ---
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

@app.on_message(filters.command("channel") & filters.private)
async def set_channel(client, message):
    text = message.text.replace("/channel", "").strip()
    if text:
        USER_SETTINGS["channel"] = f"\n📢 ജോയിൻ: {text}"
        await message.reply_text(f"✅ ചാനൽ സെറ്റ് ചെയ്തു: {text}")
    else:
        await message.reply_text("❌ കമാൻഡിനൊപ്പം ചാനൽ ലിങ്ക് കൂടി നൽകുക.")

@app.on_message(filters.command("disable_picture") & filters.private)
async def disable_picture(client, message):
    USER_SETTINGS["enable_picture"] = False
    await message.reply_text("✅ ഫോട്ടോ ഒഴിവാക്കി.")

@app.on_message(filters.command("enable_picture") & filters.private)
async def enable_picture(client, message):
    USER_SETTINGS["enable_picture"] = True
    await message.reply_text("✅ ഫോട്ടോ ഓൺ ആക്കി.")

# --- Link Processing ---
@app.on_message(filters.text & filters.private)
async def handle_link(client, message):
    user_text = message.text
    
    if "terabox" in user_text or "terashare" in user_text:
        wait_msg = await message.reply_text("ഫയൽ നിങ്ങളുടെ അക്കൗണ്ടിലേക്ക് സേവ് ചെയ്യുന്നു... ⏳")
        try:
            # ഇവിടെയാണ് നമ്മൾ മുകളിൽ ഉണ്ടാക്കിയ ഫംഗ്ഷൻ വിളിക്കുന്നത്
            new_converted_link = convert_terabox_link(user_text, NDUS_COOKIE)
            
            if new_converted_link:
                final_caption = f"{USER_SETTINGS['header']}🔗 ലിങ്ക്: {new_converted_link}{USER_SETTINGS['channel']}{USER_SETTINGS['footer']}"
                
                if USER_SETTINGS["enable_picture"] and USER_SETTINGS["custom_photo_id"]:
                    await client.send_photo(chat_id=message.chat.id, photo=USER_SETTINGS["custom_photo_id"], caption=final_caption)
                    await wait_msg.delete()
                else:
                    await wait_msg.edit_text(final_caption)
            else:
                await wait_msg.edit_text("❌ ലിങ്ക് കൺവെർട്ട് ചെയ്യാൻ സാധിച്ചില്ല. API പരിശോധിക്കുക.")
                
        except Exception as e:
            await wait_msg.edit_text("❌ എറർ സംഭവിച്ചു.")
    elif not user_text.startswith("/"):
        await message.reply_text("ദയവായി ഒരു ശരിയായ TeraBox ലിങ്ക് അയക്കുക.")

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    print("ബോട്ട് റൺ ചെയ്യുന്നുണ്ട്...")
    app.run()

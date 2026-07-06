from pyrogram import Client, filters
import os

# --- Render Environment Variables ---
# Render-ൽ കൊടുക്കുന്ന variables ഇവിടെ os.environ വഴി കോഡിലേക്ക് എടുക്കുന്നു.
# ശ്രദ്ധിക്കുക: API_ID എപ്പോഴും ഒരു നമ്പർ (Integer) ആയിരിക്കണം.
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
NDUS_COOKIE = os.environ.get("NDUS_COOKIE", "")
# ------------------------------------

app = Client("my_terabox_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# യൂസറുടെ സെറ്റിങ്സുകൾ സേവ് ചെയ്തു വെക്കാൻ ഒരു ഡിക്ഷ്ണറി
USER_SETTINGS = {
    "header": "",
    "footer": "",
    "channel": "",
    "custom_photo_id": None,
    "enable_picture": True,
    "enable_text": False
}

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("ഹലോ! നിങ്ങളുടെ അഡ്വാൻസ്ഡ് TeraBox Link Converter ബോട്ട് റെഡി.\n\nസെറ്റിങ്സുകൾ മാറ്റാൻ താഴെയുള്ള കമാൻഡുകൾ ഉപയോഗിക്കുക:\n/set_photo - കസ്റ്റം ഫോട്ടോ വെക്കാൻ\n/add_header - മുകളിൽ ടെക്സ്റ്റ് വെക്കാൻ\n/add_footer - താഴെ ടെക്സ്റ്റ് വെക്കാൻ\n/channel - ചാനൽ ലിങ്ക് വെക്കാൻ\n/disable_picture - ഫോട്ടോ ഒഴിവാക്കാൻ")

# --- കസ്റ്റമൈസേഷൻ കമാൻഡുകൾ ---

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
    if text:
        USER_SETTINGS["header"] = text + "\n\n"
        await message.reply_text(f"✅ ഹെഡർ സെറ്റ് ചെയ്തു:\n{text}")
    else:
        await message.reply_text("❌ കമാൻഡിനൊപ്പം ഹെഡർ ടെക്സ്റ്റ് കൂടി നൽകുക. ഉദാ: /add_header Watch Now!")

@app.on_message(filters.command("add_footer") & filters.private)
async def add_footer(client, message):
    text = message.text.replace("/add_footer", "").strip()
    if text:
        USER_SETTINGS["footer"] = "\n\n" + text
        await message.reply_text(f"✅ ഫൂട്ടർ സെറ്റ് ചെയ്തു:\n{text}")
    else:
        await message.reply_text("❌ കമാൻഡിനൊപ്പം ഫൂട്ടർ ടെക്സ്റ്റ് കൂടി നൽകുക.")

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
    await message.reply_text("✅ ഫോട്ടോ ഒഴിവാക്കി. ഇനി ടെക്സ്റ്റ് മാത്രമേ വരൂ.")

@app.on_message(filters.command("enable_picture") & filters.private)
async def enable_picture(client, message):
    USER_SETTINGS["enable_picture"] = True
    await message.reply_text("✅ ഫോട്ടോ ഓൺ ആക്കി.")

# --- ലിങ്ക് പ്രോസസ്സ് ചെയ്യുന്ന ഭാഗം ---

@app.on_message(filters.text & filters.private)
async def handle_link(client, message):
    user_text = message.text
    
    if "terabox" in user_text or "terashare" in user_text:
        wait_msg = await message.reply_text("പ്രോസസ്സ് ചെയ്യുന്നു... ⏳")
        try:
            # (ഇവിടെ യഥാർത്ഥ കൺവെർഷൻ API വരും. തൽക്കാലം ഡെമ്മി ലിങ്ക് ഉപയോഗിക്കുന്നു)
            new_converted_link = "https://terabox.com/s/നിങ്ങളുടെ_പുതിയ_ലിങ്ക്" 
            
            # സെറ്റിങ്സ് ഉപയോഗിച്ച് പുതിയ ക്യാപ്ഷൻ നിർമ്മിക്കുന്നു
            final_caption = f"{USER_SETTINGS['header']}🔗 ലിങ്ക്: {new_converted_link}{USER_SETTINGS['channel']}{USER_SETTINGS['footer']}"
            
            # ഫോട്ടോ ആവശ്യമുണ്ടോ എന്ന് നോക്കുന്നു
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
            await wait_msg.edit_text("❌ എറർ സംഭവിച്ചു.")
    elif not user_text.startswith("/"):
        await message.reply_text("ദയവായി ശരിയായ TeraBox ലിങ്ക് അയക്കുക.")

print("ബോട്ട് റൺ ചെയ്യുന്നുണ്ട്...")
app.run()

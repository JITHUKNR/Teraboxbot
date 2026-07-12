import logging
logging.basicConfig(level=logging.INFO) 

from pyrogram import Client, filters
import os
import threading
import re
import pymongo
from flask import Flask
from PIL import Image, ImageFilter, ImageDraw, ImageFont 

# --- Render Environment Variables ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URL = os.environ.get("MONGO_URL", "") 
# ------------------------------------

session_name = "terabox_magic_bot"
if os.path.exists(f"{session_name}.session-journal"):
    try: os.remove(f"{session_name}.session-journal")
    except: pass

app = Client(session_name, api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- MongoDB Setup ---
try:
    mongo_client = pymongo.MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000)
    db = mongo_client["my_magic_terabox_db"]
    settings_col = db["magic_bot_settings"]
    mongo_client.admin.command('ping') 
    logging.info("MongoDB Connected Successfully!")
except Exception as e:
    logging.error(f"MongoDB Error: {e}")

FILE_CACHE = {}

def get_settings(user_id):
    try:
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
                "layout_mode": "magic", 
                "file_name": "🔞_Click_To_Open_🍓",
                "watermark": "" 
            }
            settings_col.insert_one(default_settings)
            return default_settings
        return settings
    except Exception as e:
        logging.error(f"DB Fetch Error: {e}")
        return None

def update_settings(user_id, key, value):
    try:
        settings_col.update_one({"user_id": user_id}, {"$set": {key: value}}, upsert=True)
    except Exception as e:
        logging.error(f"DB Update Error: {e}")

def resize_thumbnail(thumb_path):
    try:
        img = Image.open(thumb_path)
        if img.mode != 'RGB': img = img.convert('RGB')
        img.thumbnail((320, 320))
        img.save(thumb_path, "JPEG")
    except Exception as e:
        logging.error(f"Thumbnail error: {e}")

def process_auto_blur(image_path, watermark_text):
    try:
        img = Image.open(image_path)
        if img.mode != 'RGB': img = img.convert('RGB')
        
        img = img.filter(ImageFilter.GaussianBlur(radius=18))
        
        if watermark_text:
            draw = ImageDraw.Draw(img)
            width, height = img.size
            try: font = ImageFont.load_default(size=int(width/12)) 
            except: font = ImageFont.load_default()
            
            try:
                bbox = draw.textbbox((0, 0), watermark_text, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
            except:
                try: text_w, text_h = draw.textlength(watermark_text, font=font), 30
                except: text_w, text_h = (150, 30)
                
            x = (width - text_w) / 2
            y = (height - text_h) / 2
            
            draw.text((x+3, y+3), watermark_text, font=font, fill="black")
            draw.text((x, y), watermark_text, font=font, fill="white")
            
        processed_path = f"blurred_{os.path.basename(image_path)}"
        img.save(processed_path, "JPEG")
        return processed_path
    except Exception as e:
        logging.error(f"Blur Process Error: {e}")
        return image_path

# --- Web Server ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "TeraBox Super Speed Bot is Running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# --- Commands ---
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Welcome to TeraBox Dual Mode Bot! ✨\n\nUse /mode_large, /mode_magic, or the new /mode_auto_blur.")

@app.on_message(filters.command("set_photo") & filters.private)
async def set_photo(client, message):
    if message.photo: file_id = message.photo.file_id
    elif message.document: file_id = message.document.file_id
    else: return await message.reply_text("❌ Please send a photo.")
    update_settings(message.chat.id, "custom_photo_id", file_id)
    if file_id in FILE_CACHE: del FILE_CACHE[file_id]
    await message.reply_text("✅ Original Custom photo saved!")

@app.on_message(filters.command("set_fake_photo") & filters.private)
async def set_fake_photo(client, message):
    if message.photo: file_id = message.photo.file_id
    elif message.document: file_id = message.document.file_id
    else: return await message.reply_text("❌ Please send a fake photo.")
    update_settings(message.chat.id, "fake_photo_id", file_id)
    if file_id in FILE_CACHE: del FILE_CACHE[file_id]
    await message.reply_text("✅ Fake photo (Thumbnail) saved!")

@app.on_message(filters.command("mode_large") & filters.private)
async def mode_large(client, message):
    update_settings(message.chat.id, "layout_mode", "large")
    await message.reply_text("🖼 **Large Photo Mode Enabled!**")

@app.on_message(filters.command("mode_magic") & filters.private)
async def mode_magic(client, message):
    update_settings(message.chat.id, "layout_mode", "magic")
    await message.reply_text("✨ **Magic File Mode Enabled!**")

@app.on_message(filters.command("mode_auto_blur") & filters.private)
async def mode_auto_blur(client, message):
    update_settings(message.chat.id, "layout_mode", "auto_blur")
    await message.reply_text("🌫 **Auto Blur Mode Enabled!**\nനിങ്ങൾ അയക്കുന്ന ഒറിജിനൽ ഫോട്ടോകൾ ഇനിമുതൽ തനിയെ ഫുൾ ബ്ലർ ആകുന്നതാണ്.")

@app.on_message(filters.command("set_watermark") & filters.private)
async def set_watermark(client, message):
    text = message.text.replace("/set_watermark", "").strip()
    update_settings(message.chat.id, "watermark", text)
    if text: await message.reply_text(f"✅ Watermark set to: {text}")
    else: await message.reply_text("✅ Watermark removed.")

@app.on_message(filters.command("enable_blur") & filters.private)
async def enable_blur(client, message):
    update_settings(message.chat.id, "use_blur", True)
    await message.reply_text("✅ Telegram Blur enabled!")

@app.on_message(filters.command("disable_blur") & filters.private)
async def disable_blur(client, message):
    update_settings(message.chat.id, "use_blur", False)
    await message.reply_text("✅ Telegram Blur disabled!")

@app.on_message(filters.command("enable_picture") & filters.private)
async def enable_picture(client, message):
    update_settings(message.chat.id, "enable_picture", True)
    await message.reply_text("✅ Picture enabled.")

@app.on_message(filters.command("disable_picture") & filters.private)
async def disable_picture(client, message):
    update_settings(message.chat.id, "enable_picture", False)
    await message.reply_text("✅ Picture disabled.")

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
        await message.reply_text(f"✅ Link text set to: {text} 1")

@app.on_message(filters.command("set_file_name") & filters.private)
async def set_file_name(client, message):
    text = message.text.replace("/set_file_name", "").strip()
    if text:
        update_settings(message.chat.id, "file_name", text)
        await message.reply_text(f"✅ File name set to: {text}")
    else:
        await message.reply_text("❌ Example: /set_file_name NEW🥵🍓")

# --- Link Extraction (വീഡിയോ സപ്പോർട്ട് ഉൾപ്പെടെ) ---
@app.on_message((filters.text | filters.photo | filters.video | filters.animation | filters.document) & filters.private)
async def handle_link(client, message):
    user_text = message.text or message.caption
    if not user_text: return
    
    urls = re.findall(r"(https?://\S*(?:terabox|terashare)\S*)", user_text, re.IGNORECASE)
    
    if urls:
        settings = get_settings(message.chat.id)
        if not settings: return await message.reply_text("❌ Database Error.")

        wait_msg = await message.reply_text("Designing your post... 🎨")
        
        unique_urls = list(dict.fromkeys(urls))
        formatted_links = ""
        link_prefix = settings.get('link_text', '🍓Video ')
        for index, url in enumerate(unique_urls, start=1):
            formatted_links += f"{link_prefix}{index}\n{url}\n\n\n"
        formatted_links = formatted_links.strip()
        
        final_caption = f"{settings.get('header', '')}{formatted_links}{settings.get('channel', '')}{settings.get('footer', '')}"
        
        try:
            if settings.get("layout_mode") == "auto_blur":
                incoming_media = None
                
                # ഫോട്ടോ ആണെങ്കിൽ
                if message.photo: 
                    incoming_media = message.photo.file_id
                # വീഡിയോ ആണെങ്കിൽ അതിന്റെ കവർ ഫോട്ടോ എടുക്കുന്നു
                elif message.video and message.video.thumbs:
                    incoming_media = message.video.thumbs[0].file_id
                elif message.animation and message.animation.thumbs:
                    incoming_media = message.animation.thumbs[0].file_id
                # ഡോക്യുമെന്റ് ആയിട്ടുള്ള ഇമേജ് ആണെങ്കിൽ
                elif message.document and message.document.mime_type and message.document.mime_type.startswith('image/'):
                    incoming_media = message.document.file_id
                
                if incoming_media:
                    temp_path = await client.download_media(incoming_media)
                    if temp_path:
                        blurred_path = process_auto_blur(temp_path, settings.get("watermark", ""))
                        await client.send_photo(chat_id=message.chat.id, photo=blurred_path, caption=final_caption)
                        
                        if os.path.exists(temp_path): os.remove(temp_path)
                        if os.path.exists(blurred_path): os.remove(blurred_path)
                    await wait_msg.delete()
                    return 
                else:
                    await wait_msg.edit_text("❌ ഈ വീഡിയോയ്ക്ക് കവർ ഫോട്ടോ ലഭ്യമല്ലാത്തതിനാൽ ഓട്ടോ-ബ്ലർ ചെയ്യാൻ കഴിയില്ല. ദയവായി കസ്റ്റം ഫോട്ടോ മോഡ് ഉപയോഗിക്കുക.")
                    return
            
            custom_photo = settings.get("custom_photo_id")
            fake_photo = settings.get("fake_photo_id")
            
            if custom_photo and settings.get("enable_picture", True):
                doc_path = f"{custom_photo}.jpg"
                if custom_photo not in FILE_CACHE or not os.path.exists(doc_path):
                    actual_path = await client.download_media(custom_photo)
                    if actual_path and os.path.exists(actual_path):
                        os.rename(actual_path, doc_path)
                    FILE_CACHE[custom_photo] = doc_path
                
                custom_file_name = settings.get("file_name", "🔞_Click_To_Open_🍓")
                
                if settings.get("layout_mode") == "magic":
                    thumb_path = None
                    if fake_photo:
                        thumb_path = f"{fake_photo}.jpg"
                        if fake_photo not in FILE_CACHE or not os.path.exists(thumb_path):
                            actual_thumb = await client.download_media(fake_photo)
                            if actual_thumb and os.path.exists(actual_thumb):
                                os.rename(actual_thumb, thumb_path)
                            resize_thumbnail(thumb_path)
                            FILE_CACHE[fake_photo] = thumb_path
                            
                    if settings.get("use_blur", True) and thumb_path:
                        try:
                            await client.send_document(chat_id=message.chat.id, document=doc_path, thumbnail=thumb_path, file_name=custom_file_name, caption=final_caption)
                        except TypeError:
                            await client.send_document(chat_id=message.chat.id, document=doc_path, thumb=thumb_path, file_name=custom_file_name, caption=final_caption)
                    else:
                        await client.send_document(chat_id=message.chat.id, document=doc_path, file_name=custom_file_name, caption=final_caption)
                else:
                    await client.send_photo(chat_id=message.chat.id, photo=doc_path, caption=final_caption, has_spoiler=settings.get("use_blur", True))
                
                await wait_msg.delete()
            else:
                await wait_msg.edit_text(final_caption)
                
        except Exception as e:
            logging.error(f"Send Error: {e}")
            await wait_msg.edit_text(f"❌ System Error: {str(e)}")
            
    elif not user_text.startswith("/"):
        await message.reply_text("Please forward Terabox links.")

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    print("Super Speed Bot is running smoothly...")
    app.run()

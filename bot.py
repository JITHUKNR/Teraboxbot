import logging
logging.basicConfig(level=logging.INFO) 

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import os
import asyncio
import threading
import re
import pymongo
import urllib.request
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
post_lock = None # 50 പോസ്റ്റുകൾ ഒരുമിച്ച് വന്നാൽ ബോട്ട് ഹാങ് ആവാതിരിക്കാനുള്ള ലോക്ക്

# സിനിമാറ്റിക് വെബ് ഫോണ്ടുകളുടെ ലിസ്റ്റ്
FONTS = {
    "1": {"name": "Roboto Black", "url": "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Black.ttf"},
    "2": {"name": "Montserrat Bold", "url": "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat-Bold.ttf"},
    "3": {"name": "Bebas Neue", "url": "https://github.com/google/fonts/raw/main/ofl/bebasneue/BebasNeue-Regular.ttf"},
    "4": {"name": "Anton", "url": "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf"},
    "5": {"name": "Oswald Bold", "url": "https://github.com/google/fonts/raw/main/ofl/oswald/Oswald-Bold.ttf"}
}

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
                "watermark": "",
                "play_icon": False,
                "vignette": False,
                "tint_color": "none",
                "font_choice": "0",
                "text_color": "white",
                "glow": True,
                "badge_text": "none",
                "inline_button": False,
                "target_channel": "none",
                "state": "idle" # പുതിയ State Machine സിസ്റ്റം
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

# പൂർണ്ണമായും അപ്ഡേറ്റ് ചെയ്ത പുതിയ പ്രൊഫഷണൽ എഡിറ്റിംഗ് സിസ്റ്റം (നിങ്ങളുടെ ഒറിജിനൽ)
def process_auto_blur(image_path, settings):
    try:
        img = Image.open(image_path).convert('RGBA')
        w, h = img.size
        
        # 1. ബ്ലർ എഫക്റ്റ് (Blur)
        img = img.filter(ImageFilter.GaussianBlur(radius=18))
        
        # 2. കളർ ടിന്റ് (Color Wash/Tint)
        tint = settings.get("tint_color", "none")
        if tint.lower() != "none":
            try:
                overlay = Image.new('RGBA', img.size, tint)
                overlay.putalpha(60) # Opacity
                img = Image.alpha_composite(img, overlay)
            except Exception as e: pass
                
        # 3. സിനിമാറ്റിക് വിഗ്നെറ്റ് (Dark Edges)
        if settings.get("vignette", False):
            try:
                mask = Image.new('L', img.size, 255)
                draw_mask = ImageDraw.Draw(mask)
                draw_mask.ellipse((w*0.1, h*0.1, w*0.9, h*0.9), fill=0)
                mask = mask.filter(ImageFilter.GaussianBlur(radius=int(min(w,h)/3)))
                dark_overlay = Image.new('RGBA', img.size, (0,0,0,200))
                img.paste(dark_overlay, mask=mask)
            except: pass
            
        draw = ImageDraw.Draw(img)
        
        # 4. പ്ലേ ബട്ടൺ ഐക്കൺ (Play Button)
        if settings.get("play_icon", False):
            try:
                r = min(w, h) // 8
                cx, cy = w // 2, h // 2
                circle_overlay = Image.new('RGBA', img.size, (0,0,0,0))
                c_draw = ImageDraw.Draw(circle_overlay)
                c_draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=(0,0,0,140))
                img = Image.alpha_composite(img, circle_overlay)
                draw = ImageDraw.Draw(img) 
                tr_pts = [(cx - r/3.5, cy - r/2.5), (cx + r/1.8, cy), (cx - r/3.5, cy + r/2.5)]
                draw.polygon(tr_pts, fill="white")
            except: pass

        # 5. വാട്ടർമാർക്ക്
        watermark_text = settings.get("watermark", "")
        if watermark_text:
            font_choice = settings.get("font_choice", "0")
            font = None
            try:
                font_size = int(w / 12)
                if font_choice in FONTS:
                    font_path = f"font_{font_choice}.ttf"
                    if not os.path.exists(font_path):
                        urllib.request.urlretrieve(FONTS[font_choice]["url"], font_path)
                    font = ImageFont.truetype(font_path, font_size)
                else: font = ImageFont.load_default(size=font_size)
            except: font = ImageFont.load_default()
            
            try:
                bbox = draw.textbbox((0, 0), watermark_text, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
            except: text_w, text_h = 150, 30
                
            x = (w - text_w) / 2
            y = (h / 2) + (min(w,h) // 8) + 20 if settings.get("play_icon", False) else (h - text_h) / 2
            text_color = settings.get("text_color", "white")
            
            if settings.get("glow", True):
                thickness = max(2, int(w/250))
                for dx in [-thickness, 0, thickness]:
                    for dy in [-thickness, 0, thickness]:
                        draw.text((x+dx, y+dy), watermark_text, font=font, fill="black")
                        
            try: draw.text((x, y), watermark_text, font=font, fill=text_color)
            except: draw.text((x, y), watermark_text, font=font, fill="white") 

        # 6. കോർണർ ബാഡ്ജ്
        badge = settings.get("badge_text", "none")
        if badge.lower() != "none":
            try:
                try: b_font = ImageFont.truetype("font_1.ttf", max(20, int(w/25))) 
                except: b_font = ImageFont.load_default()
                bbox = draw.textbbox((0, 0), badge, font=b_font)
                bw = bbox[2] - bbox[0]
                bh = bbox[3] - bbox[1]
                pad = int(w/50)
                bx1 = w - bw - (pad*3)
                by1 = pad
                draw.rounded_rectangle((bx1, by1, bx1+bw+(pad*2), by1+bh+(pad*2)), radius=pad, fill="#E50914") 
                draw.text((bx1+pad, by1+pad), badge, font=b_font, fill="white")
            except: pass

        processed_path = f"blurred_{os.path.basename(image_path)}"
        img = img.convert('RGB')
        img.save(processed_path, "JPEG")
        return processed_path
    except Exception as e:
        return image_path

# --- Web Server ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "TeraBox Super Speed Bot is Running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)


# ================= SMART INTERACTIVE MENUS (പുതിയത്) =================

async def send_blur_menu(client, message, edit=False):
    settings = get_settings(message.chat.id)
    text = "🌫 **ബ്ലർ സെറ്റിംഗ്സ് (Blur Settings)**\n\n👇 താഴെയുള്ള ബട്ടണുകൾ ഉപയോഗിച്ച് ON/OFF ചെയ്യാം:"
    
    btn_auto = "🟢 ഓട്ടോ ബ്ലർ (Auto Blur): ON" if settings.get("layout_mode") == "auto_blur" else "🔴 ഓട്ടോ ബ്ലർ (Auto Blur): OFF"
    btn_tg = "🟢 ടെലിഗ്രാം സ്പോയിലർ ബ്ലർ: ON" if settings.get("use_blur") else "🔴 ടെലിഗ്രാം സ്പോയിലർ ബ്ലർ: OFF"
    btn_magic = "🟢 മാജിക് മോഡ്: ON" if settings.get("layout_mode") == "magic" else "🔴 മാജിക് മോഡ്: OFF"
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_auto, callback_data="toggle_autoblur")],
        [InlineKeyboardButton(btn_magic, callback_data="toggle_magic")],
        [InlineKeyboardButton(btn_tg, callback_data="toggle_tgblur")]
    ])
    if edit: await message.edit_text(text, reply_markup=markup)
    else: await message.reply_text(text, reply_markup=markup)

async def send_photo_menu(client, message, edit=False):
    settings = get_settings(message.chat.id)
    status = "സെറ്റ് ചെയ്തിട്ടുണ്ട് ✅" if settings.get("custom_photo_id") else "ഇല്ല ❌"
    text = (
        "🖼 **കസ്റ്റം ഫോട്ടോ സെറ്റിംഗ്സ്**\n\n"
        "💡 **Smart Photo:** കസ്റ്റം ഫോട്ടോ ഒഴിവാക്കിയാൽ (Disable), നിങ്ങൾ ലിങ്കിനൊപ്പം അയക്കുന്ന പുതിയ ഫോട്ടോകൾ ബോട്ട് തനിയെ പോസ്റ്റ് ചെയ്യാൻ ഉപയോഗിക്കും.\n\n"
        f"📌 നിലവിലെ കസ്റ്റം ഫോട്ടോ: {status}"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 പുതിയ കസ്റ്റം ഫോട്ടോ അപ്‌ലോഡ് ചെയ്യുക", callback_data="ask_photo")],
        [InlineKeyboardButton("🗑️ കസ്റ്റം ഫോട്ടോ ഒഴിവാക്കുക", callback_data="disable_photo")]
    ])
    if edit: await message.edit_text(text, reply_markup=markup)
    else: await message.reply_text(text, reply_markup=markup)

async def send_design_menu(client, message, edit=False):
    settings = get_settings(message.chat.id)
    text = "🎨 **ഡിസൈൻ സെറ്റിംഗ്സ് (Design Settings)**\n\n👇 മാറ്റങ്ങൾ വരുത്താൻ താഴെ അമർത്തുക:"
    b_play = "🟢 Play Icon: ON" if settings.get("play_icon") else "🔴 Play Icon: OFF"
    b_vig = "🟢 Vignette: ON" if settings.get("vignette") else "🔴 Vignette: OFF"
    b_glow = "🟢 Glow: ON" if settings.get("glow") else "🔴 Glow: OFF"
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(b_play, callback_data="toggle_play")],
        [InlineKeyboardButton(b_vig, callback_data="toggle_vig")],
        [InlineKeyboardButton(b_glow, callback_data="toggle_glow")]
    ])
    if edit: await message.edit_text(text, reply_markup=markup)
    else: await message.reply_text(text, reply_markup=markup)

async def send_target_menu(client, message, edit=False):
    settings = get_settings(message.chat.id)
    target = settings.get("target_channel", "none")
    text = f"📢 **ചാനൽ പോസ്റ്റിംഗ് (Auto Post)**\n\n📌 നിലവിലെ ചാനൽ: `{target}`\n\n👇 എന്താണ് ചെയ്യേണ്ടത്?"
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 പുതിയ ചാനൽ സെറ്റ് ചെയ്യുക", callback_data="ask_target")],
        [InlineKeyboardButton("🛑 ചാനലിലേക്ക് അയക്കുന്നത് നിർത്തുക", callback_data="disable_target")]
    ])
    if edit: await message.edit_text(text, reply_markup=markup)
    else: await message.reply_text(text, reply_markup=markup)

async def send_button_menu(client, message, edit=False):
    settings = get_settings(message.chat.id)
    text = "🔘 **ഇൻലൈൻ ബട്ടൺ & വാട്ടർമാർക്ക്**\n\n👇 താഴെയുള്ള ബട്ടണുകൾ ഉപയോഗിക്കുക:"
    b_inline = "🟢 Inline Buttons: ON" if settings.get("inline_button") else "🔴 Inline Buttons: OFF"
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(b_inline, callback_data="toggle_inline")],
        [InlineKeyboardButton("🖋️ വാട്ടർമാർക്ക് സെറ്റ് ചെയ്യുക", callback_data="ask_watermark")],
        [InlineKeyboardButton("🗑️ വാട്ടർമാർക്ക് ഒഴിവാക്കുക", callback_data="disable_watermark")]
    ])
    if edit: await message.edit_text(text, reply_markup=markup)
    else: await message.reply_text(text, reply_markup=markup)


# ================= COMMANDS =================
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    update_settings(message.chat.id, "state", "idle")
    await message.reply_text("✨ **TeraBox Smart UI Bot-ലേക്ക് സ്വാഗതം!**\n\nഇനി മെനുവിലുള്ള പുതിയ കമാൻഡുകൾ ഉപയോഗിച്ച് ബട്ടണുകൾ വഴി എല്ലാം സെറ്റ് ചെയ്യാം.")

@app.on_message(filters.command("blur_menu") & filters.private)
async def cmd_blur(client, message): await send_blur_menu(client, message)

@app.on_message(filters.command("photo_menu") & filters.private)
async def cmd_photo(client, message): await send_photo_menu(client, message)

@app.on_message(filters.command("design_menu") & filters.private)
async def cmd_design(client, message): await send_design_menu(client, message)

@app.on_message(filters.command("target_menu") & filters.private)
async def cmd_target(client, message): await send_target_menu(client, message)

@app.on_message(filters.command("button_menu") & filters.private)
async def cmd_button(client, message): await send_button_menu(client, message)

@app.on_message(filters.command("status") & filters.private)
async def cmd_status(client, message):
    settings = get_settings(message.chat.id)
    await message.reply_text(f"📊 **Bot Status:**\n\n📌 Target Channel: `{settings.get('target_channel')}`\n✨ Layout Mode: `{settings.get('layout_mode')}`")

# പഴയ ചില കസ്റ്റം കമാൻഡുകൾ (സേഫ്റ്റിക്ക് വേണ്ടി നിലനിർത്തിയിരിക്കുന്നു, പക്ഷേ മെനുവിൽ ആവശ്യമില്ല)
@app.on_message(filters.command("set_fake_photo") & filters.private)
async def set_fake_photo(client, message):
    if message.photo: file_id = message.photo.file_id
    elif message.document: file_id = message.document.file_id
    else: return await message.reply_text("❌ Please send a fake photo.")
    update_settings(message.chat.id, "fake_photo_id", file_id)
    if file_id in FILE_CACHE: del FILE_CACHE[file_id]
    await message.reply_text("✅ Fake photo (Thumbnail) saved!")

@app.on_message(filters.command("set_link_text") & filters.private)
async def set_link_text(client, message):
    text = message.text.replace("/set_link_text", "").strip()
    if text:
        update_settings(message.chat.id, "link_text", text + " ")
        await message.reply_text(f"✅ Link text set to: {text} 1")

@app.on_message(filters.command("font_list") & filters.private)
async def font_list(client, message):
    msg = "📜 **ലഭ്യമായ സിനിമാറ്റിക് ഫോണ്ടുകൾ:**\n\n"
    for key, val in FONTS.items(): msg += f"{key}. {val['name']}\n"
    await message.reply_text(msg)

@app.on_message(filters.command("set_font") & filters.private)
async def set_font(client, message):
    text = message.text.replace("/set_font", "").strip()
    update_settings(message.chat.id, "font_choice", text)
    await message.reply_text(f"🖋️ ഫോണ്ട് സ്റ്റൈൽ {text} ലേക്ക് മാറ്റിയിരിക്കുന്നു!")


# ================= CALLBACK HANDLER (ബട്ടൺ ക്ലിക്ക് ചെയ്യുമ്പോൾ) =================
@app.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.message.chat.id
    settings = get_settings(user_id)
    
    # Toggle Handlers
    if data == "toggle_autoblur":
        new_mode = "magic" if settings.get("layout_mode") == "auto_blur" else "auto_blur"
        update_settings(user_id, "layout_mode", new_mode)
        await send_blur_menu(client, query.message, edit=True)
        
    elif data == "toggle_magic":
        new_mode = "auto_blur" if settings.get("layout_mode") == "magic" else "magic"
        update_settings(user_id, "layout_mode", new_mode)
        await send_blur_menu(client, query.message, edit=True)
        
    elif data == "toggle_tgblur":
        update_settings(user_id, "use_blur", not settings.get("use_blur"))
        await send_blur_menu(client, query.message, edit=True)
        
    elif data == "toggle_play":
        update_settings(user_id, "play_icon", not settings.get("play_icon"))
        await send_design_menu(client, query.message, edit=True)
        
    elif data == "toggle_vig":
        update_settings(user_id, "vignette", not settings.get("vignette"))
        await send_design_menu(client, query.message, edit=True)
        
    elif data == "toggle_glow":
        update_settings(user_id, "glow", not settings.get("glow"))
        await send_design_menu(client, query.message, edit=True)
        
    elif data == "toggle_inline":
        update_settings(user_id, "inline_button", not settings.get("inline_button"))
        await send_button_menu(client, query.message, edit=True)
        
    # Ask Handlers (State Machine)
    elif data == "ask_photo":
        update_settings(user_id, "state", "wait_photo")
        await query.message.reply_text("📸 **പുതിയ കസ്റ്റം ഫോട്ടോ അപ്‌ലോഡ് ചെയ്യുക**\n\nനിങ്ങളുടെ ഗാലറിയിൽ നിന്നും ഫോട്ടോ സെലക്ട് ചെയ്ത് നേരിട്ട് ഇങ്ങോട്ട് അയക്കുക.")
        
    elif data == "disable_photo":
        update_settings(user_id, "custom_photo_id", None)
        await query.answer("✅ കസ്റ്റം ഫോട്ടോ ഒഴിവാക്കി! ഇനി ലിങ്കിനൊപ്പം അയക്കുന്ന ഫോട്ടോ ബോട്ട് എടുക്കുന്നതാണ്.", show_alert=True)
        await send_photo_menu(client, query.message, edit=True)
        
    elif data == "ask_target":
        update_settings(user_id, "state", "wait_target")
        await query.message.reply_text("📢 **ടാർഗെറ്റ് ചാനൽ അയക്കുക**\n\nചാനലിന്റെ യൂസർനെയിം (ഉദാ: @mychannel) ഇങ്ങോട്ട് ടൈപ്പ് ചെയ്ത് അയക്കുക.")
        
    elif data == "disable_target":
        update_settings(user_id, "target_channel", "none")
        await query.answer("✅ ഓട്ടോ പോസ്റ്റിംഗ് ഓഫ് ചെയ്തു! ഇനി ഇൻബോക്സിൽ വരും.", show_alert=True)
        await send_target_menu(client, query.message, edit=True)
        
    elif data == "ask_watermark":
        update_settings(user_id, "state", "wait_watermark")
        await query.message.reply_text("🖋️ **വാട്ടർമാർക്ക് ടൈപ്പ് ചെയ്യുക**\n\nനിങ്ങളുടെ പേരോ ചാനലിന്റെ പേരോ ഇങ്ങോട്ട് ടൈപ്പ് ചെയ്ത് അയക്കുക.")
        
    elif data == "disable_watermark":
        update_settings(user_id, "watermark", "")
        await query.answer("✅ വാട്ടർമാർക്ക് ഒഴിവാക്കി!", show_alert=True)
        await send_button_menu(client, query.message, edit=True)


# ================= MAIN LINK & STATE HANDLER =================
@app.on_message((filters.text | filters.photo | filters.video | filters.animation | filters.document) & filters.private & ~filters.command(["start", "blur_menu", "photo_menu", "design_menu", "target_menu", "button_menu", "status"]))
async def handle_link(client, message):
    user_text = message.text or message.caption or ""
    settings = get_settings(message.chat.id)
    if not settings: return
    
    state = settings.get("state", "idle")
    
    # 1. State Machine Handling (ബോട്ട് ചോദിച്ചതിനുള്ള മറുപടി)
    if state == "wait_photo":
        if message.photo or (message.document and message.document.mime_type and message.document.mime_type.startswith('image/')):
            file_id = message.photo.file_id if message.photo else message.document.file_id
            update_settings(message.chat.id, "custom_photo_id", file_id)
            update_settings(message.chat.id, "state", "idle")
            await message.reply_text("✅ സക്സസ്ഫുൾ! പുതിയ കസ്റ്റം ഫോട്ടോ സേവ് ചെയ്തു.")
        else: await message.reply_text("❌ ദയവായി ഒരു ഫോട്ടോ അയക്കുക.")
        return
        
    elif state == "wait_target" and message.text:
        update_settings(message.chat.id, "target_channel", message.text.strip())
        update_settings(message.chat.id, "state", "idle")
        await message.reply_text(f"✅ സക്സസ്ഫുൾ! ടാർഗെറ്റ് ചാനൽ സെറ്റ് ചെയ്തു: {message.text.strip()}")
        return
        
    elif state == "wait_watermark" and message.text:
        update_settings(message.chat.id, "watermark", message.text.strip())
        update_settings(message.chat.id, "state", "idle")
        await message.reply_text(f"✅ സക്സസ്ഫുൾ! വാട്ടർമാർക്ക് സെറ്റ് ചെയ്തു: {message.text.strip()}")
        return

    # 2. Link Processing (നിങ്ങളുടെ പഴയ കോഡ് തന്നെ, Smart Photo ഫീച്ചർ മാത്രം ചേർത്തു)
    if not user_text: return
    
    urls = re.findall(r"(https?://\S*(?:terabox|terashare)\S*)", user_text, re.IGNORECASE)
    
    if urls:
        target = settings.get("target_channel", "none")
        if target.lower() != "none":
            try: target_chat = int(target)
            except ValueError: target_chat = target
        else:
            target_chat = message.chat.id

        wait_msg = await message.reply_text("Designing your post... 🎨")
        
        unique_urls = list(dict.fromkeys(urls))
        reply_markup = None
        formatted_links = ""
        link_prefix = settings.get('link_text', '🍓Video ')
        
        if settings.get("inline_button", False):
            button_list = []
            for index, url in enumerate(unique_urls, start=1):
                button_list.append([InlineKeyboardButton(f"{link_prefix.strip()} {index}", url=url)])
            reply_markup = InlineKeyboardMarkup(button_list)
        else:
            for index, url in enumerate(unique_urls, start=1):
                formatted_links += f"{link_prefix}{index}\n{url}\n\n\n"
            formatted_links = formatted_links.strip()
        
        final_caption = f"{settings.get('header', '')}{formatted_links}{settings.get('channel', '')}{settings.get('footer', '')}"
        
        global post_lock
        if post_lock is None: post_lock = asyncio.Lock()
            
        try:
            # === SMART PHOTO SELECTION ===
            incoming_media = None
            if message.photo: incoming_media = message.photo.file_id
            elif message.video and message.video.thumbs: incoming_media = message.video.thumbs[0].file_id
            elif message.animation and message.animation.thumbs: incoming_media = message.animation.thumbs[0].file_id
            elif message.document and message.document.mime_type and message.document.mime_type.startswith('image/'): incoming_media = message.document.file_id
            
            # Auto Blur Mode
            if settings.get("layout_mode") == "auto_blur":
                if incoming_media:
                    temp_path = await client.download_media(incoming_media)
                    if temp_path:
                        blurred_path = process_auto_blur(temp_path, settings)
                        async with post_lock:
                            await client.send_photo(chat_id=target_chat, photo=blurred_path, caption=final_caption, reply_markup=reply_markup)
                            await asyncio.sleep(3.5)
                        if os.path.exists(temp_path): os.remove(temp_path)
                        if os.path.exists(blurred_path): os.remove(blurred_path)
                    if target_chat != message.chat.id: await wait_msg.edit_text(f"✅ പോസ്റ്റ് {target_chat}-ലേക്ക് വിജയകരമായി അയച്ചു!")
                    else: await wait_msg.delete()
                    return 
                else:
                    await wait_msg.edit_text("❌ ഈ ലിങ്കിനൊപ്പം കവർ ഫോട്ടോ ഇല്ലാത്തതിനാൽ ഓട്ടോ-ബ്ലർ ചെയ്യാൻ കഴിയില്ല.")
                    return
            
            # Magic Mode (Smart Photo ഉപയോഗിച്ച്)
            custom_photo = incoming_media if incoming_media else settings.get("custom_photo_id")
            fake_photo = settings.get("fake_photo_id")
            
            if custom_photo and settings.get("enable_picture", True):
                doc_path = f"{custom_photo}.jpg"
                if custom_photo not in FILE_CACHE or not os.path.exists(doc_path):
                    actual_path = await client.download_media(custom_photo)
                    if actual_path and os.path.exists(actual_path): os.rename(actual_path, doc_path)
                    FILE_CACHE[custom_photo] = doc_path
                
                custom_file_name = settings.get("file_name", "🔞_Click_To_Open_🍓")
                
                if settings.get("layout_mode") == "magic":
                    thumb_path = None
                    if fake_photo:
                        thumb_path = f"{fake_photo}.jpg"
                        if fake_photo not in FILE_CACHE or not os.path.exists(thumb_path):
                            actual_thumb = await client.download_media(fake_photo)
                            if actual_thumb and os.path.exists(actual_thumb): os.rename(actual_thumb, thumb_path)
                            resize_thumbnail(thumb_path)
                            FILE_CACHE[fake_photo] = thumb_path
                            
                    async with post_lock:
                        if settings.get("use_blur", True) and thumb_path:
                            try: await client.send_document(chat_id=target_chat, document=doc_path, thumbnail=thumb_path, file_name=custom_file_name, caption=final_caption, reply_markup=reply_markup)
                            except TypeError: await client.send_document(chat_id=target_chat, document=doc_path, thumb=thumb_path, file_name=custom_file_name, caption=final_caption, reply_markup=reply_markup)
                        else:
                            await client.send_document(chat_id=target_chat, document=doc_path, file_name=custom_file_name, caption=final_caption, reply_markup=reply_markup)
                        await asyncio.sleep(3.5)
                else:
                    async with post_lock:
                        await client.send_photo(chat_id=target_chat, photo=doc_path, caption=final_caption, has_spoiler=settings.get("use_blur", True), reply_markup=reply_markup)
                        await asyncio.sleep(3.5)
                
                if target_chat != message.chat.id: await wait_msg.edit_text(f"✅ പോസ്റ്റ് {target_chat}-ലേക്ക് വിജയകരമായി അയച്ചു!")
                else: await wait_msg.delete()
            else:
                async with post_lock:
                    if target_chat != message.chat.id:
                        if reply_markup: await client.send_message(chat_id=target_chat, text=final_caption, reply_markup=reply_markup)
                        else: await client.send_message(chat_id=target_chat, text=final_caption)
                        await asyncio.sleep(3.5)
                        await wait_msg.edit_text(f"✅ പോസ്റ്റ് {target_chat}-ലേക്ക് വിജയകരമായി അയച്ചു!")
                    else:
                        if reply_markup: await wait_msg.edit_text(final_caption, reply_markup=reply_markup)
                        else: await wait_msg.edit_text(final_caption)
                        await asyncio.sleep(1)
                
        except Exception as e:
            logging.error(f"Send Error: {e}")
            await wait_msg.edit_text(f"❌ System Error: {str(e)}")
            
    elif not user_text.startswith("/"):
        await message.reply_text("Please forward Terabox links.")

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    print("Super Speed Bot is running smoothly...")
    app.run()

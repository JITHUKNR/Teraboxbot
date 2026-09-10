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
post_lock = None # 50 posts at once anti-flood lock

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
                "state": "idle" # NEW: State machine for bot interactions
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

def process_auto_blur(image_path, settings):
    try:
        img = Image.open(image_path).convert('RGBA')
        w, h = img.size
        
        img = img.filter(ImageFilter.GaussianBlur(radius=18))
        
        tint = settings.get("tint_color", "none")
        if tint.lower() != "none":
            try:
                overlay = Image.new('RGBA', img.size, tint)
                overlay.putalpha(60) 
                img = Image.alpha_composite(img, overlay)
            except Exception as e:
                logging.error(f"Tint error: {e}")
                
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
                else:
                    font = ImageFont.load_default(size=font_size)
            except:
                try: font = ImageFont.load_default(size=int(w/12))
                except: font = ImageFont.load_default()
            
            try:
                bbox = draw.textbbox((0, 0), watermark_text, font=font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
            except:
                try: text_w, text_h = draw.textlength(watermark_text, font=font), 30
                except: text_w, text_h = 150, 30
                
            x = (w - text_w) / 2
            if settings.get("play_icon", False):
                y = (h / 2) + (min(w,h) // 8) + 20 
            else:
                y = (h - text_h) / 2
                
            text_color = settings.get("text_color", "white")
            
            if settings.get("glow", True):
                thickness = max(2, int(w/250))
                for dx in [-thickness, 0, thickness]:
                    for dy in [-thickness, 0, thickness]:
                        draw.text((x+dx, y+dy), watermark_text, font=font, fill="black")
                        
            try: draw.text((x, y), watermark_text, font=font, fill=text_color)
            except: draw.text((x, y), watermark_text, font=font, fill="white") 

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

# ================= NEW SMART INTERACTIVE MENUS =================

async def send_blur_menu(client, message, edit=False):
    settings = get_settings(message.chat.id)
    text = "🌫 **Blur Settings**\n\n👇 Click the buttons below to toggle ON/OFF:"
    
    btn_auto = "🟢 Auto Blur: ON" if settings.get("layout_mode") == "auto_blur" else "🔴 Auto Blur: OFF"
    btn_tg = "🟢 Telegram Spoiler Blur: ON" if settings.get("use_blur") else "🔴 Telegram Spoiler Blur: OFF"
    btn_magic = "🟢 Magic Mode: ON" if settings.get("layout_mode") == "magic" else "🔴 Magic Mode: OFF"
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_auto, callback_data="toggle_autoblur")],
        [InlineKeyboardButton(btn_magic, callback_data="toggle_magic")],
        [InlineKeyboardButton(btn_tg, callback_data="toggle_tgblur")]
    ])
    if edit: await message.edit_text(text, reply_markup=markup)
    else: await message.reply_text(text, reply_markup=markup)

async def send_photo_menu(client, message, edit=False):
    settings = get_settings(message.chat.id)
    status = "Set ✅" if settings.get("custom_photo_id") else "None ❌"
    text = (
        "🖼 **Custom Photo Settings**\n\n"
        "💡 **Smart Photo:** If Custom Photo is disabled, the bot will automatically use the photo attached to your link.\n\n"
        f"📌 Current Custom Photo: {status}"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 Upload New Custom Photo", callback_data="ask_photo")],
        [InlineKeyboardButton("🗑️ Disable Custom Photo", callback_data="disable_photo")]
    ])
    if edit: await message.edit_text(text, reply_markup=markup)
    else: await message.reply_text(text, reply_markup=markup)

async def send_design_menu(client, message, edit=False):
    settings = get_settings(message.chat.id)
    text = "🎨 **Design Settings**\n\n👇 Click below to modify your layout:"
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
    text = f"📢 **Channel Auto Post Settings**\n\n📌 Current Target: `{target}`\n\n👇 What would you like to do?"
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Set Target Channel", callback_data="ask_target")],
        [InlineKeyboardButton("🛑 Disable Auto Post", callback_data="disable_target")]
    ])
    if edit: await message.edit_text(text, reply_markup=markup)
    else: await message.reply_text(text, reply_markup=markup)

async def send_button_menu(client, message, edit=False):
    settings = get_settings(message.chat.id)
    text = "🔘 **Inline Button & Watermark**\n\n👇 Select an option below:"
    b_inline = "🟢 Inline Buttons: ON" if settings.get("inline_button") else "🔴 Inline Buttons: OFF"
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(b_inline, callback_data="toggle_inline")],
        [InlineKeyboardButton("🖋️ Set Watermark", callback_data="ask_watermark")],
        [InlineKeyboardButton("🗑️ Disable Watermark", callback_data="disable_watermark")]
    ])
    if edit: await message.edit_text(text, reply_markup=markup)
    else: await message.reply_text(text, reply_markup=markup)

async def send_text_menu(client, message, edit=False):
    settings = get_settings(message.chat.id)
    h_status = "Set ✅" if settings.get("header") else "None ❌"
    f_status = "Set ✅" if settings.get("footer") else "None ❌"
    
    text = (
        "📝 **Caption Text Settings**\n\n"
        f"📌 **Header (Top):** {h_status}\n"
        f"📌 **Footer (Bottom):** {f_status}\n\n"
        "👇 Choose what you want to add/change:"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Set Header Text", callback_data="ask_header")],
        [InlineKeyboardButton("📝 Set Footer Text", callback_data="ask_footer")],
        [InlineKeyboardButton("🗑️ Clear All Texts", callback_data="clear_texts")]
    ])
    if edit: await message.edit_text(text, reply_markup=markup)
    else: await message.reply_text(text, reply_markup=markup)


# ================= ORIGINAL COMMANDS (Kept 100% Intact) =================
@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    update_settings(message.chat.id, "state", "idle")
    await message.reply_text("Welcome to TeraBox Dual Mode Bot! ✨\n\nYou can now use the new menu commands (/blur_menu, /photo_menu, etc.) for smart controls, or use old commands like /mode_large, /mode_magic, or /mode_auto_blur.")

# NEW MENU COMMANDS
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

@app.on_message(filters.command("text_menu") & filters.private)
async def cmd_text(client, message): await send_text_menu(client, message)

@app.on_message(filters.command("status") & filters.private)
async def cmd_status(client, message):
    settings = get_settings(message.chat.id)
    await message.reply_text(f"📊 **Bot Status:**\n\n📌 Target Channel: `{settings.get('target_channel')}`\n✨ Layout Mode: `{settings.get('layout_mode')}`")

# YOUR OLD COMMANDS START HERE
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
    await message.reply_text("🌫 **Auto Blur Mode Enabled!**")

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

@app.on_message(filters.command("enable_play_icon") & filters.private)
async def enable_play_icon(client, message):
    update_settings(message.chat.id, "play_icon", True)
    await message.reply_text("▶️ **Play Icon Enabled!**")

@app.on_message(filters.command("disable_play_icon") & filters.private)
async def disable_play_icon(client, message):
    update_settings(message.chat.id, "play_icon", False)
    await message.reply_text("❌ **Play Icon Disabled.**")

@app.on_message(filters.command("enable_vignette") & filters.private)
async def enable_vignette(client, message):
    update_settings(message.chat.id, "vignette", True)
    await message.reply_text("🌑 **Cinematic Vignette Enabled!**")

@app.on_message(filters.command("disable_vignette") & filters.private)
async def disable_vignette(client, message):
    update_settings(message.chat.id, "vignette", False)
    await message.reply_text("❌ **Vignette Disabled.**")

@app.on_message(filters.command("enable_glow") & filters.private)
async def enable_glow(client, message):
    update_settings(message.chat.id, "glow", True)
    await message.reply_text("✨ **Text Glow/Outline Enabled!**")

@app.on_message(filters.command("disable_glow") & filters.private)
async def disable_glow(client, message):
    update_settings(message.chat.id, "glow", False)
    await message.reply_text("❌ **Text Glow Disabled.**")

@app.on_message(filters.command("set_color") & filters.private)
async def set_color(client, message):
    text = message.text.replace("/set_color", "").strip()
    if text:
        update_settings(message.chat.id, "text_color", text)
        await message.reply_text(f"🎨 Text color set to: {text}")
    else:
        await message.reply_text("❌ Example: /set_color red or /set_color #FFD700")

@app.on_message(filters.command("set_tint") & filters.private)
async def set_tint(client, message):
    text = message.text.replace("/set_tint", "").strip()
    if text:
        update_settings(message.chat.id, "tint_color", text)
        await message.reply_text(f"🌈 Tint color set to: {text}")
    else:
        await message.reply_text("❌ Example: /set_tint blue")

@app.on_message(filters.command("set_badge") & filters.private)
async def set_badge(client, message):
    text = message.text.replace("/set_badge", "").strip()
    if text:
        update_settings(message.chat.id, "badge_text", text)
        await message.reply_text(f"🏷️ Corner badge set to: {text}")
    else:
        await message.reply_text("❌ Example: /set_badge 18+ or /set_badge HD")

@app.on_message(filters.command("font_list") & filters.private)
async def font_list(client, message):
    msg = "📜 **Available Cinematic Fonts:**\n\n"
    for key, val in FONTS.items():
        msg += f"{key}. {val['name']}\n"
    msg += "\nType the number of the font you want.\nExample: `/set_font 1`"
    await message.reply_text(msg)

@app.on_message(filters.command("set_font") & filters.private)
async def set_font(client, message):
    text = message.text.replace("/set_font", "").strip()
    if text:
        update_settings(message.chat.id, "font_choice", text)
        await message.reply_text(f"🖋️ Font style changed to {text}!")
    else:
        await message.reply_text("❌ Example: /set_font 1")

@app.on_message(filters.command("enable_button") & filters.private)
async def enable_button(client, message):
    update_settings(message.chat.id, "inline_button", True)
    await message.reply_text("🔘 **Inline Buttons Enabled!**")

@app.on_message(filters.command("disable_button") & filters.private)
async def disable_button(client, message):
    update_settings(message.chat.id, "inline_button", False)
    await message.reply_text("❌ **Inline Buttons Disabled.**")

@app.on_message(filters.command("set_target") & filters.private)
async def set_target(client, message):
    text = message.text.replace("/set_target", "").strip()
    if text:
        update_settings(message.chat.id, "target_channel", text)
        if text.lower() == "none":
            await message.reply_text("✅ Auto Posting disabled. Posts will go to your inbox.")
        else:
            await message.reply_text(f"✅ Target channel set to: {text}\n(Make sure the bot is an Admin in the channel!)")
    else:
        await message.reply_text("❌ Example: /set_target @mychannel or /set_target -100123456789")


# ================= CALLBACK HANDLER (For Buttons) =================
@app.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.message.chat.id
    settings = get_settings(user_id)
    
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
        
    elif data == "ask_photo":
        update_settings(user_id, "state", "wait_photo")
        await query.message.reply_text("📸 **Upload New Custom Photo**\n\nPlease send the photo directly here.")
        
    elif data == "disable_photo":
        update_settings(user_id, "custom_photo_id", None)
        await query.answer("✅ Custom photo disabled! The bot will now use the smart photo attached to your link.", show_alert=True)
        await send_photo_menu(client, query.message, edit=True)
        
    elif data == "ask_target":
        update_settings(user_id, "state", "wait_target")
        await query.message.reply_text("📢 **Set Target Channel**\n\nPlease type the channel username or ID here.")
        
    elif data == "disable_target":
        update_settings(user_id, "target_channel", "none")
        await query.answer("✅ Auto Posting disabled! Posts will now be sent to your inbox.", show_alert=True)
        await send_target_menu(client, query.message, edit=True)
        
    elif data == "ask_watermark":
        update_settings(user_id, "state", "wait_watermark")
        await query.message.reply_text("🖋️ **Type your Watermark**\n\nPlease type your watermark text here.")
        
    elif data == "disable_watermark":
        update_settings(user_id, "watermark", "")
        await query.answer("✅ Watermark disabled!", show_alert=True)
        await send_button_menu(client, query.message, edit=True)

    elif data == "ask_header":
        update_settings(user_id, "state", "wait_header")
        await query.message.reply_text("📝 **Type your Header Text**\n\n(This text will appear at the top of the post)")
        
    elif data == "ask_footer":
        update_settings(user_id, "state", "wait_footer")
        await query.message.reply_text("📝 **Type your Footer Text**\n\n(This text will appear at the bottom of the post)")
        
    elif data == "clear_texts":
        update_settings(user_id, "header", "")
        update_settings(user_id, "footer", "")
        await query.answer("✅ Header & Footer Texts Cleared!", show_alert=True)
        await send_text_menu(client, query.message, edit=True)

# ================= MAIN LINK & STATE HANDLER =================
# Excluded the new menu commands from being processed as links
@app.on_message((filters.text | filters.photo | filters.video | filters.animation | filters.document) & filters.private & ~filters.command(["blur_menu", "photo_menu", "design_menu", "target_menu", "button_menu", "text_menu", "status"]))
async def handle_link(client, message):
    user_text = message.text or message.caption or ""
    
    settings = get_settings(message.chat.id)
    if not settings: return await message.reply_text("❌ Database Error.")
    
    state = settings.get("state", "idle")
    
    # --- State Machine Inputs (If the bot asked you a question) ---
    if state == "wait_photo":
        if message.photo or (message.document and message.document.mime_type and message.document.mime_type.startswith('image/')):
            file_id = message.photo.file_id if message.photo else message.document.file_id
            update_settings(message.chat.id, "custom_photo_id", file_id)
            update_settings(message.chat.id, "state", "idle")
            await message.reply_text("✅ Success! New custom photo saved.")
        else: await message.reply_text("❌ Please send a valid photo.")
        return
        
    elif state == "wait_target" and message.text:
        update_settings(message.chat.id, "target_channel", message.text.strip())
        update_settings(message.chat.id, "state", "idle")
        await message.reply_text(f"✅ Success! Target channel set to: {message.text.strip()}")
        return
        
    elif state == "wait_watermark" and message.text:
        update_settings(message.chat.id, "watermark", message.text.strip())
        update_settings(message.chat.id, "state", "idle")
        await message.reply_text(f"✅ Success! Watermark set to: {message.text.strip()}")
        return
        
    elif state == "wait_header" and message.text:
        update_settings(message.chat.id, "header", message.text.strip() + "\n\n")
        update_settings(message.chat.id, "state", "idle")
        await message.reply_text("✅ Success! Header text saved.")
        return
        
    elif state == "wait_footer" and message.text:
        update_settings(message.chat.id, "footer", "\n\n" + message.text.strip())
        update_settings(message.chat.id, "state", "idle")
        await message.reply_text("✅ Success! Footer text saved.")
        return
    # -----------------------------------------------------------------

    if not user_text: return
    
    urls = re.findall(r"(https?://\S*(?:terabox|terashare)\S*)", user_text, re.IGNORECASE)
    
    if urls:
        # ടാർഗെറ്റ് ചാനൽ കണ്ടെത്തുന്നു
        target = settings.get("target_channel", "none")
        if target.lower() != "none":
            try:
                target_chat = int(target)
            except ValueError:
                target_chat = target
        else:
            target_chat = message.chat.id

        wait_msg = await message.reply_text("Designing your post... 🎨")
        
        unique_urls = list(dict.fromkeys(urls))
        reply_markup = None
        formatted_links = ""
        link_prefix = settings.get('link_text', '🍓Video ')
        
        # പുതിയ ഇൻലൈൻ ബട്ടൺ സിസ്റ്റം
        if settings.get("inline_button", False):
            button_list = []
            for index, url in enumerate(unique_urls, start=1):
                # ബട്ടണിനുള്ളിൽ നിങ്ങളുടെ കസ്റ്റം പേര് (ഉദാഹരണത്തിന് VIDEO🥵 1) വരുന്ന രീതി
                button_list.append([InlineKeyboardButton(f"{link_prefix.strip()} {index}", url=url)])
            reply_markup = InlineKeyboardMarkup(button_list)
        else:
            for index, url in enumerate(unique_urls, start=1):
                formatted_links += f"{link_prefix}{index}\n{url}\n\n\n"
            formatted_links = formatted_links.strip()
        
        final_caption = f"{settings.get('header', '')}{formatted_links}{settings.get('channel', '')}{settings.get('footer', '')}"
        
        # 50 പോസ്റ്റുകൾ വന്നാലും സേഫ് ആയിരിക്കാൻ ലോക്ക് സെറ്റ് ചെയ്യുന്നു
        global post_lock
        if post_lock is None:
            post_lock = asyncio.Lock()
            
        try:
            # === SMART PHOTO UPGRADE (Extracts photo sent with link) ===
            incoming_media = None
            if message.photo: 
                incoming_media = message.photo.file_id
            elif message.video and message.video.thumbs:
                incoming_media = message.video.thumbs[0].file_id
            elif message.animation and message.animation.thumbs:
                incoming_media = message.animation.thumbs[0].file_id
            elif message.document and message.document.mime_type and message.document.mime_type.startswith('image/'):
                incoming_media = message.document.file_id
            # ==========================================================

            if settings.get("layout_mode") == "auto_blur":
                if incoming_media:
                    temp_path = await client.download_media(incoming_media)
                    if temp_path:
                        blurred_path = process_auto_blur(temp_path, settings)
                        
                        # ലോക്ക് ഉപയോഗിച്ച് സുരക്ഷിതമായി പോസ്റ്റ് ചെയ്യുന്നു
                        async with post_lock:
                            await client.send_photo(chat_id=target_chat, photo=blurred_path, caption=final_caption, reply_markup=reply_markup)
                            await asyncio.sleep(3.5) # 3.5 സെക്കൻഡ് ഇടവേള (Anti-Flood)
                        
                        if os.path.exists(temp_path): os.remove(temp_path)
                        if os.path.exists(blurred_path): os.remove(blurred_path)
                        
                    if target_chat != message.chat.id:
                        await wait_msg.edit_text(f"✅ Post successfully sent to {target_chat}!")
                    else:
                        await wait_msg.delete()
                    return 
                else:
                    await wait_msg.edit_text("❌ Cannot auto-blur because no cover photo was found with this link.")
                    return
            
            # SMART PHOTO LOGIC applied here
            custom_photo = incoming_media if incoming_media else settings.get("custom_photo_id")
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
                            
                    async with post_lock:
                        if settings.get("use_blur", True) and thumb_path:
                            try:
                                await client.send_document(chat_id=target_chat, document=doc_path, thumbnail=thumb_path, file_name=custom_file_name, caption=final_caption, reply_markup=reply_markup)
                            except TypeError:
                                await client.send_document(chat_id=target_chat, document=doc_path, thumb=thumb_path, file_name=custom_file_name, caption=final_caption, reply_markup=reply_markup)
                        else:
                            await client.send_document(chat_id=target_chat, document=doc_path, file_name=custom_file_name, caption=final_caption, reply_markup=reply_markup)
                        await asyncio.sleep(3.5) # 3.5 സെക്കൻഡ് ഇടവേള
                else:
                    async with post_lock:
                        await client.send_photo(chat_id=target_chat, photo=doc_path, caption=final_caption, has_spoiler=settings.get("use_blur", True), reply_markup=reply_markup)
                        await asyncio.sleep(3.5) # 3.5 സെക്കൻഡ് ഇടവേള
                
                if target_chat != message.chat.id:
                    await wait_msg.edit_text(f"✅ Post successfully sent to {target_chat}!")
                else:
                    await wait_msg.delete()
            else:
                async with post_lock:
                    if target_chat != message.chat.id:
                        if reply_markup:
                            await client.send_message(chat_id=target_chat, text=final_caption, reply_markup=reply_markup)
                        else:
                            await client.send_message(chat_id=target_chat, text=final_caption)
                        await asyncio.sleep(3.5)
                        await wait_msg.edit_text(f"✅ Post successfully sent to {target_chat}!")
                    else:
                        if reply_markup:
                            await wait_msg.edit_text(final_caption, reply_markup=reply_markup)
                        else:
                            await wait_msg.edit_text(final_caption)
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

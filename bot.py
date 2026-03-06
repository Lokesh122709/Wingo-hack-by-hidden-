#!/usr/bin/env python3
"""
ULTIMATE RIZEN X AI – DUAL SERVER EDITION (FIXED)
Now only the active server generates predictions.
No more duplicate messages.
"""

import sys
import subprocess
import importlib

# ========== AUTO‑INSTALL MISSING PACKAGES ==========
def install_and_import(package, import_name=None, version=None):
    import_name = import_name or package
    try:
        return importlib.import_module(import_name)
    except ImportError:
        print(f"📦 Installing {package}{'=='+version if version else ''}...")
        cmd = [sys.executable, "-m", "pip", "install"]
        if version:
            cmd.append(f"{package}=={version}")
        else:
            cmd.append(package)
        try:
            subprocess.check_call(cmd)
            return importlib.import_module(import_name)
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {package}. Some features may be disabled.")
            return None

# Install core packages
aiohttp = install_and_import("aiohttp")
flask = install_and_import("flask")
telegram = install_and_import("python-telegram-bot", "telegram")
telegram_ext = install_and_import("python-telegram-bot", "telegram.ext")
colorama = install_and_import("colorama")
cfonts = install_and_import("cfonts")
apscheduler = install_and_import("apscheduler")
pytz = install_and_import("pytz")

# Try to install openai – try older pure‑Python version first, then latest
openai = install_and_import("openai", version="0.28.0")
if openai is None:
    openai = install_and_import("openai")  # try latest

if openai is None:
    print("⚠️ OpenAI module could not be installed. AI chat will be disabled.")
    openai_available = False
    openai_client = None
    openai_version = None
else:
    openai_available = True
    import openai as openai_mod
    # Detect version
    if hasattr(openai_mod, "__version__") and openai_mod.__version__.startswith("0."):
        # Old API (v0.x)
        openai_client = openai_mod
        openai_version = "old"
        print("✅ OpenAI v0.x installed (using legacy API)")
    else:
        # New API (v1+)
        from openai import OpenAI
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        openai_version = "new"
        print("✅ OpenAI v1+ installed (using new API)")

# Now import everything normally
import asyncio
import logging
import random
import json
import os
import time
import threading
from collections import deque
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any

# Telegram imports
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
    JobQueue,
)

# Flask
from flask import Flask, send_from_directory, abort

# Colorama
from colorama import Fore, Style

# Cfonts
from cfonts import render

# ========== CONFIGURATION ==========
# 🔐 YOUR CREDENTIALS – use environment variables
import os
BOT_TOKEN = os.getenv("BOT_TOKEN", "8513808688:AAGBzlIPL0nPGTJAfbBj8w1Y0UGUJe8rag8")
CHANNEL_ID = os.getenv("CHANNEL_ID", "-1003591471913")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")
OPENAI_MODEL = "gpt-4o"

# Server 1 configuration
SERVER1_CONFIG = {
    "name": "Server 1 (51game random)",
    "api_source": "51game",
    "prediction_method": "random",
    "auto_send": True,
    "goal": 0,
    "send_stickers": True,
    "send_result_updates": True,
}

# Server 2 configuration
SERVER2_CONFIG = {
    "name": "Server 2 (51game average)",
    "api_source": "51game",
    "prediction_method": "average",
    "auto_send": True,
    "goal": 0,
    "send_stickers": True,
    "send_result_updates": True,
}

PREDICTION_IMAGE_URL = "https://i.ibb.co/Sw01h2BC/Gemini-Generated-Image-lw4c2llw4c2llw4c.png"
WIN_STICKER_IDS = [
    "CAACAgUAAxkBAAEBg-donNkibZLs9zPl7MRidXxY1FKF3QACBRIAAjRZYFSuC_g0_byf5TYE",
    "CAACAgQAAxkBAAKmimf5EB9GTlXRtwVB3ez1nBUKzf69AAKaDAACfx_4UvcUEDj6i_r9NgQ",
    "CAACAgQAAxkBAAKmjWf5ECecZUCJtSeuqsaaVWILpTuyAALICwACG86YUDSKklgR_M5FNgQ",
    "CAACAgIAAxkBAAKmkGf5EDBgwnSDovUPpQGsTjMQdU69AAL4DAACNyx5S6FYW3VBcuj4NgQ"
]
NUMBER_WIN_STICKER_ID = "CAACAgUAAxkBAAEBhfNooJofyaQPYk77B0QGfe83gH0gigACbRMAAmKzUFSqQXjp5UjYE"

REGISTER_LINK = "https://bharatclub.bet/#/register?invitationCode=338764745230"
HISTORY_FILE = "prediction_history.json"

# ========== PREDICTION SERVER CLASS ==========
class PredictionServer:
    """Handles all prediction logic for one server."""
    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
        self.history = deque(maxlen=100)          # list of dicts: period, prediction, pair, status, result, result_type
        self.predictions_sent = 0
        self.goal = config.get("goal", 0)
        self.auto_send = config.get("auto_send", True)
        self.telegram_sent_periods = {}           # track which periods already had prediction/sticker sent
        self.api_source = config.get("api_source", "51game")
        self.prediction_method = config.get("prediction_method", "random")
        self.send_stickers = config.get("send_stickers", True)
        self.send_result_updates = config.get("send_result_updates", True)

        # Predefined prediction pairs (for random method)
        self.BIG_PAIRS = ["1+3", "2+4", "3+5", "4+6"]
        self.SMALL_PAIRS = ["6+8", "7+9", "8+0", "9+1"]

    def get_big_small(self, num: int) -> str:
        return "BIG" if num >= 5 else "SMALL"

    def generate_prediction_random(self) -> Tuple[str, str]:
        r = random.random()
        if r < 0.5:
            size = "SMALL"
            pool = self.SMALL_PAIRS
        else:
            size = "BIG"
            pool = self.BIG_PAIRS
        pair = random.choice(pool)
        return size, pair

    def generate_prediction_average(self) -> Tuple[str, str]:
        results = [entry["result"] for entry in self.history if entry["result"] is not None]
        if len(results) < 5:
            return self.generate_prediction_random()
        avg = sum(results[-5:]) / 5
        size = "BIG" if avg > 5 else "SMALL"
        return size, "?"   # no number pair for average method

    def generate_prediction(self) -> Tuple[str, str]:
        if self.prediction_method == "random":
            return self.generate_prediction_random()
        elif self.prediction_method == "average":
            return self.generate_prediction_average()
        else:
            return "BIG", "1+3"

    def get_stats(self) -> dict:
        wins = sum(1 for e in self.history if e["status"] == "WIN")
        losses = sum(1 for e in self.history if e["status"] == "LOSS")
        total = wins + losses
        accuracy = (wins / total * 100) if total else 0
        return {
            "wins": wins,
            "losses": losses,
            "total": total,
            "accuracy": accuracy,
            "predictions_sent": self.predictions_sent,
            "goal": self.goal,
        }

# ========== GLOBAL STATE ==========
# Create two server instances
server1 = PredictionServer("Server 1 (51game random)", SERVER1_CONFIG)
server2 = PredictionServer("Server 2 (51game average)", SERVER2_CONFIG)
active_server = server1   # start with server1

# For channel access
channel_accessible = True

# ========== LOGGING ==========
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ========== FLASK WEB SERVER ==========
app_web = Flask(__name__)
HTML_DIR = "html_dashboards"
os.makedirs(HTML_DIR, exist_ok=True)

@app_web.route('/')
def index():
    return send_from_directory(HTML_DIR, 'index.html')

@app_web.route('/<path:filename>')
def serve_file(filename):
    try:
        return send_from_directory(HTML_DIR, filename)
    except Exception:
        abort(404)

def run_flask():
    app_web.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# ========== USER HISTORY FUNCTIONS (for interactive predictions) ==========
def init_history_file():
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "w") as f:
            json.dump({}, f)

def save_prediction(user_id: int, first_name: str, username: str, pred_type: str, number: int):
    with open(HISTORY_FILE, "r") as f:
        data = json.load(f)
    uid = str(user_id)
    if uid not in data:
        data[uid] = {
            "first_name": first_name,
            "username": username,
            "history": []
        }
    data[uid]["history"].append({
        "type": pred_type,
        "number": number,
        "timestamp": time.time()
    })
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user_history(user_id: int) -> list:
    with open(HISTORY_FILE, "r") as f:
        data = json.load(f)
    return data.get(str(user_id), {}).get("history", [])

def get_user_info(user_id: int) -> Tuple[str, str]:
    with open(HISTORY_FILE, "r") as f:
        data = json.load(f)
    user_data = data.get(str(user_id), {})
    name = user_data.get("first_name", "Unknown")
    username = user_data.get("username", "N/A")
    return name, username

# ========== API FETCHING (async) ==========
async def fetch_ar_1m(session: aiohttp.ClientSession) -> Optional[dict]:
    url = "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json"
    params = {"ts": int(time.time() * 1000)}
    try:
        async with session.get(url, params=params, timeout=10) as resp:
            data = await resp.json()
            latest = data["data"]["list"][0]
            return {
                "period": latest["issueNumber"],
                "number": int(latest["number"])
            }
    except Exception as e:
        logger.error(f"ar-1m fetch error: {e}")
        return None

async def fetch_ar_30s(session: aiohttp.ClientSession) -> Optional[dict]:
    url = "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json"
    params = {"ts": int(time.time() * 1000)}
    try:
        async with session.get(url, params=params, timeout=10) as resp:
            data = await resp.json()
            latest = data["data"][0]
            return {
                "period": latest.get("issueNumber", "?"),
                "number": int(latest["winNumber"])
            }
    except Exception as e:
        logger.error(f"ar-30s fetch error: {e}")
        return None

async def fetch_51game(session: aiohttp.ClientSession) -> Optional[dict]:
    url = "https://api.51gameapi.com/api/webapi/GetNoaverageEmerdList"
    payload = {
        "pageSize": 10,
        "pageNo": 1,
        "typeId": 1,
        "language": 0,
        "random": "6fadc24ccf2c4ed4afb5a1a5f84d2ba4",
        "signature": "4E071E587A80572ED6065D6F135F3ABE",
        "timestamp": int(time.time())
    }
    headers = {"Content-Type": "application/json"}
    try:
        async with session.post(url, json=payload, headers=headers, timeout=10) as resp:
            data = await resp.json()
            latest = data["data"]["list"][0]
            return {
                "period": latest["issueNumber"],
                "number": int(latest["number"])
            }
    except Exception as e:
        logger.error(f"51game fetch error: {e}")
        return None

async def fetch_latest_result(api_source: str) -> Optional[dict]:
    async with aiohttp.ClientSession() as session:
        if api_source == "ar-1m":
            return await fetch_ar_1m(session)
        elif api_source == "ar-30s":
            return await fetch_ar_30s(session)
        elif api_source == "51game":
            return await fetch_51game(session)
        else:
            logger.error(f"Unknown API source: {api_source}")
            return None

# ========== TELEGRAM SENDING HELPERS ==========
async def send_message(bot, chat_id: str, text: str, parse_mode: str = "HTML"):
    global channel_accessible
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        logger.info(f"Message sent to {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        if "chat not found" in str(e).lower():
            channel_accessible = False
            logger.warning("⚠️ Channel is not accessible. Auto‑send disabled.")

async def send_photo(bot, chat_id: str, caption: str, photo_url: str):
    global channel_accessible
    try:
        await bot.send_photo(chat_id=chat_id, photo=photo_url, caption=caption, parse_mode="HTML")
        logger.info(f"Photo sent to {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send photo: {e}")
        if "chat not found" in str(e).lower():
            channel_accessible = False
            logger.warning("⚠️ Channel is not accessible. Auto‑send disabled.")

async def send_sticker(bot, chat_id: str, sticker_id: str):
    global channel_accessible
    try:
        await bot.send_sticker(chat_id=chat_id, sticker=sticker_id)
        logger.info(f"Sticker sent to {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send sticker: {e}")
        if "chat not found" in str(e).lower():
            channel_accessible = False
            logger.warning("⚠️ Channel is not accessible. Auto‑send disabled.")

async def send_prediction_to_channel(bot, period: str, prediction: str, pair: str):
    global channel_accessible
    if not channel_accessible:
        return
    date = datetime.now().strftime("%d-%m-%Y")
    caption = f"""🚀 <b>RIZEN X AI PREDICTION</b> 🚀

╔═◈═◈═◈═◈═◈═╗
📅 <b>Date:</b> {date}
🎯 <b>Name:</b> RIZEN AI BOT
⏳ <b>Wingo:</b> 1Min
🔢 <b>Period No:</b> {period}
╚═◈═◈═◈═◈═◈═╝

📊 <b>RESULT INFO</b> 📊
✅ <b>Big/Small:</b> {prediction}
✅ <b>Numbers:</b> {pair}
──────✦✧✦──────"""
    await send_photo(bot, CHANNEL_ID, caption, PREDICTION_IMAGE_URL)

# ========== CORE LOGIC FOR A SERVER ==========
async def update_server_results(server: PredictionServer, bot):
    """Check results for one server and update its history."""
    global channel_accessible

    if not channel_accessible:
        return

    latest = await fetch_latest_result(server.api_source)
    if not latest:
        return

    current_period = latest["period"]
    current_number = latest["number"]
    current_type = server.get_big_small(current_number)

    if server.send_result_updates and server is active_server:
        result_msg = f"📊 <b>Period {current_period} Result:</b> {current_number} ({current_type})"
        await send_message(bot, CHANNEL_ID, result_msg)

    # Update any pending prediction for this period
    for entry in server.history:
        if entry["period"] == current_period and entry["status"] == "PENDING":
            predicted_size = entry["prediction"]
            predicted_pair = entry["pair"]
            number_win = False
            if predicted_pair != "?":
                try:
                    num1, num2 = map(int, predicted_pair.split('+'))
                    number_win = (current_number == num1 or current_number == num2)
                except:
                    pass
            size_win = (predicted_size == current_type)

            if size_win or number_win:
                entry["status"] = "WIN"
                win_type = "NUMBER" if number_win else "BIGSMALL"
            else:
                entry["status"] = "LOSS"
                win_type = None

            entry["result"] = current_number
            entry["result_type"] = current_type

            if server.send_stickers and entry["status"] == "WIN" and channel_accessible and server is active_server:
                period_sent = server.telegram_sent_periods.get(current_period, {})
                if not period_sent.get("sticker"):
                    sticker = NUMBER_WIN_STICKER_ID if win_type == "NUMBER" else random.choice(WIN_STICKER_IDS)
                    await send_sticker(bot, CHANNEL_ID, sticker)
                    server.telegram_sent_periods.setdefault(current_period, {})["sticker"] = True
            break

async def generate_server_prediction(server: PredictionServer, bot):
    """Generate next prediction for the server (only for active server)."""
    global channel_accessible

    if not channel_accessible:
        return

    latest = await fetch_latest_result(server.api_source)
    if not latest:
        return

    current_period = latest["period"]
    next_period = str(int(current_period) + 1)

    # Avoid duplicate prediction in history
    for entry in server.history:
        if entry["period"] == next_period:
            return

    prediction, pair = server.generate_prediction()
    server.history.appendleft({
        "period": next_period,
        "prediction": prediction,
        "pair": pair,
        "status": "PENDING",
        "result": None,
        "result_type": None
    })

    if server.auto_send and (server.goal == 0 or server.predictions_sent < server.goal) and channel_accessible:
        period_sent = server.telegram_sent_periods.get(next_period, {})
        if not period_sent.get("prediction"):
            await send_prediction_to_channel(bot, next_period, prediction, pair)
            server.telegram_sent_periods.setdefault(next_period, {})["prediction"] = True
            server.predictions_sent += 1
            if server.goal > 0 and server.predictions_sent >= server.goal:
                logger.info(f"{server.name} goal reached, disabling auto-send")
                server.auto_send = False
                await send_message(bot, CHANNEL_ID, f"🎯 <b>{server.name} TARGET COMPLETED!</b> 🎯\nProfit Success! 🍾🎉")

# ========== BACKGROUND TASK ==========
async def periodic_update(context: ContextTypes.DEFAULT_TYPE):
    """Called every 2 seconds; updates results for both servers, but generates only for active."""
    bot = context.bot
    # Update results for both servers (they both need to know outcomes)
    await update_server_results(server1, bot)
    await update_server_results(server2, bot)
    # Generate next prediction only for active server
    await generate_server_prediction(active_server, bot)

# ========== K3 PREDICTOR ==========
def get_k3_period() -> str:
    now = datetime.now()
    total_minutes = now.hour * 60 + now.minute
    return f"{now.year}{now.month:02d}{now.day:02d}1000{10001 + total_minutes - 330}"

def seeded_random(seed: int):
    value = seed
    while True:
        value = (value * 9301 + 49297) % 233280
        yield value / 233280

def get_k3_prediction() -> str:
    period = get_k3_period()
    seed = int(period)
    rng = seeded_random(seed)
    numbers = [int(next(rng) * 6) + 1 for _ in range(3)]
    total = sum(numbers)
    big_small = "Big 🚀" if total >= 11 else "Small 🐢" if total >= 4 else "Invalid"
    odd_even = "Even 🔵" if total % 2 == 0 else "Odd 🔴"
    num_str = " + ".join(map(str, numbers))
    return (
        f"🎲 <b>K3 WINGO PREDICTION</b>\n\n"
        f"Period: <code>{period}</code>\n"
        f"Numbers: {num_str}\n"
        f"Sum: <b>{total}</b>\n"
        f"Big/Small: <b>{big_small}</b>\n"
        f"Odd/Even: <b>{odd_even}</b>"
    )

# ========== TELEGRAM COMMAND HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔮 Get Prediction", callback_data="predict"),
         InlineKeyboardButton("🗂 My History", callback_data="history")],
        [InlineKeyboardButton("🔗 Register Now", callback_data="register"),
         InlineKeyboardButton("ℹ️ About", callback_data="about")]
    ])
    welcome = (
        f"👋 *Welcome, {user.first_name}!*\n\n"
        "🚨 *Note:* Real predictions milengi *sirf tab* jab aap official registration karoge.\n"
        "👇 Click *Register Now* to join 👇"
   

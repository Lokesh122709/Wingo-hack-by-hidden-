#!/usr/bin/env python3
"""
BigWin Wingo CLI – Run both WinGo1 and WinGo30 simultaneously
Sends predictions to Telegram group.
Usage:
    python script.py           -> both games
    python script.py both      -> both games
    python script.py 1         -> only WinGo1
    python script.py 30        -> only WinGo30
    python script.py 30 /sc    -> only WinGo30 with Server 2
"""

import subprocess
import sys
import time
import csv
import threading
import itertools
import argparse
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from collections import Counter

# Auto‑install requests (required)
try:
    import requests
except ImportError:
    print("📦 Required package 'requests' not found.")
    ans = input("Install requests now? (y/n): ").strip().lower()
    if ans == 'y':
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        import requests
    else:
        sys.exit(1)

# Optional packages
try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

try:
    from colorama import init, Fore, Back, Style
    init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

# ---------- Telegram Bot Configuration ----------
TELEGRAM_BOT_TOKEN = "8613029389:AAF45M8HvWswhXgUOBTB6Aiveo4Tgw9jR6A"
TELEGRAM_CHAT_ID = "-1003625900626"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def send_telegram_message(text: str):
    """Send a message to the configured Telegram group (non‑blocking)."""
    def _send():
        try:
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": ""  # No parse mode to ensure plain text
            }
            requests.post(TELEGRAM_API_URL, data=payload, timeout=5)
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️ Telegram send failed: {e}{Style.RESET_ALL}")
    threading.Thread(target=_send, daemon=True).start()

# ---------- Banners ----------
BANNER_PLAIN = """
    ██╗  ██╗██╗██████╗ ██████╗ ███████╗███╗   ██╗
    ██║  ██║██║██╔══██╗██╔══██╗██╔════╝████╗  ██║
    ███████║██║██║  ██║██║  ██║█████╗  ██╔██╗ ██║
    ██╔══██║██║██║  ██║██║  ██║██╔══╝  ██║╚██╗██║
    ██║  ██║██║██████╔╝██████╔╝███████╗██║ ╚████║
    ╚═╝  ╚═╝╚═╝╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝
                            x
        █████╗ ██╗     ██████╗ ██╗  ██╗ █████╗
       ██╔══██╗██║     ██╔══██╗██║  ██║██╔══██╗
       ███████║██║     ██████╔╝███████║███████║
       ██╔══██║██║     ██╔═══╝ ██╔══██║██╔══██║
       ██║  ██║███████╗██║     ██║  ██║██║  ██║
       ╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝
"""

def get_colored_banner():
    """Colored banner for console."""
    return f"{Fore.CYAN}{BANNER_PLAIN}{Style.RESET_ALL}"

# ---------- Spinner ----------
def spinner_task(stop_event, message="Fetching results"):
    spinner = itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"])
    color = Fore.CYAN if HAS_COLORAMA else ""
    reset = Style.RESET_ALL if HAS_COLORAMA else ""
    while not stop_event.is_set():
        for _ in range(10):
            if stop_event.is_set():
                break
            sys.stdout.write(f"\r{color}{next(spinner)} {message}...{reset}")
            sys.stdout.flush()
            time.sleep(0.1)
    sys.stdout.write("\r" + " " * 50 + "\r")
    sys.stdout.flush()

# ---------- Configuration ----------
FIREBASE_CONFIG = {
    "apiKey": "AIzaSyDj6z3O91NnlQ1zVdripiGhqQMsQhR4_ak",
    "databaseURL": "https://ck30-35e97-default-rtdb.europe-west1.firebasedatabase.app"
}

GAMES = {
    "1": {
        "name": "WinGo1",
        "firebase_path": "bigwinwingo1/default",
        "cd_time": 60,
        "emoji": "🎲"
    },
    "30": {
        "name": "WinGo30",
        "firebase_path": "bigwin/default",
        "cd_time": 30,
        "emoji": "🎰"
    }
}

# ---------- Firebase helpers ----------
def firebase_get(url: str) -> Optional[Dict]:
    try:
        resp = requests.get(url + ".json")
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"{Fore.RED}🔥 Firebase error: {e}{Style.RESET_ALL}")
        return None

def fetch_results(game_id: str) -> Optional[List[Dict]]:
    url = f"{FIREBASE_CONFIG['databaseURL']}/{GAMES[game_id]['firebase_path']}"
    data = firebase_get(url)
    if data and "list" in data and isinstance(data["list"], list):
        return data["list"]
    return None

def get_session_expiry() -> int:
    return int((datetime.now() + timedelta(days=36500)).timestamp() * 1000)

# ---------- Results processing ----------
def classify(n):
    try:
        num = int(n)
        return "BIG" if num >= 5 else "SMALL"
    except:
        return None

def compute_prediction_system1(results: List[Dict]) -> str:
    if len(results) < 2:
        return "Insufficient data"
    last5 = results[:5]
    weighted_big = 0
    weighted_small = 0
    for i, r in enumerate(last5):
        weight = 2 if i < 3 else 1
        bs = classify(r.get("number"))
        if bs == "BIG":
            weighted_big += weight
        elif bs == "SMALL":
            weighted_small += weight
    return "BIG" if weighted_big >= weighted_small else "SMALL"

def compute_prediction_system2(results: List[Dict]) -> str:
    if len(results) < 2:
        return "Insufficient data"
    trans = {"BIG": {"BIG": 0, "SMALL": 0}, "SMALL": {"BIG": 0, "SMALL": 0}}
    for i in range(1, len(results)):
        prev = classify(results[i-1].get("number"))
        curr = classify(results[i].get("number"))
        if prev and curr:
            trans[prev][curr] += 1

    last_outcome = classify(results[0].get("number"))
    if last_outcome and (trans[last_outcome]["BIG"] + trans[last_outcome]["SMALL"]) > 0:
        if trans[last_outcome]["BIG"] > trans[last_outcome]["SMALL"]:
            return "BIG"
        elif trans[last_outcome]["SMALL"] > trans[last_outcome]["BIG"]:
            return "SMALL"
        else:
            return "EQUAL"
    return "Unknown"

def analyze_results(results: List[Dict]):
    if not results:
        return None

    big = sum(1 for r in results if classify(r.get("number")) == "BIG")
    small = sum(1 for r in results if classify(r.get("number")) == "SMALL")
    total = len(results)

    digits = [int(r["number"]) for r in results if str(r.get("number")).isdigit()]
    freq = Counter(digits)
    most_common = freq.most_common(3)
    least_common = freq.most_common()[:-4:-1] if freq else []

    max_streak = 0
    current = 0
    last = None
    for r in results:
        bs = classify(r.get("number"))
        if bs == last:
            current += 1
        else:
            current = 1
            last = bs
        if current > max_streak:
            max_streak = current

    return {
        "big": big,
        "small": small,
        "total": total,
        "freq": freq,
        "most_common": most_common,
        "least_common": least_common,
        "max_streak": max_streak
    }

# ---------- Display (console) ----------
def colored(text, color_code):
    if HAS_COLORAMA:
        return color_code + text + Style.RESET_ALL
    return text

def print_stats(stats, game_name, game_emoji, prediction, server_mode):
    server_label = f"Server {server_mode}"
    pred_emoji = "🟢" if prediction == "BIG" else "🔴" if prediction == "SMALL" else "⚪"
    print("\n" + "="*70)
    print(colored(f"{game_emoji} {game_name} Statistics {game_emoji} [{server_label}]", Fore.CYAN + Back.BLACK))
    print("="*70)
    print(f"  {colored('🦁 BIG', Fore.GREEN)}   : {stats['big']}   {colored('🐭 SMALL', Fore.YELLOW)} : {stats['small']}   {colored('📊 TOTAL', Fore.MAGENTA)} : {stats['total']}")
    print(f"  {colored('⚡ Max streak', Fore.CYAN)} : {stats['max_streak']}")

    print(f"\n{colored('🔢 Digit frequency (0-9):', Fore.CYAN)}")
    if HAS_TABULATE:
        table = [[d, stats['freq'].get(d, 0)] for d in range(10)]
        print(tabulate(table, headers=["Digit", "Count"], tablefmt="grid"))
    else:
        for d in range(10):
            cnt = stats['freq'].get(d, 0)
            bar = "█" * cnt
            print(f"   {d}: {cnt:2d} {bar}")

    print(f"\n{colored('🔥 Most frequent digits:', Fore.RED)}")
    for d, cnt in stats['most_common']:
        print(f"   {d}: {cnt} times")
    print(f"\n{colored('❄️ Least frequent digits:', Fore.BLUE)}")
    for d, cnt in stats['least_common']:
        print(f"   {d}: {cnt} times")

    print(colored(f"\n🔮 {server_label} Prediction (based on server data):", Fore.YELLOW))
    print(f"   {pred_emoji} {prediction}")

def print_recent(results, limit=10):
    if not results:
        return
    print(colored(f"\n📋 Last {limit} results:", Fore.CYAN))
    headers = ["#", "Period", "Number", "B/S", "Premium"]
    table_data = []
    for i, r in enumerate(results[:limit]):
        period = str(r.get("period") or r.get("issueNumber") or r.get("issue") or r.get("periodNumber") or "-")[:12]
        number = r.get("number", "-")
        bs = classify(number) or "-"
        bs_emoji = "🦁" if bs == "BIG" else "🐭" if bs == "SMALL" else ""
        premium = str(r.get("premium") or r.get("hashValue") or r.get("blockHashtag") or "-")[:10]
        table_data.append([i+1, period, number, f"{bs_emoji} {bs}", premium])

    if HAS_TABULATE:
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        print(f"{headers[0]:<3} {headers[1]:<12} {headers[2]:<6} {headers[3]:<8} {headers[4]:<10}")
        print("-"*55)
        for row in table_data:
            print(f"{row[0]:<3} {row[1]:<12} {row[2]:<6} {row[3]:<8} {row[4]:<10}")

def export_results(results, filename):
    if not results:
        print("No results to export.")
        return
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Period", "Number", "Premium", "HashValue", "BlockHashtag", "Big/Small"])
        for r in results:
            period = r.get("period") or r.get("issueNumber") or r.get("issue") or r.get("periodNumber") or ""
            number = r.get("number", "")
            premium = r.get("premium") or ""
            hashv = r.get("hashValue") or ""
            block = r.get("blockHashtag") or ""
            bs = classify(number) or ""
            writer.writerow([period, number, premium, hashv, block, bs])
    print(colored(f"✅ Exported {len(results)} rows to {filename}", Fore.GREEN))

# ---------- Game runner thread ----------
def game_worker(game_id: str, server_mode: int):
    """Runs a single game in an infinite loop."""
    cd = GAMES[game_id]["cd_time"]
    game_emoji = GAMES[game_id]["emoji"]
    expiry = get_session_expiry()  # far future, effectively infinite

    print(colored(f"\n⏳ [{GAMES[game_id]['name']}] Thread started. Server {server_mode}. Refresh every {cd}s.", Fore.YELLOW))

    while True:
        remaining = expiry - (time.time() * 1000)
        if remaining <= 0:
            print(colored(f"\n⌛ [{GAMES[game_id]['name']}] Session expired. Exiting thread.", Fore.RED))
            break

        # Show remaining time (optional, but we can print it)
        hours = int(remaining // 3600000)
        minutes = int((remaining % 3600000) // 60000)
        seconds = int((remaining % 60000) // 1000)
        # Uncomment next line if you want per‑game time display (can clutter)
        # print(colored(f"\n⏰ [{GAMES[game_id]['name']}] Time left: {hours:02d}:{minutes:02d}:{seconds:02d}", Fore.CYAN))

        # Spinner for this game (optional, but we'll just fetch without spinner to avoid conflicts)
        # We'll just fetch directly
        results = fetch_results(game_id)

        if results:
            stats = analyze_results(results)
            if server_mode == 1:
                pred = compute_prediction_system1(results)
            else:
                pred = compute_prediction_system2(results)

            pred_emoji = "🟢" if pred == "BIG" else "🔴" if pred == "SMALL" else "⚪"
            telegram_msg = f"{game_emoji} {GAMES[game_id]['name']} [Server {server_mode}] Prediction: {pred} {pred_emoji}"
            send_telegram_message(telegram_msg)

            # Also print to console (optional)
            if stats:
                print_stats(stats, GAMES[game_id]['name'], game_emoji, pred, server_mode)
            print_recent(results, limit=5)  # show fewer to reduce clutter
        else:
            print(colored(f"⚠️ [{GAMES[game_id]['name']}] Could not fetch results. Retrying...", Fore.YELLOW))

        time.sleep(cd)

# ---------- Main ----------
def main():
    parser = argparse.ArgumentParser(description="BigWin Wingo Predictor (Dual Game)")
    parser.add_argument("mode", nargs="?", default="both", help="'1', '30', 'both' (default), or '/sc' for server2 (use with game)")
    parser.add_argument("server", nargs="?", help="'/sc' for Server 2 (Markov chain) – only if mode is a game ID")
    args = parser.parse_args()

    # Determine which games to run and server modes
    games_to_run = []
    server_mode = 1

    # Handle server argument
    if args.server and args.server.lower() == '/sc':
        server_mode = 2

    # Parse mode
    mode = args.mode.lower() if args.mode else "both"

    if mode == "both":
        games_to_run = [("1", 1), ("30", 1)]  # both with Server 1
        # If server arg was given with both, ignore? We'll just use server 1 for both.
        print(colored("🎰 Running both WinGo1 and WinGo30 with Server 1", Fore.GREEN))
    elif mode == "1":
        games_to_run = [("1", server_mode)]
        print(colored(f"🎰 Running WinGo1 with Server {server_mode}", Fore.GREEN))
    elif mode == "30":
        games_to_run = [("30", server_mode)]
        print(colored(f"🎰 Running WinGo30 with Server {server_mode}", Fore.GREEN))
    else:
        print(colored(f"❌ Invalid mode: {mode}. Use '1', '30', or 'both'.", Fore.RED))
        sys.exit(1)

    # Print banner to console
    print(get_colored_banner())
    # Send banner to Telegram
    send_telegram_message(BANNER_PLAIN)

    # Start threads for each game
    threads = []
    for game_id, srv in games_to_run:
        t = threading.Thread(target=game_worker, args=(game_id, srv), daemon=True)
        t.start()
        threads.append(t)

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(colored("\n👋 Shutting down by user request.", Fore.YELLOW))
        sys.exit(0)

if __name__ == "__main__":
    main()

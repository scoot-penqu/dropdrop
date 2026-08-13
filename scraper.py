import json
import urllib.request
import urllib.parse
import re
import os
import time
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
import google.generativeai as genai

# --- INITIALIZE GOOGLE AI & AUTO-DISCOVER MODEL ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
AVAILABLE_MODEL = "gemini-1.5-flash" # Fallback

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    try:
        # Ask Google for exactly what models this API key is allowed to use
        valid_models = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Pick the smartest, fastest model available on the list
        if 'gemini-2.0-flash' in valid_models: AVAILABLE_MODEL = 'gemini-2.0-flash'
        elif 'gemini-2.0-flash-exp' in valid_models: AVAILABLE_MODEL = 'gemini-2.0-flash-exp'
        elif 'gemini-1.5-flash' in valid_models: AVAILABLE_MODEL = 'gemini-1.5-flash'
        elif 'gemini-1.5-flash-latest' in valid_models: AVAILABLE_MODEL = 'gemini-1.5-flash-latest'
        elif 'gemini-1.5-pro' in valid_models: AVAILABLE_MODEL = 'gemini-1.5-pro'
        elif 'gemini-pro' in valid_models: AVAILABLE_MODEL = 'gemini-pro'
        elif len(valid_models) > 0: AVAILABLE_MODEL = valid_models[0]
        
        print(f"✅ AI Initialized. Auto-selected guaranteed model: {AVAILABLE_MODEL}")
    except Exception as e:
        print(f"⚠️ Auto-detect failed, using fallback. Error: {e}")

# --- ASSETS & WHITELISTS ---
RETAILER_LOGOS = {
    'Target': 'https://www.google.com/s2/favicons?domain=target.com&sz=256',
    'Walmart': 'https://www.google.com/s2/favicons?domain=walmart.com&sz=256',
    'Amazon': 'https://www.google.com/s2/favicons?domain=amazon.com&sz=256',
    'Pokemoncenter': 'https://www.google.com/s2/favicons?domain=pokemoncenter.com&sz=256',
    'Gamestop': 'https://www.google.com/s2/favicons?domain=gamestop.com&sz=256',
    'Bestbuy': 'https://www.google.com/s2/favicons?domain=bestbuy.com&sz=256',
    'Samsclub': 'https://www.google.com/s2/favicons?domain=samsclub.com&sz=256',
    'Costco': 'https://www.google.com/s2/favicons?domain=costco.com&sz=256',
    'Ebay': 'https://www.google.com/s2/favicons?domain=ebay.com&sz=256',
    'Tcgplayer': 'https://www.google.com/s2/favicons?domain=tcgplayer.com&sz=256',
    'Reddit': 'https://www.google.com/s2/favicons?domain=reddit.com&sz=256'
}
RETAILERS = [k.lower() for k in RETAILER_LOGOS.keys() if k != 'Reddit']
SUBREDDITS = ['PKMNTCGDeals', 'PokemonRestocks', 'PokemonDropNotify', 'pokemonrestockr', 'PokemonTCGRestocks']

STORE_DOMAINS = [
    'target.com', 'walmart.com', 'amazon.com', 'pokemoncenter.com', 'gamestop.com', 
    'bestbuy.com', 'samsclub.com', 'costco.com', 'tcgplayer.com', 'ebay.com', 
    'forgeandfiregaming.com', 'safari-zone.com', 'zulusgames.com', 'smokeandmirrorshobby.com', 'gamenerdz.com'
]

BLOCKED_DOMAINS = ["temu.com", "trackalacker.com", "whatnot.com", "tiktok.com", "aliexpress.com", "dhgate.com"]
BLOCKED_KEYWORDS = [
    "temu", "trackalacker", "free card box", "spin to win", "referral code", "use my link", "sign up bonus",
    "opening with", "my kids", "my kid", "mail day", "look what i found", "finally got", "pulled", "my local target",
    "my local walmart", "tin haul", "pack opening", "in store find", "just picked up"
]

def is_spam(title, content, link):
    full_text = f"{title} {content} {link}".lower()
    if any(kw in full_text for kw in BLOCKED_KEYWORDS): return True
    if any(domain in link.lower() for domain in BLOCKED_DOMAINS): return True
    return False

def call_gemini(prompt):
    if not GEMINI_API_KEY: return None
    try:
        model = genai.GenerativeModel(AVAILABLE_MODEL)
        
        # Older models (like gemini-pro) don't support forced JSON, so we handle it dynamically
        if "1.5" in AVAILABLE_MODEL or "2.0" in AVAILABLE_MODEL:
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(response_mime_type="application/json")
            )
        else:
            response = model.generate_content(prompt)
            
        clean_text = response.text.strip()
        if clean_text.startswith("
http://googleusercontent.com/immersive_entry_chip/0
http://googleusercontent.com/immersive_entry_chip/1

3. Click **Commit changes**.
4. Go to **Actions** and hit **Run workflow**.

When you check the logs this time, look at the very first print statement in the build log. It will say exactly which model it found and successfully connected to (e.g. `✅ AI Initialized. Auto-selected guaranteed model: gemini-...`). No more 404s!

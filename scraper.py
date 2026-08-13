import json
import urllib.request
import urllib.parse
import re
import os
import time
import concurrent.futures
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from google import genai

# --- INITIALIZE GOOGLE AI & MODEL ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
AVAILABLE_MODEL = "gemini-3.6-flash" 

if GEMINI_API_KEY:
    try:
        client = genai.Client()
        print(f"✅ AI Initialized using Interactions API. Model: {AVAILABLE_MODEL}")
    except Exception as e:
        print(f"⚠️ Initialization failed. Error: {e}")

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
    'Reddit': 'https://www.google.com/s2/favicons?domain=reddit.com&sz=256',
    'PokeBeach': 'https://www.google.com/s2/favicons?domain=pokebeach.com&sz=256'
}
RETAILERS = [k.lower() for k in RETAILER_LOGOS.keys() if k not in ['Reddit', 'PokeBeach']]
SUBREDDITS = ['PKMNTCGDeals', 'PokemonRestocks', 'PokemonDropNotify', 'pokemonrestockr', 'PokemonTCGRestocks']

STORE_DOMAINS = [
    'target.com', 'walmart.com', 'amazon.com', 'pokemoncenter.com', 'gamestop.com', 
    'bestbuy.com', 'samsclub.com', 'costco.com', 'tcgplayer.com', 'ebay.com'
]

BLOCKED_DOMAINS = ["temu.com", "trackalacker.com", "whatnot.com", "tiktok.com", "aliexpress.com", "dhgate.com"]
BLOCKED_KEYWORDS = [
    "temu", "trackalacker", "free card box", "spin to win", "referral code", "use my link", "sign up bonus",
    "opening with", "my kids", "my kid", "mail day", "look what i found", "finally got", "pulled", "my local target"
]

def is_spam(title, content, link):
    full_text = f"{title} {content} {link}".lower()
    if any(kw in full_text for kw in BLOCKED_KEYWORDS): return True
    if any(domain in link.lower() for domain in BLOCKED_DOMAINS): return True
    return False

def call_gemini(prompt, retries=3):
    if not GEMINI_API_KEY: return None
    for attempt in range(retries):
        try:
            client = genai.Client()
            interaction = client.interactions.create(
                model=AVAILABLE_MODEL,
                input=prompt
            )
            clean_text = interaction.output_text.strip()
            if clean_text.startswith("```json"): clean_text = clean_text[7:-3].strip()
            elif clean_text.startswith("```"): clean_text = clean_text[3:-3].strip()
            return json.loads(clean_text)
        except Exception as e:
            error_msg = str(e).lower()
            if '429' in error_msg or 'quota' in error_msg or 'too_many_requests' in error_msg:
                sleep_time = 5 * (attempt + 1)
                time.sleep(sleep_time)
            else:
                return None
    return None

def evaluate_drop_with_ai(title, content, comments_text):
    clean_body = ' '.join(re.sub(r'<[^>]+>', ' ', content).split())[:1000]
    prompt = f"""
    Analyze this Pokémon TCG Reddit deal post.
    Title: "{title}" | Body: "{clean_body}" | Comments: {comments_text}
    REJECT if personal haul, generic card flex, mail day, or off-topic chatter.
    ACCEPT if active online restock, store drop, OR upcoming drop announcement/rumor.
    Return valid JSON ONLY:
    {{"status": "VALID" or "INVALID", "type": "ONLINE" or "IN-STORE", "summary": "1-2 sentence concise summary.", "items": "- Item Name ($Price)"}}
    """
    res = call_gemini(prompt)
    if res:
        return res.get("status", "INVALID").upper() == "VALID", res.get("type", "UNKNOWN").upper(), res.get("summary", title), res.get("items", "")
    return True, "UNKNOWN", title, ""

def evaluate_news_with_ai(title, content):
    clean_body = ' '.join(re.sub(r'<[^>]+>', ' ', content).split())[:1000]
    prompt = f"""
    Analyze this Pokémon TCG news post. Title: "{title}" | Content: "{clean_body}"
    Categorize into: RESTOCK, NEWS, LEAK, or OTHER.
    Return valid JSON ONLY:
    {{"category": "RESTOCK", "summary": "Concise summary with price and release date if available.", "price": "Extracted price or 'N/A'", "time": "Extracted time/date or 'N/A'"}}
    """
    res = call_gemini(prompt)
    if res:
        summary = res.get("summary", title)
        if res.get("price") != "N/A" and res.get("price") not in summary:
            summary += f" | 💰 {res.get('price')}"
        if res.get("time") != "N/A" and res.get("time") not in summary:
            summary += f" | 🕒 {res.get('time')}"
        return res.get("category", "OTHER").upper(), summary
    return "OTHER", title

def generate_global_intel_brief(drops, news_items):
    if not drops and not news_items: 
        return "<b>⚡ Intel Brief:</b><br>Radar currently clear. Monitoring active markets..."
        
    context = "\n".join([f"[DROP] {item['title']} | Details: {re.sub(r'<[^>]+>', ' ', item['desc']).strip()}" for item in drops[:10]] + [f"[NEWS] {item['title']} | Details: {item['desc']}" for item in news_items[:10]])
    
    prompt = f"""
    Synthesize the raw feed of active Reddit deals and news alerts below into a single "Upcoming Drop & Release Schedule" brief.
    Format using bullet points. 
    Use bolding (<b> tags) to emphasize set/item names, dates, times, and retailers. 
    DO NOT use highlight tags, HTML colors, or <mark> tags. Strictly use bolding only.
    Raw Feed: {context}
    Return valid JSON ONLY:
    {{"brief": "<b>⚡ Active & Upcoming Schedule:</b><ul style='margin-top: 6px; padding-left: 18px; line-height: 1.5;'><li><b>Set / Item Name</b> - <b>Date / Time (Retailer):</b> Status</li></ul>"}}
    """
    res = call_gemini(prompt)
    if res: 
        clean_brief = res.get("brief", "<b>⚡ Intel Brief:</b><br>Radar currently clear.").replace("<mark>", "").replace("</mark>", "")
        return clean_brief
    return "<b>⚡ Intel Brief:</b><br>Radar currently clear."

def fetch_rss_proxy(url):
    try:
        req = urllib.request.Request(f"https://api.rss2json.com/v1/api.json?rss_url={url}", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode()).get('items', [])
    except: return []

def process_single_reddit_post(post, sub):
    title, content_raw, source_link, guid = post.get('title', ''), post.get('content', ''), post.get('link', ''), post.get('guid', '')
    if is_spam(title, content_raw, source_link): return None
        
    extracted_links_html = "<div style='margin-top: 6px; padding-top: 6px; border-top: 1px solid #30363d;'><strong style='color:#f0f6fc; font-size: 0.8rem;'>🛒 Links:</strong><ul style='margin-top: 4px; padding-left: 14px; font-size: 0.8rem;'>"
    link_count, detected_retailer, extracted_image = 0, "Reddit", None
    
    for url in set(re.findall(r'(https?://[^\s)\]"\']+)', content_raw)):
        if any(ext in url.lower() for ext in ['.jpg', '.png', '.jpeg', 'i.redd.it', 'imgur.com']):
            if not extracted_image: extracted_image = url
            continue 
        if any(bd in url.lower() for bd in BLOCKED_DOMAINS) or not any(domain in url.lower() for domain in STORE_DOMAINS): continue
        if matched := next((r.capitalize() for r in RETAILERS if r in url.lower()), None): detected_retailer = matched
        extracted_links_html += f"<li style='margin-bottom: 3px;'><a href='{url}' target='_blank' style='color: #3498db; text-decoration: none;'>{url.split('?')[0][:40]}...</a></li>"
        link_count += 1
        
    if link_count == 0:
        extracted_links_html += f"<li style='margin-bottom: 3px;'><a href='{source_link}' target='_blank' style='color: #3498db; text-decoration: none;'>💬 Reddit Discussion Thread</a></li>"
    extracted_links_html += "</ul></div>"
    
    comments_text = ""
    if guid and "reddit.com" in guid:
        for c in fetch_rss_proxy(guid + ".rss" if not guid.endswith(".rss") else guid)[1:4]:
            if clean_c := re.sub(r'<[^>]+>', ' ', c.get('content', '')).strip(): comments_text += f"- {clean_c[:100]}\n"

    is_valid, drop_type, ai_summary, ai_items = evaluate_drop_with_ai(title, content_raw, comments_text)
    if not is_valid: return None
    if detected_retailer == "Reddit" and (matched := next((r.capitalize() for r in RETAILERS if r in title.lower()), None)): detected_retailer = matched

    final_desc = f"<div style='color:#a8b2bd; line-height: 1.4; font-size: 0.8rem; margin-bottom:6px;'>✨ {ai_summary}</div>"
    if ai_items: final_desc += f"<div style='white-space: pre-line; color:#a8b2bd; font-family: monospace; font-size: 0.8rem; margin-bottom:6px;'>{ai_items}</div>"
    final_desc += extracted_links_html

    try: date_str = datetime.strptime(post.get('pubDate', '')[:25].strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).isoformat()
    except: date_str = datetime.now(timezone.utc).isoformat()

    return {
        "title": title[:65] + "..." if len(title) > 65 else title, "price": "Check Details", "retailer": detected_retailer, 
        "date": date_str, "type": drop_type, "image": extracted_image or RETAILER_LOGOS.get(detected_retailer, RETAILER_LOGOS['Reddit']),
        "source_link": source_link, "desc": final_desc, "sub": sub
    }

def build_drops():
    drops = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_single_reddit_post, post, sub) for sub in SUBREDDITS for post in fetch_rss_proxy(f'https://www.reddit.com/r/{sub}/new.rss')]
        for future in concurrent.futures.as_completed(futures):
            if result := future.result():
                drops.append(result)
    drops.sort(key=lambda x: x['date'], reverse=True)
    return drops

def process_single_news_item(item, source_type):
    title_elem, link_elem = item.find('title'), item.find('link')
    if title_elem is None or link_elem is None: return None
    
    title, link = title_elem.text, link_elem.text
    desc_elem = item.find('description')
    desc = desc_elem.text if desc_elem is not None else ''
    
    if 'pocket' in title.lower() or is_spam(title, desc, link): return None
    
    category, ai_summary = evaluate_news_with_ai(title, desc)
    
    try: iso_date = datetime.strptime(item.find('pubDate').text[:25].strip(), "%a, %d %b %Y %H:%M:%S").isoformat() + "Z"
    except: iso_date = datetime.now(timezone.utc).isoformat()
    return {"title": title[:70] + "...", "source": source_type, "date": iso_date, "desc": ai_summary, "link": link, "category": category}

def fetch_google_news(query, source_type):
    news_list, seen_links = [], set()
    req = urllib.request.Request(f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en", headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            items = ET.fromstring(response.read()).findall('./channel/item')[:12]
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(process_single_news_item, i, source_type) for i in items if i.find('link').text not in seen_links and not seen_links.add(i.find('link').text)]
                for f in concurrent.futures.as_completed(futures):
                    if r := f.result(): news_list.append(r)
    except Exception as e:
        print(f"Google Search Blocked ({source_type}) - Query: {query} Error: {e}")
    news_list.sort(key=lambda x: x['date'], reverse=True)
    return news_list

def build_news(drops_data):
    web_query = 'Pokemon TCG (restock OR preorder OR drop OR "Prismatic Evolutions" OR "30th Anniversary") -site:twitter.com -site:x.com when:3d'
    
    # Enhanced Twitter query using target keywords and accounts
    x_query = '("upcoming pokemon drops" OR "pokemon tcg drops" OR @PokemonDealsTCG OR @TCGTRACKER OR @PokemonRestocks) (site:twitter.com OR site:x.com) when:2d'
    
    # PokeBeach Google RSS workaround (bypasses Cloudflare 403 Forbidden)
    pokebeach_query = 'site:pokebeach.com when:7d'
    
    articles = fetch_google_news(web_query, "Google News")
    tweets = fetch_google_news(x_query, "X / Twitter")
    pokebeach_news = fetch_google_news(pokebeach_query, "PokeBeach")
    
    intel_brief = generate_global_intel_brief(drops_data, articles + tweets + pokebeach_news)
    return {"articles": articles, "tweets": tweets, "pokebeach": pokebeach_news, "intel_brief": intel_brief}

# --- MASTER EXECUTION ---
print("🚀 Starting High-Speed Data Scrape...")
start_time = time.time()

drops_output = build_drops()
output_data = {"last_run": datetime.now(timezone.utc).isoformat(), "drops": drops_output}
output_data.update(build_news(drops_output))

with open('data.json', 'w') as f: json.dump(output_data, f, indent=4)

end_time = time.time()
print(f"✅ Auto-Detect AI Engine generated successfully in {round(end_time - start_time, 2)} seconds!")

import json
import urllib.request
import urllib.parse
import re
import os
import time
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

# Import the new Google GenAI SDK for the Interactions API
from google import genai

# --- INITIALIZE GOOGLE AI & MODEL ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
AVAILABLE_MODEL = "gemini-3.6-flash" # Updated to modern Interactions API model

if GEMINI_API_KEY:
    try:
        # Initialize the modern Interactions API client (automatically picks up GEMINI_API_KEY env var)
        client = genai.Client()
        print(f"✅ AI Initialized using Interactions API. Defaulting to: {AVAILABLE_MODEL}")
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

def call_gemini(prompt, retries=3):
    if not GEMINI_API_KEY: return None
    
    for attempt in range(retries):
        try:
            client = genai.Client()
            
            # Call the new Interactions API endpoint
            interaction = client.interactions.create(
                model=AVAILABLE_MODEL,
                input=prompt
            )
                
            clean_text = interaction.output_text.strip()
            
            # Clean up markdown code blocks if the model outputs them
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:-3].strip()
            elif clean_text.startswith("```"):
                clean_text = clean_text[3:-3].strip()
                
            return json.loads(clean_text)
            
        except Exception as e:
            error_msg = str(e).lower()
            # Check if the error is a rate limit (429)
            if '429' in error_msg or 'quota' in error_msg or 'too_many_requests' in error_msg:
                print(f"⚠️ Rate limit hit. Pausing script for 60 seconds (Retry {attempt + 1} of {retries})...")
                time.sleep(60)
            else:
                print(f"SDK Error with {AVAILABLE_MODEL}: {e}")
                return None
                
    print("❌ Max retries reached for this item. Skipping.")
    return None

def evaluate_drop_with_ai(title, content, comments_text):
    clean_body = ' '.join(re.sub(r'<[^>]+>', ' ', content).split())[:1000]
    prompt = f"""
    Analyze this Pokémon TCG Reddit deal post.
    Title: "{title}"
    Body: "{clean_body}"
    Comments: {comments_text}

    REJECT if personal haul, discussion, local find, or showing off cards.
    ACCEPT ONLY if active online restock or nationwide drop.

    SUMMARY RULES: Write 2-3 dense sentences. NEVER repeat the title. Include specific prices, stock limits, and what the community is saying in the comments (e.g., "Sold Out quickly", "Still active").

    Return valid JSON ONLY:
    {{
        "status": "VALID" or "INVALID",
        "type": "ONLINE" or "IN-STORE",
        "summary": "Dense 2-3 sentence summary.",
        "items": "- Item Name ($Price)"
    }}
    """
    res = call_gemini(prompt)
    if res:
        is_valid = res.get("status", "INVALID").upper() == "VALID"
        return is_valid, res.get("type", "UNKNOWN").upper(), res.get("summary", title), res.get("items", "")
    return True, "UNKNOWN", title, ""

def evaluate_news_with_ai(title, content):
    clean_body = ' '.join(re.sub(r'<[^>]+>', ' ', content).split())[:1000]
    prompt = f"""
    Analyze this Pokémon TCG news/tweet.
    Title: "{title}"
    Content: "{clean_body}"
    
    Task: Is this an actionable product restock, drop announcement, or preorder?
    If yes, summarize what it is. CRITICAL: If a price (e.g. $49.99) or an expected drop time (e.g. 10 AM EST) is mentioned, you MUST include it in the summary. Do not just copy the title.

    Return valid JSON ONLY:
    {{
        "is_drop": "YES" or "NO",
        "summary": "Dense summary with price and time if available.",
        "price": "Extracted price or 'N/A'",
        "time": "Extracted time or 'N/A'"
    }}
    """
    res = call_gemini(prompt)
    if res:
        summary = res.get("summary", title)
        if res.get("price") != "N/A" and res.get("price") not in summary:
            summary += f" | 💰 {res.get('price')}"
        if res.get("time") != "N/A" and res.get("time") not in summary:
            summary += f" | 🕒 {res.get('time')}"
        return res.get("is_drop", "NO").upper(), summary
    return "NO", title

def generate_global_intel_brief(news_items):
    if not news_items or not GEMINI_API_KEY: return "Radar currently clear. Monitoring active markets..."
    context = "\n".join([f"- {item['title']}: {item['desc']}" for item in news_items[:15]])
    
    prompt = f"""
    You are an expert Pokémon TCG Market Analyst. Below is a raw feed of today's news and restock tweets.
    Read them and synthesize a "Global Intel Brief" summarizing the current state of the market right now.
    
    Focus on: What major sets are actively dropping (e.g., Prismatic Evolutions, 30th Anniversary)? Where are they dropping? Are there any expected times?
    Write a cohesive, professional 2-3 paragraph executive summary. Do not list individual tweets.
    
    Raw Feed:
    {context}
    
    Return valid JSON ONLY:
    {{
        "brief": "Your multi-paragraph executive summary here."
    }}
    """
    res = call_gemini(prompt)
    if res: return res.get("brief", "Radar currently clear. Monitoring active markets...")
    return "Radar currently clear. Monitoring active markets..."

def fetch_rss_proxy(url):
    req = urllib.request.Request(f"https://api.rss2json.com/v1/api.json?rss_url={url}", headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode()).get('items', [])
    except: return []

def build_drops():
    drops = []
    for sub in SUBREDDITS:
        items = fetch_rss_proxy(f'https://www.reddit.com/r/{sub}/new.rss')
        for post in items:
            title, content_raw, source_link, guid = post.get('title', ''), post.get('content', ''), post.get('link', ''), post.get('guid', '')
            if is_spam(title, content_raw, source_link): continue
                
            extracted_links_html = "<div style='margin-top: 8px; padding-top: 8px; border-top: 1px solid #30363d;'><strong style='color:#f0f6fc; font-size: 0.8rem;'>🛒 Links:</strong><ul style='margin-top: 4px; padding-left: 14px; font-size: 0.8rem;'>"
            link_count = 0
            detected_retailer, extracted_image = "Reddit", None
            
            all_urls = re.findall(r'(https?://[^\s)\]"\']+)', content_raw)
            for url in set(all_urls):
                if any(ext in url.lower() for ext in ['.jpg', '.png', '.jpeg', 'i.redd.it', 'imgur.com']):
                    if not extracted_image: extracted_image = url
                    continue 
                if not any(domain in url.lower() for domain in STORE_DOMAINS): continue
                
                matched_retailer = next((r.capitalize() for r in RETAILERS if r in url.lower()), None)
                if matched_retailer: detected_retailer = matched_retailer
                
                link_text = url.split('?')[0][:40] + "..."
                extracted_links_html += f"<li style='margin-bottom: 3px;'><a href='{url}' target='_blank' style='color: #3498db; text-decoration: none;'>{link_text}</a></li>"
                link_count += 1
                
            if link_count == 0: continue
            extracted_links_html += "</ul></div>"
            
            comments_text = ""
            if guid and "reddit.com" in guid:
                comment_feed = fetch_rss_proxy(guid + ".rss" if not guid.endswith(".rss") else guid)
                for c in comment_feed[1:4]:
                    clean_c = re.sub(r'<[^>]+>', ' ', c.get('content', '')).strip()
                    if clean_c: comments_text += f"- {clean_c[:100]}\n"

            is_valid_drop, drop_type, ai_summary, ai_items = evaluate_drop_with_ai(title, content_raw, comments_text)
            if not is_valid_drop: continue

            if detected_retailer == "Reddit":
                title_has_retailer = next((r.capitalize() for r in RETAILERS if r in title.lower()), None)
                if title_has_retailer: detected_retailer = title_has_retailer

            sub_badge = f"<span style='background:#ff4500; color:#ffffff; padding:2px 6px; border-radius:4px; font-size:10px; font-weight:bold; display:inline-block; margin-bottom: 6px;'>r/{sub}</span>"
            final_desc = f"{sub_badge}<div style='color:#f0f6fc; margin-bottom:6px; line-height: 1.4; font-size: 0.85rem;'>{ai_summary}</div>"
            if ai_items: final_desc += f"<div style='white-space: pre-line; color:#a8b2bd; font-family: monospace; font-size: 0.8rem; margin-bottom:6px;'>{ai_items}</div>"
            final_desc += extracted_links_html

            try:
                raw_date = post.get('pubDate', '')[:25].strip()
                date_str = datetime.strptime(raw_date, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).isoformat()
            except: date_str = datetime.now(timezone.utc).isoformat()

            drops.append({
                "title": title[:65] + "..." if len(title) > 65 else title,
                "price": "Check Links", "retailer": detected_retailer, "date": date_str, "type": drop_type,
                "image": extracted_image if extracted_image else RETAILER_LOGOS.get(detected_retailer, RETAILER_LOGOS['Reddit']),
                "source_link": source_link, "desc": final_desc
            })

    drops.sort(key=lambda x: x['date'], reverse=True)
    return drops

def fetch_google_news(query, source_type):
    news_list = []
    seen_links = set()
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    try:
        with urllib.request.urlopen(req) as response:
            root = ET.fromstring(response.read())
            for item in root.findall('./channel/item')[:8]:
                title = item.find('title').text
                link = item.find('link').text
                desc = item.find('description').text or ''
                if 'pocket' in title.lower() or link in seen_links: continue
                seen_links.add(link)
                
                is_drop, ai_summary = evaluate_news_with_ai(title, desc)
                
                try:
                    raw_date = item.find('pubDate').text[:25].strip()
                    iso_date = datetime.strptime(raw_date, "%a, %d %b %Y %H:%M:%S").isoformat() + "Z"
                except: iso_date = datetime.now(timezone.utc).isoformat()
                
                news_list.append({
                    "title": title[:70] + "...", "source": source_type, "date": iso_date,
                    "desc": ai_summary, "link": link, "is_drop": is_drop
                })
    except Exception as e:
        print(f"Google Search Blocked ({source_type}): {e}")
    
    news_list.sort(key=lambda x: x['date'], reverse=True)
    return news_list

def build_news():
    master_query = 'Pokemon TCG (restock OR preorder OR drop OR "Prismatic Evolutions" OR "Ascended Heroes" OR "30th Celebrations")'
    
    web_query = f"{master_query} -site:twitter.com -site:x.com when:3d"
    x_query = f"{master_query} (site:twitter.com OR site:x.com) when:3d"
    
    articles = fetch_google_news(web_query, "Google News")
    time.sleep(2) 
    tweets = fetch_google_news(x_query, "X / Twitter")
    
    intel_brief = generate_global_intel_brief(articles + tweets)
    
    return {"articles": articles, "tweets": tweets, "intel_brief": intel_brief}

output_data = {"drops": build_drops()}
output_data.update(build_news())

with open('data.json', 'w') as f: json.dump(output_data, f, indent=4)
print("Auto-Detect AI Engine successfully generated!")

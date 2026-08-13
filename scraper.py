import json
import urllib.request
import urllib.parse
import re
import os
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

RETAILER_LOGOS = {
    'Target': 'https://upload.wikimedia.org/wikipedia/commons/c/c5/Target_Corporation_logo_%28vector%29.svg',
    'Walmart': 'https://upload.wikimedia.org/wikipedia/commons/c/ca/Walmart_logo.svg',
    'Amazon': 'https://upload.wikimedia.org/wikipedia/commons/a/a9/Amazon_logo.svg',
    'Pokemoncenter': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/Pok%C3%A9mon_Center_logo.svg/512px-Pok%C3%A9mon_Center_logo.svg.png',
    'Gamestop': 'https://upload.wikimedia.org/wikipedia/commons/0/05/GameStop_Logo.svg',
    'Bestbuy': 'https://upload.wikimedia.org/wikipedia/commons/b/b4/Best_Buy_logo.svg',
    'Samsclub': 'https://upload.wikimedia.org/wikipedia/commons/1/14/Sams_Club_Logo.svg',
    'Costco': 'https://upload.wikimedia.org/wikipedia/commons/5/59/Costco_Wholesale_logo_2010-10-26.svg',
    'Ebay': 'https://upload.wikimedia.org/wikipedia/commons/1/1b/EBay_logo.svg',
    'Tcgplayer': 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/TCGplayer_logo.svg/512px-TCGplayer_logo.svg.png',
    'Reddit': 'https://upload.wikimedia.org/wikipedia/commons/3/36/Reddit_logo.svg'
}
RETAILERS = [k.lower() for k in RETAILER_LOGOS.keys() if k != 'Reddit']
SUBREDDITS = ['PKMNTCGDeals', 'PokemonRestocks', 'PokemonDropNotify', 'pokemonrestockr', 'PokemonTCGRestocks']

# --- STRICT STORE WHITELIST ---
STORE_DOMAINS = [
    'target.com', 'walmart.com', 'amazon.com', 'pokemoncenter.com', 'gamestop.com', 
    'bestbuy.com', 'samsclub.com', 'costco.com', 'tcgplayer.com', 'ebay.com', 
    'forgeandfiregaming.com', 'safari-zone.com', 'zulusgames.com', 'smokeandmirrorshobby.com', 'gamenerdz.com'
]

# --- SPAM & PERSONAL HAUL BLOCKERS ---
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

def evaluate_drop_with_ai(title, content, comments_text):
    if not GEMINI_API_KEY:
        return True, "UNKNOWN", title, ""
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
    clean_body = re.sub(r'<[^>]+>', ' ', content)
    clean_body = ' '.join(clean_body.split())[:1000]

    prompt = f"""
    You are an AI deal filtering assistant for a Pokémon TCG alert website.
    
    Title: "{title}"
    Post Body: "{clean_body}"
    Top Community Comments:
    {comments_text if comments_text else "No comments yet."}

    STRICT REJECTION RULES:
    - REJECT if this is a personal haul, "mail day", pack pulls, or showing off a personal collection.
    - REJECT if this is about finding an item at a specific local store after they bought it.
    - REJECT if it is a discussion, question, or rumor.
    
    ACCEPT CRITERIA:
    - ONLY ACCEPT if it is an active online restock/pre-order alert or a nationwide stock drop.

    SUMMARY RULES:
    - Write 2-3 detailed sentences synthesizing the title, body, and comments. 
    - CRITICAL: Read the comments! If the community says "OOS", "Sold out", "Expired", "Scam", or "Fake", you MUST state that explicitly in your summary.
    - If the community confirms it's a great deal, mention the positive reaction.
    - NEVER just repeat the title.

    You MUST return ONLY a valid JSON object. Do not include markdown formatting.
    {{
        "status": "VALID", 
        "type": "ONLINE", 
        "summary": "Your detailed 2-3 sentence summary here.",
        "items": "- Item name ($Price)" 
    }}
    """
    
    data = json.dumps({
        "contents": [{"parts":[{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req) as response:
            ai_text = json.loads(response.read().decode())['candidates'][0]['content']['parts'][0]['text'].strip()
            parsed = json.loads(ai_text)
            
            is_valid = parsed.get("status", "INVALID").upper() == "VALID"
            drop_type = parsed.get("type", "UNKNOWN").upper()
            summary = parsed.get("summary", title)
            items = parsed.get("items", "")
            
            if not summary or summary.strip() == "":
                summary = title

            return is_valid, drop_type, summary, items
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return True, "UNKNOWN", title, ""

def evaluate_news_with_ai(title, content):
    if not GEMINI_API_KEY: return "NO", title
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""Analyze this Web/Twitter News post: Title: "{title}" Content: "{content[:1000]}"
    Return ONLY valid JSON.
    {{
        "is_drop": "YES" or "NO",
        "summary": "Your 1 sentence summary here."
    }}"""
    
    data = json.dumps({
        "contents": [{"parts":[{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            ai_text = json.loads(response.read().decode())['candidates'][0]['content']['parts'][0]['text'].strip()
            parsed = json.loads(ai_text)
            return parsed.get("is_drop", "NO").upper(), parsed.get("summary", title)
    except: return "NO", title

def fetch_rss_proxy(url):
    proxy_url = f"https://api.rss2json.com/v1/api.json?rss_url={url}"
    req = urllib.request.Request(proxy_url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode()).get('items', [])
    except: return []

def build_drops():
    drops = []
    for sub in SUBREDDITS:
        items = fetch_rss_proxy(f'https://www.reddit.com/r/{sub}/new.rss')
        for post in items:
            title = post.get('title', '')
            content_raw = post.get('content', '')
            source_link = post.get('link', '') 
            guid = post.get('guid', '') # This is the reddit thread permalink
            
            # 1. SPAM / HAUL BLOCKER
            if is_spam(title, content_raw, source_link):
                print(f"Blocked Junk Keyword: {title}")
                continue
                
            # 2. EXTRACT & VERIFY STORE LINKS
            extracted_links_html = "<div style='margin-top: 12px; padding-top: 10px; border-top: 1px solid #30363d;'><strong style='color:#f0f6fc;'>🛒 Verified Store Links:</strong><ul style='margin-top: 6px; padding-left: 18px;'>"
            link_count = 0
            detected_retailer = "Reddit"
            extracted_image = None
            
            all_urls = re.findall(r'(https?://[^\s)\]"\']+)', content_raw)
            for url in set(all_urls):
                if any(ext in url.lower() for ext in ['.jpg', '.png', '.jpeg', 'i.redd.it', 'imgur.com']):
                    if not extracted_image: extracted_image = url
                    continue 
                
                is_store_link = any(domain in url.lower() for domain in STORE_DOMAINS)
                if not is_store_link:
                    continue
                
                matched_retailer = next((r.capitalize() for r in RETAILERS if r in url.lower()), None)
                if matched_retailer: detected_retailer = matched_retailer
                
                link_text = url.split('?')[0][:45] + "..."
                extracted_links_html += f"<li style='margin-bottom: 6px;'><a href='{url}' target='_blank' style='color: #3498db; text-decoration: none;'>{link_text}</a></li>"
                link_count += 1
                
            if link_count == 0:
                print(f"Trashed (No Verified Store Links): {title}")
                continue
                
            extracted_links_html += "</ul></div>"
            
            # 3. FETCH COMMUNITY COMMENTS VIA RSS PROXY
            comments_text = ""
            if guid and "reddit.com" in guid:
                comment_url = guid + ".rss" if not guid.endswith(".rss") else guid
                comment_feed = fetch_rss_proxy(comment_url)
                # Skip the first item (the main post), grab the top 4 comments
                for c in comment_feed[1:5]:
                    clean_c = re.sub(r'<[^>]+>', ' ', c.get('content', '')).strip()
                    if clean_c: comments_text += f"- {clean_c[:150]}\n"

            # 4. AI GATEKEEPER
            is_valid_drop, drop_type, ai_summary, ai_items = evaluate_drop_with_ai(title, content_raw, comments_text)
            
            if not is_valid_drop:
                print(f"AI Filtered Out: {title}")
                continue

            if detected_retailer == "Reddit":
                title_has_retailer = next((r.capitalize() for r in RETAILERS if r in title.lower()), None)
                if title_has_retailer: detected_retailer = title_has_retailer

            # Compile description
            sub_badge = f"<div style='margin-bottom:8px;'><span style='background:#ff4500; color:#ffffff; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600; display:inline-block;'>r/{sub}</span></div>"
            final_desc = f"{sub_badge}<div style='color:#f0f6fc; margin-bottom:10px; line-height: 1.5; white-space: pre-line;'>{ai_summary}</div>"
            if ai_items: final_desc += f"<div style='white-space: pre-line; color:#a8b2bd; font-family: monospace; margin-bottom:10px;'>{ai_items}</div>"
            final_desc += extracted_links_html

            try:
                raw_date = post.get('pubDate', '')[:25].strip()
                date_obj = datetime.strptime(raw_date, "%Y-%m-%d %H:%M:%S")
                date_str = date_obj.replace(tzinfo=timezone.utc).isoformat()
            except:
                date_str = datetime.now(timezone.utc).isoformat()

            product_image = extracted_image if extracted_image else RETAILER_LOGOS.get(detected_retailer, RETAILER_LOGOS['Reddit'])
            
            drops.append({
                "title": title[:70] + "..." if len(title) > 70 else title,
                "price": "Check Retailer Links",
                "retailer": detected_retailer,
                "subreddit": f"r/{sub}",
                "date": date_str,
                "type": drop_type,
                "image": product_image,
                "source_link": source_link, 
                "desc": final_desc
            })

    if not drops:
        drops.append({
            "title": "Radar Active: Waiting for verified drops...",
            "price": "N/A", "retailer": "DropDrop AI", "subreddit": "System Alert",
            "date": datetime.now(timezone.utc).isoformat(),
            "type": "SYSTEM",
            "image": RETAILER_LOGOS['Reddit'],
            "source_link": "#", "desc": "Monitoring prioritized subreddits for new drops. The AI and Link Verifier is actively blocking spam and haul posts."
        })

    drops.sort(key=lambda x: x['date'], reverse=True)
    return drops

def fetch_google_news(query, source_type):
    news_list = []
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            root = ET.fromstring(response.read())
            for item in root.findall('./channel/item'):
                title = item.find('title').text
                desc = item.find('description').text or ''
                if 'pocket' in title.lower() or 'pocket' in desc.lower(): continue
                
                is_drop, ai_summary = evaluate_news_with_ai(title, desc)
                
                try:
                    raw_date = item.find('pubDate').text[:25].strip()
                    date_obj = datetime.strptime(raw_date, "%a, %d %b %Y %H:%M:%S")
                    iso_date = date_obj.isoformat() + "Z"
                except:
                    iso_date = datetime.now(timezone.utc).isoformat()
                
                news_list.append({
                    "title": title[:75] + "...",
                    "source": source_type,
                    "date": iso_date,
                    "desc": ai_summary,
                    "link": item.find('link').text,
                    "is_drop": is_drop
                })
                if len(news_list) >= 6: break
    except Exception as e:
        print(f"Error fetching {source_type}: {e}")
    
    return news_list

def build_news():
    google_news_query = "Pokemon TCG (restock OR preorder OR drop) -site:twitter.com -site:x.com when:7d"
    x_news_query = "Pokemon TCG (restock OR preorder OR drop) (site:twitter.com OR site:x.com) when:7d"
    
    articles = fetch_google_news(google_news_query, "Google News")
    tweets = fetch_google_news(x_news_query, "X / Twitter")
    
    return {"articles": articles, "tweets": tweets}

output_data = {"drops": build_drops()}
output_data.update(build_news())

with open('data.json', 'w') as f: json.dump(output_data, f, indent=4)
print("Comment-Reading JSON AI successfully generated!")

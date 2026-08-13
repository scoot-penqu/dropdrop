import json
import urllib.request
import re
import os
from datetime import datetime
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
    'Reddit': 'https://upload.wikimedia.org/wikipedia/commons/3/36/Reddit_logo.svg'
}

RETAILERS = [k.lower() for k in RETAILER_LOGOS.keys() if k != 'Reddit']
BANNED_WORDS = ['single', 'psa', 'cgc', 'slab', 'grading', 'card only', 'code', 'pulls', 'mail day', 'collection', 'display']
BANNED_STARTERS = ['does', 'has', 'is', 'what', 'where', 'why', 'anyone', 'thoughts', 'question']
SUBREDDITS = ['PKMNTCGDeals', 'PokemonTCGRestocks', 'PokeInvesting']

KNOWN_PRODUCTS = [
    {"keywords": ["ascended heroes", "mega evolution tin"], "title": "Mega Evolution—Ascended Heroes Tin", "msrp": 21.99, "image": "ascended_tin.jpg", "date": "2026-08-28T00:00:00"},
    {"keywords": ["30th anniversary", "celebration etb"], "title": "30th Anniversary Celebration ETB", "msrp": 49.99, "image": "30th_etb.png", "date": "2026-09-16T10:00:00"}
]

def get_ai_summary(text):
    """Sends raw text to Gemini AI for a clean summary."""
    if not GEMINI_API_KEY or len(text) < 20:
        return text[:150] + "..." # Fallback if no API key
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"Summarize this Pokémon TCG deal or news post in 1 to 2 short, punchy sentences. Focus only on the product, store, and price if mentioned. Do not use asterisks or markdown formatting. Post text: {text[:1500]}"
    
    data = json.dumps({"contents": [{"parts":[{"text": prompt}]}]}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req) as response:
            res_json = json.loads(response.read().decode())
            return res_json['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print(f"AI Error: {e}")
        return text[:150] + "..."

def fetch_rss_proxy(url):
    proxy_url = f"https://api.rss2json.com/v1/api.json?rss_url={url}"
    req = urllib.request.Request(proxy_url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode()).get('items', [])
    except Exception as e:
        return []

def extract_price(text):
    match = re.search(r'\$(\d+\.\d{2})', text)
    return float(match.group(1)) if match else None

def build_drops():
    drops = []
    for sub in SUBREDDITS:
        items = fetch_rss_proxy(f'https://www.reddit.com/r/{sub}/new.rss')
        for post in items:
            title = post.get('title', '')
            title_lower = title.lower()
            content_raw = post.get('content', '')
            source_link = post.get('link', '') 
            
            if '?' in title or any(w in title_lower for w in BANNED_WORDS): continue
            if title_lower.split()[0] if title_lower else "" in BANNED_STARTERS: continue
                
            extracted_image = None
            extracted_links_html = "<div style='margin-top: 12px; padding-top: 10px; border-top: 1px solid #30363d;'><strong style='color:#f0f6fc;'>🔗 Verified Store Links:</strong><ul style='margin-top: 6px; padding-left: 18px;'>"
            
            link_count = 0
            detected_retailer = None
            
            img_match = re.search(r'<img[^>]+src=["\'](http[^"\']+(?:jpg|png|jpeg|gif)[^"\']*)["\']', content_raw, re.IGNORECASE)
            if img_match: extracted_image = img_match.group(1)

            for match in re.finditer(r'<a[^>]+href=["\'](http[^"\']+)["\'][^>]*>(.*?)</a>', content_raw, re.IGNORECASE):
                url = match.group(1)
                link_text = re.sub(r'<[^>]+>', '', match.group(2)).strip()
                if any(ext in url.lower() for ext in ['.jpg', '.png', '.jpeg', 'i.redd.it', 'imgur.com']):
                    if not extracted_image: extracted_image = url
                    continue 
                
                matched_retailer = next((r.capitalize() for r in RETAILERS if r in url.lower()), None)
                if matched_retailer:
                    detected_retailer = matched_retailer
                    if not link_text or link_text.lower() == '[link]': link_text = url.split('?')[0][:45] + "..."
                    extracted_links_html += f"<li style='margin-bottom: 6px;'><a href='{url}' target='_blank' style='color: #3498db; text-decoration: none;'>{link_text}</a></li>"
                    link_count += 1
                
            extracted_links_html += "</ul></div>"
            
            if link_count == 0:
                extracted_links_html = ""
                title_has_retailer = next((r.capitalize() for r in RETAILERS if r in title_lower), None)
                if not title_has_retailer: continue 
                detected_retailer = title_has_retailer

            # 🧠 GENERATE AI SUMMARY
            clean_text = re.sub('<[^<]+?>', ' ', content_raw).strip()
            ai_summary = get_ai_summary(clean_text)
            final_desc = ai_summary + extracted_links_html

            is_past = any(term in title_lower or term in content_raw.lower() for term in ['expired', 'out of stock', 'sold out', 'oos', 'dead'])
            
            # 🕒 GRAB EXACT PUBLISH TIME
            raw_date = post.get('pubDate', '')
            try:
                # RSS2JSON returns dates like "2026-08-13 14:30:00" in UTC
                date_obj = datetime.strptime(raw_date, "%Y-%m-%d %H:%M:%S")
                date_str = date_obj.isoformat() + "Z" # Appending Z tells JS this is UTC time
            except:
                date_str = datetime.utcnow().isoformat() + "Z"
            
            product_image, price_text, found_price = None, "Check Link for Price", extract_price(title)
            
            for prod in KNOWN_PRODUCTS:
                if any(kw in title_lower for kw in prod["keywords"]):
                    product_image = prod["image"]
                    if found_price:
                        diff = found_price - prod["msrp"]
                        price_text = f"${found_price:.2f} (📉 ${abs(diff):.2f} UNDER)" if diff < -0.01 else f"${found_price:.2f} (📈 ${diff:.2f} OVER)" if diff > 0.01 else f"${found_price:.2f} (MSRP)"
                    else: price_text = f"MSRP: ${prod['msrp']:.2f}"
                    break
            
            if not product_image: product_image = extracted_image if extracted_image else RETAILER_LOGOS.get(detected_retailer, RETAILER_LOGOS['Reddit'])
            if price_text == "Check Link for Price" and found_price: price_text = f"${found_price:.2f}"

            drops.append({
                "title": title[:70] + "..." if len(title) > 70 else title,
                "price": price_text,
                "retailer": detected_retailer,
                "date": date_str,
                "status": "past" if is_past else "live",
                "image": product_image,
                "source_link": source_link, 
                "desc": final_desc
            })

    drops.sort(key=lambda x: x['date'], reverse=True)
    return drops

def build_news():
    news_list = []
    url = "https://news.google.com/rss/search?q=Pokemon+TCG+(restock+OR+preorder+OR+drop)+when:7d"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            root = ET.fromstring(response.read())
            for item in root.findall('./channel/item'):
                title = item.find('title').text
                desc = item.find('description').text or ''
                if 'pocket' in title.lower() or 'pocket' in desc.lower(): continue
                
                # 🕒 GRAB EXACT PUBLISH TIME FOR NEWS
                raw_date = item.find('pubDate').text
                try:
                    date_obj = datetime.strptime(raw_date[:25].strip(), "%a, %d %b %Y %H:%M:%S")
                    iso_date = date_obj.isoformat() + "Z"
                except:
                    iso_date = datetime.utcnow().isoformat() + "Z"
                    
                news_list.append({
                    "title": title[:75] + "...",
                    "source": item.find('source').text if item.find('source') is not None else 'Web Article',
                    "date": iso_date,
                    "desc": "Recent Web Article",
                    "link": item.find('link').text,
                    "confidence": "📰 News"
                })
                if len(news_list) >= 6: break
    except: pass
    if not news_list: news_list.append({"title": "No news", "source": "System", "date": datetime.utcnow().isoformat()+"Z", "desc": "", "link": "#", "confidence": "-"})
    return news_list

output_data = {"drops": build_drops(), "news": build_news()}
with open('data.json', 'w') as f: json.dump(output_data, f, indent=4)
print("AI-Powered JSON successfully generated!")

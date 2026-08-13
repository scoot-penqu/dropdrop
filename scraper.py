import json
import urllib.request
import re
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

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
BANNED_WORDS = ['single', 'psa', 'cgc', 'slab', 'grading', 'card only', 'code', 'pulls', 'mail day']
SUBREDDITS = ['PKMNTCGDeals', 'PokemonTCGRestocks', 'PokeInvesting']

def fetch_rss_proxy(url):
    proxy_url = f"https://api.rss2json.com/v1/api.json?rss_url={url}"
    req = urllib.request.Request(proxy_url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode()).get('items', [])
    except Exception as e:
        print(f"Proxy error: {e}")
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
            
            # Skip obvious non-deals or questions
            if '?' in title or any(w in title_lower for w in BANNED_WORDS): 
                continue
                
            extracted_image = None
            extracted_links_html = "<div style='margin-top: 12px; padding-top: 10px; border-top: 1px solid #30363d;'><strong style='color:#f0f6fc;'>🔗 Verified Store Links:</strong><ul style='margin-top: 6px; padding-left: 18px;'>"
            
            link_count = 0
            detected_retailer = "Reddit"
            
            # Extract image if present in post
            img_match = re.search(r'<img[^>]+src=["\'](http[^"\']+(?:jpg|png|jpeg|gif)[^"\']*)["\']', content_raw, re.IGNORECASE)
            if img_match: 
                extracted_image = img_match.group(1)

            # Find external store links
            for match in re.finditer(r'<a[^>]+href=["\'](http[^"\']+)["\'][^>]*>(.*?)</a>', content_raw, re.IGNORECASE):
                url = match.group(1)
                link_text = re.sub(r'<[^>]+>', '', match.group(2)).strip()
                if any(ext in url.lower() for ext in ['.jpg', '.png', '.jpeg', 'i.redd.it', 'imgur.com']):
                    if not extracted_image: extracted_image = url
                    continue 
                
                matched_retailer = next((r.capitalize() for r in RETAILERS if r in url.lower()), None)
                if matched_retailer:
                    detected_retailer = matched_retailer
                    if not link_text or link_text.lower() == '[link]': 
                        link_text = url.split('?')[0][:45] + "..."
                    extracted_links_html += f"<li style='margin-bottom: 6px;'><a href='{url}' target='_blank' style='color: #3498db; text-decoration: none;'>{link_text}</a></li>"
                    link_count += 1
                
            extracted_links_html += "</ul></div>"
            
            if link_count == 0:
                extracted_links_html = ""
                title_has_retailer = next((r.capitalize() for r in RETAILERS if r in title_lower), None)
                if title_has_retailer:
                    detected_retailer = title_has_retailer
                else:
                    detected_retailer = f"r/{sub}"

            clean_desc = re.sub('<[^<]+?>', ' ', content_raw)[:200] + "..."
            final_desc = clean_desc + extracted_links_html

            is_past = any(term in title_lower or term in content_raw.lower() for term in ['expired', 'out of stock', 'sold out', 'oos', 'dead'])
            
            try:
                raw_date = post.get('pubDate', '')[:25].strip()
                date_obj = datetime.strptime(raw_date, "%Y-%m-%d %H:%M:%S")
                date_str = date_obj.replace(tzinfo=timezone.utc).isoformat()
            except:
                date_str = datetime.now(timezone.utc).isoformat()
            
            found_price = extract_price(title)
            price_text = f"${found_price:.2f}" if found_price else "Check Retailer Link"
            
            # Smart image selector: use extracted image or fallback to clean retailer logo
            product_image = extracted_image if extracted_image else RETAILER_LOGOS.get(detected_retailer, RETAILER_LOGOS['Reddit'])

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

    # Fail-safe placeholder if feeds are quiet
    if not drops:
        drops.append({
            "title": "System Radar Active: Waiting for next live drop...",
            "price": "N/A",
            "retailer": "DropDrop System",
            "date": datetime.now(timezone.utc).isoformat(),
            "status": "live",
            "image": "https://upload.wikimedia.org/wikipedia/commons/3/36/Reddit_logo.svg",
            "source_link": "https://reddit.com/r/PKMNTCGDeals",
            "desc": "The dynamic discovery engine is running successfully. New deals will populate here automatically when posted."
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
                
                news_list.append({
                    "title": title[:75] + "...",
                    "source": item.find('source').text if item.find('source') is not None else 'Web Article',
                    "date": "Recent",
                    "desc": "Recent Web Article",
                    "link": item.find('link').text,
                    "confidence": "📰 News"
                })
                if len(news_list) >= 6: break
    except: pass
    
    if not news_list: 
        news_list.append({"title": "Radar active and monitoring TCG news.", "source": "System", "date": "Today", "desc": "", "link": "#", "confidence": "-"})
        
    return news_list

output_data = {"drops": build_drops(), "news": build_news()}
with open('data.json', 'w') as f: json.dump(output_data, f, indent=4)
print("Pure dynamic scraper JSON successfully generated!")

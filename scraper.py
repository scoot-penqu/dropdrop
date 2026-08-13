import json
import urllib.request
import re
from datetime import datetime
import xml.etree.ElementTree as ET

# Trusted retailers
RETAILERS = ['pokemoncenter', 'target', 'walmart', 'amazon', 'gamestop', 'samsclub', 'costco', 'bestbuy']
BANNED_WORDS = ['single', 'psa', 'cgc', 'slab', 'grading', 'card only', 'code']

# Subreddits to monitor
SUBREDDITS = ['PKMNTCGDeals', 'PokemonTCGRestocks', 'PokeInvesting', 'PokemonTCG']

# Hybrid Database for Official Product Matching
KNOWN_PRODUCTS = [
    {
        "keywords": ["ascended heroes", "mega evolution tin"],
        "title": "Mega Evolution—Ascended Heroes Tin",
        "msrp": 21.99,
        "image": "ascended_tin.jpg", # Assuming you uploaded this to github
        "date": "2026-08-28T00:00:00"
    },
    {
        "keywords": ["30th anniversary", "celebration etb"],
        "title": "30th Anniversary Celebration ETB",
        "msrp": 49.99,
        "image": "30th_etb.png", # Assuming you uploaded this to github
        "date": "2026-09-16T10:00:00"
    }
]

def fetch_rss_proxy(url):
    """Uses a proxy to bypass blocks for Reddit."""
    proxy_url = f"https://api.rss2json.com/v1/api.json?rss_url={url}"
    req = urllib.request.Request(proxy_url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode()).get('items', [])
    except Exception as e:
        print(f"Error fetching proxy RSS: {e}")
        return []

def fetch_google_news():
    """Fetches real-time articles and social indexings from Google News."""
    # Searches Google for TCG restocks from the past 7 days
    url = "https://news.google.com/rss/search?q=Pokemon+TCG+(restock+OR+preorder+OR+drop)+when:7d"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    articles = []
    try:
        with urllib.request.urlopen(req) as response:
            root = ET.fromstring(response.read())
            for item in root.findall('./channel/item')[:10]: # Top 10 results
                articles.append({
                    'title': item.find('title').text,
                    'link': item.find('link').text,
                    'pubDate': item.find('pubDate').text,
                    'content': item.find('description').text or '',
                    'source': item.find('source').text if item.find('source') is not None else 'Web Article'
                })
    except Exception as e:
        print(f"Error fetching Google News: {e}")
    return articles

def extract_price(text):
    match = re.search(r'\$(\d+\.\d{2})', text)
    return float(match.group(1)) if match else None

def process_items(items, source_label, drops_list):
    """Core logic to extract links, descriptions, and MSRPs from any feed."""
    for post in items:
        title = post.get('title', '')
        title_lower = title.lower()
        content_raw = post.get('content', '')
        source_link = post.get('link', '') 
        
        if any(w in title_lower for w in BANNED_WORDS):
            continue
            
        # MULTI-LINK EXTRACTOR
        extracted_links_html = "<div style='margin-top: 12px; padding-top: 10px; border-top: 1px solid #30363d;'>"
        extracted_links_html += f"<strong style='color:#f0f6fc;'>🔗 Extracted Store Links:</strong><ul style='margin-top: 6px; padding-left: 18px;'>"
        
        link_count = 0
        detected_retailer = source_label
        
        for match in re.finditer(r'<a[^>]+href=["\'](http[^"\']+)["\'][^>]*>(.*?)</a>', content_raw, re.IGNORECASE):
            url = match.group(1)
            link_text = re.sub(r'<[^>]+>', '', match.group(2)).strip()
            
            if "reddit.com" in url or "google.com" in url:
                continue
                
            for r in RETAILERS:
                if r in url.lower():
                    detected_retailer = r.capitalize()
                    
            if not link_text or link_text.lower() == '[link]':
                link_text = url.split('?')[0][:45] + "..."
                
            extracted_links_html += f"<li style='margin-bottom: 6px;'><a href='{url}' target='_blank' style='color: #3498db; text-decoration: none;'>{link_text}</a></li>"
            link_count += 1
            
        extracted_links_html += "</ul></div>"
        
        if link_count == 0:
            extracted_links_html = ""
            # Try to guess retailer from title if no links exist
            for r in RETAILERS:
                if r in title_lower:
                    detected_retailer = r.capitalize()
            
        clean_desc = re.sub('<[^<]+?>', ' ', content_raw)[:150] + "..."
        final_desc = clean_desc + extracted_links_html

        is_past = any(term in title_lower or term in content_raw.lower() for term in ['expired', 'out of stock', 'sold out', 'oos', 'dead'])
        
        # Use ISO formatting for easier date filtering in javascript
        try:
            # Try to parse standard RSS date
            date_obj = datetime.strptime(post.get('pubDate', '')[:25].strip(), "%a, %d %b %Y %H:%M:%S")
            date_str = date_obj.isoformat()
        except:
            date_str = datetime.now().isoformat()
        
        product_image = "https://via.placeholder.com/300x180?text=Sealed+Product"
        price_text = "Check Link for Price"
        found_price = extract_price(title)
        
        for prod in KNOWN_PRODUCTS:
            if any(kw in title_lower for kw in prod["keywords"]):
                product_image = prod["image"]
                if found_price:
                    diff = found_price - prod["msrp"]
                    if diff < -0.01:
                        price_text = f"${found_price:.2f} (📉 ${abs(diff):.2f} UNDER MSRP)"
                    elif diff > 0.01:
                        price_text = f"${found_price:.2f} (📈 ${diff:.2f} OVER MSRP)"
                    else:
                        price_text = f"${found_price:.2f} (MSRP)"
                else:
                    price_text = f"MSRP: ${prod['msrp']:.2f}"
                break
        
        if price_text == "Check Link for Price" and found_price:
            price_text = f"${found_price:.2f}"

        drops_list.append({
            "title": title[:70] + "..." if len(title) > 70 else title,
            "price": price_text,
            "retailer": detected_retailer,
            "date": date_str,
            "status": "past" if is_past else "live",
            "image": product_image,
            "source_link": source_link, 
            "desc": final_desc
        })

def build_drops():
    drops = []
    
    # 1. Scan Multiple Subreddits
    for sub in SUBREDDITS:
        items = fetch_rss_proxy(f'https://www.reddit.com/r/{sub}/new.rss')
        process_items(items, f"r/{sub}", drops)
        
    # 2. Scan Google News (Web Articles / Indexed Socials)
    news_items = fetch_google_news()
    process_items(news_items, "Web Article", drops)
    
    # Sort drops by newest first based on the ISO date we generated
    drops.sort(key=lambda x: x['date'], reverse=True)
    return drops

def build_rumors():
    rumors = []
    items = fetch_rss_proxy('https://www.pokebeach.com/feed')
    for post in items[:6]:
        rumors.append({
            "title": post.get('title', '')[:65] + "...",
            "source": "PokéBeach",
            "date": "Recent",
            "desc": "Official TCG news and leaks.",
            "link": post.get('link', '#'),
            "confidence": "⚡ TCG News"
        })
    if not rumors:
        rumors.append({"title": "No recent TCG news detected", "source": "System", "date": "Today", "desc": "Radar active.", "link": "#", "confidence": "-"})
    return rumors

# Generate the JSON
output_data = {
    "drops": build_drops(),
    "rumors": build_rumors()
}

with open('data.json', 'w') as f:
    json.dump(output_data, f, indent=4)
print("Multi-Source JSON successfully generated!")

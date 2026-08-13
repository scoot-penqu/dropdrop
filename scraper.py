import json
import urllib.request
import re
from datetime import datetime

# Trusted retailers
RETAILERS = ['pokemoncenter', 'target', 'walmart', 'amazon', 'gamestop', 'samsclub', 'costco', 'bestbuy']
BANNED_WORDS = ['single', 'psa', 'cgc', 'slab', 'grading', 'card only', 'code']

# Hybrid Database for Official Product Matching
KNOWN_PRODUCTS = [
    {
        "keywords": ["ascended heroes", "mega evolution tin"],
        "title": "Mega Evolution—Ascended Heroes Tin",
        "msrp": 21.99,
        "image": "https://tcg.pokemon.com/assets/img/mega-evolution/ascended-heroes-tin.png",
        "date": "2026-08-28T00:00:00"
    },
    {
        "keywords": ["30th anniversary", "celebration etb"],
        "title": "30th Anniversary Celebration ETB",
        "msrp": 49.99,
        "image": "https://images.pokemontcg.io/cel25/logo.png",
        "date": "2026-09-16T10:00:00"
    },
    {
        "keywords": ["delta reign booster", "delta reign bb"],
        "title": "Delta Reign Booster Box",
        "msrp": 161.64,
        "image": "https://images.pokemontcg.io/sv1/logo.png",
        "date": "2026-11-06T00:00:00"
    },
    {
        "keywords": ["shrouded fable etb", "shrouded fable elite"],
        "title": "Shrouded Fable ETB",
        "msrp": 49.99,
        "image": "https://images.pokemontcg.io/sfa/logo.png",
        "date": "2024-08-02T00:00:00"
    }
]

def fetch_rss_proxy(url):
    """Uses a proxy to bypass blocks."""
    proxy_url = f"https://api.rss2json.com/v1/api.json?rss_url={url}"
    req = urllib.request.Request(proxy_url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode()).get('items', [])
    except Exception as e:
        print(f"Error fetching RSS: {e}")
        return []

def extract_price(text):
    """Finds dollar amounts in the reddit title."""
    match = re.search(r'\$(\d+\.\d{2})', text)
    if match:
        return float(match.group(1))
    return None

def build_drops():
    drops = []
    now = datetime.now()
    
    # 1. LOAD UPCOMING CONFIRMED DROPS
    for prod in KNOWN_PRODUCTS:
        release_date = datetime.strptime(prod["date"], "%Y-%m-%dT%H:%M:%S")
        if release_date > now:
            drops.append({
                "title": prod["title"],
                "price": f"${prod['msrp']:.2f} (MSRP)",
                "retailer": "Official Release",
                "date": prod["date"],
                "status": "upcoming",
                "image": prod["image"],
                "link": "https://www.pokemoncenter.com",
                "reddit_link": "",
                "desc": "Official upcoming Pokémon TCG release. Check preferred retailers for pre-orders."
            })

    # 2. DISCOVER DYNAMIC DEALS FROM REDDIT
    items = fetch_rss_proxy('https://www.reddit.com/r/PKMNTCGDeals/new.rss')
    
    for post in items:
        title = post.get('title', '')
        title_lower = title.lower()
        content_raw = post.get('content', '')
        reddit_link = post.get('link', '') 
        
        if any(w in title_lower for w in BANNED_WORDS):
            continue
            
        # Extract the actual retailer link from the Reddit post HTML
        extracted_links = re.findall(r'href=[\'"]?([^\'" >]+)', content_raw)
        deal_link = reddit_link
        detected_retailer = "Reddit Post"
        
        for r in RETAILERS:
            if r in title_lower:
                detected_retailer = r.capitalize()
            for elink in extracted_links:
                if r in elink.lower():
                    detected_retailer = r.capitalize()
                    deal_link = elink
                    break
                    
        is_past = any(term in title_lower or term in content_raw.lower() for term in ['expired', 'out of stock', 'sold out', 'oos', 'dead'])
        date_str = post.get('pubDate', '')[:10] if post.get('pubDate') else "Recent"
        
        # Match with Known Products for Image & Price Comparison
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
            
        clean_desc = re.sub('<[^<]+?>', ' ', content_raw)[:150] + "..."

        drops.append({
            "title": title[:70] + "..." if len(title) > 70 else title,
            "price": price_text,
            "retailer": detected_retailer,
            "date": date_str,
            "status": "past" if is_past else "live",
            "image": product_image,
            "link": deal_link, 
            "reddit_link": reddit_link,
            "desc": clean_desc
        })
        
    return drops

def build_rumors():
    rumors = []
    # PokeBeach feed specifically for TCG news and leaks
    items = fetch_rss_proxy('https://www.pokebeach.com/feed')
    
    for post in items[:6]:
        rumors.append({
            "title": post.get('title', '')[:65] + "...",
            "source": "PokéBeach",
            "date": post.get('pubDate', '')[:10] if post.get('pubDate') else "Recent",
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

print("Hybrid JSON successfully generated!")

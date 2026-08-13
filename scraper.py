import json
import urllib.request
from datetime import datetime

# Retailers to look for
RETAILERS = ['pokemoncenter', 'target', 'walmart', 'amazon', 'gamestop', 'samsclub', 'costco', 'bestbuy']
BANNED_WORDS = ['single', 'psa', 'cgc', 'slab', 'grading', 'card only']

def fetch_reddit_proxy(subreddit):
    """Uses a proxy to completely bypass Reddit's datacenter blocks."""
    # We use rss2json as a free proxy to fetch Reddit's RSS feed safely
    proxy_url = f"https://api.rss2json.com/v1/api.json?rss_url=https://www.reddit.com/r/{subreddit}/new.rss"
    req = urllib.request.Request(proxy_url, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            return data.get('items', [])
    except Exception as e:
        print(f"Error fetching r/{subreddit} via proxy: {e}")
        return []

def build_drops():
    drops = []
    items = fetch_reddit_proxy('PKMNTCGDeals')
    
    for post in items:
        title = post.get('title', '')
        title_lower = title.lower()
        content = post.get('content', '').lower()
        link = post.get('link', '')
        
        # 1. Skip banned keywords
        if any(w in title_lower for w in BANNED_WORDS):
            continue
            
        # 2. Identify retailer
        detected_retailer = None
        for r in RETAILERS:
            if r in title_lower or r in link.lower() or r in content:
                detected_retailer = r
                break
                
        if not detected_retailer:
            continue
            
        # 3. Check for expired/out-of-stock indicators
        is_past = any(term in title_lower or term in content for term in ['expired', 'out of stock', 'sold out', 'oos'])
        
        # Clean up date format
        date_str = post.get('pubDate', '')[:10] if post.get('pubDate') else "Recent"
        
        drops.append({
            "title": title[:70] + "..." if len(title) > 70 else title,
            "price": "Check Retailer Link",
            "retailer": detected_retailer.capitalize(),
            "date": date_str,
            "type": "online",
            "status": "past" if is_past else "live",
            "image": "https://via.placeholder.com/300x180?text=Sealed+Product",
            "link": link
        })
        
    return drops

def build_rumors():
    rumors = []
    items = fetch_reddit_proxy('PokeLeaks')
    
    for post in items[:5]:
        rumors.append({
            "title": post.get('title', '')[:65] + "...",
            "source": "r/PokeLeaks",
            "date": post.get('pubDate', '')[:10] if post.get('pubDate') else "Recent",
            "desc": "Community leak report. Click post link on feed for details.",
            "confidence": "👀 Unconfirmed"
        })
        
    if not rumors:
        rumors.append({
            "title": "No recent leaks detected",
            "source": "System",
            "date": "Today",
            "desc": "Radar active and waiting for new reports.",
            "confidence": "-"
        })
        
    return rumors

# Build payload
output_data = {
    "drops": build_drops(),
    "rumors": build_rumors()
}

# Write out JSON file
with open('data.json', 'w') as f:
    json.dump(output_data, f, indent=4)

print(f"data.json successfully generated with {len(output_data['drops'])} drops and {len(output_data['rumors'])} rumors!")

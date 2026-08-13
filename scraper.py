import json
import urllib.request
from datetime import datetime

# Trusted retailers only
ALLOWED_DOMAINS = ['pokemoncenter.com', 'target.com', 'walmart.com', 'amazon.com', 'gamestop.com']
# Filter out singles, grading, and non-sealed items
BANNED_WORDS = ['single', 'psa', 'cgc', 'slab', 'grading', 'card only']

def fetch_reddit(subreddit, limit=25):
    """Fetches data directly from Reddit API."""
    url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
    # Custom User-Agent prevents Reddit from blocking the bot
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) PokeDrop/1.0'})
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())['data']['children']
    except Exception as e:
        print(f"Error fetching {subreddit}: {e}")
        return []

def build_drops():
    all_drops = []
    posts = fetch_reddit('PKMNTCGDeals', 50) # Scan last 50 deals
    
    for post in posts:
        data = post['data']
        title = data.get('title', '')
        url = data.get('url', '')
        domain = data.get('domain', '').lower()
        flair = data.get('link_flair_text', '') or ''
        
        # 1. Check if it's a trusted retailer
        if not any(d in domain for d in ALLOWED_DOMAINS):
            continue
            
        # 2. Check if it's a sealed product (no banned words)
        if any(w in title.lower() for w in BANNED_WORDS):
            continue
            
        # 3. Check if the deal is expired/past
        is_past = 'expired' in flair.lower() or 'out of stock' in flair.lower()
        
        # 4. Handle images (fallback to placeholder if no thumbnail)
        thumbnail = data.get('thumbnail', '')
        if not thumbnail.startswith('http'):
            thumbnail = "https://via.placeholder.com/300x180?text=Sealed+Product"
            
        all_drops.append({
            "title": title[:65] + "..." if len(title) > 65 else title,
            "price": "Check Retailer Link",
            "retailer": domain,
            "date": datetime.fromtimestamp(data['created_utc']).isoformat(),
            "type": "online",
            "status": "past" if is_past else "live",
            "image": thumbnail,
            "link": url
        })
        
    return all_drops

def build_rumors():
    rumors = []
    posts = fetch_reddit('PokeLeaks', 5)
    
    for post in posts:
        data = post['data']
        rumors.append({
            "title": data.get('title', '')[:60] + "...",
            "source": "r/PokeLeaks",
            "date": "Recent",
            "desc": "Check community feed for full leak details.",
            "confidence": "👀 Unconfirmed"
        })
        
    if not rumors:
        rumors.append({"title": "No recent rumors found.", "source": "System", "date": "Today", "desc": "Radar is quiet.", "confidence": "-"})
        
    return rumors

# Generate the JSON
data = {
    "drops": build_drops(),
    "rumors": build_rumors()
}

with open('data.json', 'w') as f:
    json.dump(data, f, indent=4)

print("data.json successfully updated via Reddit Discovery Engine!")

import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
import re

# Retailers to look for
RETAILERS = ['pokemoncenter', 'target', 'walmart', 'amazon', 'gamestop', 'samsclub', 'costco', 'bestbuy']
BANNED_WORDS = ['single', 'psa', 'cgc', 'slab', 'grading', 'card only']

def fetch_reddit_rss(subreddit):
    """Fetches posts using Reddit's RSS feed (bypasses datacenter JSON blocks)."""
    url = f"https://www.reddit.com/r/{subreddit}/new.rss?limit=25"
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}
    )
    
    entries = []
    try:
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            
            # Parse Atom XML feed namespace
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            for entry in root.findall('atom:entry', ns):
                title = entry.find('atom:title', ns).text if entry.find('atom:title', ns) is not None else ''
                link_elem = entry.find('atom:link', ns)
                link = link_elem.attrib['href'] if link_elem is not None else ''
                published = entry.find('atom:published', ns).text if entry.find('atom:published', ns) is not None else ''
                
                # Extract external links inside the post content HTML if available
                content_elem = entry.find('atom:content', ns)
                content_html = content_elem.text if content_elem is not None else ''
                
                entries.append({
                    'title': title,
                    'link': link,
                    'published': published,
                    'content': content_html
                })
        print(f"Successfully fetched {len(entries)} items from r/{subreddit}")
    except Exception as e:
        print(f"Error fetching r/{subreddit} RSS: {e}")
        
    return entries

def build_drops():
    drops = []
    raw_posts = fetch_reddit_rss('PKMNTCGDeals')
    
    for post in raw_posts:
        title = post['title']
        title_lower = title.lower()
        content = post['content'].lower()
        link = post['link']
        
        # 1. Skip banned keywords (singles, slabs, etc.)
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
        date_str = post['published'][:10] if post['published'] else "Recent"
        
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
    raw_posts = fetch_reddit_rss('PokeLeaks')
    
    for post in raw_posts[:5]:
        rumors.append({
            "title": post['title'][:65] + "..." if len(post['title']) > 65 else post['title'],
            "source": "r/PokeLeaks",
            "date": post['published'][:10] if post['published'] else "Recent",
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

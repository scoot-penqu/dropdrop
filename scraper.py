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
    'Reddit': 'https://upload.wikimedia.org/wikipedia/commons/3/36/Reddit_logo.svg'
}
RETAILERS = [k.lower() for k in RETAILER_LOGOS.keys() if k != 'Reddit']
SUBREDDITS = ['PKMNTCGDeals', 'PokemonRestocks', 'PokemonDropNotify', 'pokemonrestockr', 'PokemonTCGRestocks']

def evaluate_drop_with_ai(title, content):
    if not GEMINI_API_KEY:
        return True, "UNKNOWN", f"Summary: {title}", ""
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"""
    Analyze this Pokémon TCG Reddit post.
    Title: "{title}"
    Content: "{content[:1500]}"

    Task 1: Is this a legitimate product drop, restock, or preorder alert? (REJECT and reply INVALID if it's speculation, questions, or collection showcases).
    Task 2: Is it ONLINE or IN-STORE?
    Task 3: Write a 1-sentence summary of the drop.
    Task 4: List the specific products and prices mentioned as clean bullet points.

    Format EXACTLY like this:
    [STATUS]: VALID or INVALID
    [TYPE]: ONLINE or IN-STORE or UNKNOWN
    [SUMMARY]: (Your summary here)
    [ITEMS]:
    - Item 1 ($Price)
    """
    data = json.dumps({"contents": [{"parts":[{"text": prompt}]}]}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req) as response:
            ai_text = json.loads(response.read().decode())['candidates'][0]['content']['parts'][0]['text'].strip()
            is_valid = "INVALID" not in ai_text.upper()
            drop_type = "UNKNOWN"
            summary, items = "", ""
            
            lines = ai_text.split('\n')
            for i, line in enumerate(lines):
                if "[TYPE]:" in line: drop_type = line.replace("[TYPE]:", "").strip()
                elif "[SUMMARY]:" in line: summary = line.replace("[SUMMARY]:", "").strip()
                elif "[ITEMS]:" in line: items = "\n".join(lines[i+1:]).strip()

            return is_valid, drop_type, summary, items
    except:
        return True, "UNKNOWN", title, ""

def evaluate_news_with_ai(title, content):
    if not GEMINI_API_KEY: return "NO", title
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"""Analyze this Web/Twitter News post: Title: "{title}" Content: "{content[:1000]}"
    Task 1: Is this announcing a specific product restock or drop? (YES or NO)
    Task 2: Summarize it in 1 short sentence.
    Format EXACTLY:
    [IS_DROP]: YES or NO
    [SUMMARY]: Summary here"""
    try:
        data = json.dumps({"contents": [{"parts":[{"text": prompt}]}]}).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response:
            ai_text = json.loads(response.read().decode())['candidates'][0]['content']['parts'][0]['text'].strip()
            is_drop = "YES" if "[IS_DROP]: YES" in ai_text.upper() else "NO"
            summary = [l.replace("[SUMMARY]:", "").strip() for l in ai_text.split('\n') if "[SUMMARY]:" in l]
            return is_drop, summary[0] if summary else title
    except: return "NO", title

def fetch_rss_proxy(url):
    proxy_url = f"https://api.rss2json.com/v1/api.json?rss_url={url}"
    req = urllib.request.Request(proxy_url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode()).get('items', [])
    except:
        return []

def build_drops():
    drops = []
    for sub in SUBREDDITS:
        items = fetch_rss_proxy(f'https://www.reddit.com/r/{sub}/new.rss')
        for post in items:
            title = post.get('title', '')
            content_raw = post.get('content', '')
            source_link = post.get('link', '') 
            full_text = f"{content_raw} \n Links: {source_link}"
            
            is_valid_drop, drop_type, ai_summary, ai_items = evaluate_drop_with_ai(title, full_text)
            if not is_valid_drop: continue
                
            extracted_links_html = "<div style='margin-top: 12px; padding-top: 10px; border-top: 1px solid #30363d;'><strong style='color:#f0f6fc;'>🔗 Extracted Links:</strong><ul style='margin-top: 6px; padding-left: 18px;'>"
            link_count = 0
            detected_retailer = "Reddit"
            extracted_image = None
            
            all_urls = re.findall(r'(https?://[^\s)\]"\']+)', content_raw)
            for url in set(all_urls):
                if any(ext in url.lower() for ext in ['.jpg', '.png', '.jpeg', 'i.redd.it', 'imgur.com']):
                    if not extracted_image: extracted_image = url
                    continue 
                
                matched_retailer = next((r.capitalize() for r in RETAILERS if r in url.lower()), None)
                if matched_retailer: detected_retailer = matched_retailer
                
                link_text = url.split('?')[0][:45] + "..."
                extracted_links_html += f"<li style='margin-bottom: 6px;'><a href='{url}' target='_blank' style='color: #3498db; text-decoration: none;'>{link_text}</a></li>"
                link_count += 1
                
            extracted_links_html += "</ul></div>"
            if link_count == 0: extracted_links_html = ""
            
            if detected_retailer == "Reddit":
                title_has_retailer = next((r.capitalize() for r in RETAILERS if r in title.lower()), None)
                if title_has_retailer: detected_retailer = title_has_retailer

            final_desc = f"<div style='color:#f0f6fc; margin-bottom:10px;'>{ai_summary}</div>"
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
                "date": date_str,
                "type": drop_type,
                "image": product_image,
                "source_link": source_link, 
                "desc": final_desc
            })

    if not drops:
        drops.append({
            "title": "Radar Active: Waiting for verified drops...",
            "price": "N/A", "retailer": "DropDrop AI",
            "date": datetime.now(timezone.utc).isoformat(),
            "type": "SYSTEM",
            "image": RETAILER_LOGOS['Reddit'],
            "source_link": "#", "desc": "Monitoring prioritized subreddits for new drops."
        })

    # Sort dynamically from newest to oldest
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
    # Strict separation: Articles vs X
    google_news_query = "Pokemon TCG (restock OR preorder OR drop) -site:twitter.com -site:x.com when:7d"
    x_news_query = "Pokemon TCG (restock OR preorder OR drop) (site:twitter.com OR site:x.com) when:7d"
    
    articles = fetch_google_news(google_news_query, "Google News")
    tweets = fetch_google_news(x_news_query, "X / Twitter")
    
    return {"articles": articles, "tweets": tweets}

output_data = {"drops": build_drops()}
output_data.update(build_news())

with open('data.json', 'w') as f: json.dump(output_data, f, indent=4)
print("3-Column Sorted JSON successfully generated!")

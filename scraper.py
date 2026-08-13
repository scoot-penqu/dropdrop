import json
import urllib.request
import re
import os
import html
import time
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

# Upgraded Subreddit List
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

    Format EXACTLY like this (do not use markdown asterisks):
    [STATUS]: VALID or INVALID
    [TYPE]: ONLINE or IN-STORE or UNKNOWN
    [SUMMARY]: (Your summary here)
    [ITEMS]:
    - Item 1 ($Price)
    - Item 2 ($Price)
    """
    data = json.dumps({"contents": [{"parts":[{"text": prompt}]}]}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req) as response:
            ai_text = json.loads(response.read().decode())['candidates'][0]['content']['parts'][0]['text'].strip()
            
            is_valid = "INVALID" not in ai_text.upper()
            drop_type = "UNKNOWN"
            summary, items = "", ""
            
            # Parse AI response
            lines = ai_text.split('\n')
            for i, line in enumerate(lines):
                if "[TYPE]:" in line: drop_type = line.replace("[TYPE]:", "").strip()
                elif "[SUMMARY]:" in line: summary = line.replace("[SUMMARY]:", "").strip()
                elif "[ITEMS]:" in line: items = "\n".join(lines[i+1:]).strip()

            return is_valid, drop_type, summary, items
    except Exception as e:
        print(f"AI Error: {e}")
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

def fetch_reddit_json(sub):
    """Pulls directly from Reddit API to get exact timestamps, upvotes, and comments. Sorts by Newest."""
    url = f"https://www.reddit.com/r/{sub}/new.json?limit=10"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) DropDrop/2.0'})
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode()).get('data', {}).get('children', [])
    except Exception as e:
        print(f"Reddit API error for {sub}: {e}")
        return []

def build_drops():
    drops = []
    
    for sub in SUBREDDITS:
        posts = fetch_reddit_json(sub)
        time.sleep(1) # Prevent Reddit rate limiting
        
        for child in posts:
            post = child.get('data', {})
            title = post.get('title', '')
            content_raw = post.get('selftext', '')
            reddit_url = f"https://www.reddit.com{post.get('permalink', '')}"
            external_url = post.get('url', '')
            
            # Use raw content + URL for the AI to read
            full_text = f"{content_raw} \n Links: {external_url}"
            
            is_valid_drop, drop_type, ai_summary, ai_items = evaluate_drop_with_ai(title, full_text)
            
            if not is_valid_drop: continue
                
            extracted_links_html = "<div style='margin-top: 12px; padding-top: 10px; border-top: 1px solid #30363d;'><strong style='color:#f0f6fc;'>🔗 Extracted Links:</strong><ul style='margin-top: 6px; padding-left: 18px;'>"
            
            link_count = 0
            detected_retailer = "Reddit"
            extracted_image = None
            
            # Find URLs in the post
            all_urls = re.findall(r'(https?://[^\s)\]]+)', full_text)
            for url in set(all_urls):
                url = url.strip(')"\'')
                if any(ext in url.lower() for ext in ['.jpg', '.png', '.jpeg', 'i.redd.it', 'imgur.com']):
                    if not extracted_image: extracted_image = url
                    continue 
                
                matched_retailer = next((r.capitalize() for r in RETAILERS if r in url.lower()), None)
                if matched_retailer:
                    detected_retailer = matched_retailer
                
                link_text = url.split('?')[0][:45] + "..."
                extracted_links_html += f"<li style='margin-bottom: 6px;'><a href='{url}' target='_blank' style='color: #3498db; text-decoration: none;'>{link_text}</a></li>"
                link_count += 1
                
            extracted_links_html += "</ul></div>"
            if link_count == 0: extracted_links_html = ""
            
            if detected_retailer == "Reddit":
                title_has_retailer = next((r.capitalize() for r in RETAILERS if r in title.lower()), None)
                if title_has_retailer: detected_retailer = title_has_retailer

            # Format the AI output for the website
            final_desc = f"<div style='color:#f0f6fc; margin-bottom:10px;'>{ai_summary}</div>"
            if ai_items: final_desc += f"<div style='white-space: pre-line; color:#a8b2bd; font-family: monospace; margin-bottom:10px;'>{ai_items}</div>"
            final_desc += extracted_links_html

            # Exact timestamps from Reddit
            created_utc = post.get('created_utc', 0)
            date_str = datetime.fromtimestamp(created_utc, timezone.utc).isoformat() if created_utc else datetime.now(timezone.utc).isoformat()

            product_image = extracted_image if extracted_image else RETAILER_LOGOS.get(detected_retailer, RETAILER_LOGOS['Reddit'])
            
            # Extract stats
            score = post.get('score', 0)
            comments = post.get('num_comments', 0)

            drops.append({
                "title": title[:70] + "..." if len(title) > 70 else title,
                "price": "Check Retailer Links",
                "retailer": detected_retailer,
                "date": date_str,
                "type": drop_type,
                "score": score,
                "comments": comments,
                "image": product_image,
                "source_link": reddit_url, 
                "desc": final_desc
            })

    if not drops:
        drops.append({
            "title": "Radar Active: Waiting for verified drops...",
            "price": "N/A", "retailer": "DropDrop AI",
            "date": datetime.now(timezone.utc).isoformat(),
            "type": "SYSTEM", "score": 0, "comments": 0,
            "image": RETAILER_LOGOS['Reddit'],
            "source_link": "#", "desc": "Monitoring prioritized subreddits for new drops."
        })

    drops.sort(key=lambda x: x['date'], reverse=True)
    return drops

def build_news():
    news_list = []
    # Added X/Twitter keywords to the Google News search
    url = "https://news.google.com/rss/search?q=Pokemon+TCG+(restock+OR+preorder+OR+drop)+(site:twitter.com+OR+site:x.com+OR+news)+when:7d"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            root = ET.fromstring(response.read())
            for item in root.findall('./channel/item'):
                title = item.find('title').text
                desc = item.find('description').text or ''
                if 'pocket' in title.lower() or 'pocket' in desc.lower(): continue
                
                is_drop, ai_summary = evaluate_news_with_ai(title, desc)
                
                news_list.append({
                    "title": title[:75] + "...",
                    "source": item.find('source').text if item.find('source') is not None else 'Web/Twitter Article',
                    "date": "Recent",
                    "desc": ai_summary,
                    "link": item.find('link').text,
                    "is_drop": is_drop
                })
                if len(news_list) >= 6: break
    except: pass
    
    if not news_list: 
        news_list.append({"title": "Radar active and monitoring TCG news.", "source": "System", "date": "Today", "desc": "No recent drops detected.", "link": "#", "is_drop": "NO"})
        
    return news_list

output_data = {"drops": build_drops(), "news": build_news()}
with open('data.json', 'w') as f: json.dump(output_data, f, indent=4)
print("Ultra-AI JSON successfully generated!")

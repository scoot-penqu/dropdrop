import json
import urllib.request
import xml.etree.ElementTree as ET

def fetch_pokebeach_rss():
    """Fetches the latest news & leak items from PokéBeach RSS feed."""
    url = "https://www.pokebeach.com/feed"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    rumors = []
    try:
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            
            for item in root.findall('./channel/item')[:5]: # Take top 5 latest
                title = item.find('title').text
                link = item.find('link').text
                rumors.append({
                    "title": title,
                    "source": "PokéBeach RSS Feed",
                    "date": "Recent News",
                    "desc": f"Latest update from PokéBeach. Check full article at: {link}",
                    "confidence": "⚡ High Likelihood (News Source)"
                })
    except Exception as e:
        print(f"Error fetching RSS: {e}")
    
    return rumors

# Build the JSON file structure
data = {
    "drops": [
        {
            "title": "Mega Evolution—Ascended Heroes Tin",
            "price": "$21.99 (MSRP)",
            "retailer": "Pokémon Center / Target / Walmart",
            "date": "2026-08-28T00:00:00",
            "type": "online & in-store",
            "status": "confirmed",
            "image": "https://images.pokemontcg.io/me1/1_hires.png",
            "link": "https://www.pokemon.com/us/pokemon-tcg"
        }
    ],
    "rumors": fetch_pokebeach_rss()
}

# Save output to data.json
with open('data.json', 'w') as f:
    json.dump(data, f, indent=4)

print("data.json successfully updated!")

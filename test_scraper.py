import requests
from bs4 import BeautifulSoup

# Test script to inspect the HTML structure
url = "https://www.jemepropose.com/annonces/?offer_type=2&provider_type=1"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.content, 'html.parser')

# Find first job card
job_cards = soup.find_all('div', class_='card offer-card animate fadeLeft link', limit=2)

print(f"Found {len(job_cards)} cards\n")
print("=" * 80)

for idx, card in enumerate(job_cards, 1):
    print(f"\nCard #{idx} HTML structure:")
    print(card.prettify()[:2000])  # Print first 2000 chars
    print("\n" + "=" * 80)

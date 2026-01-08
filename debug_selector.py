import requests
from bs4 import BeautifulSoup

# Test script to count job cards
url = "https://www.jemepropose.com/annonces/?offer_type=2&provider_type=1"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.content, 'html.parser')

# Try different selectors
print("Testing different selectors:\n")

# Test 1: Original selector
cards1 = soup.find_all('div', class_='card offer-card animate fadeLeft link')
print(f"1. 'card offer-card animate fadeLeft link': {len(cards1)} cards")

# Test 2: Just 'offer-card'
cards2 = soup.find_all('div', class_='offer-card')
print(f"2. 'offer-card': {len(cards2)} cards")

# Test 3: Contains 'offer-card'
cards3 = soup.find_all('div', class_=lambda x: x and 'offer-card' in x)
print(f"3. Contains 'offer-card': {len(cards3)} cards")

# Test 4: Check for data-url attribute
cards4 = soup.find_all('div', attrs={'data-url': True})
print(f"4. Has 'data-url' attribute: {len(cards4)} cards")

# Show first few class names
print("\n\nFirst 5 card class names:")
for idx, card in enumerate(cards3[:5], 1):
    print(f"{idx}. {card.get('class')}")

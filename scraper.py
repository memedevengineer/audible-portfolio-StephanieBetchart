import json
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

BASE_URL = "https://www.audible.com/search?searchNarrator="

def scrape_narrator(narrator):
    url = BASE_URL + quote_plus(narrator)
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(url, headers=headers, timeout=20)
    soup = BeautifulSoup(response.text, "html.parser")

    books = []

    for item in soup.select("li.productListItem"):
        title_tag = item.select_one("h3 a")
        author_tag = item.select_one(".authorLabel a")
        image_tag = item.select_one("img")
        narrator_tag = item.select_one(".narratorLabel")

        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        link = "https://www.audible.com" + title_tag.get("href", "")
        author = author_tag.get_text(strip=True) if author_tag else ""
        cover = image_tag.get("src", "") if image_tag else ""

        books.append({
            "title": title,
            "author": author,
            "narrator_searched": narrator,
            "cover": cover,
            "audible_url": link
        })

    return books

def main():
    with open("narrators.txt", "r", encoding="utf-8") as f:
        narrators = [line.strip() for line in f if line.strip()]

    all_books = []

    for narrator in narrators:
        print(f"Scraping {narrator}...")
        all_books.extend(scrape_narrator(narrator))
        time.sleep(2)

    with open("books.json", "w", encoding="utf-8") as f:
        json.dump(all_books, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()

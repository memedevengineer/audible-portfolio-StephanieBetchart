import json
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from datetime import datetime, timezone

BASE_URL = "https://www.audible.com/search?searchNarrator="

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9"
}

def clean_text(text):
    return re.sub(r"\s+", " ", text).strip() if text else ""

def get_review_count(text):
    numbers = re.findall(r"[\d,]+", text or "")
    if not numbers:
        return 0
    try:
        return int(numbers[-1].replace(",", ""))
    except:
        return 0

def make_audible_narrator_link(name):
    return BASE_URL + quote_plus(name)

def scrape_narrator(narrator):
    url = BASE_URL + quote_plus(narrator)
    print(f"Scraping: {url}")

    response = requests.get(url, headers=HEADERS, timeout=30)
    soup = BeautifulSoup(response.text, "html.parser")

    books = []

    for item in soup.select("li.productListItem"):
        title_tag = item.select_one("h3 a")
        if not title_tag:
            continue

        title = clean_text(title_tag.get_text())
        link = title_tag.get("href", "")
        if link.startswith("/"):
            link = "https://www.audible.com" + link

        author_tag = item.select_one(".authorLabel a")
        author = clean_text(author_tag.get_text()) if author_tag else ""

        image_tag = item.select_one("img")
        cover = image_tag.get("src", "") if image_tag else ""

        rating_tag = item.select_one(".ratingsLabel")
        rating_text = clean_text(rating_tag.get_text(" ", strip=True)) if rating_tag else ""
        reviews = get_review_count(rating_text)

        release_tag = item.select_one(".releaseDateLabel")
        release_date = clean_text(release_tag.get_text(" ", strip=True)).replace("Release date:", "").strip() if release_tag else ""

        narrator_links = item.select(".narratorLabel a")
        co_narrators = []

        for n in narrator_links:
            name = clean_text(n.get_text())
            if name:
                co_narrators.append({
                    "name": name,
                    "audible_list": make_audible_narrator_link(name)
                })

        books.append({
            "title": title,
            "author": author,
            "cover": cover,
            "audible_url": link,
            "reviews": reviews,
            "rating_text": rating_text,
            "release_date": release_date,
            "searched_narrator": narrator,
            "co_narrators": co_narrators
        })

    return books

def main():
    with open("narrators.txt", "r", encoding="utf-8") as f:
        narrators = [line.strip() for line in f if line.strip()]

    all_books = []

    for narrator in narrators:
        all_books.extend(scrape_narrator(narrator))
        time.sleep(3)

    unique = {}
    for book in all_books:
        unique[book["audible_url"]] = book

    final_books = list(unique.values())
    final_books.sort(key=lambda x: x.get("reviews", 0), reverse=True)

    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_books": len(final_books),
        "books": final_books
    }

    with open("books.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(final_books)} books.")

if __name__ == "__main__":
    main()

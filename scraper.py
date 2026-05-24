import json
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
from datetime import datetime, timezone

BASE_URL = "https://www.audible.com/search?searchNarrator="
MANUAL_JSON = "manual_books.json"

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
    print(f"Scraping narrator: {url}")

    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

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
        release_date = ""
        if release_tag:
            release_date = clean_text(
                release_tag.get_text(" ", strip=True)
            ).replace("Release date:", "").strip()

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
            "credit_note": "",
            "manual": False,
            "co_narrators": co_narrators
        })

    return books

def load_manual_books():
    try:
        with open(MANUAL_JSON, "r", encoding="utf-8") as f:
            manual_books = json.load(f)

        print(f"Loaded {len(manual_books)} manual books.")
        return manual_books

    except FileNotFoundError:
        print("No manual_books.json found.")
        return []

    except json.JSONDecodeError:
        print("manual_books.json is not valid JSON.")
        return []

def main():
    with open("narrators.txt", "r", encoding="utf-8") as f:
        narrators = [line.strip() for line in f if line.strip()]

    all_books = []

    for narrator in narrators:
        try:
            all_books.extend(scrape_narrator(narrator))
        except Exception as e:
            print(f"Failed to scrape narrator: {narrator}")
            print(e)

        time.sleep(3)

    manual_books = load_manual_books()
    all_books.extend(manual_books)

    unique = {}

    for book in all_books:
        url = book.get("audible_url", "")

        if not url:
            continue

        unique[url] = book

    final_books = list(unique.values())

    final_books.sort(key=lambda x: x.get("reviews", 0), reverse=True)

    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_books": len(final_books),
        "books": final_books
    }

    with open("books.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(final_books)} total books.")

if __name__ == "__main__":
    main()

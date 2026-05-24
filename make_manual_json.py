import csv
import json
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

GOOGLE_SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRJzRuhnz7APifj2wBeBYoja8RCmOghvZJpGsFvU4l6wu4O1zrCjOCHdA06r4ndBO4ULhsH-qhspBRo/pub?output=csv"

OUTPUT_JSON = "manual_books.json"

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

def make_narrator_link(name):
    return "https://www.audible.com/search?searchNarrator=" + quote_plus(name)

def read_google_sheet_rows():
    response = requests.get(GOOGLE_SHEET_CSV_URL, timeout=30)
    response.raise_for_status()

    decoded = response.content.decode("utf-8").splitlines()
    reader = csv.DictReader(decoded)

    return list(reader)

def scrape_book_page(audible_url, narrator_name, credit_note):
    response = requests.get(audible_url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    title_tag = soup.select_one("h1")
    title = clean_text(title_tag.get_text()) if title_tag else ""

    author = ""
    author_tag = soup.select_one("li.authorLabel a, .authorLabel a")
    if author_tag:
        author = clean_text(author_tag.get_text())

    cover = ""
    image_tag = soup.select_one("img.bc-pub-block")
    if image_tag:
        cover = image_tag.get("src", "")

    release_date = ""
    release_text = soup.find(string=re.compile("Release date", re.I))
    if release_text:
        release_date = clean_text(str(release_text)).replace("Release date:", "").strip()

    rating_text = ""
    rating_tag = soup.select_one(".ratingsLabel")
    if rating_tag:
        rating_text = clean_text(rating_tag.get_text(" ", strip=True))

    reviews = get_review_count(rating_text)

    return {
        "title": title,
        "author": author,
        "cover": cover,
        "audible_url": audible_url,
        "reviews": reviews,
        "rating_text": rating_text,
        "release_date": release_date,
        "searched_narrator": narrator_name,
        "credit_note": credit_note,
        "manual": True,
        "co_narrators": [
            {
                "name": narrator_name,
                "audible_list": make_narrator_link(narrator_name)
            }
        ]
    }

def main():
    rows = read_google_sheet_rows()
    manual_books = []

    for row in rows:
        audible_url = clean_text(row.get("audible_url", ""))
        narrator_name = clean_text(row.get("narrator_name", ""))
        credit_note = clean_text(row.get("credit_note", "Manual credit"))

        if not audible_url or not narrator_name:
            continue

        print(f"Scraping manual book: {audible_url}")

        try:
            book = scrape_book_page(audible_url, narrator_name, credit_note)
            manual_books.append(book)
        except Exception as e:
            print(f"Failed: {audible_url}")
            print(e)

        time.sleep(2)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(manual_books, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(manual_books)} manual books.")

if __name__ == "__main__":
    main()

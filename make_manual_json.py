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

def make_narrator_link(name):
    return "https://www.audible.com/search?searchNarrator=" + quote_plus(name)

def read_google_sheet_rows():
    response = requests.get(GOOGLE_SHEET_CSV_URL, timeout=30)
    response.raise_for_status()
    return list(csv.DictReader(response.text.splitlines()))

def get_book_asin(audible_url):
    match = re.search(r"/([A-Z0-9]{10})(?:[/?]|$)", audible_url)
    return match.group(1) if match else ""

def make_cover_from_asin(asin):
    if not asin:
        return ""

    # Direct Amazon/Audible cover image pattern
    return f"https://m.media-amazon.com/images/P/{asin}.01._SL500_.jpg"

def extract_between(text, start, end):
    pattern = re.escape(start) + r"\s*(.*?)\s*" + re.escape(end)
    match = re.search(pattern, text, re.I)
    return clean_text(match.group(1)) if match else ""

def scrape_book_page(audible_url, narrator_name, credit_note):
    response = requests.get(audible_url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    page_text = clean_text(soup.get_text(" "))

    asin = get_book_asin(audible_url)

    title_tag = soup.select_one("h1")
    title = clean_text(title_tag.get_text()) if title_tag else ""

    if not title:
        og_title = soup.select_one('meta[property="og:title"]')
        title = clean_text(og_title.get("content", "")) if og_title else ""

    author = extract_between(page_text, "By:", "Narrated by:")
    release_date = extract_between(page_text, "Release date:", "Language:")

    rating_text = ""
    reviews = 0

    rating_match = re.search(
        r"([\d.]+)\s*out of 5 stars.*?([\d,]+)\s*ratings?",
        page_text,
        re.I
    )

    if rating_match:
        rating_text = f"{rating_match.group(1)} out of 5 stars {rating_match.group(2)} ratings"
        reviews = int(rating_match.group(2).replace(",", ""))

    cover = make_cover_from_asin(asin)

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
        credit_note = clean_text(row.get("credit_note", "Uncredited on Audible"))

        if not audible_url or not narrator_name:
            continue

        print(f"Scraping manual book: {audible_url}")

        try:
            manual_books.append(
                scrape_book_page(audible_url, narrator_name, credit_note)
            )
        except Exception as e:
            print(f"Failed manual book: {audible_url}")
            print(e)

        time.sleep(2)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(manual_books, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(manual_books)} manual books.")

if __name__ == "__main__":
    main()

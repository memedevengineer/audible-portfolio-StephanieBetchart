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

def get_meta_content(soup, selector):
    tag = soup.select_one(selector)
    return clean_text(tag.get("content", "")) if tag else ""

def scrape_book_page(audible_url, narrator_name, credit_note):
    response = requests.get(audible_url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    page_text = clean_text(soup.get_text(" "))

    title = (
        get_meta_content(soup, 'meta[property="og:title"]')
        or clean_text(soup.select_one("h1").get_text()) if soup.select_one("h1") else ""
    )

    cover = (
        get_meta_content(soup, 'meta[property="og:image"]')
        or get_meta_content(soup, 'meta[name="twitter:image"]')
    )

    description = (
        get_meta_content(soup, 'meta[property="og:description"]')
        or get_meta_content(soup, 'meta[name="description"]')
    )

    author = ""
    author_match = re.search(r"By:\s*(.*?)\s*Narrated by:", page_text, re.I)
    if author_match:
        author = clean_text(author_match.group(1))

    release_date = ""
    release_match = re.search(r"Release date:\s*([0-9\-\/]+)", page_text, re.I)
    if release_match:
        release_date = clean_text(release_match.group(1))

    rating_text = ""
    reviews = 0

    rating_match = re.search(
        r"([\d.]+)\s*out of 5 stars.*?([\d,]+)\s*ratings?",
        page_text,
        re.I
    )

    if rating_match:
        rating_text = f"{rating_match.group(1)} out of 5 stars {rating_match.group(2)} ratings"
        reviews = get_review_count(rating_text)

    # If Audible blocks details, at least keep title/cover from metadata
    if not author and description:
        author_match = re.search(r"By:\s*(.*?)\s*Narrated by:", description, re.I)
        if author_match:
            author = clean_text(author_match.group(1))

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
            print(f"Failed manual book: {audible_url}")
            print(e)

        time.sleep(2)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(manual_books, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(manual_books)} manual books.")

if __name__ == "__main__":
    main()

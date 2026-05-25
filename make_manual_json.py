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
    return list(csv.DictReader(response.text.splitlines()))

def get_meta_content(soup, selector):
    tag = soup.select_one(selector)
    return clean_text(tag.get("content", "")) if tag else ""

def extract_json_objects(html):
    objects = []

    for script in re.findall(r"<script[^>]*>(.*?)</script>", html, re.S | re.I):
        script = script.strip()

        if not script:
            continue

        if "__NEXT_DATA__" in script or "asin" in script.lower() or "release" in script.lower():
            try:
                start = script.find("{")
                end = script.rfind("}") + 1

                if start != -1 and end != -1:
                    objects.append(json.loads(script[start:end]))
            except:
                pass

    return objects

def walk_json(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk_json(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk_json(item)

def find_in_json(json_objects):
    data = {
        "title": "",
        "author": "",
        "cover": "",
        "release_date": "",
        "rating_text": "",
        "reviews": 0
    }

    for root in json_objects:
        for obj in walk_json(root):
            keys = {str(k).lower(): k for k in obj.keys()}

            # Title — do NOT use generic "name" because it may be publisher
            for key in ["title", "producttitle", "product_title"]:
                if key in keys and not data["title"]:
                    value = obj.get(keys[key])
                    if isinstance(value, str) and len(value) > 2:
                        data["title"] = clean_text(value)

            # Cover image
            for key in [
                "image",
                "cover",
                "coverimage",
                "cover_image",
                "productimage",
                "productimageurl",
                "product_image_url"
            ]:
                if key in keys and not data["cover"]:
                    value = obj.get(keys[key])
                    if isinstance(value, str) and "amazon" in value.lower():
                        data["cover"] = value

            # Release date
            for key in [
                "releasedate",
                "release_date",
                "publicationdate",
                "publication_date"
            ]:
                if key in keys and not data["release_date"]:
                    value = obj.get(keys[key])
                    if isinstance(value, str):
                        data["release_date"] = clean_text(value)

            # Author
            for key in ["author", "authors"]:
                if key in keys and not data["author"]:
                    value = obj.get(keys[key])

                    if isinstance(value, str):
                        data["author"] = clean_text(value)

                    elif isinstance(value, list):
                        names = []

                        for item in value:
                            if isinstance(item, str):
                                names.append(item)

                            elif isinstance(item, dict):
                                name = item.get("name") or item.get("title") or ""
                                if name:
                                    names.append(name)

                        data["author"] = clean_text(", ".join(names))

    return data

def get_best_cover_from_html(soup):
    candidates = []

    for img in soup.select("img"):
        for attr in ["data-a-hires", "data-src", "src"]:
            src = img.get(attr, "")

            if not src:
                continue

            low = src.lower()

            if "m.media-amazon.com" not in low and "images-na.ssl-images-amazon.com" not in low:
                continue

            if any(bad in low for bad in ["audible", "logo", "sprite", "transparent"]):
                continue

            score = 0

            if "_sl500" in low or "_sl600" in low or "_sl1000" in low:
                score += 50

            if "_sl63" in low or "_sl75" in low:
                score -= 20

            candidates.append((score, src))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    return ""

def extract_from_text(page_text):
    author = ""
    release_date = ""

    author_match = re.search(r"By:\s*(.*?)\s*Narrated by:", page_text, re.I)
    if author_match:
        author = clean_text(author_match.group(1))

    release_match = re.search(
        r"Release date:\s*([0-9]{1,2}-[0-9]{1,2}-[0-9]{2,4})",
        page_text,
        re.I
    )
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

    return author, release_date, rating_text, reviews

def scrape_book_page(audible_url, narrator_name, credit_note):
    response = requests.get(audible_url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    page_text = clean_text(soup.get_text(" "))

    json_data = find_in_json(extract_json_objects(html))

    h1 = soup.select_one("h1")
    h1_title = clean_text(h1.get_text()) if h1 else ""

    meta_title = get_meta_content(soup, 'meta[property="og:title"]')

    title = h1_title or meta_title or json_data["title"]

    text_author, text_release, rating_text, reviews = extract_from_text(page_text)

    author = json_data["author"] or text_author
    release_date = json_data["release_date"] or text_release
    cover = json_data["cover"] or get_best_cover_from_html(soup)

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

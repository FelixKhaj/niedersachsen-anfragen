from __future__ import annotations

import argparse
import io
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

BASE_URL = "https://www.landtag-niedersachsen.de"
SEARCH_URL = f"{BASE_URL}/dokumentensuche/"
OUTPUT = Path("data/documents.json")

HEADERS = {
    "User-Agent": (
        "Niedersachsen-Anfragen-Recherchebot/0.1 "
        "(öffentlicher journalistischer Rechercheindex)"
    )
}


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def page_html(page: int) -> str:
    params = {
        "tx_nltdocuments_documents[action]": "list",
        "tx_nltdocuments_documents[controller]": "Documents",
        "tx_nltdocuments_documents[currentPage]": page,
    }
    response = requests.get(
        SEARCH_URL, params=params, headers=HEADERS, timeout=45
    )
    response.raise_for_status()
    return response.text


def find_container(link):
    node = link
    for _ in range(8):
        node = node.parent
        if node is None:
            break
        text = normalize(node.get_text(" ", strip=True))
        if (
            "Drucksachen" in text
            and "PDF laden" in text
            and len(text) < 2500
        ):
            return node
    return link.parent


def parse_listing(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, dict] = {}

    for link in soup.select('a[href*=".pdf"]'):
        href = link.get("href")
        if not href:
            continue

        pdf_url = urljoin(BASE_URL, href)
        container = find_container(link)
        text = normalize(container.get_text(" ", strip=True))

        if "Antwort auf eine Kleine Anfrage" not in text and (
            "Antwort der Landesregierung" not in text
            and "mit Antwort der Landesregierung" not in text
        ):
            continue

        match = re.search(r"Drucksachen?\s+(\d+/\d+)", text)
        if match:
            drucksache = match.group(1)
        else:
            file_match = re.search(r"/(\d+)-(\d+)\.pdf", pdf_url, re.I)
            if not file_match:
                continue
            drucksache = f"{file_match.group(1)}/{file_match.group(2)}"

        heading = container.find(["h2", "h3", "h4"])
        title = normalize(heading.get_text(" ", strip=True)) if heading else ""

        found[pdf_url] = {
            "drucksache": drucksache,
            "title": title,
            "listing_text": text,
            "pdf_url": pdf_url,
        }

    return list(found.values())


def extract_pdf_text(pdf_url: str) -> str:
    response = requests.get(pdf_url, headers=HEADERS, timeout=90)
    response.raise_for_status()

    reader = PdfReader(io.BytesIO(response.content))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def pdf_metadata(text: str) -> dict:
    compact = normalize(text)
    result: dict[str, str] = {}

    ministry = re.search(
        r"Antwort (?:des|der) (.+?) namens der Landesregierung",
        compact,
        re.I,
    )
    if ministry:
        result["ministerium"] = ministry.group(1).strip()

    date_match = re.search(
        r"namens der Landesregierung vom (\d{2}\.\d{2}\.\d{4})",
        compact,
        re.I,
    )
    if date_match:
        result["antwortdatum"] = date_match.group(1)

    people = re.search(
        r"Anfrage (?:des|der) Abgeordneten? (.+?)(?:, eingegangen am| Antwort )",
        compact,
        re.I,
    )
    if people:
        result["anfragende"] = people.group(1).strip()

    return result


def load_existing() -> dict[str, dict]:
    if not OUTPUT.exists():
        return {}
    records = json.loads(OUTPUT.read_text(encoding="utf-8"))
    return {record["pdf_url"]: record for record in records}


def run(pages: int, pause: float) -> None:
    records = load_existing()

    for page in range(1, pages + 1):
        documents = parse_listing(page_html(page))
        print(f"Seite {page}: {len(documents)} passende Treffer")

        for document in documents:
            if document["pdf_url"] in records:
                continue

            try:
                full_text = extract_pdf_text(document["pdf_url"])
                document.update(pdf_metadata(full_text))
                document["full_text"] = full_text
                document["indexed_at"] = datetime.now(timezone.utc).isoformat()
                records[document["pdf_url"]] = document
                print("  +", document["drucksache"], document["title"][:70])
            except Exception as exc:
                print("  ! Fehler:", document["pdf_url"], exc)

            time.sleep(pause)

        time.sleep(pause)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(
        records.values(),
        key=lambda item: item.get("drucksache", ""),
        reverse=True,
    )
    OUTPUT.write_text(
        json.dumps(ordered, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"{len(ordered)} Dokumente gespeichert: {OUTPUT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=10)
    parser.add_argument("--pause", type=float, default=1.5)
    args = parser.parse_args()
    run(args.pages, args.pause)

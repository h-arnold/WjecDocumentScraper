"""Command line tool for downloading PDF documents from WJEC GCSE qualification pages."""

from __future__ import annotations

import argparse
import itertools
import json
import re
from pathlib import Path
from typing import Iterator
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


KEY_DOCUMENTS_ENDPOINT = "/umbraco/surface/TabSurface/GetKeyDocumentsTab"

QUALIFICATION_URLS = {
    "Art and Design": "https://www.wjec.co.uk/qualifications/gcse-art-and-design-teaching-from-2025/#tab_keydocuments",
    "Business": "https://www.wjec.co.uk/qualifications/gcse-business-teaching-from-2025/#tab_keydocuments",
    "Computer Science": "https://www.wjec.co.uk/qualifications/gcse-computer-science-teaching-from-2025/#tab_keydocuments",
    "Core Cymraeg": "https://www.wjec.co.uk/qualifications/gcse-core-cymraeg-teaching-from-2025/#tab_keydocuments",
    "Cymraeg Language and Literature": "https://www.wjec.co.uk/qualifications/gcse-cymraeg-language-and-literature-single-and-double-award-teaching-from-2025/#tab_keydocuments",
    "Drama": "https://www.wjec.co.uk/qualifications/gcse-drama-teaching-from-2025/#tab_keydocuments",
    "English Language and Literature": "https://www.wjec.co.uk/qualifications/gcse-english-language-and-literature-single-and-double-award-teaching-from-2025/#tab_keydocuments",
    "Food and Nutrition": "https://www.wjec.co.uk/qualifications/gcse-food-and-nutrition-teaching-from-2025/#tab_keydocuments",
    "French": "https://www.wjec.co.uk/qualifications/gcse-french-teaching-from-2025/#tab_keydocuments",
    "Geography": "https://www.wjec.co.uk/qualifications/gcse-geography-teaching-from-2025/#tab_keydocuments",
    "German": "https://www.wjec.co.uk/qualifications/gcse-german-teaching-from-2025/#tab_keydocuments",
    "Mathematics and Numeracy": "https://www.wjec.co.uk/qualifications/gcse-mathematics-and-numeracy-double-award-teaching-from-2025/#tab_keydocuments",
    "Music": "https://www.wjec.co.uk/qualifications/gcse-music-teaching-from-2025/#tab_keydocuments",
    "Religious Studies": "https://www.wjec.co.uk/qualifications/gcse-religious-studies-teaching-from-2025/#tab_keydocuments",
    "Spanish": "https://www.wjec.co.uk/qualifications/gcse-spanish-teaching-from-2025/#tab_keydocuments",
    "Level 2 Additional Core Cymraeg": "https://www.wjec.co.uk/qualifications/level-2-award-in-additional-core-cymraeg-teaching-from-2025/#tab_keydocuments",
    "Dance": "https://www.wjec.co.uk/qualifications/gcse-dance-teaching-from-2026/#tab_keydocuments",
    "Design and Technology": "https://www.wjec.co.uk/qualifications/gcse-design-and-technology-teaching-from-2026/#tab_keydocuments",
    "Digital Media and Film": "https://www.wjec.co.uk/qualifications/gcse-digital-media-and-film-teaching-from-2026/#tab_keydocuments",
    "Digital Technology": "https://www.wjec.co.uk/qualifications/gcse-digital-technology-teaching-from-2026/#tab_keydocuments",
    "Health and Social Care, and Childcare": "https://www.wjec.co.uk/qualifications/gcse-health-and-social-care-and-childcare-teaching-from-2026/#tab_keydocuments",
    "History": "https://www.wjec.co.uk/qualifications/gcse-history-teaching-from-2026/#tab_keydocuments",
    "Integrated Science (Single Award)": "https://www.wjec.co.uk/qualifications/gcse-integrated-science-single-award-teaching-from-2026/#tab_keydocuments",
    "Physical Education and Health": "https://www.wjec.co.uk/qualifications/gcse-physical-education-and-health-teaching-from-2026/#tab_keydocuments",
    "Social Studies": "https://www.wjec.co.uk/qualifications/gcse-social-studies-teaching-from-2026/#tab_keydocuments",
    "The Sciences (Double Award)": "https://www.wjec.co.uk/qualifications/gcse-the-sciences-double-award-teaching-from-2026/#tab_keydocuments",
    "Level 2 Additional Mathematics": "https://www.wjec.co.uk/qualifications/level-2-award-in-additional-mathematics-teaching-from-2026/#tab_keydocuments",
}


def fetch_html(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def iter_pdf_links(soup: BeautifulSoup, base_url: str) -> Iterator[tuple[str, str]]:
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href.lower().endswith(".pdf"):
            continue
        absolute_url = urljoin(base_url, href)
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        title = anchor.get_text(strip=True) or Path(urlparse(absolute_url).path).name
        yield title, absolute_url


def iter_pdf_from_react_props(soup: BeautifulSoup, base_url: str) -> Iterator[tuple[str, str]]:
    for props_node in soup.select("textarea.react-component--props"):
        raw_json = props_node.string or props_node.text
        if not raw_json:
            continue
        try:
            props = json.loads(raw_json)
        except json.JSONDecodeError:
            continue
        for item in props.get("listItems", []):
            link = (item.get("Link") or "").strip()
            if not link or not link.lower().endswith(".pdf"):
                continue
            title = (item.get("Name") or "").strip()
            absolute_url = urljoin(base_url, link)
            yield title or Path(urlparse(absolute_url).path).name, absolute_url


def fetch_key_documents_tab(base_url: str, landing_html: str) -> str | None:
    soup = BeautifulSoup(landing_html, "html.parser")
    qualification = soup.find("input", id="QualificationId")
    culture = soup.find("input", id="CultureId")
    if not qualification:
        return None

    params = {
        "qualificationId": qualification.get("value", "").strip(),
        "cultureId": culture.get("value", "en-GB") if culture else "en-GB",
    }
    if not params["qualificationId"]:
        return None

    base_without_fragment = base_url.split("#", 1)[0]
    endpoint_url = urljoin(base_without_fragment, KEY_DOCUMENTS_ENDPOINT)
    response = requests.get(endpoint_url, params=params, timeout=30)
    response.raise_for_status()
    return response.text


def sanitise_filename(title: str, url: str, existing: set[str]) -> str:
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", title.lower()).strip("-")
    if not stem:
        stem = Path(urlparse(url).path).stem or "document"
    if not stem.endswith(".pdf"):
        stem = f"{stem}.pdf"
    base_stem = stem
    for idx in itertools.count(1):
        if stem not in existing:
            existing.add(stem)
            return stem
        stem = f"{Path(base_stem).stem}-{idx}.pdf"


def download_file(url: str, destination: Path) -> None:
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with destination.open("wb") as file_handle:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file_handle.write(chunk)


def collect_pdf_links(url: str) -> list[tuple[str, str]]:
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    pdf_candidates = list(iter_pdf_links(soup, url))
    key_documents_html = fetch_key_documents_tab(url, html)
    if key_documents_html:
        key_documents_soup = BeautifulSoup(key_documents_html, "html.parser")
        pdf_candidates.extend(iter_pdf_links(key_documents_soup, url))
        pdf_candidates.extend(iter_pdf_from_react_props(key_documents_soup, url))

    unique_links: dict[str, str] = {}
    for title, pdf_url in pdf_candidates:
        current_title = unique_links.get(pdf_url)
        if not current_title or len(title) > len(current_title):
            unique_links[pdf_url] = title

    return list(unique_links.items())


def subject_directory_name(subject: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", subject.strip()).strip("-")
    return cleaned or "subject"


def scrape_subject(subject: str, url: str, output_root: Path) -> int:
    print(f"\n=== {subject} ===")
    print(f"Fetching page: {url}")
    pdf_links = collect_pdf_links(url)

    if not pdf_links:
        print("No PDF links found.")
        return 0

    subject_dir = output_root / subject_directory_name(subject)
    subject_dir.mkdir(parents=True, exist_ok=True)

    used_filenames: set[str] = set()
    count = 0
    for pdf_url, title in sorted(pdf_links, key=lambda item: item[1].lower() if item[1] else item[0]):
        filename = sanitise_filename(title or pdf_url, pdf_url, used_filenames)
        destination = subject_dir / filename
        print(f"Downloading {title or filename} -> {destination}")
        download_file(pdf_url, destination)
        count += 1

    print(f"Saved {count} PDF(s) to {subject_dir}")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Download PDF documents for the WJEC GCSE Made-for-Wales qualifications.")
    parser.add_argument(
        "--subjects",
        nargs="*",
        metavar="SUBJECT",
        help="Optional list of subject names to download (defaults to all configured subjects).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="Documents",
        help="Root directory where subject folders will be saved.",
    )
    args = parser.parse_args()

    selected_subjects = QUALIFICATION_URLS
    if args.subjects:
        requested = {name.lower() for name in args.subjects}
        selected_subjects = {
            subject: url for subject, url in QUALIFICATION_URLS.items() if subject.lower() in requested
        }
        missing = requested.difference({subject.lower() for subject in selected_subjects})
        if missing:
            print("Warning: some requested subjects were not recognised:")
            for item in sorted(missing):
                print(f"  - {item}")

    if not selected_subjects:
        print("No subjects selected. Exiting.")
        return

    output_root = Path(args.output)
    output_root.mkdir(parents=True, exist_ok=True)

    total_downloaded = 0
    for subject, url in selected_subjects.items():
        total_downloaded += scrape_subject(subject, url, output_root)

    print(f"\nFinished. Downloaded {total_downloaded} PDF(s) into {output_root.resolve()}")


if __name__ == "__main__":
    main()

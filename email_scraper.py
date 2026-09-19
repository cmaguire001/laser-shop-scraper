import requests
import csv
import time
import re
import json
from bs4 import BeautifulSoup

INPUT_CSV = r"C:\Users\kathe\OneDrive\Documents\laser_agent_results.csv"
OUTPUT_CSV = r"C:\Users\kathe\OneDrive\Documents\laser_agent_with_emails.csv"

HEADERS = {"User-Agent": "Mozilla/5.0"}
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2"


def find_emails_regex(html_text):
    found = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", html_text)
    cleaned = set()
    for email in found:
        if not any(skip in email for skip in ["example.com", "sentry", "wix", "wordpress", "schema", ".png", ".jpg"]):
            cleaned.add(email.lower())
    return list(cleaned)


def fetch_page(url, timeout=10):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        if resp.status_code == 200:
            return resp.text
        return None
    except:
        return None


def get_contact_pages(base_url):
    base = base_url.rstrip("/")
    pages = {}

    # Homepage
    html = fetch_page(base_url)
    if html:
        pages["homepage"] = html

    # Contact/about pages
    for path in ["/contact", "/contact-us", "/about", "/about-us", "/team", "/our-team", "/staff"]:
        html = fetch_page(base + path)
        if html:
            pages[path] = html
            time.sleep(0.3)

    return pages


def extract_with_ollama(business_name, page_text):
    prompt = f"""You are extracting contact information from a business website for "{business_name}".
Read the text below and extract any people's names, their job titles, and email addresses.
Only extract real people — skip generic emails like info@ or sales@ unless they have a name attached.
Respond ONLY with a valid JSON array, no explanation, no markdown, no backticks.
If no named contacts are found, respond with an empty array [].

Format:
[
  {{"name": "John Smith", "title": "Sales Manager", "email": "john@company.com"}},
  {{"name": "Jane Doe", "title": "Owner", "email": null}}
]

Website text:
{page_text[:3000]}"""

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        content = resp.json()["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return parsed
        return []
    except Exception as e:
        return []


def scrape_business(url, business_name):
    all_emails = set()
    contacts = []

    pages = get_contact_pages(url)

    if not pages:
        return "", "", ""

    # Fast regex pass on all pages
    for page_text in pages.values():
        emails = find_emails_regex(page_text)
        all_emails.update(emails)

    # Ollama pass on contact/about pages only
    contact_page_text = ""
    for path, html in pages.items():
        if path != "homepage":
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            contact_page_text += soup.get_text(separator=" ", strip=True) + " "

    if contact_page_text.strip():
        print(f"  Agent reading contact pages...")
        contacts = extract_with_ollama(business_name, contact_page_text)

    # Pull any emails from contacts that regex might have missed
    for c in contacts:
        if c.get("email"):
            all_emails.add(c["email"].lower())

    # Format outputs
    emails_str = ", ".join(all_emails) if all_emails else ""

    named_contacts = [c for c in contacts if c.get("name")]
    if named_contacts:
        names_str = ", ".join([c.get("name", "") for c in named_contacts])
        titles_str = ", ".join([c.get("title", "") or "" for c in named_contacts])
    else:
        names_str = ""
        titles_str = ""

    return emails_str, names_str, titles_str


def main():
    with open(INPUT_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames)

    print(f"Loaded {len(rows)} businesses\n")

    for col in ["email", "contact_name", "contact_title"]:
        if col not in fieldnames:
            fieldnames.append(col)

    results = []
    for i, row in enumerate(rows):
        name = row.get("name", "Unknown")
        website = row.get("website", "")

        print(f"\n[{i+1}/{len(rows)}] {name}")

        if not website:
            print("  No website — skipping")
            row["email"] = ""
            row["contact_name"] = ""
            row["contact_title"] = ""
        else:
            print(f"  Fetching: {website}")
            email, contact_name, contact_title = scrape_business(website, name)
            row["email"] = email
            row["contact_name"] = contact_name
            row["contact_title"] = contact_title

            if email:
                print(f"  Email: {email}")
            if contact_name:
                print(f"  Contact: {contact_name} — {contact_title}")
            if not email and not contact_name:
                print(f"  Nothing found")

        results.append(row)
        time.sleep(0.5)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    found_emails = sum(1 for r in results if r.get("email"))
    found_contacts = sum(1 for r in results if r.get("contact_name"))
    print(f"\n=== DONE ===")
    print(f"Emails found: {found_emails}/{len(results)}")
    print(f"Named contacts found: {found_contacts}/{len(results)}")
    print(f"Saved to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
import requests
import csv
import time
import re
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse

INPUT_CSV = r"C:\Users\kathe\OneDrive\Documents\laser_agent_results.csv"
OUTPUT_CSV = r"C:\Users\kathe\OneDrive\Documents\laser_agent_with_emails.csv"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2"

# ------------------------------------------------------------
# FIX 1: REDIRECT FOLLOWING + FINAL URL CAPTURE
#
# WHY: Google Places API sometimes returns stale or rebranded
# domains (e.g. westtoolenclosures.com instead of westtoolff.com).
# When a site has moved, the old domain redirects to the new one.
# Previously we followed the redirect but discarded the final URL,
# so we kept scraping/logging the wrong domain. Now we capture
# and return the resolved URL so the CSV reflects where we actually
# scraped from, and contact links are resolved against the real domain.
#
# EXAMPLE CAUGHT: West Tool Enclosures — old domain blocked cold
# email; new domain (westtoolff.com) had contact info right on
# the homepage including a direct email.
# ------------------------------------------------------------
def fetch_page(url, timeout=10):
    """
    Fetch a page and follow redirects.
    Returns (html_text, final_url) or (None, original_url) on failure.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        final_url = resp.url  # capture resolved URL after redirects
        if resp.status_code == 200:
            return resp.text, final_url
        return None, url
    except:
        return None, url


# ------------------------------------------------------------
# FIX 2: DOMAIN HEALTH CHECK + GOOGLE SEARCH FALLBACK
#
# WHY: When a domain returns a non-200 status (403, 404, 301 to
# dead page, etc.) the old code gave up and logged nothing. But
# the company may still exist under a different domain or be
# findable via a Google search. This function checks the domain
# first; if it's unhealthy it falls back to a targeted Google
# search for an alternative website before giving up entirely.
#
# EXAMPLE CAUGHT: westtoolenclosures.com returns 403 for scrapers.
# A Google search for "West Tool Enclosures Fergus Falls MN contact"
# surfaces westtoolff.com which has the email on the homepage.
# ------------------------------------------------------------
def resolve_working_url(original_url, business_name, city=""):
    """
    Verify domain is reachable. If not, search Google for an
    alternative domain and return the best candidate URL.
    Returns (working_url, was_fallback) tuple.
    """
    html, final_url = fetch_page(original_url)
    if html:
        return final_url, False  # original domain works fine

    # Domain failed — try Google search fallback
    print(f"  ⚠️  Domain unreachable — trying Google fallback...")
    search_query = f'"{business_name}" {city} contact email site'
    search_url = f"https://www.google.com/search?q={requests.utils.quote(search_query)}"

    try:
        resp = requests.get(search_url, headers={
            **HEADERS,
            "Accept-Language": "en-US,en;q=0.9",
        }, timeout=10)

        # Extract URLs from Google results
        found_urls = re.findall(r'href="(https?://[^"&]+)"', resp.text)
        skip_domains = ["google.", "youtube.", "facebook.", "linkedin.",
                        "yelp.", "bbb.org", "yellowpages.", "mapquest."]

        for candidate in found_urls:
            parsed = urlparse(candidate)
            if any(s in parsed.netloc for s in skip_domains):
                continue
            if parsed.netloc == urlparse(original_url).netloc:
                continue  # same broken domain, skip

            # Test if this candidate URL actually works
            test_html, test_final = fetch_page(candidate)
            if test_html:
                print(f"  ✅ Found alternative domain: {test_final}")
                return test_final, True  # fallback worked

    except Exception as e:
        print(f"  Google fallback failed: {e}")

    return original_url, False  # nothing worked


def find_emails_regex(html_text):
    found = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", html_text)
    cleaned = set()
    for email in found:
        if not any(skip in email for skip in [
            "example.com", "sentry", "wix", "wordpress", "schema",
            ".png", ".jpg", ".svg", "youremail", "domain.com"
        ]):
            cleaned.add(email.lower())
    return list(cleaned)


def get_contact_pages(base_url):
    """
    Fetch homepage + common contact/about subpages.
    Uses redirect-aware fetch_page so links are resolved against
    the real final domain, not the stale Google Places URL.
    """
    base = base_url.rstrip("/")
    pages = {}

    html, final_url = fetch_page(base_url)
    if html:
        pages["homepage"] = html
        # Rebase to final URL in case of redirect
        base = final_url.rstrip("/")

    for path in ["/contact", "/contact-us", "/about", "/about-us",
                 "/team", "/our-team", "/staff"]:
        html, _ = fetch_page(base + path)
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
    except Exception:
        return []


def scrape_business(url, business_name, city=""):
    all_emails = set()
    contacts = []

    # FIX 2: verify domain health, fall back to Google if needed
    working_url, used_fallback = resolve_working_url(url, business_name, city)
    if used_fallback:
        print(f"  📍 Scraping fallback URL: {working_url}")

    pages = get_contact_pages(working_url)
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

    for c in contacts:
        if c.get("email"):
            all_emails.add(c["email"].lower())

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

        # Extract city from address for better Google fallback searches
        address = row.get("address", "")
        city = ""
        if address:
            parts = address.split(",")
            if len(parts) >= 2:
                city = parts[1].strip()

        print(f"\n[{i+1}/{len(rows)}] {name}")

        if not website:
            print("  No website — skipping")
            row["email"] = ""
            row["contact_name"] = ""
            row["contact_title"] = ""
        else:
            print(f"  Fetching: {website}")
            email, contact_name, contact_title = scrape_business(website, name, city)
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
    print(f"Emails found:        {found_emails}/{len(results)}")
    print(f"Named contacts:      {found_contacts}/{len(results)}")
    print(f"Saved to:            {OUTPUT_CSV}")


if __name__ == "__main__":
    main()

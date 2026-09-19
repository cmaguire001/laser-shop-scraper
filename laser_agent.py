import requests
import csv
import time
import os
import json
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv(r"C:\Users\kathe\OneDrive\Documents\.env")
API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2"

SEARCH_LOCATIONS = [
    ("Elk River MN",   45.2969, -93.5677),
    ("Anoka MN",       45.1977, -93.3869),
    ("Monticello MN",  45.3058, -93.7936),
    ("Buffalo MN",     45.1733, -93.8752),
    ("St Cloud MN",    45.5579, -94.1632),
    ("Maple Grove MN", 45.0725, -93.4557),
    ("Plymouth MN",    45.0105, -93.4555),
    ("Blaine MN",      45.1608, -93.2349),
    ("Cambridge MN",   45.5719, -93.2244),
    ("Zimmerman MN",   45.4427, -93.5902),
]

SEARCH_TERMS = [
    "sheet metal fabrication",
    "CNC laser cutting",
    "metal fabrication shop",
    "laser cutting service",
]

def search_places(query, lat, lng):
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress",
    }
    payload = {
        "textQuery": query,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": 50000.0,
            }
        },
        "maxResultCount": 20,
    }
    resp = requests.post(url, headers=headers, json=payload)
    data = resp.json()
    if "error" in data:
        print(f"  API error: {data['error']['message']}")
        return []
    return data.get("places", [])


def get_place_details(place_id):
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    headers = {
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "displayName,formattedAddress,nationalPhoneNumber,websiteUri,rating,userRatingCount",
    }
    resp = requests.get(url, headers=headers)
    if not resp.text.strip():
        print(f"  Empty response for {place_id}")
        return {}
    try:
        return resp.json()
    except Exception as e:
        print(f"  Failed to parse details for {place_id}: {e}")
        print(f"  Raw response: {resp.text[:200]}")
        return {}


def fetch_website_text(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return text[:3000]
    except Exception as e:
        return f"ERROR: {e}"


def agent_extract(business_name, website_text):
    prompt = f"""You are a manufacturing industry researcher.
Analyze this website text from a metal fabrication company called "{business_name}" and extract the following information.
Respond ONLY with a valid JSON object, no explanation, no markdown, no backticks.

Extract these fields (use null if not found):
{{
  "laser_types": "types of laser machines they have (fiber, CO2, etc)",
  "materials": "materials they cut or work with",
  "max_thickness": "maximum material thickness they can cut",
  "cutting_area": "maximum sheet or part size",
  "certifications": "any certifications like ISO, AS9100, ITAR, etc",
  "additional_services": "other services like bending, welding, finishing, assembly",
  "industries_served": "industries they mention serving",
  "notes": "any other relevant capabilities or specializations"
}}

Website text:
{website_text}"""

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
        return json.loads(content)
    except Exception as e:
        return {
            "laser_types": None,
            "materials": None,
            "max_thickness": None,
            "cutting_area": None,
            "certifications": None,
            "additional_services": None,
            "industries_served": None,
            "notes": f"PARSE ERROR: {e}",
        }


def main():
    seen_ids = set()
    businesses = []

    # --- STEP 1: Collect businesses ---
    print("=== STEP 1: Collecting businesses from Google Places ===")

    for city, lat, lng in SEARCH_LOCATIONS:
        for term in SEARCH_TERMS:
            print(f"  Searching '{term}' near {city}...")
            places = search_places(term, lat, lng)
            print(f"  Found {len(places)} results")

            for place in places:
                place_id = place.get("id")
                if not place_id or place_id in seen_ids:
                    continue
                seen_ids.add(place_id)

                details = get_place_details(place_id)
                time.sleep(0.2)

                businesses.append({
                    "name": details.get("displayName", {}).get("text", ""),
                    "address": details.get("formattedAddress", ""),
                    "phone": details.get("nationalPhoneNumber", ""),
                    "website": details.get("websiteUri", ""),
                    "rating": details.get("rating", ""),
                    "total_ratings": details.get("userRatingCount", ""),
                })

            time.sleep(0.5)

    print(f"\nFound {len(businesses)} unique businesses.\n")

    if len(businesses) == 0:
        print("No businesses found — check your API key and that Places API (New) is enabled.")
        return

    # --- STEP 2: Agent reads each website ---
    print("=== STEP 2: Agent analyzing each website ===")
    results = []

    for biz in businesses:
        name = biz.get("name", "Unknown")
        website = biz.get("website", "")
        print(f"\n[{name}]")

        empty = {k: None for k in [
            "laser_types", "materials", "max_thickness",
            "cutting_area", "certifications",
            "additional_services", "industries_served", "notes"
        ]}

        if not website:
            print("  No website — skipping")
            extracted = empty
        else:
            print(f"  Fetching: {website}")
            text = fetch_website_text(website)
            if text.startswith("ERROR"):
                print(f"  {text}")
                extracted = empty
            else:
                print(f"  Agent thinking...")
                extracted = agent_extract(name, text)
                print(f"  Laser types: {extracted.get('laser_types', 'not found')}")

        results.append({**biz, **extracted})
        time.sleep(1)

    # --- STEP 3: Save CSV ---
    output_path = r"C:\Users\kathe\OneDrive\Documents\laser_agent_results.csv"
    fieldnames = [
        "name", "address", "phone", "website", "rating", "total_ratings",
        "laser_types", "materials", "max_thickness", "cutting_area",
        "certifications", "additional_services", "industries_served", "notes"
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n=== DONE ===")
    print(f"Processed {len(results)} businesses")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()
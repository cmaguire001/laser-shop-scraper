# Laser Shop Scraper

An AI agent that finds and analyzes sheet metal CNC laser cutting businesses within a 50-mile radius of a target location. Built as a business intelligence tool for the metal fabrication industry.

## What it does

1. **Searches Google Places API** across multiple city centers to find sheet metal and laser cutting shops
2. **Visits each company website** and scrapes readable text
3. **Uses a local LLM (Ollama/llama3.2)** to extract structured capability data from each site
4. **Scrapes emails and contact names** from contact and about pages
5. **Exports results to CSV** with full business intel ready for outreach

## Sample Output

See `sample_output.csv` for an example of the data structure produced.

| Field | Description |
|---|---|
| name | Business name |
| address | Full address |
| phone | Phone number |
| website | Website URL |
| rating | Google rating |
| laser_types | Fiber, CO2, plasma etc |
| materials | Materials they cut |
| max_thickness | Thickest material they cut |
| cutting_area | Max sheet size |
| certifications | ISO, AS9100, ITAR etc |
| additional_services | Bending, welding, finishing etc |
| industries_served | Aerospace, medical, ag etc |
| email | Contact email |
| contact_name | Name of contact person |
| contact_title | Their job title |

## Scripts

### laser_agent.py
Main agent — finds businesses via Google Places and uses Ollama to extract capability data from each website.

### email_scraper.py
Second pass — reads the output CSV, revisits each website, scrapes emails via regex and mailto links, uses Ollama to extract named contacts from contact and about pages.

## Stack

- Python 3.x
- Google Places API (New)
- Ollama + llama3.2 (local LLM, no cloud AI costs)
- requests, BeautifulSoup4, python-dotenv

## Setup

1. Install dependencies:

   pip install requests beautifulsoup4 python-dotenv

2. Install Ollama from https://ollama.com and pull the model:

   ollama pull llama3.2

3. Create a .env file:

   GOOGLE_PLACES_API_KEY=your_key_here

4. Run the main agent:

   python laser_agent.py

5. Run the email scraper on the results:

   python email_scraper.py

## Notes

- Requires Google Places API (New) enabled in Google Cloud Console
- Runs LLM inference locally — no OpenAI API costs
- CPU-only mode works but is slow (~30-60s per site)
- Some sites blocked due to Cloudflare or JavaScript rendering
- Facebook and social media links are skipped automatically
- Real output CSV is excluded from repo via .gitignore to protect business data

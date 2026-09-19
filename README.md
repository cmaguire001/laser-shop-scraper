\# Laser Shop Scraper



An AI agent that finds and analyzes sheet metal CNC laser cutting businesses within a 50-mile radius of a target location.



\## What it does



1\. \*\*Searches Google Places API\*\* across multiple city centers to find sheet metal and laser cutting shops

2\. \*\*Visits each company website\*\* and scrapes readable text

3\. \*\*Uses a local LLM (Ollama/llama3.2)\*\* to extract structured capability data from each site

4\. \*\*Exports results to CSV\*\* with full business intel



\## Data extracted per business



\- Business name, address, phone, website, Google rating

\- Laser types (fiber, CO2, plasma)

\- Materials cut

\- Max cutting thickness and area

\- Certifications (ISO, AS9100, ITAR)

\- Additional services (bending, welding, finishing)

\- Industries served



\## Stack



\- Python 3.x

\- Google Places API (New)

\- Ollama + llama3.2 (local LLM, no cloud AI costs)

\- requests, BeautifulSoup4, python-dotenv



\## Setup



1\. Install dependencies:



&#x20;  pip install requests beautifulsoup4 python-dotenv



2\. Install Ollama from https://ollama.com and pull the model:



&#x20;  ollama pull llama3.2



3\. Create a .env file:



&#x20;  GOOGLE\_PLACES\_API\_KEY=your\_key\_here



4\. Run:



&#x20;  python laser\_agent.py



\## Notes



\- Requires Google Places API (New) enabled in Google Cloud Console

\- Runs LLM inference locally - no OpenAI API costs

\- CPU-only mode works but is slow (\~30-60s per site)


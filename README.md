# SMCCD Resource Map

An interactive visual map of student resources across the San Mateo County Community College District — Cañada College, College of San Mateo, and Skyline College.

## What It Does

Students can explore internships, scholarships, clubs, events, and other opportunities from all three SMCCD colleges in one place, displayed as an interactive force-directed bubble graph.

- **Visual Bubble Map**: resources appear as bubbles colored by category, clustered by their home school
- **Live Search**: filter by title, organization, description, college, category, or major
- **Smart Filters**: hide categories or majors you're not interested in
- **AI Link Scraping**: paste any URL and the app automatically extracts resources, classifies them, and places them on the map
- **Real-Time Sync**: new resources appear live for all open browsers via Supabase
- **Dark/Light Theme**: toggle between themes, saved locally

## How It Works

1. A URL is submitted via the "Add link" modal
2. The page content is fetched and cleaned via Jina AI Reader
3. The text is sent to a Groq-hosted LLM (`llama-3.1-8b-instant`) which extracts structured resource data
4. Results are validated, normalized, and saved to a Supabase database
5. All connected browsers receive the new resource instantly and the map updates

## Tech Stack

- **Frontend**: React 18 + Vite, SVG-based force-directed graph (no charting libraries)
- **Backend**: Vercel serverless function (`/api/scrape`)
- **Database**: Supabase (PostgreSQL + real-time subscriptions)
- **AI**: Groq API for fast LLM inference, Jina AI Reader for page scraping

## Project Structure

```
27Hack/
├── api/
│   └── scrape.js           # Scraping pipeline: Jina → Groq → Supabase
├── src/
│   ├── components/         # BubbleMap, DetailCard, FilterPanel, AddResourceModal
│   ├── hooks/              # useResources (Supabase), useTheme
│   ├── lib/                # Constants, graph engine, helpers, Supabase client, theme tokens
│   ├── App.jsx
│   └── main.jsx
├── index.html
├── vite.config.js
└── vercel.json
```
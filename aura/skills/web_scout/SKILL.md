---
name: web-scout-lead-hunter
description: B2B Spinning Mill Scraper & Lead Hunter. Use when Mukil asks to scrape spinning mills, find yarn suppliers in Karur/Tirupur/Erode, source gray yarn rates, or extract business leads.
---

# B2B Spinning Mill Lead Hunter & Scraper

## 📌 Mission
Autonomously extracts verified textile mill owner contacts, spinning mill directories, yarn counts (30s, 40s Karded/Combed), and pricing from web sources across Karur, Tirupur, Coimbatore, and Erode.

## 🚀 Execution Directives
- Primary tool: `search_web` combined with targeted Playwright scrapers in `BrowserPilotAgent`.
- Data Destination: Automatically saved into Node 04 of the Distributed Drive Mesh (`1ebinMnwlZFz6RhaRFYtVHhB2whzvPXDK`).
- Target Directories:
  * IndiaMART Textile & Spinning Mill listings
  * SIMA (Southern India Mills' Association) directory
  * Local Karur Textile Association databases
- Output Format: CSV / Google Sheets formatted with Mill Name, City, Contact Person, Phone, Email, Yarn Counts Handled.

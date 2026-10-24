import requests
import json

def scan_jobs():
    results = []

    # 1. Greenhouse Companies
    gh_companies = [
        "canonical", "cloudflare", "datadog", "mongodb", "elastic", 
        "stripe", "affirm", "checkr", "gitlab"
    ]
    headers = {"User-Agent": "Mozilla/5.0"}

    print("[*] Scanning Greenhouse boards...")
    for co in gh_companies:
        url = f"https://boards-api.greenhouse.io/v1/boards/{co}/jobs"
        try:
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                data = r.json().get("jobs", [])
                for j in data:
                    title = j.get("title", "")
                    title_l = title.lower()
                    loc = (j.get("location", {}).get("name") or "")
                    loc_l = loc.lower()

                    # Senior exclusions
                    if any(s in title_l for s in ["senior", "staff", "principal", "director", "manager", "lead", "vp", "head", "architect"]):
                        continue

                    # Fresh / Entry / Software keywords
                    is_tech = any(k in title_l for k in [
                        "software", "engineer", "developer", "graduate", "associate", 
                        "intern", "junior", "trainee", "python", "java", "frontend", "backend", "full stack"
                    ])

                    # Location target
                    is_loc = any(l in loc_l for l in ["india", "bangalore", "bengaluru", "chennai", "hyderabad", "pune", "remote", "apac"])

                    if is_tech and is_loc:
                        results.append({
                            "company": co.title(),
                            "title": title,
                            "location": loc,
                            "url": j.get("absolute_url"),
                            "type": "Product / Tech"
                        })
        except Exception:
            pass

    # 2. Lever Companies
    lever_companies = ["postman", "browserstack", "razorpay", "atlan", "invideo"]
    print("[*] Scanning Lever boards...")
    for co in lever_companies:
        url = f"https://api.lever.co/v0/postings/{co}?mode=json"
        try:
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                postings = r.json()
                for j in postings:
                    title = j.get("text", "")
                    title_l = title.lower()
                    loc = j.get("categories", {}).get("location") or ""
                    loc_l = loc.lower()

                    if any(s in title_l for s in ["senior", "staff", "principal", "director", "manager", "lead", "vp", "head", "architect"]):
                        continue

                    is_tech = any(k in title_l for k in [
                        "software", "engineer", "developer", "graduate", "associate", 
                        "intern", "junior", "trainee", "python", "java", "frontend", "backend", "full stack", "qa", "sde"
                    ])

                    is_loc = any(l in loc_l for l in ["india", "bangalore", "bengaluru", "chennai", "hyderabad", "pune", "mumbai", "remote"])

                    if is_tech and is_loc:
                        results.append({
                            "company": co.title(),
                            "title": title,
                            "location": loc,
                            "url": j.get("hostedUrl"),
                            "type": "High-Growth Product"
                        })
        except Exception:
            pass

    print(f"Total matching openings found: {len(results)}\n")
    for r in results:
        print(f"[{r['company']}] {r['title']} | {r['location']}")
        print(f"   URL: {r['url']}\n")

if __name__ == "__main__":
    scan_jobs()

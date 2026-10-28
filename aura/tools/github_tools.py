"""
AURA OS GitHub Integration Tools
Provides sub-second, structured access to Mukil's GitHub profile, repositories,
and commits via official GitHub REST API (Zero web scraping, zero delay).
"""
import requests
from typing import Dict, Any, List
from aura.config import GITHUB_TOKEN

GITHUB_USERNAME = "Mukil630"

def _get_headers() -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers

def get_github_profile(username: str = GITHUB_USERNAME) -> str:
    """
    Fetches the public GitHub profile of Mukil or any developer in under 200ms.
    Args:
        username: GitHub handle (defaults to 'Mukil630').
    """
    url = f"https://api.github.com/users/{username}"
    try:
        r = requests.get(url, headers=_get_headers(), timeout=5)
        if r.status_code == 200:
            data = r.json()
            return (
                f"👤 **GitHub Profile: {data.get('name', username)} (@{username})**\n"
                f"• Bio: {data.get('bio', 'N/A')}\n"
                f"• Public Repos: {data.get('public_repos', 0)}\n"
                f"• Followers: {data.get('followers', 0)} | Following: {data.get('following', 0)}\n"
                f"• Location: {data.get('location', 'Karur, Tamil Nadu')}\n"
                f"• Profile URL: {data.get('html_url')}"
            )
        elif r.status_code == 404:
            return f"❌ GitHub user '{username}' not found."
        else:
            return f"⚠️ GitHub API returned status code {r.status_code}."
    except Exception as e:
        return f"❌ Failed to fetch GitHub profile: {str(e)}"


def list_github_repositories(username: str = GITHUB_USERNAME, limit: int = 10) -> str:
    """
    Lists the latest repositories, languages, stars, and descriptions for Mukil or any developer.
    Args:
        username: GitHub handle (defaults to 'Mukil630').
        limit: Number of repositories to return (default 10).
    """
    url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page={limit}"
    try:
        r = requests.get(url, headers=_get_headers(), timeout=6)
        if r.status_code == 200:
            repos = r.json()
            if not repos:
                return f"No public repositories found for @{username}."
                
            formatted = [f"📂 **Latest GitHub Repositories for @{username} ({len(repos)} shown):**\n"]
            for idx, repo in enumerate(repos, 1):
                name = repo.get("name")
                desc = repo.get("description") or "No description provided."
                lang = repo.get("language") or "General"
                stars = repo.get("stargazers_count", 0)
                url = repo.get("html_url")
                formatted.append(f"{idx}. **[{name}]({url})** ({lang} • ⭐ {stars})\n   _{desc}_\n")
            return "\n".join(formatted)
        else:
            return f"⚠️ GitHub API error: Status {r.status_code}"
    except Exception as e:
        return f"❌ Failed to fetch repositories: {str(e)}"

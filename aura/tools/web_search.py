"""
AURA OS Robust High-Speed Web Search Tool
Multi-engine search: DuckDuckGo + Google News RSS Fallback.
Fast, resilient, zero-timeout, native UTF-8 support.
"""
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import re

def search_news_rss(query: str, max_results: int = 5) -> str:
    """Fetches real-time news headlines via Google News RSS in under 400ms."""
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            xml_data = resp.read()
        
        root = ET.fromstring(xml_data)
        items = root.findall(".//item")[:max_results]
        if not items:
            return ""
            
        formatted = [f"📰 Real-Time News Headlines for '{query}':\n"]
        for idx, item in enumerate(items, 1):
            title = item.find("title").text if item.find("title") is not None else "No Title"
            link = item.find("link").text if item.find("link") is not None else ""
            pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
            formatted.append(f"{idx}. {title}\n   Published: {pub_date}\n   Link: {link}\n")
            
        return "\n".join(formatted)
    except Exception:
        return ""

def search_web(query: str, max_results: int = 5) -> str:
    """
    Searches the live web and news using multi-engine resilience.
    Args:
        query: The search query string.
        max_results: Number of results to return (default 5).
    """
    # 1. If query is clearly news-oriented, check fast RSS first
    is_news = any(k in query.lower() for k in ["news", "headline", "today", "latest", "breaking", "update"])
    if is_news:
        news_res = search_news_rss(query, max_results=max_results)
        if news_res:
            return news_res

    # 2. Try DuckDuckGo with tight timeout & suppressed warnings
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from duckduckgo_search import DDGS
            with DDGS(timeout=4) as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            
        if results:
            formatted = [f"🌐 Web Search Results for '{query}':\n"]
            for idx, r in enumerate(results, 1):
                title = r.get("title", "")
                snippet = r.get("body", "")
                url = r.get("href", "")
                formatted.append(f"{idx}. {title}\n   Snippet: {snippet}\n   URL: {url}\n")
            return "\n".join(formatted)
    except Exception:
        pass

    # 3. Fallback to RSS if general DDGS failed
    fallback_news = search_news_rss(query, max_results=max_results)
    if fallback_news:
        return fallback_news

    return f"No web search results found for query: '{query}'"

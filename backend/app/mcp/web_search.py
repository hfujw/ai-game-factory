"""MCP 工具 — 网页搜索引擎（自动选择可用后端）。

优先 Bing（国内可访问），fallback DuckDuckGo。
零 API Key，纯 HTTP 请求。
"""

import urllib.request
import urllib.parse
import json
import logging

logger = logging.getLogger("mcp.web_search")


def _search_bing(query: str, max_results: int = 5) -> list[dict]:
    """Bing 搜索。国内可访问，免费。"""
    url = f"https://www.bing.com/search?{urllib.parse.urlencode({'q': query})}"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        results = []
        # 从 Bing 搜索结果页提取标题和摘要
        import re
        # 匹配 Bing 的搜索结果块
        items = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)
        for item in items[:max_results]:
            title_m = re.search(r'<h2[^>]*><a[^>]*>(.*?)</a>', item, re.DOTALL)
            snippet_m = re.search(r'<p[^>]*>(.*?)</p>', item, re.DOTALL)
            url_m = re.search(r'<a[^>]*href="(https?://[^"]*)"', item)
            if title_m:
                results.append({
                    "title": re.sub(r'<[^>]+>', '', title_m.group(1)),
                    "snippet": re.sub(r'<[^>]+>', '', snippet_m.group(1)) if snippet_m else "",
                    "url": url_m.group(1) if url_m else "",
                })

        logger.info("Bing search '%s': %d results", query[:40], len(results))
        return results[:max_results]

    except Exception as e:
        logger.warning("Bing search failed: %s", e)
        return []


def _search_ddg(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo（海外 fallback）。"""
    url = f"https://api.duckduckgo.com/?{urllib.parse.urlencode({'q': query, 'format': 'json', 'no_html': 1})}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "time-pixels/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = []
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", query),
                "snippet": data.get("AbstractText", ""),
                "url": data.get("AbstractURL", ""),
            })
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and "Text" in topic:
                results.append({
                    "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                    "snippet": topic.get("Text", ""),
                    "url": topic.get("FirstURL", ""),
                })
        return [r for r in results if r["snippet"]][:max_results]
    except Exception:
        return []


def search(query: str, max_results: int = 5) -> list[dict]:
    """网页搜索。先 Bing，失败则 DuckDuckGo。返回 [{title, snippet, url}, ...]。"""
    results = _search_bing(query, max_results)
    if not results:
        results = _search_ddg(query, max_results)
    return results

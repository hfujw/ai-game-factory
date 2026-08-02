"""MCP 工具 — DuckDuckGo 网页搜索。

无 API Key，纯 HTTP 请求。返回标题+摘要+URL。
用于 crawler 补充检索，不替代 DeepSeek 兜底。
"""

import urllib.request
import urllib.parse
import json
import logging

logger = logging.getLogger("mcp.web_search")

DDG_URL = "https://api.duckduckgo.com/"


def search(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo Instant Answer API。返回 [{title, snippet, url}, ...]。

    注意：这是免费 API，没有速率限制但结果数量有限。
    如果 DuckDuckGo 挂了，返回空列表，调用方应 fallback。
    """
    params = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "no_html": 1,
        "skip_disambig": 1,
    })
    url = f"{DDG_URL}?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "time-pixels/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = []

        # Abstract（摘要）
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", query),
                "snippet": data.get("AbstractText", ""),
                "url": data.get("AbstractURL", ""),
            })

        # RelatedTopics
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and "Text" in topic:
                results.append({
                    "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                    "snippet": topic.get("Text", ""),
                    "url": topic.get("FirstURL", ""),
                })

        # 去重（按 URL）
        seen = set()
        unique = []
        for r in results:
            if r["url"] not in seen and r["snippet"]:
                seen.add(r["url"])
                unique.append(r)

        logger.info("DDG search '%s': %d results", query[:40], len(unique))
        return unique[:max_results]

    except Exception as e:
        logger.warning("DDG search failed for '%s': %s", query[:40], e)
        return []

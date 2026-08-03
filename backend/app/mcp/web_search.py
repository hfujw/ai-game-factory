"""MCP 工具 — 网页搜索引擎（自动选择可用后端）。

优先 Bing（国内可访问），fallback DuckDuckGo。
零 API Key，纯 HTTP 请求。
"""

import urllib.request
import urllib.parse
import json
import html as html_mod
import logging

logger = logging.getLogger("mcp.web_search")


def _search_bing(query: str, max_results: int = 5) -> list[dict]:
    """Bing 搜索。用 html.parser 替代纯正则，更稳定。"""
    url = f"https://www.bing.com/search?{urllib.parse.urlencode({'q': query})}"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html_text = resp.read().decode("utf-8", errors="ignore")

        results = []
        import re
        from html.parser import HTMLParser

        class BingParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.results = []
                self.in_item = False; self.in_title = False; self.in_snippet = False
                self.title = ""; self.snippet = ""; self.url = ""
                self.depth = 0; self.snip_depth = 0

            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                cls = attrs_dict.get('class', '')
                if tag == 'li' and 'b_algo' in cls:
                    self.in_item = True; self.title = ""; self.snippet = ""; self.url = ""
                if self.in_item and tag == 'h2':
                    self.in_title = True
                if self.in_item and tag == 'p':
                    self.in_snippet = True; self.snip_depth = 0
                if self.in_item and tag == 'a' and attrs_dict.get('href','').startswith('http'):
                    if not self.url or 'bing.com' not in attrs_dict.get('href',''):
                        self.url = attrs_dict.get('href','')
                if self.in_snippet: self.snip_depth += 1

            def handle_endtag(self, tag):
                if self.in_item and tag == 'h2': self.in_title = False
                if self.in_snippet: self.snip_depth -= 1
                if self.in_snippet and self.snip_depth <= 0: self.in_snippet = False
                if self.in_item and tag == 'li':
                    self.in_item = False
                    if self.title and len(self.snippet) > 10:
                        self.results.append({
                            "title": html_mod.unescape(self.title.strip()),
                            "snippet": html_mod.unescape(self.snippet.strip()),
                            "url": self.url,
                        })

            def handle_data(self, data):
                if self.in_title: self.title += data
                if self.in_snippet: self.snippet += data

        parser = BingParser()
        parser.feed(html_text)

        # Fallback: if parser got nothing, try regex
        if not parser.results:
            items = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html_text, re.DOTALL)
            for item in items[:max_results]:
                title_m = re.search(r'<h2[^>]*><a[^>]*>(.*?)</a>', item, re.DOTALL)
                snippet_m = re.search(r'<p[^>]*>(.*?)</p>', item, re.DOTALL)
                url_m = re.search(r'<a[^>]*href="(https?://[^"]*)"', item)
                if title_m:
                    parser.results.append({
                        "title": html_mod.unescape(re.sub(r'<[^>]+>', '', title_m.group(1))),
                        "snippet": html_mod.unescape(re.sub(r'<[^>]+>', '', snippet_m.group(1))) if snippet_m else "",
                        "url": url_m.group(1) if url_m and 'bing.com' not in url_m.group(1) else "",
                    })

        # Filter Bing internal links, dedup
        seen = set()
        filtered = []
        for r in parser.results:
            url = r.get("url", "")
            if url and ('bing.com' in url or 'microsoft.com/bing' in url): continue
            key = r["title"]
            if key not in seen:
                seen.add(key); filtered.append(r)

        logger.info("Bing search '%s': %d results", query[:40], len(filtered))
        return filtered[:max_results]

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

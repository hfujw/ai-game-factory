"""工具 5: verify — 审查 HTML。硬规则(纯Python) + Playwright 真执行。"""

import logging

logger = logging.getLogger(__name__)


async def tool_verify(html: str, content: dict) -> dict:
    """审查：硬规则(纯Python) + 可用Playwright时真执行。"""
    issues = []

    # Phase 1: 硬规则
    if "</html>" not in html:
        issues.append({"severity": "critical", "category": "incomplete",
                       "description": "HTML不完整，缺少</html>", "fix": "render时精简CSS，确保输出完整"})
    # 修复：只要 html 里不包含 "<script"（不区分大小写）就算缺 JS
    if "<script" not in html.lower():
        issues.append({"severity": "warning", "category": "no_js",
                       "description": "缺少<script>标签，页面无交互", "fix": "添加至少一个<script>标签"})
    if "{visual_css}" in html or "{{" in html:
        issues.append({"severity": "critical", "category": "placeholder",
                       "description": "HTML中包含未填充的占位符", "fix": "render时检查所有{{}}是否已替换"})

    # Phase 2: Playwright真执行（异步，不阻塞事件循环）
    playwright_ok = False
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            js_errors = []
            page.on("pageerror", lambda err: js_errors.append(str(err)))
            await page.set_content(html)
            await page.wait_for_timeout(800)
            if js_errors:
                issues.append({"severity": "warning", "category": "js_error",
                               "description": f"JS报错: {'; '.join(js_errors[:3])}",
                               "fix": "修复JS语法错误"})
            await browser.close()
            playwright_ok = True
    except Exception as e:
        logger.debug("Playwright不可用: %s", e)

    # Phase 3: 事实核查（有content时）
    if content and content.get("blocks"):
        claims_with_source = 0
        total_claims = 0
        for block in content.get("blocks", []):
            for claim in block.get("claims", []):
                total_claims += 1
                if claim.get("source") and claim.get("confidence") != "unknown":
                    claims_with_source += 1
        if total_claims > 0 and claims_with_source / total_claims < 0.5:
            issues.append({"severity": "warning", "category": "fact_check",
                           "description": f"仅有{claims_with_source}/{total_claims}个claim有来源",
                           "fix": "compose时给每个数字/年份标注来源"})

    # 判决
    critical = [i for i in issues if i["severity"] == "critical"]
    passed = len(critical) == 0

    rollback_target = None
    if not passed:
        if any(i["category"] in ("incomplete", "placeholder") for i in critical):
            rollback_target = "render"
        else:
            rollback_target = "compose"

    logger.info("工具=verify | passed=%s | issues=%d | playwright=%s", passed, len(issues), playwright_ok)
    return {"tool": "verify", "passed": passed, "issues": issues, "rollback_target": rollback_target,
            "playwright_ok": playwright_ok}

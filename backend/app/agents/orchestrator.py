"""编排 Agent — 思考→行动→反馈 主循环。

拿到用户输入后，不按固定流程。每一步都是：
1. 🤔 思考：告诉用户"我打算干什么、为什么"
2. 🔧 行动：调用工具
3. 📊 反馈：展示结果
4. 🔄 循环：根据反馈决定下一步
"""

import asyncio
import json
import logging
from app.llm_client import chat, chat_json, _strip_markdown_fence
from app.tools import tool_search, tool_design, tool_compose, tool_render, tool_verify
from app.knowledge.kb import get_event_by_keyword, event_to_search_results

logger = logging.getLogger(__name__)

# ── 预算（估算） ──
TOOL_COST = {"search": 0.03, "design": 0.05, "compose": 0.08, "render": 0.15, "verify": 0.05}

ORCHESTRATOR_SYSTEM_PROMPT = """你是一个视觉叙事引擎。用户给你一个主题，你生成一个好看的HTML页面。

【工具】
- search(query, reason) → 搜素材
- design → 分析素材，决定用什么叙事形式
- compose → 写文案，每个事实标来源
- render → 生成HTML
- verify → Playwright审查

【硬规则】
- render之后必须verify
- verify说过 → 停止，输出final
- verify说不过 → 退给render/compose/design，你来决定退给谁
- 最多20步，总预算¥1，最多搜8次
- HTML截断(缺</html>) → 自动失败，必须重render
- 同一工具连续3次失败 → 必须换策略

【决策指南】
- 先search还是先design？简单主题可以直接design，复杂主题先search
- 素材够了就别再search了
- verify说"visual不好看"→退render；"来源不足"→退compose；"形式不合适"→退design
- 预算紧张时用最简方案
- 【诚实模式】如果系统提示素材与主题不相关：禁止 design/compose，直接 render 一个诚实页面（标注资料有限，不编造），只生成一次不重试

输出JSON。thought 字段是你每步决策前的内心独白。
- 第1步：可以介绍主题背景（如"我对这个话题的了解是…"）
- 第2步及以后：禁止重复"用户想了解XXX""我对XXX不太熟悉"等开场白。直接从上一
  步的结果开始——"上一步搜到了5条素材，但都是朱姓百科而非朱子钦本人，所以现在…"
- 不要像个复读机每次重新介绍主题。像一个人在持续思考，不是每次都重启。
- 好例子（第3步）："连续两次搜索都只返回朱姓泛化内容，没有增量信息。继续搜没意义了，
  素材评估显示与'朱子钦'无直接关联。用朱字释义做一个诚实的汉字文化页。"
- 坏例子（第3步）："用户想了解朱子钦这个人。我对这个名字不太熟悉。搜索结果显示…"

{"thought":"3-4句自然内心独白","tool":"search|design|compose|render|verify","params":{}}"""


async def orchestrator_node(state: dict) -> dict:
    """主循环：思考→行动→反馈→循环。思考先推到前端，用户看到后AI再行动。"""
    user_input = state.get("user_input", "")
    push = state.get("_push")

    ctx = {
        "user_input": user_input,
        "material": [],
        "design": None,
        "content": None,
        "html": "",
        "visual": None,
        "steps": 0,
        "max_steps": 20,
        "budget_spent": 0.0,
        "budget_total": 1.0,
        "passed": False,
        "issues": [],
        "tool_history": [],
    }

    kb_event = get_event_by_keyword(user_input)
    if kb_event:
        ctx["material"].extend(event_to_search_results(kb_event))

    while ctx["steps"] < ctx["max_steps"] and ctx["budget_spent"] < ctx["budget_total"]:

        # 0. 诚实模式 render 后强制 verify
        if ctx.get("force_verify"):
            ctx.pop("force_verify")
            decision = {"thought": "诚实模式：自动验证", "tool": "verify", "params": {}}
        else:
            # 1. 让LLM决定下一步
            decision = await _decide(ctx)

        # 2. ⚡ 思考先推到前端（await 确保用户看到了）
        thought = decision.get("thought", "")
        tool_name = decision.get("tool", "search")
        if push:
            await push({"type": "thinking", "step": ctx["steps"] + 1, "thought": thought,
                        "tool": tool_name, "budget": ctx["budget_spent"]})

        # 3. 推"进行中"，启动心跳
        if push:
            await push({"type": "tool_result", "step": ctx["steps"] + 1, "tool": tool_name,
                        "summary": f"执行中…（{tool_name}）", "budget": ctx["budget_spent"]})
        # 心跳：长操作期间每 4 秒推一次 pulse
        async def heartbeat():
            for _ in range(15):
                await asyncio.sleep(4)
                if push:
                    await push({"type": "tool_result", "step": ctx["steps"] + 1, "tool": tool_name,
                                "summary": f"执行中…（{tool_name}）", "budget": ctx["budget_spent"]})
        hb = asyncio.create_task(heartbeat())

        # 4. 执行工具
        result = await _execute_tool(tool_name, decision.get("params", {}), ctx)
        hb.cancel()

        # 5. 推送结果
        ctx["steps"] += 1
        ctx["tool_history"].append({"step": ctx["steps"], "thought": thought,
                                     "tool": tool_name, "result_summary": _summarize(result)})
        if push:
            await push({"type": "tool_result", "step": ctx["steps"], "tool": tool_name,
                        "summary": _summarize(result), "budget": ctx["budget_spent"]})

        # 5. 搜索后评估素材质量
        if tool_name == "search" and not ctx.get("honest_mode"):
            eval_result = _evaluate_material(ctx["material"], ctx["user_input"])
            if eval_result["level"] in ("low", "none"):
                ctx["honest_mode"] = True
                ctx["material_level"] = eval_result
                if push:
                    await push({"type": "thinking", "step": ctx["steps"],
                                "thought": f"⚠️ {eval_result['reason']}。进入诚实模式：不编造内容，基于现有素材做降级呈现。",
                                "tool": "system", "budget": ctx["budget_spent"]})

        # 6. 硬检查
        if tool_name == "render":
            if not result.get("complete"):
                ctx["issues"].append("render自动失败：HTML截断")
                ctx["render_fail_count"] = ctx.get("render_fail_count", 0) + 1
            # 诚实模式：render 后强制 verify，不让 LLM 再决定
            if ctx.get("honest_mode") and result.get("complete"):
                ctx["force_verify"] = True

        if tool_name == "verify":
            ctx["passed"] = result.get("passed", False)
            ctx["issues"] = result.get("issues", [])
            if ctx["passed"] or ctx.get("honest_mode"):
                if ctx.get("honest_mode"):
                    logger.info("诚实模式=通过（跳过内容匹配检查）")
                else:
                    logger.info("编排=通过！%d步 ¥%.2f", ctx["steps"], ctx["budget_spent"])
                if push:
                    await push({"type": "complete", "html": ctx.get("html", ""),
                                "steps": ctx["steps"], "budget": ctx["budget_spent"]})
                    if ctx.get("honest_mode"):
                        await push({"type": "thinking", "step": ctx["steps"],
                                    "thought": "这是基于现有资料的诚实呈现，已标注信息局限。",
                                    "tool": "system", "budget": ctx["budget_spent"]})
                return {"status": "success", "html": ctx.get("html", ""),
                        "steps": ctx["steps"], "budget": ctx["budget_spent"],
                        "honest_mode": ctx.get("honest_mode", False),
                        "tool_history": ctx["tool_history"]}

            # ❌ verify 没通过 → 强制回退，不让 LLM 决定
            ctx["render_fail_count"] = ctx.get("render_fail_count", 0) + 1
            rollback = result.get("rollback_target", "render")
            logger.warning("verify失败 #%d → 强制回退到 %s", ctx["render_fail_count"], rollback)

            # 连续2次 verify 失败 → 不是技术问题，是素材问题，直接终止
            if ctx["render_fail_count"] >= 2:
                logger.warning("连续%d次verify失败，素材不足，强制终止", ctx["render_fail_count"])
                if push:
                    await push({"type": "thinking", "step": ctx["steps"],
                                "thought": f"连续{ctx['render_fail_count']}次生成均被审查驳回——不是技术问题，是现有素材与用户主题不匹配。建议换一个信息更充分的主题。",
                                "tool": "system", "budget": ctx["budget_spent"]})
                return {"status": "failed", "steps": ctx["steps"], "budget": ctx["budget_spent"],
                        "issues": ctx["issues"], "reason": "素材不匹配，多次生成被驳回"}

            # 强制回退：不让 LLM 决定下一步，直接跳回指定工具
            if push:
                await push({"type": "thinking", "step": ctx["steps"],
                            "thought": f"审查发现{len(ctx['issues'])}个问题，系统强制回退到「{rollback}」重做。",
                            "tool": "system", "budget": ctx["budget_spent"]})
            ctx["force_next_tool"] = rollback
            continue  # 跳过 _decide，直接进入下一轮循环执行回退工具

        # 6. 强制回退执行
        if ctx.get("force_next_tool"):
            tool_name = ctx.pop("force_next_tool")
            # 继续执行这个工具（不通过 _decide 决策）
            if push:
                await push({"type": "tool_result", "step": ctx["steps"] + 1, "tool": tool_name,
                            "summary": f"强制回退执行 {tool_name}…", "budget": ctx["budget_spent"]})
            result = await _execute_tool(tool_name, decision.get("params", {}), ctx)
            ctx["steps"] += 1
            ctx["tool_history"].append({"step": ctx["steps"], "tool": tool_name,
                                        "result_summary": _summarize(result)})
            if push:
                await push({"type": "tool_result", "step": ctx["steps"], "tool": tool_name,
                            "summary": _summarize(result), "budget": ctx["budget_spent"]})
            continue  # 回退执行完，重新进入循环（下一步会走正常的 verify）

    # 循环结束但没通过 → 推"死亡报告"到 DecisionLog
    search_count = sum(1 for h in ctx['tool_history'] if h['tool'] == 'search')
    reason = f"搜了 {search_count} 次没找到直接素材" if search_count >= 2 else "多次生成尝试仍不满意"
    logger.info("编排=超限 %d步 ¥%.2f passed=%s reason=%s", ctx["steps"], ctx["budget_spent"], ctx["passed"], reason)
    if push:
        await push({"type": "thinking", "step": ctx["steps"],
                    "thought": f"⚠️ 无法完成「{ctx['user_input']}」：{reason}。建议换一个信息更充分的主题试试。",
                    "tool": "system", "budget": ctx["budget_spent"]})
        await push({"type": "failed", "reason": reason,
                    "steps": ctx["steps"], "budget": ctx["budget_spent"]})
    return {"status": "failed", "steps": ctx["steps"], "budget": ctx["budget_spent"],
            "issues": ctx["issues"], "tool_history": ctx["tool_history"]}


def _evaluate_material(material: list, user_input: str) -> dict:
    """外置评估：素材够不够、关不相关。不是 LLM 判断。"""
    if not material:
        return {"level": "none", "reason": "零素材", "suggestion": "诚实说明素材不足"}
    query = user_input.lower()
    # 检查多少素材里包含用户输入的关键词
    relevant = [m for m in material if any(
        w in (m.get("title","") + m.get("snippet", m.get("content",""))).lower()
        for w in query.split() if len(w) >= 2
    )]
    if len(relevant) >= 3:
        return {"level": "high", "reason": f"{len(relevant)}条直接相关", "suggestion": "正常生成"}
    elif len(relevant) >= 1:
        return {"level": "medium", "reason": f"仅{len(relevant)}条弱相关", "suggestion": "降级：基于现有素材做关联呈现"}
    else:
        return {"level": "low", "reason": "素材与主题不直接相关", "suggestion": "诚实模式：生成资料局限声明页"}


async def _decide(ctx: dict) -> dict:
    """让LLM决定：下一步干什么。"""
    # 构建简洁上下文
    # 素材摘要（让LLM知道有什么内容）
    material_brief = ""
    if ctx['material']:
        titles = [r.get('title','')[:40] for r in ctx['material'][:5]]
        material_brief = f"素材来源：{' | '.join(titles)}\n"

    # 最近结果详情
    recent_detail = ""
    for h in ctx['tool_history'][-3:]:
        recent_detail += f"  [{h['tool']}] {h.get('result_summary', '')[:80]}\n"

    # 验证问题详情
    issues_detail = ""
    if ctx['issues']:
        issues_detail = "\n".join(
            f"  - [{i.get('severity','?')}] {i.get('description','')[:100]}"
            for i in ctx['issues'][:3]
        )

    summary = f"""用户想了解的具体主题：{ctx['user_input']}
⚠️ 必须围绕这个主题生成，不要偏离或扩展。
步骤：{ctx['steps']}/{ctx['max_steps']} | 预算：¥{ctx['budget_spent']:.2f}/¥{ctx['budget_total']:.0f}
{material_brief}已有素材：{len(ctx['material'])}条 | 搜索次数：{sum(1 for h in ctx['tool_history'] if h['tool']=='search')}
已设计：{ctx['design'] is not None} | 已写文案：{ctx['content'] is not None}
HTML长度：{len(ctx.get('html',''))}字符 | 上次验证：{'通过' if ctx['passed'] else '未通过'}
最近步骤：
{recent_detail if recent_detail else '  （无）'}
最近问题：
{issues_detail if issues_detail else '  （无）'}
"""

    if ctx.get("force_strategy_change"):
        summary += "\n⚠️ 连续失败！必须换策略，不能重试同一个工具。"

    if ctx.get("honest_mode"):
        eval_result = ctx.get("material_level", {})
        summary += f"\n⚠️【诚实模式】{eval_result.get('reason','素材不足')}。禁止 design/compose，直接 render 一个诚实页面。不要编造。只生成一次。"

    # 搜索死循环防护：连续2次搜空就强制禁止
    search_count = sum(1 for h in ctx['tool_history'] if h['tool'] == 'search')
    recent_searches = [h for h in ctx['tool_history'][-2:] if h['tool'] == 'search']
    all_empty = all("0条" in h.get("result_summary", "") or "不相关" in h.get("result_summary", "") or "未找到" in h.get("result_summary", "") for h in recent_searches)
    if search_count >= 3 or (search_count >= 2 and all_empty):
        summary += f"\n⚠️ 已搜索 {search_count} 次（最近2次无结果），禁止再搜！基于现有素材做设计，或诚实说素材不足。"

    try:
        result = await chat(summary, system=ORCHESTRATOR_SYSTEM_PROMPT, temperature=0.5)
        result = _strip_markdown_fence(result)
        decision = json.loads(result)
        # 兜底：如果 LLM 还是重复开场白，截断
        thought = decision.get("thought", "")
        if ctx["steps"] > 0:
            redundant = [f"想了解{ctx['user_input']}", f"对{ctx['user_input']}这个名字",
                        "我不确定他是谁", "我不确定具体是谁", "我对这个人没有太多"]
            for pattern in redundant:
                if pattern in thought[:80]:
                    # 找第一个"因此""所以""我决定""现在"截断
                    for marker in ["因此", "所以", "我决定", "接下来", "现在", "基于", "上一步", "搜索", "素材"]:
                        idx = thought.find(marker, 20)
                        if idx > 0 and idx < 120:
                            decision["thought"] = thought[idx:]
                            break
                    break
        return decision
    except Exception as e:
        logger.warning("编排决策失败: %s, 降级为search", e)
        return {"thought": f"决策异常({e})，先搜素材", "tool": "search",
                "params": {"query": ctx["user_input"], "reason": "初始搜索", "depth": "quick"}}


async def _execute_tool(tool_name: str, params: dict, ctx: dict) -> dict:
    """执行工具调用，更新ctx。"""
    cost = TOOL_COST.get(tool_name, 0.05)
    ctx["budget_spent"] += cost

    if tool_name == "search":
        result = tool_search(
            query=params.get("query", ctx["user_input"]),
            reason=params.get("reason", ""),
            depth=params.get("depth", "quick"),
            existing_material=ctx["material"],
        )
        ctx["material"].extend(result.get("results", []))
        return result

    elif tool_name == "design":
        result = await tool_design(ctx["material"], ctx["user_input"])
        ctx["design"] = result
        return result

    elif tool_name == "compose":
        result = await tool_compose(ctx["material"], ctx["design"] or {}, ctx["user_input"])
        ctx["content"] = result
        return result

    elif tool_name == "render":
        result = await tool_render(ctx["design"] or {}, ctx["content"] or {}, ctx.get("visual"))
        if result.get("html"):
            ctx["html"] = result["html"]
        return result

    elif tool_name == "verify":
        result = tool_verify(ctx.get("html", ""), ctx.get("content") or {})
        return result

    return {"error": f"未知工具: {tool_name}"}


def _summarize(result: dict) -> str:
    """工具结果的一句话摘要。"""
    tool = result.get("tool", "")
    if tool == "search":
        n = result.get("count", 0)
        return f"搜索结束，共找到 {n} 条可信素材" if n > 0 else "搜索结束，未找到新素材"
    elif tool == "design":
        comps = result.get("components", [])
        r = result.get("rationale", "")
        return f"选定「{'、'.join(comps)}」——{r[:60]}" if comps else f"设计完成：{r[:80]}"
    elif tool == "compose":
        n = len(result.get("blocks", []))
        title = result.get("title", "")
        return f"文案完成，{n} 个内容块——{title or '已生成'}"
    elif tool == "render":
        length = result.get("length", 0)
        ok = result.get("complete")
        return f"HTML 生成完毕，{length} 字符，结构{'完整' if ok else '截断需重试'}"
    elif tool == "verify":
        if result.get("passed"):
            return "Playwright 审查通过，所有检查项正常"
        n = len(result.get("issues", []))
        return f"审查发现 {n} 个问题，需{'重生成' if result.get('rollback_target') == 'render' else '重写文案' if result.get('rollback_target') == 'compose' else '重新设计'}"
    return str(result.get("error", "完成"))

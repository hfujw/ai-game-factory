"""Designer Agent —— 合并 design + compose，内部自循环。

design 选了不合适的叙事形式 → compose 硬写 → verify 不通过 → 回退重来。
合并后 Agent 内部：设计 → 试写 → 自检素材匹配度 → 不通过换形式 → 重写。
不依赖 orchestrator 来做 "design 失败 → 重 design" 的判断。
"""

import logging
from app.tools.design import tool_design
from app.tools.compose import tool_compose

logger = logging.getLogger(__name__)

# design 组件需要的素材量——低于阈值就降级
COMPONENT_MIN_MATERIAL: dict[str, int] = {
    "timeline": 3,      # 时间轴需要至少 3 个时间点
    "comparison": 3,    # 对比需要至少 3 个对比维度
    "cards": 1,         # 卡片集 1 条素材也能做
    "flowchart": 2,     # 流程图需要至少 2 个步骤
    "portrait": 1,      # 人物画像 1 条也行
    "datapanel": 2,     # 数据面板需要至少 2 个数据点
    "encyclopedia": 0,  # 百科条目不需要素材
}


class DesignerAgent:
    """设计 + 文案 Agent —— 内部决策循环。

    合并了 design 和 compose 两个工具：
    1. 分析素材 → 选叙事形式
    2. 自检：选的形式跟素材量匹配吗？
    3. 写文案 → 标来源
    4. 自检：来源覆盖率够吗？
    5. 不通过 → 换形式重试（最多 2 次）
    """

    async def run(
        self,
        material: list[dict],
        user_input: str,
        push=None,
        session_records=None,
    ) -> dict:
        """对外接口——返回 {design, content}，orchestrator 无感。"""
        mat_count = len(material)

        for attempt in range(2):
            # 1. 设计叙事形式
            design = await tool_design(material, user_input, session_records=session_records)

            # 2. 自检：素材量够撑住选定的组件吗？
            if not self._check_design_fit(design, mat_count):
                # 降级：把不适配的组件换成百科全书
                design = self._downgrade_design(design, mat_count)
                # 重新设计（带上降级 hint）
                patched = [{"title": "⚠️ 素材不足，请使用简单形式（如 encyclopedia/cards）",
                            "snippet": f"仅有 {mat_count} 条素材", "content": ""}]
                design = await tool_design(patched, user_input, session_records=session_records)

            # 3. 写文案
            content = await tool_compose(material, design, user_input, session_records=session_records)

            # 4. 自检：来源覆盖率
            coverage = self._source_coverage(content)
            if coverage >= 0.3:  # 30% 即可——LLM 自身知识也算
                logger.info("DesignerAgent=pass | attempt=%d | components=%s | coverage=%.0f%%",
                            attempt + 1, design.get("components", []), coverage * 100)
                return {"tool": "design", "design": design, "content": content, "attempts": attempt + 1}

            logger.info("DesignerAgent=retry | attempt=%d | coverage=%.0f%%", attempt + 1, coverage * 100)

        # 两次都没过 → 降级百科 + 诚实文案
        logger.info("DesignerAgent=fallback |百科降级")
        return self._fallback(material, user_input, session_records)

    # ─── 内部方法 ───

    def _check_design_fit(self, design: dict, material_count: int) -> bool:
        """检查选定的组件是否适配素材量。纯规则，不调 LLM。"""
        components = design.get("components", [])
        for comp in components:
            minimum = COMPONENT_MIN_MATERIAL.get(comp, 1)
            if material_count < minimum:
                return False
        return True

    def _downgrade_design(self, design: dict, material_count: int) -> dict:
        """把素材不够的组件替换为 encyclopedia。"""
        components = design.get("components", [])
        downgraded = []
        for comp in components:
            minimum = COMPONENT_MIN_MATERIAL.get(comp, 1)
            if material_count < minimum:
                if "encyclopedia" not in downgraded:
                    downgraded.append("encyclopedia")
            else:
                downgraded.append(comp)
        if not downgraded:
            downgraded = ["encyclopedia"]
        design["components"] = downgraded
        design["rationale"] = f"素材仅 {material_count} 条，降级为 {'+'.join(downgraded)}"
        return design

    def _source_coverage(self, content: dict) -> float:
        """统计 claims 中有 source 标注的比例。"""
        total = 0
        sourced = 0
        for block in content.get("blocks", []):
            for claim in block.get("claims", []):
                total += 1
                if claim.get("source") and claim.get("confidence", "") != "unknown":
                    sourced += 1
        return sourced / total if total > 0 else 0.0

    async def _fallback(self, material, user_input, session_records) -> dict:
        """降级：百科条目 + 诚实文案。"""
        design = {"tool": "design", "components": ["encyclopedia"],
                  "rationale": "素材不足，降级为百科条目",
                  "structure": "单列百科", "visual_hint": "简洁中性"}
        content = {"tool": "compose", "title": user_input,
                   "subtitle": "基于有限资料的诚实呈现",
                   "blocks": [], "fact_notes": "当前素材不足以生成完整叙事"}
        # 如果有素材，至少做一个百科条目
        if material:
            brief = "\n".join(
                f"- {r.get('title', '')}: {r.get('snippet', r.get('content', ''))[:200]}"
                for r in material[:5]
            )
            design["rationale"] += f"\n可用素材：\n{brief}"
        return {"tool": "design", "design": design, "content": content}

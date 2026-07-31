"""完整 Agent Pipeline 测试 — 从用户输入到游戏出炉。"""
import sys
sys.path.insert(0, ".")

from app.graph.state import initial_state
from app.graph.workflow import build_workflow

print("=" * 60)
print("🎮 AI 游戏工坊 — Agent Pipeline 测试")
print("=" * 60)

# 测试事件：在验证知识库里
user_input = "1940年 Turing 破译 Enigma"
print(f"\n📝 用户输入: {user_input}")

state = initial_state(user_input)
workflow = build_workflow()

print("\n⏳ 运行 Agent Pipeline...\n")
result = workflow.invoke(state)

# 逐项展示结果
print("=" * 60)
print("📊 结果")
print("=" * 60)

logs = result.get("agent_logs", [])
if not logs:
    print("  ⚠️ 无 Agent 日志（状态合并可能有问题）")
else:
    for log in logs:
        agent = log.get("agent", "?")
        action = log.get("action", "?")
        detail = log.get("detail", "")
        emoji = {"crawler": "🔍", "planner": "🎯", "writer": "✍️", "coder": "💻", "reviewer": "🔎", "artist": "🎨"}.get(agent, "❓")
        print(f"  {emoji} {agent}: {action}")
        if detail:
            print(f"      └─ {detail[:120]}")

print(f"\n📋 状态: {result.get('status', '?')}")
print(f"🧩 谜题类型: {result.get('puzzle_type', '?')}")
print(f"📊 素材评分: {result.get('material_score', '?')}")
print(f"✅ 审查通过: {result.get('review_passed', '?')}")
if result.get("review_details"):
    d = result["review_details"]
    print(f"   代码审查: {d.get('code_ok')}, 历史审查: {d.get('history_ok')}, 可玩性: {d.get('playable_ok')}")
print(f"🔁 重试次数: {result.get('retry_count', '?')}")

script = result.get("game_script", "")
if script:
    print(f"\n📖 剧本预览 ({len(script)} 字):")
    print("---")
    print(script[:400])
    print("---")

code = result.get("styled_code") or result.get("game_code", "")
if code:
    # 保存到文件
    output_path = "test_output.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"\n🎮 游戏代码已保存: {output_path} ({len(code)} 字)")
    print(f"   在浏览器打开 {output_path} 即可试玩")

if result.get("error_message"):
    print(f"\n⚠️ 错误: {result['error_message']}")
    if result.get("suggestions"):
        print("   建议尝试:")
        for s in result["suggestions"]:
            print(f"   → {s}")

print("\n" + "=" * 60)
print("✅ 测试完成")

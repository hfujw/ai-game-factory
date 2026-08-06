"""Demo 模块 — 预生成 HTML 页面管理。

demo 页面存放在 backend/demos/，文件名 = 主题名.html。
上层路由在 main.py 中，这里只放纯逻辑——和其他模块（tools、llm_client）一致。
"""

import os

DEMOS_DIR = os.path.join(os.path.dirname(__file__), "..", "demos")

# 和前端 App.jsx DEMO_TOPICS 保持同步
DEMO_TOPICS = [
    "秦始皇修长城",
    "Turing 破译 Enigma",
    "Python 装饰器",
    "郑和下西洋",
    "世界杯历届冠军",
]


def _fallback_html(name: str) -> str:
    """Demo HTML 未就绪时的占位页。"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>{name}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ display:flex; align-items:center; justify-content:center; min-height:100vh;
    background:linear-gradient(135deg,#0a0a0a 0%,#1a1a2e 50%,#0a0a0a 100%);
    color:#e0e0e0; font-family:'PingFang SC','Noto Serif SC',serif; }}
  .card {{ text-align:center; padding:48px 32px; max-width:480px; }}
  h1 {{ font-size:2rem; font-weight:300; letter-spacing:0.08em; margin-bottom:16px;
    background:linear-gradient(135deg,#c9a96e,#e8d5a3); -webkit-background-clip:text;
    -webkit-text-fill-color:transparent; }}
  p {{ color:#888; font-size:0.95rem; line-height:1.8; }}
</style></head>
<body>
  <div class="card">
    <h1>「{name}」</h1>
    <p>这个演示页面还在策展中，稍后回来看看。</p>
  </div>
</body>
</html>"""


def load_demo_html(name: str) -> tuple[str | None, bool]:
    """读取 demo HTML。返回 (html, cached)。name 不在 DEMO_TOPICS 中时返回 (None, False)。"""
    if name not in DEMO_TOPICS:
        return None, False

    filepath = os.path.join(DEMOS_DIR, f"{name}.html")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read(), True

    return _fallback_html(name), False


def list_demo_status() -> list[dict]:
    """返回每个 demo 的就绪状态。"""
    return [
        {
            "name": name,
            "ready": os.path.exists(os.path.join(DEMOS_DIR, f"{name}.html")),
        }
        for name in DEMO_TOPICS
    ]

"""项目配置常量 — 所有魔法数字的唯一定义点。"""

# Agent 重试次数
MAX_REVIEW_RETRIES = 3

# Crawler 素材评分阈值
MIN_MATERIAL_CHARS = 100        # 最少字符数才算"有素材"
UNVERIFIED_SCORE_DENOMINATOR = 3000  # 未验证素材评分分母
UNVERIFIED_SCORE_CAP = 0.85     # 未验证素材最高评分

# LLM 调用
LLM_TIMEOUT_SECONDS = 120
LLM_MAX_RETRIES = 2

# 前端推荐数量
EVENT_CHIPS_COUNT = 5
SUGGESTIONS_COUNT = 4

# WebSocket
SESSION_ID_LENGTH = 8

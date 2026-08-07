"""速率限制器 — IP 级免费试用 + 全站日预算硬帽。

公网开放后，Key 在后端意味着你替所有人买单。这个模块给每条防线设上限：
- 全站每天最多花 ¥5（DAILY_BUDGET），到了就拒绝所有新生成
- 每个 IP 每天只能试用 1 次（TRIALS_PER_IP），想看更多引导到 demo

数据全在内存——服务重启后清零。对作品集项目来说够用，不需要 Redis。
"""

import asyncio
from datetime import date
import logging

logger = logging.getLogger(__name__)

DAILY_BUDGET = 5.0        # 全站日预算（元）
TRIALS_PER_IP = 1          # 每 IP 每天免费试用次数
LOCALHOST_IPS = {"127.0.0.1", "::1", "localhost"}


class RateLimiter:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._successful_trials: dict[str, int] = {}  # {ip: 成功次数}
        self._today: str = str(date.today())
        self._daily_spent: float = 0.0
        self._total_generations: int = 0

    # ── 内部 ──

    async def _reset_if_new_day(self):
        today = str(date.today())
        if today != self._today:
            async with self._lock:
                if today != self._today:  # double-check
                    logger.info(
                        "新的一天，重置限流 | 昨日 %d 次生成，花费 ¥%.2f",
                        self._total_generations, self._daily_spent,
                    )
                    self._today = today
                    self._successful_trials.clear()
                    self._daily_spent = 0.0
                    self._total_generations = 0

    # ── 查询 ──

    async def daily_budget_remaining(self) -> float:
        await self._reset_if_new_day()
        return max(0.0, DAILY_BUDGET - self._daily_spent)

    def trials_used(self, ip: str) -> int:
        """该 IP 今天已成功使用的试用次数（只读快照，不要求精确）。"""
        return self._successful_trials.get(ip, 0)

    @property
    def stats(self) -> dict:
        return {
            "daily_budget": DAILY_BUDGET,
            "daily_spent": round(self._daily_spent, 4),
            "daily_remaining": round(max(0.0, DAILY_BUDGET - self._daily_spent), 4),
            "total_generations_today": self._total_generations,
            "trials_per_ip": TRIALS_PER_IP,
        }

    # ── 准入 ──

    async def can_generate(self, ip: str) -> tuple[bool, str]:
        """检查是否允许生成。返回 (允许, 原因)。"""
        await self._reset_if_new_day()

        # 本地开发不受限
        if ip in LOCALHOST_IPS:
            return True, ""

        async with self._lock:
            if self._daily_spent >= DAILY_BUDGET:
                return False, "今日全站免费额度已用完，明天再来吧 🎨"

            if self._successful_trials.get(ip, 0) >= TRIALS_PER_IP:
                return False, "您今日的免费试用次数已用完，明天可以再来"

        return True, ""

    # ── 记录 ──

    async def record_success(self, ip: str):
        """记录一次成功生成（只计成功，失败不扣次数）。"""
        if ip not in LOCALHOST_IPS:
            async with self._lock:
                self._successful_trials[ip] = self._successful_trials.get(ip, 0) + 1
                self._total_generations += 1
            logger.info("IP %s 试用成功 %d/%d", ip, self._successful_trials[ip], TRIALS_PER_IP)

    async def record_cost(self, amount: float):
        """记录实际花费（生成结束后调用）。"""
        async with self._lock:
            self._daily_spent += amount
        logger.info(
            "花费 ¥%.4f | 累计 ¥%.4f / ¥%.0f（剩余 ¥%.2f）",
            amount, self._daily_spent, DAILY_BUDGET, max(0.0, DAILY_BUDGET - self._daily_spent),
        )


rate_limiter = RateLimiter()

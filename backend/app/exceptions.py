"""统一异常体系 — 用类型替代字符串匹配做错误分类。

每个异常都有 user_message（对外展示）和原始 message（记日志）。
main.py 的 except 分支用 isinstance 匹配类型，不再靠 _friendly_error 猜。
"""


class AppError(Exception):
    """应用根异常。"""
    def __init__(self, message: str, user_message: str | None = None):
        super().__init__(message)
        self.user_message = user_message or message


class ConfigError(AppError):
    """配置错误（启动时校验失败）。"""
    pass


class LLMError(AppError):
    """LLM API 调用失败（通用）。"""
    pass


class LLMTimeoutError(LLMError):
    """LLM 请求超时。"""
    pass


class SearchError(AppError):
    """搜索失败。"""
    pass


class RenderError(AppError):
    """HTML 生成失败。"""
    pass


class RateLimitError(AppError):
    """速率限制拒绝。"""
    pass

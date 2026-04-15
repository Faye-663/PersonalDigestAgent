class PersonalDigestError(Exception):
    """应用级基础异常。"""


class ConfigurationError(PersonalDigestError):
    """配置不完整或格式错误。"""


class ProviderError(PersonalDigestError):
    """外部依赖调用失败。"""


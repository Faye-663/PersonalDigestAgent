from __future__ import annotations

import logging


class ContextDefaultsFilter(logging.Filter):
    """为结构化日志补齐默认字段，避免缺失 extra 时格式化失败。"""

    DEFAULTS = {
        "job_id": "-",
        "source_id": "-",
        "article_id": "-",
        "stage": "-",
        "status": "-",
        "duration_ms": "-",
        "error": "-",
    }

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in self.DEFAULTS.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


def configure_logging(level: int = logging.INFO) -> None:
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s "
        "job_id=%(job_id)s source_id=%(source_id)s article_id=%(article_id)s "
        "stage=%(stage)s status=%(status)s duration_ms=%(duration_ms)s error=%(error)s"
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(ContextDefaultsFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)


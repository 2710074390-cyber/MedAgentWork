#!/usr/bin/env python3
"""
telemetry.py — MedAgentWork 结构化日志模块 v1.0

提供结构化日志记录，支持：
- 批次生命周期事件
- 门禁检查结果
- 性能指标
- 错误追踪

用法:
    from scripts.telemetry import get_logger, log_batch_event
    
    logger = get_logger("medgen")
    logger.info("Starting question generation", extra={"batch_id": "batch035"})
    
    log_batch_event("batch035", "agent2_start", {"subject": "内科学"})
"""

import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# 中国标准时间 UTC+8
CST = timezone(timedelta(hours=8))

# 日志格式
LOG_FORMAT = "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"
JSON_LOG_FORMAT = "%(message)s"

# 日志级别映射
LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class StructuredFormatter(logging.Formatter):
    """结构化JSON日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(CST).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # 添加额外字段
        if hasattr(record, "batch_id"):
            log_entry["batch_id"] = record.batch_id
        if hasattr(record, "event"):
            log_entry["event"] = record.event
        if hasattr(record, "metadata"):
            log_entry["metadata"] = record.metadata
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
            
        # 添加异常信息
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }
        
        return json.dumps(log_entry, ensure_ascii=False)


class HumanReadableFormatter(logging.Formatter):
    """人类可读的日志格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        # 基础信息
        timestamp = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname.ljust(8)
        name = record.name[:20].ljust(20)
        
        # 消息
        message = record.getMessage()
        
        # 额外信息
        extras = []
        if hasattr(record, "batch_id"):
            extras.append(f"batch={record.batch_id}")
        if hasattr(record, "event"):
            extras.append(f"event={record.event}")
        if hasattr(record, "duration_ms"):
            extras.append(f"duration={record.duration_ms}ms")
        
        extra_str = f" [{', '.join(extras)}]" if extras else ""
        
        return f"{timestamp} | {name} | {level} | {message}{extra_str}"


def get_logger(
    name: str,
    level: str = "INFO",
    log_file: Path | None = None,
    json_format: bool = False,
) -> logging.Logger:
    """
    获取配置好的日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 可选的日志文件路径
        json_format: 是否使用JSON格式
    
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加handler
    if logger.handlers:
        return logger
    
    logger.setLevel(LEVEL_MAP.get(level.upper(), logging.INFO))
    
    # 控制台handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(LEVEL_MAP.get(level.upper(), logging.INFO))
    
    if json_format:
        console_handler.setFormatter(StructuredFormatter())
    else:
        console_handler.setFormatter(HumanReadableFormatter())
    
    logger.addHandler(console_handler)
    
    # 文件handler（可选）
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(LEVEL_MAP.get(level.upper(), logging.INFO))
        file_handler.setFormatter(StructuredFormatter())
        logger.addHandler(file_handler)
    
    return logger


def log_batch_event(
    batch_id: str,
    event: str,
    metadata: dict[str, Any] | None = None,
    level: str = "INFO",
) -> None:
    """
    记录批次事件
    
    Args:
        batch_id: 批次ID
        event: 事件名称
        metadata: 可选的元数据
        level: 日志级别
    """
    logger = get_logger("batch_events")
    
    # 创建日志记录
    record = logger.makeRecord(
        name=logger.name,
        level=LEVEL_MAP.get(level.upper(), logging.INFO),
        fn="",
        lno=0,
        msg=f"Batch event: {event}",
        args=(),
        exc_info=None,
    )
    
    # 添加额外字段
    record.batch_id = batch_id
    record.event = event
    record.metadata = metadata or {}
    
    logger.handle(record)


def log_gate_check(
    batch_id: str,
    gate: str,
    status: str,
    reason: str,
    duration_ms: float | None = None,
) -> None:
    """
    记录门禁检查结果
    
    Args:
        batch_id: 批次ID
        gate: 门禁名称 (GATE-A2, GATE-A3, etc.)
        status: 状态 (PASS, BLOCKED)
        reason: 原因
        duration_ms: 可选的执行时长（毫秒）
    """
    logger = get_logger("gate_checks")
    
    metadata = {
        "gate": gate,
        "status": status,
        "reason": reason,
    }
    
    if duration_ms is not None:
        metadata["duration_ms"] = duration_ms
    
    record = logger.makeRecord(
        name=logger.name,
        level=LEVEL_MAP.get("INFO", logging.INFO),
        fn="",
        lno=0,
        msg=f"Gate check: {gate} -> {status}",
        args=(),
        exc_info=None,
    )
    
    record.batch_id = batch_id
    record.event = "gate_check"
    record.metadata = metadata
    if duration_ms is not None:
        record.duration_ms = duration_ms
    
    logger.handle(record)


def log_performance(
    operation: str,
    duration_ms: float,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    记录性能指标
    
    Args:
        operation: 操作名称
        duration_ms: 执行时长（毫秒）
        metadata: 可选的元数据
    """
    logger = get_logger("performance")
    
    record = logger.makeRecord(
        name=logger.name,
        level=LEVEL_MAP.get("INFO", logging.INFO),
        fn="",
        lno=0,
        msg=f"Performance: {operation} completed in {duration_ms:.2f}ms",
        args=(),
        exc_info=None,
    )
    
    record.event = "performance"
    record.metadata = metadata or {}
    record.duration_ms = duration_ms
    
    logger.handle(record)


def log_validation(filepath: str, mode: str, fail: int, warn: int, passed: int, summary: Any = None) -> None:
    """校验结果事件（scripts/validate/engine.py 专用）。

    v2.1 回灌 (2026-10-13)：engine.validate_questions 此前一直在调用本函数，
    但 telemetry 从未实现过它 → ImportError 被静默吞掉，校验遥测一直失效
    （与评审 §6.5-P1.2 死依赖同源的问题）。现补齐。
    """
    log_info(
        f"Validation finished: fail={fail} warn={warn} pass={passed}",
        filepath=filepath, mode=mode, fail=fail, warn=warn, passed=passed, summary=summary,
    )


# 便捷函数
def log_info(message: str, **kwargs: Any) -> None:
    """记录INFO级别日志"""
    logger = get_logger("medagent")
    logger.info(message, extra=kwargs)


def log_error(message: str, exc_info: bool = True, **kwargs: Any) -> None:
    """记录ERROR级别日志"""
    logger = get_logger("medagent")
    logger.error(message, exc_info=exc_info, extra=kwargs)


def log_warning(message: str, **kwargs: Any) -> None:
    """记录WARNING级别日志"""
    logger = get_logger("medagent")
    logger.warning(message, extra=kwargs)


def log_debug(message: str, **kwargs: Any) -> None:
    """记录DEBUG级别日志"""
    logger = get_logger("medagent")
    logger.debug(message, extra=kwargs)


if __name__ == "__main__":
    # 测试日志模块
    print("Testing telemetry module...")
    
    # 测试基本日志
    log_info("Application started", batch_id="test_batch")
    
    # 测试批次事件
    log_batch_event("batch035", "agent2_start", {"subject": "内科学", "question_count": 100})
    
    # 测试门禁检查
    log_gate_check("batch035", "GATE-A2", "PASS", "All checks passed", duration_ms=123.45)
    
    # 测试性能日志
    log_performance("search_kb", 456.78, {"query": "心衰", "subject": "internal-med"})
    
    # 测试错误日志
    try:
        raise ValueError("Test error")
    except ValueError:
        log_error("An error occurred", exc_info=True, batch_id="batch035")
    
    print("Telemetry module test completed!")

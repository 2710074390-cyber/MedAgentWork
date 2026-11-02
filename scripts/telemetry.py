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
import os
import re
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
    logger.debug(message, exc_info=False, extra=kwargs)


# ══════════════════════════════════════════════════════════
# P6-S1：按批 JSONL 事件 sink（字段白名单，零用户数据）
# ══════════════════════════════════════════════════════════
#
# 设计要点：
#   1. 一 batch 一文件：reports/obs/<batch>_telemetry.jsonl，追加写；
#   2. 字段白名单：只允许系统维度（批次/阶段/规则/严重度/动作/重试/耗时/
#      token/模型/产物与提示词哈希），**任何用户维度字段一律拒收**；
#   3. 开关：环境变量 TELEMETRY_FILE=0 关闭落盘（回滚手段）；
#   4. 不抛异常：遥测失败不能拖垮管线，但必须能在 stderr 看见。

OBS_DIR = Path(__file__).resolve().parent.parent / 'reports' / 'obs'

#: 允许写入事件白名单（系统数据）
EVENT_FIELDS = frozenset({
    'ts', 'batch', 'stage', 'event', 'gate', 'status', 'rule_id', 'severity',
    'action', 'retry', 'duration_ms', 'tokens', 'count',
    'model_id', 'prompt_sha256', 'artifact_sha256', 'config_hash', 'source',
})

#: 出现即拒收的键（用户/会话/交互维度）——防的是「顺手把用户数据写进日志」
FORBIDDEN_FIELD_HINTS = (
    'user', 'session', 'attempt_by', 'student', 'account', 'phone', 'email',
    'name', 'device', 'ip', 'cookie', 'token_user', 'nickname', 'wechat',
)


def telemetry_enabled() -> bool:
    """TELEMETRY_FILE=0 关闭落盘（默认开启）。"""
    return os.environ.get('TELEMETRY_FILE', '1').strip().lower() not in ('0', 'false', 'off', 'no')


def jsonl_path(batch: str) -> Path:
    """批次事件文件路径。批次名做白名单化，防路径穿越。"""
    safe = re.sub(r'[^A-Za-z0-9_.\-]', '_', str(batch or 'unknown'))[:64]
    safe = safe.replace('..', '_').lstrip('.') or 'unknown'
    return OBS_DIR / f'{safe}_telemetry.jsonl'


def _reject_reason(fields: dict) -> str | None:
    for k in fields:
        low = str(k).lower()
        if k not in EVENT_FIELDS:
            for hint in FORBIDDEN_FIELD_HINTS:
                if hint in low:
                    return f'拒绝写入疑似用户维度字段 {k!r}'
            return f'字段不在白名单内 {k!r}（见 EVENT_FIELDS）'
    return None


def record_event(batch: str, event: str, **fields: Any) -> dict | None:
    """记录一条系统事件到该批次的 JSONL。

    返回写入的记录（被拒收/关闭时返回 None）。字段不合规时**拒收并报错到 stderr**，
    不会静默丢弃。
    """
    payload = {'ts': datetime.now(CST).isoformat(timespec='seconds'),
               'batch': str(batch), 'event': str(event)}
    payload.update(fields)

    bad = _reject_reason({k: v for k, v in payload.items() if k not in ('ts', 'batch', 'event')})
    if bad:
        print(f'  ⚠️ telemetry 事件被拒收：{bad}', file=sys.stderr)
        return None
    if not telemetry_enabled():
        return None
    try:
        OBS_DIR.mkdir(parents=True, exist_ok=True)
        with open(jsonl_path(batch), 'a', encoding='utf-8') as f:
            f.write(json.dumps(payload, ensure_ascii=False) + '\n')
        return payload
    except Exception as e:
        print(f'  ⚠️ telemetry 写入失败({e})，事件未落盘', file=sys.stderr)
        return None


def read_events(batch: str | None = None) -> list[dict]:
    """读取事件：给定 batch 读单文件，否则读全部批次文件。"""
    paths = [jsonl_path(batch)] if batch else sorted(OBS_DIR.glob('*_telemetry.jsonl'))
    out = []
    for p in paths:
        if not p.exists():
            continue
        for line in p.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                out.append(obj)
    return out


def validate_event_schema(events: list[dict]) -> list[str]:
    """字段白名单体检：返回违规说明列表（空 = 合规）。用于 AC-P6-01 证据。"""
    issues = []
    for i, e in enumerate(events):
        if not isinstance(e, dict):
            issues.append(f'[{i}] 不是对象')
            continue
        for k in e:
            if k not in EVENT_FIELDS:
                issues.append(f'[{i}] 非白名单字段 {k!r}')
    return issues


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

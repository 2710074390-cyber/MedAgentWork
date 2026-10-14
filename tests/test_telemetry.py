#!/usr/bin/env python3
"""
test_telemetry.py — telemetry 模块单元测试
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 添加项目根目录到路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.telemetry import (
    get_logger,
    log_batch_event,
    log_gate_check,
    log_performance,
    log_info,
    log_error,
    log_warning,
    log_debug,
    CST,
    StructuredFormatter,
    HumanReadableFormatter,
)


class TestCSTTimezone:
    """测试时区配置"""
    
    def test_cst_is_utc_plus_8(self):
        """CST应该是UTC+8"""
        assert CST == timezone(timedelta(hours=8))
    
    def test_cst_offset(self):
        """CST偏移量应为8小时"""
        assert CST.utcoffset(None) == timedelta(hours=8)


class TestStructuredFormatter:
    """测试结构化JSON格式化器"""
    
    def setup_method(self):
        self.formatter = StructuredFormatter()
    
    def test_format_basic(self):
        """测试基本格式化"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        result = self.formatter.format(record)
        data = json.loads(result)
        
        assert "timestamp" in data
        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["message"] == "Test message"
    
    def test_format_with_batch_id(self):
        """测试带batch_id的格式化"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.batch_id = "batch035"
        
        result = self.formatter.format(record)
        data = json.loads(result)
        
        assert data["batch_id"] == "batch035"
    
    def test_format_with_event(self):
        """测试带event的格式化"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.event = "gate_check"
        
        result = self.formatter.format(record)
        data = json.loads(result)
        
        assert data["event"] == "gate_check"
    
    def test_format_with_metadata(self):
        """测试带metadata的格式化"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.metadata = {"subject": "内科学"}
        
        result = self.formatter.format(record)
        data = json.loads(result)
        
        assert data["metadata"]["subject"] == "内科学"
    
    def test_format_with_exception(self):
        """测试带异常的格式化"""
        try:
            raise ValueError("Test error")
        except ValueError:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )
        
        result = self.formatter.format(record)
        data = json.loads(result)
        
        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"
        assert data["exception"]["message"] == "Test error"


class TestHumanReadableFormatter:
    """测试人类可读格式化器"""
    
    def setup_method(self):
        self.formatter = HumanReadableFormatter()
    
    def test_format_basic(self):
        """测试基本格式化"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        result = self.formatter.format(record)
        
        assert "INFO" in result
        assert "test" in result
        assert "Test message" in result
    
    def test_format_with_extras(self):
        """测试带额外信息的格式化"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.batch_id = "batch035"
        record.event = "gate_check"
        record.duration_ms = 123.45
        
        result = self.formatter.format(record)
        
        assert "batch=batch035" in result
        assert "event=gate_check" in result
        assert "duration=123.45ms" in result


class TestGetLogger:
    """测试get_logger函数"""
    
    def test_get_logger_returns_logger(self):
        """测试返回正确的logger"""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"
    
    def test_get_logger_default_level(self):
        """测试默认日志级别"""
        logger = get_logger("test_default")
        assert logger.level == logging.INFO
    
    def test_get_logger_custom_level(self):
        """测试自定义日志级别"""
        logger = get_logger("test_debug", level="DEBUG")
        assert logger.level == logging.DEBUG
    
    def test_get_logger_no_duplicate_handlers(self):
        """测试不会重复添加handler"""
        logger1 = get_logger("test_no_dup")
        handler_count1 = len(logger1.handlers)
        
        logger2 = get_logger("test_no_dup")
        handler_count2 = len(logger2.handlers)
        
        assert handler_count1 == handler_count2
    
    def test_get_logger_with_file(self, tmp_path):
        """测试带文件输出的logger"""
        log_file = tmp_path / "test.log"
        logger = get_logger("test_file", log_file=log_file)
        
        logger.info("Test message")
        
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "Test message" in content


class TestLogBatchEvent:
    """测试log_batch_event函数"""
    
    def test_log_batch_event(self):
        """测试批次事件记录"""
        with patch("scripts.telemetry.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            log_batch_event("batch035", "agent2_start", {"subject": "内科学"})
            
            mock_get_logger.assert_called_with("batch_events")
            mock_logger.handle.assert_called_once()
            
            record = mock_logger.handle.call_args[0][0]
            assert record.batch_id == "batch035"
            assert record.event == "agent2_start"
            assert record.metadata["subject"] == "内科学"


class TestLogGateCheck:
    """测试log_gate_check函数"""
    
    def test_log_gate_check_pass(self):
        """测试门禁通过记录"""
        with patch("scripts.telemetry.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            log_gate_check("batch035", "GATE-A2", "PASS", "All checks passed")
            
            mock_logger.handle.assert_called_once()
            record = mock_logger.handle.call_args[0][0]
            assert record.batch_id == "batch035"
            assert record.metadata["gate"] == "GATE-A2"
            assert record.metadata["status"] == "PASS"
    
    def test_log_gate_check_with_duration(self):
        """测试带时长的门禁记录"""
        with patch("scripts.telemetry.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            log_gate_check("batch035", "GATE-A2", "PASS", "All checks passed", duration_ms=123.45)
            
            record = mock_logger.handle.call_args[0][0]
            assert record.duration_ms == 123.45


class TestLogPerformance:
    """测试log_performance函数"""
    
    def test_log_performance(self):
        """测试性能日志记录"""
        with patch("scripts.telemetry.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            log_performance("search_kb", 456.78, {"query": "心衰"})
            
            mock_logger.handle.assert_called_once()
            record = mock_logger.handle.call_args[0][0]
            assert record.event == "performance"
            assert record.duration_ms == 456.78
            assert record.metadata["query"] == "心衰"


class TestConvenienceFunctions:
    """测试便捷函数"""
    
    def test_log_info(self):
        """测试log_info函数"""
        with patch("scripts.telemetry.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            log_info("Test info", batch_id="batch035")
            
            mock_logger.info.assert_called_once()
    
    def test_log_error(self):
        """测试log_error函数"""
        with patch("scripts.telemetry.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            log_error("Test error", batch_id="batch035")
            
            mock_logger.error.assert_called_once()
    
    def test_log_warning(self):
        """测试log_warning函数"""
        with patch("scripts.telemetry.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            log_warning("Test warning", batch_id="batch035")
            
            mock_logger.warning.assert_called_once()
    
    def test_log_debug(self):
        """测试log_debug函数"""
        with patch("scripts.telemetry.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            log_debug("Test debug", batch_id="batch035")
            
            mock_logger.debug.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

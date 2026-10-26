#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""quality_policy.py — 全流程质量基准的单一事实来源加载器（HC-25）。

用法
    python scripts/quality_policy.py --validate
    python scripts/quality_policy.py --show pilot
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DEFAULT_POLICY = Path(__file__).resolve().parent / "quality_policy.json"


def load_policy(path: Path | None = None) -> dict:
    p = Path(path) if path else DEFAULT_POLICY
    data = json.loads(p.read_text(encoding="utf-8"))
    validate_policy(data)
    return data


def validate_policy(data: dict) -> None:
    if not isinstance(data, dict):
        raise ValueError("policy 必须是对象")
    if data.get("schema_version") != 1:
        raise ValueError("policy.schema_version 必须为 1")
    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError("policy.profiles 不能为空")
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            raise ValueError(f"profile {name} 必须是对象")
        checks = profile.get("required_checks")
        if not isinstance(checks, list) or not checks:
            raise ValueError(f"profile {name}.required_checks 不能为空")
        thresholds = profile.get("thresholds")
        if not isinstance(thresholds, dict) or not thresholds:
            raise ValueError(f"profile {name}.thresholds 不能为空")
        for key, value in thresholds.items():
            if not isinstance(value, (int, float)):
                raise ValueError(f"profile {name}.thresholds.{key} 必须是数字")
            if value < 0:
                raise ValueError(f"profile {name}.thresholds.{key} 不能为负")


def get_profile(name: str, policy: dict | None = None) -> dict:
    data = policy or load_policy()
    profiles = data.get("profiles", {})
    if name not in profiles:
        raise KeyError(f"未知 profile: {name}；可选 {sorted(profiles)}")
    return profiles[name]


def get_threshold(profile: dict, key: str, default=None):
    return profile.get("thresholds", {}).get(key, default)


def main() -> int:
    ap = argparse.ArgumentParser(description="质量基准加载器（HC-25）")
    ap.add_argument("--policy", default=str(DEFAULT_POLICY))
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--show", default="")
    args = ap.parse_args()
    try:
        data = load_policy(Path(args.policy))
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if args.show:
        try:
            profile = get_profile(args.show, data)
        except KeyError as exc:
            print(f"[FAIL] {exc}", file=sys.stderr)
            return 2
        print(json.dumps(profile, ensure_ascii=False, indent=2))
        return 0
    print(f"✅ policy 校验通过：{len(data['profiles'])} 个 profile；版本 {data.get('policy_version')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

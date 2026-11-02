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


# ── 策略动作层（P6-S4 预置 · 阶段 0 只做审计，不改门禁流程）──────────
#
# severity → 动作的显式映射。**未知 severity 一律 HALT**：
# 宁可停管线，也不能因为「没写 severity」而隐式放行。

ACTIONS = ('PASS', 'WARN', 'REPAIR', 'REGENERATE', 'QUARANTINE', 'HUMAN', 'HALT')


def resolve_action(severity, policy: dict | None = None) -> dict:
    """把严重度解析成动作，返回 {severity, action, source, reason}。

    - 命中 severity_actions → 返回配置动作；
    - 未命中 → 返回 action_fallback（默认 HALT），reason 写明「非白名单严重度」；
    - 配置里的动作值不在 ACTIONS 内 → 同样 HALT（配置写错不能变放行）。
    """
    data = policy or load_policy()
    table = data.get('severity_actions') or {}
    fallback = str(data.get('action_fallback') or 'HALT').upper()
    sev = str(severity or '').strip().upper()
    if not sev:
        return {'severity': '', 'action': fallback, 'source': 'fallback',
                'reason': 'severity 缺失，按 fail-closed 处理'}
    if sev in table:
        action = str(table[sev]).upper()
        if action in ACTIONS:
            return {'severity': sev, 'action': action, 'source': 'severity_actions',
                    'reason': f'{sev} → {action}'}
        return {'severity': sev, 'action': fallback, 'source': 'fallback',
                'reason': f'配置动作 {action!r} 非法（允许 {ACTIONS}），按 fail-closed 处理'}
    return {'severity': sev, 'action': fallback, 'source': 'fallback',
            'reason': f'{sev} 不在 severity_actions 白名单内，按 fail-closed 处理'}


def audit_actions(securities=('FAIL', 'WARN', 'INFO', 'SKIPPED', '', 'UNKNOWN'),
                  policy: dict | None = None) -> list[dict]:
    """生成策略动作审计记录（一行一个 severity，可直接写 JSONL）。"""
    return [resolve_action(s, policy) for s in securities]


def main() -> int:
    ap = argparse.ArgumentParser(description="质量基准加载器（HC-25）")
    ap.add_argument("--policy", default=str(DEFAULT_POLICY))
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--show", default="")
    ap.add_argument("--audit-actions", action="store_true",
                    help="输出 severity→动作审计记录（JSONL），用于 AC-P6-05")
    ap.add_argument("--jsonl", default="", help="审计记录输出路径")
    args = ap.parse_args()
    try:
        data = load_policy(Path(args.policy))
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if args.audit_actions:
        rows = audit_actions(policy=data)
        for r in rows:
            r['policy_version'] = data.get('policy_version')
            r['recorded_at'] = __import__('datetime').datetime.now().isoformat(timespec='seconds')
        if args.jsonl:
            out = Path(args.jsonl)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n',
                           encoding='utf-8')
            print(f'📄 策略动作审计: {out}（{len(rows)} 条）')
        else:
            for r in rows:
                print(json.dumps(r, ensure_ascii=False))
        return 0
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

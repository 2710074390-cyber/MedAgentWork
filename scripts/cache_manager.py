#!/usr/bin/env python3
"""
cache_manager.py — RAG 缓存管理工具 v1.0

提供缓存统计、清理、导出功能，帮助用户管理检索缓存。

用法:
    python scripts/cache_manager.py stats              # 显示缓存统计
    python scripts/cache_manager.py list               # 列出所有缓存
    python scripts/cache_manager.py clear              # 清空所有缓存
    python scripts/cache_manager.py clear --older-than 7  # 清理7天前的缓存
    python scripts/cache_manager.py export --output cache_export.json  # 导出缓存
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 配置
BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "知识库素材" / "cache"
CST = timezone(timedelta(hours=8))


def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计信息"""
    if not CACHE_DIR.exists():
        return {"exists": False, "count": 0, "total_size": 0}
    
    cache_files = list(CACHE_DIR.glob("*.json"))
    total_size = sum(f.stat().st_size for f in cache_files)
    
    # 按类型分类
    embed_count = 0
    search_count = 0
    other_count = 0
    
    for f in cache_files:
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
            if 'embedding' in data:
                embed_count += 1
            elif 'results' in data or 'rerank' in str(data.keys()):
                search_count += 1
            else:
                other_count += 1
        except Exception:
            other_count += 1
    
    # 获取最早和最晚的修改时间
    if cache_files:
        timestamps = [f.stat().st_mtime for f in cache_files]
        oldest = datetime.fromtimestamp(min(timestamps), tz=CST)
        newest = datetime.fromtimestamp(max(timestamps), tz=CST)
    else:
        oldest = newest = None
    
    return {
        "exists": True,
        "count": len(cache_files),
        "total_size": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "embed_count": embed_count,
        "search_count": search_count,
        "other_count": other_count,
        "oldest": oldest.isoformat() if oldest else None,
        "newest": newest.isoformat() if newest else None,
    }


def list_cache_files(older_than_days: int = None) -> List[Dict[str, Any]]:
    """列出缓存文件"""
    if not CACHE_DIR.exists():
        return []
    
    cache_files = list(CACHE_DIR.glob("*.json"))
    result = []
    
    cutoff_time = None
    if older_than_days:
        cutoff_time = datetime.now(tz=CST) - timedelta(days=older_than_days)
    
    for f in cache_files:
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=CST)
        
        if cutoff_time and mtime > cutoff_time:
            continue
        
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
            
            # 提取缓存类型
            cache_type = "unknown"
            if 'embedding' in data:
                cache_type = "embed"
            elif 'results' in data:
                cache_type = "search"
            
            result.append({
                "file": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "modified": mtime.isoformat(),
                "type": cache_type,
            })
        except Exception:
            result.append({
                "file": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "modified": mtime.isoformat(),
                "type": "corrupted",
            })
    
    return sorted(result, key=lambda x: x['modified'], reverse=True)


def clear_cache(older_than_days: int = None) -> int:
    """清空缓存，返回删除的文件数"""
    if not CACHE_DIR.exists():
        return 0
    
    cache_files = list(CACHE_DIR.glob("*.json"))
    deleted = 0
    
    cutoff_time = None
    if older_than_days:
        cutoff_time = datetime.now(tz=CST) - timedelta(days=older_than_days)
    
    for f in cache_files:
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=CST)
        
        if cutoff_time and mtime > cutoff_time:
            continue
        
        try:
            f.unlink()
            deleted += 1
        except Exception as e:
            print(f"  [WARN] Failed to delete {f.name}: {e}", file=sys.stderr)
    
    return deleted


def export_cache(output_path: Path) -> int:
    """导出缓存到JSON文件"""
    if not CACHE_DIR.exists():
        return 0
    
    cache_files = list(CACHE_DIR.glob("*.json"))
    exported = []
    
    for f in cache_files:
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
            exported.append({
                "file": f.name,
                "data": data,
                "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=CST).isoformat(),
            })
        except Exception:
            pass
    
    with open(output_path, 'w', encoding='utf-8') as fp:
        json.dump(exported, fp, ensure_ascii=False, indent=2)
    
    return len(exported)


def main():
    parser = argparse.ArgumentParser(description="RAG 缓存管理工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # stats 命令
    subparsers.add_parser("stats", help="显示缓存统计")
    
    # list 命令
    list_parser = subparsers.add_parser("list", help="列出缓存文件")
    list_parser.add_argument("--older-than", type=int, help="只显示N天前的文件")
    
    # clear 命令
    clear_parser = subparsers.add_parser("clear", help="清空缓存")
    clear_parser.add_argument("--older-than", type=int, help="只清理N天前的文件")
    
    # export 命令
    export_parser = subparsers.add_parser("export", help="导出缓存")
    export_parser.add_argument("--output", type=Path, default=Path("cache_export.json"), help="输出文件")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "stats":
        stats = get_cache_stats()
        if not stats["exists"]:
            print("  缓存目录不存在")
            return
        
        print(f"\n{'='*50}")
        print(f"  RAG 缓存统计")
        print(f"{'='*50}")
        print(f"  缓存文件数: {stats['count']}")
        print(f"  总大小: {stats['total_size_mb']} MB")
        print(f"  Embed缓存: {stats['embed_count']}")
        print(f"  Search缓存: {stats['search_count']}")
        print(f"  其他: {stats['other_count']}")
        if stats['oldest']:
            print(f"  最早: {stats['oldest']}")
        if stats['newest']:
            print(f"  最新: {stats['newest']}")
        print(f"{'='*50}\n")
    
    elif args.command == "list":
        files = list_cache_files(args.older_than)
        if not files:
            print("  没有找到缓存文件")
            return
        
        print(f"\n{'='*70}")
        print(f"  缓存文件列表 (共 {len(files)} 个)")
        print(f"{'='*70}")
        for f in files[:20]:  # 最多显示20个
            size_kb = f['size'] / 1024
            print(f"  {f['file'][:40]:<40} {size_kb:>6.1f}KB  {f['type']:<8} {f['modified'][:19]}")
        if len(files) > 20:
            print(f"  ... 还有 {len(files) - 20} 个文件")
        print(f"{'='*70}\n")
    
    elif args.command == "clear":
        deleted = clear_cache(args.older_than)
        print(f"  已删除 {deleted} 个缓存文件")
    
    elif args.command == "export":
        exported = export_cache(args.output)
        print(f"  已导出 {exported} 个缓存到 {args.output}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""webp -> png 批量转换 + 可选同步更新 MD 引用（解决 Obsidian 不显示 webp 的问题）。

用法（在项目根目录）：
  python -X utf8 scripts/webp_to_png.py                      # 仅转换，不改 MD
  python -X utf8 scripts/webp_to_png.py --update-md          # 转换并把 MD 中 images_webp/*.webp 引用改为 *.png
  python -X utf8 scripts/webp_to_png.py --remove-webp        # 转换成功后删除原 webp（默认保留，可回滚）
  python -X utf8 scripts/webp_to_png.py "复习资料/急诊与灾难医学教学计划版"   # 只处理指定科目

说明：
  - 输出 png 与原 webp 同目录同名（images_webp/xxx.png），保持 1600px 宽。
  - MD 引用替换仅作用于 ![]() 图片行内的 images_webp/ 相对路径，不影响其他文本。
  - check_refs.py 按引用实际路径校验，转换后重跑即可验证。
"""
import os, re, sys, io, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SUBJ_DIRS = [d for d in os.listdir(os.path.join(ROOT, '复习资料'))
             if d.endswith('教学计划版')]

REF_PAT = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')
IMG_PAT = re.compile(r'^images_webp/([^)]+)\.webp$', re.IGNORECASE)


def convert_webp_to_png(wpath):
    """返回生成的 png 路径；失败返回 None。"""
    png = os.path.splitext(wpath)[0] + '.png'
    if os.path.exists(png):
        return png  # 已存在则跳过（幂等）
    try:
        im = Image.open(wpath)
        if im.mode in ('RGBA', 'LA', 'P'):
            im = im.convert('RGBA')
        rgb = Image.new('RGB', im.size, (255, 255, 255))
        rgb.paste(im, mask=im.split()[-1] if im.mode == 'RGBA' else None)
        # 统一 1600px 宽（与部署规范一致）
        if rgb.width != 1600:
            h = round(rgb.height * 1600 / rgb.width)
            rgb = rgb.resize((1600, h), Image.LANCZOS)
        rgb.save(png, 'PNG', optimize=True)
        return png
    except Exception as e:
        print(f'   [失败] {wpath}: {e}', file=sys.stderr)
        return None


def update_md_refs(md_path):
    """把 MD 内 ![]() 引用中的 images_webp/xxx.webp 改为 .png；返回改动数。"""
    text = open(md_path, encoding='utf-8').read()

    def repl(m):
        ref = m.group(1)
        img = IMG_PAT.match(ref)
        if img and os.path.exists(os.path.join(os.path.dirname(md_path),
                                               'images_webp', img.group(1) + '.png')):
            return m.group(0).replace('.webp', '.png').replace('.WEBP', '.png')
        return m.group(0)

    new_text = REF_PAT.sub(repl, text)
    if new_text != text:
        open(md_path, 'w', encoding='utf-8', newline='').write(new_text)
        # 统计实际改动次数
        return sum(1 for a, b in zip(text.split('\n'), new_text.split('\n')) if a != b)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='*', help='科目目录（可多个），默认全部教学计划版')
    ap.add_argument('--update-md', action='store_true', help='同步把 MD 引用 .webp 改为 .png')
    ap.add_argument('--remove-webp', action='store_true', help='转换成功后删除原 webp')
    args = ap.parse_args()

    dirs = args.dirs or [os.path.join(ROOT, '复习资料', d) for d in SUBJ_DIRS]
    total_png = total_webp = 0
    for d in dirs:
        sdir = d if os.path.isabs(d) else os.path.join(ROOT, d)
        wdir = os.path.join(sdir, 'images_webp')
        if not os.path.isdir(wdir):
            print(f'== {os.path.basename(sdir)}: 无 images_webp，跳过')
            continue
        webs = sorted(f for f in os.listdir(wdir) if f.lower().endswith('.webp'))
        if not webs:
            continue
        print(f'== {os.path.basename(sdir)}: {len(webs)} 个 webp')
        for f in webs:
            png = convert_webp_to_png(os.path.join(wdir, f))
            if png:
                total_png += 1
                if args.remove_webp:
                    os.remove(os.path.join(wdir, f))
                else:
                    total_webp += 1
        if args.update_md:
            for md in [f for f in os.listdir(sdir) if f.endswith('.md')]:
                n = update_md_refs(os.path.join(sdir, md))
                if n:
                    print(f'   MD 引用更新 {n} 行: {md}')
    print(f'\n完成：生成/确认 png {total_png} 张，保留 webp {total_webp} 张'
          + ('（已按 --remove-webp 删除原 webp）' if args.remove_webp else ''))


if __name__ == '__main__':
    main()

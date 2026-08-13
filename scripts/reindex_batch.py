#!/usr/bin/env python3
"""批量重新索引所有科目，启用教材印刷页码"""
import sys, os, json
sys.path.insert(0, '知识库素材')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from embed_index import get_api_key, process_pdf, embed_and_store, update_manifest
from pathlib import Path

BASE = Path(r'C:\Users\38063\Desktop\MedAgentWork')
PDF_DIR = BASE / '知识库素材'

SUBJECTS = [
    ('神经病学', 'neurology', '25. 神经病学 .pdf'),
    ('内科学', 'internal-med', '21. 内科学（第10版）公众号：在逃小番茄Lynn.pdf'),
    ('儿科学', 'pediatrics', '24. 儿科学 .pdf'),
    ('外科学', 'surgery', '22. 外科学 .pdf'),
    ('皮肤性病学', 'dermatology', '31. 皮肤性病学.pdf'),
    ('精神病学', 'psychiatry', '26. 精神病学（第9版）.pdf'),
    ('医患沟通', 'doctor-patient', '51. 医患沟通.pdf'),
]

api_key = get_api_key()
manifest_path = BASE / '知识库素材' / 'index_store' / 'index_manifest.json'

for subject, code, filename in SUBJECTS:
    pdf_path = PDF_DIR / subject / filename
    if not pdf_path.exists():
        pdf_path = PDF_DIR / filename
    if not pdf_path.exists():
        print('[SKIP] %s: not found' % subject)
        sys.stdout.flush()
        continue

    print('\n[REINDEX] %s (%s)' % (subject, code))
    sys.stdout.flush()

    try:
        chunks = process_pdf(pdf_path, subject, code)
        printed = sum(1 for c in chunks if c['meta']['page_number'] != c['meta']['pdf_page_number'])
        total = len(chunks)
        print('  Printed pages resolved: %d/%d chunks' % (printed, total))
        sys.stdout.flush()

        embed_and_store(chunks, code, api_key)
        update_manifest(code, subject, len(chunks), pdf_path)

        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        if code in manifest:
            manifest[code]['page_number_source'] = 'printed_textbook'
            manifest[code]['printed_pages_available'] = True
            manifest[code]['reindexed_at'] = manifest[code].get('indexed_at', '')
            manifest[code].pop('page_number_fix', None)
            manifest[code].pop('estimated_offset', None)
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        print('[OK] %s (%d chunks)' % (subject, total))
        sys.stdout.flush()
    except Exception as e:
        print('[FAIL] %s: %s' % (subject, e))
        sys.stdout.flush()
        import traceback
        traceback.print_exc()

print('\n[DONE] All reindexed.')

import re, json, sys

with open(r"C:\Users\38063\Desktop\MedAgentWork\中间产物\batch026_analysis\batch026_analysis_questions.json", "r", encoding="utf-8") as f:
    raw = f.read()

# Fix ASCII double quotes used as Chinese quotation marks inside string values
# Replace Chinese-context ASCII " with full-width Chinese quotes
# Strategy: find " surrounded by CJK characters
raw = re.sub(r'(?<=[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef])"', '\u201d', raw)
raw = re.sub(r'"(?=[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef])', '\u201c', raw)

# Also handle the case where " is before a ( or after )
raw = re.sub(r'\u201c(?=[\uff08])', '\u201c', raw)  # no-op, just for safety

try:
    data = json.loads(raw)
    print(f"Fixed! {len(data)} questions valid JSON")
    with open(r"C:\Users\38063\Desktop\MedAgentWork\中间产物\batch026_analysis\batch026_analysis_questions.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("File rewritten successfully")
except json.JSONDecodeError as e:
    print(f"Error at pos {e.pos}: {e}")
    print(f"Context: {repr(raw[e.pos-30:e.pos+30])}")

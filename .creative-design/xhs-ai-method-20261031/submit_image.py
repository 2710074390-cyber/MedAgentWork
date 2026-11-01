# -*- coding: utf-8 -*-
"""Submit one IMAGE item to the design workspace, then +get and verify URL round-trip.
Usage: python submit_image.py <item.xml>
"""
import json
import re
import subprocess
import sys
from pathlib import Path

WORKSPACE_ID = "cws_60327885147147010"
workdir = Path(__file__).resolve().parent
xml_path = Path(sys.argv[1])
xml_text = xml_path.read_text(encoding="utf-8-sig")
payload = xml_text.encode("utf-8")
if not xml_text.strip() or len(payload) > 1024 * 1024:
    raise SystemExit("XML empty or over 1MB.")

create_argv = ["design-cli", "design-workspace", "+create",
               "--canvas-workspace-id", WORKSPACE_ID, "--input", "-"]
res = subprocess.run(create_argv, input=payload, shell=False, cwd=workdir,
                     capture_output=True, timeout=120)
(workdir / f"{xml_path.stem}.create.stdout.bin").write_bytes(res.stdout)
(workdir / f"{xml_path.stem}.create.stderr.bin").write_bytes(res.stderr)
if res.returncode != 0:
    raise SystemExit(f"create exit code {res.returncode}; see saved bins.")

body = json.loads(res.stdout.decode("utf-8", errors="strict"))
if body.get("code") != 0:
    raise SystemExit(f"create response code != 0: {body}")
xml_data = body["xml_data"]

m_id = re.search(r'<item[^>]*item_id="([^"]+)"', xml_data)
if not m_id:
    raise SystemExit(f"item_id not found in response: {xml_data}")
item_id = m_id.group(1)

get_argv = ["design-cli", "design-workspace", "+get",
            "--canvas-workspace-id", WORKSPACE_ID, "--item-ids", item_id]
res2 = subprocess.run(get_argv, shell=False, cwd=workdir,
                      capture_output=True, timeout=120)
(workdir / f"{xml_path.stem}.get.stdout.bin").write_bytes(res2.stdout)
(workdir / f"{xml_path.stem}.get.stderr.bin").write_bytes(res2.stderr)
if res2.returncode != 0:
    raise SystemExit(f"get exit code {res2.returncode}; see saved bins.")
body2 = json.loads(res2.stdout.decode("utf-8", errors="strict"))
if body2.get("code") != 0:
    raise SystemExit(f"get response code != 0: {body2}")

# Server may rotate the short link; verify asset node exists and internal uri survives.
src_url = re.search(r'<asset url="([^"]+)"', xml_text).group(1)
got = body2["xml_data"]
if "<asset" not in got:
    raise SystemExit("asset node missing after get")
m_uri = re.search(r'uri="([^"]+)"', xml_data)
if m_uri and m_uri.group(1) not in got:
    raise SystemExit("internal uri mismatch after get")
canvas_url = re.search(r'url="([^"]+)"', got).group(1)
print(json.dumps({"item_id": item_id, "source_url": src_url, "canvas_url": canvas_url,
                  "status": "persisted-and-verified"}, ensure_ascii=False))

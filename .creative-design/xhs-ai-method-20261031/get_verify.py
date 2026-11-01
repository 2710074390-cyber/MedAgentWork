# -*- coding: utf-8 -*-
"""+get an existing item and verify its asset URL round-trip."""
import json, re, subprocess, sys
from pathlib import Path

WORKSPACE_ID = "cws_60327885147147010"
item_id, src_url = sys.argv[1], sys.argv[2]
workdir = Path(__file__).resolve().parent

argv = ["design-cli", "design-workspace", "+get",
        "--canvas-workspace-id", WORKSPACE_ID, "--item-ids", item_id]
res = subprocess.run(argv, shell=False, cwd=workdir, capture_output=True, timeout=120)
(workdir / f"get-{item_id}.stdout.bin").write_bytes(res.stdout)
(workdir / f"get-{item_id}.stderr.bin").write_bytes(res.stderr)
if res.returncode != 0:
    raise SystemExit(f"get exit code {res.returncode}")
body = json.loads(res.stdout.decode("utf-8", errors="strict"))
if body.get("code") != 0:
    raise SystemExit(f"get code != 0: {body}")
got = body["xml_data"]
if "<asset" not in got:
    raise SystemExit("asset node missing after get")
# Server may rotate the short link; match on the internal uri if present, else source url.
uri = re.search(r'uri="([^"]+)"', got)
if uri and uri.group(1) not in got:
    raise SystemExit("internal uri missing")
print(json.dumps({"item_id": item_id, "canvas_url": re.search(r'url="([^"]+)"', got).group(1), "status": "verified"}, ensure_ascii=False))

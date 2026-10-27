#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_concept_atlas.py — 概念地图预览（W6）。

产物是**单文件 HTML**，无外部请求、无 CDN、无字体外链，双击即可看。
用途：给「学习器」做静态预览——判断这套概念层值不值得继续投入 P1；
      不是站点交付物，落在 reports/atlas/。

数据来源
    question_bank/concept_graph.json      节点 + 三类边
    question_bank/concept_labels.jsonl    题目级角色（主/鉴别/相关）
    主复习资料 MD                         卡片「💡 记忆钩子」（复用 build_concept_cards 的解析）

用法
    python scripts/render_concept_atlas.py
    python scripts/render_concept_atlas.py --out reports/atlas/concept_atlas.html
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

def _configure_stdio() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from build_concept_cards import parse_review_cards, resolve_review  # noqa: E402

DEFAULT_GRAPH = BASE / "question_bank/concept_graph.json"
DEFAULT_LABELS = BASE / "question_bank/concept_labels.jsonl"
DEFAULT_OUT = BASE / "reports/atlas/concept_atlas.html"


def build_payload(graph: dict, labels_path: Path) -> dict:
    hooks: dict[str, str] = {}
    for subject in {n["subject"] for n in graph["nodes"]}:
        review = resolve_review(graph, subject)
        if not review:
            continue
        cards = parse_review_cards(review)
        for n in graph["nodes"]:
            if n["subject"] != subject:
                continue
            c = cards.get(n["display_id"])
            if c and c.get("hook"):
                hooks[n["kc_id"]] = c["hook"]

    measures = graph["edges"]["measures"]
    by_q: dict[str, list[dict]] = defaultdict(list)
    by_kc: dict[str, list[dict]] = defaultdict(list)
    for m in measures:
        by_q[m["qid"]].append({"kc": m["kc_id"], "role": m["role"], "conf": m.get("confidence"),
                               "ev": m.get("evidence", "")})
        by_kc[m["kc_id"]].append({"qid": m["qid"], "role": m["role"], "conf": m.get("confidence"),
                                  "ev": m.get("evidence", "")})

    children: dict[str, list[str]] = defaultdict(list)
    for e in graph["edges"]["prereq"]:
        children[e["from"]].append(e["to"])
    refs: dict[str, list[str]] = defaultdict(list)
    for e in graph["edges"]["ref"]:
        refs[e["from"]].append(e["to"])
        refs[e["to"]].append(e["from"])

    multi = {}
    if labels_path.exists():
        rows = [json.loads(l) for l in labels_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        pool = defaultdict(lambda: [0, 0])
        for r in rows:
            if r["type"] in {"A2", "A3", "A4", "X", "B1"}:
                pool[r["subject"]][0] += 1
                if r["secondary"]:
                    pool[r["subject"]][1] += 1
        multi = {k: (round(v[1] / v[0], 3) if v[0] else None) for k, v in pool.items()}

    nodes = []
    for n in graph["nodes"]:
        nodes.append({
            "id": n["kc_id"], "did": n["display_id"], "subject": n["subject"],
            "module": n["module"], "title": n["title"],
            "kps": n["keypoints"], "pages": n["source_pages"],
            "weight": n["weight"], "status": n["status"], "anchor": n["review_anchor"],
            "pre": n["prereq"], "child": sorted(children.get(n["kc_id"], [])),
            "ref": sorted(set(refs.get(n["kc_id"], []))),
            "hook": hooks.get(n["kc_id"], ""),
            "qs": sorted(by_kc.get(n["kc_id"], []), key=lambda x: (x["role"] != "primary", x["qid"])),
        })

    subjects = {}
    for s in graph["subjects"]:
        sub_nodes = [n for n in nodes if n["subject"] == s["subject"]]
        subjects[s["subject"]] = {
            "batch": s["batch"],
            "modules": sorted({n["module"] for n in sub_nodes}),
            "nodes": len(sub_nodes),
            "questions": len({q["qid"] for n in sub_nodes for q in n["qs"] if q["role"] == "primary"}),
            "multi": multi.get(s["subject"]),
        }

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "subjects": subjects,
        "nodes": nodes,
        "stats": {
            "measures": len(measures),
            "prereq": len(graph["edges"]["prereq"]),
            "ref": len(graph["edges"]["ref"]),
            "module_prereq": len(graph.get("module_prereq") or []),
        },
    }


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>概念地图 · MedAgentWork</title>
<style>
:root{
--bg:#0b1220;--panel:#111b2e;--panel2:#16233a;--line:#22304a;--ink:#e8eefb;--dim:#93a4c0;
--accent:#5eead4;--amber:#fbbf24;--blue:#60a5fa;--rose:#fb7185;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:var(--bg);color:var(--ink);font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.app{display:grid;grid-template-columns:330px 1fr;height:100vh;overflow:hidden}
aside{border-right:1px solid var(--line);background:var(--panel);display:flex;flex-direction:column;min-height:0}
main{display:flex;flex-direction:column;min-height:0}
.top{padding:16px 20px;border-bottom:1px solid var(--line);background:var(--panel2)}
.top h1{margin:0 0 6px;font-size:16px;font-weight:600;letter-spacing:.02em}
.top .meta{color:var(--dim);font-size:12px}
.tabs{display:flex;gap:8px;margin:12px 0 0}
.tab{padding:5px 12px;border:1px solid var(--line);border-radius:999px;background:transparent;color:var(--dim);cursor:pointer;font-size:12px}
.tab.on{color:#062d2a;background:var(--accent);border-color:var(--accent);font-weight:600}
.search{padding:12px 14px;border-bottom:1px solid var(--line)}
.search input{width:100%;padding:7px 10px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink);font-size:13px;outline:none}
.search input:focus{border-color:var(--accent)}
.list{overflow:auto;flex:1;padding:8px 0 24px}
.mod{padding:10px 14px 4px;color:var(--dim);font-size:11px;letter-spacing:.08em;display:flex;justify-content:space-between}
.mod b{color:var(--accent);font-weight:600}
.item{padding:8px 14px 8px 18px;border-left:2px solid transparent;cursor:pointer;display:block}
.item:hover{background:#16233a}
.item.on{background:#1b2c47;border-left-color:var(--accent)}
.item .t{font-size:13px;display:flex;gap:6px;align-items:baseline}
.item .kid{color:var(--dim);font-size:11px;flex:0 0 auto}
.item .nm{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.item .sub{color:var(--dim);font-size:11px;margin-top:2px}
.badge{display:inline-block;min-width:18px;text-align:center;padding:0 5px;border-radius:6px;font-size:11px;background:#1e3050;color:var(--blue)}
.badge.zero{background:#2a1f24;color:#f59e9e}
.detail{overflow:auto;padding:22px 26px 60px}
.detail h2{margin:0 0 4px;font-size:20px;font-weight:600}
.detail .kicker{color:var(--dim);font-size:12px;margin-bottom:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin:0 0 18px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.stat .k{color:var(--dim);font-size:11px}
.stat .v{font-size:16px;font-weight:600;color:var(--accent)}
.hook{background:linear-gradient(180deg,#132238,#111b2e);border:1px solid var(--line);border-left:3px solid var(--amber);border-radius:10px;padding:12px 14px;margin:0 0 18px;font-size:14px}
.hook b{color:var(--amber);font-size:11px;letter-spacing:.1em;display:block;margin-bottom:4px;font-weight:600}
.sec{margin:0 0 18px}
.sec h3{margin:0 0 8px;font-size:12px;color:var(--dim);letter-spacing:.1em;font-weight:600}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{padding:3px 9px;border-radius:999px;background:#182740;border:1px solid var(--line);color:var(--ink);font-size:12px;cursor:pointer}
.chip:hover{border-color:var(--accent);color:var(--accent)}
.chip.plain{cursor:default}
.chip.plain:hover{border-color:var(--line);color:var(--ink)}
.chip.dim{color:var(--dim)}
.empty{color:var(--dim);font-size:12px}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid #1b2942;vertical-align:top}
th{color:var(--dim);font-weight:600;font-size:11px;letter-spacing:.06em}
td.q{font-family:ui-monospace,Consolas,monospace;color:var(--blue);white-space:nowrap}
td.ev{color:var(--dim)}
.role{font-size:11px;padding:1px 7px;border-radius:999px;white-space:nowrap}
.r-primary{background:#0f3b36;color:#5eead4}
.r-differential{background:#3a2a12;color:#fbbf24}
.r-related{background:#1b2a45;color:#93c5fd}
.legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--dim);font-size:11px;margin-top:10px}
.chain{display:flex;gap:4px;flex-wrap:wrap;align-items:center;color:var(--dim);font-size:11px;margin-top:6px}
.chain i{font-style:normal;color:#3d5677}
@media (max-width:820px){
.app{grid-template-columns:1fr;grid-template-rows:auto 1fr}
aside{max-height:44vh}
.detail{padding:16px}
}
</style>
</head>
<body>
<div class="app">
<aside>
  <div class="top">
    <h1>概念地图</h1>
    <div class="meta" id="meta"></div>
    <div class="tabs" id="tabs"></div>
  </div>
  <div class="search"><input id="q" placeholder="搜 K-ID 或标题…" autocomplete="off"></div>
  <div class="list" id="list"></div>
</aside>
<main>
  <div class="detail" id="detail"></div>
</main>
</div>
<script id="atlas-data" type="application/json">__DATA__</script>
<script>
(function(){
var D=JSON.parse(document.getElementById('atlas-data').textContent);
var byId={}; D.nodes.forEach(function(n){byId[n.id]=n;});
var cur=D.nodes.length?D.nodes[0].subject:'';
var sel=null, kw='';

function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function short(id){return id.split(':').pop();}

function renderTabs(){
  var h='';
  Object.keys(D.subjects).forEach(function(s){
    h+='<button class="tab'+(s===cur?' on':'')+'" data-s="'+esc(s)+'">'+esc(s)
      +' <span style="opacity:.6">'+D.subjects[s].nodes+'</span></button>';
  });
  document.getElementById('tabs').innerHTML=h;
  var m=D.subjects[cur];
  document.getElementById('meta').textContent=(m?m.batch+' · '+m.nodes+' 张卡 · '+m.questions+' 题':'')
    +' · 全库 '+D.stats.measures+' 条 measures / '+D.stats.prereq+' 条前置';
}

function renderList(){
  var nodes=D.nodes.filter(function(n){return n.subject===cur;});
  if(kw){var k=kw.toLowerCase();nodes=nodes.filter(function(n){return (n.did+' '+n.title).toLowerCase().indexOf(k)>=0;});}
  var g={}; nodes.forEach(function(n){(g[n.module]=g[n.module]||[]).push(n);});
  var mods=Object.keys(g).sort();
  var h='';
  mods.forEach(function(m){
    var list=g[m].slice().sort(function(a,b){return a.did<b.did?-1:1;});
    var qn=list.reduce(function(s,n){return s+n.weight;},0);
    h+='<div class="mod"><span>'+esc(m)+'</span><span><b>'+qn+'</b> 题</span></div>';
    list.forEach(function(n){
      h+='<div class="item'+(sel===n.id?' on':'')+'" data-id="'+esc(n.id)+'">'
        +'<div class="t"><span class="kid">'+esc(n.did)+'</span><span class="nm">'+esc(n.title)+'</span></div>'
        +'<div class="sub"><span class="badge'+(n.weight?'':' zero')+'">'+n.weight+' 题</span>'
        +(n.pre.length?' · 前置 '+n.pre.length:' · 模块起点')
        +(n.child.length?' · 后继 '+n.child.length:'')+'</div></div>';
    });
  });
  document.getElementById('list').innerHTML=h||'<div class="mod">无匹配</div>';
}

function chips(ids,cls){
  if(!ids||!ids.length) return '<span class="empty">—</span>';
  return ids.map(function(id){
    var n=byId[id];
    return '<span class="chip" data-id="'+esc(id)+'">'+esc(n?n.did:short(id))
      +(n?' · '+esc(n.title):'')+'</span>';
  }).join('');
}
function chipPlain(arr,pre){
  if(!arr||!arr.length) return '<span class="empty">—</span>';
  return arr.map(function(x){return '<span class="chip plain '+ (pre||'') +'">'+esc(x)+'</span>';}).join('');
}

function renderDetail(){
  var el=document.getElementById('detail');
  var n=sel?byId[sel]:null;
  if(!n){
    el.innerHTML='<div class="empty">左侧选一张卡</div>';
    return;
  }
  var primary=n.qs.filter(function(q){return q.role==='primary';}).length;
  var sec=n.qs.filter(function(q){return q.role!=='primary';}).length;
  var h='<h2>'+esc(n.did)+' '+esc(n.title)+'</h2>'
    +'<div class="kicker">'+esc(n.subject)+' · '+esc(n.module)
    +' · 教师重点 '+(n.kps.length?n.kps.map(function(x){return '第'+x+'条';}).join('、'):'—')
    +' · 教材 '+(n.pages.length?n.pages.map(function(p){return 'P'+p;}).join('、'):'—')
    +' · 主资料锚点 '+esc(n.anchor||'—')+'</div>';

  h+='<div class="grid">'
    +'<div class="stat"><div class="k">主概念题</div><div class="v">'+primary+'</div></div>'
    +'<div class="stat"><div class="k">次要概念命中</div><div class="v">'+sec+'</div></div>'
    +'<div class="stat"><div class="k">前置 / 后继</div><div class="v">'+n.pre.length+' / '+n.child.length+'</div></div>'
    +'<div class="stat"><div class="k">状态</div><div class="v" style="font-size:13px">'+esc(n.status)+'</div></div>'
    +'</div>';

  if(n.hook){h+='<div class="hook"><b>记忆钩子</b>'+esc(n.hook)+'</div>';}

  h+='<div class="sec"><h3>前置（学这张之前）</h3><div class="chips">'+chips(n.pre)+'</div></div>';
  h+='<div class="sec"><h3>后继（这张之后）</h3><div class="chips">'+chips(n.child)+'</div></div>';
  h+='<div class="sec"><h3>同锚点 / 同页关联</h3><div class="chips">'+chips(n.ref)+'</div></div>';

  h+='<div class="sec"><h3>关联题目（'+n.qs.length+'）</h3>';
  if(!n.qs.length){h+='<div class="empty">暂无题目</div>';}
  else{
    h+='<table><thead><tr><th>题号</th><th>角色</th><th>证据</th></tr></thead><tbody>';
    n.qs.forEach(function(q){
      h+='<tr><td class="q">'+esc(q.qid)+'</td>'
        +'<td><span class="role r-'+esc(q.role)+'">'+({primary:'主概念',differential:'鉴别',related:'相关'}[q.role]||q.role)+'</span></td>'
        +'<td class="ev">'+esc(q.ev||'—')+'</td></tr>';
    });
    h+='</tbody></table>';
  }
  h+='</div>';

  h+='<div class="legend"><span>主概念：这道题答错直接算这张卡</span>'
    +'<span>鉴别：干扰项对应的概念</span><span>相关：解析里顺带提到的概念</span></div>';

  el.innerHTML=h;
}

document.addEventListener('click',function(e){
  var t=e.target.closest('[data-id]');
  if(t){sel=t.getAttribute('data-id');renderList();renderDetail();
    var d=document.getElementById('detail'); if(d) d.scrollTop=0; return;}
  var tab=e.target.closest('[data-s]');
  if(tab){cur=tab.getAttribute('data-s');sel=null;renderTabs();renderList();renderDetail();}
});
document.getElementById('q').addEventListener('input',function(e){kw=e.target.value.trim();renderList();});

renderTabs();
sel=D.nodes.filter(function(n){return n.subject===cur;})[0].id;
renderList();renderDetail();
})();
</script>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="渲染概念地图预览")
    ap.add_argument("--graph", default=str(DEFAULT_GRAPH))
    ap.add_argument("--labels", default=str(DEFAULT_LABELS))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    graph = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    payload = build_payload(graph, Path(args.labels))
    html = TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"节点 {len(payload['nodes'])}　边 {payload['stats']}")
    print(f"→ {out}（{out.stat().st_size/1024:.0f} KB）")
    return 0


if __name__ == "__main__":
    _configure_stdio()
    raise SystemExit(main())

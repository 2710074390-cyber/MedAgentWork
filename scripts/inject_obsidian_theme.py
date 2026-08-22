#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inject_obsidian_theme.py v3 — MedAgentWork 押题卷「Obsidian 树」主题系统（幂等 + 自动升级）

功能：
1. 主题切换：默认主题 <-> Obsidian 树（深色紫调，参考 Obsidian 官方 Default 设计令牌）
2. 树形导航 v3（完整 Obsidian 文件树质感）：
   - 树线（indentation guide）：垂直引导线 + 条目水平折线，hover 亮起
   - 文件夹/文件图标（lucide 风格 SVG），文件夹随展开变色
   - 选中态：accent 背景 + 左侧指示条；IntersectionObserver 滚动跟踪当前题目
   - 折叠动画（chevron 旋转 + grid-rows 展开），分组折叠状态 localStorage 持久化
   - Obsidian 式交互：点击条目跳转后树保持打开，遮罩点击收起
3. localStorage 持久化主题/树状态，head 内联脚本防闪烁

用法：
  python inject_obsidian_theme.py <file.html> [file2.html ...]
  python inject_obsidian_theme.py --all          # 处理 最终产物/ 下全部押题卷 + index.html
  MAW_KEY_PREFIX=maw python inject_obsidian_theme.py <线上站押题卷...>   # 线上站 key 与 index 一致

幂等：已注入文件执行自动升级（反注入旧版 → 注入新版），不重复堆叠。
"""

import sys
import io
import re
import os
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = Path(__file__).resolve().parent.parent / "最终产物"

# key 前缀参数化：本地单页版用 maq（自洽），线上站（index 用 maw-theme）传 MAW_KEY_PREFIX=maw 保持跨页一致
PREFIX = os.environ.get("MAW_KEY_PREFIX", "maq")
THEME_KEY = f"{PREFIX}-theme"
TREE_KEY = f"{PREFIX}-tree"
GROUPS_KEY = f"{PREFIX}-tree-groups"

# ---------------------------------------------------------------- 注入内容

MARK_HTML = "<!-- maq-obsidian-tree -->\n"

HEAD_SCRIPT = MARK_HTML + """<script>
(function(){try{var t=localStorage.getItem('__THEME_KEY__');if(t==='obsidian')document.documentElement.setAttribute('data-theme','obsidian');var s=localStorage.getItem('__TREE_KEY__');if(s==='1'&&!document.documentElement.hasAttribute('data-tree'))document.documentElement.setAttribute('data-tree','1');}catch(e){}})();
</script>"""

OBSIDIAN_VARS = """html[data-theme="obsidian"]{--bg:#202020;--card:#282828;--card2:#2e2e2e;--gold:#7f6df2;--gold2:#8875ff;--accent:#483699;--accent2:#a882ff;--green:#44cf6e;--red:#fb464c;--text:#dcddde;--text2:#999;--blue:#027aff;--orange:#e9973f;--purple:#a882ff;--teal:#53dfdd}"""

# 无 :root 变量文件的浅色兜底变量（与原浅色页面协调）
FALLBACK_VARS = """:root{--bg:#eef1f5;--card:#ffffff;--card2:#f5f6f8;--gold:#1a73e8;--text:#1a1a2e;--text2:#666666;--accent2:#1a73e8}"""

CSS_EXTRA = """
/* ===== Obsidian 树 主题覆盖（参考 Obsidian 官方 Default dark 设计令牌） ===== */
html[data-theme="obsidian"] body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif;background:var(--bg);background-image:none;padding-top:132px}
html[data-theme="obsidian"] #topbar{background:linear-gradient(180deg,rgba(22,22,22,.98),rgba(32,32,32,.95));border-bottom:1px solid #333}
html[data-theme="obsidian"] #topbar h1{color:var(--gold);font-family:inherit;letter-spacing:1px}
html[data-theme="obsidian"] #topbar .decor{background:linear-gradient(90deg,var(--gold),transparent)}
html[data-theme="obsidian"] #topbar button{border-color:rgba(127,109,242,.4);color:var(--text2)}
html[data-theme="obsidian"] #topbar button:hover{border-color:var(--gold);color:var(--gold);background:rgba(127,109,242,.1)}
html[data-theme="obsidian"] #topbar .progress-wrap{background:rgba(255,255,255,.08);border-radius:4px}
html[data-theme="obsidian"] #topbar .progress-label{color:var(--text2)}
html[data-theme="obsidian"] #topbar .stat{color:var(--text2)}
html[data-theme="obsidian"] .question{background:var(--card);border:1px solid #333;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.3)}
html[data-theme="obsidian"] .question.correct{background:linear-gradient(135deg,var(--card),rgba(68,207,110,.05));border-left:3px solid var(--green)}
html[data-theme="obsidian"] .question.wrong{background:linear-gradient(135deg,var(--card),rgba(251,70,76,.05));border-left:3px solid var(--red)}
html[data-theme="obsidian"] .question::before{background:linear-gradient(90deg,transparent,rgba(127,109,242,.2),transparent)}
html[data-theme="obsidian"] .q-num{font-family:inherit;color:var(--accent2)}
html[data-theme="obsidian"] .q-stem{color:var(--text)}
html[data-theme="obsidian"] .option{border:1px solid rgba(255,255,255,.06);border-radius:6px;background:transparent;color:var(--text2)}
html[data-theme="obsidian"] .option:hover{border-color:var(--accent2);background:rgba(168,130,255,.08);color:var(--text)}
html[data-theme="obsidian"] .option.picked{background:rgba(168,130,255,.1);border-color:var(--purple)}
html[data-theme="obsidian"] .q-type.A1{border-color:rgba(83,223,221,.45);color:var(--teal)}
html[data-theme="obsidian"] .q-type.A2{border-color:rgba(2,122,255,.5);color:var(--blue)}
html[data-theme="obsidian"] .q-type.A3,.q-type.A4{border-color:rgba(251,70,76,.4);color:var(--red)}
html[data-theme="obsidian"] .q-type.B1{border-color:rgba(233,151,63,.5);color:var(--orange)}
html[data-theme="obsidian"] .q-type.X{border-color:rgba(168,130,255,.5);color:var(--purple)}
html[data-theme="obsidian"] .q-type.判断{border-color:rgba(83,223,221,.4);color:var(--teal)}
html[data-theme="obsidian"] .case-group{background:var(--card2);border-left:2px solid var(--blue);border-radius:8px}
html[data-theme="obsidian"] .case-header{background:rgba(2,122,255,.07);color:var(--text)}
html[data-theme="obsidian"] .b1-box{border-left:2px solid var(--orange);background:rgba(233,151,63,.05);color:var(--text2)}
html[data-theme="obsidian"] .exp{color:var(--text2)}
html[data-theme="obsidian"] .src{color:rgba(127,109,242,.7)}
html[data-theme="obsidian"] .footer{border-top:1px solid #333;color:var(--text2)}
html[data-theme="obsidian"] ::-webkit-scrollbar{width:8px;height:8px}
html[data-theme="obsidian"] ::-webkit-scrollbar-track{background:var(--bg)}
html[data-theme="obsidian"] ::-webkit-scrollbar-thumb{background:#3f3f3f;border-radius:4px}
html[data-theme="obsidian"] ::-webkit-scrollbar-thumb:hover{background:#555}
html[data-theme="obsidian"] .ans-head.green{color:var(--green)}
html[data-theme="obsidian"] .ans-head.red{color:var(--red)}
html[data-theme="obsidian"] #topbar .stat b{color:var(--gold)}
html[data-theme="obsidian"] .case-label{color:var(--blue)}
html[data-theme="obsidian"] .b1-label{color:var(--orange)}
/* 题目跳转闪烁高亮 */
.tree-flash{animation:treeFlash 1.2s ease}
@keyframes treeFlash{0%{box-shadow:0 0 0 2px var(--gold);background:rgba(201,168,76,.08)}100%{box-shadow:0 0 0 0 transparent}}
html[data-theme="obsidian"] .tree-flash{animation-name:treeFlashO}
@keyframes treeFlashO{0%{box-shadow:0 0 0 2px var(--gold);background:rgba(127,109,242,.12)}100%{box-shadow:0 0 0 0 transparent}}
/* ===== Obsidian 树 侧边栏 v3（树线/图标/选中态，参考 Obsidian 官方文件树） ===== */
#tree-panel{position:fixed;top:118px;left:0;bottom:0;width:320px;z-index:990;background:var(--card2);border-right:1px solid rgba(255,255,255,.06);transform:translateX(-102%);transition:transform .3s cubic-bezier(.2,.7,.2,1);display:flex;flex-direction:column;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif}
html[data-tree="1"] #tree-panel{transform:translateX(0)}
html[data-theme="obsidian"] #tree-panel{background:#161616;border-right:1px solid #333;box-shadow:2px 0 12px rgba(0,0,0,.4)}
#tree-panel .tree-header{display:flex;align-items:center;gap:6px;padding:10px 12px;font-size:12px;font-weight:600;color:var(--text);border-bottom:1px solid rgba(255,255,255,.06);letter-spacing:.5px;flex-shrink:0}
html[data-theme="obsidian"] #tree-panel .tree-header{border-bottom-color:#333;color:#dcddde}
#tree-panel .tree-header .t-ico{display:flex;color:var(--gold);flex-shrink:0}
#tree-panel .tree-header .t-ico svg{width:14px;height:14px}
#tree-panel .tree-header .t-title{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#tree-panel .t-btn{background:none;border:none;color:var(--text2);cursor:pointer;width:24px;height:24px;display:flex;align-items:center;justify-content:center;border-radius:4px;font-size:13px;transition:all .15s;flex-shrink:0}
#tree-panel .t-btn:hover{color:var(--gold);background:rgba(255,255,255,.07)}
html[data-theme="obsidian"] #tree-panel .t-btn:hover{background:rgba(255,255,255,.075)}
#tree-body{flex:1;overflow-y:auto;padding:6px 0 24px;font-size:13px}
#tree-body::-webkit-scrollbar{width:6px}
#tree-body::-webkit-scrollbar-thumb{background:rgba(255,255,255,.12);border-radius:3px}
html[data-theme="obsidian"] #tree-body::-webkit-scrollbar-thumb{background:#3f3f3f}
/* 分组 = 文件夹（chevron + folder 图标） */
.tree-group{user-select:none}
.tree-group>.g-head{display:flex;align-items:center;gap:7px;padding:6px 10px;cursor:pointer;font-size:12.5px;color:var(--text);border-radius:4px;margin:1px 6px;transition:background .15s;position:relative}
.tree-group>.g-head:hover{background:rgba(255,255,255,.06)}
html[data-theme="obsidian"] .tree-group>.g-head:hover{background:rgba(255,255,255,.075)}
.tree-group>.g-head .g-arrow{width:10px;height:10px;flex-shrink:0;color:var(--text2);transition:transform .18s ease}
.tree-group>.g-head .g-folder{display:flex;color:var(--text2);flex-shrink:0;transition:color .18s}
.tree-group>.g-head .g-folder svg{width:15px;height:15px}
.tree-group>.g-head .g-name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:500}
.tree-group>.g-head .g-count{font-size:11px;color:var(--text2);font-variant-numeric:tabular-nums}
.tree-group.open>.g-head .g-arrow{transform:rotate(90deg)}
.tree-group.open>.g-head .g-folder{color:var(--gold)}
html[data-theme="obsidian"] .tree-group.open>.g-head .g-folder{color:#a882ff}
/* 树线（Obsidian indentation guide）：垂直引导线 + 折叠动画（grid-rows） */
.tree-group>.g-items{display:grid;grid-template-rows:0fr;margin:0 6px 2px 21px;border-left:1px solid rgba(255,255,255,.09);transition:grid-template-rows .22s ease,border-color .22s ease}
html[data-theme="obsidian"] .tree-group>.g-items{border-left-color:rgba(255,255,255,.13)}
.tree-group.open>.g-items{grid-template-rows:1fr}
.tree-group:not(.open)>.g-items{border-left-color:transparent}
.g-items-inner{min-height:0;overflow:hidden}
/* 条目 = 文件（file 图标 + 题号 + 题干，hover/选中态） */
.t-item{display:flex;align-items:center;gap:8px;padding:4.5px 10px 4.5px 12px;cursor:pointer;font-size:12.5px;color:var(--text2);position:relative;transition:background .15s,color .15s;border-radius:0 4px 4px 0}
.t-item::before{content:'';position:absolute;left:-1px;top:50%;width:8px;height:1px;background:rgba(255,255,255,.09);transition:background .15s}
html[data-theme="obsidian"] .t-item::before{background:rgba(255,255,255,.13)}
.t-item:hover{background:rgba(255,255,255,.06);color:var(--text)}
.t-item:hover::before{background:rgba(255,255,255,.3)}
.t-item .t-file{display:flex;color:var(--text2);flex-shrink:0;transition:color .15s}
.t-item .t-file svg{width:13px;height:13px}
.t-item .t-no{font-size:11px;color:var(--text2);flex-shrink:0;min-width:24px;text-align:right;font-variant-numeric:tabular-nums;transition:color .15s}
.t-item .t-stem{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* 选中态：accent 背景 + 左侧指示条（Obsidian 风格） */
.t-item.active{background:rgba(127,109,242,.14);color:var(--text)}
.t-item.active::after{content:'';position:absolute;left:0;top:18%;bottom:18%;width:2.5px;border-radius:2px;background:var(--gold)}
.t-item.active .t-file{color:var(--accent2)}
.t-item.active .t-no{color:var(--gold)}
html[data-theme="obsidian"] .t-item.active{background:rgba(127,109,242,.16);color:#dcddde}
html[data-theme="obsidian"] .t-item.active::after{background:#a882ff}
html[data-theme="obsidian"] .t-item.active .t-no{color:#a882ff}
html[data-theme="obsidian"] .t-item.active .t-file{color:#a882ff}
#tree-scrim{position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:980;opacity:0;pointer-events:none;transition:opacity .25s}
html[data-tree="1"] #tree-scrim{opacity:1;pointer-events:auto}
"""

SIDEBAR_HTML = """<div id="tree-panel"><div class="tree-header"><span class="t-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/><path d="M12 10v6"/><path d="m9 13 3 3 3-3"/></svg></span><span class="t-title" id="tree-title"></span><button class="t-btn" id="tree-toggle-all" title="全部展开/折叠">⇅</button><button class="t-btn" onclick="Tree.close()" title="收起">✕</button></div><div id="tree-body"></div></div><div id="tree-scrim" onclick="Tree.close()"></div>"""

TREEBTN = '<button id="btn-tree" onclick="Tree.toggle()" title="目录树">☰</button>'
THEMEBTN = '<button id="btn-theme" onclick="Theme.toggle()" title="切换主题">◐</button>'

THEME_SCRIPT = """<script>
var Theme = {
  key:'__THEME_KEY__',
  get:function(){try{return localStorage.getItem(this.key)||'default'}catch(e){return 'default'}},
  set:function(t){try{localStorage.setItem(this.key,t)}catch(e){}document.documentElement.setAttribute('data-theme',t);var b=document.getElementById('btn-theme');if(b)b.textContent=t==='obsidian'?'🌲':'◐'},
  toggle:function(){this.set(this.get()==='obsidian'?'default':'obsidian')}
};
var Tree = {
  key:'__TREE_KEY__',
  groupsKey:'__GROUPS_KEY__',
  open:false,
  activeIdx:-1,
  SVG:{
    folder:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/></svg>',
    file:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>',
    chevron:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>'
  },
  toggle:function(){this.open=!this.open;try{localStorage.setItem(this.key,this.open?'1':'0')}catch(e){}document.documentElement.setAttribute('data-tree',this.open?'1':'0')},
  close:function(){this.open=false;try{localStorage.setItem(this.key,'0')}catch(e){}document.documentElement.setAttribute('data-tree','0')},
  build:function(data){
    var titleEl=document.getElementById('tree-title');
    if(titleEl){var h1=document.querySelector('#topbar h1');if(h1)titleEl.textContent=h1.textContent;}
    var groupsOpen={};
    try{groupsOpen=JSON.parse(localStorage.getItem(this.groupsKey)||'{}')}catch(e){groupsOpen={}}
    var order=['A1','A2','A3','A4','B1','X','判断'];
    var groups={},realNum=0;
    for(var i=0;i<data.length;i++){
      var q=data[i];
      if(q.t!=='q')continue;
      realNum++;
      var key=q.tp;
      if(!groups[key])groups[key]={items:[]};
      groups[key].items.push({no:realNum,idx:i,stem:q.s});
    }
    var body=document.getElementById('tree-body'),h='',g=0;
    for(;g<order.length;g++){
      var k=order[g];
      if(!groups[k])continue;
      var isOpen=groupsOpen[k]!==undefined?groupsOpen[k]:(g===0);
      h+='<div class="tree-group" data-g="'+k+'"'+(isOpen?' data-open="1"':'')+'><div class="g-head">'+this.SVG.chevron.replace('<svg','<svg class="g-arrow"')+'<span class="g-folder">'+this.SVG.folder+'</span><span class="g-name">'+k+' 题型</span><span class="g-count">'+groups[k].items.length+'</span></div><div class="g-items"><div class="g-items-inner">';
      for(var j=0;j<groups[k].items.length;j++){
        var it=groups[k].items[j];
        h+='<div class="t-item" data-idx="'+it.idx+'" title="第'+it.no+'题"><span class="t-file">'+this.SVG.file+'</span><span class="t-no">'+it.no+'</span><span class="t-stem">'+it.stem+'</span></div>';
      }
      h+='</div></div></div>';
    }
    body.innerHTML=h;
    var ges=body.querySelectorAll('.tree-group');
    for(var x=0;x<ges.length;x++){if(ges[x].getAttribute('data-open')==='1')ges[x].classList.add('open');}
    var self=this;
    var ghs=body.querySelectorAll('.g-head');
    for(var a=0;a<ghs.length;a++){
      ghs[a].addEventListener('click',function(){var gr=this.parentNode;gr.classList.toggle('open');self.persist();});
    }
    var items=body.querySelectorAll('.t-item');
    for(var b2=0;b2<items.length;b2++){
      items[b2].addEventListener('click',function(){var idx=parseInt(this.getAttribute('data-idx'),10);self.goTo(idx);});
    }
    var ta=document.getElementById('tree-toggle-all');
    if(ta){
      ta.onclick=function(){
        var anyClosed=body.querySelectorAll('.tree-group:not(.open)').length>0;
        for(var c=0;c<ges.length;c++)ges[c].classList.toggle('open',anyClosed);
        self.persist();
      };
    }
    this.watchScroll();
  },
  persist:function(){
    var o={},gs=document.querySelectorAll('.tree-group');
    for(var i=0;i<gs.length;i++)o[gs[i].getAttribute('data-g')]=gs[i].classList.contains('open');
    try{localStorage.setItem(this.groupsKey,JSON.stringify(o))}catch(e){}
  },
  goTo:function(idx){
    var el=document.getElementById('q'+idx);
    if(!el)return;
    el.scrollIntoView({behavior:'smooth',block:'center'});
    this.setActive(idx);
    el.classList.remove('tree-flash');void el.offsetWidth;el.classList.add('tree-flash');
    var t=this;
    setTimeout(function(){el.classList.remove('tree-flash')},1400);
    /* Obsidian 式：点击跳转后树保持打开，遮罩点击收起 */
  },
  setActive:function(idx){
    this.activeIdx=idx;
    var items=document.querySelectorAll('.t-item'),cur=null;
    for(var i=0;i<items.length;i++){
      var isA=parseInt(items[i].getAttribute('data-idx'),10)===idx;
      items[i].classList.toggle('active',isA);
      if(isA)cur=items[i];
    }
    if(cur&&cur.scrollIntoView)cur.scrollIntoView({block:'nearest'});
  },
  watchScroll:function(){
    if(!('IntersectionObserver' in window))return;
    var self=this,last=-1;
    var io=new IntersectionObserver(function(entries){
      var best=null,bestDist=1e9;
      var vh=window.innerHeight||document.documentElement.clientHeight;
      for(var i=0;i<entries.length;i++){
        if(!entries[i].isIntersecting)continue;
        var r=entries[i].boundingClientRect;
        var dist=Math.abs(r.top+r.height/2-vh/2);
        if(dist<bestDist){bestDist=dist;best=entries[i].target;}
      }
      if(best){
        var idx=parseInt(String(best.id).replace('q',\''),10);
        if(!isNaN(idx)&&idx!==last){last=idx;self.setActive(idx);}
      }
    },{threshold:[0.2,0.5,0.8]});
    var qs=document.querySelectorAll('.question');
    for(var j=0;j<qs.length;j++)io.observe(qs[j]);
  }
};
(function(){try{var t=Theme.get();if(t==='obsidian')Theme.set('obsidian');var s=localStorage.getItem('__TREE_KEY__');if(s==='1'){Tree.open=true;document.documentElement.setAttribute('data-tree','1');}}catch(e){}})();
</script>"""

# ---------------------------------------------------------------- 反注入（升级用）


def strip_old(html: str) -> str:
    """移除旧版（v1/v2）全部注入痕迹，恢复原始文件"""
    # 1. head 防闪烁 script（带标记）
    html = re.sub(r"<!-- maq-obsidian-tree -->\s*<script>(?:(?!</script>).)*</script>\s*", "", html, flags=re.S)
    # 2. Theme/Tree script 块
    html = re.sub(r"<script>(?:(?!</script>).)*?var Theme = \{(?:(?!</script>).)*?</script>\s*", "", html, flags=re.S)
    # 3. CSS_EXTRA（从 Obsidian 树 注释到 </style> 前）
    html = re.sub(r"/\* ===== Obsidian 树(?:(?!</style>).)*?(?=</style>)", "", html, flags=re.S)
    # 4. OBSIDIAN_VARS / FALLBACK（:root 后或 <style> 后）
    html = re.sub(r"(:root\{[^}]+\})html\[data-theme=\"obsidian\"\]\{--bg[^}]+\}", r"\1", html, flags=re.S)
    html = re.sub(r"<style>\s*:root\{[^}]+\}\s*html\[data-theme=\"obsidian\"\]\{--bg[^}]+\}", "<style>", html, flags=re.S)
    # 5. 侧边栏 DOM
    html = re.sub(r"<body>\s*(?:<div id=\"tree-panel\">|<div class=\"tree-header\">)(?:(?!</body>).)*?id=\"tree-scrim\"[^>]*></div>\s*", "<body>", html, flags=re.S)
    # 6. 按钮
    html = re.sub(r'<button id="btn-tree"[^>]*>☰</button>', "", html)
    html = re.sub(r'<button id="btn-theme"[^>]*>◐</button>', "", html)
    html = re.sub(r' onclick="Tree\.toggle\(\)" title="目录树">☰</button>', "", html)
    html = re.sub(r' onclick="Theme\.toggle\(\)" title="切换主题">◐</button>', "", html)
    html = re.sub(r'<button id="theme-fab"[^>]*>◐</button>', "", html)
    # 7. Tree.build 调用还原
    html = re.sub(r"render\(\);\s*updateBar\(\);\s*Tree\.build\(data\);", "render();\nupdateBar();", html)
    html = re.sub(r"render\(\);\s*\n\s*Tree\.build\(data\);\s*\n\s*updateBar\(\);", "render();\nupdateBar();", html)
    # 8. 进度条颜色还原
    html = html.replace("style.background='var(--green)'", "style.background='#00c853'")
    html = html.replace("style.background='var(--gold)'", "style.background='#c9a84c'")
    return html


# ---------------------------------------------------------------- 注入函数


def already_injected(html: str) -> bool:
    return "maq-obsidian-tree" in html


def inject_exam(html: str) -> str:
    # 1) head 防闪烁脚本
    html = html.replace("</head>", HEAD_SCRIPT + "</head>", 1)
    # 2) 变量：有 :root 则附加 Obsidian 变量；无则插兜底 + 变量
    m = re.search(r"(:root\{[^}]+\})", html)
    if m:
        html = html.replace(m.group(1), m.group(1) + OBSIDIAN_VARS, 1)
    else:
        html = html.replace(
            "<style>",
            "<style>" + FALLBACK_VARS + "\n" + OBSIDIAN_VARS,
            1,
        )
    # 3) 非变量覆盖 + 侧边栏样式
    html = html.replace("</style>", CSS_EXTRA + "</style>", 1)
    # 4) 侧边栏 DOM（body 后）
    html = html.replace("<body>", "<body>\n" + SIDEBAR_HTML, 1)
    # 5) 按钮（正则匹配所有 showAll 按钮变体，插在其后）
    btn_re = re.compile(r'(onclick="Quiz\.showAll\(\)">[^<]*</button>)')
    mm = btn_re.search(html)
    if mm:
        html = html[: mm.end()] + TREEBTN + THEMEBTN + html[mm.end():]
    # 6) Theme/Tree JS（插在 Quiz 块的 <script> 开标签之前——不能插在 var Quiz 前，
    #    否则 THEME_SCRIPT 自带 </script> 会提前闭合原始 <script>，把 Quiz 代码挤出 script 块）
    m6 = re.search(r"<script>\s*\n\s*var Quiz = \(function\(\)\{", html)
    if m6:
        html = html[: m6.start()] + THEME_SCRIPT + html[m6.start():]
    # 7) 构建树（render(); 调用后）
    idx = html.rfind("render();")
    if idx >= 0:
        html = html[: idx + len("render();")] + "\nTree.build(data);" + html[idx + len("render();"):]
    # 8) JS 硬编码进度条颜色 → 变量（Obsidian 下自动跟随，可选替换）
    html = html.replace("style.background='#00c853'", "style.background='var(--green)'")
    html = html.replace("style.background='#c9a84c'", "style.background='var(--gold)'")
    return html


INDEX_CSS = """html[data-theme="obsidian"] body{background:#202020;padding-top:40px}
html[data-theme="obsidian"] h1{color:#dcddde}
html[data-theme="obsidian"] .subtitle{color:#999}
html[data-theme="obsidian"] .section-title{color:#999}
html[data-theme="obsidian"] .card{background:#282828;border:1px solid #333;border-radius:8px}
html[data-theme="obsidian"] .card:hover{background:#303030;border-color:#7f6df2;transform:translateX(4px);box-shadow:0 4px 24px rgba(0,0,0,.4)}
html[data-theme="obsidian"] .card .icon{background:rgba(255,255,255,.06);border-radius:6px}
html[data-theme="obsidian"] .card .info h2{color:#dcddde}
html[data-theme="obsidian"] .card .info p{color:#999}
html[data-theme="obsidian"] .badge-new{background:rgba(68,207,110,.15);color:#44cf6e}
html[data-theme="obsidian"] .badge-hot{background:rgba(251,70,76,.15);color:#fb464c}
html[data-theme="obsidian"] .footer{color:#666}
html[data-theme="obsidian"] .footer a{color:#999}
#theme-fab{position:fixed;top:16px;right:20px;z-index:1000;width:38px;height:38px;border-radius:50%;border:1px solid rgba(255,255,255,.25);background:rgba(255,255,255,.1);color:#fff;font-size:16px;cursor:pointer;backdrop-filter:blur(8px);transition:all .25s}
#theme-fab:hover{transform:scale(1.08);border-color:#fff}
html[data-theme="obsidian"] #theme-fab{background:#282828;border-color:#333;color:#dcddde}
html[data-theme="obsidian"] #theme-fab:hover{border-color:#7f6df2}
/* ===== Obsidian 工作区编排（obsidian 主题专用布局：文件树 + 内容区） ===== */
#ob-layout{display:none}
html[data-theme="obsidian"] .masthead,html[data-theme="obsidian"] .view,html[data-theme="obsidian"] .colophon{display:none!important}
html[data-theme="obsidian"] #ob-layout{display:flex;margin:14px -32px 0;min-height:calc(100vh - 130px);align-items:stretch}
html[data-theme="obsidian"] .wrap{max-width:none}
html[data-theme="obsidian"] .toolbar{margin-bottom:0}
#ob-sidebar{width:300px;flex-shrink:0;background:#161616;border-right:1px solid #333;display:flex;flex-direction:column;overflow:hidden}
#ob-sidebar .ob-sb-head{display:flex;align-items:center;gap:8px;padding:12px 14px;font-size:13px;font-weight:700;color:#dcddde;border-bottom:1px solid #333;letter-spacing:.5px;flex-shrink:0}
#ob-sidebar .ob-sb-head svg{width:15px;height:15px;color:#a882ff}
#ob-sidebar .ob-sb-head .ob-vault-sub{font-size:11px;color:#666;font-weight:400;margin-left:4px}
#ob-tree{flex:1;overflow-y:auto;padding:8px 0 20px;font-size:13px;user-select:none}
#ob-tree::-webkit-scrollbar{width:6px}
#ob-tree::-webkit-scrollbar-thumb{background:#3f3f3f;border-radius:3px}
/* 树：复用押题卷树的视觉语言（树线/图标/选中态） */
#ob-tree .tree-group>.g-head{display:flex;align-items:center;gap:7px;padding:6px 10px;cursor:pointer;font-size:12.5px;color:#dcddde;border-radius:4px;margin:1px 6px;transition:background .15s;position:relative}
#ob-tree .tree-group>.g-head:hover{background:rgba(255,255,255,.075)}
#ob-tree .tree-group>.g-head .g-arrow{width:10px;height:10px;flex-shrink:0;color:#666;transition:transform .18s ease}
#ob-tree .tree-group>.g-head .g-folder{display:flex;color:#666;flex-shrink:0;transition:color .18s}
#ob-tree .tree-group>.g-head .g-folder svg{width:15px;height:15px}
#ob-tree .tree-group>.g-head .g-name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:500}
#ob-tree .tree-group>.g-head .g-count{font-size:11px;color:#666;font-variant-numeric:tabular-nums}
#ob-tree .tree-group.open>.g-head .g-arrow{transform:rotate(90deg)}
#ob-tree .tree-group.open>.g-head .g-folder{color:#a882ff}
#ob-tree .tree-group>.g-items{display:grid;grid-template-rows:0fr;margin:0 6px 2px 21px;border-left:1px solid rgba(255,255,255,.13);transition:grid-template-rows .22s ease,border-color .22s ease}
#ob-tree .tree-group.open>.g-items{grid-template-rows:1fr}
#ob-tree .tree-group:not(.open)>.g-items{border-left-color:transparent}
#ob-tree .g-items-inner{min-height:0;overflow:hidden}
#ob-tree .t-item{display:flex;align-items:center;gap:8px;padding:4.5px 10px 4.5px 12px;cursor:pointer;font-size:12.5px;color:#999;position:relative;transition:background .15s,color .15s;border-radius:0 4px 4px 0}
#ob-tree .t-item::before{content:'';position:absolute;left:-1px;top:50%;width:8px;height:1px;background:rgba(255,255,255,.13);transition:background .15s}
#ob-tree .t-item:hover{background:rgba(255,255,255,.075);color:#dcddde}
#ob-tree .t-item:hover::before{background:rgba(255,255,255,.3)}
#ob-tree .t-item .t-file{display:flex;color:#666;flex-shrink:0}
#ob-tree .t-item .t-file svg{width:13px;height:13px}
#ob-tree .t-item .t-stem{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#ob-tree .t-item.active{background:rgba(127,109,242,.16);color:#dcddde}
#ob-tree .t-item.active::after{content:'';position:absolute;left:0;top:18%;bottom:18%;width:2.5px;border-radius:2px;background:#a882ff}
#ob-tree .t-item.active .t-file{color:#a882ff}
/* 内容区（Obsidian 阅读模式感） */
#ob-main{flex:1;min-width:0;background:#202020;padding:36px 52px 60px;overflow-y:auto}
#ob-main::-webkit-scrollbar{width:8px}
#ob-main::-webkit-scrollbar-thumb{background:#3f3f3f;border-radius:4px}
.ob-path{font-family:"Cascadia Code","SF Mono",Consolas,monospace;font-size:11px;color:#666;letter-spacing:.08em;margin-bottom:28px;padding-bottom:12px;border-bottom:1px solid #333;display:flex;align-items:center;gap:6px}
.ob-path .seg{color:#666}
.ob-path .seg.current{color:#a882ff}
.ob-path .sep{opacity:.5}
.ob-doc{max-width:720px}
.ob-doc .ob-doc-icon{width:52px;height:52px;border:1px solid #333;border-radius:10px;display:flex;align-items:center;justify-content:center;background:#282828;font-size:24px;margin-bottom:20px}
.ob-doc h2{font-size:30px;font-weight:700;color:#e6e6e6;margin:0 0 8px;letter-spacing:.01em}
.ob-doc .ob-doc-meta{font-family:"Cascadia Code","SF Mono",Consolas,monospace;font-size:12px;color:#666;letter-spacing:.1em;margin-bottom:18px;text-transform:uppercase}
.ob-doc .ob-doc-desc{font-size:14.5px;color:#999;line-height:1.9;margin-bottom:32px}
.ob-doc .ob-doc-rule{height:1px;background:linear-gradient(90deg,#333,transparent);margin-bottom:28px}
.ob-actions{display:flex;flex-wrap:wrap;gap:10px}
.ob-btn{padding:9px 20px;font-size:12.5px;font-weight:600;letter-spacing:.03em;border:1px solid #7f6df2;background:transparent;color:#a882ff;cursor:pointer;transition:all .2s;border-radius:4px;font-family:inherit}
.ob-btn:hover{background:#7f6df2;color:#202020}
.ob-btn.ghost{border-color:#555;color:#999}
.ob-btn.ghost:hover{background:#555;color:#e6e6e6;border-color:#555}
.ob-empty{padding:80px 20px;text-align:center;color:#666;font-size:14px}
.ob-empty .ob-empty-ico{font-size:40px;margin-bottom:14px;opacity:.6}"""

INDEX_LAYOUT = """<div id="ob-layout">
  <div id="ob-sidebar">
    <div class="ob-sb-head"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/><path d="M12 10v6"/><path d="m9 13 3 3 3-3"/></svg>MedAgentWork<span class="ob-vault-sub" id="ob-vault-count"></span></div>
    <div id="ob-tree"></div>
  </div>
  <div id="ob-main">
    <div class="ob-path" id="ob-path"></div>
    <div class="ob-doc" id="ob-doc"></div>
  </div>
</div>"""

INDEX_JS = """<script>
/* ===== Obsidian 工作区（文件树 + 内容区） ===== */
(function(){
  var VSVG={
    folder:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/></svg>',
    file:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>',
    chev:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>'
  };
  var groupsKey='__GROUPS_KEY__';
  var gOpen={};try{gOpen=JSON.parse(localStorage.getItem(groupsKey)||'{}')}catch(e){}
  var vault=null;
  /* 注意：页面用 const 声明 EXAMS/BANKS/REVIEWS（全局词法环境，不挂 window），直接 typeof 检测 */
  try{ if(typeof EXAMS!=='undefined'&&typeof BANKS!=='undefined'&&typeof REVIEWS!=='undefined') vault={exam:EXAMS,bank:BANKS,review:REVIEWS}; }catch(e){}
  if(!vault) vault={exam:[{name:'神经病学押题卷',html:'神经病学押题卷_117题.html',desc:'117 题 · batch020',meta:'HOT'},{name:'中医学押题卷',html:'中医学押题卷_95题.html',desc:'95 题 · batch021',meta:'HOT'}],bank:[],review:[]};
  var KINDS=[{k:'exam',label:'押题卷'},{k:'bank',label:'题库'},{k:'review',label:'复习资料'}];
  /* 注意：以下 JS 字符串内的 \' 是 Python 层转义，输出后为 JS 的 \'（反斜杠保留） */
  function pv(){
    var o={};var gs=document.querySelectorAll('#ob-tree .tree-group');
    for(var i=0;i<gs.length;i++)o[gs[i].getAttribute('data-g')]=gs[i].classList.contains('open');
    try{localStorage.setItem(groupsKey,JSON.stringify(o))}catch(e){}
  }
  function buildVault(){
    var total=vault.exam.length+vault.bank.length+vault.review.length;
    var c=document.getElementById('ob-vault-count');if(c)c.textContent=total+' 个文件';
    var h='';
    for(var z=0;z<KINDS.length;z++){
      var kd=KINDS[z],arr=vault[kd.k];
      if(!arr||!arr.length)continue;
      var isOpen=gOpen[kd.k]!==undefined?gOpen[kd.k]:(z===0);
      h+='<div class="tree-group" data-g="'+kd.k+'"'+(isOpen?' data-open="1"':'')+'><div class="g-head">'+VSVG.chev.replace('<svg','<svg class="g-arrow"')+'<span class="g-folder">'+VSVG.folder+'</span><span class="g-name">'+kd.label+'</span><span class="g-count">'+arr.length+'</span></div><div class="g-items"><div class="g-items-inner">';
      for(var i=0;i<arr.length;i++){
        h+='<div class="t-item" data-kind="'+kd.k+'" data-i="'+i+'" title="'+arr[i].name+'"><span class="t-file">'+VSVG.file+'</span><span class="t-stem">'+arr[i].name+'</span></div>';
      }
      h+='</div></div></div>';
    }
    var tree=document.getElementById('ob-tree');
    tree.innerHTML=h;
    var ges=tree.querySelectorAll('.tree-group');
    for(var x=0;x<ges.length;x++){if(ges[x].getAttribute('data-open')==='1')ges[x].classList.add('open');}
    var ghs=tree.querySelectorAll('.g-head');
    for(var a=0;a<ghs.length;a++){
      ghs[a].addEventListener('click',function(){var gr=this.parentNode;gr.classList.toggle('open');pv();});
    }
    var its=tree.querySelectorAll('.t-item');
    for(var b=0;b<its.length;b++){
      its[b].addEventListener('click',function(){showDoc(this.getAttribute('data-kind'),parseInt(this.getAttribute('data-i'),10));});
    }
    var first=tree.querySelector('.t-item');
    if(first)showDoc(first.getAttribute('data-kind'),parseInt(first.getAttribute('data-i'),10));
  }
  var ICO={'内科学':'🫀','精神病学':'🧠','神经病学':'⚡','医患沟通':'💬','外科学':'🔪','中医学':'🌿','中医心理学':'🧘'};
  function iconOf(name){var m=name.match(/^(内科学|精神病学|神经病学|医患沟通|外科学|中医学|中医心理学)/);return m?ICO[m[1]]:'📄';}
  function showDoc(kind,i){
    var arr=vault[kind];if(!arr||!arr[i])return;
    var it=arr[i];
    var label=kind==='exam'?'押题卷':kind==='bank'?'题库':'复习资料';
    var its=document.querySelectorAll('#ob-tree .t-item');
    for(var a=0;a<its.length;a++)its[a].classList.remove('active');
    var cur=document.querySelector('#ob-tree .t-item[data-kind="'+kind+'"][data-i="'+i+'"]');
    if(cur)cur.classList.add('active');
    var path=document.getElementById('ob-path');
    path.innerHTML='<span class="seg">MedAgentWork</span><span class="sep">/</span><span class="seg">'+label+'</span><span class="sep">/</span><span class="seg current">'+it.name+'</span>';
    var meta=it.meta?it.meta:(it.pdf?it.pdf.split('/').pop():it.md?it.md.split('/').pop():'');
    var desc=it.desc||'';
    var btns='';
    if(kind==='exam'){
      btns+=\'<button class="ob-btn" onclick="viewOnline(\\'\'+it.html+\'\\')">👁 在线答题</button>\';
      btns+=\'<button class="ob-btn ghost" onclick="printHTML(\\'\'+it.html+\'\\')">🖨 打印 PDF</button>\';
    }else if(kind==='bank'){
      btns+=\'<button class="ob-btn" onclick="previewPDF(\\''+it.pdf+'\\',\\''+it.name+'\\')">👁 预览</button>\';
      btns+=\'<button class="ob-btn ghost" onclick="downloadFile(\\''+it.pdf+'\\',\\''+it.pdf.split('/').pop()+'\\')">⬇ 下载 PDF</button>\';
    }else{
      btns+=\'<button class="ob-btn" onclick="previewMD(\\''+it.md+'\\',\\''+it.name+'\\')">👁 预览</button>\';
      btns+=\'<button class="ob-btn ghost" onclick="downloadFile(\\''+it.md+'\\',\\''+it.md.split('/').pop()+'\\')">⬇ 下载 MD</button>\';
      if(it.html){btns+=\'<button class="ob-btn ghost" onclick="viewOnline(\\'\'+it.html+\'\\')">↗ HTML</button><button class="ob-btn ghost" onclick="printHTML(\\'\'+it.html+\'\\')">🖨 打印</button>\';}
    }
    var doc=document.getElementById('ob-doc');
    doc.innerHTML='<div class="ob-doc-icon">'+iconOf(it.name)+'</div><h2>'+it.name+'</h2><div class="ob-doc-meta">'+meta+'</div><div class="ob-doc-desc">'+desc+'</div><div class="ob-doc-rule"></div><div class="ob-actions">'+btns+'</div>';
    document.getElementById('ob-main').scrollTop=0;
  }
  buildVault();
})();
</script>"""


def inject_index(html: str) -> str:
    html = html.replace("</style>", INDEX_CSS + "</style>", 1)
    html = html.replace("</head>", HEAD_SCRIPT + THEME_SCRIPT + "</head>", 1)
    # 注：主 script 的打印模板内含 </body> 字符串，必须用 rfind 定位真正的闭合标签
    bi = html.rfind("</body>")
    if bi >= 0:
        html = html[:bi] + INDEX_LAYOUT + INDEX_JS + "\n</body>" + html[bi + len("</body>"):]
    # 无工具栏圆点（.theme-switch）的简化入口页才加 fab 悬浮按钮
    if '<button id="theme-fab"' not in html and ".theme-switch" not in html:
        html = html.replace(
            "<body>",
            '<body>\n<button id="theme-fab" onclick="Theme.toggle()" title="切换主题">◐</button>',
            1,
        )
    return html


def remove_index_manual(html: str) -> str:
    """移除 index 页面手工添加的 obsidian 主题块（线上站版：变量块/细节覆盖/圆点/按钮）"""
    # 1. 变量块 + 细节覆盖（55-78 行区域）
    block = """:root[data-theme="obsidian"] {
  --paper:#202020; --paper-2:#282828; --paper-edge:#333333;
  --ink:#dcddde; --ink-soft:#999999; --ink-faint:#666666;
  --moss:#7f6df2; --moss-deep:#483699; --oxblood:#fb464c; --ochre:#e9973f;
  --rule:rgba(220,221,222,0.14); --rule-soft:rgba(220,221,222,0.07);
  --card-bg:rgba(40,40,40,0.85); --card-hover-bg:rgba(48,48,48,0.95);
  --accent:#7f6df2; --hero:#e6e6e6;
  --f-display:"PingFang SC","Microsoft YaHei",system-ui,sans-serif;
  --f-body:"PingFang SC","Microsoft YaHei",system-ui,sans-serif;
  --f-mono:"SF Mono","Cascadia Code",Consolas,monospace;
  --noise:0;
}
:root[data-theme="obsidian"] body::before { background:radial-gradient(ellipse 60% 50% at 50% 0%, rgba(127,109,242,0.07), transparent 70%); }
:root[data-theme="obsidian"] .term-tab.active { color:var(--moss); }
:root[data-theme="obsidian"] .masthead h1 .red,
:root[data-theme="obsidian"] .masthead .tagline,
:root[data-theme="obsidian"] .section-num,
:root[data-theme="obsidian"] .coming p { font-style:normal; }
:root[data-theme="obsidian"] .card:hover { box-shadow:0 18px 40px -18px rgba(0,0,0,0.6); border-color:var(--moss); }
:root[data-theme="obsidian"] .btn.primary { background:var(--moss-deep); border-color:var(--moss-deep); }
:root[data-theme="obsidian"] .btn.primary:hover { background:var(--oxblood); border-color:var(--oxblood); }
:root[data-theme="obsidian"] .colophon a { color:var(--moss); }
:root[data-theme="obsidian"] .colophon .mark { font-style:normal; }
"""
    html = html.replace(block, "", 1)
    # 2. 圆点样式
    html = re.sub(r"\n\.theme-btn\[data-t=\"obsidian\"\]\{[^\n]*\}\n", "\n", html, count=1)
    # 3. HTML 圆点按钮
    html = re.sub(r"\s*<button class=\"theme-btn\" data-t=\"obsidian\"[^>]*></button>", "", html, count=1)
    # 4. html 标签上的 data-theme 初始值还原为 classic
    html = re.sub(r'<html lang="zh-CN" data-theme="obsidian">', '<html lang="zh-CN" data-theme="classic">', html, count=1)
    return html


def process(path: Path, remove: bool = False) -> bool:
    html = path.read_text(encoding="utf-8")
    upgraded = False
    if remove:
        if already_injected(html):
            html = strip_old(html)
        if "grid-exam" in html or "theme-switch" in html:
            html = remove_index_manual(html)
        path.write_text(html, encoding="utf-8")
        print(f"  ✖  {path.name} — Obsidian 主题已移除")
        return True
    if already_injected(html):
        print(f"  ↻  {path.name} — 检测到旧注入，执行升级（反注入 → 重注入）")
        html = strip_old(html)
        upgraded = True
    if "quiz-root" in html:
        html = inject_exam(html)
        html = html.replace("__THEME_KEY__", THEME_KEY).replace("__TREE_KEY__", TREE_KEY).replace("__GROUPS_KEY__", GROUPS_KEY)
    elif 'class="card"' in html or "grid-exam" in html or "theme-switch" in html:
        html = inject_index(html)
        html = html.replace("__THEME_KEY__", THEME_KEY).replace("__TREE_KEY__", TREE_KEY).replace("__GROUPS_KEY__", GROUPS_KEY)
    else:
        print(f"  ⚠  {path.name} — 无法识别类型，跳过")
        return False
    path.write_text(html, encoding="utf-8")
    print(f"  ✔  {path.name} — {'升级完成' if upgraded else '注入完成'}")
    return True


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    remove = "--remove" in args
    args = [a for a in args if a != "--remove"]
    if args == ["--all"]:
        targets = sorted(BASE.glob("*押题卷*.html")) + [BASE / "index.html"]
    else:
        targets = [Path(a) for a in args]
    print(f"目标 {len(targets)} 个文件（模式：{'移除' if remove else '注入'}）：")
    for t in targets:
        if not t.exists():
            print(f"  ✘  {t} — 不存在")
            continue
        process(t, remove=remove)
    print("完成。")


if __name__ == "__main__":
    main()

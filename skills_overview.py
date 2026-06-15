#!/usr/bin/env python3
"""
Claude Skills & Agents Overview
Portable browser-based dashboard for your Claude Code installation.

Usage:  python skills_overview.py
        Opens http://localhost:8765 automatically in your browser.

Requirements: Python 3.8+  (no pip installs needed — stdlib only)
Portability:  Reads ~/.claude on any OS / user.  Copy & run.
"""

import json
import re
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Timer

# ── Configuration ─────────────────────────────────────────────────────────────
PORT = 8765
CLAUDE_DIR  = Path.home() / ".claude"
SKILLS_DIR  = CLAUDE_DIR / "skills"
AGENTS_DIR  = CLAUDE_DIR / "agents"
STATE_FILE  = CLAUDE_DIR / ".skills_overview_state.json"
CACHE_FILE  = CLAUDE_DIR / ".skills_overview_cache.json"

# ── Category definitions ───────────────────────────────────────────────────────
CATEGORY_DEFS = [
    {
        "id": "gsd",
        "label": "GSD – Project Management",
        "color": "#4F46E5",
        "icon": "\U0001f4cb",
        "prefixes": ["gsd-"],
        "exact": [],
    },
    {
        "id": "seo",
        "label": "SEO",
        "color": "#059669",
        "icon": "\U0001f50d",
        "prefixes": ["seo-"],
        "exact": ["seo"],
    },
    {
        "id": "dev",
        "label": "Development & Engineering",
        "color": "#DC2626",
        "icon": "⚙️",
        "prefixes": [
            "agent-", "code-", "hook-", "mcp-", "plugin-", "test-",
            "systematic-", "frontend-", "receiving-", "requesting-",
            "using-", "finishing-", "verification-", "dispatching-",
            "skill-", "writing-", "executing-", "keyword-",
        ],
        "exact": [
            "brainstorming", "deep-research", "update-config",
            "keybindings-help", "verify", "run", "init", "review",
            "security-review", "simplify", "schedule", "loop",
            "claude-api", "fewer-permission-prompts", "find-skills",
        ],
    },
    {
        "id": "agents",
        "label": "Agents",
        "color": "#7C3AED",
        "icon": "\U0001f916",
        "prefixes": [],
        "exact": [],
        "special": "agents",
    },
    {
        "id": "other",
        "label": "Overig / Utilities",
        "color": "#B45309",
        "icon": "\U0001f527",
        "prefixes": [],
        "exact": [],
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> dict:
    """Extract name and description from YAML frontmatter block."""
    result = {"name": "", "description": ""}
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return result
    fm = m.group(1)

    nm = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
    if nm:
        result["name"] = nm.group(1).strip().strip("\"'")

    dm = re.search(r"^description:\s*(.*)$", fm, re.MULTILINE)
    if dm:
        first = dm.group(1).strip()
        if first in ("|", ">", "|-", ">-", ""):
            lines = fm.splitlines()
            desc_lines = []
            capturing = False
            for line in lines:
                if re.match(r"^description:", line):
                    capturing = True
                    continue
                if capturing:
                    if line and not line[0].isspace():
                        break
                    desc_lines.append(line.strip())
            result["description"] = " ".join(l for l in desc_lines if l)
        else:
            result["description"] = first.strip("\"'")

    return result


def get_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def categorize(dir_name: str) -> str:
    dn = dir_name.lower()
    for cat in CATEGORY_DEFS:
        if cat.get("special") == "agents" or cat["id"] == "other":
            continue
        for prefix in cat.get("prefixes", []):
            if dn.startswith(prefix):
                return cat["id"]
        if dn in cat.get("exact", []):
            return cat["id"]
    return "other"


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"last_mtime": 0.0, "last_count": 0}


def save_state(mtime: float, count: int) -> None:
    try:
        STATE_FILE.write_text(
            json.dumps({"last_mtime": mtime, "last_count": count}),
            encoding="utf-8",
        )
    except Exception:
        pass


def load_cache() -> dict:
    """Load persisted scan results. Returns dict keyed by dir_name."""
    try:
        entries = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        return {e["dir_name"]: e for e in entries if "dir_name" in e}
    except Exception:
        return {}


def save_cache(items: list) -> None:
    """Persist current scan results for next run."""
    try:
        CACHE_FILE.write_text(json.dumps(items, default=str), encoding="utf-8")
    except Exception:
        pass


# ── Scanner ───────────────────────────────────────────────────────────────────

def scan_all() -> dict:
    """Incremental scan: only re-reads files whose mtime changed since cache."""
    cache = load_cache()
    seen_keys: set = set()
    items = []
    added: list = []
    newest_mtime = 0.0

    if SKILLS_DIR.exists():
        for skill_dir in sorted(SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            dn = skill_dir.name
            mtime = get_mtime(skill_md)
            newest_mtime = max(newest_mtime, mtime)
            seen_keys.add(dn)

            cached = cache.get(dn)
            if cached and cached.get("mtime") == mtime:
                items.append(dict(cached))
            else:
                try:
                    content = skill_md.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    content = ""
                fm = parse_frontmatter(content)
                items.append({
                    "name":        fm["name"] or dn,
                    "dir_name":    dn,
                    "description": fm["description"] or "(geen beschrijving)",
                    "type":        "skill",
                    "category":    categorize(dn),
                    "mtime":       mtime,
                })
                if dn not in cache:
                    added.append(dn)

    if AGENTS_DIR.exists():
        for agent_file in sorted(AGENTS_DIR.glob("*.md")):
            dn = agent_file.stem
            mtime = get_mtime(agent_file)
            newest_mtime = max(newest_mtime, mtime)
            seen_keys.add(dn)

            cached = cache.get(dn)
            if cached and cached.get("mtime") == mtime:
                items.append(dict(cached))
            else:
                try:
                    content = agent_file.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    content = ""
                fm = parse_frontmatter(content)
                items.append({
                    "name":        fm["name"] or dn,
                    "dir_name":    dn,
                    "description": fm["description"] or "(geen beschrijving)",
                    "type":        "agent",
                    "category":    "agents",
                    "mtime":       mtime,
                })
                if dn not in cache:
                    added.append(dn)

    removed = [k for k in cache if k not in seen_keys]
    save_cache(items)

    categories = [
        {
            "id":    cat["id"],
            "label": cat["label"],
            "color": cat["color"],
            "icon":  cat["icon"],
            "count": sum(1 for i in items if i["category"] == cat["id"]),
        }
        for cat in CATEGORY_DEFS
    ]

    return {
        "items":        items,
        "categories":   categories,
        "total":        len(items),
        "newest_mtime": newest_mtime,
        "claude_dir":   str(CLAUDE_DIR),
        "added":        added,
        "removed":      removed,
    }


# ── Server state ──────────────────────────────────────────────────────────────
_startup_info: dict = {}
_last_api_mtime: float = 0.0


# ── HTTP Handler ──────────────────────────────────────────────────────────────

class SkillsHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._respond(200, "text/html; charset=utf-8", HTML.encode("utf-8"))
        elif self.path == "/api/skills":
            self._serve_api()
        else:
            self.send_error(404)

    def _respond(self, code: int, ctype: str, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _serve_api(self):
        global _last_api_mtime
        data = scan_all()
        _last_api_mtime = data["newest_mtime"]

        data["changed"] = bool(data["added"] or data["removed"])
        data["startup_has_changes"] = _startup_info.get("has_changes", False)
        data["startup_delta_count"]  = _startup_info.get("delta_count", 0)

        body = json.dumps(data, default=str).encode("utf-8")
        self._respond(200, "application/json", body)


# ── HTML (embedded) ───────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claude Skills &amp; Agents</title>
<style>
:root{
  --bg:#F0F2F5;--surface:#fff;--border:#E5E7EB;
  --text:#111827;--muted:#6B7280;
  --accent:#5B21B6;--accent-light:#EDE9FE;
  --r:10px;
  --sh:0 1px 3px rgba(0,0,0,.07),0 1px 2px rgba(0,0,0,.04);
  --sh-md:0 4px 12px rgba(0,0,0,.10),0 2px 4px rgba(0,0,0,.05);
}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
     background:var(--bg);color:var(--text);min-height:100vh;}

/* ── Header ── */
header{position:sticky;top:0;z-index:100;background:var(--surface);
       border-bottom:1px solid var(--border);
       padding:10px 24px;display:flex;align-items:center;gap:16px;
       box-shadow:var(--sh);}
.brand{display:flex;align-items:center;gap:10px;flex-shrink:0;}
.brand-icon{width:32px;height:32px;background:var(--accent);border-radius:8px;
            display:flex;align-items:center;justify-content:center;
            font-size:18px;color:#fff;}
.brand h1{font-size:17px;font-weight:700;color:var(--accent);white-space:nowrap;}
.controls{display:flex;align-items:center;gap:10px;flex:1;
          max-width:560px;margin-left:auto;}
#search{flex:1;padding:8px 14px;border:1px solid var(--border);border-radius:8px;
        font-size:14px;background:var(--bg);outline:none;transition:border-color .15s;}
#search:focus{border-color:var(--accent);}
#refresh-btn{display:flex;align-items:center;gap:6px;padding:8px 18px;
             background:var(--accent);color:#fff;border:none;border-radius:8px;
             font-size:14px;font-weight:600;cursor:pointer;
             transition:opacity .15s,transform .1s;white-space:nowrap;}
#refresh-btn:hover{opacity:.88;}
#refresh-btn:active{transform:scale(.96);}
#refresh-btn.busy{opacity:.55;pointer-events:none;}
.spin{display:inline-block;animation:spin .65s linear infinite;}
@keyframes spin{to{transform:rotate(360deg);}}

/* ── Banner ── */
#banner{margin:14px 24px 0;padding:11px 16px;border-radius:var(--r);
        font-size:13.5px;display:flex;align-items:center;gap:8px;}
#banner.green{background:#ECFDF5;border:1px solid #6EE7B7;color:#065F46;}
#banner.blue {background:#EFF6FF;border:1px solid #93C5FD;color:#1E40AF;}
#banner.hidden{display:none;}
.banner-close{margin-left:auto;background:none;border:none;cursor:pointer;
              font-size:17px;color:inherit;line-height:1;padding:0 2px;}

/* ── Layout ── */
.layout{display:flex;max-width:1440px;margin:0 auto;
        padding:18px 24px;gap:20px;align-items:flex-start;}

/* ── Sidebar ── */
aside{width:210px;flex-shrink:0;position:sticky;top:62px;}
.sidebar-title{font-size:11px;font-weight:600;text-transform:uppercase;
               letter-spacing:.08em;color:var(--muted);margin-bottom:8px;padding:0 4px;}
.cat-btn{display:flex;align-items:center;gap:8px;width:100%;
         padding:8px 10px;border:none;border-radius:8px;
         background:transparent;font-size:13px;color:var(--text);
         cursor:pointer;text-align:left;transition:background .12s;margin-bottom:2px;}
.cat-btn:hover{background:var(--border);}
.cat-btn.active{background:var(--accent-light);color:var(--accent);font-weight:600;}
.cat-icon{width:20px;text-align:center;font-size:14px;}
.cat-label{flex:1;}
.cat-badge{font-size:11px;font-weight:600;padding:1px 7px;border-radius:20px;
           background:var(--border);color:var(--muted);}
.cat-btn.active .cat-badge{background:var(--accent-light);color:var(--accent);}
.stats-box{margin-top:14px;padding:12px;background:var(--surface);
           border:1px solid var(--border);border-radius:var(--r);
           font-size:12px;color:var(--muted);line-height:1.7;}
.stats-box strong{color:var(--text);}

/* ── Main ── */
main{flex:1;min-width:0;}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:13px;}

/* ── Category sections ── */
.cat-section{margin-bottom:30px;}
.cat-section-hdr{display:flex;align-items:center;gap:10px;
                  margin-bottom:12px;padding-bottom:8px;
                  border-bottom:2px solid var(--border);}
.cat-section-name{font-size:15px;font-weight:700;}
.cat-section-cnt{font-size:13px;color:var(--muted);}
.filtered-hdr{display:flex;align-items:baseline;gap:10px;margin-bottom:14px;}
.filtered-title{font-size:16px;font-weight:700;}
.filtered-cnt{font-size:13px;color:var(--muted);}

/* ── Card ── */
.card{background:var(--surface);border:1px solid var(--border);
      border-radius:var(--r);padding:15px;box-shadow:var(--sh);
      display:flex;flex-direction:column;gap:8px;
      transition:box-shadow .15s,transform .12s;cursor:default;}
.card:hover{box-shadow:var(--sh-md);transform:translateY(-1px);}
.card-top{display:flex;align-items:flex-start;gap:10px;}
.card-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0;margin-top:5px;}
.card-name{font-size:13.5px;font-weight:600;line-height:1.35;word-break:break-word;}
.card-desc{font-size:12.5px;color:var(--muted);line-height:1.5;
           display:-webkit-box;-webkit-line-clamp:3;
           -webkit-box-orient:vertical;overflow:hidden;}
.card-tag{font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;
          background:var(--border);color:var(--muted);}
.card-tag.agent{background:#EDE9FE;color:#7C3AED;}
.card-tag.new-badge{background:#FEF3C7;color:#92400E;}

/* ── Empty / loading ── */
.empty,.loading-msg{grid-column:1/-1;text-align:center;
                    padding:60px 20px;color:var(--muted);}
.empty-icon{font-size:36px;margin-bottom:10px;}

/* ── Responsive ── */
@media(max-width:768px){
  .layout{flex-direction:column;padding:12px;}
  aside{width:100%;position:relative;top:0;}
  .grid{grid-template-columns:1fr;}
}
</style>
</head>
<body>

<header>
  <div class="brand">
    <div class="brand-icon">&#x26A1;</div>
    <h1>Claude Skills &amp; Agents</h1>
  </div>
  <div class="controls">
    <input type="search" id="search" placeholder="Zoek op naam of beschrijving…">
    <button id="refresh-btn" onclick="doRefresh()">
      <span id="ri">↻</span> Refresh
    </button>
  </div>
</header>

<div id="banner" class="hidden"></div>

<div class="layout">
  <aside>
    <div class="sidebar-title">Categorieën</div>
    <div id="cat-list"></div>
    <div class="stats-box" id="stats-box">Laden…</div>
  </aside>
  <main>
    <div class="grid" id="grid">
      <div class="loading-msg"><span class="spin">↻</span>&nbsp; Skills worden geladen…</div>
    </div>
  </main>
</div>

<script>
var D = null, activeCat = 'all', q = '';
var _newSkills = new Set();   // dir_names added since last cache (this session)

function esc(s){
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function showBanner(text, type){
  var b = document.getElementById('banner');
  b.className = type;
  b.innerHTML = '<span>' + (type==='green'?'✨':'ℹ️') + '</span>'
    + '<span>' + esc(text) + '</span>'
    + '<button class="banner-close" onclick="hideBanner()">&times;</button>';
}
function hideBanner(){ document.getElementById('banner').className='hidden'; }

function catColor(id){
  if(!D) return '#78716C';
  var c = D.categories.find(function(c){return c.id===id;});
  return c ? c.color : '#78716C';
}

function renderSidebar(){
  var list = document.getElementById('cat-list');
  var all  = '<button class="cat-btn '+(activeCat==='all'?'active':'')+'" data-cat="all" onclick="setCat(this.dataset.cat)">'
    + '<span class="cat-icon">🌐</span>'
    + '<span class="cat-label">Alles</span>'
    + '<span class="cat-badge">'+D.total+'</span></button>';
  var cats = D.categories.filter(function(c){return c.count>0;}).map(function(c){
    return '<button class="cat-btn '+(activeCat===c.id?'active':'')+'" data-cat="'+c.id+'" onclick="setCat(this.dataset.cat)">'
      +'<span class="cat-icon">'+c.icon+'</span>'
      +'<span class="cat-label">'+esc(c.label)+'</span>'
      +'<span class="cat-badge">'+c.count+'</span></button>';
  }).join('');
  list.innerHTML = all + cats;

  var path = D.claude_dir.replace(/\\\\/g,'/');
  document.getElementById('stats-box').innerHTML =
    '<strong>'+D.total+'</strong> items<br>'
    +'📁 '+esc(path);
}

function filtered(){
  var items = D.items.slice();
  if(activeCat !== 'all') items = items.filter(function(i){return i.category===activeCat;});
  if(q){
    var lq = q.toLowerCase();
    items = items.filter(function(i){
      return i.name.toLowerCase().indexOf(lq)>=0
          || i.dir_name.toLowerCase().indexOf(lq)>=0
          || i.description.toLowerCase().indexOf(lq)>=0;
    });
  }
  return items;
}

function card(item, color){
  var tag = item.type==='agent'
    ? '<span class="card-tag agent">🤖 Agent</span>'
    : '<span class="card-tag">⚡ Skill</span>';
  var newBadge = _newSkills.has(item.dir_name)
    ? '<span class="card-tag new-badge">Nieuw</span>' : '';
  return '<div class="card">'
    +'<div class="card-top">'
    +'<div class="card-dot" style="background:'+color+'"></div>'
    +'<div class="card-name">'+esc(item.name||item.dir_name)+'</div>'
    +'</div>'
    +'<div class="card-desc">'+esc(item.description)+'</div>'
    +'<div style="display:flex;gap:6px">'+tag+newBadge+'</div>'
    +'</div>';
}

function renderGrid(){
  var grid  = document.getElementById('grid');
  var items = filtered();

  if(items.length===0){
    grid.innerHTML='<div class="empty"><div class="empty-icon">🔍</div>'
      +'<div>Geen resultaten voor <strong>'+esc(q||activeCat)+'</strong></div></div>';
    return;
  }

  if(activeCat==='all' && !q){
    // Grouped by category sections
    var html = D.categories.filter(function(c){return c.count>0;}).map(function(cat){
      var catItems = items.filter(function(i){return i.category===cat.id;});
      if(!catItems.length) return '';
      return '<div class="cat-section">'
        +'<div class="cat-section-hdr">'
        +'<span style="font-size:18px">'+cat.icon+'</span>'
        +'<span class="cat-section-name" style="color:'+cat.color+'">'+esc(cat.label)+'</span>'
        +'<span class="cat-section-cnt">'+catItems.length+' items</span>'
        +'</div>'
        +'<div class="grid">'+catItems.map(function(i){return card(i, cat.color);}).join('')+'</div>'
        +'</div>';
    }).join('');
    // Replace outer grid with sections (no grid class at top level here)
    grid.className = '';
    grid.innerHTML = html;
  } else {
    var cat   = D.categories.find(function(c){return c.id===activeCat;});
    var label = activeCat==='all' ? 'Zoekresultaten' : (cat ? cat.label : activeCat);
    var color = cat ? cat.color : '#78716C';
    grid.className = '';
    grid.innerHTML =
      '<div class="filtered-hdr"><span class="filtered-title">'+esc(label)+'</span>'
      +'<span class="filtered-cnt">'+items.length+' items</span></div>'
      +'<div class="grid">'+items.map(function(i){return card(i, color);}).join('')+'</div>';
  }
}

function render(){
  renderSidebar();
  renderGrid();
}

function setCat(id){
  activeCat = id;
  document.getElementById('search').value = '';
  q = '';
  render();
}

document.getElementById('search').addEventListener('input', function(){
  q = this.value.trim();
  if(D) renderGrid();
});

async function load(){
  var resp = await fetch('/api/skills');
  if(!resp.ok) throw new Error('HTTP ' + resp.status);
  return await resp.json();
}

function diffBannerText(data){
  var parts = [];
  if(data.added && data.added.length)   parts.push(data.added.length + ' nieuw');
  if(data.removed && data.removed.length) parts.push(data.removed.length + ' verwijderd');
  return parts.length ? parts.join(', ') + ' — lijst bijgewerkt.' : null;
}

async function doRefresh(){
  var btn = document.getElementById('refresh-btn');
  var ri  = document.getElementById('ri');
  btn.classList.add('busy');
  ri.className = 'spin';
  try {
    var data = await load();
    if(data.added) data.added.forEach(function(n){ _newSkills.add(n); });
    D = data;
    render();
    var msg = diffBannerText(data);
    if(msg) showBanner(msg, 'green');
  } catch(e) {
    alert('Fout bij laden: ' + e.message);
  } finally {
    btn.classList.remove('busy');
    ri.className = '';
  }
}

// Initial load
(async function(){
  try {
    var data = await load();
    if(data.added) data.added.forEach(function(n){ _newSkills.add(n); });
    D = data;
    render();
    if(data.startup_has_changes){
      var n = data.startup_delta_count;
      var msg = 'Startup check: ';
      if(data.added && data.added.length) msg += data.added.length + ' skill(s) nieuw';
      if(data.removed && data.removed.length){
        if(data.added && data.added.length) msg += ', ';
        msg += data.removed.length + ' verwijderd';
      }
      if(msg === 'Startup check: ') msg += (n > 0 ? n+' gewijzigd' : 'wijzigingen gedetecteerd');
      msg += '.';
      showBanner(msg, 'blue');
    }
  } catch(e) {
    document.getElementById('grid').innerHTML =
      '<div class="empty"><div class="empty-icon">&#9888;&#65039;</div>'
      +'<div>Kon skills niet laden.<br><small>'+esc(e.message)+'</small></div></div>';
  }
})();
</script>
</body>
</html>
"""


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    global _startup_info, _last_api_mtime

    if not CLAUDE_DIR.exists():
        print(f"Let op: {CLAUDE_DIR} niet gevonden.")
        print("Zorg dat Claude Code is geinstalleerd.")

    # Startup scan — cache determines what changed since last run
    data = scan_all()
    _last_api_mtime = data["newest_mtime"]

    has_changes = bool(data["added"] or data["removed"])
    delta_count = len(data["added"]) - len(data["removed"])
    _startup_info = {
        "has_changes": has_changes,
        "delta_count": delta_count,
    }

    server = HTTPServer(("127.0.0.1", PORT), SkillsHandler)

    print()
    print("  Claude Skills & Agents Overview")
    print(f"  Gescand: {CLAUDE_DIR}")
    print(f"  Gevonden: {data['total']} items")
    if has_changes:
        print(f"  Startup check: {'+' if delta_count>=0 else ''}{delta_count} items t.o.v. vorige keer")
    print()
    print(f"  Open: http://localhost:{PORT}")
    print("  Ctrl+C om te stoppen.\n")

    Timer(0.7, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGestopt.")
        server.shutdown()


if __name__ == "__main__":
    main()

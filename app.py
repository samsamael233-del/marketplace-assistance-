import os, sqlite3, threading, time
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)
DB = os.getenv("DB_PATH", "marketplace.db")
POLL_SECONDS = max(300, int(os.getenv("POLL_SECONDS", "300")))

HTML = """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Marketplace Assistant</title><style>
body{font-family:system-ui;margin:0;background:#f5f6f8;color:#171717}main{max-width:950px;margin:auto;padding:18px}
.card{background:#fff;border-radius:16px;padding:18px;margin:12px 0;box-shadow:0 2px 12px #0001}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
input,select,button{padding:12px;border-radius:10px;border:1px solid #ddd;font-size:16px}
button{cursor:pointer}.badge{display:inline-block;padding:6px 9px;border-radius:99px;background:#eee;margin:3px}
.match{padding:12px 0;border-bottom:1px solid #eee}.score{font-weight:800}
@media(max-width:650px){.grid{grid-template-columns:1fr}}a{color:inherit}</style></head>
<body><main><h1>Marketplace Assistant</h1>
<p>Mobile deal monitor — rules, scoring, duplicate protection and listing history.</p>
<div class="card"><h2>Add search rule</h2><form id="rule"><div class="grid">
<select id="marketplace"><option>Trade Me</option><option>Facebook</option></select>
<input id="keywords" placeholder="Keywords, e.g. vintage Nike">
<input id="max_price" type="number" step="0.01" placeholder="Max price">
<input id="exclude_words" placeholder="Exclude words">
</div><p><button>Add rule</button></p></form><div id="rules">Loading...</div></div>
<div class="card"><h2>Matches</h2><div id="listings">Loading...</div></div>
<script>
async function load(){
 const r=await (await fetch("/api/rules")).json();
 document.getElementById("rules").innerHTML=r.map(x=>'<span class="badge">'+x.marketplace+' · '+(x.keywords||'any')+(x.max_price!==null?' · ≤ $'+x.max_price:'')+(x.enabled?'':' · OFF')+'</span>').join('')||'No rules yet.';
 const l=await (await fetch("/api/matches")).json();
 document.getElementById("listings").innerHTML=l.map(x=>'<div class="match"><span class="score">🔥 '+x.score+'/100</span> <b>'+esc(x.title)+'</b> · $'+(x.price??'')+' · '+x.marketplace+(x.url?' · <a href="'+x.url+'" target="_blank">Open listing</a>':'')+'<br><small>'+x.matched_at+'</small></div>').join('')||'No matches yet.';
}
function esc(s){return String(s||'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
document.getElementById("rule").onsubmit=async e=>{e.preventDefault();await fetch("/api/rules",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({marketplace:marketplace.value,keywords:keywords.value,max_price:max_price.value||null,exclude_words:exclude_words.value})});e.target.reset();load()};load();setInterval(load,30000);
</script></main></body></html>"""

def db():
    c=sqlite3.connect(DB, check_same_thread=False); c.row_factory=sqlite3.Row; return c

def init():
    c=db()
    c.execute("CREATE TABLE IF NOT EXISTS rules(id INTEGER PRIMARY KEY AUTOINCREMENT,marketplace TEXT NOT NULL,keywords TEXT,max_price REAL,exclude_words TEXT,enabled INTEGER DEFAULT 1)")
    c.execute("CREATE TABLE IF NOT EXISTS listings(id INTEGER PRIMARY KEY AUTOINCREMENT,external_id TEXT UNIQUE,marketplace TEXT,title TEXT,price REAL,url TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    c.execute("CREATE TABLE IF NOT EXISTS matches(id INTEGER PRIMARY KEY AUTOINCREMENT,listing_id INTEGER,rule_id INTEGER,score INTEGER,matched_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(listing_id,rule_id))")
    c.commit(); c.close()

def norm(s): return (s or "").strip().lower()

def matches_rule(listing, rule):
    title=norm(listing["title"])
    keys=[norm(x) for x in (rule["keywords"] or "").split(",") if norm(x)]
    excluded=[norm(x) for x in (rule["exclude_words"] or "").split(",") if norm(x)]
    if norm(rule["marketplace"]) != norm(listing["marketplace"]): return False,0
    if keys and not any(k in title for k in keys): return False,0
    if any(x in title for x in excluded): return False,0
    if rule["max_price"] is not None and listing["price"] is not None and float(listing["price"])>float(rule["max_price"]): return False,0
    score=50+(20 if keys else 0)
    if rule["max_price"] is not None and listing["price"] is not None:
        ratio=float(listing["price"])/max(float(rule["max_price"]),.01)
        score+=max(0,min(30,int((1-ratio)*30)))
    return True,min(100,score)

def process_listing(listing_id):
    c=db(); listing=c.execute("SELECT * FROM listings WHERE id=?",(listing_id,)).fetchone()
    if not listing: c.close(); return
    for rule in c.execute("SELECT * FROM rules WHERE enabled=1"):
        ok,score=matches_rule(listing,rule)
        if ok: c.execute("INSERT OR IGNORE INTO matches(listing_id,rule_id,score) VALUES(?,?,?)",(listing_id,rule["id"],score))
    c.commit(); c.close()

@app.get("/")
def home(): return render_template_string(HTML)
@app.get("/health")
def health(): return jsonify(ok=True,poll_seconds=POLL_SECONDS)

@app.get("/api/rules")
def rules_get():
    c=db(); x=[dict(r) for r in c.execute("SELECT * FROM rules ORDER BY id DESC")]; c.close(); return jsonify(x)

@app.post("/api/rules")
def rules_post():
    d=request.get_json(force=True); c=db()
    q=c.execute("INSERT INTO rules(marketplace,keywords,max_price,exclude_words) VALUES(?,?,?,?)",(d.get("marketplace"),d.get("keywords"),d.get("max_price") or None,d.get("exclude_words")))
    c.commit(); c.close(); return jsonify(id=q.lastrowid),201

@app.get("/api/listings")
def listings_get():
    c=db(); x=[dict(r) for r in c.execute("SELECT * FROM listings ORDER BY id DESC LIMIT 100")]; c.close(); return jsonify(x)

@app.post("/api/listings")
def listings_post():
    d=request.get_json(force=True); c=db()
    try:
        q=c.execute("INSERT INTO listings(external_id,marketplace,title,price,url) VALUES(?,?,?,?,?)",(d.get("external_id"),d.get("marketplace"),d.get("title"),d.get("price"),d.get("url")))
        c.commit(); listing_id=q.lastrowid
    except sqlite3.IntegrityError:
        row=c.execute("SELECT id FROM listings WHERE external_id=?",(d.get("external_id"),)).fetchone(); listing_id=row["id"] if row else None; c.close()
        return jsonify(ok=True,duplicate=True,listing_id=listing_id)
    c.close(); process_listing(listing_id); return jsonify(ok=True,listing_id=listing_id),201

@app.get("/api/matches")
def matches_get():
    c=db(); x=[dict(r) for r in c.execute("""SELECT m.id,m.score,m.matched_at,l.marketplace,l.title,l.price,l.url FROM matches m JOIN listings l ON l.id=m.listing_id ORDER BY m.id DESC LIMIT 100""")]; c.close(); return jsonify(x)

def worker():
    while True: time.sleep(POLL_SECONDS)

init()
if __name__=="__main__":
    threading.Thread(target=worker,daemon=True).start()
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","8080")))

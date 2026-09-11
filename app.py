import os, sqlite3
from flask import Flask, jsonify, request, render_template_string

app=Flask(__name__)
DB=os.getenv("DB_PATH","marketplace.db")

HTML="""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Marketplace Assistant</title><style>
body{font-family:system-ui;margin:0;background:#f5f6f8}main{max-width:900px;margin:auto;padding:20px}
.card{background:white;border-radius:16px;padding:18px;margin:12px 0;box-shadow:0 2px 12px #0001}
input,button{padding:12px;border-radius:10px;border:1px solid #ddd;font-size:16px}
button{cursor:pointer}.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:650px){.grid{grid-template-columns:1fr}}.badge{display:inline-block;padding:6px 9px;border-radius:99px;background:#eee;margin:3px}
</style></head><body><main><h1>Marketplace Assistant</h1>
<p>Trade Me + Facebook Marketplace monitoring dashboard.</p>
<div class="card"><h2>Rules</h2><form id="rule"><div class="grid">
<input id="marketplace" placeholder="Trade Me or Facebook" required>
<input id="keywords" placeholder="Keywords">
<input id="max_price" type="number" step="0.01" placeholder="Max price">
<input id="exclude_words" placeholder="Exclude words"></div><p><button>Add rule</button></p></form>
<div id="rules"></div></div><div class="card"><h2>Recent matches</h2><div id="listings">Loading...</div></div>
<script>
async function load(){let r=await fetch("/api/rules"),a=await r.json();
rules.innerHTML=a.map(x=>'<span class="badge">'+x.marketplace+" · "+(x.keywords||"any")+(x.max_price?" · ≤ $"+x.max_price:"")+"</span>").join("")||"No rules yet.";
let l=await (await fetch("/api/listings")).json();
listings.innerHTML=l.map(x=>'<div><b>'+x.title+'</b> · $'+(x.price??"")+' · '+x.marketplace+'</div>').join("<hr>")||"No matches yet."}
rule.onsubmit=async e=>{e.preventDefault();await fetch("/api/rules",{method:"POST",headers:{"Content-Type":"application/json"},
body:JSON.stringify({marketplace:marketplace.value,keywords:keywords.value,max_price:max_price.value||null,exclude_words:exclude_words.value})});e.target.reset();load()};load();
</script></main></body></html>"""

def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

c=db()
c.execute("CREATE TABLE IF NOT EXISTS rules(id INTEGER PRIMARY KEY AUTOINCREMENT,marketplace TEXT,keywords TEXT,max_price REAL,exclude_words TEXT,enabled INTEGER DEFAULT 1)")
c.execute("CREATE TABLE IF NOT EXISTS listings(id INTEGER PRIMARY KEY AUTOINCREMENT,external_id TEXT UNIQUE,marketplace TEXT,title TEXT,price REAL,url TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
c.commit();c.close()

@app.get("/")
def home(): return render_template_string(HTML)
@app.get("/health")
def health(): return jsonify(ok=True)
@app.get("/api/rules")
def rules_get():
 c=db(); x=[dict(r) for r in c.execute("SELECT * FROM rules ORDER BY id DESC")]; c.close(); return jsonify(x)
@app.post("/api/rules")
def rules_post():
 d=request.get_json(); c=db(); q=c.execute("INSERT INTO rules(marketplace,keywords,max_price,exclude_words) VALUES(?,?,?,?)",(d.get("marketplace"),d.get("keywords"),d.get("max_price"),d.get("exclude_words"))); c.commit(); c.close(); return jsonify(id=q.lastrowid),201
@app.get("/api/listings")
def listings_get():
 c=db(); x=[dict(r) for r in c.execute("SELECT * FROM listings ORDER BY id DESC LIMIT 100")]; c.close(); return jsonify(x)
@app.post("/api/listings")
def listings_post():
 d=request.get_json(); c=db()
 try: c.execute("INSERT INTO listings(external_id,marketplace,title,price,url) VALUES(?,?,?,?,?)",(d.get("external_id"),d.get("marketplace"),d.get("title"),d.get("price"),d.get("url"))); c.commit()
 except sqlite3.IntegrityError: pass
 c.close(); return jsonify(ok=True)

if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.getenv("PORT","8080")))

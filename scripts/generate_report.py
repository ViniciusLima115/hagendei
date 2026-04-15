#!/usr/bin/env python3
"""
Gera SYSTEM_REPORT.html a partir de SYSTEM_REPORT.md com design premium.
Executado automaticamente no pre-commit hook.

Uso:
    python3 scripts/generate_report.py
"""

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
MD_PATH = ROOT / "SYSTEM_REPORT.md"
HTML_PATH = ROOT / "SYSTEM_REPORT.html"


def ensure_markdown():
    try:
        import markdown
        return markdown
    except ImportError:
        print("[generate_report] Instalando python-markdown...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "markdown", "-q"],
            stdout=subprocess.DEVNULL,
        )
        import markdown
        return markdown


def get_git_info():
    try:
        h = subprocess.check_output(["git", "log", "-1", "--pretty=%h"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        msg = subprocess.check_output(["git", "log", "-1", "--pretty=%s"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        total = subprocess.check_output(["git", "rev-list", "--count", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        return h or "—", msg or "—", total or "0", branch or "main"
    except Exception:
        return "—", "—", "0", "main"


def convert_md(content, md_module):
    m = md_module.Markdown(extensions=["tables", "fenced_code"])
    return m.convert(content)


def slugify(text):
    text = re.sub(r"<[^>]+>", "", text).strip().lower()
    text = re.sub(r"[^\w\s/-]", "", text)
    text = re.sub(r"[\s/–—]+", "-", text)
    return text.strip("-")


def add_ids(html):
    def repl_h2(m):
        s = slugify(m.group(1))
        return f'<h2 id="{s}">{m.group(1)}</h2>'

    def repl_h3(m):
        s = slugify(m.group(1))
        return f'<h3 id="{s}">{m.group(1)}</h3>'

    html = re.sub(r"<h2>(.+?)</h2>", repl_h2, html)
    html = re.sub(r"<h3>(.+?)</h3>", repl_h3, html)
    return html


def extract_h2(html):
    return [(m.group(1), re.sub(r"<[^>]+>", "", m.group(2)))
            for m in re.finditer(r'<h2 id="([^"]+)">(.+?)</h2>', html)]


def post_process(html):
    # Remove H1 and intro metadata before first H2
    idx = html.find("<h2 ")
    if idx > 0:
        html = html[idx:]
    # Wrap tables
    html = re.sub(r"<table>", '<div class="tbl-wrap"><table>', html)
    html = html.replace("</table>", "</table></div>")
    # Style code blocks
    html = re.sub(r"<pre><code", '<pre class="cb"><code', html)
    return html


def wrap_sections(html):
    parts = re.split(r"(?=<h2 )", html)
    out = []
    for i, p in enumerate(parts):
        if p.strip():
            out.append(f'<section class="sec" style="animation-delay:{i * 0.05:.2f}s">\n{p}\n</section>')
    return "\n".join(out)


CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

:root{
  --bg:#0B0907;--surf:#111009;--card:#191610;
  --bdr:#2B2419;--bdr2:#3A3025;
  --amb:#C8922A;--amb2:#8B621C;
  --ag:rgba(200,146,42,.10);--ag2:rgba(200,146,42,.20);
  --cr:#F2EAD8;--cr2:#C4B8A4;
  --mt:#7A6E60;--fnt:#3D352A;
  --cbg:#0D0B09;
  --sw:254px;--hh:54px;
  --fd:'Cormorant Garamond',Georgia,serif;
  --fb:'Outfit',system-ui,sans-serif;
  --fm:'JetBrains Mono','Fira Code',monospace;
}

html{scroll-behavior:smooth;scroll-padding-top:calc(var(--hh) + 28px)}

body{
  background:var(--bg);color:var(--cr);
  font-family:var(--fb);font-size:15px;line-height:1.75;
  min-height:100vh;
}

/* grain */
body::after{
  content:'';position:fixed;inset:0;pointer-events:none;z-index:9999;opacity:.022;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='300' height='300' filter='url(%23n)'/%3E%3C/svg%3E");
}

/* ── Header ── */
.hdr{
  position:fixed;top:0;left:0;right:0;height:var(--hh);
  background:rgba(11,9,7,.93);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
  border-bottom:1px solid var(--bdr);
  display:flex;align-items:center;padding:0 28px;gap:14px;z-index:500;
}
.hdr-logo{font-family:var(--fd);font-size:19px;font-weight:600;color:var(--amb);letter-spacing:.02em;white-space:nowrap}
.hdr-sep{width:1px;height:18px;background:var(--bdr2);flex-shrink:0}
.hdr-title{font-size:13px;color:var(--cr2);flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hdr-branch{
  font-family:var(--fm);font-size:11px;color:var(--mt);
  padding:2px 9px;border:1px solid var(--bdr2);border-radius:2px;white-space:nowrap;
}
.hdr-commit{font-family:var(--fm);font-size:11px;color:var(--mt);display:flex;align-items:center;gap:8px;white-space:nowrap}
.hdr-hash{color:var(--amb);background:var(--ag);padding:2px 8px;border-radius:2px;border:1px solid var(--amb2)}

/* ── Layout ── */
.wrap{display:flex;padding-top:var(--hh);min-height:100vh}

/* ── Sidebar ── */
.sb{
  position:fixed;top:var(--hh);left:0;width:var(--sw);
  height:calc(100vh - var(--hh));overflow-y:auto;overflow-x:hidden;
  padding:28px 0 40px;border-right:1px solid var(--bdr);background:var(--surf);
  scrollbar-width:thin;scrollbar-color:var(--bdr2) transparent;
}
.sb::-webkit-scrollbar{width:3px}
.sb::-webkit-scrollbar-thumb{background:var(--bdr2);border-radius:2px}
.sb-lbl{font-family:var(--fm);font-size:9.5px;text-transform:uppercase;letter-spacing:.18em;color:var(--mt);padding:0 22px 14px}
.sb nav ul{list-style:none}
.nl{
  display:block;padding:7px 22px;font-size:13px;color:var(--cr2);
  text-decoration:none;line-height:1.35;border-left:2px solid transparent;
  transition:color .12s,background .12s,border-color .12s;
}
.nl:hover{color:var(--cr);background:var(--ag);border-left-color:var(--amb2)}
.nl.on{color:var(--amb);background:var(--ag);border-left-color:var(--amb);font-weight:500}

/* ── Main ── */
.main{
  margin-left:var(--sw);flex:1;
  padding:52px 72px 96px 60px;
  max-width:calc(var(--sw) + 940px);min-width:0;
}

/* ── Hero ── */
.hero{margin-bottom:60px;padding-bottom:52px;border-bottom:1px solid var(--bdr);position:relative}
.hero::after{content:'';position:absolute;bottom:-1px;left:0;width:72px;height:1px;background:var(--amb)}
.hero-tag{font-family:var(--fm);font-size:10.5px;text-transform:uppercase;letter-spacing:.22em;color:var(--amb);margin-bottom:16px}
.hero h1{font-family:var(--fd);font-size:52px;font-weight:300;line-height:1.08;color:var(--cr);letter-spacing:-.02em;margin-bottom:6px}
.hero h1 em{font-style:italic;color:var(--amb)}
.hero-dom{font-family:var(--fm);font-size:13px;color:var(--mt);margin-bottom:36px}
.hero-dom a{color:var(--amb2);text-decoration:none}
.hero-dom a:hover{color:var(--amb)}
.kpis{display:flex;flex-wrap:wrap}
.kpi{
  padding:16px 26px;border:1px solid var(--bdr);background:var(--card);
  display:flex;flex-direction:column;gap:5px;
  margin-right:-1px;margin-bottom:-1px;
  transition:background .14s,border-color .14s;cursor:default;
}
.kpi:hover{background:var(--ag);border-color:var(--amb2);z-index:1;position:relative}
.kn{font-family:var(--fd);font-size:32px;font-weight:600;color:var(--amb);line-height:1}
.kl{font-family:var(--fm);font-size:10px;text-transform:uppercase;letter-spacing:.12em;color:var(--mt)}

/* ── Sections ── */
.sec{margin-bottom:60px;opacity:0;transform:translateY(14px);animation:rise .45s ease forwards}
@keyframes rise{to{opacity:1;transform:translateY(0)}}

/* ── Headings ── */
h2{
  font-family:var(--fd);font-size:27px;font-weight:600;color:var(--cr);
  margin-bottom:24px;padding-bottom:14px;border-bottom:1px solid var(--bdr);
  position:relative;letter-spacing:-.01em;
}
h2::after{content:'';position:absolute;bottom:-1px;left:0;width:36px;height:1px;background:var(--amb)}
h3{
  font-family:var(--fb);font-size:12px;font-weight:600;
  text-transform:uppercase;letter-spacing:.12em;color:var(--amb);
  margin:34px 0 14px;
}
h4{font-family:var(--fb);font-size:14px;font-weight:600;color:var(--cr);margin:20px 0 10px}
p{color:var(--cr2);margin-bottom:14px}
p:last-child{margin-bottom:0}
strong{color:var(--cr);font-weight:600}
em{font-style:italic}
a{color:var(--amb);text-decoration:none}
a:hover{text-decoration:underline}
hr{border:none;border-top:1px solid var(--bdr);margin:28px 0}

/* ── Tables ── */
.tbl-wrap{overflow-x:auto;margin:22px 0;border:1px solid var(--bdr);border-radius:4px}
table{width:100%;border-collapse:collapse;font-size:13.5px}
thead th{
  padding:11px 14px;text-align:left;
  font-family:var(--fm);font-size:10px;text-transform:uppercase;letter-spacing:.12em;
  color:var(--mt);font-weight:500;background:var(--card);border-bottom:1px solid var(--bdr);
}
tbody tr{border-bottom:1px solid var(--bdr);transition:background .12s}
tbody tr:last-child{border-bottom:none}
tbody tr:hover{background:var(--ag)}
tbody td{padding:10px 14px;color:var(--cr2);vertical-align:top}
tbody td:first-child{font-family:var(--fm);font-size:12.5px;color:var(--amb);white-space:nowrap}
td code,th code{
  font-family:var(--fm);font-size:12px;background:var(--card);color:var(--amb);
  padding:1px 5px;border-radius:2px;border:1px solid var(--bdr2);
}

/* ── Code ── */
pre.cb{
  background:var(--cbg);border:1px solid var(--bdr);border-radius:4px;
  padding:20px 22px;overflow-x:auto;margin:18px 0;position:relative;
}
pre.cb::before{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,var(--amb) 0%,transparent 55%);border-radius:4px 4px 0 0;
}
pre.cb code{
  font-family:var(--fm);font-size:13px;line-height:1.65;
  color:var(--cr2);background:none;padding:0;border:none;
}
code{
  font-family:var(--fm);font-size:12.5px;background:var(--card);color:var(--amb);
  padding:2px 6px;border-radius:2px;border:1px solid var(--bdr2);
}

/* ── Lists ── */
ul,ol{padding-left:0;list-style:none;margin:10px 0 18px}
ul>li{padding:3px 0 3px 22px;position:relative;color:var(--cr2)}
ul>li::before{content:'–';position:absolute;left:2px;color:var(--amb2);font-family:var(--fm)}
ol{counter-reset:li}
ol>li{padding:3px 0 3px 28px;position:relative;color:var(--cr2);counter-increment:li}
ol>li::before{
  content:counter(li,decimal-leading-zero);position:absolute;left:0;top:5px;
  font-family:var(--fm);font-size:10.5px;color:var(--amb);
}
li ul,li ol{margin:4px 0 2px}
li p{margin:0}

/* ── Blockquote ── */
blockquote{border-left:2px solid var(--amb);padding:12px 18px;margin:18px 0;background:var(--ag);border-radius:0 3px 3px 0}
blockquote p{margin:0;font-style:italic;color:var(--cr2)}

/* ── Footer ── */
.ftr{
  margin-left:var(--sw);padding:20px 72px 20px 60px;
  border-top:1px solid var(--bdr);
  display:flex;align-items:center;justify-content:space-between;
  font-family:var(--fm);font-size:11px;color:var(--mt);gap:16px;flex-wrap:wrap;
}

/* ── Scrollbar ── */
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--bdr2);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--mt)}

/* ── Responsive ── */
@media(max-width:860px){
  .sb,.hdr-commit,.hdr-branch{display:none}
  .main,.ftr{margin-left:0}
  .main{padding:32px 20px 60px}
  .hero h1{font-size:36px}
}
""".strip()

JS = """
(function(){
  var links=document.querySelectorAll('.nl');
  var heads=Array.from(document.querySelectorAll('h2[id]'));
  if(!links.length||!heads.length)return;
  function setActive(id){links.forEach(function(l){l.classList.toggle('on',l.getAttribute('href')==='#'+id)})}
  var io=new IntersectionObserver(function(entries){
    entries.forEach(function(e){if(e.isIntersecting)setActive(e.target.id)});
  },{rootMargin:'-74px 0px -55% 0px'});
  heads.forEach(function(h){io.observe(h)});
  links.forEach(function(l){
    l.addEventListener('click',function(){
      setActive(l.getAttribute('href').slice(1));
    });
  });
})();
""".strip()


def build_html(sections_html, headings, commit_hash, commit_msg, total_commits, branch, now):
    nav = "\n".join(
        f'        <li><a href="#{slug}" class="nl">{text}</a></li>'
        for slug, text in headings
    )
    short_msg = commit_msg[:54] + ("…" if len(commit_msg) > 54 else "")
    footer_msg = commit_msg[:66] + ("…" if len(commit_msg) > 66 else "")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Relatório do Sistema — VirtualBarber</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Outfit:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
{CSS}
</style>
</head>
<body>

<header class="hdr">
  <span class="hdr-logo">VirtualBarber</span>
  <div class="hdr-sep"></div>
  <span class="hdr-title">Relatório do Sistema</span>
  <span class="hdr-branch">⎇ {branch}</span>
  <div class="hdr-commit">
    <span class="hdr-hash">{commit_hash}</span>
    <span>{short_msg}</span>
  </div>
</header>

<div class="wrap">

  <aside class="sb">
    <div class="sb-lbl">Seções</div>
    <nav><ul>
{nav}
    </ul></nav>
  </aside>

  <main class="main">

    <div class="hero">
      <div class="hero-tag">Sistema SaaS · Documentação Técnica</div>
      <h1>Virtual<em>Barber</em></h1>
      <p class="hero-dom">
        <a href="https://virtualbarber.shop" target="_blank" rel="noopener">virtualbarber.shop</a>
        &nbsp;·&nbsp;
        <a href="https://app.virtualbarber.shop" target="_blank" rel="noopener">app.virtualbarber.shop</a>
      </p>
      <div class="kpis">
        <div class="kpi"><span class="kn">162</span><span class="kl">Testes</span></div>
        <div class="kpi"><span class="kn">15</span><span class="kl">Rotas</span></div>
        <div class="kpi"><span class="kn">11</span><span class="kl">Modelos</span></div>
        <div class="kpi"><span class="kn">3</span><span class="kl">Planos</span></div>
        <div class="kpi"><span class="kn">{total_commits}</span><span class="kl">Commits</span></div>
      </div>
    </div>

{sections_html}

  </main>
</div>

<footer class="ftr">
  <span>Gerado em {now}</span>
  <span>{commit_hash} — {footer_msg}</span>
</footer>

<script>{JS}</script>
</body>
</html>"""


def main():
    if not MD_PATH.exists():
        print(f"[generate_report] Erro: {MD_PATH} não encontrado.")
        sys.exit(1)

    md_module = ensure_markdown()
    content = MD_PATH.read_text(encoding="utf-8")
    commit_hash, commit_msg, total_commits, branch = get_git_info()
    now = datetime.now().strftime("%d/%m/%Y às %H:%M")

    html_body = convert_md(content, md_module)
    html_body = post_process(html_body)
    html_body = add_ids(html_body)
    headings = extract_h2(html_body)
    sections_html = wrap_sections(html_body)

    html = build_html(sections_html, headings, commit_hash, commit_msg, total_commits, branch, now)
    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"[generate_report] ✓ {HTML_PATH.name} gerado ({len(html):,} bytes)")


if __name__ == "__main__":
    main()

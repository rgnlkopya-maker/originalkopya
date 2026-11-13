from pathlib import Path
from html import escape
from hashlib import sha256
import json
import os

OUT = Path(__file__).parent / 'dist'
OUT.mkdir(exist_ok=True)
(OUT / 'assets').mkdir(exist_ok=True)
SITE = 'https://eylus.com.tr'  # Canonical public domain for metadata, robots and sitemap
DEMO = 'https://eylus-demo.onrender.com/'
SOCIAL = 'https://www.instagram.com/eylustech/'
# All public files are generated here. No production settings, media or databases are copied.
CSS = r'''
:root{--ink:#20202b;--muted:#656571;--purple:#6450d8;--deep:#372773;--pale:#f2effc;--line:#e8e6ed;--white:#fff;--green:#23775e;--orange:#a95c24;--radius:18px}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:100px}body{margin:0;color:var(--ink);background:#fff;font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;-webkit-font-smoothing:antialiased}a{color:inherit;text-decoration:none}button,input,textarea,select{font:inherit}button,a{-webkit-tap-highlight-color:transparent}button{cursor:pointer}a:focus-visible,button:focus-visible,summary:focus-visible{outline:3px solid #917ce8;outline-offset:5px}p{line-height:1.75}h1,h2,h3,p{margin-top:0}h1,h2,h3{font-weight:650}button{color:inherit}::selection{background:#e2d9ff}.wrap{width:min(1180px,calc(100% - 64px));margin-inline:auto}.skip{position:fixed;top:8px;left:12px;transform:translateY(-200%);z-index:100;background:white;padding:15px}.skip:focus{transform:none}.nav{position:sticky;top:0;z-index:30;background:rgba(255,255,255,.95);backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}.nav-inner{height:82px;display:flex;gap:36px;align-items:center;justify-content:space-between}.wordmark{display:inline-flex;align-items:center;flex:none;line-height:1}.wordmark img{display:block;width:148px;height:auto;max-width:100%}.nav-links{display:flex;gap:28px;margin-left:auto;font-size:14px;color:#55545f}.nav-links a{padding:10px 0}.nav-links a:hover,.nav-links a[aria-current=page]{color:var(--purple)}.nav-cta{display:flex;align-items:center;gap:20px;font-size:13px;font-weight:600}.button{display:inline-flex;gap:15px;align-items:center;justify-content:center;min-height:48px;padding:13px 22px;border:1px solid transparent;border-radius:8px;background:var(--ink);color:white;font-weight:600;font-size:14px;transition:background .18s,transform .18s;text-align:center}.button:hover{background:#383643;transform:translateY(-2px)}.button.secondary{background:#fff;color:var(--ink);border-color:#d8d5e1}.button.secondary:hover{background:#f6f4fa}.button.purple{background:var(--purple)}.button.purple:hover{background:#5140b4}.button.light{color:var(--ink);background:#fff}.arrow{font-size:18px;line-height:1}.menu-toggle{display:none;border:1px solid var(--line);background:#fff;border-radius:8px;padding:10px 13px}.eyebrow{font-size:11px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--purple);display:flex;align-items:center;gap:10px}.eyebrow:before{content:'';width:6px;height:6px;background:var(--purple);border-radius:50%}.hero{padding:90px 0 68px;background:radial-gradient(ellipse at 87% 39%,#f1edff 0,transparent 52%)}.hero-grid{display:grid;grid-template-columns:1.03fr 1fr;align-items:center;gap:54px}.hero h1{font-size:clamp(48px,5.1vw,68px);line-height:1.08;letter-spacing:-.055em;margin:22px 0}.hero h1 em{font-style:normal;color:var(--purple)}.hero-copy>p{font-size:17px;color:var(--muted);max-width:460px;margin-bottom:28px}.actions{display:flex;flex-wrap:wrap;gap:12px;align-items:center}.note{color:var(--muted);font-size:11px;line-height:1.7}.hero-note{margin:17px 0 0}.visual-shell{position:relative;padding:24px 0 35px 16px;min-width:0}.app-frame{background:white;border:1px solid #e0dce9;border-radius:15px;box-shadow:0 18px 65px #35256514;overflow:hidden;transform:rotate(-1deg)}.app-chrome{height:43px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 17px;font-size:10px;color:#77727e}.dots{display:flex;gap:4px}.dots i{display:block;width:5px;height:5px;border-radius:50%;background:#d6d2e0}.app-body{display:grid;grid-template-columns:102px 1fr;min-height:318px}.app-nav{padding:21px 10px;border-right:1px solid var(--line);background:#fbfaff;font-size:9px;color:#716c80}.app-nav b{font-size:18px;color:#383044;display:block;margin:0 9px 28px;letter-spacing:-.8px}.app-nav span{display:block;padding:10px 8px;margin:3px 0;border-radius:5px}.app-nav span.selected{background:#eeebfb;color:var(--purple);font-weight:600}.app-main{padding:23px 17px}.app-main h3{font-size:16px;letter-spacing:-.5px;margin-bottom:5px}.app-main .sub{font-size:9px;color:#777}.mini-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin:19px 0}.mini-stats>div{border:1px solid var(--line);padding:12px 9px;border-radius:7px}.mini-stats span{font-size:8px;display:block;color:var(--muted)}.mini-stats b{display:block;font-size:24px;font-weight:600;margin-top:7px;letter-spacing:-1px}.mini-stats .warn{background:#fff7f0;border-color:#f5e4d6}.mini-stats .warn b{color:var(--orange)}.mini-row{display:grid;grid-template-columns:1fr 1fr auto;align-items:center;font-size:9px;gap:7px;padding:13px 0;border-bottom:1px solid #f0edf4}.mini-row:last-child{border-bottom:0}.badge{display:inline-flex;align-items:center;gap:5px;padding:5px 8px;border-radius:5px;background:#f0edfb;color:#65528b;font-size:10px;white-space:nowrap}.badge.green{background:#edf6f1;color:var(--green)}.badge.orange{background:#fff2e7;color:#955523}.floating-card{position:absolute;left:-9px;bottom:9px;background:#fff;border:1px solid #e4dfed;box-shadow:0 12px 30px #30234a12;border-radius:11px;padding:14px 20px;display:flex;align-items:center;gap:13px;font-size:11px}.check-icon{width:31px;height:31px;border-radius:50%;display:grid;place-items:center;background:#edf6f1;color:var(--green);font-weight:700;font-size:16px}.floating-card strong{display:block;font-weight:600;margin-bottom:3px}.floating-card small{color:var(--muted)}.visual-caption{text-align:right;margin:13px 1px 0;font-size:10px;color:#736c80}.scope-strip{display:flex;gap:24px;align-items:center;justify-content:space-between;border-top:1px solid var(--line);padding-top:27px;margin-top:55px}.scope-strip>span{font-size:11px;max-width:210px;color:var(--muted);line-height:1.7}.scope-items{display:flex;gap:32px;flex-wrap:wrap;font-size:13px;color:#4e495a}.scope-items span:before{content:'\2713';color:#9b8bc5;margin-right:9px}.section{padding:94px 0}.section.soft{background:#f8f7fb;border-block:1px solid #efedf5}.section h2,.cta h2{font-size:clamp(32px,3.6vw,46px);line-height:1.16;letter-spacing:-.045em;margin:18px 0}.section-heading{max-width:650px;margin-bottom:42px}.section-heading p{color:var(--muted);font-size:16px;max-width:570px}.questions{display:grid;grid-template-columns:.86fr 1.14fr;gap:64px;align-items:center}.questions h2{margin-top:18px}.question-intro{color:var(--muted);font-size:15px}.tabs{display:grid;gap:8px;margin-top:27px}.question{display:grid;grid-template-columns:32px 1fr 16px;gap:8px;align-items:center;text-align:left;border:1px solid transparent;border-bottom-color:#e3dfea;background:transparent;padding:19px 17px;font-size:14px;border-radius:8px;min-height:64px;font-weight:500}.question span:first-child{font-size:11px;color:#98919f}.question:hover{background:#eeebf6}.question[aria-selected=true]{background:white;border:1px solid #ded8ed;box-shadow:0 4px 15px #35265906;color:var(--purple)}.question[aria-selected=true] span:first-child{color:var(--purple)}.tour-frame{background:#fff;border:1px solid #e2ddeb;border-radius:15px;box-shadow:0 16px 40px #2b22470a;overflow:hidden;min-height:383px}.tour-top{padding:16px 22px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);font-size:11px;color:#746d7e}.tour-top b{font-size:15px;color:#40354e;letter-spacing:-.4px}.tour-panel{padding:25px}.tour-panel h3{font-size:21px;letter-spacing:-.6px;margin-bottom:7px}.tour-panel p{font-size:13px;color:var(--muted);margin-bottom:22px}.tour-panel[hidden]{display:none}.data-row{display:grid;grid-template-columns:1.4fr 1fr auto;gap:8px;padding:15px 0;align-items:center;border-top:1px solid #efecf3;font-size:12px}.data-row strong{font-size:12px;font-weight:600}.data-row small{font-size:10px;display:block;color:var(--muted);margin-top:4px}.tour-foot{background:#fbfaff;padding:12px 25px;font-size:10px;color:#6a6275;border-top:1px solid #eeebf4}.timeline{display:grid;gap:0;margin:20px 0 3px}.timeline>div{display:grid;grid-template-columns:25px 1fr auto;gap:10px;align-items:center;font-size:12px;padding:12px 0}.timeline i{width:22px;height:22px;border-radius:50%;font-style:normal;display:grid;place-items:center;background:#eef6f1;color:var(--green);font-size:11px}.timeline .active i{background:var(--purple);color:#fff}.timeline .pending{color:#91899a}.timeline .pending i{background:#f0edf4;color:#91899a}.timeline small{font-size:10px;color:#847b8e}.link{font-weight:600;font-size:13px;color:var(--purple);display:inline-flex;align-items:center;gap:10px}.link:hover{text-decoration:underline}.feature-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:0;border-top:1px solid var(--line);border-left:1px solid var(--line);border-radius:12px;overflow:hidden}.feature{padding:31px 29px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}.feature-number{font-size:11px;color:#92849f;display:block;margin-bottom:26px;letter-spacing:.08em}.feature h3{font-size:19px;letter-spacing:-.4px;margin-bottom:10px}.feature p{font-size:14px;color:var(--muted);margin-bottom:0}.split{display:grid;grid-template-columns:1fr 1fr;gap:75px;align-items:center}.split p{color:var(--muted);font-size:15px}.tag{display:inline-block;border:1px solid #ddd4ed;border-radius:30px;padding:6px 12px;font-size:11px;margin:4px 4px 4px 0;color:#6b5b81}.textile-panel{background:#ede8f6;border:1px solid #e3daed;border-radius:16px;padding:32px;position:relative}.textile-panel>.eyebrow{font-size:9px;margin-bottom:23px}.order-sheet{background:#fff;border:1px solid #e8e0ee;border-radius:10px;padding:25px;box-shadow:0 12px 25px #5e46800a}.order-title{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding-bottom:17px;margin-bottom:17px}.order-title b{font-size:17px;letter-spacing:-.4px}.order-sheet small{color:var(--muted);font-size:10px}.spec-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:20px 0}.spec-grid strong{display:block;font-size:14px;margin-top:7px;font-weight:600}.step-track{display:flex;align-items:center;gap:5px;padding-top:20px;border-top:1px solid var(--line);font-size:9px;flex-wrap:wrap}.step-track span{padding:7px 8px;background:#f3f0f8;border-radius:4px}.step-track span.current{background:#6b51bc;color:white}.origin{border-left:3px solid #b5a4db;padding:4px 0 4px 25px;font-size:22px!important;line-height:1.6;letter-spacing:-.4px;color:#3e344c!important}.value-list{display:grid;gap:24px}.value-list div{padding-bottom:23px;border-bottom:1px solid var(--line)}.value-list h3{font-size:17px;margin:0 0 8px}.value-list p{margin:0;font-size:14px}.cta{background:#2b213d;color:#fff;border-radius:19px;padding:55px 60px;display:flex;gap:40px;align-items:center;justify-content:space-between;margin-block:70px}.cta .eyebrow{color:#c7b5e8}.cta .eyebrow:before{background:#c7b5e8}.cta h2{font-size:38px;max-width:620px;margin-bottom:12px}.cta p{color:#cdc4d7;font-size:14px;margin:0}.cta .actions{flex-shrink:0}.footer{border-top:1px solid var(--line);padding:46px 0 25px}.footer-top{display:flex;justify-content:space-between;gap:30px;padding-bottom:35px}.footer p{font-size:12px;color:var(--muted);max-width:260px;margin:15px 0 0}.footer-links{display:flex;gap:48px;font-size:12px}.footer-links div{display:grid;gap:12px;align-content:start}.footer-links strong{font-size:11px;color:#827589;font-weight:500;margin-bottom:4px}.footer-links a:hover{color:var(--purple)}.footer-bottom{display:flex;justify-content:space-between;gap:20px;font-size:10px;color:#7a727e;border-top:1px solid var(--line);padding-top:24px}.page-hero{padding:75px 0 55px;background:linear-gradient(140deg,#fff 25%,#f6f2fc)}.page-hero h1{font-size:clamp(38px,4.8vw,62px);line-height:1.12;letter-spacing:-.05em;max-width:820px;margin:21px 0}.page-hero p{font-size:17px;color:var(--muted);max-width:650px;margin-bottom:0}.breadcrumb{font-size:11px;color:#7f748a;margin-bottom:27px}.breadcrumb a:hover{color:var(--purple)}.wide-copy{max-width:800px}.wide-copy h2{font-size:30px}.wide-copy p{font-size:16px;color:var(--muted)}.detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}.detail-box{border:1px solid var(--line);border-radius:12px;padding:32px}.detail-box h2{font-size:24px;margin-top:0}.detail-box p{font-size:14px;color:var(--muted)}.detail-box ul{padding-left:18px;font-size:13px;line-height:2.1;color:#62596e}.callout{background:#f5f1fc;border:1px solid #e7dff3;padding:22px 26px;border-radius:10px;margin-top:30px;font-size:13px;color:#655673;line-height:1.8}.demo-steps{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-bottom:35px}.demo-step{border:1px solid var(--line);padding:25px;border-radius:12px}.demo-step>b{font-size:12px;color:var(--purple);display:block;margin-bottom:20px}.demo-step h2{font-size:19px;letter-spacing:-.3px}.demo-step p{font-size:13px;color:var(--muted);margin:0}.demo-entry{background:#f5f2fb;border:1px solid #e7e0f2;border-radius:15px;padding:35px;display:flex;gap:35px;align-items:center;justify-content:space-between}.demo-entry h2{font-size:25px;margin:0 0 9px}.demo-entry p{font-size:13px;color:var(--muted);margin:0;max-width:580px}.demo-entry .button{flex-shrink:0}.contact-card{border:1px solid var(--line);padding:35px;border-radius:16px;background:#faf8fd}.contact-handle{font-size:29px;letter-spacing:-1px;display:block;margin:23px 0}.message{padding:23px;border-left:3px solid #c3b2e0;background:#faf8fd;font-size:14px;line-height:1.8;margin:25px 0}.faq{max-width:800px;margin-inline:auto}.faq details{border-bottom:1px solid var(--line);padding:22px 0}.faq summary{font-weight:550;cursor:pointer;line-height:1.6;font-size:15px}.faq details p{font-size:14px;color:var(--muted);margin:16px 0 0}.privacy{font-size:13px;color:var(--muted);line-height:1.8;max-width:720px}.no-margin{margin:0}.offscreen{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media(min-width:1200px){.hero{padding-top:98px}.hero-grid{gap:65px}}
@media(max-width:1050px){.wrap{width:calc(100% - 48px)}.nav-links{gap:17px}.nav-inner{gap:22px}.nav-cta>.plain{display:none}.hero-grid{gap:27px}.hero h1{font-size:54px}.app-body{grid-template-columns:80px 1fr}.app-main{padding:21px 13px}.scope-items{gap:20px}.questions{gap:35px}.split{gap:40px}.cta{padding:43px;display:block}.cta .actions{margin-top:25px}}
@media(max-width:780px){.wrap{width:calc(100% - 36px)}.nav-inner{height:70px;gap:16px}.wordmark img{width:132px}.nav-cta{margin-left:auto}.nav-cta .button{min-height:40px;padding:10px 13px;font-size:12px}.menu-toggle{display:block}.nav-links{display:none;position:absolute;top:70px;left:0;right:0;background:#fff;padding:20px 24px;border-bottom:1px solid var(--line);box-shadow:0 12px 20px #20102e0a}.nav-links.open{display:flex;flex-direction:column;gap:5px}.nav-links a{font-size:15px}.hero{padding:58px 0 40px}.hero-grid,.questions,.split{grid-template-columns:1fr;gap:37px}.hero h1{font-size:clamp(43px,9.2vw,64px);max-width:620px}.hero-copy>p{font-size:16px;max-width:550px}.visual-shell{padding:6px 5px 34px 18px;max-width:560px;width:100%;margin:auto}.floating-card{left:0;bottom:7px}.app-body{grid-template-columns:100px 1fr}.app-main{padding:23px 20px}.scope-strip{display:block;margin-top:32px;padding-top:23px}.scope-strip>span{display:block;max-width:none;margin-bottom:17px}.scope-items{gap:14px 23px;font-size:12px}.section{padding:65px 0}.section h2{font-size:35px}.feature-grid{grid-template-columns:1fr 1fr}.feature{padding:26px 22px}.feature h3{font-size:17px}.questions{gap:28px}.question{padding:17px 14px}.tour-frame{min-height:360px}.split .textile-panel{order:2}.textile-panel{padding:26px}.cta{padding:35px 28px;margin-block:45px}.cta h2{font-size:33px}.footer-top{display:block}.footer-links{margin-top:30px;gap:50px}.footer-bottom{flex-direction:column;gap:10px}.page-hero{padding:48px 0 42px}.page-hero h1{font-size:42px}.detail-grid,.demo-steps{grid-template-columns:1fr}.demo-entry{display:block;padding:27px}.demo-entry .button{margin-top:25px}.section .detail-box h2{font-size:24px}.section .demo-step h2{font-size:21px}.contact-card{padding:28px}}
@media(max-width:400px){.nav-cta .button{font-size:11px;padding:10px}.nav-inner{gap:10px}.wordmark img{width:115px}.hero h1{font-size:43px}.actions{gap:9px}.actions .button{font-size:12px;padding:12px 16px}.app-body{grid-template-columns:74px 1fr}.app-nav{padding:20px 6px;font-size:8px}.app-main{padding:20px 12px}.mini-stats{gap:5px}.mini-stats>div{padding:10px 7px}.mini-stats span{font-size:7px}.mini-stats b{font-size:22px}.mini-row{font-size:8px}.mini-row .badge{font-size:8px;padding:4px 5px}.feature-grid{grid-template-columns:1fr}.tour-panel{padding:20px}.data-row{font-size:11px}.tour-top{padding:16px}.tour-top>span{font-size:9px}.textile-panel{padding:18px}.order-sheet{padding:19px}.tag{font-size:10px}.footer-links{gap:34px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*,*:before,*:after{animation:none!important;transition:none!important}}
'''
JS = r'''
'use strict';
const menu = document.querySelector('.menu-toggle');
const nav = document.querySelector('#primary-nav');
function closeMenu(){if(!menu||!nav)return;nav.classList.remove('open');menu.setAttribute('aria-expanded','false');}
if(menu&&nav){menu.addEventListener('click',()=>{const open=menu.getAttribute('aria-expanded')!=='true';menu.setAttribute('aria-expanded',String(open));nav.classList.toggle('open',open);});nav.addEventListener('click',e=>{if(e.target.closest('a'))closeMenu();});document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeMenu();menu.focus();}});}
const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
function choose(tab,focus=false){tabs.forEach(t=>{const selected=t===tab;t.setAttribute('aria-selected',String(selected));t.tabIndex=selected?0:-1;const panel=document.getElementById(t.getAttribute('aria-controls'));if(panel)panel.hidden=!selected;});if(focus)tab.focus();}
tabs.forEach((tab,i)=>{tab.addEventListener('click',()=>choose(tab));tab.addEventListener('keydown',e=>{let n=i;if(e.key==='ArrowDown'||e.key==='ArrowRight')n=(i+1)%tabs.length;else if(e.key==='ArrowUp'||e.key==='ArrowLeft')n=(i+tabs.length-1)%tabs.length;else if(e.key==='Home')n=0;else if(e.key==='End')n=tabs.length-1;else return;e.preventDefault();choose(tabs[n],true);});});
'''
NAV = [('/urun/','Ürün'),('/tekstil/','Çözümler'),('/neden-eylus/','Neden Eylus?')]
def button(text,href,kind='',external=False):
    extra=' target="_blank" rel="noopener noreferrer"' if external else ''
    return f'<a class="button {kind}" href="{href}"{extra}>{text}<span class="arrow" aria-hidden="true">{chr(8599) if external else chr(8594)}</span></a>'
def actions():
    return '<div class="actions">'+button('Canlı demoyu incele','/demo/','purple')+button('Bizimle görüşün','/iletisim/','secondary')+'</div>'
def eyebrow(s): return '<div class="eyebrow">'+s+'</div>'
def header(path):
    links = (
        '<a href="/tekstil/">Çözümler</a>'
        '<a href="/neden-eylus/">Hakkımızda</a>'
    )
    chat_icon = '<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11.5a7.9 7.9 0 0 1-8 8 9 9 0 0 1-3.7-.8L4 20l1.4-4.1A8 8 0 1 1 20 11.5Z"/><path d="M8.7 10.2c1 2.1 2.3 3.4 4.4 4.4"/></svg>'
    return f'''<a class="skip" href="#main">İçeriğe geç</a><header class="nav eylus-header"><div class="wrap nav-inner"><a class="wordmark" href="/" aria-label="Eylus ana sayfa"><img src="/assets/eylus-wordmark.png" width="1488" height="252" alt="EYLUS" decoding="async"></a><nav id="primary-nav" class="nav-links" aria-label="Ana menü">{links}</nav><div class="nav-cta"><details class="eylus-nav-contact"><summary class="nav-write">{chat_icon}<span>Bize Yazın</span></summary><div class="eylus-contact-options eylus-contact-nav-options"><a href="https://www.instagram.com/eylustech/" target="_blank" rel="noopener noreferrer">Instagram <small>@eylustech</small></a><a href="https://wa.me/905368163125" target="_blank" rel="noopener noreferrer">WhatsApp <small>Mesaj gönder</small></a></div></details></div><button class="menu-toggle" aria-label="Menüyü aç veya kapat" aria-controls="primary-nav" aria-expanded="false" type="button">☰</button></div></header>'''
def footer():
    return f'''<footer class="footer eylus-footer"><div class="wrap">
      <div class="footer-top"><div class="eylus-footer-brand">
        <a class="wordmark" href="/" aria-label="Eylus ana sayfa"><img src="/assets/eylus-wordmark.png" width="1488" height="252" alt="EYLUS" loading="lazy" decoding="async"></a>
        <p>Üretimin her aşaması kontrolünüzde.</p>
        <div class="eylus-footer-intro">
          <p>İşletmenizde ne olup bittiğini öğrenmek için sürekli telefon açmayın. Eylus; sipariş, üretim, personel, sevkiyat ve maliyet bilgilerini tek yerde toplar.</p>
          <p>Personeliniz QR okutarak işlemleri kolayca kaydeder; siz de gecikmeleri erken fark eder, işletmenizi nerede olursanız olun telefonunuzdan takip edersiniz.</p>
        </div>
      </div></div>
      <div class="footer-bottom">
        <span class="eylus-footer-copyright">© 2026 Eylus</span>
        <nav class="eylus-footer-legal" aria-label="Alt sayfa bağlantıları">
          <a class="eylus-footer-guide" href="/uretim-takip-programi/">Rehber</a>
          <a class="eylus-footer-stock" href="/stok-takip-programi/">Stok</a>
          <a class="eylus-footer-orders" href="/siparis-takip-programi/">Sipariş</a>
          <a class="eylus-footer-personnel" href="/personel-takip-programi/">Personel</a>
          <a class="eylus-footer-work" href="/is-takip-programi/">İş</a>
          <a class="eylus-footer-invoice" href="/fatura-programi/">Fatura</a>
          <a class="eylus-footer-privacy" href="/iletisim/#gizlilik">Site ve gizlilik bilgisi</a>
        </nav>
      </div>
    </div></footer>'''
def cta():
    return '<section class="wrap cta"><div>'+eyebrow('Eylus ile tanışın')+'<h2>Üretiminize birlikte<br>daha yakından bakalım.</h2><p>Önce ürünü keşfedin. Sonra işletmenize uyumunu konuşalım.</p></div><div class="actions">'+button('Demoyu incele','/demo/','light')+'</div></section>'
def intro(label,title,description):
    return f'<section class="page-hero"><div class="wrap"><div class="breadcrumb"><a href="/">Ana sayfa</a> / {label}</div>{eyebrow(label)}<h1>{title}</h1><p>{description}</p></div></section>'
FEATURES = [
 ('Sipariş yönetimi','Ürün, renk, beden, adet ve teslim tarihini aynı siparişte buluşturun.'),
 ('Üretim aşamaları','İşlerin kesimden sevkiyata hangi noktada olduğunu takip edin.'),
 ('QR ile hareket kaydı','Ürüne ait kayda ulaşın; üretim hareketlerini siparişle ilişkilendirin.'),
 ('Teslimat ve sevkiyat','Yaklaşan teslimatları ve hazır ürünleri birlikte değerlendirin.'),
 ('Maliyet görünümü','Ürün ve sipariş maliyetlerini takip ederek kararlarınızı veriye dayandırın.'),
 ('Raporlar ve genel bakış','Operasyonun ayrıntılarını kaybetmeden bütünü görün.')]
def features():
    return '<div class="feature-grid">'+''.join(f'<article class="feature"><span class="feature-number">0{i+1} /</span><h3>{title}</h3><p>{desc}</p></article>' for i,(title,desc) in enumerate(FEATURES))+'</div>'
HERO_VISUAL = '''<div class="visual-shell"><div class="app-frame"><div class="app-chrome"><span class="dots"><i></i><i></i><i></i></span><span>Örnek üretim görünümü</span><span>•••</span></div><div class="app-body"><div class="app-nav"><b>eylus.</b><span class="selected">Genel bakış</span><span>Siparişler</span><span>Üretim</span><span>Sevkiyat</span><span>Raporlar</span></div><div class="app-main"><h3>Üretime genel bakış</h3><span class="sub">İşlerinizin tamamı, aynı yerde.</span><div class="mini-stats"><div><span>Üretimde</span><b>24</b></div><div class="warn"><span>Geciken</span><b>3</b></div><div><span>Sevke hazır</span><b>8</b></div></div><div class="mini-row"><strong>ÖRNEK-001</strong><span>Model 8020</span><span class="badge">Dikim</span></div><div class="mini-row"><strong>ÖRNEK-002</strong><span>Model 7119</span><span class="badge">Süsleme</span></div><div class="mini-row"><strong>ÖRNEK-003</strong><span>Model 8050</span><span class="badge green">Hazır</span></div></div></div></div><div class="floating-card"><span class="check-icon">✓</span><div><strong>Siparişten sevkiyata</strong><small>Her aşama aynı akışta.</small></div></div><p class="visual-caption">Temsili görünüm · Örnek veriler · Canlı ekran değildir</p></div>'''
TOUR = '''<section class="section soft" id="kesfet"><div class="wrap questions"><div>'''+eyebrow('Üç soru. Daha net bir üretim.')+'''<h2>Aradığınız cevap,<br>aynı yerde.</h2><p class="question-intro">İşletmenizde her gün sorulan soruları seçin.<br>Eylus'un takip yaklaşımını bir örnekle keşfedin.</p><div class="tabs" role="tablist" aria-label="Üretim soruları" aria-orientation="vertical"><button class="question" type="button" id="tab-late" role="tab" aria-selected="true" aria-controls="panel-late"><span>01</span><span>Hangi siparişler gecikti?</span><span aria-hidden="true">↗</span></button><button class="question" type="button" id="tab-stage" role="tab" aria-selected="false" tabindex="-1" aria-controls="panel-stage"><span>02</span><span>Siparişim hangi aşamada?</span><span aria-hidden="true">↗</span></button><button class="question" type="button" id="tab-ship" role="tab" aria-selected="false" tabindex="-1" aria-controls="panel-ship"><span>03</span><span>Bu hafta ne sevk edeceğiz?</span><span aria-hidden="true">↗</span></button></div></div><div class="tour-frame"><div class="tour-top"><b>eylus.</b><span>ETKİLEŞİMLİ ÖRNEK SENARYO</span></div><div class="tour-panel" id="panel-late" role="tabpanel" aria-labelledby="tab-late" tabindex="0"><h3>Öncelik bekleyen siparişler</h3><p>Teslim tarihi geçen işleri mevcut aşamasıyla birlikte değerlendirin.</p><div class="data-row"><div><strong>ÖRNEK-001</strong><small>Model 8020 · Lacivert</small></div><span>Dikim</span><span class="badge orange">2 gün gecikti</span></div><div class="data-row"><div><strong>ÖRNEK-002</strong><small>Model 7119 · Ekru</small></div><span>Süsleme</span><span class="badge orange">1 gün gecikti</span></div><div class="data-row"><div><strong>ÖRNEK-004</strong><small>Model 8077 · Siyah</small></div><span>Kesim</span><span class="badge orange">1 gün gecikti</span></div></div><div class="tour-panel" id="panel-stage" role="tabpanel" aria-labelledby="tab-stage" tabindex="0" hidden><h3>Bir siparişin yolculuğu</h3><p>ÖRNEK-002 · Model 7119 · Ekru · 38 beden</p><div class="timeline"><div><i>✓</i><strong>Kesim tamamlandı</strong><small>1. aşama</small></div><div><i>✓</i><strong>Dikim tamamlandı</strong><small>2. aşama</small></div><div class="active"><i>3</i><strong>Süsleme devam ediyor</strong><small>Mevcut aşama</small></div><div class="pending"><i>4</i><span>Hazır / Sevkiyat</span><small>Sıradaki</small></div></div></div><div class="tour-panel" id="panel-ship" role="tabpanel" aria-labelledby="tab-ship" tabindex="0" hidden><h3>Haftanın sevkiyat planı</h3><p>Teslimat takviminizi üretimin hazırlık durumuyla birlikte görün.</p><div class="data-row"><div><strong>Pazartesi</strong><small>Örnek teslimat grubu A</small></div><span>3 adet</span><span class="badge green">Hazır</span></div><div class="data-row"><div><strong>Çarşamba</strong><small>Örnek teslimat grubu B</small></div><span>5 adet</span><span class="badge green">Hazır</span></div><div class="data-row"><div><strong>Cuma</strong><small>Örnek teslimat grubu C</small></div><span>4 adet</span><span class="badge">Üretimde</span></div></div><div class="tour-foot">Anlatım amaçlı temsili arayüz ve veriler; gerçek müşteri bilgisi içermez.</div></div></div></section>'''
TEXTILE_VISUAL = '''<div class="textile-panel">'''+eyebrow('Tekstilden bir örnek')+'''<div class="order-sheet"><div class="order-title"><b>Model 7119</b><span class="badge">Örnek sipariş</span></div><small>HER DETAYIYLA AYNI KAYITTA</small><div class="spec-grid"><div><small>Renk</small><strong>Ekru</strong></div><div><small>Beden</small><strong>38</strong></div><div><small>Adet</small><strong>1</strong></div></div><div class="step-track"><span>Kesim</span>→<span>Dikim</span>→<span class="current">Süsleme</span>→<span>Hazır</span></div></div><p class="note" style="margin:15px 0 0">Temsili sipariş akışı. Canlı veri değildir.</p></div>'''

# Home-only customer-problem discovery. Other pages retain their existing tours.
CSS += r'''
.problem-section{padding:92px 0 100px;background:#f8f7fb;border-top:1px solid #eeebf4;border-bottom:1px solid #eeebf4}
.problem-heading{max-width:780px;margin-bottom:32px}.problem-heading h2{max-width:730px}
.problem-heading p{font-size:16px;color:var(--muted);max-width:680px}
.problem-layout{display:grid;grid-template-columns:minmax(0,.92fr) minmax(0,1.08fr);gap:22px;align-items:stretch}
.problem-options{display:grid;gap:12px}
.problem-choice{width:100%;min-height:128px;text-align:left;background:#fff;border:1px solid #e7e1ef;border-radius:14px;padding:24px;display:grid;grid-template-columns:44px minmax(0,1fr) 24px;gap:13px;align-items:center;transition:border-color .2s,box-shadow .2s,transform .2s}
.problem-choice:hover{border-color:#b4a6df;transform:translateY(-2px)}
.problem-choice[aria-expanded=true]{border:2px solid #7762cf;box-shadow:0 14px 36px #54409512;background:#fff}
.problem-num{height:42px;width:42px;border-radius:12px;display:grid;place-items:center;background:#f2effc;color:#6650bf;font-weight:700;font-size:12px}
.problem-choice strong{display:block;font-size:18px;letter-spacing:-.02em;margin-bottom:7px}
.problem-choice small{display:block;color:#726c7b;font-size:12px;line-height:1.55;font-weight:400}
.problem-chevron{font-size:23px;color:#9484bf}
.problem-result{background:white;border:1px solid #e4deed;border-radius:16px;padding:36px;min-height:407px;box-shadow:0 16px 42px #29203a0b;display:flex;flex-direction:column;justify-content:center}
.problem-result[hidden]{display:none}
.problem-result .eyebrow{margin-bottom:16px}
.problem-result h3{font-size:clamp(24px,2.5vw,32px);letter-spacing:-.035em;line-height:1.2;margin:0 0 17px}
.problem-result p{font-size:15px;color:#625e6d;line-height:1.8;max-width:470px}
.problem-demo{border:1px solid #ede8f4;background:#faf9fd;border-radius:12px;padding:21px;margin:13px 0 24px}
.problem-demo-label{display:block;font-size:10px;font-weight:700;letter-spacing:.12em;color:#7868a1;margin-bottom:13px}
.problem-demo-row{display:flex;align-items:center;justify-content:space-between;gap:12px;border-top:1px solid #e8e4ef;padding:12px 0;font-size:12px}
.problem-demo-row:first-of-type{border:0;padding-top:0}
.problem-demo-row strong{font-weight:650}
.problem-mini-status{font-size:11px;border-radius:6px;padding:6px 10px;background:#eeeafb;color:#5945ae;white-space:nowrap}
.problem-mini-status.warn{background:#fff1e5;color:#9c5425}
.problem-mini-status.ok{background:#eaf6ef;color:#287454}
.problem-result .actions{margin-top:auto}
.problem-foot{margin-top:19px;color:#777080;font-size:11px;line-height:1.7}
@media(max-width:800px){.problem-section{padding:68px 0}.problem-layout{grid-template-columns:1fr}.problem-choice{min-height:106px;padding:17px}.problem-result{padding:26px;min-height:0}.problem-heading h2{font-size:35px}}
@media(max-width:430px){.problem-choice{grid-template-columns:37px minmax(0,1fr) 18px;gap:9px}.problem-num{width:36px;height:36px}.problem-choice strong{font-size:16px}.problem-result{padding:21px}.problem-demo{padding:15px}}
'''
JS += r'''
const problemButtons = [...document.querySelectorAll('[data-problem-select]')];
const problemPanels = [...document.querySelectorAll('[data-problem-panel]')];
function selectProblem(id){
  problemButtons.forEach(btn=>btn.setAttribute('aria-expanded',String(btn.dataset.problemSelect===id)));
  problemPanels.forEach(panel=>{panel.hidden=panel.dataset.problemPanel!==id;});
}
problemButtons.forEach(btn=>btn.addEventListener('click',()=>selectProblem(btn.dataset.problemSelect)));
'''
HOME_PROBLEMS = '''<section class="problem-section" id="sorununu-sec"><div class="wrap">
<div class="problem-heading">'''+eyebrow('Sorununu seç · Çözümünü gör · Demoyu incele')+'''<h2>İşletmenizde bugün sizi en çok ne zorluyor?</h2><p>Üç sorudan birini seçin. Eylus'un üretimde size nasıl yardımcı olabileceğini kısa bir örnekle görün.</p></div>
<div class="problem-layout"><div class="problem-options" aria-label="İşletmenizin sorunları">
<button type="button" class="problem-choice" data-problem-select="gorunurluk" aria-expanded="true" aria-controls="problem-gorunurluk"><span class="problem-num">01</span><span><strong>Üretimde neler oluyor?</strong><small>Siparişimin nerede olduğunu öğrenmek için sürekli sormak zorunda mıyım?</small></span><span class="problem-chevron" aria-hidden="true">→</span></button>
<button type="button" class="problem-choice" data-problem-select="gecikme" aria-expanded="false" aria-controls="problem-gecikme"><span class="problem-num">02</span><span><strong>Hangi işler gecikiyor?</strong><small>Gecikmeleri teslim günü gelmeden fark edebilir miyim?</small></span><span class="problem-chevron" aria-hidden="true">→</span></button>
<button type="button" class="problem-choice" data-problem-select="kontrol" aria-expanded="false" aria-controls="problem-kontrol"><span class="problem-num">03</span><span><strong>İşletmemi ne kadar kontrol ediyorum?</strong><small>Personelin yaptığı işleri ve maliyetleri tek yerde görebilir miyim?</small></span><span class="problem-chevron" aria-hidden="true">→</span></button>
</div><div class="problem-results" aria-live="polite">
<div class="problem-result" id="problem-gorunurluk" data-problem-panel="gorunurluk">'''+eyebrow('Eylus ile çözümü')+'''<h3>Her siparişin nerede olduğunu tek bakışta görün.</h3><p>Kesim, dikim, süsleme, hazır ve sevkiyat aşamalarını aynı sipariş kaydında takip edin. İşlemler kaydedildikçe güncel durum görünür olur.</p><div class="problem-demo"><span class="problem-demo-label">ÖRNEK ÜRETİM TAKİBİ</span><div class="problem-demo-row"><strong>Örnek sipariş · 7119</strong><span class="problem-mini-status">Süslemede</span></div><div class="problem-demo-row"><span>Kesim → Dikim → Süsleme</span><span class="problem-mini-status ok">İlerliyor</span></div></div><div class="actions">'''+button('Demoyu incele','/demo/','purple')+'''</div></div>
<div class="problem-result" id="problem-gecikme" data-problem-panel="gecikme" hidden>'''+eyebrow('Eylus ile çözümü')+'''<h3>Gecikme riskini son güne bırakmayın.</h3><p>Teslim tarihi yaklaşan siparişleri ve üretimde hareketsiz kalan işleri takip edin. Bildirim ve aşama kontrolüyle müdahale etmeniz gereken işleri görün.</p><div class="problem-demo"><span class="problem-demo-label">ÖRNEK TESLİMAT KONTROLÜ</span><div class="problem-demo-row"><strong>Örnek sipariş · 8020</strong><span class="problem-mini-status warn">Teslimat yaklaşıyor</span></div><div class="problem-demo-row"><span>Üretim aşaması</span><span class="problem-mini-status">Dikim</span></div></div><div class="actions">'''+button('Demoyu incele','/demo/','purple')+'''</div></div>
<div class="problem-result" id="problem-kontrol" data-problem-panel="kontrol" hidden>'''+eyebrow('Eylus ile çözümü')+'''<h3>Üretim hareketlerini ve maliyetleri birlikte değerlendirin.</h3><p>İşlem geçmişinde personel hareketlerini inceleyin; ürün ve sipariş maliyetlerini merkezi olarak takip edin. Dağınık bilgiler yerine kayıtlı verilere dayanın.</p><div class="problem-demo"><span class="problem-demo-label">ÖRNEK YÖNETİM GÖRÜNÜMÜ</span><div class="problem-demo-row"><strong>İşlem geçmişi</strong><span class="problem-mini-status ok">Kayıtlı</span></div><div class="problem-demo-row"><span>Sipariş maliyet bilgisi</span><span class="problem-mini-status">Görüntülenebilir</span></div></div><div class="actions">'''+button('Demoyu incele','/demo/','purple')+'''</div></div>
</div></div><p class="problem-foot">Gösterilen siparişler ve paneller temsili örnektir; gerçek müşteri verisi kullanılmaz. Demo uygulaması ayrı ortamda açılır.</p></div></section>'''

CSS += r'''
/* Approved Nov 2026 EYLUS homepage concept: actual clickable UI, no baked-in text. */
.eylus-header{background:rgba(255,255,255,.97);border-bottom:1px solid #ece8f0;box-shadow:0 2px 15px rgba(26,19,48,.03)}
.eylus-header .nav-inner{width:min(1490px,calc(100% - 90px));height:86px;gap:30px}
.eylus-header .wordmark img{width:205px}
.eylus-header .nav-links{gap:34px;align-items:center;margin-left:auto}
.eylus-header .nav-links>a,.eylus-header .nav-drop>summary{display:flex;align-items:center;gap:6px;min-height:40px;font-size:15px;font-weight:650;color:#1a1930;white-space:nowrap;padding:5px 0}
.eylus-header .nav-links>a:hover,.eylus-header .nav-drop>summary:hover{color:#6127c8}
.eylus-header .nav-drop{position:relative}
.eylus-header .nav-drop>summary{cursor:pointer;list-style:none;user-select:none}
.eylus-header .nav-drop>summary::-webkit-details-marker{display:none}
.eylus-header .nav-caret{font-size:17px;line-height:1;margin-left:3px}
.eylus-header .nav-drop[open] .nav-caret{transform:rotate(180deg)}
.eylus-header .nav-drop-panel{position:absolute;top:100%;left:-15px;min-width:255px;padding:9px;background:white;border:1px solid #e3dcef;border-radius:13px;box-shadow:0 18px 38px #2d18401a;z-index:45}
.eylus-header .nav-drop-panel a{display:block;font-size:13px;font-weight:600;line-height:1.45;border-radius:8px;padding:12px 13px;color:#2e2840;white-space:normal}
.eylus-header .nav-drop-panel a:hover{background:#f3effc;color:#5c28bc}
.eylus-header .nav-cta{gap:12px;margin-left:8px}
.eylus-header .nav-login,.eylus-header .nav-write{display:inline-flex;align-items:center;justify-content:center;min-height:45px;border-radius:11px;font-size:14px;font-weight:750;white-space:nowrap;padding:10px 18px;transition:transform .15s,box-shadow .15s,background .15s}
.eylus-header .nav-login{border:1.5px solid #171525;background:#fff;color:#151425}
.eylus-header .nav-login:hover{background:#f6f3fb}
.eylus-header .nav-write{gap:10px;background:#6423c8;color:#fff;box-shadow:0 6px 16px #6423c825}
.eylus-header .nav-write:hover{background:#4e18a6;color:#fff;box-shadow:0 8px 20px #6423c82e}
.eylus-header .nav-write svg{width:21px;height:21px;flex:none}
.eylus-header .nav-login:hover,.eylus-header .nav-write:hover{transform:translateY(-1px)}
.eylus-header .mobile-signin{display:none!important}
.eylus-home-hero{position:relative;display:flex;align-items:center;min-height:760px;background:#fff;overflow:hidden;border-bottom:1px solid #ece9f4}
.eylus-hero-photo{position:absolute;right:0;top:0;bottom:0;width:58%;overflow:hidden}
.eylus-hero-photo img{display:block;width:100%;height:100%;object-fit:cover;object-position:center 35%}
.eylus-hero-photo:before{content:'';position:absolute;inset:0;z-index:1;background:linear-gradient(90deg,#fff 0%,rgba(255,255,255,.97) 5%,rgba(255,255,255,.62) 25%,rgba(255,255,255,0) 54%);pointer-events:none}
.eylus-hero-container{position:relative;z-index:2;width:min(1490px,calc(100% - 90px))}
.eylus-hero-content{max-width:710px;width:57%;padding:62px 0 68px}
.eylus-hero-prompts{display:grid;gap:14px;margin-bottom:58px}
.eylus-hero-prompt{display:flex;align-items:center;gap:18px;color:#141529;font-size:15px;font-weight:650;line-height:1.5;white-space:nowrap;letter-spacing:-.02em}
.eylus-hero-prompt b{font-size:19px;margin:0 3px;color:#6b29d6}
.eylus-prompt-icon{display:grid;place-items:center;flex:0 0 51px;width:51px;height:51px;border-radius:13px;background:#eee5fa;color:#6a2fca}
.eylus-prompt-icon svg{width:26px;height:26px}
.eylus-home-hero h1{font-size:clamp(62px,5.8vw,88px);line-height:.99;letter-spacing:-.065em;font-weight:800;margin:0 0 29px;color:#0c0c28}
.eylus-home-hero h1 em{font-style:normal;color:#6121c6;position:relative;display:inline-block}
.eylus-home-hero h1 em:after{content:'';position:absolute;bottom:-13px;left:30%;width:57%;height:7px;border-top:4px solid #a97bf1;border-radius:60% 55% 0 0;transform:rotate(-3deg)}
.eylus-hero-description{font-size:20px;line-height:1.45;color:#37344a;letter-spacing:-.02em;max-width:615px;margin:0 0 44px}
.eylus-hero-actions{display:flex;align-items:stretch;gap:13px;flex-wrap:nowrap}
.eylus-hero-button{display:flex;align-items:center;justify-content:flex-start;gap:14px;border-radius:13px;min-height:84px;padding:15px 20px;text-align:left;box-shadow:0 6px 18px #41256f0c;transition:transform .18s,box-shadow .18s;flex:1 1 0;min-width:0}
.eylus-hero-button:hover{transform:translateY(-3px);box-shadow:0 13px 26px #41256f20}
.eylus-hero-button-icon{display:grid;place-items:center;flex:0 0 30px}
.eylus-hero-button-icon svg{width:28px;height:28px}
.eylus-hero-button strong{font-size:16px;font-weight:780;display:block;line-height:1.25;white-space:nowrap}
.eylus-hero-button small{font-size:10px;font-weight:550;display:block;line-height:1.45;margin-top:6px;white-space:nowrap}
.eylus-hero-primary{background:#6422cc;color:#fff;border:1px solid #6422cc}
.eylus-hero-primary:hover{background:#5215b4;color:#fff}
.eylus-hero-primary small{color:#f0e5ff}
.eylus-hero-secondary{background:#fff;color:#161329;border:2px solid #682ed0}
.eylus-hero-secondary:hover{background:#fcfaff;color:#161329}
.eylus-hero-secondary small{color:#504765}
@media(max-width:1350px){
  .eylus-header .nav-inner{width:calc(100% - 52px);gap:22px}
  .eylus-header .wordmark img{width:164px}
  .eylus-header .nav-links{gap:23px}
  .eylus-header .nav-links>a,.eylus-header .nav-drop>summary{font-size:14px}
  .eylus-header .nav-login,.eylus-header .nav-write{padding:10px 14px}
  .eylus-hero-container{width:calc(100% - 62px)}
  .eylus-home-hero{min-height:720px}
  .eylus-hero-content{width:59%;max-width:660px}
  .eylus-hero-prompt{font-size:13px;gap:12px}
  .eylus-hero-prompts{margin-bottom:40px}
  .eylus-home-hero h1{font-size:clamp(56px,6vw,76px)}
  .eylus-hero-description{font-size:18px}
  .eylus-hero-button{padding:13px;gap:9px;min-height:76px}
  .eylus-hero-button strong{font-size:14px}
  .eylus-hero-button small{font-size:9px}
}
@media(max-width:960px){
  .eylus-header .nav-inner{height:73px}
  .eylus-header .nav-links{display:none;position:absolute;top:73px;left:0;right:0;margin:0;background:#fff;border-bottom:1px solid #e6dff0;padding:16px 23px 23px;box-shadow:0 15px 24px #21112e12;z-index:45;gap:4px}
  .eylus-header .nav-links.open{display:flex;flex-direction:column;align-items:stretch}
  .eylus-header .nav-links>a,.eylus-header .nav-drop>summary{padding:12px 8px;width:100%;font-size:15px}
  .eylus-header .nav-drop-panel{position:static;min-width:0;box-shadow:none;padding:2px 5px 6px;margin-bottom:8px}
  .eylus-header .mobile-signin{display:flex!important}
  .eylus-header .nav-login{display:none}
  .eylus-header .menu-toggle{display:block}
  .eylus-home-hero{display:flex;flex-direction:column-reverse;min-height:0}
  .eylus-hero-photo{position:relative;flex:none;width:100%;height:420px;inset:auto}
  .eylus-hero-photo:before{background:linear-gradient(180deg,#fff 0%,rgba(255,255,255,0) 25%)}
  .eylus-hero-container{width:calc(100% - 60px)}
  .eylus-hero-content{width:100%;max-width:780px;padding:51px 0 27px}
  .eylus-hero-prompts{margin-bottom:34px}
  .eylus-hero-prompt{font-size:15px;white-space:normal}
  .eylus-home-hero h1{font-size:clamp(54px,9vw,79px)}
  .eylus-hero-description{font-size:19px;margin-bottom:30px}
  .eylus-hero-actions{max-width:730px}
  .eylus-hero-button{min-height:77px}
  .eylus-hero-button strong{font-size:16px}
  .eylus-hero-button small{font-size:10px}
}
@media(max-width:600px){
  .eylus-header .nav-inner{width:calc(100% - 32px);height:68px;gap:8px}
  .eylus-header .wordmark img{width:123px}
  .eylus-header .nav-cta{margin-left:auto;margin-right:6px}
  .eylus-header .nav-write{min-height:38px;padding:8px 11px;border-radius:9px;gap:6px;font-size:12px}
  .eylus-header .nav-write svg{width:17px;height:17px}
  .eylus-header .nav-links{top:68px}
  .eylus-header .menu-toggle{padding:8px 10px;font-size:17px}
  .eylus-hero-container{width:calc(100% - 36px)}
  .eylus-hero-content{padding:32px 0 23px}
  .eylus-hero-prompts{gap:10px;margin-bottom:34px}
  .eylus-hero-prompt{align-items:flex-start;gap:10px;font-size:12px;line-height:1.65}
  .eylus-hero-prompt b{font-size:14px;margin:0 2px}
  .eylus-prompt-icon{flex-basis:39px;width:39px;height:39px;border-radius:11px}
  .eylus-prompt-icon svg{width:22px;height:22px}
  .eylus-home-hero h1{font-size:clamp(48px,12.7vw,69px);margin-bottom:26px}
  .eylus-hero-description{font-size:17px;line-height:1.5;margin-bottom:26px}
  .eylus-desktop-break{display:none}
  .eylus-hero-actions{display:grid;grid-template-columns:1fr;gap:10px}
  .eylus-hero-button{width:100%;min-height:71px;padding:13px 17px}
  .eylus-hero-button strong{font-size:16px}
  .eylus-hero-button small{font-size:11px;white-space:normal}
  .eylus-hero-photo{height:315px}
}
@media(prefers-reduced-motion:reduce){
 .eylus-hero-button,.eylus-header .nav-login,.eylus-header .nav-write{transition:none}
}
'''

# Eylus homepage: photo-led, single-screen introduction; keep imagery and copy intact.
CSS += r'''
.eylus-home-hero{display:flex;flex-direction:row;align-items:center;min-height:min(880px,calc(100svh - 82px));background:#eee9f7;overflow:visible}
.eylus-hero-photo{position:absolute;inset:0;width:100%;height:100%;overflow:hidden;pointer-events:none}
.eylus-hero-photo img{object-fit:cover;object-position:center 41%;width:100%;height:100%}
.eylus-hero-photo:before{background:linear-gradient(90deg,rgba(255,255,255,.97) 0%,rgba(255,255,255,.94) 30%,rgba(255,255,255,.75) 49%,rgba(255,255,255,.22) 100%);z-index:1}
.eylus-hero-container{width:min(1320px,calc(100% - 96px));z-index:3}
.eylus-hero-content{width:min(720px,68%);max-width:720px;padding:84px 0 91px}
.eylus-hero-prompts{margin-bottom:38px}
.eylus-hero-prompt{white-space:normal}
.eylus-hero-actions{max-width:720px}
.eylus-hero-actions>.eylus-contact-menu,.eylus-hero-actions>a{flex:1 1 0;min-width:0}
.eylus-hero-button{min-height:76px;width:100%;box-shadow:0 12px 28px rgba(56,22,114,.16)}
.eylus-hero-primary,.eylus-hero-secondary{background:#6422cc;border:1px solid #6422cc;color:#fff}
.eylus-hero-primary:hover,.eylus-hero-secondary:hover{background:#5117a9;color:#fff;border-color:#5117a9}
.eylus-hero-primary small,.eylus-hero-secondary small{color:#f0e7ff}
.eylus-contact-menu,.eylus-nav-contact{position:relative}
.eylus-contact-menu>summary,.eylus-nav-contact>summary{list-style:none;cursor:pointer}
.eylus-contact-menu>summary::-webkit-details-marker,.eylus-nav-contact>summary::-webkit-details-marker{display:none}
.eylus-contact-summary-copy{flex:1;min-width:0}
.eylus-contact-chevron{margin-left:auto;font-size:23px;line-height:1;color:#f4eaff;transition:transform .16s}
.eylus-contact-menu[open] .eylus-contact-chevron{transform:rotate(180deg)}
.eylus-contact-options{position:absolute;left:0;right:0;top:calc(100% + 9px);display:grid;gap:3px;z-index:60;padding:9px;border:1px solid #e6dff1;border-radius:14px;background:#fff;box-shadow:0 22px 52px rgba(31,15,68,.18)}
.eylus-contact-options a{display:flex;align-items:center;justify-content:space-between;gap:9px;min-height:52px;padding:11px 14px;border-radius:9px;color:#211a38;font-size:14px;font-weight:750}
.eylus-contact-options a:hover,.eylus-contact-options a:focus-visible{background:#f3effb;color:#5723b8}
.eylus-contact-options a small{font-size:11px;font-weight:500;color:#716783}
.eylus-header .eylus-nav-contact{flex:none}
.eylus-header .eylus-nav-contact>.nav-write{display:inline-flex}
.eylus-contact-nav-options{min-width:260px;right:0;left:auto}
.eylus-contact-menu[open]>summary,.eylus-nav-contact[open]>summary{outline-offset:3px}
@media(max-width:1120px){
 .eylus-home-hero{min-height:720px}
 .eylus-hero-container{width:calc(100% - 64px)}
 .eylus-hero-content{width:75%;max-width:660px;padding:67px 0}
 .eylus-hero-prompt{font-size:13px}
 .eylus-home-hero h1{font-size:clamp(52px,6.1vw,72px)}
 .eylus-hero-actions{flex-wrap:wrap}
}
@media(max-width:960px){
 .eylus-home-hero{display:flex;flex-direction:row;align-items:center;min-height:690px}
 .eylus-hero-photo{position:absolute;inset:0;width:100%;height:100%}
 .eylus-hero-photo:before{background:linear-gradient(90deg,rgba(255,255,255,.96),rgba(255,255,255,.91) 43%,rgba(255,255,255,.65) 100%)}
 .eylus-hero-container{width:calc(100% - 58px)}
 .eylus-hero-content{width:min(700px,100%);max-width:700px;padding:64px 0}
 .eylus-hero-actions{max-width:700px;flex-direction:row}
 .eylus-hero-button{min-height:74px}
}
@media(max-width:650px){
 .eylus-home-hero{min-height:calc(100svh - 68px);align-items:center}
 .eylus-hero-photo img{object-position:59% center}
 .eylus-hero-photo:before{background:linear-gradient(180deg,rgba(255,255,255,.91) 0%,rgba(255,255,255,.95) 44%,rgba(255,255,255,.88) 100%)}
 .eylus-hero-container{width:calc(100% - 38px)}
 .eylus-hero-content{padding:40px 0 53px;width:100%}
 .eylus-hero-prompts{margin-bottom:28px;gap:11px}
 .eylus-hero-prompt{font-size:12px;line-height:1.55;gap:10px}
 .eylus-home-hero h1{font-size:clamp(43px,11.5vw,62px);margin-bottom:25px}
 .eylus-hero-description{font-size:16px;line-height:1.5;margin-bottom:27px}
 .eylus-hero-actions{display:grid;grid-template-columns:1fr;max-width:450px}
 .eylus-hero-button{min-height:69px}
 .eylus-contact-menu[open] .eylus-hero-contact-options{position:relative;top:auto;margin-top:8px}
 .eylus-header .eylus-nav-contact>.nav-write{min-height:38px}
 .eylus-contact-nav-options{min-width:240px}
}
@media(max-width:370px){
 .eylus-header .nav-write span{display:none}
 .eylus-hero-content{padding:30px 0 42px}
 .eylus-hero-prompts{gap:7px;margin-bottom:20px}
 .eylus-home-hero h1{font-size:43px}
 .eylus-hero-button strong{font-size:14px}
}
@media(prefers-reduced-motion:reduce){.eylus-contact-chevron{transition:none}}
'''


# Match the approved photo-led composition on desktop and give mobile its own
# genuinely visible photograph, rather than washing it out behind long text.
CSS += r'''
@media(min-width:961px){
 .eylus-home-hero{min-height:min(790px,calc(100svh - 82px));background:#fff}
 .eylus-hero-photo{inset:0 0 0 auto;width:68%;height:100%}
 .eylus-hero-photo img{object-fit:cover;object-position:center 42%}
 .eylus-hero-photo:before{background:linear-gradient(90deg,#fff 0%,rgba(255,255,255,.97) 14%,rgba(255,255,255,.69) 33%,rgba(255,255,255,.07) 69%,transparent 100%)}
 .eylus-hero-content{width:60%;padding:62px 0}
 .eylus-hero-prompts{margin-bottom:30px}
 .eylus-home-hero h1{font-size:clamp(62px,5.4vw,80px)}
 .eylus-hero-description{margin-bottom:30px}
 .eylus-hero-button{min-height:73px}
}
@media(min-width:651px) and (max-width:960px){
 .eylus-home-hero{min-height:700px}
 .eylus-hero-photo:before{background:linear-gradient(90deg,rgba(255,255,255,.97) 0%,rgba(255,255,255,.88) 33%,rgba(255,255,255,.27) 100%)}
 .eylus-hero-content{padding:44px 0}
 .eylus-hero-prompts{margin-bottom:22px}
}
@media(max-width:650px){
 .eylus-home-hero{display:block;position:relative;min-height:0;background:#fff;overflow:hidden;border-bottom:1px solid #eee9f3;padding-top:198px}
 .eylus-hero-photo{position:absolute;inset:0 0 auto;width:100%;height:305px;overflow:hidden}
 .eylus-hero-photo img{display:block;width:100%;height:100%;object-fit:cover;object-position:center 30%}
 .eylus-hero-photo:before{background:linear-gradient(180deg,rgba(255,255,255,0) 0%,rgba(255,255,255,.01) 37%,rgba(255,255,255,.48) 63%,rgba(255,255,255,.95) 88%,#fff 100%)}
 .eylus-hero-container{position:relative;width:calc(100% - 34px);z-index:3}
 .eylus-hero-content{width:100%;max-width:none;padding:0 0 35px}
 .eylus-hero-prompts{display:grid;gap:6px;margin:0 0 18px}
 .eylus-hero-prompt{display:flex;align-items:center;gap:9px;font-size:11px;line-height:1.36;letter-spacing:-.015em;white-space:normal}
 .eylus-hero-prompt b{font-size:11px;margin:0 1px}
 .eylus-prompt-icon{flex:0 0 31px;width:31px;height:31px;border-radius:9px;background:#eee5fae8}
 .eylus-prompt-icon svg{width:17px;height:17px}
 .eylus-home-hero h1{font-size:clamp(43px,11vw,55px);line-height:1.01;letter-spacing:-.055em;margin:0 0 19px}
 .eylus-home-hero h1 em:after{bottom:-9px;height:4px;border-top-width:3px}
 .eylus-hero-description{font-size:14px;line-height:1.48;margin-bottom:20px;max-width:430px}
 .eylus-hero-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;max-width:none}
 .eylus-hero-actions>.eylus-contact-menu,.eylus-hero-actions>a{min-width:0;max-width:100%}
 .eylus-hero-button{display:flex;align-items:center;gap:8px;min-height:70px;padding:10px 10px;border-radius:12px;box-shadow:0 5px 14px #42147c14}
 .eylus-hero-button-icon{flex:0 0 22px;width:22px}
 .eylus-hero-button-icon svg{width:21px;height:21px}
 .eylus-hero-button strong{font-size:12.5px;line-height:1.15;white-space:normal;overflow-wrap:normal;letter-spacing:-.02em}
 .eylus-hero-button small{display:none}
 .eylus-contact-chevron{font-size:15px;margin-left:auto}
 .eylus-contact-menu[open] .eylus-hero-contact-options{position:absolute;top:calc(100% + 7px);margin-top:0}
 .eylus-contact-options{padding:6px}
 .eylus-contact-options a{min-height:43px;flex-direction:column;align-items:flex-start;justify-content:center;gap:2px;padding:8px 10px;font-size:12px}
 .eylus-contact-options a small{display:block;font-size:10px}
}
@media(max-width:370px){
 .eylus-home-hero{padding-top:172px}
 .eylus-hero-photo{height:280px}
 .eylus-hero-container{width:calc(100% - 28px)}
 .eylus-hero-prompts{gap:4px}
 .eylus-hero-prompt{font-size:10.5px;line-height:1.35}
 .eylus-home-hero h1{font-size:clamp(39px,11vw,45px)}
 .eylus-hero-button{gap:6px;padding:9px 8px}
 .eylus-hero-button strong{font-size:11.5px}
}
'''


# Eylus hero and footer: mobile-first refinement approved 11 Nov 2026.
CSS += r'''
/* Compact, airy process chips, kept readable over the original workshop photo. */
.eylus-hero-prompts{gap:10px;margin-bottom:34px}
.eylus-hero-prompt{display:flex;align-items:center;gap:11px;width:fit-content;max-width:100%;padding:9px 15px 9px 10px;border:1px solid rgba(228,218,246,.94);border-radius:16px;background:rgba(255,255,255,.82);box-shadow:0 5px 22px rgba(49,28,95,.045);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);font-size:13px;font-weight:630;line-height:1.45;white-space:normal;color:#242035}
.eylus-hero-prompt>span:last-child{min-width:0;overflow-wrap:break-word}
.eylus-hero-prompt b{font-size:12px;margin:0 2px;color:#8858d2}
.eylus-prompt-icon{flex:0 0 35px;width:35px;height:35px;border-radius:11px;background:#efe9fb;color:#6633bc}
.eylus-prompt-icon svg{width:20px;height:20px}
/* A restrained primary CTA and clearly distinct quiet secondary CTA. */
.eylus-hero-actions{display:flex;gap:13px;align-items:stretch}
.eylus-hero-actions>a{flex:1 1 0;min-width:0}
.eylus-hero-button{border-radius:17px;min-height:76px;padding:14px 17px;gap:12px;box-shadow:0 7px 23px rgba(71,35,134,.095);transform:none}
.eylus-hero-button:hover{transform:translateY(-2px);box-shadow:0 11px 28px rgba(71,35,134,.14)}
.eylus-hero-primary{background:linear-gradient(120deg,#56319d,#7546c0);border:1px solid #6a40ad;color:#fff}
.eylus-hero-primary:hover{background:linear-gradient(120deg,#4d298d,#6739ad);border-color:#6739ad;color:#fff}
.eylus-hero-secondary{background:rgba(255,255,255,.92);border:1px solid #b4a0d4;color:#4c2986}
.eylus-hero-secondary:hover{background:#f6f0fe;border-color:#9d83c9;color:#432178}
.eylus-hero-primary small{color:#f2eafe}.eylus-hero-secondary small{color:#64547b}
.eylus-hero-button strong{white-space:normal;overflow-wrap:break-word;font-size:15px;letter-spacing:-.012em}
.eylus-hero-button small{display:block;font-size:11px;white-space:normal;line-height:1.35;margin-top:4px}
.eylus-hero-button-icon{flex:0 0 30px}
.eylus-hero-button-icon svg{width:24px;height:24px}
.eylus-hero-button-arrow{font-size:18px;margin-left:auto;opacity:.84;flex:none}
.eylus-trust-strip{padding:30px 0 36px;background:linear-gradient(180deg,#fff 0%,#f8f6fc 100%);border-bottom:1px solid #eee8f5}
.eylus-trust-inner{display:flex;gap:16px;align-items:center;justify-content:center;max-width:1060px}
.eylus-trust-mark{width:35px;height:35px;flex:0 0 35px;display:grid;place-items:center;border:1px solid #e5d9f4;border-radius:11px;color:#7651b2;background:#fff}
.eylus-trust-inner p{margin:0;color:#665b75;font-size:13px;line-height:1.65;flex:1}
.eylus-trust-inner p strong{color:#332746;font-weight:750}
.eylus-trust-inner>a{color:#6436a2;font-size:12px;font-weight:700;white-space:nowrap}
.eylus-trust-inner>a:hover{text-decoration:underline}
.eylus-footer{background:#f8f7fb;border-top:0;padding-top:57px;color:#332e40}
.eylus-footer .footer-top{gap:60px;padding-bottom:42px}
.eylus-footer .footer-links{gap:65px}
.eylus-footer .footer-links strong{font-size:11px;letter-spacing:.085em}
.eylus-footer .footer-links a{font-size:13px;line-height:1.65}
.eylus-footer .eylus-footer-brand p{font-weight:650;margin:14px 0 6px;font-size:15px}
.eylus-footer .eylus-footer-brand small{display:block;color:#766f7d;max-width:310px;line-height:1.7;font-size:12px}
.eylus-footer .footer-bottom{border-top:1px solid #e7e2ed;padding-top:19px;gap:18px}
@media(max-width:960px){
 .eylus-header .nav-cta{display:none!important}
 .eylus-header .menu-toggle{margin-left:auto}
 .eylus-home-hero .eylus-hero-content{max-width:780px}
}
@media(max-width:650px){
 .eylus-home-hero{padding-top:202px}
 .eylus-hero-photo{height:303px}
 .eylus-hero-prompts{gap:8px;margin-bottom:23px}
 .eylus-hero-prompt{max-width:100%;width:100%;gap:9px;padding:7px 10px 7px 8px;border-radius:12px;background:rgba(255,255,255,.88);font-size:11.5px;line-height:1.4}
 .eylus-prompt-icon{flex:0 0 30px;width:30px;height:30px;border-radius:9px}
 .eylus-prompt-icon svg{width:17px;height:17px}
 .eylus-home-hero h1{margin-bottom:23px}
 .eylus-hero-description{margin-bottom:22px}
 .eylus-hero-actions{display:grid!important;grid-template-columns:minmax(0,1fr)!important;gap:11px;max-width:100%}
 .eylus-hero-button{width:100%;min-height:75px;padding:14px 17px;gap:12px;border-radius:17px}
 .eylus-hero-button strong{font-size:16px;line-height:1.25}
 .eylus-hero-button small{display:block!important;font-size:11px;margin-top:4px}
 .eylus-hero-button-icon{flex:0 0 27px;width:27px}
 .eylus-hero-button-icon svg{width:23px;height:23px}
 .eylus-trust-strip{padding:25px 0 30px}
 .eylus-trust-inner{align-items:flex-start;gap:10px;flex-wrap:wrap}
 .eylus-trust-mark{flex-basis:30px;width:30px;height:30px}
 .eylus-trust-inner p{flex:1 1 calc(100% - 45px);font-size:12px}
 .eylus-trust-inner>a{margin-left:40px;margin-top:-2px}
 .eylus-footer{padding-top:39px}
 .eylus-footer .footer-top{display:grid;grid-template-columns:1fr;gap:31px;padding-bottom:33px}
 .eylus-footer .eylus-footer-brand small{max-width:390px}
 .eylus-footer .footer-links{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:19px}
 .eylus-footer .footer-bottom{display:flex;flex-wrap:wrap;justify-content:space-between;gap:10px;padding-top:16px}
}
@media(max-width:370px){
 .eylus-hero-prompt{font-size:10.5px;padding:6px 7px}
 .eylus-hero-button{min-height:73px}
 .eylus-hero-button strong{font-size:15px}
}
@media(prefers-reduced-motion:reduce){.eylus-hero-button{transition:none}}
'''

# Clean hero and simplified navigation (approved 11 Nov 2026).
CSS += r'''
/* Keep only the clear message: headline and two actions. All former prompt chips,
   explanatory paragraph and redundant transition strip have been removed in markup. */
.eylus-hero-content{display:flex;flex-direction:column;gap:26px}
.eylus-home-hero h1{margin:0!important;max-width:650px}
.eylus-hero-actions{margin-top:0}
.eylus-home-hero{min-height:600px}
.eylus-hero-content{padding:74px 0}
.eylus-header .nav-links{gap:32px}
.eylus-footer .footer-links{gap:70px}
@media (min-width:961px){
 .eylus-home-hero{min-height:620px}
 .eylus-hero-content{padding:74px 0;width:60%}
 .eylus-hero-actions{max-width:680px}
}
@media (min-width:651px) and (max-width:960px){
 .eylus-home-hero{min-height:560px}
 .eylus-hero-content{padding:58px 0;gap:27px}
}
@media (max-width:650px){
 .eylus-home-hero{padding-top:288px;min-height:0;background:#fff}
 .eylus-hero-photo{height:330px}
 .eylus-hero-photo:before{background:linear-gradient(180deg,rgba(255,255,255,0) 0%,rgba(255,255,255,0) 61%,rgba(255,255,255,.45) 83%,#fff 100%)}
 .eylus-hero-content{padding:18px 0 49px;gap:26px}
 .eylus-home-hero h1{font-size:clamp(43px,11vw,56px);line-height:1.02;margin:0!important}
 .eylus-hero-actions{grid-template-columns:minmax(0,1fr);gap:11px}
 .eylus-hero-button{min-height:76px}
 .eylus-footer{border-top:1px solid #e8e3ee}
}
@media (max-width:370px){
 .eylus-home-hero{padding-top:263px}
 .eylus-hero-photo{height:304px}
 .eylus-hero-content{padding-top:14px;gap:23px}
}
'''

# Approved homepage polish: more readable workshop photo, calmer CTAs, clear heading.
CSS += r'''
/* Final hero refinements: both actions are neutral, outlined and equally weighted. */
.eylus-home-hero .eylus-hero-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;width:100%;max-width:680px}
.eylus-home-hero .eylus-hero-actions>a{min-width:0;max-width:100%}
.eylus-home-hero .eylus-hero-button{background:rgba(255,255,255,.97);border:1.5px solid #8b62c5;color:#4e2787;box-shadow:0 6px 20px rgba(58,32,99,.075);min-width:0;min-height:77px}
.eylus-home-hero .eylus-hero-button:hover,.eylus-home-hero .eylus-hero-button:focus-visible{background:#f6f0ff;border-color:#6e3fac;color:#3c1a74;box-shadow:0 10px 25px rgba(81,44,143,.13)}
.eylus-home-hero .eylus-hero-button-icon,.eylus-home-hero .eylus-hero-button-arrow{color:#6b38b3}
.eylus-home-hero .eylus-hero-button small{color:#695982}
.eylus-home-hero .eylus-hero-content{gap:28px}
.eylus-home-hero .eylus-hero-content h1{line-height:1.035;max-width:690px}
.eylus-home-hero .eylus-hero-photo img{filter:none}
@media(min-width:961px){
 .eylus-home-hero .eylus-hero-photo:before{background:linear-gradient(90deg,#fff 0%,rgba(255,255,255,.985) 10%,rgba(255,255,255,.89) 25%,rgba(255,255,255,.48) 45%,rgba(255,255,255,.03) 72%,transparent 100%)}
 .eylus-home-hero .eylus-hero-content{padding-top:96px;padding-bottom:67px}
 .eylus-home-hero h1{font-size:clamp(52px,5.1vw,70px)}
}
@media(min-width:651px) and (max-width:960px){
 .eylus-home-hero .eylus-hero-photo:before{background:linear-gradient(90deg,rgba(255,255,255,.97) 0%,rgba(255,255,255,.88) 30%,rgba(255,255,255,.40) 68%,rgba(255,255,255,.13) 100%)}
 .eylus-home-hero .eylus-hero-content{padding-top:72px;padding-bottom:43px}
 .eylus-home-hero h1{font-size:clamp(49px,5.6vw,63px)}
}
@media(max-width:650px){
 .eylus-home-hero{padding-top:319px}
 .eylus-home-hero .eylus-hero-photo{height:365px}
 .eylus-home-hero .eylus-hero-photo:before{background:linear-gradient(180deg,rgba(255,255,255,0) 0%,rgba(255,255,255,0) 70%,rgba(255,255,255,.18) 81%,rgba(255,255,255,.72) 94%,#fff 100%)}
 .eylus-home-hero .eylus-hero-content{padding-top:18px;padding-bottom:39px;gap:23px}
 .eylus-home-hero h1{font-size:clamp(36px,9.5vw,47px);letter-spacing:-.052em;line-height:1.065}
 .eylus-home-hero .eylus-hero-actions{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:9px;max-width:100%}
 .eylus-home-hero .eylus-hero-button{gap:7px;padding:11px 9px;min-height:68px;border-radius:13px}
 .eylus-home-hero .eylus-hero-button-icon{width:23px;flex:0 0 23px}
 .eylus-home-hero .eylus-hero-button-icon svg{width:21px;height:21px}
 .eylus-home-hero .eylus-hero-button strong{font-size:12.5px;line-height:1.22;overflow-wrap:break-word}
 .eylus-home-hero .eylus-hero-button small{display:none!important}
 .eylus-home-hero .eylus-hero-button-arrow{font-size:14px;margin-left:auto}
}
@media(max-width:359px){
 .eylus-home-hero{padding-top:290px}
 .eylus-home-hero .eylus-hero-photo{height:332px}
 .eylus-home-hero .eylus-hero-actions{grid-template-columns:minmax(0,1fr)!important}
 .eylus-home-hero .eylus-hero-button{min-height:61px;padding:10px 14px}
 .eylus-home-hero .eylus-hero-button strong{font-size:14px}
 .eylus-home-hero h1{font-size:clamp(35px,10.6vw,40px)}
}
'''

# Give first-time visitors a concise description without crowding the mobile hero.
CSS += r'''
.eylus-home-hero .eylus-hero-content{gap:0}
.eylus-home-hero .eylus-hero-content h1{margin:0 0 20px!important}
.eylus-home-hero .eylus-hero-intro{font-size:17px;line-height:1.58;letter-spacing:-.01em;font-weight:450;color:#514a5c;max-width:580px;margin:0 0 26px;overflow-wrap:break-word}
.eylus-home-hero .eylus-hero-actions{margin:0}
@media(min-width:961px){
 .eylus-home-hero .eylus-hero-content{padding-top:77px;padding-bottom:68px}
 .eylus-home-hero .eylus-hero-intro{font-size:18px;line-height:1.55;margin-bottom:29px}
}
@media(min-width:651px) and (max-width:960px){
 .eylus-home-hero .eylus-hero-intro{font-size:16.5px;margin-bottom:25px}
}
@media(max-width:650px){
 .eylus-home-hero .eylus-hero-content h1{margin-bottom:13px!important}
 .eylus-home-hero .eylus-hero-intro{font-size:14.5px;line-height:1.48;color:#5a5363;margin-bottom:21px;max-width:37ch}
}
@media(max-width:359px){
 .eylus-home-hero .eylus-hero-intro{font-size:13.5px;line-height:1.47;margin-bottom:17px}
}
'''

# Center the Eylus introduction and move discover links to the copyright strip.
CSS += r'''
.eylus-footer{padding:57px 0 24px;background:#f9f8fc}
.eylus-footer .footer-top{display:block;text-align:center;max-width:840px;margin:0 auto;padding:0 0 43px}
.eylus-footer .eylus-footer-brand{display:flex;flex-direction:column;align-items:center;text-align:center;min-width:0}
.eylus-footer .eylus-footer-brand .wordmark{display:inline-flex;justify-content:center;align-items:center}
.eylus-footer .eylus-footer-brand .wordmark img{display:block;width:190px;max-width:100%;height:auto}
.eylus-footer .eylus-footer-brand>p{font-size:22px;line-height:1.35;font-weight:760;color:#29233b;max-width:none;margin:22px auto 15px;letter-spacing:-.025em}
.eylus-footer .eylus-footer-intro{width:100%;max-width:740px;margin:0 auto}
.eylus-footer .eylus-footer-intro p{font-size:15px;font-weight:400;line-height:1.72;max-width:none;color:#625b6b;margin:0 auto 12px}
.eylus-footer .eylus-footer-intro p:last-child{margin-bottom:0}
.eylus-footer .footer-bottom{display:grid;grid-template-columns:max-content minmax(0,1fr) max-content;align-items:center;gap:22px;border-top:1px solid #e7e1ed;padding-top:21px;color:#756d80;font-size:11px}
.eylus-footer .eylus-footer-nav{display:flex;justify-content:center;align-items:center;gap:10px 23px;flex-wrap:wrap;min-width:0}
.eylus-footer .eylus-footer-nav a{font-size:12px;line-height:1.5;white-space:nowrap;color:#574c6c;transition:color .16s}
.eylus-footer .eylus-footer-nav a:hover,.eylus-footer .eylus-footer-privacy:hover{color:#6239b4}
.eylus-footer .eylus-footer-copyright,.eylus-footer .eylus-footer-privacy{white-space:nowrap}
@media(max-width:1050px){
 .eylus-footer .footer-bottom{grid-template-columns:1fr 1fr;gap:18px}
 .eylus-footer .eylus-footer-nav{grid-column:1 / -1;grid-row:1;gap:12px 23px}
 .eylus-footer .eylus-footer-copyright{grid-column:1;grid-row:2;text-align:left}
 .eylus-footer .eylus-footer-privacy{grid-column:2;grid-row:2;text-align:right}
}
@media(max-width:650px){
 .eylus-footer{padding:38px 0 20px}
 .eylus-footer .footer-top{padding-bottom:32px}
 .eylus-footer .eylus-footer-brand .wordmark img{width:159px}
 .eylus-footer .eylus-footer-brand>p{font-size:19px;margin:17px auto 13px}
 .eylus-footer .eylus-footer-intro{max-width:440px}
 .eylus-footer .eylus-footer-intro p{font-size:13px;line-height:1.65;margin-bottom:13px}
 .eylus-footer .footer-bottom{padding-top:19px;gap:20px 10px;font-size:10.5px}
 .eylus-footer .eylus-footer-nav{gap:12px 18px}
 .eylus-footer .eylus-footer-nav a{font-size:11.5px}
}
@media(max-width:360px){
 .eylus-footer .eylus-footer-nav{gap:10px 14px}
 .eylus-footer .eylus-footer-nav a{font-size:11px}
 .eylus-footer .eylus-footer-privacy{font-size:10px}
}
'''

# Minimal footer legal strip: only copyright and privacy link.
CSS += r'''
.eylus-footer .footer-bottom{
 display:flex;flex-direction:row;justify-content:space-between;align-items:center;
 flex-wrap:wrap;gap:10px 18px;
}
.eylus-footer .eylus-footer-copyright,
.eylus-footer .eylus-footer-privacy{grid-column:auto;grid-row:auto}
@media(max-width:650px){
 .eylus-footer .footer-bottom{display:flex;flex-direction:row;justify-content:space-between;gap:10px}
}
'''


# Quiet legal row with a visible sitewide guide link (not hidden from visitors).
CSS += r'''
.eylus-footer .eylus-footer-legal{display:flex;align-items:center;justify-content:flex-end;gap:17px;flex-wrap:wrap}
.eylus-footer .eylus-footer-legal a{font-size:11px;line-height:1.5;color:#756d80;white-space:nowrap}
.eylus-footer .eylus-footer-legal a:hover{color:#6239b4}
@media(max-width:650px){
 .eylus-footer .eylus-footer-legal{gap:12px}
 .eylus-footer .eylus-footer-legal a{font-size:10.5px}
}
@media(max-width:359px){
 .eylus-footer .footer-bottom{gap:8px}
 .eylus-footer .eylus-footer-legal{gap:9px}
 .eylus-footer .eylus-footer-legal a{font-size:10px}
}
'''

# Lightweight guide design: readable typography, indexable semantic content,
# purposeful internal links, no fabricated screenshots or third-party scripts.
CSS += r'''
.home-knowledge{padding:76px 0 84px;background:linear-gradient(180deg,#fff 0%,#f8f6fd 100%);border-bottom:1px solid #ede8f5}
.home-knowledge-inner{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(280px,.65fr);gap:75px;align-items:center}
.home-knowledge-kicker,.guide-kicker{display:block;color:#6841aa;font-size:11px;font-weight:800;letter-spacing:.14em}
.home-knowledge h2{font-size:clamp(28px,3.2vw,41px);letter-spacing:-.045em;line-height:1.17;margin:16px 0 19px}
.home-knowledge p{font-size:15px;line-height:1.78;color:#635c6d;max-width:710px;margin:0 0 23px}
.home-knowledge-links{display:flex;gap:20px 25px;flex-wrap:wrap;align-items:center}
.home-knowledge-links a{font-size:13px;font-weight:750;color:#5e2f9f;line-height:1.5}
.home-knowledge-links .home-knowledge-main-link{border-bottom:1px solid #906dc2;padding-bottom:4px}
.home-knowledge-links .home-knowledge-quiet-link{color:#655975}
.home-knowledge-links a:hover{color:#3d167e}
.home-knowledge-facts{border:1px solid #e9e1f3;background:#fff;border-radius:17px;padding:9px 25px;box-shadow:0 12px 40px #30224909}
.home-knowledge-facts div{display:grid;grid-template-columns:36px 1fr;gap:4px 11px;padding:19px 0;border-bottom:1px solid #ece8f2}
.home-knowledge-facts div:last-child{border-bottom:0}
.home-knowledge-facts span{grid-row:span 2;color:#846abe;font-size:13px;font-weight:750}
.home-knowledge-facts strong{font-size:14px;color:#282039}
.home-knowledge-facts small{font-size:12px;line-height:1.6;color:#766e7e}
.guide-page{background:#fff;color:#292439}
.guide-header{background:linear-gradient(125deg,#fff 18%,#f4f0fd 100%);border-bottom:1px solid #ebe4f3;padding:54px 0 66px}
.guide-header-inner{max-width:1100px}
.guide-breadcrumb{display:flex;gap:10px;align-items:center;color:#7d718d;font-size:12px;margin:0 0 37px}
.guide-breadcrumb a:hover{color:#5928a1}
.guide-header h1{max-width:980px;font-size:clamp(36px,4.7vw,62px);letter-spacing:-.053em;line-height:1.12;margin:17px 0 25px;font-weight:740}
.guide-header h1 em{font-style:normal;color:#6840b4}
.guide-deck{font-size:clamp(16px,1.7vw,19px);line-height:1.7;color:#5e566b;max-width:780px;margin:0}
.guide-header-actions{display:flex;gap:16px 28px;flex-wrap:wrap;margin-top:29px}
.guide-header-actions a{font-size:13px;font-weight:740;color:#62359e}
.guide-body{display:grid;grid-template-columns:225px minmax(0,790px);justify-content:space-between;gap:55px;padding-top:64px;padding-bottom:65px}
.guide-side{position:sticky;top:117px;align-self:start;border-left:1px solid #e7e0f0;padding:10px 0 10px 17px;display:grid;gap:13px}
.guide-side p{font-size:10px;letter-spacing:.13em;font-weight:850;color:#8b71b3;margin:0 0 7px}
.guide-side a{font-size:12px;line-height:1.45;color:#6f657c}
.guide-side a:hover{color:#592b9e}
.guide-copy{min-width:0}
.guide-copy>section{scroll-margin-top:110px;margin-bottom:55px}
.guide-copy h2{font-size:clamp(25px,2.6vw,34px);line-height:1.26;letter-spacing:-.035em;margin:0 0 19px}
.guide-copy h3{font-size:19px;line-height:1.45;letter-spacing:-.022em;margin:26px 0 7px}
.guide-copy p{font-size:15px;line-height:1.83;color:#585366;margin:0 0 18px}
.guide-copy strong{color:#30263f;font-weight:730}
.guide-copy a:not(.guide-button-primary):not(.guide-button-secondary){color:#633caa;text-decoration:underline;text-underline-offset:3px}
.guide-note{background:#f6f3fc;border-left:3px solid #865dbe;border-radius:0 10px 10px 0;padding:20px 23px;color:#51465f;font-size:14px;line-height:1.8;margin:24px 0}
.guide-steps{padding-left:25px;margin:25px 0}
.guide-steps li{padding:0 0 14px 9px;margin-bottom:15px}
.guide-steps li::marker{color:#6d42b1;font-weight:800}
.guide-steps strong{font-size:16px}
.guide-steps p{margin:8px 0 0}
.guide-benefits{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px;margin:26px 0}
.guide-benefits div{border:1px solid #e9e2f1;background:#fbfafd;border-radius:12px;padding:23px}
.guide-benefits span{color:#936aca;font-size:12px;font-weight:800}
.guide-benefits h3{font-size:17px;margin:12px 0 9px}
.guide-benefits p{font-size:13px;margin:0;line-height:1.75}
.guide-checklist{padding-left:23px;margin:22px 0}
.guide-checklist li{font-size:15px;line-height:1.75;color:#585366;padding:0 0 11px 4px}
.guide-checklist li::marker{color:#774cb0}
.guide-last{background:#f6f2fc;border:1px solid #e9e0f2;border-radius:18px;padding:35px}
.guide-last h2{font-size:27px;margin:15px 0}
.guide-last-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:24px}
.guide-button-primary,.guide-button-secondary{display:inline-flex;align-items:center;justify-content:center;gap:14px;padding:13px 17px;border-radius:9px;font-size:13px;font-weight:750;min-height:47px}
.guide-button-primary{background:#6237a6;color:#fff}
.guide-button-primary:hover{background:#512b91}
.guide-button-secondary{background:#fff;color:#57338d;border:1px solid #b6a4d2}
.guide-button-secondary:hover{background:#f7f3ff}
@media(max-width:900px){
 .home-knowledge-inner{grid-template-columns:1fr;gap:25px}
 .home-knowledge-facts{max-width:670px}
 .guide-body{grid-template-columns:1fr;gap:0;padding-top:38px}
 .guide-side{display:none}
}
@media(max-width:650px){
 .home-knowledge{padding:49px 0 56px}
 .home-knowledge p{font-size:14px}
 .home-knowledge-facts{padding:3px 20px}
 .guide-header{padding:33px 0 44px}
 .guide-breadcrumb{margin-bottom:25px}
 .guide-header h1{font-size:clamp(33px,9vw,45px);line-height:1.16}
 .guide-header-actions{gap:14px 23px}
 .guide-copy>section{margin-bottom:44px}
 .guide-copy p,.guide-checklist li{font-size:14px}
 .guide-benefits{grid-template-columns:1fr}
 .guide-last{padding:26px 20px}
 .guide-last-actions{flex-direction:column}
 .guide-last-actions a{width:100%}
}
'''

EYLUS_HOME_HERO = '''<section class="eylus-home-hero" aria-labelledby="eylus-hero-heading">
  <div class="eylus-hero-photo" aria-hidden="true">
    <img src="/assets/eylus-hero-workshop.webp" width="706" height="760" alt="" decoding="async" fetchpriority="high">
  </div>
  <div class="wrap eylus-hero-container"><div class="eylus-hero-content">
    <h1 id="eylus-hero-heading">Süreçlerinizi<br><em>nasıl takip<br>ediyorsunuz?</em></h1>
    <p class="eylus-hero-intro">Eylus, üretim yapan işletmeler için geliştirilmiş bir yönetim yazılımıdır. Siparişlerinizi, üretim aşamalarınızı ve sevkiyatlarınızı tek sistemden takip edin.</p>
    <div class="eylus-hero-actions">
      <a class="eylus-hero-button eylus-hero-primary eylus-demo-request" href="https://wa.me/905368163125?text=Merhaba%2C%20Eylus%20icin%20demo%20talep%20ediyorum." target="_blank" rel="noopener noreferrer" aria-label="WhatsApp üzerinden Eylus demo talep et"><span class="eylus-hero-button-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11.5a7.9 7.9 0 0 1-8 8 9 9 0 0 1-3.7-.8L4 20l1.4-4.1A8 8 0 1 1 20 11.5Z"/><path d="M8.7 10.2c1 2.1 2.3 3.4 4.4 4.4"/></svg></span><span><strong>Demo Talep Et</strong><small>WhatsApp üzerinden hızlıca ulaşın</small></span><span class="eylus-hero-button-arrow" aria-hidden="true">↗</span></a>
      <a class="eylus-hero-button eylus-hero-secondary" href="/tekstil/"><span class="eylus-hero-button-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg></span><span><strong>Çözümleri İnceleyin</strong><small>Sorununuzu seçin, çözümümüzü görün</small></span></a>
    </div>
  </div></div>
</section>'''


# Helpful evergreen guide; a separate crawlable page rather than a long homepage hero.
ARTICLE_URL = '/uretim-takip-programi/'
HOME_READING_BANNER = '''
<section class="home-knowledge" aria-labelledby="home-knowledge-title">
  <div class="wrap home-knowledge-inner">
    <div class="home-knowledge-copy">
      <span class="home-knowledge-kicker">EYLUS REHBER</span>
      <h2 id="home-knowledge-title">Üretim takip programı ne işe yarar?</h2>
      <p>Bir siparişin nerede olduğunu öğrenmek için atölyeyi aramak zorunda değilsiniz. Üretim takip programı; sipariş, üretim aşaması ve teslimat bilgilerini aynı akışta toplar. Eylus’ta personel, ürünün QR kodunu okutarak yaptığı işlemi kaydeder; yönetici ise geciken işleri, yaklaşan teslimatları ve üretimin son durumunu telefonundan veya bilgisayarından inceleyebilir.</p>
      <div class="home-knowledge-links">
        <a href="/uretim-takip-programi/" class="home-knowledge-main-link">Üretim takip programı rehberini okuyun <span aria-hidden="true">↗</span></a>
        <a href="/urun/" class="home-knowledge-quiet-link">Eylus’un özelliklerini keşfedin <span aria-hidden="true">→</span></a>
      </div>
    </div>
    <div class="home-knowledge-facts" aria-label="Üretim takibinin temel adımları">
      <div><span>01</span><strong>Sipariş kaydı</strong><small>Model, renk, beden ve teslim tarihi bir arada</small></div>
      <div><span>02</span><strong>Üretim hareketi</strong><small>QR ile kayıt, aşama bazlı görünürlük</small></div>
      <div><span>03</span><strong>Sevkiyat planı</strong><small>Yaklaşan işleri zamanında değerlendirme</small></div>
    </div>
  </div>
</section>
'''

PRODUCTION_GUIDE = '''
<article class="guide-page">
  <header class="guide-header">
    <div class="wrap guide-header-inner">
      <nav class="guide-breadcrumb" aria-label="İçerik yolu"><a href="/">Ana sayfa</a><span aria-hidden="true">/</span><span>Üretim takip programı</span></nav>
      <span class="guide-kicker">EYLUS REHBER · ÜRETİM YÖNETİMİ</span>
      <h1>Üretim Takip Programı Nedir? <em>Siparişten Sevkiyata Üretiminizi Nasıl Yönetirsiniz?</em></h1>
      <p class="guide-deck">Siparişiniz atölyede hangi aşamada? Hangi işler gecikiyor, yarın ne sevk edilecek? Üretim takip programı bu soruların cevaplarını tek yerde görmenizi sağlar.</p>
      <div class="guide-header-actions">
        <a href="#uretim-takip-nedir">Rehberi okuyun <span aria-hidden="true">↓</span></a>
        <a href="/tekstil/">Eylus çözümlerini inceleyin <span aria-hidden="true">↗</span></a>
      </div>
    </div>
  </header>
  <div class="wrap guide-body">
    <aside class="guide-side" aria-label="Yazı içeriği">
      <p>BU YAZIDA</p>
      <a href="#uretim-takip-nedir">Üretim takip programı nedir?</a>
      <a href="#uretim-takip-adimlar">Nasıl çalışır?</a>
      <a href="#qr-ile-uretim">QR kod ile üretim takibi</a>
      <a href="#yoneticiye-faydasi">İşletme sahibine faydaları</a>
      <a href="#program-secerken">Program seçerken nelere bakmalı?</a>
      <a href="#uretim-takip-sorular">Sık sorulan sorular</a>
    </aside>
    <div class="guide-copy">
      <section id="uretim-takip-nedir" aria-labelledby="guide-what">
        <h2 id="guide-what">Üretim takip programı nedir?</h2>
        <p><strong>Üretim takip programı</strong>, bir işletmenin aldığı siparişleri, üretimde yapılan işlemleri ve teslimat sürecini dijital ortamda izlemek için kullanılan yazılımdır. Hangi ürünün hangi aşamada olduğu, ne zaman teslim edileceği ve nerede beklediği aynı kayıtta görülebilir.</p>
        <p>Örneğin bir tekstil atölyesinde model, renk, beden ve adet bilgileriyle açılan sipariş önce kesime, sonra dikime ve süslemeye ilerler. Bu hareketler farklı defterlerde veya mesajlarda tutulursa işletme sahibi güncel durumu öğrenmek için çalışanları tek tek aramak zorunda kalır. Dijital üretim takibi, bu dağınık bilgileri tek bir akışta toplar.</p>
        <div class="guide-note"><strong>Kısaca:</strong> Üretim takip yazılımı yalnızca “kaç siparişimiz var?” sorusunu değil, “hangi sipariş şimdi nerede ve sıradaki işimiz ne?” sorusunu yanıtlamaya yardımcı olur.</div>
      </section>

      <section id="uretim-takip-adimlar" aria-labelledby="guide-how">
        <h2 id="guide-how">Üretim takip programı nasıl çalışır?</h2>
        <p>İyi bir sistemin başlangıç noktası sipariştir. Siparişin üretim bilgileriyle bağlantısı kurulduğunda takip, personel için günlük bir kayıt işlemine; yönetici için ise güncel bir iş görünümüne dönüşür.</p>
        <ol class="guide-steps">
          <li><strong>Siparişi açın.</strong><p>Müşteri, ürün kodu, renk, beden, adet ve teslim tarihini kaydedin. Siparişe ait bilgiler tek dosyada toplansın.</p></li>
          <li><strong>Üretim hareketlerini kaydedin.</strong><p>Ürün kesimden dikime, dikimden süslemeye ilerledikçe ilgili işlemler siparişe işlensin. Böylece bilgi sözlü aktarıma bağlı kalmasın.</p></li>
          <li><strong>Bekleyen işleri kontrol edin.</strong><p>Uzun süredir ilerlemeyen siparişleri ve eksik aşama kayıtlarını inceleyin. Gecikmenin büyümesini beklemeden ilgili işin durumunu değerlendirin.</p></li>
          <li><strong>Sevkiyatı planlayın.</strong><p>Yaklaşan teslimatları ve hazır siparişleri birlikte görerek hangi ürünün hangi gün çıkacağını organize edin.</p></li>
        </ol>
      </section>

      <section id="qr-ile-uretim" aria-labelledby="guide-qr">
        <h2 id="guide-qr">QR kod ile üretim takibi neyi kolaylaştırır?</h2>
        <p>Üretim takibinin işe yaraması, sahadaki kayıtların düzenli yapılmasına bağlıdır. Her hareketin sonradan bilgisayara yazılması istenirse takip ek bir iş yüküne dönüşebilir.</p>
        <p>Eylus'ta personel, ürüne ait <strong>QR kodunu okutarak</strong> ilgili üretim işlemini kaydeder. Bu kayıt siparişle eşleşir; yetkili kişiler de siparişin son aşamasını uygulamada görebilir. Amaç, personeli uzun formlarla oyalamadan atölyedeki gerçek hareketi kayıt altına almaktır.</p>
        <p>QR kod bir sihirli otomasyon değildir: İşlemin doğru aşamada, doğru kişi tarafından kaydedilmesi yine önemlidir. Eylus bu nedenle eksik aşama kayıtları ve uzun süre hareketsiz kalan işler için ayrıca kontrol ekranları sunar.</p>
      </section>

      <section id="yoneticiye-faydasi" aria-labelledby="guide-benefits">
        <h2 id="guide-benefits">Üretim takip sisteminin işletme sahibine faydaları</h2>
        <div class="guide-benefits">
          <div><span>01</span><h3>Daha az telefon trafiği</h3><p>“Siparişim nerede?” sorusunun cevabını her seferinde atölyeden istemek yerine sipariş kaydını inceleyin.</p></div>
          <div><span>02</span><h3>Gecikmeleri daha erken fark etme</h3><p>Hareketsiz işleri, eksik üretim hareketlerini ve yaklaşan teslimatları bir arada değerlendirin.</p></div>
          <div><span>03</span><h3>Sevkiyatın daha planlı ilerlemesi</h3><p>Haftalık teslimat görünümüyle hangi müşteriye ne zaman ürün çıkacağını takip edin.</p></div>
          <div><span>04</span><h3>Her yerden kontrol</h3><p>İnternet bağlantısıyla ofisten, evden veya seyahatteyken telefon ve bilgisayar üzerinden kayıtları inceleyin.</p></div>
        </div>
        <p>Takip yalnızca üretim aşamasıyla sınırlı kalmamalıdır. Eylus'un sipariş, sevkiyat, maliyet ve rapor ekranları; yöneticinin üretim kararlarını farklı bilgilerle birlikte değerlendirmesine yardımcı olur. İşletmenin ihtiyacına göre diğer modülleri de <a href="/tekstil/">Çözümler sayfasında</a> inceleyebilirsiniz.</p>
      </section>

      <section id="program-secerken" aria-labelledby="guide-checklist">
        <h2 id="guide-checklist">Üretim takip programı seçerken nelere dikkat edilmeli?</h2>
        <p>Her işletmenin üretim akışı farklıdır. Yalnızca ekran görüntüsüne bakmak yerine yazılımı kendi siparişleriniz üzerinden değerlendirin:</p>
        <ul class="guide-checklist">
          <li><strong>Üretim akışı:</strong> Kullanılan aşamalar kesim, dikim ve son işlemler gibi kendi süreçlerinizle uyumlu mu?</li>
          <li><strong>Personel için kullanım kolaylığı:</strong> İşlem kaydı sahada hızlı ve anlaşılır mı?</li>
          <li><strong>Sipariş ayrıntıları:</strong> Model, renk, beden, adet ve teslim tarihini birlikte takip edebiliyor musunuz?</li>
          <li><strong>Gecikme kontrolü:</strong> Uzun süredir ilerlemeyen işler ve eksik kayıtlar bulunabiliyor mu?</li>
          <li><strong>Mobil erişim:</strong> İşletme dışında olduğunuzda telefonunuzdan güncel durumu görebiliyor musunuz?</li>
        </ul>
        <p>Özellikle tekstil üretiminde numune ile seri siparişler, renk–beden dağılımları ve teslimat tarihleri birlikte yönetilir. Seçilen programın bu günlük gerçekleri karşılayıp karşılamadığını bir <a href="/demo/">canlı demo</a> üzerinden incelemek, uzun özellik listelerinden daha yararlı olacaktır.</p>
      </section>

      <section id="uretim-takip-sorular" aria-labelledby="guide-faq">
        <h2 id="guide-faq">Sık sorulan sorular</h2>
        <h3>Üretim takip programı ile stok takip programı aynı mı?</h3>
        <p>Hayır. Stok takip programları ağırlıklı olarak eldeki ürün ve malzeme hareketlerine odaklanır. Üretim takip programı ise siparişin hangi işlemden geçtiğini, nerede beklediğini ve teslimat sürecini görünür kılar. Bazı yazılımlar iki ihtiyacı birlikte karşılayabilir.</p>
        <h3>Üretim takip programı sadece bilgisayarda mı kullanılır?</h3>
        <p>Bu, yazılımın altyapısına bağlıdır. Eylus internet üzerinden çalışır; yetkili kullanıcılar, bağlantı ve erişim izinleri bulunduğunda telefon veya bilgisayardan işletmenin kayıtlarını inceleyebilir.</p>
        <h3>QR kod okutmak bütün üretim işlemlerini otomatik bitirir mi?</h3>
        <p>Hayır. QR kod, ilgili ürüne ve üretim kaydına hızlı erişmek için kullanılır. Personelin yaptığı işlemin doğru biçimde kaydedilmesi gerekir; sistem bu bilgilerle üretim durumunu günceller.</p>
      </section>

      <section class="guide-last" aria-labelledby="guide-cta-heading">
        <span class="guide-kicker">EYLUS İLE TANIŞIN</span>
        <h2 id="guide-cta-heading">Siparişinizin nerede olduğunu sormak yerine görün.</h2>
        <p>Üretim sürecini işletmenizin gerçek akışına göre değerlendirin. Eylus'un sipariş, QR, üretim aşaması ve sevkiyat ekranlarını inceleyin.</p>
        <div class="guide-last-actions">
          <a href="/tekstil/" class="guide-button-primary">Eylus çözümlerini görün <span aria-hidden="true">↗</span></a>
          <a href="/demo/" class="guide-button-secondary">Canlı demoyu inceleyin <span aria-hidden="true">→</span></a>
        </div>
      </section>
    </div>
  </div>
</article>
'''

# Separate crawlable article on warehouse inventory, distinct from production tracking.
STOCK_ARTICLE_URL = '/stok-takip-programi/'
STOCK_GUIDE = '''
<article class="guide-page">
  <header class="guide-header">
    <div class="wrap guide-header-inner">
      <nav class="guide-breadcrumb" aria-label="İçerik yolu"><a href="/">Ana sayfa</a><span aria-hidden="true">/</span><span>Stok takip programı</span></nav>
      <span class="guide-kicker">EYLUS REHBER · STOK VE LOJİSTİK</span>
      <h1>Stok Takip Programı Nedir? <em>Depodaki Ürün ve Malzemeleri Nasıl Yönetirsiniz?</em></h1>
      <p class="guide-deck">Hangi depoda kaç ürün var? Bir malzeme ne zaman girip çıktı? Müşteriye konsinye verilen ürünlerden ne kadar kaldı? Düzenli stok takibi bu soruların cevaplarını kayıt altına alır.</p>
      <div class="guide-header-actions">
        <a href="#stok-takip-nedir">Rehberi okuyun <span aria-hidden="true">↓</span></a>
        <a href="/tekstil/">Eylus çözümlerini inceleyin <span aria-hidden="true">↗</span></a>
      </div>
    </div>
  </header>
  <div class="wrap guide-body">
    <aside class="guide-side" aria-label="Yazı içeriği">
      <p>BU YAZIDA</p>
      <a href="#stok-takip-nedir">Stok takip programı nedir?</a>
      <a href="#hangi-stoklar">Malzeme ve ürün stoğu</a>
      <a href="#stok-hareketleri">Stok giriş ve çıkışları</a>
      <a href="#depo-yonetimi">Birden fazla depo</a>
      <a href="#konsinye-stok">Konsinye ürünler</a>
      <a href="#stok-ve-uretim">Üretim takibinden farkı</a>
      <a href="#stok-programi-secimi">Seçim kriterleri</a>
      <a href="#stok-sik-sorulanlar">Sık sorulan sorular</a>
    </aside>
    <div class="guide-copy">
      <section id="stok-takip-nedir" aria-labelledby="stock-what">
        <h2 id="stock-what">Stok takip programı nedir?</h2>
        <p><strong>Stok takip programı</strong>, işletmedeki ürün ve malzemelerin miktarlarını, hangi depoda bulunduklarını ve yapılan giriş-çıkış hareketlerini dijital olarak izlemek için kullanılan yazılımdır. Sadece mevcut adedi değil, bu adede hangi kayıtların sonucunda ulaşıldığını da görmeyi amaçlar.</p>
        <p>Bir tekstil atölyesi düşünün: Üretimde kullanılan malzemeler, tamamlanan ürünler ve farklı depolara yerleştirilen modeller aynı gün içinde hareket edebilir. Bu bilgiler yalnızca kâğıtta veya birbirinden bağımsız dosyalarda tutulduğunda, gerçek stok miktarını öğrenmek zorlaşır. Düzenli bir stok sistemi, depodaki fiziksel kontrolle sistem kaydını karşılaştırmayı kolaylaştırır.</p>
        <div class="guide-note"><strong>Önemli:</strong> Stok miktarının güvenilir olması için hareketlerin zamanında ve doğru kaydedilmesi gerekir. Hiçbir yazılım, fiziksel sayımın veya doğru veri girişinin yerini tek başına tutmaz.</div>
      </section>

      <section id="hangi-stoklar" aria-labelledby="stock-types">
        <h2 id="stock-types">Malzeme ve hazır ürün stokları neden ayrı takip edilir?</h2>
        <p>Üretim yapan bir işletmenin stoğu yalnızca müşteriye gönderilmeye hazır üründen oluşmaz. Kumaş, astar, aksesuar gibi üretim malzemeleri ile bitmiş ürünler farklı operasyonel sorulara cevap verir. Bir malzemenin depoda bulunması, o üründen sevke hazır adet olduğu anlamına gelmez.</p>
        <div class="guide-benefits">
          <div><span>01 / MALZEME</span><h3>Üretimde kullanılan malzemeler</h3><p>Hangi depoda hangi malzemeden ne kadar bulunduğunu ve son hareketlerini kontrol edin. Üretim başlamadan önce eksikleri araştırın.</p></div>
          <div><span>02 / HAZIR ÜRÜN</span><h3>Depodaki tamamlanmış ürünler</h3><p>Ürün koduna göre mevcut adetleri ayrı görün. Sipariş hazırlarken sistem kaydını fiziksel stokla karşılaştırın.</p></div>
        </div>
        <p>Eylus'un depo yapısında malzeme stokları ile ürün stokları ayrı kayıtlarda tutulur. Yetkili kullanıcılar depo detayında her iki grubu inceleyebilir. Bu yaklaşım, depodaki bir ürünün adediyle üretimde kullanılacak bir malzemenin miktarını birbirine karıştırmamaya yardımcı olur.</p>
      </section>

      <section id="stok-hareketleri" aria-labelledby="stock-moves">
        <h2 id="stock-moves">Stok giriş, çıkış, iade ve sayım hareketleri nasıl kaydedilir?</h2>
        <p>Bir stok takip sisteminde en önemli konu, sayının kendisinden çok o sayıyı değiştiren hareketlerdir. Depoya yeni bir ürün geldiğinde giriş, depodan ürün ayrıldığında çıkış kaydı oluşturulur. İade ve sayım düzeltmesi gibi işlemler de normal hareketlerden ayrı değerlendirilmelidir.</p>
        <ol class="guide-steps">
          <li><strong>Depoyu belirleyin.</strong><p>İşlem hangi depoda gerçekleştiyse o depoyu seçin. Böylece aynı ürünün farklı depolardaki miktarları birbirine karışmaz.</p></li>
          <li><strong>Ürün veya malzemeyi bulun.</strong><p>Ürün kodu, malzeme kodu veya adıyla doğru kayda ulaşın. Yanlış kart seçimi stok farklarına neden olabilir.</p></li>
          <li><strong>Hareket türünü ve miktarı girin.</strong><p>Giriş, çıkış, iade veya sayım düzeltmesi işlemini gerçek hareketle eşleştirin. Gerekiyorsa açıklama ekleyin.</p></li>
          <li><strong>Son durumu karşılaştırın.</strong><p>İşlemden önceki miktar ile sonraki miktarı inceleyin. Fiziksel sayım farklı sonuç veriyorsa nedeni araştırın.</p></li>
        </ol>
        <p>Eylus'un stok kayıtlarında ürün ve malzeme hareketleri ilgili depoyla ilişkilendirilir. Program, miktarın eksiye düşmesini engelleyen kontroller de uygular. Bu kontrol yanlış kaydı tamamen önlemez; ancak geçersiz stok miktarlarının oluşmasına karşı yararlı bir sınırdır.</p>
      </section>

      <section id="depo-yonetimi" aria-labelledby="stock-warehouse">
        <h2 id="stock-warehouse">Birden fazla depoda stok yönetimi nasıl yapılır?</h2>
        <p>Toplam stok miktarı tek başına yeterli olmayabilir. Ürünün hangi depoda bulunduğu, son giriş veya çıkışın nerede kaydedildiği ve ihtiyaç duyulan malzemenin hangi depodan alınacağı da önemlidir. Bu nedenle çok depolu işletmelerde miktarın depo bazında görülebilmesi gerekir.</p>
        <p>Eylus'taki <strong>Depolar</strong> ekranında aktif depolar listelenir. Depo detaylarında mevcut ürün ve malzeme stokları ayrı incelenebilir. İlgili kayıt, ürün kodu veya malzeme bilgisiyle aranabilir. Böylece kontrol edilmesi gereken stok için doğru depoya yönelmek kolaylaşır.</p>
        <p>Program seçerken depo bazlı görünüm ile depolar arası otomatik transfer özelliğini aynı şey sanmamak gerekir. Her işletmenin ihtiyaç duyduğu hareketler ve onay kuralları farklıdır. Kullanacağınız iş akışını gerçek bir senaryoyla değerlendirmek daha doğrudur.</p>
      </section>

      <section id="konsinye-stok" aria-labelledby="stock-consignment">
        <h2 id="stock-consignment">Konsinye stok takibi ne işe yarar?</h2>
        <p>Konsinye verilen ürünler işletmenin kendi deposunda bulunmasa bile müşteri ve ürün bazında izlenmesi gereken kayıtlardır. Hangi müşteriye hangi ürünün gönderildiği, kalan miktar ve sonradan gerçekleşen hareketler takip edilmediğinde eldeki stokla müşterideki stok karışabilir.</p>
        <p>Özellikle toptan tekstil satışında model, renk ve beden ayrıntıları önemlidir. Eylus'un <strong>Konsinye Ürünler</strong> bölümünde müşteriyle ilişkilendirilmiş ürünler, kaynak sipariş ve kalan adet bilgisi izlenebilir. İlgili yetkiye sahip kişiler hareket geçmişini de inceleyebilir.</p>
        <p>Konsinye ile normal depo stoklarını ayrı düşünmek, satış ve yeni sipariş planlamasında daha sağlıklı kararlar alınmasına yardımcı olur. Her iki kayıt da güncel tutulduğunda, stok hakkında farklı kişilerin farklı sayılar söylemesi ihtimali azalır.</p>
      </section>

      <section id="stok-ve-uretim" aria-labelledby="stock-production-difference">
        <h2 id="stock-production-difference">Stok takip programı ile üretim takip programı arasındaki fark</h2>
        <p><strong>Stok takip programı</strong> ağırlıklı olarak “Hangi depoda kaç adet var, ne girip çıktı?” sorularını yanıtlar. <strong>Üretim takip programı</strong> ise “Hangi sipariş kesimde, hangisi dikimde, ne zaman sevk edilecek?” gibi üretim aşamalarını görünür kılar. Stok miktarı ile üretim aşaması aynı bilgi değildir.</p>
        <p>Bir sipariş üretimde ilerliyor olabilir ama henüz hazır ürün stoğuna girmemiştir. Depoda ürün bulunması da o ürüne ilişkin her siparişin tamamlandığı anlamına gelmez. Bu iki süreci birlikte değerlendiren işletmeler, stok ve teslimat kararlarını daha az varsayımla alabilir.</p>
        <p>İlgileniyorsanız <a href="/uretim-takip-programi/">üretim takip programı rehberinde</a> siparişten sevkiyata aşama takibini anlatıyoruz. Eylus'ta QR ile üretim hareketi kaydı ayrı bir süreçtir; depo giriş ve çıkışlarının tümünün otomatik olarak QR okutmayla yapıldığı varsayılmamalıdır.</p>
      </section>

      <section id="stok-programi-secimi" aria-labelledby="stock-choice">
        <h2 id="stock-choice">Stok takip yazılımı seçerken nelere bakmalı?</h2>
        <p>Bir işletmede işlevsel olan program, başka bir işletmenin gereksinimlerini karşılamayabilir. Karar vermeden önce gerçek depo akışınızı düşünün ve aşağıdaki soruların karşılığını ürün üzerinde inceleyin.</p>
        <ul class="guide-checklist">
          <li><strong>Depo bazlı kayıt:</strong> Ürün ve malzeme miktarları her depo için ayrı gösteriliyor mu?</li>
          <li><strong>Hareket geçmişi:</strong> Giriş, çıkış, iade ve sayım düzeltmelerini ayrı inceleyebiliyor musunuz?</li>
          <li><strong>Malzeme ve ürün ayrımı:</strong> Üretim malzemelerini tamamlanmış ürünlerden ayrı takip edebiliyor musunuz?</li>
          <li><strong>Konsinye ürünler:</strong> Müşteriye bırakılan ürünler ve kalan adetleri görülebiliyor mu?</li>
          <li><strong>Yetkilendirme:</strong> Her kullanıcı yalnızca göreviyle ilgili stok işlemlerine mi erişiyor?</li>
          <li><strong>Sipariş ve üretim ilişkisi:</strong> Stok kayıtlarını üretim ve sevkiyat süreçleriyle birlikte değerlendirebiliyor musunuz?</li>
        </ul>
        <p>Programı değerlendirirken belirli bir ürünün hangi depoda bulunduğunu arayın; ardından bir giriş ve çıkış hareketinin nasıl kaydedildiğini inceleyin. Konsinye işlem yapıyorsanız müşteride kalan ürünleri de kontrol edin. Böylece bir özellik listesi yerine kendi işletmenize uygunluğu test etmiş olursunuz.</p>
      </section>

      <section id="stok-sik-sorulanlar" aria-labelledby="stock-faq">
        <h2 id="stock-faq">Sık sorulan sorular</h2>
        <h3>Excel ile stok takibi yapmak yeterli değil mi?</h3>
        <p>Az sayıda ürün ve seyrek hareket için Excel yeterli olabilir. Çok depolu, çok kullanıcılı işletmelerde hareket geçmişi, yetki ve güncel miktar kontrolü zorlaşabilir. Bir stok programı bilgileri aynı kayıt düzeninde tutmaya yardımcı olur.</p>
        <h3>Stok takip programı fiziksel sayım ihtiyacını ortadan kaldırır mı?</h3>
        <p>Hayır. Fiziksel sayım, hatalı girişleri ve kayıt dışı hareketleri fark etmek için gereklidir. Program sayım farklarının daha düzenli incelenmesini sağlar.</p>
        <h3>Stok takip sisteminde QR kod kullanmak zorunlu mu?</h3>
        <p>Hayır. Bu, kullanılan programın iş akışına bağlıdır. Eylus'ta QR kod temel olarak üretim aşaması hareketlerinde kullanılır; depo stokları ayrıca kendi stok ekranlarında takip edilir.</p>
      </section>

      <section class="guide-last" aria-labelledby="stock-cta">
        <span class="guide-kicker">EYLUS İLE TANIŞIN</span>
        <h2 id="stock-cta">Stok ve üretim süreçlerinizi birlikte değerlendirin.</h2>
        <p>Depolar, konsinye ürünler, siparişler ve üretim takibine yönelik Eylus çözümlerini inceleyin. İşletmenizin ihtiyaçlarını birlikte konuşalım.</p>
        <div class="guide-last-actions">
          <a href="/tekstil/" class="guide-button-primary">Eylus çözümlerini görün <span aria-hidden="true">↗</span></a>
          <a href="/demo/" class="guide-button-secondary">Canlı demoyu inceleyin <span aria-hidden="true">→</span></a>
        </div>
      </section>
    </div>
  </div>
</article>
'''


# A focused search landing page for manufacturing order management, distinct
# from stock quantity management and production-stage tracking.
ORDER_ARTICLE_URL = '/siparis-takip-programi/'
ORDER_GUIDE = '''
<article class="guide-page">
  <header class="guide-header">
    <div class="wrap guide-header-inner">
      <nav class="guide-breadcrumb" aria-label="İçerik yolu"><a href="/">Ana sayfa</a><span aria-hidden="true">/</span><span>Sipariş takip programı</span></nav>
      <span class="guide-kicker">EYLUS REHBER · SİPARİŞ YÖNETİMİ</span>
      <h1>Sipariş Takip Programı Nedir? <em>Üretim Siparişlerini ve Teslim Tarihlerini Nasıl Yönetirsiniz?</em></h1>
      <p class="guide-deck">Hangi müşterinin hangi siparişi hazırlanıyor? Ürün kesimde mi, dikimde mi? Teslim tarihine kaç gün kaldı? Sipariş takip programı, üretici işletmelerin bu soruları tek bir kayıt üzerinden yanıtlamasına yardımcı olur.</p>
      <div class="guide-header-actions">
        <a href="#siparis-takip-nedir">Rehberi okuyun <span aria-hidden="true">↓</span></a>
        <a href="/tekstil/">Eylus çözümlerini inceleyin <span aria-hidden="true">↗</span></a>
      </div>
    </div>
  </header>
  <div class="wrap guide-body">
    <aside class="guide-side" aria-label="Yazı içeriği">
      <p>BU YAZIDA</p>
      <a href="#siparis-takip-nedir">Sipariş takip programı nedir?</a>
      <a href="#siparis-kaydi">Sipariş kaydında gerekli bilgiler</a>
      <a href="#siparis-durumlari">Üretim aşamaları nasıl izlenir?</a>
      <a href="#teslim-tarihi">Teslim tarihi ve sevkiyat</a>
      <a href="#siparis-foyu">Sipariş föyüyle çalışma</a>
      <a href="#musteri-rapor">Müşteri ve raporlar</a>
      <a href="#program-secerken">Program seçimi</a>
      <a href="#siparis-sorular">Sık sorulan sorular</a>
    </aside>
    <div class="guide-copy">
      <section id="siparis-takip-nedir" aria-labelledby="order-what">
        <h2 id="order-what">Sipariş takip programı nedir?</h2>
        <p><strong>Sipariş takip programı</strong>, müşteriden gelen siparişlerin ürün bilgilerini, miktarlarını, hazırlanma durumlarını ve teslim tarihlerini aynı sistemde tutan yazılımdır. Bir siparişin alınmasından tamamlanıp sevk edilmesine kadar geçen süreçte hangi işlemin yapıldığını ve sıradaki adımın ne olduğunu görmeyi kolaylaştırır.</p>
        <p>Örneğin toptan tekstil üretiminde aynı modelin farklı renk ve bedenleri birden fazla müşteriye hazırlanabilir. Sipariş bilgileri deftere, mesajlaşma uygulamasına ve farklı Excel dosyalarına dağılırsa bir değişikliğin herkese zamanında ulaşması zorlaşır. Ortak sipariş kaydı, ekiplerin aynı bilgiden hareket etmesine yardımcı olur.</p>
        <div class="guide-note"><strong>Önemli ayrım:</strong> İnternetten alışveriş yapan kişinin kargo numarasıyla paket sorgulaması, üretici firmanın sipariş yönetiminden farklıdır. Bu rehber, <strong>sipariş alıp üretim yapan işletmelerin</strong> iç süreçlerini ele alır.</div>
      </section>

      <section id="siparis-kaydi" aria-labelledby="order-fields">
        <h2 id="order-fields">Sipariş kaydında hangi bilgiler bulunmalı?</h2>
        <p>Bir siparişi yalnızca müşteri adı ve toplam adetle tanımlamak çoğu zaman yeterli değildir. Özellikle farklı model, renk ve beden seçenekleriyle çalışan atölyelerde küçük bir bilgi eksikliği yanlış üretime veya hatalı teslimata neden olabilir.</p>
        <div class="guide-benefits">
          <div><span>01 / MÜŞTERİ</span><h3>Kim için üretiliyor?</h3><p>Müşteri kaydı ve gerekiyorsa müşterinin kullandığı referans numarası, siparişin doğru kişi veya mağazayla eşleşmesini sağlar.</p></div>
          <div><span>02 / ÜRÜN</span><h3>Ne üretilecek?</h3><p>Ürün kodu, renk, beden ve adet bilgileri, hangi modelden kaç parça hazırlanacağını açıkça tanımlar.</p></div>
          <div><span>03 / TARİH</span><h3>Ne zaman teslim edilecek?</h3><p>Planlanan teslim tarihi işlerin önceliklendirilmesine ve sevkiyat hazırlığının zamanında yapılmasına yardımcı olur.</p></div>
          <div><span>04 / AÇIKLAMA</span><h3>Özel bir talep var mı?</h3><p>İlgili notlar ve sipariş türü gibi ayrıntılar, üretime aktarılacak bilgilerin netleşmesini sağlar.</p></div>
        </div>
        <p>Eylus'ta siparişler müşteri, ürün kodu, renk, beden, adet, teslim tarihi ve açıklama gibi bilgilerle tutulabilir. Siparişlerin birbirinden ayrılması için sistemde kayıtlı sipariş numarası ve sipariş türü gibi alanlar da kullanılır. Bu bilgiler, bir siparişi açtığınızda ilgili üretim süreciyle birlikte değerlendirilebilir.</p>
      </section>

      <section id="siparis-durumlari" aria-labelledby="order-stages">
        <h2 id="order-stages">Sipariş üretimde hangi aşamada, nasıl öğrenilir?</h2>
        <p>Siparişin sisteme girilmesi başlangıçtır; üretim devam ederken aynı kaydın güncel tutulması gerekir. İşin kesimde, dikimde, süslemede veya sevke hazır durumda olduğunu görebilmek, yöneticiye telefonla bilgi toplamak yerine kayıt üzerinden ilerleme imkânı verir.</p>
        <ol class="guide-steps">
          <li><strong>Siparişi oluşturun.</strong><p>Müşteri ve ürün ayrıntılarını kaydedin. Teslim tarihini, üretim önceliği belirlemek için baştan görünür hale getirin.</p></li>
          <li><strong>Üretime aktarın.</strong><p>İşlem sırasındaki değişiklikleri ilgili siparişle ilişkilendirin. Aynı ürünün farklı siparişlerini birbirine karıştırmayın.</p></li>
          <li><strong>Aşamaları kaydedin.</strong><p>Kesim, dikim, süsleme ve hazır gibi aşamalarda yapılan hareketleri ürünün kaydına işleyin. Bilgilerin düzenli girilmesini sağlayın.</p></li>
          <li><strong>Gecikme riskini kontrol edin.</strong><p>İlerlemesi durmuş işleri, eksik hareket kayıtlarını ve yaklaşan teslimatları birlikte inceleyin.</p></li>
          <li><strong>Sevkiyat durumunu izleyin.</strong><p>Hazır ürünleri ve sevkiyat planını kontrol ederek müşteriye neyin hangi gün gönderileceğini değerlendirin.</p></li>
        </ol>
        <p>Eylus'ta personel ürünün QR kodunu okutarak üretim işlemlerini kaydedebilir. Yönetici, sipariş listesi ve aşama kontrol ekranlarında bu kayıtların son durumunu inceleyebilir. QR kod tek başına fiziksel işi yapmaz; doğru ve zamanında işlem kaydı gereklidir.</p>
        <p>Bu konunun ayrıntılarını <a href="/uretim-takip-programi/">üretim takip programı rehberimizde</a> de bulabilirsiniz.</p>
      </section>

      <section id="teslim-tarihi" aria-labelledby="order-delivery">
        <h2 id="order-delivery">Teslim tarihi yaklaşan siparişler nasıl takip edilir?</h2>
        <p>Bir siparişin gecikmesini yalnızca teslim günü öğrenmek, müdahale seçeneklerini azaltır. Önemli olan, sipariş henüz üretimdeyken teslim tarihiyle mevcut aşamasını karşılaştırabilmektir. Böylece hazır olmayan ürünleri önceden tespit etmek ve işlerin sırasını gözden geçirmek mümkün olur.</p>
        <p>Eylus'un sevkiyat planı, yaklaşan teslimatların bir arada görülmesine yardımcı olur. Siparişin teslim tarihi ile üretimde bulunduğu aşamayı birlikte değerlendiren yönetici, hangi işleri öncelikle kontrol etmesi gerektiğini belirleyebilir.</p>
        <p>Burada otomatik olarak her gecikmenin önleneceğini söylemek doğru olmaz. Malzeme eksikliği, üretim kapasitesi veya müşteri değişiklikleri yine operasyonel karar gerektirir. Sipariş takip yazılımının katkısı, sorunların fark edilmesini kolaylaştıracak bilgiyi erişilebilir kılmasıdır.</p>
      </section>

      <section id="siparis-foyu" aria-labelledby="order-sheet">
        <h2 id="order-sheet">Sipariş föyü ile sipariş takibi birlikte nasıl çalışır?</h2>
        <p>Üretici firmalarda müşteriden gelen sipariş bazen bir föy, tablo veya belge üzerinden iletilir. Belgede yazan bilgilerin üretim sistemine eksik veya yanlış aktarılması, sonraki tüm aşamaları etkileyebilir. Bu yüzden siparişin sisteme alınmadan önce kontrol edilmesi önemlidir.</p>
        <p>Eylus'un sipariş föyü iş akışında taslak ve onaylı kayıtlar ayrı değerlendirilebilir. Sipariş föyünden alınan müşteri, ürün kodu, renk, beden, adet ve teslim tarihi gibi bilgiler kontrol edildikten sonra sipariş oluşturma sürecine aktarılabilir. Böylece belgedeki talep ile üretime giren sipariş arasında bir kontrol adımı bulunur.</p>
        <p>Bu yaklaşım özellikle çok satırlı siparişlerde yararlıdır. Aynı model için farklı renk ve bedenler istendiğinde her satırın doğru ürünle eşleşmesi gerekir. Belge aktarımı otomatik yapılıyor olsa da insan kontrolünün tamamen gereksiz hale geldiği varsayılmamalıdır.</p>
      </section>

      <section id="musteri-rapor" aria-labelledby="order-reports">
        <h2 id="order-reports">Müşteri bazlı sipariş takibi ve raporlar</h2>
        <p>İşletme sahibi yalnızca bugün üretimde kaç sipariş olduğunu değil, belirli bir müşterinin hangi siparişlerinin hazırlandığını da görmek isteyebilir. Tek bir müşteri için farklı model ve teslim tarihleri söz konusu olduğunda listeleme ve filtreleme önem kazanır.</p>
        <p>Eylus'un sipariş listesi ve rapor ekranları, kayıtları müşteri ve ürün bilgileriyle birlikte incelemeye yardımcı olur. Siparişin üretim aşamasını ve sevkiyat durumunu aynı yönetim sürecinde değerlendirmek, birbirinden ayrı listelerin yarattığı karışıklığı azaltabilir.</p>
        <p>Satış fiyatı, maliyet ve fatura gibi finansal bilgiler ayrı kontrol konularıdır. Sipariş takibi, tüm muhasebe işlemlerinin otomatik ve hatasız yapıldığı anlamına gelmez; ancak ilgili siparişin kayıtlı olması, bu işlemler arasında düzen kurulmasına yardımcı olur.</p>
      </section>

      <section id="program-secerken" aria-labelledby="order-checklist">
        <h2 id="order-checklist">Sipariş takip programı seçerken nelere dikkat edilmeli?</h2>
        <p>Yazılım seçerken farklı özellik başlıklarından önce günlük iş akışınıza bakın. Bir müşterinin siparişini açıp üretimden sevkiyata kadar kendi senaryonuzla denemek, özellik listesini okumaktan daha anlamlı sonuç verir.</p>
        <ul class="guide-checklist">
          <li><strong>Ürün ayrıntıları:</strong> Model, renk, beden, adet ve teslim tarihi aynı kayıtta tutuluyor mu?</li>
          <li><strong>Üretimle ilişki:</strong> Siparişin kesim, dikim, süsleme ve hazır aşamaları görülebiliyor mu?</li>
          <li><strong>Gecikme kontrolü:</strong> Hareket etmeyen işler ve yaklaşan teslimatlar kolayca bulunabiliyor mu?</li>
          <li><strong>Personel kullanım kolaylığı:</strong> Çalışanların hareket kaydetmesi hızlı ve anlaşılır mı?</li>
          <li><strong>Belge kontrolü:</strong> Sipariş föyüyle çalışılıyorsa bilgilerin kontrol edilerek aktarılması mümkün mü?</li>
          <li><strong>Sevkiyat ve raporlama:</strong> Hazır işler, planlanan teslimatlar ve müşteri bazlı siparişler incelenebiliyor mu?</li>
          <li><strong>Mobil erişim:</strong> Yetkili kullanıcılar ofis dışında da siparişlerin son durumuna ulaşabiliyor mu?</li>
        </ul>
        <p>Tekstil üretimiyle çalışıyorsanız aynı modelin birden fazla renk ve bedenle sipariş edilmesini örnek alın. Siparişi oluşturun, üretim hareketi kaydedin ve sevkiyat planında nasıl göründüğüne bakın. İşletmenize uygunluğu değerlendirmek için <a href="/demo/">Eylus canlı demosunu</a> inceleyebilirsiniz.</p>
      </section>

      <section id="siparis-sorular" aria-labelledby="order-faq">
        <h2 id="order-faq">Sık sorulan sorular</h2>
        <h3>Sipariş takip programı ile kargo takip sistemi aynı mı?</h3>
        <p>Hayır. Kargo takibi gönderilmiş bir paketin taşıma durumuna odaklanır. Üretim odaklı sipariş takibi ise müşterinin talebinin alınması, üretimde ilerlemesi, hazırlanması ve sevkiyata planlanmasıyla ilgilenir.</p>
        <h3>Sipariş takip programı Excel yerine kullanılabilir mi?</h3>
        <p>Excel az sayıda sipariş için iş görebilir. Ancak aynı anda çok sayıda müşteri, model, renk, beden ve üretim hareketi takip edildiğinde ortak kayıtların güncel tutulması zorlaşabilir. Sipariş yazılımı bu bilgileri aynı iş akışında birleştirebilir.</p>
        <h3>Sipariş takip sisteminde QR kod zorunlu mudur?</h3>
        <p>Her sipariş takip sisteminde QR kod kullanmak zorunlu değildir. Eylus'ta QR kod, personelin üretim aşaması hareketlerini sipariş kaydına bağlayarak kaydetmesini kolaylaştırır.</p>
        <h3>Sipariş takibi ile stok takibi arasındaki fark nedir?</h3>
        <p>Sipariş takibi müşterinin istediği ürünlerin hazırlık ve teslim süreçlerini, stok takibi ise depolardaki mevcut ürün veya malzeme miktarlarını inceler. Stok konusu için <a href="/stok-takip-programi/">stok takip programı rehberimizi</a> okuyabilirsiniz.</p>
      </section>

      <section class="guide-last" aria-labelledby="order-cta">
        <span class="guide-kicker">EYLUS İLE TANIŞIN</span>
        <h2 id="order-cta">Siparişin nerede olduğunu sormak yerine görün.</h2>
        <p>Sipariş kaydından üretim aşamalarına ve sevkiyat planına kadar Eylus'un iş akışını inceleyin; işletmenize uygunluğu kendi üretim düzeniniz üzerinden değerlendirin.</p>
        <div class="guide-last-actions">
          <a href="/tekstil/" class="guide-button-primary">Eylus çözümlerini görün <span aria-hidden="true">↗</span></a>
          <a href="/demo/" class="guide-button-secondary">Canlı demoyu inceleyin <span aria-hidden="true">→</span></a>
        </div>
      </section>
    </div>
  </div>
</article>
'''


# Personnel management article: public SEO content anchored in genuine product functions.
PERSONNEL_ARTICLE_URL = '/personel-takip-programi/'
PERSONNEL_GUIDE = '''
<article class="guide-page">
  <header class="guide-header">
    <div class="wrap guide-header-inner">
      <nav class="guide-breadcrumb" aria-label="İçerik yolu"><a href="/">Ana sayfa</a><span aria-hidden="true">/</span><span>Personel takip programı</span></nav>
      <span class="guide-kicker">EYLUS REHBER · PERSONEL VE PUANTAJ</span>
      <h1>Personel Takip Programı Nedir? <em>Puantaj, Mesai ve Üretim Ekibini Nasıl Yönetirsiniz?</em></h1>
      <p class="guide-deck">Bugün kim çalışıyor? Kim giriş veya çıkış kaydını eksik bıraktı? Fazla mesai ne kadar? Üretimde hangi işlemi kim kaydetti? Personel takip programı, bu sorulara kayıt üzerinden cevap arayan işletmeler için tasarlanır.</p>
      <div class="guide-header-actions">
        <a href="#personel-takip-nedir">Rehberi okuyun <span aria-hidden="true">↓</span></a>
        <a href="/tekstil/">Eylus çözümlerini inceleyin <span aria-hidden="true">↗</span></a>
      </div>
    </div>
  </header>
  <div class="wrap guide-body">
    <aside class="guide-side" aria-label="Yazı içeriği">
      <p>BU YAZIDA</p>
      <a href="#personel-takip-nedir">Personel takip programı nedir?</a>
      <a href="#personel-puantaj">Puantaj ve giriş-çıkış</a>
      <a href="#personel-mesai">Geç kalma ve fazla mesai</a>
      <a href="#personel-qr">QR ve cihaz kayıtları</a>
      <a href="#personel-uretim">Üretim aşaması sorumluluğu</a>
      <a href="#personel-izin">İzin ve personel kayıtları</a>
      <a href="#personel-maas">Maaş ve puantaj farkı</a>
      <a href="#personel-secimi">Program seçim kriterleri</a>
      <a href="#personel-sorular">Sık sorulan sorular</a>
    </aside>
    <div class="guide-copy">
      <section id="personel-takip-nedir" aria-labelledby="personnel-intro">
        <h2 id="personnel-intro">Personel takip programı nedir?</h2>
        <p><strong>Personel takip programı</strong>, çalışanların iş günü kayıtlarını, çalışma saatlerini, izin durumlarını ve yetkilerini düzenli biçimde yönetmeye yardımcı olan yazılımdır. Üretim işletmelerinde personelin hangi görevde çalıştığı ve iş akışına hangi hareketleri kaydettiği de önemli olabilir.</p>
        <p>Bir atölyede kesim, dikim, süsleme ve sevkiyat ekiplerinin farklı sorumlulukları bulunur. İşletme sahibi personelin her gün hangi saatte işe başladığını öğrenmek için ayrı listelere bakıyor, üretim hareketlerini de çalışanlardan sözlü olarak topluyorsa zaman kaybeder. Kayıtların ortak bir sistemde bulunması, günlük kontrolü kolaylaştırır.</p>
        <div class="guide-note"><strong>Kısaca:</strong> Personel takibi yalnızca çalışan adlarının listelendiği bir tablo değildir. Puantaj, izin, fazla mesai ve görev yetkilerinin tutarlı biçimde izlenmesini de kapsar.</div>
      </section>

      <section id="personel-puantaj" aria-labelledby="personnel-attendance">
        <h2 id="personnel-attendance">Dijital puantaj ve personel giriş-çıkış takibi</h2>
        <p>Puantaj, personelin belirli bir iş günündeki çalışma durumunu kayıt altına alır. Giriş ve çıkış saatleri, izinli veya raporlu olunan günler ve eksik kayıtlar bu sürecin parçalarıdır. Dijital puantajda kayıtlar tek bir tabloda tutulabildiği için geçmiş günleri incelemek ve ay sonu kontrolü yapmak kolaylaşır.</p>
        <p>Eylus'un puantaj yapısında personel bazında günlük giriş ve çıkış kayıtları bulunur. Yöneticiler, yetkileri kapsamında ilgili tarihlerin kayıtlarını inceleyebilir. Personelin giriş yapıp çıkış yapmayı unuttuğu durumlar da ayrıca değerlendirilmesi gereken kayıtlar olarak işaretlenebilir.</p>
        <p>Bununla birlikte dijital bir zaman kaydı, çalışanın o saatler boyunca fiilen hangi işi yaptığını tek başına ispatlamaz. Puantaj bilgisi, gerektiğinde yöneticinin incelemesi ve işletmenin çalışma kurallarıyla birlikte değerlendirilmelidir.</p>
      </section>

      <section id="personel-mesai" aria-labelledby="personnel-overtime">
        <h2 id="personnel-overtime">Geç kalma, erken çıkış ve fazla mesai nasıl izlenir?</h2>
        <p>Çalışanın giriş ve çıkış saatleri tek başına yeterli olmayabilir. İşletmenin çalışma saatlerine göre geç kalma, erken ayrılma veya fazla mesai gibi durumların da değerlendirilmesi gerekir. Bu hesapların nasıl yapıldığı işletmenin kurallarına ve ilgili mevzuata bağlıdır.</p>
        <ol class="guide-steps">
          <li><strong>Giriş ve çıkış saatlerini kaydedin.</strong><p>Personelin o gün için oluşturduğu zaman kayıtlarını ilgili kişiyle ve tarihle ilişkilendirin.</p></li>
          <li><strong>İşyeri çalışma düzenini tanımlayın.</strong><p>Giriş ve çıkış zamanlarını kurumun kullandığı normal çalışma saatleriyle karşılaştırın.</p></li>
          <li><strong>İstisnaları inceleyin.</strong><p>Eksik çıkış kaydı, izinli gün veya olağan dışı süre gibi durumları ay sonundan önce kontrol edin.</p></li>
          <li><strong>Raporları gözden geçirin.</strong><p>Geç kalma, erken çıkış ve mesai sürelerini kişi ve dönem bazında değerlendirip gerekli düzeltmeleri yapın.</p></li>
        </ol>
        <p>Eylus'ta personelin günlük kayıtları üzerinden geç kalma, erken çıkış ve fazla mesai sürelerinin hesaplanmasına yönelik alanlar bulunur. Kayıtların doğru yorumlanması için mesai kuralları, izin türleri ve eksik veriler ayrıca kontrol edilmelidir. Programın hesapladığı süre, tek başına hukuki ücret veya hak ediş kararı anlamına gelmez.</p>
      </section>

      <section id="personel-qr" aria-labelledby="personnel-qr">
        <h2 id="personnel-qr">QR kod ve onaylı cihazla personel takibi</h2>
        <p>Kâğıt puantaj çizelgesinde çalışanların giriş ve çıkışlarını sonradan toplamak zaman alabilir. Mobil bir kayıt ekranı, yetkili personelin gerekli bilgileri kendisi girmesini kolaylaştırabilir. Bunun güvenilir olabilmesi için kimlik, cihaz ve gerektiğinde işyeri konumu gibi kontrollerin süreçle birlikte tasarlanması önemlidir.</p>
        <p>Eylus'un puantaj iş akışında işyerine ait QR doğrulaması, cihaz onayı ve konumla ilgili kontroller bulunur. Bu kontroller, kayıtların işyeri kuralları çerçevesinde oluşturulmasına yardımcı olur. Ancak telefonun konum doğruluğu veya bağlantı koşulları değişebileceğinden, sorunlu kayıtları inceleme yolu da bulunmalıdır.</p>
        <p>Burada iki farklı QR kullanımı olduğunu unutmamak gerekir: <strong>personel puantajı</strong> giriş-çıkış kaydına, <strong>üretim QR işlemleri</strong> ise siparişin kesim, dikim veya süsleme aşamalarına ilişkindir. Bir işlem kaydı, diğerinin otomatik olarak yapıldığı anlamına gelmez.</p>
      </section>

      <section id="personel-uretim" aria-labelledby="personnel-production">
        <h2 id="personnel-production">Üretim atölyelerinde personel bazlı iş takibi</h2>
        <p>Üretim yapan işletmeler için çalışanların yalnızca saatlerini bilmek yeterli değildir. Siparişin hangi aşamada olduğunu ve bu aşamaya ilişkin kaydı kimin oluşturduğunu görmek de iş akışı kontrolü açısından önemlidir.</p>
        <p>Eylus'ta kesim, dikim, süsleme, hazır ve sevkiyat gibi üretim görevleri tanımlanabilir. Ürüne ait QR işlemleri siparişle ilişkilendirilerek kaydedilir. Yetkili yöneticiler, aşama hareketleriyle personel kayıtlarını birlikte inceleyebilir; eksik veya uyumsuz görünen hareketleri araştırabilir.</p>
        <p>Bir işlemi sisteme kaydeden kişinin belirlenmesi, her üretim hatasının kesin olarak o kişiden kaynaklandığını göstermez. Doğru yaklaşım, olay kaydını sorumluluk incelemesi için başlangıç noktası olarak kullanmaktır. <a href="/uretim-takip-programi/">Üretim takip programı rehberimizde</a> bu aşamaları daha ayrıntılı anlattık.</p>
      </section>

      <section id="personel-izin" aria-labelledby="personnel-leave">
        <h2 id="personnel-leave">İzin, rapor ve personel özlük kayıtları</h2>
        <p>Bir çalışanın belirli bir gün neden giriş kaydı bulunmadığını anlamak için izin ve rapor bilgisi önem taşır. Puantajda çalışılan günlerle izinli veya raporlu günlerin ayrılması, eksik kayıtların yanlış yorumlanmasını önlemeye yardımcı olur.</p>
        <p>Eylus'un personel ve puantaj altyapısında günlük çalışma durumu için izinli, yıllık izin ve raporlu gibi kayıt türleri vardır. Personel profilinde işe başlama ve işten ayrılma tarihi gibi özlük alanları da tutulabilir. Bu bilgiler, yetkili kişilerin yönetim süreçlerinde kullanılmak üzere düzenlenmiştir.</p>
        <p>Personel verileri kişisel veri niteliği taşıyabilir. Bu nedenle işletme, hangi bilgiyi hangi amaçla tuttuğunu belirlemeli; yalnızca yetkili kişilere erişim vermeli ve yürürlükteki kişisel veri koruma yükümlülüklerini dikkate almalıdır.</p>
      </section>

      <section id="personel-maas" aria-labelledby="personnel-payroll">
        <h2 id="personnel-payroll">Personel takip programı ile maaş yönetimi aynı mı?</h2>
        <p>Hayır. Puantaj ve mesai takibi çalışılan zaman ve devam durumunu ele alırken maaş yönetimi ücret tanımlarını, ödeme planlarını ve ödemeleri inceler. İlişkili olsalar da aynı işlem değildirler; puantaj kaydını görmek, maaşın kendiliğinden ve eksiksiz ödendiği anlamına gelmez.</p>
        <p>Eylus'ta puantajdan ayrı bir maaş yönetimi bölümü bulunur. Yetkili kullanıcılar dönem, ücret tanımı, ödeme planı ve ödeme kayıtlarını burada değerlendirebilir. Maaş ekranları personel bilgilerinin hassasiyeti nedeniyle daha sınırlı erişimle ele alınmalıdır.</p>
        <p>Bir yazılım seçerken bordro, SGK bildirimi veya resmî muhasebe entegrasyonu gibi özelliklerin mevcut olduğunu varsaymak yerine her birini ayrıca doğrulayın. Eylus'un personel ve maaş ekranlarını işletmenizin ihtiyaçlarına göre incelemeniz daha sağlıklı olur.</p>
      </section>

      <section id="personel-secimi" aria-labelledby="personnel-checklist">
        <h2 id="personnel-checklist">Personel takip programı seçerken nelere dikkat edilmeli?</h2>
        <p>Bir personel takip sisteminin başarılı olabilmesi için yöneticinin rapor alması kadar çalışanların kaydı kolay yapabilmesi de gerekir. Yazılımı değerlendirirken kendi atölyenizin günlük işleyişinden örneklerle ilerleyin.</p>
        <ul class="guide-checklist">
          <li><strong>Giriş-çıkış kaydı:</strong> Personelin çalışma günleri ve saatleri kolayca incelenebiliyor mu?</li>
          <li><strong>Eksik kayıtlar:</strong> Unutulan çıkış işlemleri ve olağan dışı süreler belirlenebiliyor mu?</li>
          <li><strong>Puantaj ve mesai:</strong> Geç kalma, erken çıkış ve fazla mesai bilgileri ayrı görülebiliyor mu?</li>
          <li><strong>İzin durumları:</strong> İzin, rapor ve çalışma günleri birbirinden ayrılabiliyor mu?</li>
          <li><strong>Yetkilendirme:</strong> Yöneticiler ile personel için uygun erişim sınırları var mı?</li>
          <li><strong>Üretimle ilişki:</strong> Üretim aşaması hareketlerini kaydeden kişi görülebiliyor mu?</li>
          <li><strong>Mobil kullanım:</strong> Çalışanın kayıt işlemi günlük işini gereksiz yere zorlaştırıyor mu?</li>
        </ul>
        <p>Programı denemek için bir personelin tam iş gününü örnek alın: giriş kaydını, çıkış kaydını, gerekiyorsa fazla mesaisini ve o gün üretimde kaydettiği işlemleri inceleyin. Ardından yönetici olarak aynı günün özetini bulmaya çalışın.</p>
      </section>

      <section id="personel-sorular" aria-labelledby="personnel-faq">
        <h2 id="personnel-faq">Sık sorulan sorular</h2>
        <h3>Personel takip programı sadece büyük fabrikalar için mi?</h3>
        <p>Hayır. Küçük ve orta ölçekli atölyelerde de çalışma saatleri, izinler ve üretim aşaması kayıtları yönetilmek zorundadır. Önemli olan kullanılan programın iş yüküne ve ekibin çalışma biçimine uygun olmasıdır.</p>
        <h3>Puantaj programı fazla mesai ücretini otomatik öder mi?</h3>
        <p>Hayır. Puantajda mesai süresi hesaplanması ödeme işleminin yapıldığı anlamına gelmez. Ücret ve ödeme kayıtları ayrı süreçlerde kontrol edilmelidir.</p>
        <h3>QR kodla personel takibi ile üretim takibi aynı şey mi?</h3>
        <p>Hayır. Puantaj QR işlemi personelin işe giriş sürecini doğrulamaya yönelikken üretim QR işlemi ürünün ilgili aşamasındaki kaydı tutar. İki işlem türü farklı amaçlara hizmet eder.</p>
        <h3>Personel takip programı sipariş yönetimiyle birlikte kullanılabilir mi?</h3>
        <p>Evet. Üretim işletmelerinde personel ve sipariş süreçlerinin birlikte değerlendirilmesi faydalıdır. Müşteri siparişlerini nasıl izleyeceğinizi <a href="/siparis-takip-programi/">sipariş takip programı rehberimizde</a> anlattık.</p>
      </section>

      <section class="guide-last" aria-labelledby="personnel-cta">
        <span class="guide-kicker">EYLUS İLE TANIŞIN</span>
        <h2 id="personnel-cta">Personeli, puantajı ve üretimi aynı işletme düzeninde görün.</h2>
        <p>Personel, puantaj, üretim aşamaları ve rapor ekranlarını iş akışınıza göre değerlendirin. Eylus'un işletmeniz için uygun olup olmadığını örnekler üzerinden inceleyin.</p>
        <div class="guide-last-actions">
          <a href="/tekstil/" class="guide-button-primary">Eylus çözümlerini görün <span aria-hidden="true">↗</span></a>
          <a href="/demo/" class="guide-button-secondary">Canlı demoyu inceleyin <span aria-hidden="true">→</span></a>
        </div>
      </section>
    </div>
  </div>
</article>
'''


# Evergreen work tracking SEO guide: separate personal tasks from production operations.
WORK_ARTICLE_URL = '/is-takip-programi/'
WORK_GUIDE = '''
<article class="guide-page">
  <header class="guide-header">
    <div class="wrap guide-header-inner">
      <nav class="guide-breadcrumb" aria-label="İçerik yolu"><a href="/">Ana sayfa</a><span aria-hidden="true">/</span><span>İş takip programı</span></nav>
      <span class="guide-kicker">EYLUS REHBER · İŞ VE OPERASYON TAKİBİ</span>
      <h1>İş Takip Programı Nedir? <em>Yapılacak İşleri ve Üretimdeki Gecikmeleri Nasıl Yönetirsiniz?</em></h1>
      <p class="guide-deck">Bugün hangi iş yapılmalı? Hangi hatırlatma bekliyor? Hangi üretim siparişi günlerdir ilerlemiyor? Bir iş takip programının temel amacı bu soruları farklı mesajlarda aramak yerine düzenli kayıtlardan yanıtlamaktır.</p>
      <div class="guide-header-actions">
        <a href="#is-takip-nedir">Rehberi okuyun <span aria-hidden="true">↓</span></a>
        <a href="/tekstil/">Eylus çözümlerini inceleyin <span aria-hidden="true">↗</span></a>
      </div>
    </div>
  </header>
  <div class="wrap guide-body">
    <aside class="guide-side" aria-label="Yazı içeriği">
      <p>BU YAZIDA</p>
      <a href="#is-takip-nedir">İş takip programı nedir?</a>
      <a href="#yapilacak-isler">Yapılacak işler ve tarihler</a>
      <a href="#hatirlatma-alarm">Hatırlatma ve alarm</a>
      <a href="#uretimde-is-takibi">Üretimde iş ve aşama takibi</a>
      <a href="#geciken-isler">Geciken ve hareketsiz işler</a>
      <a href="#is-ve-siparis">İş ve sipariş takibi farkı</a>
      <a href="#is-takip-secimi">Program seçerken</a>
      <a href="#is-takip-sorular">Sık sorulan sorular</a>
    </aside>
    <div class="guide-copy">
      <section id="is-takip-nedir" aria-labelledby="work-what">
        <h2 id="work-what">İş takip programı nedir?</h2>
        <p><strong>İş takip programı</strong>, yapılması gereken işlerin kaydedilmesine, tarihlerinin izlenmesine ve tamamlanma durumlarının kontrol edilmesine yardımcı olan yazılımdır. Kimi işletme için bir yapılacaklar listesi yeterliyken, üretim yapan firmalarda müşteri siparişleri, üretim aşamaları ve teslimatlar da iş takibinin parçasıdır.</p>
        <p>Örneğin bir atölye yöneticisinin aynı gün malzeme eksiklerini kontrol etmesi, müşteriye dönüş yapması ve yarın sevk edilecek siparişleri gözden geçirmesi gerekebilir. Bunlar farklı türde işlerdir. Hepsini akılda tutmaya çalışmak yerine tek tek kayıt altına almak, öncelikleri belirlemeyi kolaylaştırır.</p>
        <div class="guide-note"><strong>Önemli ayrım:</strong> Kişisel yapılacaklar listesi ile işletme genelindeki üretim takibi aynı işlev değildir. Eylus'ta kişisel iş hatırlatmaları ve siparişlerin üretim aşaması kontrolü farklı ekranlarda ele alınır.</div>
      </section>

      <section id="yapilacak-isler" aria-labelledby="work-todo">
        <h2 id="work-todo">Yapılacak işler nasıl düzenlenir?</h2>
        <p>Günlük işlerin takibinde ilk adım, yapılacak işi herkesin anlayacağı kadar açık tanımlamaktır. “Müşteriye bak” gibi belirsiz bir not yerine “Model 8020 teslim tarihi için müşteriye dönüş yap” gibi somut bir ifade, işin tamamlanıp tamamlanmadığını kontrol etmeyi kolaylaştırır.</p>
        <p>İş kaydı oluştururken bir başlık, gerekiyorsa açıklama ve hedef tarih kullanılabilir. Ardından açık işlerle tamamlanan işlerin ayrılması, aynı konuya tekrar tekrar dönmeyi azaltır. Tarihsiz küçük işler de gerektiğinde listede tutulabilir.</p>
        <div class="guide-benefits">
          <div><span>01 / KAYIT</span><h3>Yapılacaklar listesi</h3><p>Kısa başlık ve açıklamayla unutulmaması gereken işleri ayrı kayıtlara dönüştürün.</p></div>
          <div><span>02 / ÖNCELİK</span><h3>Tarih bazlı görünüm</h3><p>Geciken, bugün yapılacak, yaklaşan ve tarihi olmayan işleri farklı gruplarda değerlendirin.</p></div>
          <div><span>03 / TAKİP</span><h3>Tamamlandı bilgisi</h3><p>Yapılan işleri açık listeden ayırın; hangi kaydın tamamlandığını görün.</p></div>
          <div><span>04 / KONTROL</span><h3>Eksik işleri belirleme</h3><p>Gün sonunda halen açık kalan işleri sonraki çalışma planına dahil edin.</p></div>
        </div>
        <p>Eylus'un <strong>Yapılacaklar</strong> bölümünde kullanıcı kendi işlerini başlık, not ve isteğe bağlı tarih ile kaydedebilir. Liste geciken, bugün, yaklaşan, tarihi olmayan ve tamamlanan işler olarak gruplandırılır. Bu bölüm, her çalışana otomatik iş dağıtan bir ekip proje yönetim sistemi olarak tanıtılmamalıdır; kişisel yapılacakların kaydına odaklanır.</p>
      </section>

      <section id="hatirlatma-alarm" aria-labelledby="work-alarm">
        <h2 id="work-alarm">İş hatırlatmaları ve alarm sistemi ne işe yarar?</h2>
        <p>Bir görevi listeye yazmak her zaman yeterli olmaz. Özellikle gün içinde farklı konularla ilgilenen işletme sahiplerinin, belirli saatte yapılacak işleri hatırlatmaya ihtiyacı olabilir. Tarih ve saatli bir hatırlatma bu amaçla kullanılır.</p>
        <p>Eylus'ta bir yapılacak işe gelecek bir tarih ve saat belirlenerek alarm oluşturulabilir. Alarm aralıkları seçilebilir; kullanıcı bir işi tamamladığında veya uygun bir süre ertelediğinde kayıt buna göre güncellenir. Böylece tamamlanmış bir işin halen yapılacakmış gibi takip edilmesi önlenebilir.</p>
        <p>Bildirimlerin cihaza ulaşması internet bağlantısına, tarayıcı izinlerine ve telefonun bildirim desteğine bağlı olabilir. Bu nedenle önemli işletme kararları için tek bir bildirim kanalına güvenmek yerine ilgili ekranı düzenli kontrol etmek de yerinde olur.</p>
      </section>

      <section id="uretimde-is-takibi" aria-labelledby="work-production">
        <h2 id="work-production">Üretim yapan işletmelerde iş takibi nasıl çalışır?</h2>
        <p>Bir tekstil üreticisinde yapılacaklar listesi günlük hatırlatmalar için kullanışlıdır; fakat asıl üretim işi bir siparişin kesimden dikime, süslemeden sevkiyata ilerlemesidir. Bu nedenle üretim işlerini yönetirken kişisel görev kaydının yanında siparişin gerçek aşama hareketlerini takip etmek gerekir.</p>
        <ol class="guide-steps">
          <li><strong>Sipariş bilgisini netleştirin.</strong><p>Müşteri, ürün kodu, renk, beden, adet ve teslim tarihini tek kayıtta tutun.</p></li>
          <li><strong>Üretim aşamalarını görünür kılın.</strong><p>Kesim, dikim, süsleme ve hazır gibi işlem adımlarındaki hareketleri siparişle ilişkilendirin.</p></li>
          <li><strong>İşlem kayıtlarını kontrol edin.</strong><p>Hangi aşamanın başladığını veya bittiğini ve ilgili hareketi kimin kaydettiğini gerektiğinde inceleyin.</p></li>
          <li><strong>Sevkiyata yaklaşan işleri değerlendirin.</strong><p>Teslim tarihi yaklaşan ürünlerde mevcut üretim aşamasını gözden geçirerek öncelik verin.</p></li>
        </ol>
        <p>Eylus'un üretim takibinde personel, ürüne ait QR kodu kullanarak üretim hareketini siparişe kaydedebilir. Yönetici sipariş listesi ve aşama kontrol ekranlarından işin son durumunu değerlendirebilir. Ayrıntılı akış için <a href="/uretim-takip-programi/">üretim takip programı rehberimize</a bakabilirsiniz.</p>
      </section>

      <section id="geciken-isler" aria-labelledby="work-stalled">
        <h2 id="work-stalled">Geciken ve hareketsiz işler nasıl fark edilir?</h2>
        <p>Bir işin listede bulunması, mutlaka ilerlediği anlamına gelmez. Üretim siparişi açıldıktan sonra günlerce hareket kaydedilmiyorsa teslimat riski artabilir. Bu nedenle işletme sahibi yalnızca toplam sipariş sayısını değil, son işlem tarihi gibi bilgileri de kontrol etmelidir.</p>
        <p>Eylus'un <strong>Üretim Aşaması Kontrolü</strong> ekranında üretimde hareketsiz kalan siparişler incelenebilir. Aşama kayıtlarında başlangıç veya bitiş gibi eksik adımlar da araştırılabilir. Bu bilgiler, üretimde gerçekten bir gecikme olup olmadığını anlamak için kontrol noktası oluşturur.</p>
        <p>Sistem, son üretim hareketinin üzerinden belirli süre geçen ve sevk edilmemiş işleri tespit etmeye yönelik kontroller içerir. Örneğin üç gün veya daha uzun süre hareket görmeyen siparişler için inceleme listesi oluşturulabilir. Ancak kaydın eksik olması fiziksel olarak hiçbir işlem yapılmadığını kesin olarak kanıtlamaz; ilgili personel ve iş akışıyla doğrulama gerekir.</p>
        <p>Yetkili yöneticiler için yaklaşan teslimatlara ve bekleyen işlere ilişkin bildirim mekanizmaları da bulunabilir. Bu bildirimler, doğru veri girişine ve uygulamanın çalışma koşullarına bağlıdır; her sorunu kendiliğinden çözen otomatik planlama olarak düşünülmemelidir.</p>
      </section>

      <section id="is-ve-siparis" aria-labelledby="work-order-difference">
        <h2 id="work-order-difference">İş takip programı ile sipariş takip programı arasındaki fark nedir?</h2>
        <p><strong>İş takip programı</strong> daha genel bir kavramdır: bir yöneticinin hatırlatması, yapılacak kontrol veya üretimdeki bir iş adımı bu kapsama girebilir. <strong>Sipariş takip programı</strong> ise müşterinin belirli bir ürüne ilişkin talebinin alınmasından teslimata kadar olan süreci izler.</p>
        <p>Örneğin “Yarın müşteriye telefon et” kişisel bir yapılacak iştir. “Müşterinin model 7119 siparişi dikimde bekliyor” ise siparişin üretim durumuyla ilgili bilgidir. Bu ayrım, hangi konunun yapılacaklar listesinde, hangi konunun üretim ekranında takip edileceğini belirlemeyi kolaylaştırır.</p>
        <p>Müşteri, ürün ve teslim tarihlerini içeren iş akışı hakkında daha fazla bilgi için <a href="/siparis-takip-programi/">sipariş takip programı rehberini</a inceleyebilirsiniz.</p>
      </section>

      <section id="is-takip-secimi" aria-labelledby="work-checklist">
        <h2 id="work-checklist">İş takip programı seçerken nelere dikkat edilmeli?</h2>
        <p>İş takibi için yazılım seçerken önce neyi takip etmek istediğinizi belirleyin. Sadece kişisel hatırlatmalar mı, ekip görevleri mi, müşteri siparişleri mi, yoksa üretimin her aşaması mı? Bu farklı ihtiyaçların tek bir başlık altında değerlendirilmesi yanlış beklenti yaratabilir.</p>
        <ul class="guide-checklist">
          <li><strong>İş tanımı:</strong> Görev başlığı ve açıklaması yeterince açık kaydedilebiliyor mu?</li>
          <li><strong>Tarih ve hatırlatma:</strong> İşe tarih eklenebiliyor ve uygun zamanda hatırlatma kurulabiliyor mu?</li>
          <li><strong>Tamamlanma takibi:</strong> Açık ve tamamlanmış işler ayrı görülebiliyor mu?</li>
          <li><strong>Üretim akışı:</strong> Müşteri siparişinin hangi üretim aşamasında olduğu incelenebiliyor mu?</li>
          <li><strong>Hareketsiz işler:</strong> Uzun süredir işlem kaydı olmayan siparişler bulunabiliyor mu?</li>
          <li><strong>Yetkilendirme:</strong> Kullanıcı yalnızca erişmesi gereken görev ve işletme bilgilerini mi görebiliyor?</li>
          <li><strong>Mobil kullanım:</strong> İşletme dışında olunan anlarda gerekli kayıtlara erişilebiliyor mu?</li>
        </ul>
        <p>Bir deneme yaparken iki farklı senaryo kullanın: Önce tarihli kişisel bir hatırlatma oluşturup tamamlayın; sonra bir üretim siparişinin son aşamasını ve gecikme riskini kontrol edin. Bu iki senaryonun da çalışma biçiminize uygun olması, uzun özellik listelerinden daha iyi bir karşılaştırma sunar.</p>
      </section>

      <section id="is-takip-sorular" aria-labelledby="work-faq">
        <h2 id="work-faq">Sık sorulan sorular</h2>
        <h3>İş takip programı sadece yapılacaklar listesi midir?</h3>
        <p>Hayır. Bazı programlar sadece kişisel görevleri izler; bazıları ekip projelerine, bazıları üretim siparişlerine odaklanır. İşletmenin ihtiyacına göre uygun kapsam seçilmelidir.</p>
        <h3>İş takibi üretim gecikmelerini otomatik önler mi?</h3>
        <p>Hayır. Yazılım, bekleyen işleri fark etmeyi kolaylaştırır. Gecikmeye neden olan malzeme, kapasite veya süreç sorunları yine işletme tarafından değerlendirilmelidir.</p>
        <h3>Personel performansı yalnızca işlem kayıtlarından ölçülebilir mi?</h3>
        <p>Tek başına doğru olmaz. Bir hareketi sisteme kimin kaydettiği faydalı bir bilgidir; ancak işin zorluğu, görev dağılımı ve gerçek üretim koşulları da dikkate alınmalıdır. Personel süreçleri hakkında <a href="/personel-takip-programi/">personel takip programı rehberini</a okuyabilirsiniz.</p>
        <h3>İş takip programına telefondan erişilebilir mi?</h3>
        <p>Programın altyapısına bağlıdır. Eylus, yetkili kullanıcıların internet bağlantısıyla telefon veya bilgisayardan ilgili işletme ekranlarını incelemesine imkân tanır.</p>
      </section>

      <section class="guide-last" aria-labelledby="work-cta">
        <span class="guide-kicker">EYLUS İLE TANIŞIN</span>
        <h2 id="work-cta">Yapılacakları ve üretimde bekleyen işleri daha görünür hale getirin.</h2>
        <p>Yapılacaklar, siparişler, üretim aşamaları ve sevkiyat planını işletmenizin gerçek iş akışı üzerinden değerlendirin.</p>
        <div class="guide-last-actions">
          <a href="/tekstil/" class="guide-button-primary">Eylus çözümlerini görün <span aria-hidden="true">↗</span></a>
          <a href="/demo/" class="guide-button-secondary">Canlı demoyu inceleyin <span aria-hidden="true">→</span></a>
        </div>
      </section>
    </div>
  </div>
</article>
'''


# Focused invoicing and invoice-draft article based on the existing order-linked module.
INVOICE_ARTICLE_URL = '/fatura-programi/'
INVOICE_GUIDE = '''
<article class="guide-page">
  <header class="guide-header">
    <div class="wrap guide-header-inner">
      <nav class="guide-breadcrumb" aria-label="İçerik yolu"><a href="/">Ana sayfa</a><span aria-hidden="true">/</span><span>Fatura programı</span></nav>
      <span class="guide-kicker">EYLUS REHBER · FATURA VE SİPARİŞ YÖNETİMİ</span>
      <h1>Fatura Programı Nedir? <em>Siparişten Fatura Taslağına Süreç Nasıl Yönetilir?</em></h1>
      <p class="guide-deck">Hangi sipariş faturaya aktarıldı? Hangi müşterinin taslağı hazır? Muhasebe sistemindeki kayıt oluşturuldu mu? Üretim yapan işletmeler için fatura süreci, yalnızca belge hazırlamaktan daha fazlasıdır.</p>
      <div class="guide-header-actions">
        <a href="#fatura-programi-nedir">Rehberi okuyun <span aria-hidden="true">↓</span></a>
        <a href="/tekstil/">Eylus çözümlerini inceleyin <span aria-hidden="true">↗</span></a>
      </div>
    </div>
  </header>
  <div class="wrap guide-body">
    <aside class="guide-side" aria-label="Yazı içeriği">
      <p>BU YAZIDA</p>
      <a href="#fatura-programi-nedir">Fatura programı nedir?</a>
      <a href="#siparisten-faturaya">Siparişten taslak faturaya</a>
      <a href="#fatura-satirlari">Fatura satırları ve KDV</a>
      <a href="#manuel-fatura">Manuel fatura ve proforma</a>
      <a href="#cari-eslestirme">Cari müşteri eşleştirme</a>
      <a href="#muhasebe-aktarimi">Muhasebe entegrasyonları</a>
      <a href="#e-fatura-farki">E-fatura ile taslak farkı</a>
      <a href="#fatura-takibi">Fatura durumlarının takibi</a>
      <a href="#fatura-programi-secimi">Program seçerken</a>
      <a href="#fatura-sorular">Sık sorulan sorular</a>
    </aside>
    <div class="guide-copy">
      <section id="fatura-programi-nedir" aria-labelledby="invoice-what">
        <h2 id="invoice-what">Fatura programı nedir?</h2>
        <p><strong>Fatura programı</strong>, müşterilere düzenlenecek satış belgelerinin bilgilerinin hazırlanmasına, fatura satırlarının kontrol edilmesine ve fatura kayıtlarının izlenmesine yardımcı olan yazılımdır. Bazı sistemler e-fatura veya e-arşiv düzenleme yeteneğine sahipken bazıları yalnızca taslakları hazırlar ve muhasebe programına aktarır. Bu özelliklerin birbirinden ayrılması önemlidir.</p>
        <p>Bir tekstil üreticisinde siparişler model, renk, beden ve adet bazında oluşur. Müşterinin aldığı ürünlerin fatura listesine yeniden elle yazılması, eksik veya fazla satır yazma riskini artırabilir. Sipariş bilgisinden fatura taslağı hazırlanması, aynı verinin tekrar girilmesini azaltmaya yardımcı olur.</p>
        <div class="guide-note"><strong>Önemli ayrım:</strong> Eylus, üretim ve sipariş yönetimiyle bağlantılı <strong>fatura taslağı ve muhasebe aktarım</strong> akışı sunar. Eylus'un tek başına GİB üzerinden resmî e-fatura veya e-arşiv belge düzenlediği varsayılmamalıdır.</div>
      </section>

      <section id="siparisten-faturaya" aria-labelledby="invoice-order">
        <h2 id="invoice-order">Siparişten fatura taslağı nasıl hazırlanır?</h2>
        <p>Üretim ve sevkiyat kayıtlarıyla bağlantısı olmayan fatura hazırlama sürecinde, hangi üründen kaç adet gönderildiğini bulmak zaman alabilir. Siparişin sistemde tanımlı olması bu işi kolaylaştırır: ilgili sipariş fatura hazırlama akışına alınabilir ve satır bilgileri üzerinden kontrol yapılabilir.</p>
        <ol class="guide-steps">
          <li><strong>İlgili siparişi açın.</strong><p>Müşteri, ürün kodu, renk, beden, adet, satış fiyatı ve para birimi gibi bilgilerin doğru olduğundan emin olun.</p></li>
          <li><strong>Fatura taslağına aktarın.</strong><p>Faturaya dahil edilmesi gereken siparişi seçip müşteriyle ilişkili fatura kaydında değerlendirin.</p></li>
          <li><strong>Satırları ve tutarları kontrol edin.</strong><p>Fiyat, miktar, açıklama, KDV oranı ve toplam gibi alanları belgenin hazırlanma amacına göre gözden geçirin.</p></li>
          <li><strong>Muhasebe kaydını ayrıca doğrulayın.</strong><p>Dış muhasebe sistemine aktarım yapılacaksa cari eşleştirme ve aktarım durumunu kontrol edin; resmî belge işlemini ilgili sistemde tamamlayın.</p></li>
        </ol>
        <p>Eylus'un <strong>Faturalar</strong> bölümünde siparişe bağlı taslak kayıtlar bulunur. Yönetici fatura içeriğini ve aktarım durumunu inceleyebilir. Bu akışta siparişin fatura taslağına alınması, ürünün sevk edildiği veya resmî fatura belgesinin kesildiği anlamına gelmez; bu durumlar ayrı kontrol edilmelidir.</p>
      </section>

      <section id="fatura-satirlari" aria-labelledby="invoice-lines">
        <h2 id="invoice-lines">Fatura satırı, satış fiyatı ve KDV kontrolü</h2>
        <p>Fatura hazırlığında en sık kontrol edilmesi gereken bilgiler ürün veya hizmet açıklaması, adet, birim fiyat, para birimi ve KDV oranıdır. Özellikle çok satırlı toptan siparişlerde benzer ürünlerin birbiriyle karıştırılmaması gerekir. Ürün kodunun yanına renk ve beden gibi tanımlayıcı bilgiler eklemek, satırları birbirinden ayırmayı kolaylaştırabilir.</p>
        <div class="guide-benefits">
          <div><span>01 / ÜRÜN</span><h3>Satır açıklaması</h3><p>Ürün kodu ve ilgili sipariş ayrıntılarını kullanarak doğru ürünün faturaya alındığını kontrol edin.</p></div>
          <div><span>02 / TUTAR</span><h3>Fiyat ve para birimi</h3><p>Satış bedelini siparişteki para birimiyle karşılaştırın; beklenmeyen farkları aktarım öncesinde inceleyin.</p></div>
          <div><span>03 / VERGİ</span><h3>KDV oranı</h3><p>Her satırın vergi oranını ilgili mevzuat ve ürün niteliğine göre teyit edin.</p></div>
          <div><span>04 / KONTROL</span><h3>Genel toplam</h3><p>Satırların vergi dahil tutarlarını kontrol ederek taslak ile muhasebe kaydının uyumunu değerlendirin.</p></div>
        </div>
        <p>Eylus'un fatura modelinde siparişe bağlı satırlar ve ayrıca eklenebilen manuel satırlar yer alır. Satırların fiyat ve KDV oranı bilgilerinden toplam hesaplanabilir. Fakat belirli bir entegrasyon için teknik KDV kısıtları bulunabilir; örneğin mevcut Paraşüt aktarım akışında satırların %10 KDV koşulunu karşılaması gerekmektedir. Bu teknik kural, her ürün veya işlem için geçerli bir vergi oranı tavsiyesi değildir.</p>
      </section>

      <section id="manuel-fatura" aria-labelledby="invoice-manual">
        <h2 id="invoice-manual">Manuel fatura ile proforma fatura arasındaki fark</h2>
        <p>Her fatura mutlaka sistemdeki üretim siparişinden doğmayabilir. Ek bir satış kalemi veya farklı bir işlem için manuel fatura kaydı gerekebilir. Bu tür kayıtlarda satır açıklaması, miktar, birim fiyat ve vergi bilgilerinin açıkça girilmesi önemlidir.</p>
        <p><strong>Proforma</strong> ise ticari işlem öncesinde sunulan, çoğunlukla teklif ve bilgilendirme amacı taşıyan belgedir; tek başına düzenlenmiş resmî satış faturası sayılmaz. Proforma ile gerçek satış faturasının ayrı tutulması, daha sonra hesaplarda yanlış anlaşılmaları azaltır.</p>
        <p>Eylus'ta siparişten bağımsız manuel fatura kayıtları ve ayrı proforma kayıtları oluşturulmasına yönelik alanlar bulunur. Proforma belgeler muhasebe sistemine normal satış faturası gibi gönderilmez. Bu ayrım, yanlış belge türüyle işlem yapılmaması için önemlidir.</p>
      </section>

      <section id="cari-eslestirme" aria-labelledby="invoice-mapping">
        <h2 id="invoice-mapping">Muhasebe programında cari müşteri eşleştirme neden gereklidir?</h2>
        <p>Üretim yazılımındaki müşteri adı ile muhasebe programındaki cari hesabın adı aynı olmak zorunda değildir. Bir müşterinin farklı şubeleri üretim takibinde ayrı kaydedilmiş olabilirken muhasebede tek cari hesap kullanılabilir. Kayıtlar doğru eşleştirilmezse belge yanlış cariye aktarılabilir.</p>
        <p>Eylus'ta BizimHesap ve Paraşüt için müşteri eşleştirme kayıtları bulunur. Yetkili kullanıcı, üretim sistemindeki müşteri ile dış muhasebe sistemindeki ilgili cari kaydı eşleştirebilir. Bu nedenle fatura aktarımından önce müşteri eşleşmesini doğrulamak gerekir.</p>
        <p>Cari eşleştirmenin doğru olması, muhasebedeki tüm müşteri bilgilerinin otomatik ve hatasız güncellendiği anlamına gelmez. Özellikle adres ve resmî bilgilerin hangi sistemde yönetildiği, entegrasyonun davranışına göre ayrıca değerlendirilmelidir.</p>
      </section>

      <section id="muhasebe-aktarimi" aria-labelledby="invoice-export">
        <h2 id="invoice-export">BizimHesap ve Paraşüt entegrasyonu nasıl çalışır?</h2>
        <p>Bir işletmenin üretim yazılımıyla muhasebe yazılımı farklı görevler üstlenebilir. Üretim yazılımı ürün ve siparişin ayrıntılarını bilir; muhasebe yazılımı ise resmî fatura süreçlerini yürütür. Entegrasyonun amacı, aynı satış satırlarını iki kez elle yazma ihtiyacını azaltmaktır.</p>
        <p>Eylus'ta BizimHesap ve Paraşüt ile <strong>satış faturası taslağı veya satış kaydı aktarımına</strong> yönelik iş akışları bulunur. Aktarım, gerekli yapılandırma ve yetkiler sağlandığında açık bir kullanıcı işlemiyle yapılır. Eksik cari eşleştirmesi, hatalı satır bilgisi veya bağlantı sorunu nedeniyle aktarım engellenebilir ya da sonucu belirsiz kalabilir.</p>
        <p>Özellikle dış sistemden yanıt alınamadığında aynı faturayı tekrar göndermek, mükerrer kayıt oluşturma riski taşıyabilir. Eylus'un aktarım kayıtlarında gönderilmedi, aktarıldı veya kontrol gerekli gibi durumlar izlenir. Sonucun belirsiz olduğu işlemlerde muhasebe sistemini kontrol etmeden yeniden deneme yapılmaması gerekir.</p>
      </section>

      <section id="e-fatura-farki" aria-labelledby="invoice-efatura">
        <h2 id="invoice-efatura">E-fatura, e-arşiv ve taslak fatura aynı şey mi?</h2>
        <p>Hayır. <strong>Fatura taslağı</strong>, düzenlenecek belgenin müşteri, kalem ve tutar bilgilerini hazırlamak için kullanılan kayıttır. <strong>E-fatura</strong> ve <strong>e-arşiv fatura</strong> ise yürürlükteki kurallara uygun olarak oluşturulan ve ilgili elektronik belge altyapısı üzerinden yürütülen resmî işlemlerdir.</p>
        <p>Bir satış kaydının Paraşüt'e veya BizimHesap'a aktarılmış olması, resmî elektronik belgenin mutlaka oluşturulduğunu ve alıcıya gönderildiğini kanıtlamaz. Dış sistemde belgenin türü, durumu ve resmî numarası ayrıca kontrol edilmelidir.</p>
        <p>Eylus'un rolü, üretim siparişi ile faturaya hazırlanan veriler arasında bağlantı kurmak ve yapılandırılmış muhasebe sistemlerine aktarım sürecini desteklemektir. E-fatura yükümlülükleri ve uygulanacak vergi oranları için muhasebecinizin ve ilgili resmî düzenlemelerin esas alınması gerekir.</p>
      </section>

      <section id="fatura-takibi" aria-labelledby="invoice-status">
        <h2 id="invoice-status">Fatura durumları nasıl kontrol altında tutulur?</h2>
        <p>Bir faturanın içerik olarak hazırlanması, muhasebe sistemine aktarılması ve resmî numarasının alınması birbirinden farklı aşamalar olabilir. Bu aşamalar karıştırıldığında “hangi fatura kesildi?” sorusunun cevabı belirsizleşir.</p>
        <p>Eylus'un fatura listesinde müşteri, tutar, para birimi, resmî fatura numarası ve muhasebe platformundaki işlem durumu gibi alanlar yer alabilir. Aktarım dışarıda elle yapılmışsa buna ilişkin durum da kaydedilebilir. Bazı taslaklar açık hesap veya aktarılmayacak şeklinde sınıflandırılabilir.</p>
        <p>Özellikle dönem sonunda fatura listesiyle muhasebe sistemindeki belgelerin karşılaştırılması yararlıdır. “Aktarıldı” işaretinin hangi işlemden sonra oluştuğunu anlamak, faturanın durumu hakkında daha sağlıklı yorum yapmayı sağlar.</p>
      </section>

      <section id="fatura-programi-secimi" aria-labelledby="invoice-criteria">
        <h2 id="invoice-criteria">Üretim işletmeleri fatura programı seçerken nelere bakmalı?</h2>
        <p>İşletmeniz için yazılım seçerken yalnızca fatura ekranının görünümüne bakmak yeterli değildir. Sipariş, sevkiyat ve muhasebe kayıtlarının nasıl bağlandığını kendi günlük çalışma biçiminizle test edin.</p>
        <ul class="guide-checklist">
          <li><strong>Sipariş bağlantısı:</strong> Mevcut müşteri ve ürün bilgilerinden fatura taslağı hazırlanabiliyor mu?</li>
          <li><strong>Manuel satırlar:</strong> Sipariş dışında eklenmesi gereken kalemler ayrıca kaydedilebiliyor mu?</li>
          <li><strong>Para birimi:</strong> Fatura para birimi ve satış fiyatı siparişle tutarlı mı?</li>
          <li><strong>KDV kontrolü:</strong> Satırların vergi oranları ve aktarım kısıtları açıkça görülebiliyor mu?</li>
          <li><strong>Cari eşleştirme:</strong> Müşterilerin dış muhasebe sistemindeki karşılıkları doğru seçilebiliyor mu?</li>
          <li><strong>Aktarım güvenliği:</strong> Belirsiz yanıt, mükerrer gönderim ve hatalı veri durumları nasıl yönetiliyor?</li>
          <li><strong>Resmî belge ayrımı:</strong> Taslak, muhasebe satış kaydı ve e-fatura düzenleme süreçleri doğru tanımlanıyor mu?</li>
        </ul>
        <p>Örneğin tek müşterinin farklı renk ve bedenlerdeki siparişlerini seçin. Bir taslak oluşturup satırların doğru geldiğini kontrol edin; ardından uygun cari eşleştirme ve muhasebe aktarım sürecini değerlendirin. <a href="/siparis-takip-programi/">Sipariş takip programı rehberimizde</a> üretim siparişlerinin başlangıç aşamasını ayrıca anlattık.</p>
      </section>

      <section id="fatura-sorular" aria-labelledby="invoice-faq">
        <h2 id="invoice-faq">Sık sorulan sorular</h2>
        <h3>Fatura programı e-fatura kesmek zorunda mı?</h3>
        <p>Hayır. Bazı yazılımlar fatura taslağı hazırlamak veya muhasebe sistemine satış kaydı aktarmak için kullanılır. Resmî e-fatura düzenleme ayrı teknik ve hukuki gerekliliklere tabidir.</p>
        <h3>Eylus'ta hazırlanan taslak doğrudan resmî fatura mı?</h3>
        <p>Hayır. Eylus'un fatura hazırlama kaydı, resmî e-belge düzenlendiği anlamına gelmez. İlgili muhasebe sisteminde e-fatura veya e-arşiv işlemi ayrıca kontrol edilmelidir.</p>
        <h3>Faturaya aktarılmamış siparişler kontrol edilebilir mi?</h3>
        <p>Eylus'ta sevk edilmiş olup faturaya aktarılmayan siparişler için kontrol amaçlı ekranlar bulunur. Böylece fatura hazırlama sürecinde gözden kaçan işleri incelemek kolaylaşır.</p>
        <h3>Proforma fatura ile satış faturası aynı mı?</h3>
        <p>Hayır. Proforma genellikle işlem öncesi teklif ve bilgilendirme amaçlı hazırlanır; resmî satış faturasının yerine geçmez. Eylus bu kayıtları ayrı türler olarak ele alır.</p>
        <h3>Paraşüt ve BizimHesap'a aynı şekilde aktarım yapılır mı?</h3>
        <p>İki muhasebe yazılımının API ve veri kuralları farklıdır. Eylus'taki aktarım işlemleri gerekli cari eşleştirmesi, doğrulama ve uygun yapılandırma koşullarına bağlıdır. Her taslağın koşulsuz aktarılacağı varsayılmamalıdır.</p>
      </section>

      <section class="guide-last" aria-labelledby="invoice-cta">
        <span class="guide-kicker">EYLUS İLE TANIŞIN</span>
        <h2 id="invoice-cta">Siparişten faturaya hazırlık sürecini daha düzenli yönetin.</h2>
        <p>Sipariş, sevkiyat, fatura taslağı ve muhasebe aktarım ekranlarının işletmenizde nasıl birlikte kullanılabileceğini değerlendirin.</p>
        <div class="guide-last-actions">
          <a href="/tekstil/" class="guide-button-primary">Eylus çözümlerini görün <span aria-hidden="true">↗</span></a>
          <a href="/demo/" class="guide-button-secondary">Canlı demoyu inceleyin <span aria-hidden="true">→</span></a>
        </div>
      </section>
    </div>
  </div>
</article>
'''

HOME = EYLUS_HOME_HERO
PRODUCT = intro('Ürün','Bir siparişten<br>bütün üretime.','Siparişin bilgisi, üretimin hareketi ve teslimatın planı. Birbirinden kopuk değil, birlikte.')+'<section class="section"><div class="wrap">'+features()+'<div class="callout">Eylus’un işletmenizdeki kapsamını ve kullanacağınız modülleri birlikte değerlendirelim. Bu site otomatik teklif veya lisans taahhüdü oluşturmaz.</div></div></section>'+TOUR+cta()

# Solution discovery page (public-facing; screenshot slots are intentionally empty until
# approved, redacted screenshots from the demo are added to eylus-site/screens/).
SOLUTION_GROUPS = [
  ("operasyon", "Operasyon", [
    ("operasyon-01", "Siparişlerinizin üretimde hangi aşamada olduğunu tek ekrandan takip edebiliyor musunuz?", "Siparişlerin son durumunu tek ekrandan görün", "Siparişinizin hangi aşamada olduğunu öğrenmek için atölyeyi aramanıza gerek kalmaz. Kesim, dikim, süsleme, malzeme eksikliği ve sevkiyat gibi güncel durumları; müşteri, model, beden ve teslim tarihiyle birlikte tek listede görüntüleyin. Arama ve filtreleme ile istediğiniz siparişi kolayca bulun.", "Sipariş Listesi"),
    ("operasyon-02", "Üretimde eksik veya yanlış kaydedilen aşamaları fark edebiliyor musunuz?", "Aşama sorunlarını görün", "Önceki üretim aşaması eksik olan siparişleri bulun; işlemi kaydeden kişiyi inceleyin. Bu kayıt kesin kusur tespiti değildir.", "Üretim Kontrol Merkezi · Aşama Problemleri"),
    ("operasyon-03", "Üretimde günlerdir ilerlemeyen siparişleri zamanında fark ediyor musunuz?", "Hareketsiz işleri fark edin", "Üç gün veya daha uzun süredir hareket görülmeyen, henüz sevk edilmemiş siparişleri görün.", "Üretim Kontrol Merkezi · Hareketsiz Siparişler"),
    ("operasyon-04", "Bu hafta hangi siparişleri hangi gün teslim edeceğinizi biliyor musunuz?", "Sevkiyatı haftalık planlayın", "Beş günlük sevkiyat planını müşteri, ürün, renk ve beden detayları ve günlük notlarla takip edin.", "Sevkiyat Planı"),
    ("operasyon-05", "Sevkiyata çıkacak siparişlerin fatura durumunu kolayca görebiliyor musunuz?", "Sevkiyat ve faturayı birlikte izleyin", "Planlı siparişlerin fatura işaretlerini görüntüleyin, detaylarına doğrudan geçin.", "Sevkiyat Planı · Fatura Durumu"),
    ("operasyon-06", "Hangi üründen, hangi renk ve bedende kaç adet kesileceğini planlayabiliyor musunuz?", "Kesim planınızı yönetin", "Siparişleri kesim gününe ekleyin. Model, renk, beden ve günlük/haftalık adet toplamlarını görün.", "Seri Kesim Planlama"),
    ("operasyon-07", "Kesim planınızı Excel'e aktarmak için yeniden tablo mu hazırlıyorsunuz?", "Kesim listesini Excel'e aktarın", "Her ürünün ayrı sekmede olduğu, renk-beden matrisi şeklinde haftalık Excel çıktısı alın.", "Seri Kesim Planı · Excel"),
    ("operasyon-08", "İşletmenizle ilgili bilgi bulmak için çalışanlara veya dosyalara mı bakıyorsunuz?", "Eylus Asistan'a sorun", "Aradığınız bilgiyi dosyalarda aramak yerine Eylus'un sanal asistanına sorun. Sipariş, gecikme ve sevkiyat verilerinizle ilgili sorularınıza, erişim yetkiniz kapsamındaki kayıtlar üzerinden doğal Türkçeyle yanıt alın.", "Eylus Asistan"),
    ("operasyon-09", "Aynı ürünün geçmiş siparişlerini kolayca karşılaştırabiliyor musunuz?", "Sohbet ederek sipariş analizi yapın", "Eylus Asistan'dan bir modelin siparişlerini müşterilere göre incelemesini veya günlük yönetici özetini isteyin.", "Eylus Asistan · Analiz"),
  ]),
  ("satis", "Satış", [
    ("satis-01", "Müşteri bilgileriniz farklı dosyalarda mı?", "Müşteriyi tek kartta tanıyın", "Telefon, adres, yetkili kişi, fatura ve ticari bilgilerini birlikte yönetin.", "Müşteriler"),
    ("satis-02", "En çok satış yaptığınız müşteriniz en kârlı müşteriniz mi?", "Müşteri kârlılığını görün", "Müşteri bazında ciro, maliyet, brüt kâr ve kâr marjını değerlendirin.", "Müşteri Detayı · Genel Bakış"),
    ("satis-03", "Müşterilerinizin en çok hangi modelleri aldığını biliyor musunuz?", "Satın alma alışkanlıklarını izleyin", "Sık alınan ürünleri, sevkiyat geçmişini ve dönemsel grafikleri inceleyin.", "Müşteri Detayı · Ürün İçgörüleri"),
    ("satis-04", "Konsinye ürünlerinizin hangi müşteride olduğunu biliyor musunuz?", "Konsinyeyi müşteri bazında yönetin", "Müşteri kartının konsinye bölümünden ilgili ürünleri inceleyin.", "Müşteri Detayı · Konsinye"),
    ("satis-05", "Ürün fiyatlarınız maliyet ve hedef kâra göre mi oluşuyor?", "Maliyet esaslı fiyatlandırın", "Ürün kartındaki malzeme, işçilik ve diğer maliyetlerin üzerine belirlediğiniz kâr ve indirim oranlarını uygulayın.", "Fiyat Listeleri · Kâr"),
    ("satis-06", "Kur değiştiğinde bütün fiyatları tekrar mı hesaplıyorsunuz?", "Döviz kuruna göre güncelleyin", "TCMB kurları hafta içi 09.15'te kontrol edilir; gerekirse günün kuru yeniden denenir veya son geçerli kur kullanılır. USD/EUR manuel değiştirilebilir.", "Fiyat Listeleri · Döviz"),
    ("satis-07", "Nakit ve 3, 6, 9 ay vadeli fiyatları ayrı ayrı mı hazırlıyorsunuz?", "Vadeli fiyatları hesaplayın", "Aylık vade oranına göre nakit, 3, 6 ve 9 aylık satış fiyatlarını birlikte görüntüleyin.", "Fiyat Listeleri · Vade"),
    ("satis-08", "İndirim yaptıktan sonra kalan kârınızı biliyor musunuz?", "Reel kârı görün", "Kâr ve indirim oranlarının birlikte oluşturduğu maliyet bazlı reel kârı hesaplayın.", "Fiyat Listeleri · Reel Kâr"),
    ("satis-09", "TL, dolar ve euro fiyat listeniz farklı dosyalarda mı?", "Para birimlerini birlikte yönetin", "TL nakit ve vadeli fiyatlarla USD/EUR karşılıklarını tek listede görüntüleyin, Excel'e aktarın.", "Fiyat Listeleri · Excel"),
    ("satis-10", "El yazısı sipariş föylerini satır satır mı giriyorsunuz?", "Yapay zekâ fotoğraftan okusun", "Bir veya birden fazla föy fotoğrafından ürün, renk, beden, adet ve fiyatları okutun; kontrol etmeden veriler föye uygulanmaz.", "Sipariş Föyü · Yapay Zekâ"),
    ("satis-11", "Föyden üretime geçerken bütün bilgileri yeniden mi yazıyorsunuz?", "Onaylı föyü siparişe dönüştürün", "Kontrol ekranından ürün, renk, beden ve adet bilgilerini siparişlere aktarın; daha önce oluşturulanları tekrarlamayın.", "Sipariş Föyü · Sipariş Oluşturma"),
    ("satis-12", "Müşteriyle anlaştığınız fiyat ve ödemeleri bir yerde görebiliyor musunuz?", "Föyde fiyat ve tahsilatı izleyin", "Fiyat, indirim, KDV, tahsilat, ödeme sözü ve kalan bakiyeyi föyde takip edin.", "Sipariş Föyü · Ödeme Planı"),
    ("satis-13", "Kesinleşmemiş ve onaylanan föyleri nasıl ayırıyorsunuz?", "Taslak ve onayı yönetin", "Föyleri taslak olarak hazırlayın, düzenleyin ve onaylandığında üretime aktarın.", "Sipariş Föyü · Onay"),
    ("satis-14", "Eski föylerinizin orijinal fotoğrafını kolayca bulabiliyor musunuz?", "Orijinal föyü arşivleyin", "Orijinal föy fotoğraflarını dijital kayda ekleyin; müşteri kartından inceleyin ve yazdırın.", "Sipariş Föyü · Arşiv"),
  ]),
  ("muhasebe", "Muhasebe", [
    ("muhasebe-01", "Siparişleri faturalandırırken bilgileri tekrar mı yazıyorsunuz?", "Siparişten faturaya aktarın", "Sipariş Detayı'ndaki Faturaya Aktar özelliğiyle kayıtlı bilgileri fatura taslağında kullanın.", "Sipariş Detayı · Faturaya Aktar"),
    ("muhasebe-02", "Fatura bilgilerini muhasebe programına tek tek mi giriyorsunuz?", "Entegrasyonlarla taslak gönderin", "Uygun taslakları BizimHesap veya Paraşüt'e aktarın. Paraşüt'te güncel %10 KDV koşulu bulunur.", "Fatura Detayı · Entegrasyonlar"),
    ("muhasebe-03", "Hangi faturanın işlem beklediğini biliyor musunuz?", "Fatura durumlarını takip edin", "Taslak, faturalı ve açık hesap durumlarını, resmî numaraları ve aktarım sonuçlarını izleyin.", "Faturalar Listesi"),
    ("muhasebe-04", "Faturadaki satırı düzeltmek için yeniden mi başlıyorsunuz?", "Faturayı esnek düzenleyin", "Satırları değiştirin, çıkarın, manuel ekleyin veya yeni faturaya ayırın.", "Fatura Detayı · Satırlar"),
    ("muhasebe-05", "Proforma için ayrı bir dosya mı hazırlıyorsunuz?", "Proformayı uygulamadan hazırlayın", "Müşteriye sunulabilecek proforma belgelerini Faturalar bölümünde oluşturun.", "Faturalar · Proforma"),
    ("muhasebe-06", "Çek ve senetlerinizi hâlâ defterde mi takip ediyorsunuz?", "Evrakları tek listede görün", "Alınan ve verilen çek/senet kayıtlarını banka, müşteri, tutar ve vade bilgileriyle yönetin.", "Çek ve Senetler"),
    ("muhasebe-07", "Yaklaşan çek ve senet vadelerini önceden görebiliyor musunuz?", "Vade aralıklarını filtreleyin", "Ödeme ve tahsilat evraklarını vade tarihlerine göre inceleyin.", "Çek ve Senetler · Vade"),
    ("muhasebe-08", "Bir çekin hangi durumda ve hangi firmada olduğunu biliyor musunuz?", "Evrakı hızla bulun", "Müşteri, banka, evrak numarası, verilen firma ve durumla arayın.", "Çek ve Senetler · Filtreler"),
    ("muhasebe-09", "Çek fotoğraflarını bulmak için telefonunuzu mu arıyorsunuz?", "Evrak görsellerini arşivleyin", "Fotoğrafları ilgili çek/senet kaydında saklayın, görüntüleyin ve yazdırın.", "Çek ve Senetler · Görseller"),
    ("muhasebe-10", "Çek/senet kayıtlarınızın yedeklerini nasıl alıyorsunuz?", "Google Drive'a yedekleyin", "Kayıt ve görsel yedeklemesini bağlantılı Google Drive hesabında başlatın.", "Çek ve Senetler · Yedek"),
  ]),
  ("yonetim", "Yönetim", [
    ("yonetim-01", "Bugün işletmenizde neler olduğunu kimseye sormadan görebiliyor musunuz?", "Patron Ekranı ile genel durumu görün", "Geciken işler, üretim, personel ve dikkat gerektiren kayıtları tek merkezde inceleyin.", "Patron Ekranı"),
    ("yonetim-02", "Bugün ve dün üretimde neler yapıldığını biliyor musunuz?", "Günlük üretimi karşılaştırın", "Bugünün ve dünün üretim hareketlerini aşama bazında adetlerle görün.", "Patron Ekranı · Üretim"),
    ("yonetim-03", "Önce hangi üretim sorununa müdahale etmelisiniz?", "Dikkat gerektirenleri ayırın", "Hareketsiz siparişleri, malzeme eksiklerini, hata kayıtlarını ve yaklaşan teslimatları izleyin.", "Patron Ekranı · Öncelikler"),
    ("yonetim-04", "Hangi personeliniz bugün geldi veya geç kaldı?", "Personel özetini izleyin", "Ekip bazında gelen, geç kalan ve gelmeyen personel sayılarını görüntüleyin.", "Patron Ekranı · Personel"),
    ("yonetim-05", "Dünkü sevkiyatların ciro ve brüt kârını biliyor musunuz?", "Sevkiyat finansını görün", "Dünkü sevkiyatın ciro, maliyet, brüt kâr ve kâr marjını para birimi bazında inceleyin.", "Patron Ekranı · Finans"),
  ]),
]
# Explicitly approved, anonymized real app captures only. Do not auto-discover photos.
# After user approval, map: "operasyon-01": ("siparis-listesi.webp", "Sipariş Listesi ekranı")
APPROVED_SOLUTION_SCREENSHOTS = {
    "operasyon-01": ("siparis-listesi-onayli.webp", "Eylus Sipariş Listesi: Son Durum sütunu kırmızı kalemle vurgulanmış, müşteri ve sipariş bilgileri örnek verilerle anonimleştirilmiş gerçek uygulama ekranı"),
}

def approved_solution_screen(key):
    approved = APPROVED_SOLUTION_SCREENSHOTS.get(key)
    if not approved:
        return ''
    filename, alt = approved
    if Path(filename).name != filename or Path(filename).suffix.lower() not in ('.webp', '.png', '.jpg', '.jpeg'):
        raise ValueError('Unsafe screenshot filename for ' + key)
    original = Path(__file__).parent / 'screens' / filename
    if not original.is_file():
        raise FileNotFoundError('Approved screenshot file missing: ' + filename)
    from shutil import copyfile
    output = OUT / 'assets' / 'solutions'
    output.mkdir(parents=True, exist_ok=True)
    copyfile(original, output / filename)
    url = '/assets/solutions/' + escape(filename, quote=True)
    return (f'<figure class="sol-real-screen"><button type="button" class="sol-screen-open" '
            f'data-sol-image-open data-sol-image-src="{url}" '
            f'data-sol-image-alt="{escape(alt, quote=True)}" '
            f'aria-label="Ekran görüntüsünü büyüt">'
            f'<img loading="lazy" decoding="async" src="{url}" alt="{escape(alt, quote=True)}">'
            f'<span class="sol-zoom-indicator" aria-hidden="true">⤢</span></button></figure>')

# Every new solution uses the approved title -> lead -> support -> real screen pattern.
# Original approved texts remain unchanged unless explicitly revised.
SOLUTION_EDITORIAL_COPY = {
    "operasyon-01": (
        "Atölyeyi aramadan, siparişinizin hangi aşamada olduğunu tek bakışta görün.",
        "Kesimden sevkiyata güncel durumları; müşteri, model, beden ve teslim tarihiyle birlikte takip edin. Arama ve filtrelerle istediğiniz siparişe kolayca ulaşın.",
    ),
    "operasyon-02": (
        "Üretim ilerlerken eksik kalan aşama kayıtlarını gözden kaçırmayın.",
        "Kesim, dikim ve süslemede eksik bırakılmış Başladı veya Bitti işlemlerini sipariş bazında görün. Personel bazlı görünümden ilgili siparişleri ve kaydı ortaya çıkaran işlemi inceleyin. Bunlar kayıt tutarsızlığı uyarılarıdır; kesin kusur tespiti değildir.",
    ),
    "yonetim-01": (
        "İşletmenizde bugün neler olduğunu öğrenmek için tek tek rapor istemeyin.",
        "Patron Ekranı'nda geciken ve yaklaşan teslimatları, günlük üretim hareketlerini, malzeme eksiklerini ve personel özetini bir arada görün. Öncelik vermeniz gereken işleri daha hızlı belirleyin.",
    ),
}

def solution_page():
    def solution_content(key, title, description, module, compact=False):
        heading = 'h4' if compact else 'h3'
        if key in SOLUTION_EDITORIAL_COPY:
            lead, support = SOLUTION_EDITORIAL_COPY[key]
            details = (f'<p class="sol-lead">{escape(lead)}</p>'
                       f'<p class="sol-support">{escape(support)}</p>')
        else:
            details = f'<p>{escape(description)}</p>'
        return (f'<div class="sol-answer">'
            f'<{heading}>{escape(title)}</{heading}>'
            f'{details}'
            f'{approved_solution_screen(key)}'
            f'</div>')

    categories = []
    questions = []
    desktop_panels = []
    total = sum(len(rows) for _, _, rows in SOLUTION_GROUPS)
    for group_index, (group_key, group_name, rows) in enumerate(SOLUTION_GROUPS):
        is_initial_group = group_index == 0
        categories.append(
            f'<button type="button" class="sol-category" data-sol-category="{escape(group_key)}" '
            f'aria-pressed="{str(is_initial_group).lower()}">'
            f'<span class="sol-category-title">{escape(group_name)}</span>'
            f'<span class="sol-category-count">{len(rows)} konu</span></button>'
        )
        for number, (key, question, title, description, module) in enumerate(rows, 1):
            is_initial_item = is_initial_group and number == 1
            questions.append(
                f'<article class="sol-item {"is-active" if is_initial_item else ""}" '
                f'data-sol-item="{escape(key)}" data-sol-group="{escape(group_key)}" '
                f'{"hidden" if not is_initial_group else ""}>'
                f'<button type="button" class="sol-question" data-sol-question="{escape(key)}" '
                f'aria-controls="sol-mobile-{escape(key)}" aria-expanded="false">'
                f'<span class="sol-question-index">{number:02}</span>'
                f'<span class="sol-question-label">{escape(question)}</span>'
                f'<span class="sol-question-chevron" aria-hidden="true">⌄</span></button>'
                f'<div class="sol-mobile-panel" data-sol-mobile-panel="{escape(key)}" '
                f'id="sol-mobile-{escape(key)}" hidden>'
                f'{solution_content(key,title,description,module,True)}</div></article>'
            )
            desktop_panels.append(
                f'<section class="sol-desktop-panel" data-sol-desktop-panel="{escape(key)}" '
                f'aria-label="{escape(question,quote=True)}" {"hidden" if not is_initial_item else ""}>'
                f'{solution_content(key,title,description,module)}</section>'
            )
    return (
        '<section class="sol-section" id="sorular"><div class="wrap">'
        + '<div class="sol-section-heading"><h1>Hangi alanda çözüm arıyorsunuz?</h1></div>'
        + '<div class="sol-categories" role="group" aria-label="Çözüm kategorileri">'
        + ''.join(categories) + '</div>'
        + '<div class="sol-layout">'
        + '<div class="sol-left"><div class="sol-left-heading">'
        + '<h2>Şu anda sizi en çok hangi sorun zorluyor?</h2>'
        + '</div><div class="sol-question-list" aria-label="Müşteri soruları">'
        + ''.join(questions) + '</div></div>'
        + '<div class="sol-right">'
        + ''.join(desktop_panels) + '</div>'
        + '</div>'
        + '</div></section>'
        + '<dialog class="sol-screen-dialog" id="sol-screen-dialog" aria-label="Eylus uygulama ekran görüntüsü">'
        + '<div class="sol-dialog-toolbar"><span>Ekran görüntüsü</span><div class="sol-dialog-actions">'
        + '<button type="button" data-sol-image-zoom class="sol-dialog-zoom">Yakınlaştır</button>'
        + '<button type="button" data-sol-image-close class="sol-dialog-close" aria-label="Görseli kapat">×</button>'
        + '</div></div><div class="sol-dialog-viewport"><img alt=""></div></dialog>'
        + cta()
    )

CSS += r'''
/* Eylus solutions: purposeful desktop two-column layout, native mobile accordion. */
.sol-hero{padding:65px 0 58px;background:radial-gradient(ellipse at 83% 38%,#efeaff 0,transparent 48%),linear-gradient(180deg,#fff,#fcfbff);border-bottom:1px solid #ece7f4}
.sol-hero-inner{max-width:1180px}.sol-hero .eyebrow{font-size:11px;letter-spacing:.14em}
.sol-hero h1{font-size:clamp(36px,4.35vw,58px);letter-spacing:-.052em;line-height:1.12;margin:22px 0 19px;max-width:900px}
.sol-hero h1 em{font-style:normal;color:var(--purple)}
.sol-hero p{max-width:700px;color:var(--muted);font-size:16px;line-height:1.7;margin:0 0 20px}
.sol-hero-link{display:inline-flex;gap:9px;align-items:center;color:var(--purple);font-size:13px;font-weight:700;padding:5px 0}
.sol-section{background:#faf9fc;padding:38px 0 85px}
.sol-section-heading{margin-bottom:22px}
.sol-section-heading h1{font-size:clamp(27px,3vw,36px);line-height:1.2;letter-spacing:-.04em;margin:0}
.sol-section-heading p{color:var(--muted);font-size:13px;line-height:1.6;margin:0 0 3px;max-width:350px}
.sol-categories{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:11px;margin-bottom:36px}
.sol-category{width:100%;display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:66px;text-align:left;border:1px solid #e8e0ee;background:#fff;border-radius:12px;padding:16px 17px;transition:box-shadow .2s,border-color .2s,background .2s}
.sol-category:hover{border-color:#b2a3d9;box-shadow:0 5px 22px #4134610b}
.sol-category[aria-pressed=true]{border:2px solid var(--purple);background:#f6f3ff;box-shadow:0 7px 22px #49369310;padding:15px 16px}
.sol-category-title{font-size:15px;font-weight:750;letter-spacing:-.015em;color:#282236}
.sol-category-count{font-size:11px;color:#81748e;white-space:nowrap}
.sol-layout{display:grid;grid-template-columns:minmax(0,.96fr) minmax(0,1.04fr);gap:25px;align-items:start}
.sol-left,.sol-right{min-width:0}
.sol-left-heading{margin-bottom:18px}
.sol-left-heading h2{font-size:23px;letter-spacing:-.03em;margin:0}
.sol-question-list{display:grid;gap:9px}
.sol-item{min-width:0;border:1px solid #e9e3ef;background:#fff;border-radius:12px;overflow:hidden;transition:border-color .15s,box-shadow .15s}
.sol-item[hidden]{display:none!important}
.sol-item:hover{border-color:#c3b8df}
.sol-item.is-active{border-color:#917ddb;box-shadow:0 5px 18px #47378a0d}
.sol-question{width:100%;display:grid;grid-template-columns:34px minmax(0,1fr) 19px;gap:13px;align-items:center;text-align:left;border:0;background:transparent;min-height:72px;padding:14px 15px;color:#302b3b}
.sol-question-index{width:33px;height:33px;display:grid;place-items:center;border-radius:9px;background:#f4f1fa;color:#8776b6;font-size:11px;font-weight:750}
.sol-question-label{font-size:13.5px;font-weight:600;line-height:1.47;overflow-wrap:anywhere}
.sol-question-chevron{font-size:22px;line-height:1;color:#998bab;transform:rotate(-90deg)}
.sol-item.is-active .sol-question-index{background:#eee8ff;color:var(--purple)}
.sol-item.is-active .sol-question-label{color:#4e36a7}
.sol-right{position:sticky;top:105px;border:1px solid #e8e1ef;background:white;box-shadow:0 17px 45px #30224b0c;border-radius:18px;overflow:hidden}
.sol-desktop-panel[hidden]{display:none!important}
.sol-answer{padding:34px 30px 30px}
.sol-answer h3,.sol-answer h4{font-size:clamp(24px,2.25vw,31px);font-weight:700;letter-spacing:-.035em;line-height:1.23;margin:0 0 17px}
.sol-answer p{font-size:15px;color:#5b5668;font-weight:400;line-height:1.78;letter-spacing:.002em;margin:0 0 22px}
.sol-answer .sol-lead{font-size:16px;color:#40394d;font-weight:500;line-height:1.6;margin:0 0 11px;letter-spacing:0}
.sol-answer .sol-support{font-size:14.5px;color:#676172;font-weight:400;line-height:1.78;margin:0 0 24px;max-width:60ch}
.sol-real-screen{margin:0;border:1px solid #e9e3f7;border-radius:13px;overflow:hidden;background:#fff}
.sol-screen-open{display:block;width:100%;border:0;padding:0;background:#fff;position:relative;cursor:zoom-in;line-height:0}
.sol-screen-open img{display:block;width:100%;max-height:460px;height:auto;object-fit:contain}
.sol-screen-open:focus-visible{outline:3px solid var(--purple);outline-offset:-3px}
.sol-zoom-indicator{position:absolute;right:12px;top:12px;background:#fff;box-shadow:0 3px 15px #26203333;color:#44308c;font-size:22px;line-height:1;border-radius:10px;padding:8px 11px}
.sol-screen-dialog{border:0;border-radius:18px;padding:0;position:fixed;inset:0;margin:auto;width:min(1100px,95vw);max-width:95vw;max-height:90dvh;overflow:hidden;background:#fff;box-shadow:0 20px 90px #0005}
.sol-screen-dialog::backdrop{background:rgba(15,14,24,.76)}
.sol-dialog-toolbar{display:flex;align-items:center;justify-content:space-between;gap:14px;min-height:60px;padding:10px 15px 10px 22px;border-bottom:1px solid #e7e4ec;background:#fff;color:#292334;font-size:14px;font-weight:750}
.sol-dialog-actions{display:flex;align-items:center;gap:9px}
.sol-dialog-zoom,.sol-dialog-close{border:1px solid #ded9e8;background:#f8f6fd;border-radius:10px;min-height:38px;color:#372b55;cursor:pointer;font-weight:700}
.sol-dialog-zoom{padding:8px 13px;font-size:13px}
.sol-dialog-close{width:40px;font-size:25px;line-height:1}
.sol-dialog-zoom:focus-visible,.sol-dialog-close:focus-visible{outline:3px solid var(--purple);outline-offset:2px}
.sol-dialog-viewport{max-height:calc(90dvh - 60px);overflow:auto;overscroll-behavior:contain;background:#f4f4f8;text-align:center;touch-action:pan-x pan-y}
.sol-dialog-viewport img{display:block;width:100%;max-width:100%;max-height:calc(90dvh - 65px);height:auto;object-fit:contain;margin:0 auto}
.sol-screen-dialog.is-zoomed .sol-dialog-viewport img{width:max(1100px,160vw);max-width:none;max-height:none}
@media(max-width:560px){.sol-screen-dialog{width:96vw;max-width:96vw;border-radius:13px}.sol-dialog-toolbar{padding:8px 10px 8px 13px;min-height:54px;font-size:12px}.sol-dialog-viewport{max-height:calc(90dvh - 54px)}.sol-dialog-viewport img{max-height:calc(90dvh - 54px)}.sol-dialog-zoom{font-size:12px;padding:7px 10px}.sol-dialog-close{min-height:38px;width:38px}}
.sol-mobile-panel{display:none}
@media(max-width:900px){
 .sol-categories{grid-template-columns:repeat(2,minmax(0,1fr))}
 .sol-layout{grid-template-columns:1fr;gap:16px}
 .sol-right{display:none}
 .sol-mobile-panel:not([hidden]){display:block;border-top:1px solid #eee8f6;background:#fcfbff}
 .sol-item.is-active{border:1px solid var(--purple);box-shadow:0 8px 20px #53439613}
 .sol-item.is-active .sol-question-chevron{transform:rotate(180deg)}
 .sol-question-chevron{transform:rotate(0deg)}
 .sol-answer{padding:19px 19px 21px}
 .sol-answer h4{font-size:23px;line-height:1.24;margin:0 0 15px}
 .sol-answer p{font-size:14.5px;color:#5b5668;font-weight:400;line-height:1.76;margin-bottom:18px}
 .sol-answer .sol-lead{font-size:15.5px;color:#40394d;font-weight:500;line-height:1.63;margin-bottom:10px}
 .sol-answer .sol-support{font-size:14px;color:#676172;font-weight:400;line-height:1.76;margin-bottom:22px}
 .sol-section{padding:30px 0 68px}
}
@media(max-width:560px){
 .sol-hero{padding:47px 0 37px}
 .sol-hero h1{font-size:clamp(33px,9vw,43px);line-height:1.14;margin:17px 0}
 .sol-hero p{font-size:14px}
 .sol-section-heading{display:block;margin-bottom:17px}
 .sol-section-heading h1{font-size:25px;margin:0}
 .sol-section-heading p{font-size:12px}
 .sol-categories{gap:8px;margin-bottom:26px}
 .sol-category{min-height:58px;padding:12px;display:flex;flex-direction:column;align-items:flex-start;gap:4px}
 .sol-category[aria-pressed=true]{padding:11px}
 .sol-category-title{font-size:14px}
 .sol-category-count{font-size:10px}
 .sol-left-heading h2{font-size:20px}
 .sol-question{min-height:69px;padding:12px;grid-template-columns:29px minmax(0,1fr) 16px;gap:10px}
 .sol-question-index{width:29px;height:29px;font-size:10px}
 .sol-question-label{font-size:13px}
 .sol-answer{padding:17px 14px 19px}
 .sol-answer h4{font-size:21px}
 .sol-cta{gap:14px}
 .sol-secondary-link{font-size:12px}
}
@media(prefers-reduced-motion:reduce){.sol-category,.sol-item{transition:none}}
'''

JS += r'''
const solCategories=[...document.querySelectorAll('[data-sol-category]')];
const solQuestionButtons=[...document.querySelectorAll('[data-sol-question]')];
const solItems=[...document.querySelectorAll('[data-sol-item]')];
const solMobileMedia=window.matchMedia('(max-width: 900px)');
let solSelected=solQuestionButtons[0]?.dataset.solQuestion||null;
function solSetQuestion(key){
  solSelected=key;
  solQuestionButtons.forEach(btn=>{
    const active=btn.dataset.solQuestion===key;
    btn.setAttribute('aria-expanded',String(active));
  });
  solItems.forEach(item=>item.classList.toggle('is-active',item.dataset.solItem===key));
  document.querySelectorAll('[data-sol-mobile-panel]').forEach(panel=>{
    panel.hidden=panel.dataset.solMobilePanel!==key;
  });
  document.querySelectorAll('[data-sol-desktop-panel]').forEach(panel=>{
    panel.hidden=panel.dataset.solDesktopPanel!==key;
  });
}
function solSelectCategory(group){
  solCategories.forEach(btn=>btn.setAttribute('aria-pressed',String(btn.dataset.solCategory===group)));
  solItems.forEach(item=>{item.hidden=item.dataset.solGroup!==group;});
  const first=solItems.find(item=>item.dataset.solGroup===group);
  solSetQuestion(solMobileMedia.matches?null:(first?.dataset.solItem||null));
}
solCategories.forEach(btn=>btn.addEventListener('click',()=>solSelectCategory(btn.dataset.solCategory)));
solQuestionButtons.forEach(btn=>{
  btn.addEventListener('click',()=>{
    const key=btn.dataset.solQuestion;
    solSetQuestion(solMobileMedia.matches&&solSelected===key?null:key);
  });
});

// Keep mobile initially collapsed; desktop retains the first active solution.
if(solMobileMedia.matches)solSetQuestion(null);
solMobileMedia.addEventListener('change',e=>{
  if(e.matches){solSetQuestion(null);return;}
  if(!solSelected){
    const firstVisible=solItems.find(item=>!item.hidden);
    solSetQuestion(firstVisible?.dataset.solItem||null);
  }
});

// Responsive solution screenshot viewer: bounded dialog, zoom, tap-away and Escape to dismiss.
const solScreenDialog=document.getElementById('sol-screen-dialog');
if(solScreenDialog){
  const img=solScreenDialog.querySelector('.sol-dialog-viewport img');
  const viewport=solScreenDialog.querySelector('.sol-dialog-viewport');
  const zoomButton=solScreenDialog.querySelector('[data-sol-image-zoom]');
  const closeButton=solScreenDialog.querySelector('[data-sol-image-close]');
  const resetZoom=()=>{
    solScreenDialog.classList.remove('is-zoomed');
    zoomButton.textContent='Yakınlaştır';
    viewport.scrollTop=0;viewport.scrollLeft=0;
  };
  document.querySelectorAll('[data-sol-image-open]').forEach(button=>{
    button.addEventListener('click',()=>{
      resetZoom();
      img.src=button.dataset.solImageSrc;
      img.alt=button.dataset.solImageAlt||'Eylus uygulama ekranı';
      solScreenDialog.showModal();
      closeButton.focus();
    });
  });
  closeButton.addEventListener('click',()=>solScreenDialog.close());
  zoomButton.addEventListener('click',()=>{
    const zoomed=solScreenDialog.classList.toggle('is-zoomed');
    zoomButton.textContent=zoomed?'Ekrana sığdır':'Yakınlaştır';
    viewport.scrollTop=0;viewport.scrollLeft=0;
  });
  solScreenDialog.addEventListener('click',event=>{
    if(event.target===solScreenDialog)solScreenDialog.close();
  });
  solScreenDialog.addEventListener('close',()=>{
    resetZoom();
    img.removeAttribute('src');
  });
}
'''

TEXTILE = solution_page()
WHY = intro('Neden Eylus?','Üretimi yönetmek,<br>ne olduğunu bilmekle başlar.','Eylus’un merkezinde bir ekran değil; o ekrana yansıyan gerçek iş akışı var.')+'<section class="section"><div class="wrap split"><div><p class="origin">“Bu sipariş nerede?” sorusunun cevabı, kişiden kişiye dolaşmak yerine kayıtta olmalı.</p><p>Eylus, tekstil üretimindeki günlük ihtiyaçlardan yola çıkan bir üretim yönetim yazılımıdır. Sipariş bilgisi ile atölyedeki ilerlemeyi aynı bakışta buluşturmayı amaçlar.</p><p>İlk odağımız tekstil. Marka vizyonumuz, üretim yapan işletmelerin süreçlerini daha görünür hale getirmek. Farklı bir sektördeyseniz, uyumu varsaymak yerine iş akışınızı birlikte değerlendirelim.</p></div><div class="value-list"><div><h3>Somut ihtiyaçlar</h3><p>Model, renk, beden, üretim aşaması ve teslim tarihi gibi günlük ayrıntılar.</p></div><div><h3>Birbirine bağlı süreçler</h3><p>Siparişin açılmasından sevkiyata uzanan bir takip yaklaşımı.</p></div><div><h3>Göstererek anlatım</h3><p>Uzun vaatler yerine ürünü inceleme ve işletmenizin ihtiyaçlarını konuşma.</p></div></div></div></section>'+cta()
DEMO_PAGE = intro('Canlı demo','Önce görün.<br>Sonra kendi üretiminizi düşünün.','Uygulamayı incelerken bu üç soruyu izleyin. Tanıtım sayfasındaki örneklerle mevcut demo uygulaması birbirinden ayrıdır.')+'<section class="section"><div class="wrap"><div class="demo-steps">'+''.join(f'<article class="demo-step"><b>0{i+1}</b><h2>{title}</h2><p>{desc}</p></article>' for i,(title,desc) in enumerate([('Geciken işleri bulun.','Siparişlerin teslim tarihlerini ve üretim durumlarını birlikte inceleyin.'),('Bir siparişi açın.','Ürün detaylarından üretim geçmişine ilerleyin.'),('Teslimat planına bakın.','Yaklaşan teslimatlar ile hazır ürünlerin durumunu karşılaştırın.')]))+'</div><div class="demo-entry"><div><h2>Eylus uygulamasını açın.</h2><p>Mevcut demo ortamı yeni sekmede açılır. Giriş bilgisi istenirse veya erişim sorunu yaşarsanız bizimle iletişime geçin. Bu sayfa otomatik ziyaretçi hesabı oluşturmaz.</p></div>'+button('Canlı uygulamaya git',DEMO,'purple',True)+'</div><div class="callout">Demoya gerçek müşteri, personel, fatura veya ödeme bilgisi girmeyin. Hesap oluşturmadan tanıtımı görmek için <a class="link" href="/#kesfet">etkileşimli örneğe dönün →</a></div></div></section><section class="section soft"><div class="wrap faq"><h2>Demoya geçmeden önce</h2><details><summary>Bu sitedeki paneller gerçek uygulama ekranı mı?</summary><p>Hayır. Bu ilk yayındaki paneller, iş akışını anlatan temsili arayüzlerdir. Sayılar ve siparişler örnektir. Gerçek uygulamayı ayrı demo bağlantısından inceleyebilirsiniz.</p></details><details><summary>Demo bir satın alma işlemi başlatır mı?</summary><p>Bu tanıtım sitesindeki demo bağlantısı herhangi bir ödeme veya abonelik başlatmaz.</p></details><details><summary>Kendi işletmem için görüşebilir miyiz?</summary><p>Evet. İletişim sayfasındaki Eylus Instagram hesabı üzerinden üretim akışınızı anlatabilir ve görüşme talep edebilirsiniz.</p></details></div></section>'
CONTACT = intro('İletişim','Sizin üretiminizi<br>konuşalım.','Ne üretiyorsunuz, siparişlerinizi nasıl takip ediyorsunuz, en çok nerede zorlanıyorsunuz? Buradan başlayalım.')+'<section class="section"><div class="wrap split"><div><h2>Bir mesajla başlayın.</h2><p>Firma adınızı, üretim alanınızı ve öncelikli ihtiyacınızı paylaşın. Kendi iş akışınız üzerinden Eylus’u değerlendirelim.</p><div class="message">Merhaba, Eylus’u işletmemiz için incelemek istiyoruz. Üretim alanımız: … En çok ihtiyaç duyduğumuz takip konusu: … Görüşme planlayabilir miyiz?</div><p class="note">Yukarıdaki metin yalnızca mesaj örneğidir; otomatik gönderilmez.</p></div><div class="contact-card">'+eyebrow('Eylus — doğrudan iletişim')+f'<strong class="contact-handle">@eylustech</strong><p>Eylus Instagram hesabından mesaj göndererek demo erişimi veya görüşme talep edebilirsiniz.</p>'+button('Instagram’dan yazın',SOCIAL,'purple',True)+'<p class="note" style="margin:20px 0 0">Instagram yeni sekmede açılır ve mesaj göndermek için hesabınıza giriş yapmanız gerekebilir. Bu sitede form veya takvim kaydı oluşturulmaz.</p></div></div></section><section class="section soft" id="gizlilik"><div class="wrap privacy"><h2>Site ve gizlilik bilgisi</h2><p>Bu tanıtım sitesine reklam izleme kodu, analitik çerezi veya bilgi toplama formu eklenmemiştir. Gösterilen siparişler ve sayılar temsili verilerdir.</p><p>Siteyi sunan altyapı, hizmetin çalışması ve güvenliği için teknik erişim kayıtları tutabilir. Instagram ve demo bağlantıları ayrı ortamlara yönlendirir; bu ortamların veri işleme koşulları ayrıdır.</p><p>İletişim kurarken ilk aşamada işletmenizi ve ihtiyacınızı kısaca anlatmanız yeterlidir. Gerçek müşteri listesi, personel bilgisi veya finansal belge göndermeyin.</p></div></section>'
PAGES = {
 '/': ('Üretim Takip ve Yönetim Yazılımı', 'Eylus ile sipariş, üretim, personel, maliyet ve sevkiyat süreçlerinizi tek yerden yönetin. QR ile kolay veri girişi, telefon ve bilgisayardan anlık takip.', HOME),
 '/uretim-takip-programi/': ('Üretim Takip Programı Nedir?', 'Üretim takip programı nedir, QR kodla üretim nasıl izlenir? Sipariş, kesim, dikim ve sevkiyat takibini Eylus örneğiyle öğrenin.', PRODUCTION_GUIDE),
 '/stok-takip-programi/': ('Stok Takip Programı Nedir?', 'Stok takip programı nedir? Depo bazında ürün ve malzeme miktarlarını, giriş-çıkış, iade, sayım ve konsinye takibini Eylus örneğiyle öğrenin.', STOCK_GUIDE),
 '/siparis-takip-programi/': ('Sipariş Takip Programı Nedir?', 'Sipariş takip programı nedir? Üretici işletmelerde sipariş kaydı, renk-beden bilgileri, QR ile üretim aşamaları ve teslimat planını öğrenin.', ORDER_GUIDE),
 '/personel-takip-programi/': ('Personel Takip Programı Nedir?', 'Personel takip programı nedir? Puantaj, giriş-çıkış, mesai, izin ve üretim ekibinin iş takibini Eylus örneğiyle öğrenin.', PERSONNEL_GUIDE),
 '/is-takip-programi/': ('İş Takip Programı Nedir?', 'İş takip programı nedir? Yapılacaklar, hatırlatmalar, geciken üretim işleri ve sipariş aşamalarını Eylus örneğiyle öğrenin.', WORK_GUIDE),
 '/fatura-programi/': ('Fatura Programı Nedir?', 'Fatura programı nedir? Siparişten taslak fatura oluşturma, proforma, cari eşleştirme ve Paraşüt/BizimHesap muhasebe aktarımını öğrenin.', INVOICE_GUIDE),
 '/urun/': ('Ürün ve üretim yönetimi', 'Sipariş, QR, üretim aşamaları, maliyet ve sevkiyat takibi. Eylus ürününü tanıyın.', PRODUCT),
 '/tekstil/': ('Üretim sorunlarına Eylus çözümleri', 'Sipariş takibi, gecikmeler, personel, sevkiyat, maliyet, fatura ve daha fazlası için Eylus çözümlerini keşfedin.', TEXTILE),
 '/neden-eylus/': ('Neden Eylus?', 'Üretimin içinden gelen bir yaklaşım. Eylus’un üretim yönetimi vizyonunu keşfedin.', WHY),
 '/demo/': ('Canlı demo', 'Eylus demo uygulamasına geçin; sipariş, üretim aşaması ve sevkiyat akışını inceleyin.', DEMO_PAGE),
 '/iletisim/': ('İletişim ve görüşme', 'Eylus ile iletişime geçin. İşletmenize uygun üretim takibini ve demo erişimini konuşalım.', CONTACT),
}

# Fingerprint the generated page and its assets on every release to prevent stale local CSS/JS.
CACHE_VERSION = sha256((CSS + JS + TEXTILE).encode('utf-8')).hexdigest()[:12]
# Identify the public website and its brand to search engines; never claim
# reviews, awards, paid plans or other unsupported product information.
HOME_STRUCTURED_DATA = {
    "@context": "https://schema.org",
    "@graph": [
        {
            "@type": "Organization",
            "@id": SITE + "/#organization",
            "name": "Eylus",
            "url": SITE + "/",
            "logo": SITE + "/assets/eylus-wordmark.png",
            "sameAs": [SOCIAL],
            "description": "Üretim yapan işletmelere yönelik üretim takip ve yönetim yazılımı."
        },
        {
            "@type": "WebSite",
            "@id": SITE + "/#website",
            "name": "Eylus",
            "url": SITE + "/",
            "inLanguage": "tr-TR",
            "publisher": {"@id": SITE + "/#organization"}
        }
    ]
}

GUIDE_STRUCTURED_DATA = {
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "Üretim Takip Programı Nedir? Siparişten Sevkiyata Üretiminizi Nasıl Yönetirsiniz?",
    "description": "Üretim takip programının işleyişini, QR kodla üretim aşamalarını ve sevkiyat takibini Eylus örneğiyle öğrenin.",
    "mainEntityOfPage": SITE + ARTICLE_URL,
    "author": {"@id": SITE + "/#organization"},
    "publisher": {"@id": SITE + "/#organization"},
    "inLanguage": "tr-TR",
    "datePublished": "2026-11-12"
}

STOCK_GUIDE_STRUCTURED_DATA = {
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "Stok Takip Programı Nedir? Depodaki Ürün ve Malzemeleri Nasıl Yönetirsiniz?",
    "description": "Depo, ürün ve malzeme stok takibini; giriş-çıkış, sayım ve konsinye süreçlerini Eylus örneğiyle öğrenin.",
    "mainEntityOfPage": SITE + STOCK_ARTICLE_URL,
    "author": {"@id": SITE + "/#organization"},
    "publisher": {"@id": SITE + "/#organization"},
    "inLanguage": "tr-TR",
    "datePublished": "2026-11-12"
}

ORDER_GUIDE_STRUCTURED_DATA = {
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "Sipariş Takip Programı Nedir? Üretim Siparişlerini ve Teslim Tarihlerini Nasıl Yönetirsiniz?",
    "description": "Sipariş kayıtları, üretim aşamaları, sipariş föyü ve sevkiyat planını üretici işletmeler için Eylus örneğiyle öğrenin.",
    "mainEntityOfPage": SITE + ORDER_ARTICLE_URL,
    "author": {"@id": SITE + "/#organization"},
    "publisher": {"@id": SITE + "/#organization"},
    "inLanguage": "tr-TR",
    "datePublished": "2026-11-12"
}

PERSONNEL_GUIDE_STRUCTURED_DATA = {
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "Personel Takip Programı Nedir? Puantaj, Mesai ve Üretim Ekibini Nasıl Yönetirsiniz?",
    "description": "Personel takibi, dijital puantaj, giriş-çıkış, izin, mesai ve üretimde görev kayıtlarını Eylus örneğiyle öğrenin.",
    "mainEntityOfPage": SITE + PERSONNEL_ARTICLE_URL,
    "author": {"@id": SITE + "/#organization"},
    "publisher": {"@id": SITE + "/#organization"},
    "inLanguage": "tr-TR",
    "datePublished": "2026-11-12"
}

WORK_GUIDE_STRUCTURED_DATA = {
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "İş Takip Programı Nedir? Yapılacak İşleri ve Üretimdeki Gecikmeleri Nasıl Yönetirsiniz?",
    "description": "İş takip programı, kişisel yapılacaklar, hatırlatmalar ve üretimde hareketsiz kalan işlerin Eylus'ta nasıl izlendiğini öğrenin.",
    "mainEntityOfPage": SITE + WORK_ARTICLE_URL,
    "author": {"@id": SITE + "/#organization"},
    "publisher": {"@id": SITE + "/#organization"},
    "inLanguage": "tr-TR",
    "datePublished": "2026-11-12"
}

INVOICE_GUIDE_STRUCTURED_DATA = {
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "Fatura Programı Nedir? Siparişten Fatura Taslağına Süreç Nasıl Yönetilir?",
    "description": "Üretim siparişlerinden taslak fatura hazırlama, proforma, KDV kontrolleri ve muhasebe aktarımını Eylus örneğiyle öğrenin.",
    "mainEntityOfPage": SITE + INVOICE_ARTICLE_URL,
    "author": {"@id": SITE + "/#organization"},
    "publisher": {"@id": SITE + "/#organization"},
    "inLanguage": "tr-TR",
    "datePublished": "2026-11-12"
}

def page(path,title,desc,body,noindex=False):
    page_title = f'{title} | Eylus'
    home_data = (f'<script type="application/ld+json">'
                 + json.dumps(HOME_STRUCTURED_DATA, ensure_ascii=False, separators=(',', ':'))
                 + '</script>') if path == '/' else ''
    home_image = (f'<meta property="og:image" content="{SITE}/assets/eylus-hero-workshop.webp">'
                  f'<meta name="twitter:image" content="{SITE}/assets/eylus-hero-workshop.webp">') if path == '/' else ''
    article_schema = (GUIDE_STRUCTURED_DATA if path == ARTICLE_URL else
                      STOCK_GUIDE_STRUCTURED_DATA if path == STOCK_ARTICLE_URL else
                      ORDER_GUIDE_STRUCTURED_DATA if path == ORDER_ARTICLE_URL else
                      PERSONNEL_GUIDE_STRUCTURED_DATA if path == PERSONNEL_ARTICLE_URL else
                      WORK_GUIDE_STRUCTURED_DATA if path == WORK_ARTICLE_URL else
                      INVOICE_GUIDE_STRUCTURED_DATA if path == INVOICE_ARTICLE_URL else None)
    guide_data = ('<script type="application/ld+json">'
                  + json.dumps(article_schema, ensure_ascii=False, separators=(',', ':'))
                  + '</script>') if article_schema else ''
    return f'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(page_title)}</title><meta name="description" content="{escape(desc,quote=True)}"><meta name="theme-color" content="#6450d8"><meta name="referrer" content="strict-origin-when-cross-origin"><meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'none'; object-src 'none'; base-uri 'self'; form-action 'none'"><meta name="robots" content="{'noindex,follow' if noindex else 'index,follow'}"><link rel="canonical" href="{SITE}{path}"><meta property="og:type" content="website"><meta property="og:site_name" content="Eylus"><meta property="og:locale" content="tr_TR"><meta property="og:title" content="{escape(page_title,quote=True)}"><meta property="og:description" content="{escape(desc,quote=True)}"><meta property="og:url" content="{SITE}{path}"><meta name="twitter:card" content="summary_large_image" >{home_image}{home_data}{guide_data}<meta name="eylus-release" content="{CACHE_VERSION}"><link rel="icon" type="image/png" sizes="96x96" href="/assets/eylus-brand-icon.png"><link rel="stylesheet" href="/assets/site.css?v={CACHE_VERSION}"><script src="/assets/site.js?v={CACHE_VERSION}" defer></script></head><body>{header(path)}<main id="main">{body}</main>{footer()}</body></html>'''
for path,(title,desc,body) in PAGES.items():
    dest=OUT / path.strip('/') / 'index.html'
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(page(path,title,desc,body,noindex=path=='/demo/'),encoding='utf-8')
# Versioned QA route is unlinked, noindex, and has the same markup as the main solutions page.
qa = OUT / 'surum-kontrol-20261110-1531' / 'index.html'
qa.parent.mkdir(parents=True, exist_ok=True)
qa.write_text(page('/tekstil/', PAGES['/tekstil/'][0], PAGES['/tekstil/'][1], TEXTILE, True), encoding='utf-8')
(OUT/'site-version.txt').write_text('EYLUS release: ' + CACHE_VERSION + '\nMain solutions: /tekstil/\n',encoding='utf-8')
(OUT/'assets/site.css').write_text(CSS,encoding='utf-8')
(OUT/'assets/site.js').write_text(JS,encoding='utf-8')
# Publish the approved workshop scene as a first-party, optimized site asset.
(OUT/'assets/eylus-hero-workshop.webp').write_bytes((Path(__file__).parent/'brand'/'hero-workshop.webp').read_bytes())
# Publish approved, frame-free EYLUS assets with all site pages.
for brand_file in ('eylus-wordmark.png', 'eylus-brand-icon.png'):
    (OUT/'assets'/brand_file).write_bytes((Path(__file__).parent/'brand'/brand_file).read_bytes())
(OUT/'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n',encoding='utf-8')
(OUT/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+SITE+p+'</loc></url>' for p in PAGES if p!='/demo/')+'</urlset>',encoding='utf-8')
(OUT/'404.html').write_text(page('/404.html','Sayfa bulunamadı','Aradığınız sayfa bulunamadı.',intro('404','Bu sayfayı bulamadık.','Ana sayfadan devam edebilirsiniz.')+'<section class="section"><div class="wrap">'+button('Ana sayfaya dön','/')+'</div></section>',True),encoding='utf-8')
print('Built 6 pages and a 404 page; only public assets in',OUT)

from pathlib import Path
from html import escape
from hashlib import sha256
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
        f'<a class="mobile-signin" href="{DEMO}" target="_blank" rel="noopener noreferrer">Giriş Yap</a>'
    )
    chat_icon = '<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11.5a7.9 7.9 0 0 1-8 8 9 9 0 0 1-3.7-.8L4 20l1.4-4.1A8 8 0 1 1 20 11.5Z"/><path d="M8.7 10.2c1 2.1 2.3 3.4 4.4 4.4"/></svg>'
    return f'''<a class="skip" href="#main">İçeriğe geç</a><header class="nav eylus-header"><div class="wrap nav-inner"><a class="wordmark" href="/" aria-label="Eylus ana sayfa"><img src="/assets/eylus-wordmark.png" width="1488" height="252" alt="EYLUS" decoding="async"></a><nav id="primary-nav" class="nav-links" aria-label="Ana menü">{links}</nav><div class="nav-cta"><a class="nav-login" href="{DEMO}" target="_blank" rel="noopener noreferrer" title="Eylus demo giriş ekranı">Giriş Yap</a><details class="eylus-nav-contact"><summary class="nav-write">{chat_icon}<span>Bize Yazın</span></summary><div class="eylus-contact-options eylus-contact-nav-options"><a href="https://www.instagram.com/eylustech/" target="_blank" rel="noopener noreferrer">Instagram <small>@eylustech</small></a><a href="https://wa.me/905368163125" target="_blank" rel="noopener noreferrer">WhatsApp <small>Mesaj gönder</small></a></div></details></div><button class="menu-toggle" aria-label="Menüyü aç veya kapat" aria-controls="primary-nav" aria-expanded="false" type="button">☰</button></div></header>'''
def footer():
    return f'''<footer class="footer eylus-footer"><div class="wrap">
      <div class="footer-top"><div class="eylus-footer-brand">
        <a class="wordmark" href="/" aria-label="Eylus ana sayfa"><img src="/assets/eylus-wordmark.png" width="1488" height="252" alt="EYLUS" loading="lazy" decoding="async"></a>
        <p>Üretimin her aşaması kontrolünüzde.</p>
        <div class="eylus-footer-intro">
          <p>“Bu sipariş nerede?”, “Neden hâlâ bitmedi?”, “Yarın ne sevk edeceğiz?” sorularını gün boyu çalışanlarınıza sormak zorunda kalmayın. Eylus ile hangi siparişin kesimde, dikimde veya süslemede olduğunu, nerede beklediğini ve hangi teslimatların yaklaştığını tek ekrandan görün. Atölyede, evde ya da seyahatte olun; işletmenizin güncel durumuna telefonunuzdan veya bilgisayarınızdan ulaşın.</p>
          <p>Üstelik personeliniz uzun formlar doldurmaz; yaptığı işlemi ürünün QR kodunu okutarak kaydeder. Siz de üretimde aksayan işleri daha erken fark eder, teslimatları daha rahat planlar ve zamanında müdahale edersiniz. <strong>Daha az telefon trafiği, daha az son dakika sürprizi, daha fazla kontrol.</strong></p>
        </div>
      </div></div>
      <div class="footer-bottom">
        <span class="eylus-footer-copyright">© 2026 Eylus</span>
        <nav class="eylus-footer-nav" aria-label="Alt bağlantılar">
          <a href="/tekstil/">Çözümler</a>
          <a href="/demo/">Canlı demo</a>
          <a href="/neden-eylus/">Neden Eylus?</a>
          <a href="/iletisim/">İletişim</a>
          <a href="{SOCIAL}" target="_blank" rel="noopener noreferrer">Instagram</a>
        </nav>
        <a class="eylus-footer-privacy" href="/iletisim/#gizlilik">Site ve gizlilik bilgisi</a>
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
 '/': ('Üretimin her aşaması kontrolünüzde', 'Eylus ile siparişleri, üretim aşamalarını ve teslimatları tek yerden takip edin. Tekstil odaklı üretim yönetim yazılımını keşfedin.', HOME),
 '/urun/': ('Ürün ve üretim yönetimi', 'Sipariş, QR, üretim aşamaları, maliyet ve sevkiyat takibi. Eylus ürününü tanıyın.', PRODUCT),
 '/tekstil/': ('Üretim sorunlarına Eylus çözümleri', 'Sipariş takibi, gecikmeler, personel, sevkiyat, maliyet, fatura ve daha fazlası için Eylus çözümlerini keşfedin.', TEXTILE),
 '/neden-eylus/': ('Neden Eylus?', 'Üretimin içinden gelen bir yaklaşım. Eylus’un üretim yönetimi vizyonunu keşfedin.', WHY),
 '/demo/': ('Canlı demo', 'Eylus demo uygulamasına geçin; sipariş, üretim aşaması ve sevkiyat akışını inceleyin.', DEMO_PAGE),
 '/iletisim/': ('İletişim ve görüşme', 'Eylus ile iletişime geçin. İşletmenize uygun üretim takibini ve demo erişimini konuşalım.', CONTACT),
}

# Fingerprint the generated page and its assets on every release to prevent stale local CSS/JS.
CACHE_VERSION = sha256((CSS + JS + TEXTILE).encode('utf-8')).hexdigest()[:12]
def page(path,title,desc,body,noindex=False):
    return f'''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} | Eylus</title><meta name="description" content="{escape(desc,quote=True)}"><meta name="theme-color" content="#6450d8"><meta name="referrer" content="strict-origin-when-cross-origin"><meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'none'; object-src 'none'; base-uri 'self'; form-action 'none'"><meta name="robots" content="{'noindex,follow' if noindex else 'index,follow'}"><link rel="canonical" href="{SITE}{path}"><meta property="og:type" content="website"><meta property="og:site_name" content="Eylus"><meta property="og:locale" content="tr_TR"><meta property="og:title" content="{escape(title,quote=True)} | Eylus"><meta property="og:description" content="{escape(desc,quote=True)}"><meta property="og:url" content="{SITE}{path}"><meta name="twitter:card" content="summary"><meta name="eylus-release" content="{CACHE_VERSION}"><link rel="icon" type="image/png" sizes="96x96" href="/assets/eylus-brand-icon.png"><link rel="stylesheet" href="/assets/site.css?v={CACHE_VERSION}"><script src="/assets/site.js?v={CACHE_VERSION}" defer></script></head><body>{header(path)}<main id="main">{body}</main>{footer()}</body></html>'''
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

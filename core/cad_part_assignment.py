"""Assign semantic labels to DXF contour entities for preview, without saving data."""
import json
from html import escape as html_escape

LABELS = {
    "on_orta": "Ön orta", "on_kup": "Ön kup", "on_yan": "Ön yan",
    "arka_orta": "Arka orta", "arka_yan": "Arka yan", "astar": "Astar",
    "etek": "Etek", "diger": "Diğer"
}

def labeled_preview(result):
    points = [v for shape in result["paths"] for v in shape["points"]]
    minx,maxx = min(x for x,y in points),max(x for x,y in points)
    miny,maxy = min(y for x,y in points),max(y for x,y in points)
    scale = min(920/max(maxx-minx,1),620/max(maxy-miny,1))
    width,height = (maxx-minx)*scale+40,(maxy-miny)*scale+40
    parts=[]
    for i,shape in enumerate(result["paths"]):
        coords = shape["points"]
        d = "M " + " L ".join(f"{(x-minx)*scale+20:.2f},{(maxy-y)*scale+20:.2f}" for x,y in coords)
        layer = html_escape(shape["layer"], quote=True)
        parts.append(f'<path id="shape-{i}" data-index="{i}" data-layer="{layer}" d="{d}" fill="none" stroke="#2563a6" stroke-width="1.4" stroke-linejoin="round"/>')
    return f'<svg id="cad-drawing" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.1f} {height:.1f}" role="img" aria-label="DXF parçalarını seçin">' + "".join(parts) + "</svg>"

def part_assignment_ui(result):
    options = "".join(f'<option value="{html_escape(k)}">{html_escape(v)}</option>' for k,v in LABELS.items())
    rows=[]
    for i,p in enumerate(result["paths"]):
        layer = html_escape(p["layer"])
        rows.append(f'<div class="part-row" data-part="{i}"><span>#{i+1} · {layer} · {p["type"]}</span><select aria-label="Çizim {i+1} parça adı" data-label="{i}"><option value="">Tanımsız</option>{options}</select></div>')
    script = """<script>
(function(){
const root=document.getElementById('cad-drawing');
const paths=[...root.querySelectorAll('path[data-index]')];
const selected=document.getElementById('selected-piece');
const labels=document.querySelectorAll('select[data-label]');

const seamShapes=JSON.parse(document.getElementById('seam-data').textContent);
const seamInfo=document.getElementById('seam-info');
let seamPicked=[],seamEdges=[];let activeIndex=-1;
function seamLength(points,a,b){let n=0;for(let k=a;k<b;k++)n+=Math.hypot(points[k+1][0]-points[k][0],points[k+1][1]-points[k][1]);return n;}
function seamSelect(i){
 if(seamEdges.length===2)return;
 activeIndex=i;
 root.querySelectorAll('circle.seam-marker').forEach(n=>n.remove());
 const pts=seamShapes[i].screen;
 pts.forEach((p,j)=>{
  const el=document.createElementNS('http://www.w3.org/2000/svg','circle');
  el.setAttribute('cx',p[0]);el.setAttribute('cy',p[1]);el.setAttribute('r','4');
  el.setAttribute('fill','#e11d48');el.setAttribute('class','seam-marker');
  el.style.cursor='pointer';
  el.addEventListener('click',e=>{
   e.stopPropagation();
   if(seamPicked.length===0)seamPicked=[j];
   else if(j!==seamPicked[0]){
    const a=Math.min(j,seamPicked[0]),b=Math.max(j,seamPicked[0]);
    const mm=seamLength(seamShapes[i].mm,a,b);
    seamEdges.push({index:i,a,b,mm});seamPicked=[];
    root.querySelectorAll('circle.seam-marker').forEach(n=>n.remove());
    seamInfo.textContent=seamEdges.length===1?'İlk kenar: '+mm.toFixed(1)+' mm. İkinci konturu seçin.':'Kenarlar: '+seamEdges.map(v=>v.mm.toFixed(1)).join(' / ')+' mm; fark: '+Math.abs(seamEdges[0].mm-seamEdges[1].mm).toFixed(1)+' mm. Düzeltmek için aşağıdaki butona basın.';
   }
  });root.appendChild(el);
 });
 seamInfo.textContent='Kontur #'+(i+1)+': kenarın iki uç noktasını seçin.';
}
document.getElementById('seam-reset').addEventListener('click',()=>{seamEdges=[];seamPicked=[];root.querySelectorAll('circle.seam-marker').forEach(n=>n.remove());seamInfo.textContent='İlk konturu seçin.';});
function updatePointLists(i){
 const pts=seamShapes[i].mm;
 for(const id of ['seam-start','seam-end']){
  const el=document.getElementById(id);el.replaceChildren();
  pts.forEach((p,j)=>{const option=document.createElement('option');option.value=j;option.textContent='Nokta '+(j+1)+' ('+p[0].toFixed(0)+', '+p[1].toFixed(0)+' mm)';el.appendChild(option);});
 }
 document.getElementById('seam-end').value=String(pts.length-1);
}
document.getElementById('seam-add').addEventListener('click',()=>{
 if(activeIndex<0){seamInfo.textContent='Önce listeden bir parça seçin.';return;}
 if(seamEdges.length>=2){seamInfo.textContent='İki kenar zaten seçildi. Yeni seçim için sıfırlayın.';return;}
 const a=Number(document.getElementById('seam-start').value),b=Number(document.getElementById('seam-end').value);
 if(!Number.isInteger(a)||!Number.isInteger(b)||a===b){seamInfo.textContent='İki farklı uç nokta seçin.';return;}
 const lo=Math.min(a,b),hi=Math.max(a,b),mm=seamLength(seamShapes[activeIndex].mm,lo,hi);
 if(mm<=0){seamInfo.textContent='Seçilen kenarın uzunluğu sıfır.';return;}
 seamEdges.push({index:activeIndex,a:lo,b:hi,mm});seamPicked=[];
 seamInfo.textContent=seamEdges.length===1?'İlk kenar kaydedildi: '+mm.toFixed(1)+' mm. Şimdi diğer parçayı seçin.':'İki kenar seçildi: '+seamEdges[0].mm.toFixed(1)+' / '+mm.toFixed(1)+' mm. Fark: '+Math.abs(seamEdges[0].mm-mm).toFixed(1)+' mm.';
});
const colors={'on_orta':'#0d9488','on_kup':'#a855f7','on_yan':'#2563eb','arka_orta':'#dc2626','arka_yan':'#e8793e','astar':'#16a34a','etek':'#b45309','diger':'#64748b'};
const front=paths.find(p=>p.dataset.layer==='ON_ORTA');
if(front){
 const original=front.getAttribute('d');
 const matches=[...original.matchAll(/(-?\\d+(?:\\.\\d+)?),(-?\\d+(?:\\.\\d+)?)/g)];
 const coords=matches.map(m=>[Number(m[1]),Number(m[2])]);
 if(coords.length){
  const minx=Math.min(...coords.map(p=>p[0])),maxx=Math.max(...coords.map(p=>p[0]));
  const ghost=front.cloneNode(false);ghost.removeAttribute('id');ghost.removeAttribute('data-index');ghost.setAttribute('stroke','#94a3b8');ghost.setAttribute('stroke-dasharray','5 4');ghost.style.pointerEvents='none';front.parentNode.insertBefore(ghost,front);
  const panel=document.getElementById('front-edit');panel.hidden=false;
  const slider=document.getElementById('front-change'),out=document.getElementById('front-change-value');
  slider.addEventListener('input',()=>{
   const mm=Number(slider.value);out.textContent=(mm>0?'+':'')+mm+' mm';
   const scale=1+mm*3/Math.max(1,maxx-minx);
   front.setAttribute('d',coords.map((p,i)=>(i?'L ':'M ')+(minx+(p[0]-minx)*scale).toFixed(2)+','+p[1].toFixed(2)).join(' '));
  });
 }
}
function choose(i){seamSelect(i);updatePointLists(i);document.getElementById('piece-picker').value=String(i);paths.forEach((p,j)=>p.style.strokeWidth=j===i?'4':'1.4');selected.textContent='Seçili çizim: #'+(i+1);document.querySelector('[data-label="'+i+'"]').focus({preventScroll:true});}
paths.forEach((p,i)=>p.addEventListener('click',()=>choose(i)));
document.getElementById('piece-picker').addEventListener('change',e=>choose(Number(e.target.value)));
const hits=paths.map((p,i)=>{const h=p.cloneNode(false);h.removeAttribute('id');h.removeAttribute('data-index');h.setAttribute('stroke','transparent');h.setAttribute('stroke-width','18');h.setAttribute('fill','none');h.style.cursor='pointer';h.addEventListener('click',()=>choose(i));p.parentNode.insertBefore(h,p);return h;});
document.getElementById('seam-adjust').addEventListener('click',()=>{
 if(seamEdges.length!==2){seamInfo.textContent='Önce iki kenarı seçin.';return;}
 if(document.getElementById('cad-unit').dataset.unit!=='4'){seamInfo.textContent='DXF mm birimi doğrulanmadığı için işlem durduruldu.';return;}
 const target=seamEdges[0],edit=seamEdges[1];
 if(target.mm<=0||edit.mm<=0||target.index===edit.index){seamInfo.textContent='İki farklı parçadan geçerli kenarlar seçin.';return;}
 const pts=seamShapes[edit.index].mm,original=pts.map(p=>p.slice());
 const ratio=target.mm/edit.mm;
 if(ratio<0.9||ratio>1.1){seamInfo.textContent='Fark yüzde 10 sınırını aşıyor; otomatik değişiklik yapılmadı.';return;}
 const anchor=original[edit.a],end=original[edit.b];
 const dx=(end[0]-anchor[0])*(ratio-1),dy=(end[1]-anchor[1])*(ratio-1);
 for(let j=edit.a;j<pts.length;j++){
  const weight=j<=edit.b?(j-edit.a)/(edit.b-edit.a):1;
  pts[j]=[original[j][0]+dx*weight,original[j][1]+dy*weight];
 }
 const newLength=seamLength(pts,edit.a,edit.b);
 seamInfo.textContent='İkinci kontur güncellendi. Yeni kenar: '+newLength.toFixed(1)+' mm; hedef: '+target.mm.toFixed(1)+' mm. Üretim onayı değildir.';
 const all=seamShapes.flatMap(s=>s.mm),xs=all.map(p=>p[0]),ys=all.map(p=>p[1]);
 const minx=Math.min(...xs),maxy=Math.max(...ys),scale=Number(document.getElementById('seam-scale').value);
 const updated=pts.map(p=>[(p[0]-minx)*scale+20,(maxy-p[1])*scale+20]);
 paths[edit.index].setAttribute('d',updated.map((p,j)=>(j?'L ':'M ')+p[0].toFixed(2)+','+p[1].toFixed(2)).join(' '));
 seamEdges=[];seamPicked=[];root.querySelectorAll('circle.seam-marker').forEach(n=>n.remove());
});

labels.forEach(s=>s.addEventListener('change',()=>{paths[Number(s.dataset.label)].style.stroke=colors[s.value]||'#2563a6';}));
document.getElementById('export-labels').addEventListener('click',()=>{
 const payload={version:1,unit:document.getElementById('cad-unit').dataset.unit,labels:[...labels].map(s=>({index:Number(s.dataset.label),label:s.value}))};
 const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});
 const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='moli-kalip-parca-eslestirme.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
});
})();
</script>"""
    points = [v for shape in result["paths"] for v in shape["points"]]
    minx, maxx = min(x for x,y in points), max(x for x,y in points)
    miny, maxy = min(y for x,y in points), max(y for x,y in points)
    scale = min(920/max(maxx-minx,1),620/max(maxy-miny,1))
    seam_data = [{"mm": p["points"], "screen": [[round((x-minx)*scale+20,2),round((maxy-y)*scale+20,2)] for x,y in p["points"]]} for p in result["paths"]]
    data_tag = '<script id="seam-data" type="application/json">' + json.dumps(seam_data).replace('<','\\u003c') + '</script>'
    data_tag += '<input type="hidden" id="seam-scale" value="' + str(scale) + '">'
    return data_tag + '<div class="part-layout"><div class="preview">' + labeled_preview(result) + '</div><div class="part-sidebar"><h3>Parça eşleştirme</h3><p id="selected-piece">Çizgiye dokunarak seçin</p>' + "".join(rows) + '<label>Parçayı seç <select id="piece-picker">' + ''.join('<option value="' + str(i) + '">#' + str(i+1) + ' · ' + html_escape(p['layer']) + '</option>' for i,p in enumerate(result['paths'])) + '</select></label><div style="border-top:1px solid #ddd;padding-top:12px"><h3>Dikiş kenarı karşılaştırma</h3><p>Konturu seçin, ardından kenarın iki uç noktasına dokunun. İkinci parçada tekrarlayın. DXF mm biriminde olmalıdır.</p><label>Başlangıç <select id="seam-start"></select></label><label>Bitiş <select id="seam-end"></select></label><button type="button" id="seam-add">Bu kenarı kaydet</button><p id="seam-info">İlk konturu seçin.</p><button type="button" id="seam-reset">Sıfırla</button><button type="button" id="seam-adjust">İkinci kenarı uyumla</button><p>Kontur düzeltmesi yaklaşık geometrik işlemdir; üretim kalıbı değildir.</p></div><div id="front-edit" hidden><strong>Ön orta genişlik denemesi</strong><p>Gri: orijinal; mavi: değişen çizim. Üretim kalıbı değildir.</p><input id="front-change" type="range" min="-20" max="20" value="0" step="1"><output id="front-change-value">0 mm</output></div><button type="button" id="export-labels">Eşleştirmeyi indir (JSON)</button></div></div>' + script

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
 activeIndex=i;
 root.querySelectorAll('.seam-preview').forEach(n=>n.remove());
 seamInfo.textContent='Parça seçildi. Kenar üzerinde basılı tutup sürükleyin.';
}
function showHighlight(i,a,b){
 const pts=seamShapes[i].screen.slice(a,b+1);
 const line=document.createElementNS('http://www.w3.org/2000/svg','polyline');
 line.setAttribute('points',pts.map(p=>p.join(',')).join(' '));
 line.setAttribute('fill','none');line.setAttribute('stroke','#16a34a');line.setAttribute('stroke-width','5');line.setAttribute('class','seam-highlight');
 line.style.pointerEvents='none';root.appendChild(line);
}
function closestPoint(e,i){
 const matrix=root.getScreenCTM();if(!matrix)return -1;
 const p=root.createSVGPoint();p.x=e.clientX;p.y=e.clientY;
 const local=p.matrixTransform(matrix.inverse());
 let best=-1,dist=Infinity;
 seamShapes[i].screen.forEach((v,j)=>{const d=Math.hypot(v[0]-local.x,v[1]-local.y);if(d<dist){dist=d;best=j;}});
 return best;
}
function dragPreview(i,a,b){
 root.querySelectorAll('.seam-preview').forEach(n=>n.remove());
 if(a===b||a<0||b<0)return;
 const pts=seamShapes[i].screen.slice(Math.min(a,b),Math.max(a,b)+1);
 const line=document.createElementNS('http://www.w3.org/2000/svg','polyline');
 line.setAttribute('points',pts.map(p=>p.join(',')).join(' '));
 line.setAttribute('fill','none');line.setAttribute('stroke','#f59e0b');line.setAttribute('stroke-width','5');
 line.setAttribute('class','seam-preview');line.style.pointerEvents='none';root.appendChild(line);
}
function sampledEdge(edge,count=25){
 const source=seamShapes[edge.index].mm.slice(edge.a,edge.b+1);
 const distances=[0];
 for(let i=1;i<source.length;i++)distances.push(distances[i-1]+Math.hypot(source[i][0]-source[i-1][0],source[i][1]-source[i-1][1]));
 const total=distances[distances.length-1];
 if(total<=0)return [];
 return Array.from({length:count},(_,k)=>{
  const at=total*k/(count-1);let j=1;
  while(j<distances.length-1&&distances[j]<at)j++;
  const span=distances[j]-distances[j-1],t=span?(at-distances[j-1])/span:0;
  return [source[j-1][0]+(source[j][0]-source[j-1][0])*t,source[j-1][1]+(source[j][1]-source[j-1][1])*t];
 });
}
function curvatureComparison(first,second){
 const a=sampledEdge(first),b=sampledEdge(second);
 if(a.length!==25||b.length!==25)return null;
 function turnProfile(pts){
  const angles=[];
  for(let i=1;i<pts.length-1;i++){
   const u=[pts[i][0]-pts[i-1][0],pts[i][1]-pts[i-1][1]];
   const v=[pts[i+1][0]-pts[i][0],pts[i+1][1]-pts[i][1]];
   angles.push(Math.atan2(u[0]*v[1]-u[1]*v[0],u[0]*v[0]+u[1]*v[1]));
  }
  return angles;
 }
 const aa=turnProfile(a),bb=turnProfile(b),reversed=turnProfile([...b].reverse());
 const score=other=>aa.reduce((sum,v,i)=>sum+Math.abs(v-other[i]),0)/aa.length*180/Math.PI;
 return Math.min(score(bb),score(reversed));
}
function renderSeamComparison(){
 const panel=document.getElementById('seam-comparison');
 if(!panel)return;
 if(!seamEdges.length){panel.hidden=true;panel.replaceChildren();return;}
 panel.hidden=false;panel.replaceChildren();
 const names=seamEdges.map(v=>seamShapes[v.index].name||('Parça '+(v.index+1)));
 const line=(label,value)=>{const p=document.createElement('p');const strong=document.createElement('strong');strong.textContent=label+' ';p.append(strong,document.createTextNode(value));panel.appendChild(p);};
 line('1. kenar — '+names[0]+':',seamEdges[0].mm.toFixed(1)+' mm');
 if(seamEdges.length===1){line('Durum:','İkinci kenarı seçin.');return;}
 const first=seamEdges[0],second=seamEdges[1],diff=second.mm-first.mm;
 const pct=Math.abs(diff)/first.mm*100;
 line('2. kenar — '+names[1]+':',second.mm.toFixed(1)+' mm');
 line('Mutlak fark:',Math.abs(diff).toFixed(1)+' mm');
 line('İlk kenara göre fark:',pct.toFixed(2)+'%');
 line('Sonuç:',Math.abs(diff)<0.05?'Uzunluklar ölçüm hassasiyetinde eşit.':diff>0?names[1]+' kenarı '+Math.abs(diff).toFixed(1)+' mm daha uzun.':names[1]+' kenarı '+Math.abs(diff).toFixed(1)+' mm daha kısa.');
 const curvature=curvatureComparison(first,second);
 if(curvature!==null){
  line('Eğri karşılaştırması:',curvature.toFixed(1)+'° ortalama yön değişimi farkı (yaklaşık).');
  line('Yorum:',curvature<3?'Eğrilerin dönüş dağılımı benzer.':curvature<8?'Eğrilerin dönüş dağılımında farklılık var.':'Eğrilerin dönüş dağılımı belirgin farklı; kalıpçı kontrolü gerekli.');
 }
 const note=document.createElement('small');note.textContent='Eğri karşılaştırması örneklenmiş yön değişimi analizidir; dikiş uyumu garantisi değildir. Dikiş payı, çıtlar ve kalıp doğruluğu kontrol edilmemiştir.';panel.appendChild(note);
}
function finishDrag(i,a,b){
 root.querySelectorAll('.seam-preview').forEach(n=>n.remove());
 if(a===b||a<0||b<0){seamInfo.textContent='Çizgi boyunca sürükleyerek bir kenar seçin.';return;}
 const lo=Math.min(a,b),hi=Math.max(a,b),mm=seamLength(seamShapes[i].mm,lo,hi);
 if(mm<=0)return;
 seamEdges.push({index:i,a:lo,b:hi,mm});
 showHighlight(i,lo,hi);
 renderSeamComparison();
 seamInfo.textContent=seamEdges.length===1?'İlk kenar '+mm.toFixed(1)+' mm. İkinci parçaya geçin.':'İki kenar '+seamEdges[0].mm.toFixed(1)+' / '+mm.toFixed(1)+' mm. Fark: '+Math.abs(seamEdges[0].mm-mm).toFixed(1)+' mm.';
}
document.getElementById('seam-reset').addEventListener('click',()=>{
 seamEdges=[];seamPicked=[];renderSeamComparison();root.querySelectorAll('.seam-marker,.seam-highlight,.seam-preview').forEach(n=>n.remove());seamInfo.textContent='İlk parçayı seçin.';
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
function choose(i){seamSelect(i);document.getElementById('piece-picker').value=String(i);paths.forEach((p,j)=>p.style.strokeWidth=j===i?'4':'1.4');selected.textContent='Seçili çizim: #'+(i+1);document.querySelector('[data-label="'+i+'"]').focus({preventScroll:true});}
paths.forEach((p,i)=>p.addEventListener('pointerdown',e=>beginDrag(e,i)));
document.getElementById('piece-picker').addEventListener('change',e=>choose(Number(e.target.value)));
let dragging=null;
function beginDrag(e,i){
 if(seamEdges.length>=2||e.button!==0)return;
 e.preventDefault();
 if(activeIndex!==i)choose(i);
 const start=closestPoint(e,i);if(start<0)return;
 dragging={index:i,start,end:start,pointer:e.pointerId};
 root.setPointerCapture(e.pointerId);
 seamInfo.textContent='Sürüklediğiniz kenar turuncu renkle gösteriliyor.';
}
root.addEventListener('pointermove',e=>{
 if(!dragging||dragging.pointer!==e.pointerId)return;
 dragging.end=closestPoint(e,dragging.index);
 dragPreview(dragging.index,dragging.start,dragging.end);
});
root.addEventListener('pointerup',e=>{
 if(!dragging||dragging.pointer!==e.pointerId)return;
 const d=dragging;dragging=null;
 const end=closestPoint(e,d.index);
 if(root.hasPointerCapture(e.pointerId))root.releasePointerCapture(e.pointerId);
 finishDrag(d.index,d.start,end);
});
root.addEventListener('pointercancel',()=>{dragging=null;root.querySelectorAll('.seam-preview').forEach(n=>n.remove());});
const hits=paths.map((p,i)=>{const h=p.cloneNode(false);h.removeAttribute('id');h.removeAttribute('data-index');h.setAttribute('stroke','transparent');h.setAttribute('stroke-width','18');h.setAttribute('fill','none');h.style.cursor='pointer';h.addEventListener('pointerdown',e=>beginDrag(e,i));p.parentNode.insertBefore(h,p);return h;});
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
    seam_data = [{"name": p["layer"], "mm": p["points"], "screen": [[round((x-minx)*scale+20,2),round((maxy-y)*scale+20,2)] for x,y in p["points"]]} for p in result["paths"]]
    data_tag = '<script id="seam-data" type="application/json">' + json.dumps(seam_data).replace('<','\\u003c') + '</script>'
    data_tag += '<input type="hidden" id="seam-scale" value="' + str(scale) + '">'
    return data_tag + '<div class="part-layout"><div class="preview">' + labeled_preview(result) + '</div><div class="part-sidebar"><h3>Parça eşleştirme</h3><p id="selected-piece">Çizgiye dokunarak seçin</p>' + "".join(rows) + '<label>Parçayı seç <select id="piece-picker">' + ''.join('<option value="' + str(i) + '">#' + str(i+1) + ' · ' + html_escape(p['layer']) + '</option>' for i,p in enumerate(result['paths'])) + '</select></label><div style="border-top:1px solid #ddd;padding-top:12px"><h3>Dikiş kenarı karşılaştırma</h3><p>Parçayı seçin, çizginin başında fareye basılı tutun ve kenarın sonuna sürükleyip bırakın. İkinci parçada tekrarlayın.</p><p id="seam-info">İlk konturu seçin.</p><div id="seam-comparison" hidden style="border:1px solid #cbd5e1;border-radius:10px;padding:12px;margin:10px 0;background:#f8fafc"></div><button type="button" id="seam-reset">Sıfırla</button><button type="button" id="seam-adjust">İkinci kenarı uyumla</button><p>Kontur düzeltmesi yaklaşık geometrik işlemdir; üretim kalıbı değildir.</p></div><div id="front-edit" hidden><strong>Ön orta genişlik denemesi</strong><p>Gri: orijinal; mavi: değişen çizim. Üretim kalıbı değildir.</p><input id="front-change" type="range" min="-20" max="20" value="0" step="1"><output id="front-change-value">0 mm</output></div><button type="button" id="export-labels">Eşleştirmeyi indir (JSON)</button></div></div>' + script

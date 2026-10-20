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
const colors={'on_orta':'#0d9488','on_kup':'#a855f7','on_yan':'#2563eb','arka_orta':'#dc2626','arka_yan':'#e8793e','astar':'#16a34a','etek':'#b45309','diger':'#64748b'};
function choose(i){paths.forEach((p,j)=>p.style.strokeWidth=j===i?'4':'1.4');selected.textContent='Seçili çizim: #'+(i+1);document.querySelector('[data-label="'+i+'"]').focus({preventScroll:true});}
paths.forEach((p,i)=>p.addEventListener('click',()=>choose(i)));
labels.forEach(s=>s.addEventListener('change',()=>{paths[Number(s.dataset.label)].style.stroke=colors[s.value]||'#2563a6';}));
document.getElementById('export-labels').addEventListener('click',()=>{
 const payload={version:1,unit:document.getElementById('cad-unit').dataset.unit,labels:[...labels].map(s=>({index:Number(s.dataset.label),label:s.value}))};
 const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});
 const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='moli-kalip-parca-eslestirme.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
});
})();
</script>"""
    return '<div class="part-layout"><div class="preview">' + labeled_preview(result) + '</div><div class="part-sidebar"><h3>Parça eşleştirme</h3><p id="selected-piece">Çizgiye dokunarak seçin</p>' + "".join(rows) + '<button type="button" id="export-labels">Eşleştirmeyi indir (JSON)</button></div></div>' + script

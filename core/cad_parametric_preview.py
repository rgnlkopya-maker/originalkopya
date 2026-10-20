"""Experimental five-panel bodice geometry. Not production-ready grading."""
import math
from html import escape

def render_bodice(measurements):
    bust=float(measurements["bust"])
    waist=float(measurements["waist"])
    length=float(measurements["length"])
    if not (65 <= bust <= 145 and 45 <= waist <= 135 and 25 <= length <= 65):
        raise ValueError("Ölçüler geçerli aralıkta değil.")
    ease_bust=4
    ease_waist=3
    # Four quarter-body zones split into five visible panels.
    widths_b=[(bust+ease_bust)*r for r in (.115,.135,.135,.115,.0)]
    widths_w=[(waist+ease_waist)*r for r in (.115,.135,.135,.115,.0)]
    names=["Ön orta","Ön yan","Arka yan","Arka orta"]
    svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 950 550" style="width:100%;background:#f8fafc;border:1px solid #ddd">']
    x=28
    for i,name in enumerate(names):
        top=widths_b[i]*5
        bottom=widths_w[i]*5
        p=f"M {x:.1f} 80 Q {x+top/2:.1f} {60 if i==1 else 80} {x+top:.1f} 80 L {x+bottom:.1f} {80+length*5:.1f} L {x:.1f} {80+length*5:.1f} Z"
        svg.append(f'<path d="{p}" fill="#dbeafe" stroke="#174a9d" stroke-width="2"/>')
        svg.append(f'<text x="{x:.1f}" y="{95+length*5:.1f}" font-size="13">{escape(name)}</text>')
        x+=max(top,bottom)+45
    # Fifth piece is an illustrative center-front facing, not an independently drafted production piece.
    w=widths_b[0]*5
    svg.append(f'<path d="M {x:.1f} 80 L {x+w:.1f} 80 L {x+w:.1f} 120 L {x:.1f} 120 Z" fill="#dcfce7" stroke="#15803d" stroke-width="2"/>')
    svg.append(f'<text x="{x:.1f}" y="142" font-size="13">Ön pervaz (temsili)</text>')
    svg.append('</svg>')
    return ''.join(svg)

"""Read-only DXF preview engine. Does not generate production patterns."""
import io
import math
from collections import Counter

MAX_BYTES = 3 * 1024 * 1024
MAX_ENTITIES = 3000
MAX_POINTS = 60000
SUPPORTED = {"LWPOLYLINE", "POLYLINE", "LINE", "ARC", "CIRCLE", "SPLINE", "ELLIPSE"}

def parse_pattern_dxf(data):
    if not data or len(data) > MAX_BYTES:
        raise ValueError("DXF boş veya 3 MB sınırını aşıyor.")
    if b"\x00" in data[:1000]:
        raise ValueError("Şimdilik yalnızca ASCII DXF destekleniyor.")
    try:
        import ezdxf
        from ezdxf.path import make_path
    except ImportError as exc:
        raise ValueError("DXF okuyucu kurulu değil.") from exc
    try:
        source = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        source = data.decode("cp1252")
    try:
        doc = ezdxf.read(io.StringIO(source))
    except Exception as exc:
        raise ValueError("DXF dosyası okunamadı.") from exc
    entities = list(doc.modelspace())
    if len(entities) > MAX_ENTITIES:
        raise ValueError("Dosyada çok fazla çizim öğesi var.")
    paths, counts, total = [], Counter(), 0
    for entity in entities:
        kind = entity.dxftype()
        if kind not in SUPPORTED:
            continue
        try:
            points = [(float(v.x), float(v.y)) for v in make_path(entity).flattening(distance=0.25, segments=8)]
            if len(points) < 2 or any(not (math.isfinite(x) and math.isfinite(y) and abs(x)<1e7 and abs(y)<1e7) for x,y in points):
                continue
            total += len(points)
            if total > MAX_POINTS:
                raise ValueError("Çizim önizleme sınırını aşıyor.")
            paths.append({"points":points, "layer":str(entity.dxf.layer)[:80], "type":kind})
            counts[kind] += 1
        except ValueError:
            raise
        except Exception:
            continue
    if not paths:
        raise ValueError("Desteklenen çizgi veya kontur bulunamadı.")
    return {"paths":paths, "counts":dict(counts), "units":int(doc.header.get("$INSUNITS",0)),
            "points":total, "layers":sorted({p["layer"] for p in paths})}

def preview_svg(result):
    points = [v for shape in result["paths"] for v in shape["points"]]
    minx,maxx = min(x for x,y in points),max(x for x,y in points)
    miny,maxy = min(y for x,y in points),max(y for x,y in points)
    scale = min(920/max(maxx-minx,1),620/max(maxy-miny,1))
    width,height = (maxx-minx)*scale+40,(maxy-miny)*scale+40
    shapes = []
    for shape in result["paths"]:
        d = "M " + " L ".join(f"{(x-minx)*scale+20:.2f},{(maxy-y)*scale+20:.2f}" for x,y in shape["points"])
        shapes.append(f'<path d="{d}" fill="none" stroke="#2058a8" stroke-width="1.2" stroke-linejoin="round"/>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.1f} {height:.1f}" role="img" aria-label="DXF çizimi">' + "".join(shapes) + "</svg>"

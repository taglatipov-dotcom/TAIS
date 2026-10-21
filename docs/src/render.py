import sys, math
from pathlib import Path
# Картинки построений для документации: python gallery.py (из папки docs/src) → a/g_*.svg
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'Backend'))
from tais.generator.scheme import run_scheme, _shift

COL = {'post':'#24527e','ledger':'#4f8fc6','diagonal':'#d0473b','toeboard':'#c98a1c','ladder':'#2e9e6b',
       'jack':'#3b3f46','starter':'#24527e'}
SW = {'post':2.4,'ledger':1.25,'diagonal':1.3,'toeboard':2.2,'ladder':1.8,'jack':2.8,'starter':2.4}
def proj(p, az, el):
    x,y,z=p; a=math.radians(az); e=math.radians(el)
    X = x*math.cos(a) + y*math.sin(a)
    Yd = -x*math.sin(a) + y*math.cos(a)
    return X, -(z*math.cos(e) + Yd*math.sin(e)), Yd

def prims_of(els, az, el, ghost=False):
    out=[]
    for e in els:
        k=e['kind']
        if k in ('deck','hatch'):
            if e.get('poly'): pts=e['poly']
            elif e.get('box'):
                x0,y0,dx,dy=e['box']; pts=[[x0,y0],[x0+dx,y0],[x0+dx,y0+dy],[x0,y0+dy]]
            else: continue
            P=[proj((p[0],p[1],e['z']),az,el) for p in pts]
            col = '#e98a7a' if k=='hatch' else ('#9aa6b2' if e['article'].startswith('U00141') else '#eab84c')
            out.append((max(p[2] for p in P), 'poly', P, '#c7ccd3' if ghost else col, ghost))
        elif e.get('seg'):
            a,b=e['seg']; A=proj(a,az,el); B=proj(b,az,el)
            out.append(((A[2]+B[2])/2, 'line', (A,B), '#c3c8cf' if ghost else COL.get(k,'#888'), ghost, k))
    return out

def svg(items, path=None, W=900, H=700, az=-28, el=24, pad=24, lw=1.0, ghost=None, plan=False):
    res = run_scheme(items)
    if plan: az, el = 0, 90
    prims = prims_of(res['elements'], az, el)
    if ghost:
        g = run_scheme(ghost['items'])
        gel = [_shift(e, ghost.get('dx',0), ghost.get('dy',0)) for e in g['elements']]
        prims += prims_of(gel, az, el, ghost=True)
    xs=[q[0] for p in prims for q in p[2]]; ys=[q[1] for p in prims for q in p[2]]
    mnx,mxx,mny,mxy=min(xs),max(xs),min(ys),max(ys)
    s=min((W-2*pad)/(mxx-mnx),(H-2*pad)/(mxy-mny))
    ox=pad+((W-2*pad)-(mxx-mnx)*s)/2; oy=pad+((H-2*pad)-(mxy-mny)*s)/2
    T=lambda q: (ox+(q[0]-mnx)*s, oy+(q[1]-mny)*s)
    prims.sort(key=lambda p:-p[0])
    o=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">']
    for p in prims:
        if p[1]=='poly':
            pts=" ".join("%.1f,%.1f"%T(q) for q in p[2])
            o.append(f'<polygon points="{pts}" fill="{p[3]}" fill-opacity="{0.35 if p[4] else 0.6}" stroke="{p[3]}" stroke-width="{0.5*lw:.2f}"/>')
        else:
            (x1,y1),(x2,y2)=T(p[2][0]),T(p[2][1])
            w=SW.get(p[5],1.2)*lw*(0.6 if p[4] else 1)
            o.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{p[3]}" stroke-width="{w:.2f}" stroke-linecap="round"/>')
    o.append('</svg>')
    txt='\n'.join(o)
    if path: open(path,'w').write(txt)
    return res, txt

import sys, json; sys.path.insert(0,'.')
from render import svg
F=lambda **k: {'kind':'facade','intermediate_decks':True,'entrance':True,**k}
G = {
 'tower':      ([{'kind':'auto','length':3,'width':2,'height':8.2}], {}),
 'facade':     ([{'kind':'auto','length':12,'width':1,'height':10.2}], {'lw':0.9}),
 'low':        ([{'kind':'auto','length':3,'width':2,'height':3.2}], {}),
 'facade_low': ([{'kind':'auto','length':6,'width':1,'height':4.2}], {}),
 'tower_wid':  ([{'kind':'tower','length':3,'width':2,'height':8.2},{'kind':'widening','length':3,'width':1,'height':8.2,'attach_to':1,'side':'y0','offset':0}], {'az':-40}),
 'facade_wid_end': ([F(length=9,width=1,height=8.2),{'kind':'widening','length':1,'width':1.5,'height':6.2,'attach_to':1,'side':'x1','offset':0}], {}),
 'facade_balc':([F(length=9,width=1,height=8.2),{'kind':'balcony','length':3,'width':1,'height':0,'attach_to':1,'side':'y0','offset':3}], {}),
 'wid_balc':   ([F(length=9,width=1,height=10.2),{'kind':'widening','length':3,'width':1,'height':4.2,'attach_to':1,'side':'y0','offset':3},{'kind':'balcony','length':3,'width':1,'height':0,'attach_to':1,'side':'y0','offset':3}], {}),
 'wid_alone':  ([{'kind':'widening','length':6,'width':1,'height':6.2}], {'ghost':{'items':[F(length=6,width=1,height=6.2,entrance=False)],'dy':-1000},'az':152}),
 'balc_alone': ([{'kind':'balcony','length':6,'width':1,'height':8.2}], {'ghost':{'items':[F(length=6,width=1,height=8.2,entrance=False)],'dy':-1000},'az':152}),
 'radial':     ([{'kind':'radial','length':24,'width':1,'height':6.2}], {'el':30}),
 'radial_wid': ([{'kind':'radial','length':30,'width':1.5,'height':8,'widening':True,'widening_width':1}], {'el':34,'lw':0.75}),
 'radial_big': ([{'kind':'radial','length':60,'width':1,'height':10.2}], {'el':30,'lw':0.6}),
 'radial_plan':([{'kind':'radial','length':24,'width':1,'height':6.2}], {'plan':True,'H':900,'W':900}),
 'radial_wid_plan':([{'kind':'radial','length':30,'width':1.5,'height':8,'widening':True,'widening_width':1}], {'plan':True,'H':900,'W':900,'lw':0.8}),
 'multi':      ([{'kind':'auto','length':3,'width':2,'height':6.2},{'kind':'auto','length':9,'width':1,'height':8.2}], {'az':-68,'el':20}),
}
only=sys.argv[1:]
for k,(items,kw) in G.items():
    if only and k not in only: continue
    r,_=svg(items, f'a/g_{k}.svg', **kw); print(k, len(r['elements']))

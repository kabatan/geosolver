"""Plot saved measurements as SVG using the standard library; no searches.

The specified Python has no plotting package. ImageMagick renders PNG previews.
"""
import html
import json
import math
from pathlib import Path
import experiment as e

OUT = Path(__file__).resolve().parent
inputs = json.loads((OUT / 'inputs.json').read_text())
summary = json.loads((OUT / 'summary.json').read_text())
e.check_lock()
COLORS = {'F':'#d6d9dd', 'R0':'#1768ac', 'R1':'#ed8b2c', 'merged':'#23916c', 'U':'#111111'}

class SVG:
    def __init__(self,w,h):
        self.p=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">','<style>text{font-family:DejaVu Sans,sans-serif;fill:#16283a}</style>','<rect width="100%" height="100%" fill="white"/>']
    def add(self,s): self.p.append(s)
    def text(self,x,y,s,size=14,anchor='start',extra=''):
        self.add(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" {extra}>{html.escape(str(s))}</text>')
    def line(self,x,y,a,b,color='#657587',width=1,extra=''):
        self.add(f'<line x1="{x}" y1="{y}" x2="{a}" y2="{b}" stroke="{color}" stroke-width="{width}" {extra}/>')
    def rect(self,x,y,w,h,color,extra=''):
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{color}" {extra}/>')
    def save(self,name): (OUT/name).write_text('\n'.join(self.p+['</svg>\n']))

fig=SVG(1280,1430)
fig.text(640,36,'Finite-budget LM classifications',25,'middle')
fig.text(640,62,'32 x 32 fixed starts per problem; F pools all non-hits',16,'middle')
columns=[(80,'X'),(320,'X'),(320,'G'),(320,'T')]
names={'X':'Coordinate branches','G':'Geometric classes','T':'Target classes'}
for col,(cap,label) in enumerate(columns):
    fig.text(190+297*col,93,f'{label}: {names[label]} | K={cap}',15,'middle')
for row,inp in enumerate(inputs):
    top=140+row*310
    fig.text(70,top-17,inp['id'],17,extra='font-weight="bold"')
    for col,(cap,label) in enumerate(columns):
        left,size=70+col*297,240
        clip=f'clip-{row}-{col}'
        fig.add(f'<defs><clipPath id="{clip}"><rect x="{left}" y="{top}" width="{size}" height="{size}"/></clipPath></defs>')
        fig.add(f'<g clip-path="url(#{clip})" shape-rendering="crispEdges">')
        mapping={**COLORS,'T0':COLORS['merged'],'G0':COLORS['merged'] if inp['main'] else COLORS['R0'],'G1':COLORS['R1']}
        for r in e.read_records(inp['id'],cap):
            x0=(r['i']+.37-.5)/32
            y1=(r['j']+.61+.5)/32
            fig.rect(left+x0*size,top+(1-y1)*size,size/32,size/32,mapping[r[label]])
        fig.add('</g>')
        fig.rect(left,top,size,size,'none','stroke="#657587"')
        for tick in (0,.5,1):
            fig.text(left+tick*size,top+size+18,f'{tick:g}',12,'middle')
            fig.text(left-8,top+(1-tick)*size+4,f'{tick:g}',12,'end')
        fig.text(left+size/2,top+size+39,inp['var_names'][0]+' (normalized)',13,'middle')
        fig.text(left-38,top+size/2,inp['var_names'][1]+' (normalized)',13,'middle',f'transform="rotate(-90 {left-38} {top+size/2})"')
for x,color,label in [(90,COLORS['R0'],'Branch 0'),(320,COLORS['R1'],'Branch 1'),(550,COLORS['merged'],'Merged valid branches'),(920,COLORS['F'],'F: all non-hits')]:
    fig.rect(x,1380,19,19,color)
    fig.text(x+28,1395,label,15)
fig.save('basin-maps.svg')

fig=SVG(1340,930)
fig.text(670,37,'Finite-scale disagreement between starts',25,'middle')
fig.text(670,64,'Four measured scales; slopes are not certified dimensions',16,'middle')
for x,label,color,dashed in [(150,'X, K=80',COLORS['R0'],False),(430,'X, K=320',COLORS['R0'],True),(710,'T, K=80',COLORS['merged'],False),(990,'T, K=320',COLORS['merged'],True)]:
    fig.line(x,92,x+45,92,color,2.5,'stroke-dasharray="8 5"' if dashed else '')
    if dashed: fig.rect(x+18,88,8,8,'white',f'stroke="{color}" stroke-width="2"')
    else: fig.add(f'<circle cx="{x+22}" cy="92" r="4" fill="{color}"/>')
    fig.text(x+57,97,label,15)
for index,metric in enumerate(summary['metrics']):
    left,top,width,height=110+(index%2)*650,155+(index//2)*375,480,260
    fig.text(left+width/2,top-17,metric['id'],18,'middle','font-weight="bold"')
    def xp(v): return left+math.log2(v/(1/32))/3*width
    def yp(v): return top-math.log10(v)/2*height
    for v in (.01,.03,.1,.3,1):
        fig.line(left,yp(v),left+width,yp(v),'#e0e6eb')
        fig.text(left-10,yp(v)+4,f'{v:g}',13,'end')
    for v,label in [(1/32,'1/32'),(1/16,'1/16'),(1/8,'1/8'),(1/4,'1/4')]:
        fig.line(xp(v),top,xp(v),top+height,'#e0e6eb')
        fig.text(xp(v),top+height+22,label,14,'middle')
    fig.line(left,top,left,top+height)
    fig.line(left,top+height,left+width,top+height)
    fig.text(left+width/2,top+height+48,'Start separation / box width (log scale)',15,'middle')
    fig.text(left-65,top+height/2,'Fraction with different labels (log)',14,'middle',f'transform="rotate(-90 {left-65} {top+height/2})"')
    for cap in (80,320):
        for label,color in [('X',COLORS['R0']),('T',COLORS['merged'])]:
            curve=metric['caps'][str(cap)]['labels'][label]['curve']
            if not all(p['U']>0 for p in curve): continue
            pts=[(xp(p['epsilon']),yp(p['U'])) for p in curve]
            coords=' '.join(f'{x},{y}' for x,y in pts)
            dash='stroke-dasharray="8 5"' if cap==320 else ''
            fig.add(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2.4" {dash}/>')
            for x,y in pts:
                if cap==320: fig.rect(x-4,y-4,8,8,'white',f'stroke="{color}" stroke-width="2"')
                else: fig.add(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>')
    if metric['main']: fig.text(left+13,top+height-14,'G = T',14)
    else:
        fig.text(left+13,top+25,'T = 0 at every scale (omitted on log axis)',14)
        fig.text(left+13,top+46,'G = X: noncongruent control',14)
fig.text(670,898,'The same starts are used at K=80 and K=320; coincident curves overlap.',15,'middle')
fig.save('uncertainty-curves.svg')
print('wrote basin-maps.svg and uncertainty-curves.svg; no new local searches')

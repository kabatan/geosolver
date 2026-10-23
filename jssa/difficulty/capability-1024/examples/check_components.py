"""Saturate only to diagnose extra components; no original scores are changed."""
import pathlib, subprocess,os,resource
O=pathlib.Path(__file__).resolve().parent/'evidence'
def lim():
 os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});resource.setrlimit(resource.RLIMIT_AS,(1536<<20,1536<<20));resource.setrlimit(resource.RLIMIT_CPU,(20,20))
for id,extra in [('AIME-2005-I-01','''LIB "elim.lib";
ideal J=I;
poly f;
int i;int j;
list xs=30-x11,x12,x13,x14,x15,x16;
list ys=0,x17,x18,x19,x20,x21;
for(i=1;i<=6;i++){for(j=i+1;j<=6;j++){if(j-i!=1 && j-i!=5){f=(xs[i]-xs[j])^2+(ys[i]-ys[j])^2;J=sat(J,ideal(f));}}}
print("DISTINCT_DIM");print(dim(std(J)));print(J);
'''),('HMMT-2019-FEB-GUTS-17','''LIB "elim.lib";
ideal J=sat(I,ideal(x15));print("NONZERO_S_DIM");print(dim(std(J))); print(J);
''')]:
 base=(O/(id+'.sing')).read_text().replace('quit;','')
 p=O/(id+'.components.sing');p.write_text(base+extra+'\nquit;\n')
 try:
  r=subprocess.run(['/tmp/q6-tools/bin/Singular','-q',str(p)],text=True,capture_output=True,timeout=23,preexec_fn=lim);log=r.stdout+r.stderr
 except subprocess.TimeoutExpired as e:log=(e.stdout or b'').decode()+'TIMEOUT'
 (O/(id+'.components.log')).write_text(log);print(id,log[-1800:],flush=True)

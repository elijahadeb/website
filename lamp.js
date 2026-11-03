/* lamp.js — the hero ----------------------------------------------------------------
   a bare bulb hanging out in the room, the wall behind it, and moths. drawn as
   text on a character grid, the way the site draws everything; written from scratch.

   flight follows the 2024 finding (fabian et al., nature communications): moths
   don't aim at light. they keep their backs tilted toward the brightest thing they
   can see. near a point light that rule traps them: they fly across the light
   instead of at it, orbit, stall, and flip over.

   what makes it read as real, and where each piece comes from:
   - wings beat at real rates (a hawk-moth ~30 times a second), far faster than a
     frame, so each frame blends several wing positions: a blurred fan, sharp body.
   - a resting moth shivers its wings to warm up before it can fly (heinrich &
     bartholomew, 1971): about 8 beats a second when cold, rising toward flight.
   - they hit the glass, tumble, drop and recover.
   - characters are picked by shape, not just brightness (after alex harri): each
     cell is sampled at six points and matched to the glyph whose ink sits in the
     same places, so edges come out as / ( _ ' instead of steps.
   - light falls off with distance. a moth between you and the bulb is lit from
     behind: its wings glow through and its edges catch a rim.
   - colour only shows where there is light; in the dark a moth is a shape.
   - every moth casts a shadow by real geometry: huge and soft near the bulb,
     crisp when it sits on the wall (penumbra = light size x gap / distance).
   - glare and a starburst around the bulb (spencer et al., 1995), dimmed when a
     moth crosses in front of it.
   the cast is real moths that come to lights: elephant hawk-moth, rosy maple,
   luna, garden tiger. */
/* usage: DSLamp(canvas, {hero, hint, pin, clear, keep}) — hero takes the pointer, hint and pin
   are text elements, clear is the copy column (the bulb hangs beside it) and keep
   lists the blocks of copy a landing moth stays off. returns {setTheme, step, render}; setTheme after a theme change. */
(function(){
"use strict";
window.DSLamp=function(cv,opt){
opt=opt||{};
var doc=document,root=doc.documentElement;
var reduced=matchMedia("(prefers-reduced-motion: reduce)").matches;
var coarse=matchMedia("(hover: none)").matches;
var hero=opt.hero||cv.parentNode,ctx=cv.getContext("2d",{alpha:false});
var hintEl=opt.hint||null,pinEl=opt.pin||null,clearEl=opt.clear||null,copyR=0;
var W=0,H=0,DPR=1,CW=8,CH=12,COLS=0,ROWS=0,T=0,FONT="monospace";
var tex=doc.createElement("canvas"),zones=[],stage=false;
var P=null,caughtN=0;

function clamp(v,a,b){return v<a?a:v>b?b:v}
function lerp(a,b,t){return a+(b-a)*t}
function rnd(a,b){return a+Math.random()*(b-a)}
function smooth(a,b,x){var t=clamp((x-a)/(b-a),0,1);return t*t*(3-2*t)}
function hash(x,y,z){var h=Math.imul(x|0,374761393)^Math.imul(y|0,668265263)^Math.imul(z|0,1442695041);
  h=Math.imul(h^(h>>>13),1274126177);h^=h>>>16;return (h>>>0)/4294967296}
function angDiff(a,b){var d=(b-a)%6.283185307;if(d>Math.PI)d-=6.283185307;if(d<-Math.PI)d+=6.283185307;return d}
function mix(a,b,t){return [a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t]}
function segDist(x,y,ax,ay,bx,by){var dx=bx-ax,dy=by-ay,t=clamp(((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy),0,1);
  return Math.hypot(x-ax-dx*t,y-ay-dy*t)}

/* night, and a cream daytime version of the same wall. the wall has a colour of
   its own (albedo); the light is multiplied into it every frame. moths are
   nocturnal: by day most of them sit on the wall until the bulb comes close. */
function pageColor(){var v=getComputedStyle(root).getPropertyValue("--bg").trim(),m=/^#([0-9a-f]{6})$/i.exec(v);
  return m?[parseInt(m[1].slice(0,2),16),parseInt(m[1].slice(2,4),16),parseInt(m[1].slice(4,6),16)]:null}
function palette(){
  var dark=root.getAttribute("data-theme")==="dark";
  P=dark?{dark:true,day:false,wall:[196,190,178],amb:[0.056,0.062,0.08],e0:0.45,warm:[1,0.8,0.58],shadow:0.92,glare:1,
      fill:1,ex:2,grain:"rgba(38,30,22,1)",cord:[150,144,132],specks:[180,172,158]}
    :{dark:false,day:true,wall:[249,247,240],amb:[0.93,0.93,0.92],e0:0.14,warm:[1,0.8,0.58],shadow:0.32,glare:0.5,
      fill:1,ex:2,grain:"rgba(60,52,44,1)",cord:[60,56,52],specks:[40,34,30]};
  P.page=pageColor();
}

/* wing outlines in units of the half-span: u runs tail to head, v from the body out.
   tip: the index of the wing tip, splitting the leading edge from the outer margin */
var WINGS={
  hawk:{tip:4,fore:[[0.10,0.05],[0.17,0.25],[0.15,0.55],[0.08,0.82],[-0.02,1.0],[-0.10,0.97],[-0.16,0.80],
          [-0.24,0.56],[-0.28,0.34],[-0.22,0.10],[-0.04,0.05]],
        hind:[[-0.10,0.06],[-0.16,0.30],[-0.26,0.46],[-0.38,0.50],[-0.48,0.40],[-0.50,0.22],[-0.42,0.08],[-0.28,0.05]]},
  silk:{tip:4,fore:[[0.10,0.05],[0.22,0.28],[0.24,0.58],[0.18,0.86],[0.06,0.98],[-0.08,0.96],[-0.24,0.78],
          [-0.34,0.52],[-0.30,0.24],[-0.16,0.07],[-0.04,0.05]],
        hind:[[-0.08,0.06],[-0.14,0.36],[-0.26,0.62],[-0.42,0.72],[-0.58,0.62],[-0.64,0.40],[-0.56,0.16],[-0.36,0.05]]},
  luna:{tip:4,fore:[[0.10,0.05],[0.22,0.26],[0.26,0.55],[0.22,0.82],[0.14,1.0],[0.04,0.98],[-0.06,0.90],
          [-0.20,0.74],[-0.30,0.50],[-0.27,0.24],[-0.14,0.07],[-0.04,0.05]],
        hind:[[-0.08,0.06],[-0.14,0.32],[-0.24,0.54],[-0.36,0.62],[-0.50,0.56],[-0.70,0.50],[-0.95,0.45],
          [-1.20,0.42],[-1.40,0.43],[-1.50,0.37],[-1.45,0.29],[-1.22,0.29],[-0.96,0.26],[-0.72,0.19],[-0.52,0.10],[-0.30,0.05]]},
  tiger:{tip:4,fore:[[0.10,0.05],[0.21,0.30],[0.21,0.62],[0.13,0.90],[0.02,1.0],[-0.14,0.92],[-0.30,0.68],
          [-0.37,0.42],[-0.25,0.10],[-0.04,0.05]],
        hind:[[-0.06,0.06],[-0.16,0.40],[-0.30,0.66],[-0.46,0.71],[-0.62,0.57],[-0.67,0.34],[-0.55,0.12],[-0.36,0.05]]}
};
/* the garden tiger's cream net: borders between jittered cells */
function net(u,v){var gx=Math.floor(v/0.13),gy=Math.floor((u+0.5)/0.13),d1=9,d2=9;
  for(var i=-1;i<=1;i++)for(var j=-1;j<=1;j++){var cx=gx+i,cy=gy+j;
    var px=(cx+0.15+0.7*hash(cx,cy,91))*0.13,py=(cy+0.15+0.7*hash(cx,cy,92))*0.13-0.5,d=Math.hypot(v-px,(u-py)*1.15);
    if(d<d1){d2=d1;d1=d}else if(d<d2)d2=d}
  return d2-d1}
function eyespot(u,v,cu,cv,ru,rv){var r=Math.hypot((u-cu)/ru,(v-cv)/rv);
  return r<0.45?[222,230,196,0.85]:r<0.62?[234,200,84,0.3]:r<0.8?[40,34,30,0.1]:r<1?[146,74,86,0.2]:null}
var TIGER_SPOTS=[[-0.24,0.42,0.07],[-0.40,0.58,0.07],[-0.52,0.36,0.065],[-0.36,0.22,0.055],[-0.58,0.55,0.045]];

/* four real moths that come to lights. colours are albedo; fore/hind return
   [r,g,b,transmission] in wing space; eL/eO are distances to the leading edge
   and to the outer margin. rest: [fore sweep, fore spread, hind sweep, hind spread] */
var SPECIES=[
 {id:1,name:"elephant hawk-moth",veins:0.1,w:3,wing:"hawk",span:[62,76],hz:30,amp:1.0,glide:false,reach:1.1,u0:-0.86,
  rest:[0.8,0.86,0.52,0.55],
  body:{th:[0.10,0.15,0.105],ab:[-0.02,-0.76,0.098],hd:0.07,col:[124,118,62],stripe:[222,104,150],ant:2},
  fore:function(u,v,eL,eO){var c=v<0.16?[104,100,52]:[124,118,62];
    if(segDist(u,v,-0.02,0.98,-0.22,0.12)<0.034||segDist(u,v,-0.13,0.9,-0.27,0.32)<0.026)c=[222,104,150];
    if(eO<0.035)c=[214,124,160];else if(eL<0.03)c=mix(c,[150,142,84],0.6);
    return [c[0],c[1],c[2],0.2]},
  hind:function(u,v,eL,eO){var c=[214,96,140];if(v<0.22)c=mix([44,30,32],c,v/0.22);
    if(eO<0.03)c=[232,212,204];return [c[0],c[1],c[2],0.36]}},
 {id:2,name:"rosy maple moth",veins:0.05,w:3,wing:"silk",span:[50,62],hz:17,amp:1.1,glide:true,reach:1.1,u0:-0.8,
  rest:[0.42,0.9,0.28,0.75],
  body:{th:[0.09,0.15,0.11],ab:[-0.03,-0.56,0.095],hd:0.072,col:[246,210,82],ant:1,antCol:[196,120,110]},
  fore:function(u,v,eL,eO){var pink=[230,112,160],yel=[246,214,110];
    var t=smooth(0.2,0.3,v)*(1-smooth(0.68,0.8,v+(u+0.1)*0.25)),c=mix(pink,yel,t);
    if(eL<0.04)c=mix(c,pink,0.5);return [c[0],c[1],c[2],0.32]},
  hind:function(u,v,eL,eO){var c=[246,226,164];if(eO<0.08)c=mix(c,[236,150,170],0.55);
    if(v<0.12)c=mix([250,214,96],c,v/0.12);return [c[0],c[1],c[2],0.42]}},
 {id:3,name:"luna moth",veins:0.16,w:1.6,wing:"luna",span:[92,112],hz:9,amp:1.15,glide:true,reach:1.56,u0:-1.58,
  rest:[0.16,1,0.08,1],
  body:{th:[0.09,0.14,0.1],ab:[-0.03,-0.6,0.085],hd:0.066,col:[238,234,224],ant:1,antCol:[200,170,96]},
  fore:function(u,v,eL,eO){var e=eyespot(u,v,-0.03,0.56,0.075,0.07);if(e)return e;
    var c=mix([164,208,124],[192,216,118],smooth(0.4,1,v));
    if(eL<0.045)c=[128,66,86];else if(eO<0.02)c=[214,208,128];return [c[0],c[1],c[2],0.52]},
  hind:function(u,v,eL,eO){var e=eyespot(u,v,-0.34,0.42,0.06,0.06);if(e)return e;
    var c=mix([164,208,124],[214,196,128],smooth(0.8,1.45,-u));
    if(eO<0.02)c=mix(c,[180,120,140],0.6);return [c[0],c[1],c[2],0.55]}},
 {id:4,name:"garden tiger",veins:0.04,w:3,wing:"tiger",span:[64,80],hz:15,amp:1.05,glide:false,reach:1.1,u0:-0.84,
  rest:[0.62,0.72,0.56,0.5],
  body:{th:[0.09,0.135,0.09],ab:[-0.03,-0.64,0.08],hd:0.065,col:[96,62,40],collar:[198,52,40],abCol:[214,94,50],
    bands:true,ant:0},
  fore:function(u,v,eL,eO){var c=net(u,v)<0.05?[234,224,198]:[92,58,38];if(eO<0.025)c=[78,50,34];
    return [c[0],c[1],c[2],0.12]},
  hind:function(u,v,eL,eO){for(var i=0;i<TIGER_SPOTS.length;i++){var s=TIGER_SPOTS[i];
      if(Math.hypot(u-s[0],v-s[1])<s[2])return [26,30,58,0.08]}
    var c=v<0.13?mix([120,44,30],[226,92,44],v/0.13):[226,92,44];return [c[0],c[1],c[2],0.42]}}
];
function pickSpecies(){var t=0,i;for(i=0;i<SPECIES.length;i++)t+=SPECIES[i].w;
  var r=Math.random()*t;for(i=0;i<SPECIES.length;i++){r-=SPECIES[i].w;if(r<=0)return SPECIES[i]}return SPECIES[0]}

/* each wing is baked once into a small texture in wing space: coverage, albedo
   and how much light its scales let through. sampling a wing is then a lookup. */
var TEXN=72;
function inPoly(x,y,p){var c=false;for(var i=0,j=p.length-1;i<p.length;j=i++){
  var xi=p[i][0],yi=p[i][1],xj=p[j][0],yj=p[j][1];
  if((yi>y)!==(yj>y)&&x<(xj-xi)*(y-yi)/(yj-yi)+xi)c=!c}return c}
function lineDist(x,y,p,a,b){var d=9;for(var i=a;i<b;i++)d=Math.min(d,segDist(x,y,p[i][0],p[i][1],p[i+1][0],p[i+1][1]));return d}
function bakeWing(p,tip,fn,veins){
  var x0=9,x1=-9,y0=9,y1=-9,i,j;
  for(i=0;i<p.length;i++){x0=Math.min(x0,p[i][0]);x1=Math.max(x1,p[i][0]);y0=Math.min(y0,p[i][1]);y1=Math.max(y1,p[i][1])}
  x0-=0.01;x1+=0.01;y0-=0.01;y1+=0.01;
  var n=TEXN,cov=new Float32Array(n*n),col=new Float32Array(n*n*3),tr=new Float32Array(n*n),sx=(x1-x0)/n,sy=(y1-y0)/n;
  var closed=p.concat([p[0]]);
  for(j=0;j<n;j++)for(i=0;i<n;i++){var u=x0+(i+0.5)*sx,v=y0+(j+0.5)*sy,c=0;
    for(var s=0;s<4;s++)if(inPoly(u+((s&1)-0.5)*sx*0.5,v+((s>>1)-0.5)*sy*0.5,p))c+=0.25;
    var k=j*n+i;cov[k]=c;if(!c)continue;
    var q=fn(u,v,lineDist(u,v,p,0,tip),lineDist(u,v,closed,tip,closed.length-2));
    var an=Math.atan2(u+0.03,v),vn=Math.abs(((an*6.2)%1+1)%1-0.5),vf=vn<0.05&&v>0.2?1-veins:1;
    col[k*3]=q[0]/255*vf;col[k*3+1]=q[1]/255*vf;col[k*3+2]=q[2]/255*vf;tr[k]=q[3]*(vf<1?0.6:1)}
  return {x0:x0,x1:x1,y0:y0,y1:y1,ix:n/(x1-x0),iy:n/(y1-y0),cov:cov,col:col,tr:tr};
}
for(var si=0;si<SPECIES.length;si++){var sp0=SPECIES[si],wg=WINGS[sp0.wing];
  sp0.FT=bakeWing(wg.fore,wg.tip,sp0.fore,sp0.veins);sp0.HT=bakeWing(wg.hind,2,sp0.hind,sp0.veins)}
/* ---- anatomy ---- */
var NONE=0,FW=1,HW=2,THX=3,ABD=4,HEAD=5,EYE=6,ANT=7;
var S_PART=0,S_U=0,S_V=0,S_I=0,S_NU=0,S_NV=0;   /* scratch outputs of the samplers */
/* the body: eyes, head, a furry thorax, a tapering abdomen, antennae. it also sets
   a surface normal (S_NU along the body, S_NV across) so the body shades round */
function sampleBody(m,u,v){
  var b=m.sp.body,av=v<0?-v:v,sg=v<0?-1:1,thu=b.th[0],thl=b.th[1],thw=b.th[2],hr=b.hd,hu=thu+thl+hr*0.15,d;
  var eu=hu+0.012,ev=hr*0.68,er=hr*0.45;d=(u-eu)*(u-eu)+(av-ev)*(av-ev);
  if(d<er*er){S_PART=EYE;S_U=(u-eu)/er;S_V=(av-ev)/er;S_NU=S_U*0.8;S_NV=sg*S_V*0.8;return true}
  d=(u-hu)*(u-hu)+av*av;
  if(d<hr*hr){S_PART=HEAD;S_U=(u-hu)/hr;S_V=av/hr;S_NU=S_U*0.75;S_NV=sg*S_V*0.75;return true}
  var tu=(u-thu)/thl,tv=av/thw;
  if(tu*tu+tv*tv<1){S_PART=THX;S_U=tu;S_V=tv;S_NU=tu*0.7;S_NV=sg*tv*0.8;return true}
  var a0=b.ab[0],a1=b.ab[1];
  if(u<a0&&u>a1){var k=(u-(a0+a1)/2)/((a0-a1)/2),w=b.ab[2]*Math.sqrt(Math.max(0,1-k*k))*(k<0?1+0.25*k:1);
    if(av<w){S_PART=ABD;S_U=(u-a1)/(a0-a1);S_V=av/w;S_NU=0;S_NV=sg*S_V*0.85;return true}}
  /* antennae: feathery on the silk moths, thin elsewhere, clubbed on the hawk-moth */
  if(u>hu&&u<hu+0.4&&av<0.32){
    for(var i=0;i<=9;i++){var t=i/9,qa=(1-t)*(1-t),qb=2*(1-t)*t,qc=t*t;
      var cu=hu+qa*0.035+qb*0.225+qc*0.335+m.twitch*t*0.02,cv=qa*0.025+qb*0.07+qc*0.25;
      var rad=b.ant===1?0.012+0.03*Math.sin(t*Math.PI):b.ant===2?0.011+(t>0.78?0.012:0):0.011+0.007*Math.sin(t*Math.PI);
      if((u-cu)*(u-cu)+(av-cv)*(av-cv)<rad*rad){S_PART=ANT;S_U=t;S_V=av;S_NU=0;S_NV=0;return true}}}
  return false;
}
/* one wing position (a pose) at a time: undo the flap's foreshortening and the sweep
   about the shoulder, then look the point up in the baked wing */
function sampleWing(m,q,u,v){
  var sp=m.sp,av=v<0?-v:v,right=v>=0,t,x,y,i,j,k;
  var f=right?q.fR:q.fL;
  if(f>0.04){var vv=av/f;if(vv<1.2){var ru=u-0.02,rv=vv-0.05;x=ru*q.cs+rv*q.sn+0.02;y=-ru*q.sn+rv*q.cs+0.05;t=sp.FT;
    if(x>t.x0&&x<t.x1&&y>t.y0&&y<t.y1){i=((x-t.x0)*t.ix)|0;j=((y-t.y0)*t.iy)|0;k=j*TEXN+i;
      if(t.cov[k]>=0.5){S_PART=FW;S_I=k;return true}}}}
  var fh=right?q.hR:q.hL;
  if(fh>0.04){var vh=av/fh;if(vh<1.2){var hu=u+0.06,hv=vh-0.06;x=hu*q.cs2+hv*q.sn2-0.06;y=-hu*q.sn2+hv*q.cs2+0.06;t=sp.HT;
    if(x>t.x0&&x<t.x1&&y>t.y0&&y<t.y1){i=((x-t.x0)*t.ix)|0;j=((y-t.y0)*t.iy)|0;k=j*TEXN+i;
      if(t.cov[k]>=0.5){S_PART=HW;S_I=k;return true}}}}
  return false;
}
/* the wing blur. eyes and cameras gather light over about 1/30 s, and a wing beating
   30 times a second sweeps a whole stroke in that time. so each frame takes K wing
   positions across that window and the renderer averages them: dense where the wing
   dwells (the ends of the stroke), faint where it moves fastest. a resting or gliding
   moth gets one pose and stays sharp. */
var TAU=1/30,KMAX=7;
function poses(m){
  var sp=m.sp,K=1,span=0,PS=m.P,jit=Math.random(),o=m.open,r=sp.rest;
  if(m.flapping){span=6.2832*m.hzNow*TAU;K=clamp(Math.ceil(span/0.8),1,KMAX)}
  var roll=Math.abs(Math.cos(m.roll)),bk=m.bank;
  for(var k=0;k<K;k++){
    var ph=m.ph-(K>1?span*(k+jit)/K:0),el=m.amp*Math.sin(ph);
    /* stroke: elevation foreshortens the wing; the sweep traces the figure-eight. at
       rest (o=0) the same terms make the small fast shiver of a warm-up */
    var fo=lerp(r[1],1,o)*Math.cos(el),fh=lerp(r[3],1,o)*Math.cos(el*0.9-0.1*o);
    var sw=lerp(r[0],0.06,o)+0.12*Math.sin(ph+0.6)*o+el*0.25*(1-o);
    var sw2=lerp(r[2],0.04,o)+0.08*Math.sin(ph+0.2)*o+el*0.2*(1-o);
    if(m.pinned){fo=fh=1;sw=0.16;sw2=0.1;el=0}
    var q=PS[k]||(PS[k]={});
    q.fL=fo*(1+bk)*roll;q.fR=fo*(1-bk)*roll;q.hL=fh*(1+bk)*roll;q.hR=fh*(1-bk)*roll;
    q.cs=Math.cos(sw);q.sn=Math.sin(sw);q.cs2=Math.cos(sw2);q.sn2=Math.sin(sw2);q.el=el*o;
  }
  m.K=K;m.under=Math.cos(m.roll)<0;
}

/* ---- the bulb on its cord, hanging out in the room ---- */
var lamp={x:0,y:0,z:600,vx:0,vy:0,ax:0,ay:-6,L:200,Lr:200,th:0,om:0,held:false,I:1,flare:0,tick:0,px:0,py:0,rb:30};
function lampRest(){
  var margin=W-copyR;
  lamp.ax=W<700?W*0.66:margin>300?copyR+margin*0.42:W*0.86;lamp.Lr=H*(W<700?0.3:0.4);
  /* how far the bulb hangs in front of the wall: far enough to light all of it */
  lamp.z=Math.max(W,H*1.2)*0.42;lamp.rb=clamp(Math.min(W,H)*0.045,16,40)}
function lampInit(){lampRest();lamp.L=lamp.Lr;lamp.th=0.12;lamp.om=0;
  lamp.x=lamp.ax+Math.sin(lamp.th)*lamp.L;lamp.y=lamp.ay+Math.cos(lamp.th)*lamp.L}
function lampStep(dt){
  if(lamp.held){
    /* the cursor has it: a stiff spring toward the pointer */
    var kx=lamp.px-lamp.x,ky=lamp.py-lamp.y;
    lamp.vx+=(kx*90-lamp.vx*16)*dt;lamp.vy+=(ky*90-lamp.vy*16)*dt;
    lamp.x+=lamp.vx*dt;lamp.y+=lamp.vy*dt;
  }else{
    /* let go: it swings on the cord and reels back to its resting length */
    var g=1400;
    lamp.om+=(-(g/lamp.L)*Math.sin(lamp.th)-lamp.om*0.55)*dt;
    lamp.th+=lamp.om*dt;
    lamp.L+=(lamp.Lr-lamp.L)*Math.min(1,dt*1.6);
    var nx=lamp.ax+Math.sin(lamp.th)*lamp.L,ny=lamp.ay+Math.cos(lamp.th)*lamp.L;
    lamp.vx=(nx-lamp.x)/dt;lamp.vy=(ny-lamp.y)/dt;lamp.x=nx;lamp.y=ny;
  }
  lamp.flare*=Math.exp(-dt*3.2);lamp.tick*=Math.exp(-dt*14);
  /* the hum of an old filament */
  lamp.I=1+0.03*Math.sin(T*47)+0.02*Math.sin(T*13.3)+lamp.flare*0.9;
}
function release(){
  if(!lamp.held)return;lamp.held=false;
  var dx=lamp.x-lamp.ax,dy=lamp.y-lamp.ay;lamp.L=Math.max(40,Math.hypot(dx,dy));
  lamp.th=Math.atan2(dx,dy);
  var tx=Math.cos(lamp.th),ty=-Math.sin(lamp.th);
  lamp.om=clamp((lamp.vx*tx+lamp.vy*ty)/lamp.L,-6,6);
}
/* light, in units where the wall straight behind the bulb gets P.e0. on a moth: the
   inverse square from a small source. on the wall: the same, times the cosine of the
   angle it lands at, so it fades toward the edges of the room */
function E3(x,y,z){var dx=x-lamp.x,dy=y-lamp.y,dz=z-lamp.z,z2=lamp.z*lamp.z;
  return lamp.I*P.e0*z2/(dx*dx+dy*dy+dz*dz+z2*0.0625)}
function Ewall(r){var z2=lamp.z*lamp.z,k=z2/(z2+r*r);return lamp.I*P.e0*k*Math.sqrt(k)}
/* the camera sits four bulb-depths from the wall: nearer moths look bigger */
function depthScale(z){return 3*lamp.z/(4*lamp.z-z)}
function lightAt(x,y){return 1-Math.exp(-E3(x,y,lamp.z*0.8)*P.ex)}

/* ---- moths ---- */
var moths=[],specks=[],dust=[];
function newMoth(fromEdge){
  var sp=pickSpecies(),sc=clamp(Math.min(W,H)/700,0.6,1.3);
  var m={sp:sp,S:lerp(sp.span[0],sp.span[1],Math.random())*sc,h:rnd(0,6.283),side:Math.random()<0.5?1:-1,
    bias:rnd(0.04,0.3),v0:rnd(150,230)*sc,ph:rnd(0,6.283),hzNow:sp.hz,amp:sp.amp,open:1,flapping:true,glide:0,
    wander:0,stall:0,mode:"fly",energy:P.day?rnd(3,7):rnd(10,24),restT:0,warmT:0,warmDur:1,tumble:0,spin:0,fall:0,roll:0,rollV:0,
    tx:0,ty:0,rh:0,z:0,zc:rnd(0.3,1.1)*lamp.z,zph:rnd(0,6.283),twitch:0,ct:0,fade:1,bank:0,P:[],K:1,under:false,pinned:false};
  if(fromEdge){var e=Math.floor(Math.random()*4);
    m.x=e===0?-60:e===1?W+60:rnd(0,W);m.y=e===2?-60:e===3?H+60:rnd(0,H);
    m.h=Math.atan2(lamp.y-m.y,lamp.x-m.x)+rnd(-0.6,0.6)}
  else{m.x=rnd(W*0.15,W*0.95);m.y=rnd(H*0.1,H*0.9)}
  m.z=m.zc;return m;
}
function seedAll(){
  moths=[];specks=[];dust=[];
  var n=Math.round(clamp(W*H/210000,3,5));
  for(var i=0;i<n;i++)moths.push(newMoth(false));
  /* some already resting on the wall (by day, nearly all of them) */
  for(i=0;i<(P.day?n-1:2)&&i<moths.length;i++)settle(moths[i],true);
  for(i=0;i<Math.round(clamp(W*H/60000,8,20));i++)specks.push({x:rnd(0,W),y:rnd(0,H),h:rnd(0,6.283),
    side:Math.random()<0.5?1:-1,v:rnd(70,130),ph:rnd(0,6.283),bias:rnd(0.05,0.3)});
}
/* the wall, minus the copy: where a tired moth may land */
function onCopy(x,y,pad){for(var i=0;i<zones.length;i++){var z=zones[i];
  if(x>z.x0-pad&&x<z.x1+pad&&y>z.y0-pad&&y<z.y1+pad)return true}return false}
function restSpot(m){
  var pad=m.S*0.45;
  for(var k=0;k<40;k++){var x=rnd(W*0.05,W*0.95),y=rnd(H*0.08,H*0.92);
    if(onCopy(x,y,pad)||Math.hypot(x-lamp.x,y-lamp.y)<150)continue;
    m.tx=x;m.ty=y;break}
  if(k===40){m.tx=rnd(W*0.55,W*0.95);m.ty=rnd(H*0.05,H*0.14)}
  m.rh=-Math.PI/2+rnd(-0.5,0.5)+(Math.random()<0.3?Math.PI:0);
}
function settle(m,now){m.mode=now?"rest":"land";restSpot(m);m.restT=P.day?rnd(12,28):rnd(4,9);
  if(now){m.x=m.tx;m.y=m.ty;m.z=6;m.h=m.rh;m.open=0;m.flapping=false}}
function warmUp(m,quick){m.mode="warm";m.warmT=0;m.warmDur=quick?rnd(0.6,1.1):rnd(1.8,3.6)}
function stepMoth(m,dt){
  var sp=m.sp,dx=lamp.x-m.x,dy=lamp.y-m.y,dist=Math.hypot(dx,dy)||1,la=Math.atan2(dy,dx);
  if(m.mode==="caught"){m.ct+=dt;m.h+=angDiff(m.h,-Math.PI/2)*Math.min(1,dt*6);m.flapping=false;m.pinned=true;
    m.roll=0;m.rollV=0;m.z+=(4-m.z)*Math.min(1,dt*5);if(m.ct>5.5)m.fade-=dt*0.9;return}
  if(m.mode==="rest"){m.flapping=false;m.open+=(0-m.open)*Math.min(1,dt*5);m.z+=(6-m.z)*Math.min(1,dt*6);
    m.twitch=Math.sin(T*3+m.ph)*(Math.random()<0.02?1:0.2);m.restT-=dt;
    var close=dist<90+m.S*0.5;if(close)m.restT=Math.min(m.restT,0);
    if(m.restT<=0)warmUp(m,close);
    return}
  if(m.mode==="warm"){
    /* shivering: small fast strokes heat the flight muscles; the rate climbs as they warm */
    m.warmT+=dt;var k=clamp(m.warmT/m.warmDur,0,1);
    m.flapping=true;m.hzNow=lerp(8,Math.min(sp.hz,25),k);m.amp=lerp(0.1,0.3,k);
    m.open+=(0.42*k*k-m.open)*Math.min(1,dt*8);m.ph+=6.2832*m.hzNow*dt;
    m.twitch=Math.sin(T*11+m.ph)*0.6;
    if(k>=1){m.mode="fly";m.energy=P.day?rnd(4,8):rnd(7,16);m.h=-Math.PI/2+rnd(-1.2,1.2);m.stall=0;m.zc=rnd(0.3,1.1)*lamp.z}
    return}
  if(m.mode==="land"){
    var lx=m.tx-m.x,ly=m.ty-m.y,ld=Math.hypot(lx,ly);
    m.z+=(0-m.z)*Math.min(1,dt*clamp(300/(ld+40),0.5,4));
    if(ld<30){m.x+=lx*Math.min(1,dt*5);m.y+=ly*Math.min(1,dt*5);m.h+=angDiff(m.h,m.rh)*Math.min(1,dt*7);
      if(ld<3&&m.z<16){m.mode="rest";m.x=m.tx;m.y=m.ty}}
    else{m.h+=angDiff(m.h,Math.atan2(ly,lx))*Math.min(1,dt*5);
      var sl=Math.min(m.v0,ld*2.2+18);m.x+=Math.cos(m.h)*sl*dt;m.y+=Math.sin(m.h)*sl*dt}
    flap(m,dt,0);return}
  /* flying: the dorsal light response, a wander, a flutter */
  var inf=Math.pow(clamp(1-dist/(Math.max(W,H)*0.85),0,1),0.55);
  var near=clamp(1-dist/(Math.min(W,H)*0.55),0,1);
  var target=la-m.side*(Math.PI/2-m.bias-(1-near)*0.75);
  m.wander=clamp(m.wander+(Math.random()-0.5)*dt*7,-1.5,1.5);
  var wt=m.h+m.wander,tx=Math.cos(target)*inf*2.4+Math.cos(wt)*(1-inf*0.75),ty=Math.sin(target)*inf*2.4+Math.sin(wt)*(1-inf*0.75);
  var turn=clamp(angDiff(m.h,Math.atan2(ty,tx))*6.5,-7.5,7.5);
  m.h+=(turn+(Math.random()-0.5)*10*(0.35+0.65*inf))*dt;
  m.bank+=(clamp(turn*0.035,-0.28,0.28)-m.bank)*Math.min(1,dt*8);
  /* after a hit: spinning, wings out of time, dropping, until it rights itself */
  if(m.tumble>0){m.tumble-=dt;m.h+=m.spin*dt;m.spin*=Math.exp(-dt*2.5);m.fall+=520*dt;
    m.bank=0.55*Math.sin(T*41+m.ph)}else m.fall*=Math.exp(-dt*5);
  /* rolling onto its back and over: the inverted flight in the 2024 videos */
  if(m.rollV){m.roll+=m.rollV*dt;m.fall+=160*dt;if(m.roll>=6.2832){m.roll=0;m.rollV=0}}
  /* depth: far off they cruise; near the bulb the orbit is a tilted ring, so they
     pass in front of it and behind it */
  var ang=Math.atan2(m.y-lamp.y,m.x-lamp.x),rr=Math.min(dist,lamp.z*0.5),zo=lamp.z-rr*0.35+rr*1.1*Math.sin(ang+m.zph);
  m.z+=(lerp(m.zc,zo,near)-m.z)*Math.min(1,dt*2.4);m.z=clamp(m.z,10,lamp.z*1.5);
  /* the bulb is glass */
  var dz=m.z-lamp.z,d3=Math.sqrt(dist*dist+dz*dz),glass=lamp.rb*1.15+m.S*0.3;
  if(d3<glass&&m.tumble<=0)hit(m,dx,dy,dz,d3,glass);
  /* over the light the same rule pitches them up: a stall, or a roll onto the back */
  if(m.tumble<=0&&!m.rollV&&m.stall<=0&&m.y<lamp.y-lamp.rb&&Math.abs(m.x-lamp.x)<lamp.rb*3&&dist<lamp.rb*5&&
     Math.random()<dt*0.5){if(Math.random()<0.7)m.stall=rnd(0.3,0.6);else m.rollV=rnd(14,20)}
  if(inf>0.35&&Math.random()<dt*0.16)m.side=-m.side;
  if(inf>0.3&&Math.random()<dt*0.1)m.stall=rnd(0.2,0.5);
  var st=m.stall>0?0.3:1;if(m.stall>0){m.stall-=dt;m.y-=26*dt}
  var spd=m.v0*(1+0.24*Math.sin(T*2.3+m.zph))*st*(0.82+0.32*inf)*(m.tumble>0?0.4:1);
  m.x+=Math.cos(m.h)*spd*dt;m.y+=Math.sin(m.h)*spd*dt+m.fall*dt;
  /* soft walls: the room is bigger than the hero, but not much */
  var M=-30;
  if(m.x<M)m.h+=angDiff(m.h,0)*dt*3;else if(m.x>W-M)m.h+=angDiff(m.h,Math.PI)*dt*3;
  if(m.y<M)m.h+=angDiff(m.h,Math.PI/2)*dt*3;else if(m.y>H-M)m.h+=angDiff(m.h,-Math.PI/2)*dt*3;
  flap(m,dt,m.stall>0||m.tumble>0?1:0);
  if(dist<200&&Math.random()<dt*1.6)shed(m,1);
  m.energy-=dt;if(m.energy<=0&&dist>180&&m.tumble<=0&&!m.rollV)settle(m,false);
}
function hit(m,dx,dy,dz,d3,glass){
  m.h=Math.atan2(-dy,-dx)+rnd(-1,1);m.tumble=rnd(0.3,0.65);m.spin=(Math.random()<0.5?-1:1)*rnd(9,16);
  m.fall=rnd(40,120);m.stall=0;if(Math.random()<0.55)m.side=-m.side;
  var k=(glass+3)/(d3||1);m.x=lamp.x-dx*k;m.y=lamp.y-dy*k;m.z=lamp.z+dz*k;
  lamp.tick=1;shed(m,6);
}
function flap(m,dt,hurry){var sp=m.sp;
  m.open+=(1-m.open)*Math.min(1,dt*6);
  m.hzNow+=(sp.hz*(hurry?1.25:1)-m.hzNow)*Math.min(1,dt*4);m.amp+=(sp.amp-m.amp)*Math.min(1,dt*4);
  if(m.glide>0){m.glide-=dt;m.flapping=false;return}
  /* the big silk moths sometimes glide a beat, wings held out flat */
  if(sp.glide&&!hurry&&Math.random()<dt*0.3){m.glide=rnd(0.25,0.6);m.ph=Math.round(m.ph/Math.PI)*Math.PI;
    m.flapping=false;return}
  m.flapping=true;m.ph+=6.2832*m.hzNow*dt;
}
function shed(m,n){for(var i=0;i<n&&dust.length<160;i++)dust.push({x:m.x+rnd(-m.S,m.S)*0.5,y:m.y+rnd(-m.S,m.S)*0.4,
  vx:rnd(-14,14),vy:rnd(6,26),life:rnd(1.6,3.4),age:0,ph:rnd(0,6.283)})}
function stepSpeck(s,dt){
  var dx=lamp.x-s.x,dy=lamp.y-s.y,dist=Math.hypot(dx,dy)||1,la=Math.atan2(dy,dx);
  var target=la-s.side*(Math.PI/2-s.bias);
  s.h+=clamp(angDiff(s.h,target)*4,-6,6)*dt+(Math.random()-0.5)*9*dt;
  if(dist<16){s.h=la+Math.PI+rnd(-1,1);if(Math.random()<0.5)s.side=-s.side}
  if(Math.random()<dt*0.1)s.side=-s.side;
  s.x+=Math.cos(s.h)*s.v*dt;s.y+=Math.sin(s.h)*s.v*dt;s.ph+=dt*16;
}

/* ---- the grid ---- */
/* glyphs by shape (after alex harri, "ascii characters are not pixels"): each glyph
   is rendered once and measured at six points in a 2x3 grid, staggered the way ink
   sits in a monospace cell. a cell of the scene is sampled at the same six points
   and gets the glyph with the nearest shape. */
var GLY=" .,'`:;-_~^\"/\\()<>[]{}+=*#%&@",NG=GLY.length,SV=new Float32Array(NG*6),LUT=null;
var SPX=[0.28,0.28,0.28,0.72,0.72,0.72],SPY=[0.26,0.54,0.82,0.18,0.46,0.74];
function size(){
  var r=cv.getBoundingClientRect();
  W=Math.max(1,Math.round(r.width));H=Math.max(1,Math.round(r.height));DPR=Math.min(2,devicePixelRatio||1);
  cv.width=Math.round(W*DPR);cv.height=Math.round(H*DPR);
  CW=clamp(Math.round(W/190),5,8);CH=Math.round(CW*1.6);COLS=Math.ceil(W/CW);ROWS=Math.ceil(H/CH);
  FONT=getComputedStyle(cv).fontFamily;
  stage=H<hero.getBoundingClientRect().height-4;
  var wr=(clearEl||hero).getBoundingClientRect();copyR=wr.right-r.left;
  /* the copy, block by block, so moths can still land in the gaps around it */
  zones=(opt.keep||[]).map(function(e){var b=e.getBoundingClientRect();
    return {x0:b.left-r.left,x1:b.right-r.left,y0:b.top-r.top,y1:b.bottom-r.top}});
  cellsAlloc();shapesBuild();litKey="";
  /* the wall's own colour and its plaster grain; the light is multiplied in each frame,
     so the grain only shows where the bulb rakes across it */
  tex.width=cv.width;tex.height=cv.height;
  var g=tex.getContext("2d");g.setTransform(DPR,0,0,DPR,0,0);
  g.fillStyle="rgb("+P.wall[0]+","+P.wall[1]+","+P.wall[2]+")";g.fillRect(0,0,W,H);
  g.font="400 "+Math.round(CH*0.7)+"px "+FONT;g.textAlign="center";g.textBaseline="middle";g.fillStyle=P.grain;
  for(var y=0;y<ROWS;y++)for(var x=0;x<COLS;x++){var h=hash(x,y,3);if(h>0.5)continue;
    g.globalAlpha=0.05+h*0.3;g.fillText(h<0.05?":":h<0.12?",":".",x*CW+CW/2,y*CH+CH/2)}
  g.globalAlpha=1;
}
function shapesBuild(){
  var s=4,w=CW*s,h=CH*s,c=doc.createElement("canvas");c.width=w;c.height=h;
  var g=c.getContext("2d",{willReadFrequently:true}),mx=[0,0,0,0,0,0],rad=0.3*CW*s,i,k,x,y;
  g.font="500 "+Math.round(CH*0.78*s)+"px "+FONT;g.textAlign="center";g.textBaseline="middle";g.fillStyle="#fff";
  for(i=0;i<NG;i++){g.clearRect(0,0,w,h);g.fillText(GLY.charAt(i),w/2,h/2+s);var d=g.getImageData(0,0,w,h).data;
    for(k=0;k<6;k++){var cx=SPX[k]*w,cy=SPY[k]*h,sum=0,n=0;
      for(y=Math.max(0,Math.floor(cy-rad));y<Math.min(h,Math.ceil(cy+rad));y++)
        for(x=Math.max(0,Math.floor(cx-rad));x<Math.min(w,Math.ceil(cx+rad));x++){
          var ex=x+0.5-cx,ey=y+0.5-cy;if(ex*ex+ey*ey>rad*rad)continue;sum+=d[(y*w+x)*4+3];n++}
      var val=n?sum/(n*255):0;SV[i*6+k]=val;if(val>mx[k])mx[k]=val}}
  for(i=0;i<NG;i++)for(k=0;k<6;k++)SV[i*6+k]/=mx[k]||1;
  LUT=new Int8Array(262144).fill(-1);
}
/* six samples, 3 bits each, make the key; the nearest glyph is found once and kept */
function glyphFor(key){var g=LUT[key];if(g>=0)return g;
  var best=0,bd=1e9;
  for(var i=0;i<NG;i++){var d=0;for(var k=0;k<6;k++){var t=(((key>>(3*k))&7)+0.5)/8-SV[i*6+k];d+=t*t}
    if(d<bd){bd=d;best=i}}
  LUT[key]=best;return best}

/* batching: everything is queued under a quantised colour + alpha and drawn one
   fillStyle per bucket, the way a tile renderer would. 5 bits a channel, 16 alphas. */
var CSTR=[];function cstr(k){var s=CSTR[k];if(!s){s=CSTR[k]="rgb("+(((k>>10)&31)*8+4)+","+(((k>>5)&31)*8+4)+","+((k&31)*8+4)+")"}return s}
var FQ={},FK=[],GQ={},GK=[];
function qkey(r,g,b,a){r=r>255?255:r<0?0:r;g=g>255?255:g<0?0:g;b=b>255?255:b<0?0:b;
  return ((((r>>3)<<10)|((g>>3)<<5)|(b>>3))<<4)|((a>1?1:a<0?0:a)*15+0.5|0)}
function qfill(k,x,y,w,h){var q=FQ[k];if(!q){q=FQ[k]=[];FK.push(k)}q.push(x,y,w,h)}
function qglyph(k,x,y,g){if(!(k&15))return;var q=GQ[k];if(!q){q=GQ[k]=[];GK.push(k)}q.push(x,y,g)}
function flushQ(c){
  c=c||ctx;var i,j,k,q;
  for(i=0;i<FK.length;i++){k=FK[i];q=FQ[k];c.globalAlpha=(k&15)/15;c.fillStyle=cstr(k>>4);
    for(j=0;j<q.length;j+=4)c.fillRect(q[j],q[j+1],q[j+2],q[j+3])}
  for(i=0;i<GK.length;i++){k=GK[i];q=GQ[k];c.globalAlpha=(k&15)/15;c.fillStyle=cstr(k>>4);
    for(j=0;j<q.length;j+=3)c.fillText(q[j+2],q[j],q[j+1])}
  FQ={};FK=[];GQ={};GK=[];c.globalAlpha=1;
}
/* the cell layer. under the glyphs, a soft underpaint: one pixel per sample point
   (2 x 3 per cell), scaled up smoothly, so silhouettes stay round instead of
   stepping. on top, one glyph per cell; a nearer moth's cell replaces a farther one's. */
var subCv=doc.createElement("canvas"),subCtx=subCv.getContext("2d"),subImg=null,subPix=null,SW=0,SHh=0;
var gChar=null,gKey=null,gCov=null,touched=null,stampA=null,nT=0,frameN=1,DX0=0,DX1=-1,DY0=0,DY1=-1;
function cellsAlloc(){
  var n=COLS*ROWS;SW=COLS*2;SHh=ROWS*3;subCv.width=SW;subCv.height=SHh;subImg=subCtx.createImageData(SW,SHh);
  subPix=new Uint32Array(subImg.data.buffer);gChar=new Array(n);gKey=new Int32Array(n);gCov=new Float32Array(n);
  touched=new Int32Array(n);stampA=new Uint32Array(n);
}
function cellsBegin(){
  /* clear only what the last layer used */
  if(DX1>=DX0)for(var y=DY0;y<=DY1;y++)subPix.fill(0,y*SW+DX0,y*SW+DX1+1);
  nT=0;frameN++;DX0=SW;DX1=-1;DY0=SHh;DY1=-1}
function subFill(x,y,r,g,b,a){if(x<0||y<0||x>=SW||y>=SHh)return;
  if(x<DX0)DX0=x;if(x>DX1)DX1=x;if(y<DY0)DY0=y;if(y>DY1)DY1=y;
  r=r>255?255:r<0?0:r;g=g>255?255:g<0?0:g;b=b>255?255:b<0?0:b;
  subPix[y*SW+x]=(((a>1?255:a*255)|0)<<24)|((b|0)<<16)|((g|0)<<8)|(r|0)}
function cellGlyph(i,ch,k,cov){
  if(stampA[i]!==frameN){stampA[i]=frameN;touched[nT++]=i}
  else if(cov<gCov[i]*0.6)return;   /* a faint edge doesn't knock out a solid cell behind it */
  gChar[i]=ch;gKey[i]=k;gCov[i]=cov}
function cellsFlush(){
  if(DX1>=DX0){
    var x0=Math.max(0,DX0-1),y0=Math.max(0,DY0-1),x1=Math.min(SW-1,DX1+1),y1=Math.min(SHh-1,DY1+1),w=x1-x0+1,h=y1-y0+1;
    subCtx.putImageData(subImg,0,0,x0,y0,w,h);
    ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality="low";
    ctx.drawImage(subCv,x0,y0,w,h,x0*CW/2,y0*CH/3,w*CW/2,h*CH/3)}
  for(var j=0;j<nT;j++){var i=touched[j];if(gChar[i]!==" ")qglyph(gKey[i],(i%COLS)*CW+CW/2,((i/COLS)|0)*CH+CH/2+1,gChar[i])}
  flushQ();
}

/* ---- drawing a moth ---- */
var cY=new Float32Array(6),SCALES="'`^~,.:;\"";
function bodyColor(m,part,u,v){
  var b=m.sp.body,c;
  if(part===THX){c=b.collar&&u>0.55?b.collar:b.stripe&&v>0.7?b.stripe:b.col;
    var fz=0.82+0.3*hash(Math.round(u*8),Math.round(v*8),m.sp.id*3);return [c[0]*fz/255,c[1]*fz/255,c[2]*fz/255]}
  if(part===ABD){c=b.abCol||b.col;
    if(b.bands&&((u*9)%1)<0.3&&v<0.8)c=[34,28,30];
    if(b.stripe&&v>0.5)c=mix(c,b.stripe,0.85);
    var sh=0.88+0.14*(1-v);return [c[0]*sh/255,c[1]*sh/255,c[2]*sh/255]}
  if(part===HEAD){c=mix(b.col,[22,18,16],0.25);return [c[0]/255,c[1]/255,c[2]/255]}
  if(part===EYE)return [0.07,0.055,0.05];
  c=b.antCol||mix(b.col,[240,230,206],0.3);return [c[0]/255,c[1]/255,c[2]/255]
}
function drawMoth(m){
  var sp=m.sp,S=m.S*depthScale(m.z),ch=Math.cos(m.h),sh=Math.sin(m.h),a=m.fade;
  var ox=m.x+(m.mode==="warm"?Math.sin(T*97+m.ph)*0.5:0),oy=m.y;
  var reach=S*sp.reach,c0=Math.max(0,Math.floor((ox-reach)/CW)),c1=Math.min(COLS-1,Math.floor((ox+reach)/CW));
  var r0=Math.max(0,Math.floor((oy-reach)/CH)),r1=Math.min(ROWS-1,Math.floor((oy+reach)/CH));
  if(c0>c1||r0>r1)return;
  var K=m.K,PS=m.P,invK=1/K,amb=P.amb,wm=P.warm,lzc=lamp.z-m.z,FT=sp.FT,HT=sp.HT,fk=P.fill*255;
  /* the moth as a whole: with the bulb behind it, its outline catches a rim of light */
  var dS=Math.hypot(lamp.x-ox,lamp.y-oy),Em=E3(ox,oy,m.z);
  var back=clamp(-lzc/(Math.abs(lzc)+dS*0.6+1),0,1);
  var rimK=Em*(0.12+0.9*back)*clamp(1.5-dS/(S*2.4+lamp.rb),0,1);
  var tape=m.mode==="caught";
  for(var r=r0;r<=r1;r++)for(var c=c0;c<=c1;c++){
    var x0=c*CW,y0=r*CH,tot=0,sR=0,sG=0,sB=0,sY=0,k;
    for(k=0;k<6;k++){
      var px=x0+SPX[k]*CW,py=y0+SPY[k]*CH,dx=(px-ox)/S,dy=(py-oy)/S,u=dx*ch+dy*sh,v=-dx*sh+dy*ch;
      var cov=0,R=0,G=0,B=0,nu=0,nv=0,nz=1,trn=0,wing=false,eye=false;
      if(sampleBody(m,u,v)){cov=1;var bc=bodyColor(m,S_PART,S_U,S_V);R=bc[0];G=bc[1];B=bc[2];
        nu=S_NU;nv=S_NV;eye=S_PART===EYE;var nn=nu*nu+nv*nv;nz=nn<1?Math.sqrt(1-nn):0}
      else{var el=0;
        for(var q=0;q<K;q++)if(sampleWing(m,PS[q],u,v)){var t=S_PART===FW?FT:HT,ii=S_I*3;
          cov+=invK;R+=t.col[ii];G+=t.col[ii+1];B+=t.col[ii+2];trn+=t.tr[S_I];el+=PS[q].el}
        if(cov>0){var n=1/(cov*K);R*=n;G*=n;B*=n;trn*=n;el*=n;wing=true;
          /* rolled over: the underside, paler and duller */
          if(m.under){var gy=(R+G+B)/3;R=lerp(R,gy,0.55)+0.06;G=lerp(G,gy,0.55)+0.06;B=lerp(B,gy,0.55)+0.05}
          /* a raised wing tilts its face toward the body */
          nv=-Math.sin(el)*(v<0?-1:1);nz=Math.cos(el)}}
      if(cov<=0){cY[k]=0;continue}
      /* light from the bulb in 3d: lambert on the face, light through the wing when
         it comes from behind, a soft sheen on the fur, and a little cool room light */
      var nx=nu*ch-nv*sh,ny=nu*sh+nv*ch;
      var lx=lamp.x-px,ly=lamp.y-py,ld=Math.sqrt(lx*lx+ly*ly+lzc*lzc)||1;
      var ndl=(nx*lx+ny*ly+nz*lzc)/ld,E=E3(px,py,m.z);
      var dif=ndl>0?ndl:0,bk=wing&&ndl<0?Math.pow(-ndl,0.7)*trn*1.6:0,shn=wing?0:0.22*(1-Math.abs(ndl));
      var rr=R*(E*(dif+shn)*wm[0]+amb[0])+R*R*bk*E*wm[0];
      var gg=G*(E*(dif+shn)*wm[1]+amb[1])+G*G*bk*E*wm[1];
      var bb=B*(E*(dif+shn)*wm[2]+amb[2])+B*B*bk*E*wm[2];
      if(eye){var gl=E*0.06*(dif+0.3);rr+=gl;gg+=gl*0.55;bb+=gl*0.3}   /* eyeshine */
      /* tone map on brightness, keeping the hue; the hottest spots roll toward white */
      var y=0.299*rr+0.587*gg+0.114*bb,yt=1-Math.exp(-y*P.ex),s=y>1e-6?yt/y:0;
      rr*=s;gg*=s;bb*=s;
      var mxc=rr>gg?(rr>bb?rr:bb):(gg>bb?gg:bb);
      if(mxc>1){var w2=Math.min(1,(mxc-1)*0.8)*0.5;rr=lerp(rr/mxc,1,w2);gg=lerp(gg/mxc,1,w2);bb=lerp(bb/mxc,1,w2)}
      /* colour only where there's light: in the dark it fades to a grey shape */
      var sat=smooth(0.02,0.22,yt);rr=lerp(yt,rr,sat);gg=lerp(yt*0.98,gg,sat);bb=lerp(yt*0.94,bb,sat);
      cY[k]=yt*cov;tot+=cov;sR+=rr*cov;sG+=gg*cov;sB+=bb*cov;sY+=yt*cov;
      subFill(2*c+(k<3?0:1),3*r+k%3,rr*fk,gg*fk,bb*fk,cov*a*0.97);
    }
    if(tot<=0)continue;
    var ci=r*COLS+c;
    if(tape){var tu=((c+0.5)*CW-ox)/S,tv=((r+0.5)*CH-oy)/S,uu=tu*ch+tv*sh,vv=-tu*sh+tv*ch;
      /* two strips of tape across the wings, the logbook way */
      if(Math.abs(vv*0.94+uu*0.34-0.42)<0.12||Math.abs(-vv*0.94+uu*0.34-0.42)<0.12){
        var tc=P.dark?[214,204,176]:[240,232,206];
        for(k=0;k<6;k++)subFill(2*c+(k<3?0:1),3*r+k%3,tc[0],tc[1],tc[2],0.92*a);
        cellGlyph(ci,"=",qkey(150,140,118,0.7*a),1);continue}}
    /* the glyph: the six brightnesses, contrast pushed so shapes read, matched by shape */
    var mc=tot/6,mx=0,key=0;
    /* a grain that belongs to the wing, not the screen: it moves with the moth */
    var gu2=((c+0.5)*CW-ox)/S,gv2=((r+0.5)*CH-oy)/S,gq=hash(Math.round((gu2*ch+gv2*sh)*22),Math.round((-gu2*sh+gv2*ch)*22),sp.id);
    for(k=0;k<6;k++){cY[k]*=0.86+0.28*hash(gq*997|0,k,7);if(cY[k]>mx)mx=cY[k]}
    for(k=0;k<6;k++){var tq=mx>0?mx*Math.pow(cY[k]/mx,1.7):0;key|=Math.min(7,(tq*8.8)|0)<<(3*k)}
    var iv=1/tot,gY=sY*iv,mn=9;for(k=0;k<6;k++)if(cY[k]<mn)mn=cY[k];
    if(mc>0.97){
      /* inside the wing the paint carries the picture; the glyphs are its scales: small
         marks, a shade lighter or darker than the wing, fixed to the wing as it moves */
      if(gY<0.04)continue;
      var lt=gq<0.62?1.22+0.25*gq:0.7,sg2=SCALES.charAt((gq*SCALES.length*7|0)%SCALES.length);
      cellGlyph(ci,sg2,qkey(sR*iv*lt*fk,sG*iv*lt*fk,sB*iv*lt*fk,a*(0.32+0.3*gY)),mc);continue}
    /* on the outline: the glyph whose shape matches, brighter, with the rim if backlit */
    var gi=glyphFor(key);if(gi===0)continue;
    var gain=1.2+0.45*(1-gY),rim=mc<0.92?1-Math.exp(-rimK*(1-mc)*1.8):0;
    cellGlyph(ci,GLY.charAt(gi),qkey((sR*iv*gain+rim*wm[0])*255,(sG*iv*gain+rim*wm[1])*255,(sB*iv*gain+rim*wm[2])*255,
      a*(0.45+0.4*Math.min(1,mc*1.6))),mc);
  }
}

/* ---- shadows ---- */
/* projected from the bulb onto the wall: a moth at depth z casts a shadow M times its
   size, M = zl/(zl - z), blurred by the bulb's size times gap over distance. so the
   shadow is crisp under a moth on the wall and huge and soft when it flies near the
   bulb. each one is the moth's own silhouette (wing blur included), sampled coarsely
   into a small mask, blurred, and stretched onto the wall. */
var MG=64,MW=MG+2,MSK=doc.createElement("canvas"),mctx=MSK.getContext("2d");MSK.width=MW;MSK.height=MW;
var mimg=mctx.createImageData(MW,MW),mbuf=new Float32Array(MW*MW);
function drawShadow(m){
  var zL=lamp.z,z=m.z,sp=m.sp,M,Ss,b,sx,sy,alpha;
  if(P.day){
    /* by day the light is a window, high and to the left: a soft shadow just below
       and right of each moth, drifting off and fading as it leaves the wall */
    if(z>170)return;
    Ss=m.S*0.75;b=2.5+z*0.22;sx=m.x+2+z*0.35;sy=m.y+3+z*0.5;alpha=0.3*m.fade*(1-smooth(20,170,z));
  }else{
    if(z>=zL-8)return;
    var mM=W<700?7:12;M=zL/(zL-z);if(M>mM)return;
    Ss=m.S*0.75*M;b=lamp.rb*0.28*z/(zL-z);   /* a clear bulb: the filament is the source */
    sx=lamp.x+(m.x-lamp.x)*M;sy=lamp.y+(m.y-lamp.y)*M;
    /* a shadow only takes away the bulb's share of the light there, not the room's */
    var dirE=1-Math.exp(-Ewall(Math.hypot(sx-lamp.x,sy-lamp.y))*P.ex),share=dirE/(dirE+P.amb[1]);
    alpha=share*P.shadow*m.fade/(1+Math.pow(b/(Ss*0.45),2))*(1-smooth(mM*0.6,mM,M));
  }
  var ext=Ss*1.6+b;if(sx+ext<0||sx-ext>W||sy+ext<0||sy-ext>H)return;
  if(alpha<0.01)return;
  var u0=sp.u0-0.08,u1=0.8,v0=-1.36,v1=1.36,step=Math.max(2.2,b*0.6)/Ss;
  var gu=Math.min(MG,Math.ceil((u1-u0)/step)),gv=Math.min(MG,Math.ceil((v1-v0)/step)),du=(u1-u0)/gu,dv=(v1-v0)/gv;
  var K=Math.min(m.K,3),stride=m.K/K,i,j,q;
  for(j=0;j<gv+2;j++)for(i=0;i<gu+2;i++)mbuf[j*MW+i]=0;
  for(j=0;j<gv;j++)for(i=0;i<gu;i++){var u=u0+(i+0.5)*du,v=v0+(j+0.5)*dv,cc=0;
    if(sampleBody(m,u,v))cc=1;else for(q=0;q<K;q++)if(sampleWing(m,m.P[(q*stride)|0],u,v))cc+=1/K;
    mbuf[(j+1)*MW+i+1]=cc}
  /* one pass of a 3x3 blur, so the stretch has nothing blocky to enlarge */
  var d=mimg.data;
  for(j=0;j<gv+2;j++)for(i=0;i<gu+2;i++){var s=0,n=0;
    for(var yy=j-1;yy<=j+1;yy++)for(var xx=i-1;xx<=i+1;xx++)if(xx>=0&&yy>=0&&xx<gu+2&&yy<gv+2){s+=mbuf[yy*MW+xx];n++}
    var o=(j*MW+i)*4;d[o]=0;d[o+1]=0;d[o+2]=0;d[o+3]=(s/n)*255}
  mctx.putImageData(mimg,0,0,0,0,gu+2,gv+2);
  ctx.save();ctx.translate(sx,sy);ctx.rotate(m.h);ctx.globalAlpha=alpha;ctx.imageSmoothingEnabled=true;
  ctx.drawImage(MSK,0,0,gu+2,gv+2,(u0-du)*Ss,(v0-dv)*Ss,(gu+2)*du*Ss,(gv+2)*dv*Ss);
  ctx.restore();
}

/* ---- the wall, the cord, the bulb, the glare ---- */
/* the lit wall is kept between frames and redrawn only when the bulb has moved a few
   pixels or flared; the light falls off too smoothly for a 3 px step to show. the
   filament's hum shows on the bulb and the moths, not on the wall */
var litC=doc.createElement("canvas"),litKey="";
function drawWall(){
  var I=1+lamp.flare*0.9,key=Math.round(lamp.x/3)+","+Math.round(lamp.y/3)+","+Math.round(I*20)+","+cv.width+","+cv.height;
  if(key!==litKey){litKey=key;
    if(litC.width!==cv.width||litC.height!==cv.height){litC.width=cv.width;litC.height=cv.height}
    var g0=litC.getContext("2d");g0.setTransform(1,0,0,1,0,0);g0.globalCompositeOperation="source-over";g0.drawImage(tex,0,0);
    g0.setTransform(DPR,0,0,DPR,0,0);
    /* the light on the wall, multiplied into its colour: room light plus the bulb's */
    var rMax=Math.hypot(Math.max(lamp.x,W-lamp.x),Math.max(lamp.y,H-lamp.y))+20,keep=lamp.I;lamp.I=I;
    var g=g0.createRadialGradient(lamp.x,lamp.y,0,lamp.x,lamp.y,rMax),am=P.amb,wm=P.warm;
    for(var i=0;i<=12;i++){var t=i/12,d=1-Math.exp(-Ewall(rMax*t*t)*P.ex);
      g.addColorStop(t*t,"rgb("+Math.round(clamp(am[0]+d*wm[0],0,1)*255)+","+Math.round(clamp(am[1]+d*wm[1],0,1)*255)+","+
        Math.round(clamp(am[2]+d*wm[2],0,1)*255)+")")}
    lamp.I=keep;
    g0.globalCompositeOperation="multiply";g0.fillStyle=g;g0.fillRect(0,0,W,H);g0.globalCompositeOperation="source-over"}
  ctx.setTransform(1,0,0,1,0,0);ctx.drawImage(litC,0,0);ctx.setTransform(DPR,0,0,DPR,0,0);
}
function drawCord(){
  var ax=lamp.ax,ay=0,bx=lamp.x,by=lamp.y-lamp.rb*1.95,dx=bx-ax,dy=by-ay,dd=Math.hypot(dx,dy)||1;
  var sag=lamp.held?Math.max(0,lamp.Lr*1.05-dd)*0.55:0,mx=(ax+bx)/2,my=(ay+by)/2+sag,lastC=-1,lastR=-1,cc=P.cord;
  for(var i=0;i<=200;i++){var t=i/200,a=(1-t)*(1-t),b=2*(1-t)*t,c=t*t;
    var x=a*ax+b*mx+c*bx,y=a*ay+b*my+c*by,col=Math.floor(x/CW),row=Math.floor(y/CH);
    if(col===lastC&&row===lastR)continue;lastC=col;lastR=row;
    var tx=2*(1-t)*(mx-ax)+2*t*(bx-mx),ty=2*(1-t)*(my-ay)+2*t*(by-my);
    var gl=Math.abs(tx)<Math.abs(ty)*0.45?"|":Math.abs(ty)<Math.abs(tx)*0.45?"-":(tx*ty>0?"\\":"/");
    var L=0.35+0.9*lightAt(x,y);qglyph(qkey(cc[0]*L,cc[1]*L,cc[2]*L,0.9),col*CW+CW/2,row*CH+CH/2+1,gl)}
  flushQ();
}
function drawBulb(){
  var rb=lamp.rb,bx=lamp.x,by=lamp.y,sw=rb*0.92,sh2=rb*1.12,sy=by-rb*1.95,k;
  /* the socket: dark ribbed metal, lit from below by its own bulb */
  var sg=ctx.createLinearGradient(bx-sw/2,0,bx+sw/2,0);
  sg.addColorStop(0,"#17150f");sg.addColorStop(0.32,"#6a5f50");sg.addColorStop(0.55,"#3a342c");sg.addColorStop(1,"#100e0b");
  ctx.fillStyle=sg;ctx.fillRect(bx-sw/2,sy,sw,sh2);
  ctx.fillStyle="rgba(0,0,0,0.4)";for(k=sy+3;k<sy+sh2-2;k+=4)ctx.fillRect(bx-sw/2,k,sw,1);
  var lg=ctx.createLinearGradient(0,sy+sh2*0.5,0,sy+sh2);lg.addColorStop(0,"rgba(255,190,120,0)");lg.addColorStop(1,"rgba(255,190,120,0.45)");
  ctx.fillStyle=lg;ctx.fillRect(bx-sw/2,sy+sh2*0.5,sw,sh2*0.5);
  /* the glass: a neck into the socket, then the globe, hottest round the filament */
  var gg=ctx.createRadialGradient(bx-rb*0.15,by-rb*0.1,rb*0.05,bx,by,rb*1.05);
  gg.addColorStop(0,"rgb(255,253,244)");gg.addColorStop(0.4,"rgb(255,232,182)");gg.addColorStop(0.82,"rgb(255,196,118)");
  gg.addColorStop(1,"rgba(255,176,96,0.55)");
  ctx.fillStyle=gg;ctx.beginPath();
  ctx.moveTo(bx-sw*0.42,sy+sh2);ctx.lineTo(bx+sw*0.42,sy+sh2);
  ctx.quadraticCurveTo(bx+rb*0.42,by-rb*0.75,bx+rb*0.86,by-rb*0.5);
  ctx.arc(bx,by,rb,-0.53,Math.PI+0.53);
  ctx.quadraticCurveTo(bx-rb*0.42,by-rb*0.75,bx-sw*0.42,sy+sh2);ctx.fill();
  /* the filament and a glint, as text */
  for(k=-2;k<=2;k++)qglyph(qkey(255,128,44,1),Math.floor((bx+k*CW)/CW)*CW+CW/2,Math.floor(by/CH)*CH+CH/2+1,k===0?"w":"~");
  qglyph(qkey(255,255,250,0.9),Math.floor((bx-rb*0.45)/CW)*CW+CW/2,Math.floor((by-rb*0.42)/CH)*CH+CH/2+1,lamp.tick>0.3?"*":"o");
  flushQ();
}
/* glare (spencer et al. 1995): light scattered in the eye makes a bloom, and the
   eye's own structures make a starburst of fine rays at random angles. it happens in
   the eye, so it lies over everything, and it dims when a moth covers the bulb. */
var RAYS=[];for(var ri=0;ri<30;ri++)RAYS.push({a:rnd(0,6.2832),l:rnd(1.5,4)*(Math.random()<0.2?1.9:1),
  w:rnd(0.3,1),f:rnd(0.5,2),p:rnd(0,6.283)});
function drawGlare(occl){
  var rb=lamp.rb,bx=lamp.x,by=lamp.y,I=Math.min(1.7,lamp.I)*(1-occl)*P.glare*(1+lamp.tick*0.2);
  if(I<0.01)return;
  ctx.globalCompositeOperation=P.dark?"lighter":"source-over";
  var R=rb*12,g=ctx.createRadialGradient(bx,by,0,bx,by,R);
  g.addColorStop(0,"rgba(255,240,214,"+Math.min(1,0.95*I)+")");g.addColorStop(0.07,"rgba(255,226,180,"+Math.min(1,0.55*I)+")");
  g.addColorStop(0.18,"rgba(255,206,150,"+0.2*I+")");g.addColorStop(0.42,"rgba(255,188,120,"+0.06*I+")");
  g.addColorStop(1,"rgba(255,180,110,0)");
  ctx.fillStyle=g;ctx.fillRect(bx-R,by-R,R*2,R*2);
  ctx.globalCompositeOperation="source-over";
  for(var k=0;k<RAYS.length;k++){var q=RAYS[k],an=q.a+0.03*Math.sin(T*0.31+q.p),
      len=rb*q.l*(0.82+0.18*Math.sin(T*q.f+q.p)),ca=Math.cos(an),sa=Math.sin(an),lastC=-9,lastR=-9;
    var gl=Math.abs(ca)>0.92?"-":Math.abs(sa)>0.92?"|":(ca*sa>0?"\\":"/");
    for(var t=rb*1.05;t<len;t+=CW*0.45){var px=bx+ca*t,py=by+sa*t,col=Math.floor(px/CW),row=Math.floor(py/CH);
      if(col===lastC&&row===lastR)continue;lastC=col;lastR=row;
      var f=1-(t-rb)/(len-rb);qglyph(qkey(255,230,190,f*f*q.w*I*0.9),col*CW+CW/2,row*CH+CH/2+1,gl)}}
  flushQ();
}
function byZ(a,b){return a.z-b.z}
function render(){
  drawWall();
  var i,m,behind=[],front=[],caught=[];
  for(i=0;i<moths.length;i++){m=moths[i];poses(m);if(m.mode==="caught")caught.push(m);else (m.z<lamp.z?behind:front).push(m)}
  for(i=0;i<moths.length;i++)drawShadow(moths[i]);
  ctx.font="500 "+Math.round(CH*0.78)+"px "+FONT;ctx.textAlign="center";ctx.textBaseline="middle";
  /* far specks: the swarm behind the big moths */
  for(i=0;i<specks.length;i++){var s=specks[i],L=lightAt(s.x,s.y),sc=P.specks;
    ctx.globalAlpha=clamp(0.12+L*0.85,0,0.95);ctx.fillStyle=L>0.5?"rgb(255,220,170)":"rgb("+sc[0]+","+sc[1]+","+sc[2]+")";
    ctx.fillText(Math.sin(s.ph)>0.2?"v":Math.sin(s.ph)<-0.2?"^":"-",Math.floor(s.x/CW)*CW+CW/2,Math.floor(s.y/CH)*CH+CH/2+1)}
  ctx.globalAlpha=1;
  behind.sort(byZ);front.sort(byZ);
  for(i=0;i<behind.length;i++){cellsBegin();drawMoth(behind[i]);cellsFlush()}
  /* scale dust, glinting as it falls through the light */
  for(i=0;i<dust.length;i++){var d=dust[i],Ld=lightAt(d.x,d.y);
    ctx.globalAlpha=clamp((1-d.age/d.life)*(0.1+Ld*0.9),0,1);
    ctx.fillStyle=Ld>0.4?"rgb(255,222,170)":(P.dark?"rgb(200,190,170)":"rgb(110,96,80)");
    ctx.fillText(Ld>0.6&&Math.sin(d.ph+T*9)>0.6?"*":".",Math.floor(d.x/CW)*CW+CW/2,Math.floor(d.y/CH)*CH+CH/2+1)}
  ctx.globalAlpha=1;
  drawCord();drawBulb();
  for(i=0;i<front.length;i++){cellsBegin();drawMoth(front[i]);cellsFlush()}
  var occl=0;for(i=0;i<front.length;i++){m=front[i];
    occl+=clamp(1-Math.hypot(m.x-lamp.x,m.y-lamp.y)/(m.S*depthScale(m.z)*0.5+lamp.rb*0.5),0,1)*0.5}
  drawGlare(Math.min(0.5,occl));
  for(i=0;i<caught.length;i++){cellsBegin();drawMoth(caught[i]);cellsFlush()}
  if(stage&&P.page){var fh=H*0.16,fg=ctx.createLinearGradient(0,H-fh,0,H),pc=P.page;
    fg.addColorStop(0,"rgba("+pc[0]+","+pc[1]+","+pc[2]+",0)");fg.addColorStop(1,"rgb("+pc[0]+","+pc[1]+","+pc[2]+")");
    ctx.fillStyle=fg;ctx.fillRect(0,H-fh,W,fh)}
}
function step(dt){
  T+=dt;lampStep(dt);
  var i;
  for(i=0;i<moths.length;i++)stepMoth(moths[i],dt);
  for(i=moths.length-1;i>=0;i--)if(moths[i].fade<=0){moths.splice(i,1);
    setTimeout(function(){moths.push(newMoth(true))},1200)}
  for(i=0;i<specks.length;i++)stepSpeck(specks[i],dt);
  for(i=dust.length-1;i>=0;i--){var d=dust[i];d.age+=dt;d.vy+=(18-d.vy)*dt*0.8;
    d.x+=(d.vx+Math.sin(T*1.7+d.ph)*10)*dt;d.y+=d.vy*dt;d.vx*=Math.exp(-dt*0.8);if(d.age>d.life)dust.splice(i,1)}
}


/* ---- pointer: grab the bulb and drag it; click a moth to catch it ---- */
var drag=null,tap=null;
function local(e){var r=cv.getBoundingClientRect();return {x:e.clientX-r.left,y:e.clientY-r.top}}
function inside(p){return p.x>=0&&p.y>=0&&p.x<=W&&p.y<=H}
/* the glass and its socket, with a little slack for fingers */
function onBulb(p,slack){var dx=p.x-lamp.x,dy=p.y-(lamp.y-lamp.rb*0.45);return dx*dx+dy*dy*0.45<lamp.rb*lamp.rb*2.1*slack*slack}
function mothAt(p,slack){var best=null,bd=1e9;
  for(var i=0;i<moths.length;i++){var m=moths[i];if(m.mode==="caught")continue;
    var d=Math.hypot(m.x-p.x,m.y-p.y);if(d<Math.max(16,m.S*depthScale(m.z)*0.75)*(slack||1)&&d<bd){bd=d;best=m}}
  return best}
function isUi(e){return e.target.closest&&e.target.closest("a,button")}
function catchMoth(best){
  best.mode="caught";best.ct=0;best.tumble=0;best.rollV=0;best.roll=0;caughtN++;
  if(hintEl)hintEl.textContent="bugs caught: "+caughtN+" · taped into the log";
  if(pinEl){pinEl.style.left=clamp(best.x+best.S*0.9,8,Math.max(8,W-280))+"px";pinEl.style.top=clamp(best.y-10,8,H-30)+"px";
    pinEl.style.opacity=1;clearTimeout(pinEl.t);pinEl.t=setTimeout(function(){pinEl.style.opacity=0},4200)}
  if(reduced)render();
}
/* open wall: the filament flares and everyone scatters; the resting ones have to warm up first */
function flare(){
  lamp.flare=1;
  for(var i=0;i<moths.length;i++){var q=moths[i];if(q.mode==="caught"||q.mode==="warm")continue;
    if(Math.hypot(q.x-lamp.x,q.y-lamp.y)<320){
      if(q.mode==="rest"){warmUp(q,true);continue}
      if(q.mode==="land"){q.mode="fly";q.energy=rnd(6,12)}
      q.h=Math.atan2(q.y-lamp.y,q.x-lamp.x)+rnd(-0.5,0.5);q.stall=0;q.side=-q.side}}
}
hero.addEventListener("pointermove",function(e){
  var p=local(e);
  if(drag!==null){lamp.px=p.x;lamp.py=p.y;if(reduced){lamp.x=p.x;lamp.y=p.y;render()}return}
  if(tap&&e.pointerId===tap.id&&Math.hypot(p.x-tap.x,p.y-tap.y)>12)tap=null;
  if(e.pointerType!=="mouse")return;
  hero.style.cursor=isUi(e)||!inside(p)?"":onBulb(p,1)?"grab":mothAt(p)?"pointer":"";
});
hero.addEventListener("pointerdown",function(e){
  if(e.button>0||isUi(e))return;
  var p=local(e);if(!inside(p))return;
  if(onBulb(p,e.pointerType==="mouse"?1:1.5)){
    drag=e.pointerId;lamp.held=true;lamp.px=p.x;lamp.py=p.y;hero.classList.add("drag");hero.style.cursor="";
    try{hero.setPointerCapture(e.pointerId)}catch(x){}
    e.preventDefault();return}
  /* a mouse acts at once. a finger might be starting a scroll, so it only counts as a
     tap if it lifts again soon without moving */
  if(e.pointerType==="mouse"){var best=mothAt(p);if(best)catchMoth(best);else flare();return}
  tap={id:e.pointerId,x:p.x,y:p.y,t:performance.now(),m:mothAt(p,1.3)};
});
hero.addEventListener("pointerup",function(e){
  if(drag!==null){endDrag(e);return}
  var t=tap;tap=null;
  if(!t||e.pointerId!==t.id||performance.now()-t.t>600)return;
  if(t.m&&t.m.mode!=="caught"&&Math.hypot(t.m.x-t.x,t.m.y-t.y)<Math.max(24,t.m.S*depthScale(t.m.z)))catchMoth(t.m);
  else flare();
});
function endDrag(e){if(drag===null||(e&&e.pointerId!==drag))return;drag=null;hero.classList.remove("drag");
  if(reduced){lamp.held=false;return}release()}
hero.addEventListener("pointercancel",function(e){tap=null;endDrag(e)});
hero.addEventListener("lostpointercapture",endDrag);
/* a touch that starts on the bulb drags it instead of scrolling the page */
hero.addEventListener("touchstart",function(e){var t=e.touches[0];if(!t)return;var r=cv.getBoundingClientRect();
  if(onBulb({x:t.clientX-r.left,y:t.clientY-r.top},1.5))e.preventDefault()},{passive:false});

/* ---- loop ----
   the drawing adapts to the device. it watches the time between frames: a phone that
   can't keep up first loses some of the wing blur, then draws every other frame
   (the flight itself still steps every frame, so the motion stays true) */
var run=false,vis=false,last=0,acc=0,STEP=1/60,ft=16.7,QL=2,qT=-2,ups=0,sinceDrop=99,odd=0;
function setQ(q){QL=q;KMAX=q>=2?7:q===1?3:2}
function frame(now){if(!run)return;var dt=Math.min(0.1,(now-last)/1000);last=now;acc+=dt;var n=0;
  while(acc>=STEP&&n<4){step(STEP);acc-=STEP;n++}if(n===4)acc=0;
  if(dt>0&&dt<0.25)ft+=(dt*1000-ft)*0.04;
  qT+=dt;sinceDrop+=dt;
  if(qT>1.5){qT=0;
    if(QL>0&&ft>(QL===1?30:24)){setQ(QL-1);ft=16.7;sinceDrop=0}
    else if(QL<2&&ups<1&&sinceDrop>5&&ft<17.5){setQ(QL+1);ups++;ft=16.7}}
  if(QL>0||(odd^=1))render();
  requestAnimationFrame(frame)}
function go(){var on=vis&&!doc.hidden&&!reduced;
  if(on&&!run){run=true;last=performance.now();qT=-1;requestAnimationFrame(frame)}else if(!on)run=false}
function still(){for(var i=0;i<240;i++)step(STEP);render()}
palette();size();lampInit();seedAll();if(reduced)still();
new IntersectionObserver(function(en){vis=en[0].isIntersecting;go()}).observe(cv);
doc.addEventListener("visibilitychange",go);
var rt=null;window.addEventListener("resize",function(){clearTimeout(rt);rt=setTimeout(function(){
  var r=cv.getBoundingClientRect();if(Math.round(r.width)!==W||Math.round(r.height)!==H){size();lampRest();if(reduced)render()}},160)});
if(hintEl&&!reduced)hintEl.textContent="drag the bulb · "+(coarse?"tap":"click")+" a moth to catch it";
if(doc.fonts&&doc.fonts.ready)doc.fonts.ready.then(function(){size();if(reduced)render()}).catch(function(){});
return {setTheme:function(){palette();size();if(reduced)render()},step:step,render:render};
};
})();

/* easel.js — shows the painting, and replays it being painted.

   the painter (_tools/paint/bench.py) saves four things per picture:
     the finished picture, the picture after the block-in, the pencil underdrawing,
     and a map of when each pixel was painted (red = during the block-in, green =
     during the finish; 0..255 across each phase).
   the replay: every pixel starts as pencil. as the clock passes the moment a pixel
   was blocked in, it takes the block-in's colour; as it passes the moment the
   finish reached it, it takes the finished colour. so what you watch is the real
   order the strokes went down in, not an effect.

   plain 2d canvas, so it runs anywhere a picture does. the pixels are sorted by
   their moment once, up front; after that each frame only touches the pixels whose
   moment has come. with reduced motion it just shows the finished picture.

   usage: DSEasel(canvas, {art:"art/", name:"bench", meta:window.DSART}) -> {show(mode, play, fast), replay(), view()}
   mode is "night" or "day"; name is which painting ("bench" on the front page, "garden"
   on the garden page). written from scratch. */
(function(){
"use strict";
window.DSEasel=function(cv,opt){
var art=opt.art||"art/",meta=opt.meta||{},doc=document;
var reduced=matchMedia("(prefers-reduced-motion: reduce)").matches;
var narrow=matchMedia("(max-width: 700px)");
var ctx=cv.getContext("2d"),cur=null,raf=0,token=0,job=null,imgs={};

function view(){return narrow.matches?"tall":"wide"}
function key(mode){return mode+"-"+view()}
function base(mode){return art+(opt.name||"bench")+"-"+key(mode)}
function load(src){
  if(imgs[src])return imgs[src];
  return imgs[src]=new Promise(function(ok,no){var im=new Image();im.decoding="async";
    im.onload=function(){ok(im)};im.onerror=function(){delete imgs[src];no()};im.src=src})}
function size(m){
  var dpr=Math.min(2,window.devicePixelRatio||1),w=Math.min(m.w,Math.round(cv.clientWidth*dpr))||m.w;
  /* the replay touches every pixel, so keep it to about a million on small machines */
  if(w*w*m.h/m.w>1.1e6&&narrow.matches)w=Math.round(Math.sqrt(1.1e6*m.w/m.h));
  var h=Math.round(w*m.h/m.w);
  if(cv.width!==w||cv.height!==h){cv.width=w;cv.height=h}
  cv.style.aspectRatio=m.w+" / "+m.h;
}
function pixels(im,smooth){
  var c=doc.createElement("canvas");c.width=cv.width;c.height=cv.height;
  var x=c.getContext("2d",{willReadFrequently:true});x.imageSmoothingEnabled=smooth;
  x.drawImage(im,0,0,c.width,c.height);
  return x.getImageData(0,0,c.width,c.height);
}
/* indices of the pixels, in the order of their moment: one counting sort */
function schedule(data,ch,n){
  var count=new Uint32Array(257),i,v;
  for(i=0;i<n;i++)count[data[i*4+ch]+1]++;
  for(i=1;i<257;i++)count[i]+=count[i-1];
  var start=new Uint32Array(count),idx=new Uint32Array(n);
  for(i=0;i<n;i++){v=data[i*4+ch];idx[count[v]++]=i}
  return {idx:idx,start:start};                    /* start[v] .. start[v+1] are the pixels of moment v */
}
function prepare(F,B,P,O){
  var n=cv.width*cv.height,out=pixels(P,true),f=pixels(F,true),b=pixels(B,true),o=pixels(O,false).data;
  var s1=schedule(o,0,n),s2=schedule(o,1,n);
  return {n:n,out:out,o32:new Uint32Array(out.data.buffer),f32:new Uint32Array(f.data.buffer),
    b32:new Uint32Array(b.data.buffer),o:o,s1:s1,s2:s2,p1:s1.start[1],p2:s2.start[1],F:F};
}
function ease(x){return x<.5?2*x*x:1-Math.pow(-2*x+2,2)/2}
function advance(j,a,b){
  /* block-in: everything whose red moment is <= a. a pixel the finish will repaint
     shows the block-in's colour for now; one it won't shows its final colour. */
  var e1=j.s1.start[Math.min(256,Math.floor(a*255)+1)],e2=j.s2.start[Math.min(256,Math.floor(b*255)+1)],i,k;
  var idx=j.s1.idx,o=j.o,o32=j.o32,f32=j.f32,b32=j.b32;
  for(k=j.p1;k<e1;k++){i=idx[k];o32[i]=o[i*4+1]?b32[i]:f32[i]}
  if(e1>j.p1)j.p1=e1;
  idx=j.s2.idx;
  if(b>0){for(k=j.p2;k<e2;k++){i=idx[k];o32[i]=f32[i]}if(e2>j.p2)j.p2=e2}
}
function finish(j){ctx.drawImage(j.F,0,0,cv.width,cv.height);if(opt.onprogress)opt.onprogress(1)}
function play(j,dur){
  var t0=performance.now(),me=token;
  cancelAnimationFrame(raf);
  (function frame(now){
    if(me!==token)return;
    var t=now-t0,a=Math.min(1,Math.max(0,t)/dur[0]),b=Math.max(0,Math.min(1,(t-dur[0])/dur[1]));
    advance(j,ease(a),ease(b));
    ctx.putImageData(j.out,0,0);
    if(opt.onprogress)opt.onprogress(Math.min(.999,(a*dur[0]+b*dur[1])/(dur[0]+dur[1])));
    if(b<1)raf=requestAnimationFrame(frame);else{raf=0;job=null;finish(j)}
  })(t0);
}
function still(mode,me){
  load(base(mode)+".webp").then(function(im){if(me!==token)return;
    ctx.drawImage(im,0,0,cv.width,cv.height);if(opt.onprogress)opt.onprogress(1)}).catch(function(){});
}
function show(mode,animate,fast){
  var m=meta[key(mode)],me=++token;
  if(!m)return;
  cur=mode;cancelAnimationFrame(raf);raf=0;job=null;size(m);
  var b=base(mode);
  if(!animate||reduced){still(mode,me);return}
  /* the pencil first, so there is something on the easel straight away */
  load(b+"-under.webp").then(function(im){if(me===token&&!job)ctx.drawImage(im,0,0,cv.width,cv.height)}).catch(function(){});
  Promise.all([load(b+".webp"),load(b+"-block.webp"),load(b+"-under.webp"),load(b+"-order.png")]).then(function(r){
    if(me!==token)return;
    try{job=prepare(r[0],r[1],r[2],r[3])}catch(e){job=null;still(mode,me);return}
    play(job,fast?[2600,2000]:[5200,3800]);
  }).catch(function(){if(me===token)still(mode,me)});
}
var rs=0;
window.addEventListener("resize",function(){clearTimeout(rs);rs=setTimeout(function(){
  if(!cur)return;
  var w=cv.width,was=cv.getAttribute("data-view");
  cv.setAttribute("data-view",view());
  var m=meta[key(cur)];if(!m)return;
  if(was!==view()){show(cur,false);return}
  if(raf)return;                                   /* mid-replay: leave it be */
  size(m);if(cv.width!==w)still(cur,++token);
},200)});
cv.setAttribute("data-view",view());
return {show:show,replay:function(){if(cur)show(cur,true)},view:view};
};
})();

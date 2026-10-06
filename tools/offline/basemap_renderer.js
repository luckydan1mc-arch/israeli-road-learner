// ---------- offline basemap: OpenStreetMap data from bm-1.js, bm-2.js, drawn locally on a canvas ----------
// Falls back to a plain land + road-network backdrop when the data files are not next to the app.
map.createPane("base");map.getPane("base").style.zIndex=200;map.getPane("base").style.pointerEvents="none";
const BM={ok:false,lines:{},polys:{},places:[],wl:[]};
const BM_POLY={sea:1,water:1,built:1,green:1};
const W0=256, D2R=Math.PI/180;
const wx=lon=>(lon/360+.5)*W0, wy=lat=>(.5-Math.log(Math.tan(Math.PI/4+lat*D2R/2))/(2*Math.PI))*W0;
function bmDecode(){
 const raw=window.IRL_BASE||[];if(!raw.length)return false;
 const AL="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_",V=new Int16Array(128).fill(-1);
 for(let i=0;i<64;i++)V[AL.charCodeAt(i)]=i;
 const ring=(pts)=>{const a=new Float64Array(pts.length);let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
  for(let k=0;k<pts.length;k+=2){const y=wy(pts[k]/1e5),x=wx(pts[k+1]/1e5);a[k]=x;a[k+1]=y;if(x<x0)x0=x;if(x>x1)x1=x;if(y<y0)y0=y;if(y>y1)y1=y;}
  return {a,b:[x0,y0,x1,y1]};};
 for(const rec of raw){
  if(rec.k==="places"){rec.d.forEach(p=>BM.places.push({n:p[0],k:p[1],x:wx(p[3]),y:wy(p[2]),pop:p[4]||0}));continue;}
  if(rec.k==="wlabels"){rec.d.forEach(p=>BM.wl.push({n:p[0],x:wx(p[2]),y:wy(p[1]),a:p[3]}));continue;}
  if(rec.k==="snames"){BM.sn=(BM.sn||[]).concat(rec.d);continue;}
  if(rec.k==="sanch"){const s=rec.d.join(""),n=s.length;let i=0,la=0,lo=0;BM.st=BM.st||[];
   const num=()=>{let z=0,m=1,c;for(;;){c=V[s.charCodeAt(i++)];if(c>=32){z+=(c-32)*m;m*=32;}else{z+=c*m;break;}}return z;};
   const sg=z=>(z%2)?-(z+1)/2:z/2;
   while(i<n){const ni=sg(num());la+=sg(num());lo+=sg(num());const ang=sg(num())-90,c=sg(num());
    BM.st.push({ni,x:wx(lo/1e5),y:wy(la/1e5),r:-ang*D2R,c});}
   continue;}
  const s=rec.d.join(""),n=s.length,poly=!!BM_POLY[rec.k];
  const out=(poly?BM.polys:BM.lines)[rec.k]||((poly?BM.polys:BM.lines)[rec.k]=[]);
  let i=0,aLat=0,aLon=0,rings=[];
  const num=()=>{let z=0,m=1,c;for(;;){c=V[s.charCodeAt(i++)];if(c>=32){z+=(c-32)*m;m*=32;}else{z+=c*m;break;}}return (z%2)?-(z+1)/2:z/2;};
  while(i<n){
   aLat+=num();aLon+=num();let la=aLat,lo=aLon;const pts=[la,lo];
   while(i<n){const ch=s.charCodeAt(i);if(ch===59||ch===44)break;la+=num();lo+=num();pts.push(la,lo);}
   rings.push(ring(pts));
   const ch=i<n?s.charCodeAt(i):44;i++;
   if(ch===44){if(poly){const b=rings[0].b.slice();out.push({r:rings,b});}else out.push(rings[0]);rings=[];}
  }}
 // biggest places first, so they win label collisions
 BM.places.sort((a,b)=>a.k-b.k||b.pop-a.pop);
 return true;}
BM.ok=bmDecode();

// styles (Google-like light map)
const C={land:"#f2efe9",sea:"#aad3ec",water:"#aad3ec",built:"#e6e1d8",green:"#d3e6c3",border:"#8d86a3"};
const RS=[ // fill, casing, min zoom, width stops (zoom:px)
 {f:"#fdd577",c:"#e0a23a",z:5,w:[[6,1.2],[8,2],[10,3],[12,5],[14,8],[16,14],[18,30]]},
 {f:"#fde293",c:"#dcae4c",z:6,w:[[7,1],[8,1.6],[10,2.6],[12,4.5],[14,7],[16,12],[18,26]]},
 {f:"#fff4c4",c:"#dcc485",z:8,w:[[8,.9],[10,2],[12,3.5],[14,6],[16,11],[18,24]]},
 {f:"#ffffff",c:"#cfc7b8",z:9,w:[[9,.8],[10,1.4],[12,2.8],[14,5],[16,10],[18,22]]},
 {f:"#ffffff",c:"#d6cfc3",z:10.5,w:[[10.5,.6],[12,1.8],[14,4],[16,9],[18,20]]},
 {f:"#ffffff",c:"#ddd7ce",z:12.5,w:[[12.5,.5],[14,2],[15,3.5],[16,6.5],[18,16]]}];
const stopW=(st,z)=>{if(z<=st[0][0])return st[0][1];for(let i=1;i<st.length;i++){const [z1,w1]=st[i],[z0,w0]=st[i-1];if(z<=z1){const t=(z-z0)/(z1-z0);return w0*Math.pow(w1/w0,t);}}return st[st.length-1][1];};
// place labels: kind -> min zoom, font
const PK=[{z:6,f:'700 15px "Segoe UI",Arial,sans-serif',c:"#1d1d1d"},{z:8.5,f:'700 13px "Segoe UI",Arial,sans-serif',c:"#262626"},
 {z:11,f:'600 12px "Segoe UI",Arial,sans-serif',c:"#333"},{z:12.5,f:'500 11px "Segoe UI",Arial,sans-serif',c:"#444"},
 {z:13,f:'500 11px "Segoe UI",Arial,sans-serif',c:"#5b5b5b"},{z:14.5,f:'500 11px "Segoe UI",Arial,sans-serif',c:"#666"}];
const placeMinZ=p=>p.k===1&&p.pop>40000?7.5:p.k===2&&p.pop>8000?10:p.k===2&&p.pop>2500?10.5:PK[p.k].z;
// road number shields (from the app's own numbered-road data)
const shieldStyle=r=>r.h==="motorway"?{bg:"#1f5fbf",fg:"#fff",bd:"#fff"}:r.dig<=2?{bg:"#c62828",fg:"#fff",bd:"#fff"}:r.dig===3?{bg:"#2e7d32",fg:"#fff",bd:"#fff"}:{bg:"#ffffff",fg:"#111",bd:"#222"};
const shieldMinZ=r=>r.dig<=2?7.5:r.dig===3?10:12;
let roadsW=null;
function roadWorld(){if(roadsW)return roadsW;roadsW=ROADS.map(r=>{let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
 const ls=r.g.map(l=>{const a=new Float64Array(l.length*2);l.forEach((p,k)=>{const x=wx(p[1]),y=wy(p[0]);a[2*k]=x;a[2*k+1]=y;if(x<x0)x0=x;if(x>x1)x1=x;if(y<y0)y0=y;if(y>y1)y1=y;});return a;});
 return {r,ls,b:[x0,y0,x1,y1]};});return roadsW;}

function drawBasemap(ctx,bounds,m){
 if(!BM.ok||!bounds)return;
 const z=m.getZoom(),S=Math.pow(2,z),o=m.getPixelOrigin(),ox=o.x,oy=o.y;
 const bx0=(bounds.min.x+ox)/S,by0=(bounds.min.y+oy)/S,bx1=(bounds.max.x+ox)/S,by1=(bounds.max.y+oy)/S;
 const vis=b=>!(b[2]<bx0||b[0]>bx1||b[3]<by0||b[1]>by1);
 const px=(a,k)=>a[k]*S-ox, py=(a,k)=>a[k+1]*S-oy;
 // land background
 ctx.fillStyle=C.land;ctx.fillRect(bounds.min.x,bounds.min.y,bounds.max.x-bounds.min.x,bounds.max.y-bounds.min.y);
 const path=(a)=>{let lx=px(a,0),ly=py(a,0);ctx.moveTo(lx,ly);const n=a.length;
  for(let k=2;k<n;k+=2){const x=a[k]*S-ox,y=a[k+1]*S-oy,dx=x-lx,dy=y-ly;if(dx*dx+dy*dy<.36&&k<n-2)continue;ctx.lineTo(x,y);lx=x;ly=y;}};
 const fillLayer=(k,col,minz)=>{if(z<minz||!BM.polys[k])return;ctx.fillStyle=col;
  for(const f of BM.polys[k]){if(!vis(f.b))continue;
   const w=(f.b[2]-f.b[0])*S,h=(f.b[3]-f.b[1])*S;if(w<1.5&&h<1.5)continue;   // sub-pixel shapes
   ctx.beginPath();for(const r of f.r){path(r.a);ctx.closePath();}ctx.fill("evenodd");}};
 fillLayer("green",C.green,9);fillLayer("built",C.built,8.5);fillLayer("sea",C.sea,0);fillLayer("water",C.water,0);
 // country borders
 if(BM.lines.border){ctx.beginPath();for(const f of BM.lines.border)if(vis(f.b))path(f.a);
  ctx.setLineDash([6,4]);ctx.strokeStyle=C.border;ctx.lineWidth=z<9?1.1:1.6;ctx.lineJoin="round";ctx.stroke();ctx.setLineDash([]);}
 // roads: all casings (minor -> major), then all fills
 ctx.lineCap="round";ctx.lineJoin="round";
 const drawn=[];
 for(let c=5;c>=0;c--){const st=RS[c],L=BM.lines["r"+c];if(z<st.z||!L)continue;const w=stopW(st.w,z);
  ctx.beginPath();let any=false;for(const f of L){if(!vis(f.b))continue;path(f.a);any=true;}
  if(!any)continue;drawn.push([c,w]);
  if(w<1.6){ctx.strokeStyle=st.c;ctx.lineWidth=Math.max(w,.6);ctx.stroke();}
  else{ctx.strokeStyle=st.c;ctx.lineWidth=w+2;ctx.stroke();}}
 for(const [c,w] of drawn){if(w<1.6)continue;const L=BM.lines["r"+c];ctx.beginPath();for(const f of L)if(vis(f.b))path(f.a);ctx.strokeStyle=RS[c].f;ctx.lineWidth=w;ctx.stroke();}
 // ---- labels with collision boxes ----
 const boxes=[],hit=(x0,y0,x1,y1)=>{for(const b of boxes)if(x0<b[2]&&x1>b[0]&&y0<b[3]&&y1>b[1])return true;return false;};
 const inView=(x,y)=>x>bounds.min.x&&x<bounds.max.x&&y>bounds.min.y&&y<bounds.max.y;
 ctx.textAlign="center";ctx.textBaseline="middle";
 const label=(t,x,y,font,col,halo)=>{ctx.font=font;const w=ctx.measureText(t).width,h=parseInt(font.match(/(\d+)px/)[1],10);
  const r=[x-w/2-2,y-h/2-1,x+w/2+2,y+h/2+1];if(!inView(x,y)||hit(...r))return false;boxes.push(r);
  ctx.lineWidth=3;ctx.strokeStyle=halo||"rgba(255,255,255,.95)";ctx.strokeText(t,x,y);ctx.fillStyle=col;ctx.fillText(t,x,y);return true;};
 const places=BM.places.filter(p=>z>=placeMinZ(p));
 // cities and big towns first, then road numbers, then the rest
 const big=places.filter(p=>p.k<=1),rest=places.filter(p=>p.k>1);
 for(const p of big)label(p.n,p.x*S-ox,p.y*S-oy,PK[p.k].f,PK[p.k].c);
 if(z>=9)for(const w of BM.wl)if(w.a>2e7||z>=10.5)label(w.n,w.x*S-ox,w.y*S-oy,'italic 600 13px "Segoe UI",Arial,sans-serif',"#2f6690","rgba(240,248,255,.9)");
 if(labelsOn&&z>=7.5){let count=0;const spacing=z<10?260:300;
  ctx.font='700 11px "Segoe UI",Arial,sans-serif';
  for(const R of roadWorld()){const r=R.r;if(z<shieldMinZ(r)||!vis(R.b))continue;const sty=shieldStyle(r),t=String(r.n),tw=ctx.measureText(t).width+8,th=15;
   for(const a of R.ls){let acc=spacing*.45,lx=a[0]*S-ox,ly=a[1]*S-oy;
    for(let k=2;k<a.length;k+=2){const x=a[k]*S-ox,y=a[k+1]*S-oy,seg=Math.hypot(x-lx,y-ly);
     while(acc<=seg&&seg>0){const t2=acc/seg,sx=lx+(x-lx)*t2,sy=ly+(y-ly)*t2;
      const bx=[sx-tw/2-3,sy-th/2-3,sx+tw/2+3,sy+th/2+3];
      if(inView(sx,sy)&&!hit(...bx)){boxes.push(bx);count++;
       ctx.fillStyle=sty.bg;ctx.strokeStyle=sty.bd;ctx.lineWidth=1.5;
       const x0=sx-tw/2,y0=sy-th/2;ctx.beginPath();ctx.roundRect?ctx.roundRect(x0,y0,tw,th,3):ctx.rect(x0,y0,tw,th);ctx.fill();ctx.stroke();
       ctx.fillStyle=sty.fg;ctx.fillText(t,sx,sy+.5);acc+=spacing;}
      else acc+=spacing*.25;}
     acc-=seg;lx=x;ly=y;}}
   if(count>400)break;}}
 for(const p of rest)label(p.n,p.x*S-ox,p.y*S-oy,PK[p.k].f,PK[p.k].c);
 // street names along the street direction
 if(labelsOn&&z>=14.5&&BM.st&&BM.sn){const minz=[0,0,14.5,14.5,15,15.5];ctx.font='500 11px "Segoe UI",Arial,sans-serif';
  for(const a of BM.st){if(z<minz[a.c])continue;const x=a.x*S-ox,y=a.y*S-oy;if(!inView(x,y))continue;
   const t=BM.sn[a.ni];if(!t)continue;const w=ctx.measureText(t).width+4,h=13,cs=Math.abs(Math.cos(a.r)),sn=Math.abs(Math.sin(a.r));
   const hw=(w*cs+h*sn)/2,hh=(w*sn+h*cs)/2,r=[x-hw,y-hh,x+hw,y+hh];if(hit(...r))continue;boxes.push(r);
   ctx.save();ctx.translate(x,y);ctx.rotate(a.r);ctx.lineWidth=3;ctx.strokeStyle="rgba(255,255,255,.95)";ctx.strokeText(t,0,0);ctx.fillStyle="#5d5a55";ctx.fillText(t,0,0);ctx.restore();}}
}
const BaseRenderer=L.Canvas.extend({
 options:{pane:"base",padding:.25},
 _updatePaths(){if(this._postponeUpdatePaths)return;this._redraw();},
 _draw(){if(this._ctx&&this._bounds)drawBasemap(this._ctx,this._bounds,this._map);},
 _onClick(){},_onMouseMove(){},_handleMouseOut(){}});
let baseR=null;
function bmRedraw(){if(baseR&&baseR._map)baseR._redraw();}
const baseCanvas=L.canvas({pane:"base",tolerance:0});
const baseLand=L.layerGroup().addTo(map),baseNet=L.layerGroup().addTo(map);
function drawBase(){
 baseLand.clearLayers();baseNet.clearLayers();
 if(BM.ok){baseR=new BaseRenderer();map.addLayer(baseR);$("map").style.background=C.land;return;}
 // fallback: no basemap files next to the app
 RG.regions.forEach(g=>baseLand.addLayer(L.polygon(g.o,{renderer:baseCanvas,color:"#ccd5cd",weight:1,opacity:.9,lineJoin:"round",fillColor:"#f4f6f2",fillOpacity:1,interactive:false})));
 ROADS.forEach(r=>{const w=r.dig<=2?1.3:r.dig===3?0.9:0.55;
  baseNet.addLayer(L.polyline(r.g,{renderer:baseCanvas,color:"#c3b7d0",weight:w,opacity:.8,interactive:false,smoothFactor:2}));});
 const note=document.createElement("div");note.className="bmwarn";
 note.innerHTML="קובצי המפה לא נמצאו. כדי לראות מפה מלאה עם יישובים ומספרי כבישים, שים את <b>bm-1.js</b> ו־<b>bm-2.js</b> באותה תיקייה עם הקובץ הזה.";
 $("map").parentNode.insertBefore(note,$("map"));}
drawBase();

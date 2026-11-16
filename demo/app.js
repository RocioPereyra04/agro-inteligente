
const $=i=>document.getElementById(i),cl=(v,a,b)=>Math.max(a,Math.min(b,v));
const T={
veg:{ic:'🌱',n:'Vegetation',scan:'Measuring how green the plants are…',c:3,col:'rgba(255,150,60,.35)',ring:'#ffb04a',src:'MODIS and Landsat greenness (NDVI)',z:[[300,420,30],[540,300,34],[650,470,28],[450,560,34]]},
suelo:{ic:'<svg viewBox="0 0 24 24" width="20" height="20"><path d="M2 8c4-3 8-3 10 0s6 3 10 0v13H2z" fill="#9a6b3f"/><path d="M2 14c5-2 9 2 12 0s6-1 8 0v7H2z" fill="#6f4a2a"/><circle cx="7" cy="17" r="1.4" fill="#e3d2b0"/><circle cx="14" cy="18" r="1.2" fill="#e3d2b0"/><circle cx="18" cy="16" r="1.1" fill="#e3d2b0"/></svg>',n:'Soil',scan:'Looking for soil with low organic matter…',t:'soil with low organic matter',a:'0.42 ha',p:'28%',c:1,col:'rgba(70,140,52,.38)',ring:'#ffe27a',src:'local soil maps (incomplete)',z:[[320,520,44],[420,380,30],[600,330,34],[560,600,38]],tl:'SUGGESTION: FERTILIZE',tip:'We suggest fertilizing these zones, using more where there is less organic matter. A soil test at these spots would confirm the satellite data.',mk:[[320,520,'LOW','0.16% carbon<br>Fertilize: 120 kg/ha','#ff7a66'],[420,380,'LOW','0.19% carbon<br>Fertilize: 95 kg/ha','#ff7a66'],[600,330,'MEDIUM','0.24% carbon<br>Fertilize: 55 kg/ha','#f0d27a'],[560,600,'MEDIUM','0.27% carbon<br>Fertilize: 35 kg/ha','#f0d27a']]},
plagas:{ic:'🐛',n:'Pests',scan:'Looking for where pests could start…',t:'pest risk',a:'0.38 ha',p:'25%',c:1,col:'rgba(255,60,45,.42)',ring:'#ff4a3a',src:'GPM and NASA POWER weather, MODIS greenness',z:[[380,360,34],[560,470,38],[450,600,30],[300,500,26],[600,330,28]],mk:'🐛',risk:[['Caterpillar',85],['Stink bug',60],['Aphid',55],['Powdery mildew',30]],tl:'⚠ IMPORTANT',imp:1,tip:'This is a forecast, not a sighting: it is not certain. The satellite cannot see pests directly, so check these zones in the field before acting.'},
agua:{ic:'💧',n:'Water',scan:'Measuring soil moisture…',t:'dry zones',a:'0.53 ha',p:'35%',c:3,col:'rgba(240,205,100,.4)',ring:'#7fe3ff',src:'SMAP soil moisture and GPM rainfall',z:[[345,360,36],[470,330,42],[575,410,30],[430,480,38],[610,540,30],[380,600,32],[520,620,26]],mk:'💧'},
rot:{ic:'🔄',n:'Rotation',scan:'Comparing crops for the next season…',c:2,z:[],src:'SMAP moisture, GPM rainfall and local soil maps',tl:'PLANTING SUGGESTION',tip:'This is a suggestion for the next crop to plant in this plot, not an order. Confirm it with your agronomist before planting.'}};
const INFO={
veg:'Each part of the plot is colored according to its NDVI, a greenness index measured by satellite: brown is dry plants or no crop and deep green is healthy, vigorous plants. The orange patches mark the zones with the least vigor.',
suelo:'The patches show where the soil has low organic matter, meaning fewer nutrients for the plants; the yellow outline highlights them. The little stones, crystals and granules mark where it is worth taking samples. We suggest fertilizing those zones: more where there is the greatest shortage.',
plagas:'This is a risk forecast, not a sighting. The red patches are the zones where weather and greenness make it more likely for pests to appear. In the bars: red is high risk, orange is medium and yellow is low.',
agua:'Shows a recommended irrigation plan based on the soil moisture percentage: the drier it is, the more water is suggested. The patches are the dry zones and change color with moisture. The drop with a white outline is the selected day, and today is marked separately.',
rot:'This is a suggestion for the next crop to plant, calculated from moisture, rainfall and soil. Each bar shows how viable it is: red is not very advisable and green is highly advisable.',
past:'Archive image from 2003 (Sentinel-2): shows what this same place looked like 23 years ago, with little plant cover, to compare it with today.'};
const C={tomate:['Tomato',.8,0,'🍅'],lechuga:['Lettuce',.5,1,'🥬'],zapallo:['Squash',.7,0,'🎃'],frutilla:['Strawberry',.6,1,'🍓'],naranja:['Orange',.85,0,'🍊'],melon:['Melon',.65,1,'🍈'],sandia:['Watermelon',.68,0,'🍉'],ciruela:['Plum',.8,0,'<svg class="ic16" viewBox="0 0 24 24" width="16" height="16"><circle cx="12" cy="14" r="8" fill="#6b2d8c"/><path d="M12 6c0-3 2-4 4-4" stroke="#5a8a2a" stroke-width="2" fill="none"/><ellipse cx="9" cy="11" rx="2" ry="3" fill="#ffffff44"/></svg>']};
const rc=v=>v>=70?'#ff4b3e':v>=50?'#ff9f2e':'#f5d547';
const rank=()=>Object.entries(C).map(([k,[n,w,l,ic]])=>[n,cl(Math.round(78-Math.max(0,w-.5)*110+(l?14:0)+(w<.5?8:0)-(k==S.crop?32:0)),5,95),ic]).sort((a,b)=>b[1]-a[1]);
const gy=v=>`rgb(${ramp([[0,[255,75,62]],[.5,[245,200,60]],[1,[60,220,110]]],v/100)})`;
const bars=(L,m)=>L.map(([n,v,ic])=>{const c=m==1?rc(v):m==2?gy(v):'';return`<div class="rb"><span>${ic?ic+' ':''}${n}</span><i><u style="width:${v}%${c?';background:'+c:''}"></u></i><b${c?` style="color:${c}"`:''}>${v}%</b></div>`}).join('');
const stage=v=>v<.1?['🟫','bare land','No crop','Plot not worked or with dry plants. Time to decide what to plant: check the Rotation tab.']:v<.4?['🌾','harvest time','Harvest','The plant is starting to wilt: the crop is mature. Get ready to harvest and think about the next planting.']:v<.7?['🌿','growing','Growth','The crop is still green and growing. It is not harvest time yet.']:['🌸','flowering','Flowering','Peak greenness: the crop is flowering. Take care of the water at this stage.'];
const fm=n=>n.toFixed(2);
const ramp=(A,v)=>{let i=0;while(i<A.length-2&&v>A[i+1][0])i++;const a=A[i],b=A[i+1],f=cl((v-a[0])/(b[0]-a[0]),0,1);return[0,1,2].map(k=>Math.round(a[1][k]+(b[1][k]-a[1][k])*f))};
const FLD=[[0,[122,92,58]],[.25,[160,128,56]],[.45,[150,160,56]],[.65,[78,150,44]],[.85,[36,140,48]],[1,[32,170,70]]];
const PLT=[[0,[107,68,35]],[.25,[150,110,45]],[.45,[190,175,58]],[.65,[110,185,45]],[.85,[45,190,60]],[1,[70,255,110]]];
function ndviColor(v){return`rgb(${ramp(FLD,v)})`}
const DUR=4200;
const CF=['','Not very sure','Fairly sure','Very sure'],CC=['','#ff9a85','#f0d27a','#8ee6a6'];
const CT=['','There is little data or the image is not clear. Take it as a hint, not as a fact.','The sources partly agree. It is worth confirming it in the field.','Several sources agree and the image is clear. Even so, walk the plot before deciding.'];
const DN=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'],DNS=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'],TD0=new Date().getDay(),D=[0,1,2,3,4,5,6].map(k=>DN[(TD0+k)%7]),DS=[0,1,2,3,4,5,6].map(k=>DNS[(TD0+k)%7]),MM=[3.8,2.4,0,0,1.6,3.1,2.2];
const SAT=[1,.85,1.25];
const S={rx:58,rz:-128,z:1,trx:58,trz:-128,tz:1,tab:'veg',past:0,day:0,ndvi:.85,crop:'tomate',scan:0,hum:41,s:100,t0:0};
const base=()=>cl(Math.min(innerWidth/620,innerHeight/560),.5,1.25);
S.z=S.tz=base();
function R(a){return()=>{a|=0;a=a+1831565813|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
function minerals(x,y,r,s){const q=R(s*7+3);let h='';
 for(let k=0;k<11;k++){const a=q()*6.283,d=Math.sqrt(q())*r*.85,px=x+Math.cos(a)*d,py=y+Math.sin(a)*d,t=q();
  if(t<.4){const w=4+q()*5,e=3+q()*3.5;h+=`<g transform="translate(${px} ${py}) rotate(${q()*180})"><ellipse cx="1" cy="1.8" rx="${w}" ry="${e}" fill="#0006"/><ellipse rx="${w}" ry="${e}" fill="${['#b7ad9c','#8f877a','#d1c8b6'][k%3]}" stroke="#4a4338" stroke-width=".9"/><ellipse cx="${-w*.3}" cy="${-e*.3}" rx="${w*.4}" ry="${e*.35}" fill="#fff7"/></g>`}
  else if(t<.75)h+=`<circle cx="${px+1}" cy="${py+1.8}" r="3.6" fill="#0006"/><circle cx="${px}" cy="${py}" r="3.6" fill="${['#f4f1e8','#7fc7ff','#ffb347'][k%3]}" stroke="#0005" stroke-width=".7"/><circle cx="${px-1.1}" cy="${py-1.1}" r="1.2" fill="#fff"/>`;
  else h+=`<g transform="translate(${px} ${py}) rotate(${q()*40-20}) scale(1.3)"><polygon points="0,-7 4.5,-1 0,7 -4.5,-1" fill="#c07aff" stroke="#fff" stroke-width=".9"/><polygon points="0,-7 4.5,-1 0,1" fill="#e9c9ff"/></g>`}
 return h}
function m2t(t){$('m2').textContent=t;$('m2').dataset.tip=t=='2D'?'2D view':'3D view'}
function clock(){const el=$('clk'),sm=innerWidth<721,tk=()=>{el.textContent=new Date().toLocaleString('en-GB',{day:'numeric',month:sm?'short':'long',year:'numeric',hour:'2-digit',minute:'2-digit',second:sm?undefined:'2-digit',hour12:false}).replace(/, | at /,' · ')};tk();setInterval(tk,1000)}
const HUM=[[0,[225,170,60]],[.35,[235,210,90]],[.6,[110,200,200]],[1,[50,130,235]]];
const humFill=()=>`rgba(${ramp(HUM,S.hum/100)},.6)`;
const dry=()=>{const p=Math.round(cl((80-S.hum)*.9,0,80));return{p,a:(p*1.5/100).toFixed(2)+' ha'}};
const hmm=i=>{const d=cl((75-S.hum)/55,0,1);return d<.02?0:Math.round(MM[i]*(.4+1.2*d)*10)/10};
const FERT=[['Zone 1',120],['Zone 2',95],['Zone 3',55],['Zone 4',35]];
const fert=()=>'<div class="lab" style="color:var(--amb);margin-bottom:2px">SUGGESTED FERTILIZATION BY ZONE</div>'+FERT.map(([z,k])=>`<div class="rb"><span>${z}</span><i><u style="width:${k/1.5}%;background:#e8b878"></u></i><b style="color:#e8b878">${k} kg/ha</b></div>`).join('')+'<div style="margin-top:6px;font-size:12px;color:var(--mut)">More where there is less organic matter. Indicative demo values.</div>';
const pcn=()=>{const tb=S.tab;
 if(S.past)return'<b>38%</b> of the field with plants: the part of the plot (1.5 ha) that was covered by vegetation in the archive image.';
 if(tb=='veg')return`<b>${Math.round(cl(8+(1-S.ndvi)*60,5,68))}%</b> of the field with low vigor: the part of the plot (1.5 ha) marked with orange patches, where the plants are less green than in the rest.`;
 if(tb=='suelo')return'<b>28%</b> of the field (0.42 ha of 1.5 ha): the area of the patches, where the soil has low organic matter, relative to the whole plot.';
 if(tb=='plagas')return'<b>25%</b> of the field (0.38 ha of 1.5 ha): the area of the red patches, where pests are more likely to appear today.';
 if(tb=='agua'){const g=dry();return`<b>${g.p}%</b> of the field (${g.a} of 1.5 ha): the area of the patches, where the soil is drier than in the rest of the plot.`}
 return`<b>${rank()[0][1]}%</b> viability: not a field area, but the estimated probability that the crop will adapt to this plot based on moisture, rainfall and soil.`};
function updHum(){document.querySelectorAll('#zones path').forEach(p=>p.setAttribute('fill',humFill()));render(1)}
const KS=8,TH=.73,CS=Math.cos(TH),SN=Math.sin(TH),WL=[7.4,-6.3,57.759];
const SL=(u,v)=>{const a=u-(WL[0]-WL[2]/2),b=v-(WL[1]+WL[2]/2);return[450+KS*(a*CS+b*SN),450+KS*(-a*SN+b*CS)]};
const BP=SL(0,0),LOTW=[[WL[0],WL[1]],[WL[0]-WL[2],WL[1]],[WL[0]-WL[2],WL[1]+WL[2]],[WL[0],WL[1]+WL[2]]].map(p=>SL(p[0],p[1]));
// Surroundings taken from the satellite view (image coordinates: 924×950 px, building at 537,318; 8.5 px per meter)
const inLot=(x,y,m)=>{const dx=(x-537)/8.5,dz=(y-318)/8.5,u=dx*CS-dz*SN,v=dx*SN+dz*CS;return u>WL[0]-WL[2]-m&&u<WL[0]+m&&v>WL[1]-m&&v<WL[1]+WL[2]+m};
const ROADS=[[26,[-60,-30],[0,50],[100,170],[190,310],[252,455]],[24,[252,462],[330,395],[415,335],[500,262],[545,238]],[26,[250,470],[190,540],[120,610],[40,690],[-60,780]],[24,[260,470],[400,540],[520,600],[610,665],[700,725],[820,790],[980,840]],[20,[620,690],[640,770],[590,850],[690,945],[770,1030]],[22,[0,690],[40,770],[130,840],[230,905],[290,960],[340,1040]],[18,[410,945],[520,885],[580,855]]];
const HS=[[258,547,30,22,.5,'#e3e7ea'],[335,585,46,38,-.35,'#d9dde1'],[208,610,56,50,.4,'#e8ebee'],[150,640,44,36,.5,'#c7ccd2'],[382,625,36,36,0,'#c58a73'],[170,745,38,32,.3,'#e3e7ea'],[230,765,36,36,.2,'#c7ccd2'],[490,745,58,48,.4,'#dfe3e7'],[435,795,68,38,-.35,'#e8ebee'],[300,885,56,48,.3,'#d9dde1'],[338,915,34,36,0,'#c7ccd2'],[600,785,56,56,.1,'#e8ebee'],[752,928,46,38,.2,'#dfe3e7'],[595,930,38,34,0,'#d9dde1'],[28,810,50,46,.1,'#e3e7ea'],[-70,610,50,40,.2,'#d9dde1'],[880,880,50,40,.2,'#c7ccd2']];
const dseg=(x,y,a,b)=>{const dx=b[0]-a[0],dy=b[1]-a[1],t=cl(((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy),0,1);return Math.hypot(x-a[0]-t*dx,y-a[1]-t*dy)};
const nearRoad=(x,y,d)=>ROADS.some(([w,...q])=>q.some((a,i)=>i&&dseg(x,y,q[i-1],a)<d+w/2));
const CLR=[[450,225,80,50],[745,490,60,60],[830,330,40,40],[560,470,50,40]];
function terrain(p){
 const c=$('terrain').getContext('2d'),r=R(11),f=KS/8.5;
 c.setTransform(f,0,0,f,250+BP[0]-537*f,250+BP[1]-318*f);
 c.fillStyle=p?'#a39a78':'#78884f';c.fillRect(-400,-400,2000,2000);
 for(let i=0;i<300;i++){c.fillStyle=r()<.5?(p?'#c2b68f2a':'#c7b57e33'):(p?'#8a806a2a':'#5d7a3a33');c.beginPath();c.arc(-300+r()*1500,-300+r()*1500,15+r()*45,0,7);c.fill()}
 ROADS.forEach(([w,...q])=>[[w+6,p?'#9c8a68':'#a98759'],[w,p?'#c9b891':'#d2b184']].forEach(([lw,col])=>{c.strokeStyle=col;c.lineWidth=lw;c.lineCap=c.lineJoin='round';c.beginPath();q.forEach((a,i)=>i?c.lineTo(a[0],a[1]):c.moveTo(a[0],a[1]));c.stroke()}));
 for(let i=0;i<3400;i++){const x=-300+r()*1500,y=-300+r()*1500,q=r(),vil=x>40&&x<720&&y>520&&y<1010,clr=CLR.some(([a,b,rx,ry])=>((x-a)/rx)**2+((y-b)/ry)**2<1);
  if(q>(vil?.1:clr?.12:.82)||inLot(x,y,0)||nearRoad(x,y,20))continue;
  const rr=8+r()*14;c.fillStyle=p?`hsl(${60+r()*20},12%,${34+r()*10}%)`:`hsl(${95+r()*30},${38+r()*14}%,${17+r()*12}%)`;c.beginPath();c.arc(x,y,rr,0,7);c.fill();
  c.fillStyle=p?'#ffffff12':'#9fd36a22';c.beginPath();c.arc(x-rr*.25,y-rr*.3,rr*.55,0,7);c.fill()}
 HS.forEach(([x,y,w,h,a,col],i)=>{if(inLot(x,y,5)||(p&&i>4))return;c.save();c.translate(x,y);c.rotate(a);c.fillStyle='#0005';c.fillRect(-w/2+5,-h/2+6,w,h);c.fillStyle=col;c.fillRect(-w/2,-h/2,w,h);c.strokeStyle='#0003';c.lineWidth=1.5;c.beginPath();c.moveTo(-w/2,0);c.lineTo(w/2,0);c.stroke();c.restore()});
 c.setTransform(1,0,0,1,250,250);c.beginPath();LOTW.forEach((q,i)=>i?c.lineTo(q[0],q[1]):c.moveTo(q[0],q[1]));c.closePath();c.fillStyle=p?'#a79d7d':'#9aa266';c.fill();
}
function facade(){
 const c=document.createElement('canvas');c.width=600;c.height=540;const x=c.getContext('2d'),r=R(21);
 x.fillStyle='#eceae3';x.fillRect(0,0,600,540);x.fillStyle='#4aa3c7';x.fillRect(0,510,600,30);
 for(let i=0;i<110;i++){const a=i%2?400+r()*200:r()*200;x.fillStyle=`hsl(${Math.floor(r()*360)},70%,55%)`;x.beginPath();x.arc(a,(i%2?430:400)+r()*90,8+r()*22,0,7);x.fill()}
 x.fillStyle='#22305c';x.fillRect(200,290,200,250);x.fillStyle='#16203f';x.fillRect(299,290,2,250);
 x.textAlign='center';x.fillStyle='#4a5058';x.font='bold 34px Georgia,serif';x.fillText('LUJÁN MODEL FACTORY',300,250);
 x.font='24px Georgia,serif';x.fillText('Sweets and Preserves',300,282);x.fillStyle='#222';x.font='bold 26px Georgia,serif';x.fillText('THE CHRYSALIS',500,380);
 return c.toDataURL()}
// Empty building (6 × 11 m, estimated dimensions) on the square plot; 1 m = KS px, local axes: x width, y length (toward the back), z height
function site(){
 const b=$('bld'),W=6,L=11,HE=3.6,HR=5.4,k=KS;
 b.style.transform=`translate3d(${BP[0]}px,${BP[1]}px,0) rotateZ(${-TH}rad)`;
 const T3=(x,y,z)=>`translate3d(${x*k}px,${y*k}px,${z*k}px) `;
 const F=(p,w,h,tr,bg,css,html)=>{const d=document.createElement('div');d.className='f';d.style.cssText=`width:${w*k}px;height:${h*k}px;transform:${tr};background:${bg};${css||''}`;if(html)d.innerHTML=html;p.appendChild(d)};
 const BX=(p,x0,x1,y0,y1,z0,z1,top,s1,s2)=>{F(p,x1-x0,y1-y0,T3(x0,y0,z1),top);
  [y0,y1].forEach(y=>F(p,x1-x0,z1-z0,T3(x0,y,z1)+'rotateX(-90deg)',s1));
  [x0,x1].forEach(x=>F(p,y1-y0,z1-z0,T3(x,y0,z1)+'rotateZ(90deg) rotateX(-90deg)',s2))};
 const wall='#eceae3',wl2='#dcd9d0',gp=`polygon(50% 0,100% ${(HR-HE)/HR*100}%,100% 100%,0 100%,0 ${(HR-HE)/HR*100}%)`;
 F(b,W+.8,L+.8,T3(-W/2+.4,-L/2+.6,.1),'#0000004d','border-radius:6px');
 F(b,W,L,T3(-W/2,-L/2,.2),'#b8b4aa');
 const win=[-3,0,3].map(z=>`<i class="wn" style="left:${(L/2+z-.35)/L*100}%"></i>`).join('');
 [-1,1].forEach(s=>F(b,L,HE,T3(s*W/2,-L/2,HE)+'rotateZ(90deg) rotateX(-90deg)',s<0?wl2:wall,'',win));
 F(b,W,HR,T3(W/2,-L/2,HR)+'rotateZ(180deg) rotateX(-90deg)',`url(${facade()}) 0 0/100% 100%`,`clip-path:${gp}`);
 F(b,W,HR,T3(-W/2,L/2,HR)+'rotateX(-90deg)',wl2,`clip-path:${gp}`);
 BX(b,-W/2-.5,W/2+.5,-L/2-1.3,-L/2,0,.15,'#b0aca2','#9c988e','#9c988e');
 BX(b,-W/2-2.6,-W/2,L/2-3.2,L/2,0,2.6,'#f4f1ea','#f4f1ea','#e6e2d8');
 BX(b,-W/2-2.8,-W/2+.1,L/2-3.4,L/2+.2,2.6,2.72,'#8c99a6','#7f8b97','#7f8b97');
 const stn='radial-gradient(circle at 30% 40%,#a59a8b 0 2.2px,transparent 2.6px) 0 0/9px 8px,radial-gradient(circle at 70% 70%,#6f665a 0 2.5px,transparent 3px) 4px 3px/10px 9px,#8a7f72';
 BX(b,-W/2-12,-W/2,-L/2-.475,-L/2-.025,0,2.2,'#a0958a',stn,stn);
 BX(b,W/2,W/2+4,-L/2-.35,-L/2-.15,0,2,'#b5654a','repeating-linear-gradient(0deg,#b5654a 0 6px,#9a5340 6px 7px)','#9a5340');
 const rf=document.createElement('div');rf.id='roof';b.appendChild(rf);
 const ov=.35,ex=W/2+ov,ey=HE-ov*(HR-HE)/(W/2),sl=Math.hypot(ex,HR-ey),al=Math.atan2(HR-ey,ex),RL=L+.6,rc='repeating-linear-gradient(0deg,#8f9ba8 0 3px,#7b8794 3px 6px)';
 F(rf,sl,RL,T3(0,-RL/2,HR)+`rotateY(${al}rad)`,rc);
 F(rf,sl,RL,T3(0,-RL/2,HR)+`rotateY(${Math.PI-al}rad)`,rc);
 BX(rf,-.15,.15,-RL/2,RL/2,HR,HR+.12,'#a9b4bf','#a9b4bf','#a9b4bf');
}
(function(){const r=R(5),g=Array.from({length:49},()=>r()),L=(a,b,t)=>a+(b-a)*t;let h='';
for(let gx=0;gx<24;gx++)for(let gy=0;gy<24;gy++){const u=gx/4,w=gy/4,i=u|0,j=w|0,fu=u-i,fw=w-j,v=L(L(g[i*7+j],g[(i+1)*7+j],fu),L(g[i*7+j+1],g[(i+1)*7+j+1],fu),fw)+(r()-.5)*.12;
 if(v>.45)h+=`<rect x="${126+gx*27}" y="${126+gy*27}" width="27" height="27" fill="#000" fill-opacity="${((v-.45)*.6).toFixed(2)}"/>`;
 else if(v<.3)h+=`<rect x="${126+gx*27}" y="${126+gy*27}" width="27" height="27" fill="#fff" fill-opacity="${((.3-v)*.4).toFixed(2)}"/>`}
$('deco').innerHTML=h})();
const SPR='<svg class="pl" viewBox="0 0 20 22" width="26" height="29"><path d="M10 22V10" stroke="#5a4222" stroke-width="2.4"/><path d="M10 12C3 12 1 5 3 3c5 0 7 4 7 9z"/><path d="M10 10c0-5 3-8 8-8 1 4-1 9-8 8z"/></svg>';
function blob(x,y,r,s){const q=R(s),n=9,p=[];for(let i=0;i<n;i++){const a=i/n*6.283,k=r*(.75+.5*q());p.push([x+Math.cos(a)*k,y+Math.sin(a)*k])}
 let d=`M${(p[0][0]+p[n-1][0])/2} ${(p[0][1]+p[n-1][1])/2}`;for(let i=0;i<n;i++){const a=p[i],b=p[(i+1)%n];d+=`Q${a[0]} ${a[1]} ${(a[0]+b[0])/2} ${(a[1]+b[1])/2}`}return d+'Z'}
function marks(f){if(f&&!S.past&&!S.scan&&document.querySelector('.bb')){const e=document.querySelector('.bb .sg');if(S.tab=='veg'&&e){const g=stage(S.ndvi);e.querySelector('.em').textContent=g[0];e.querySelector('small').textContent=g[2]}return}document.querySelectorAll('.bb').forEach(e=>e.remove());if(S.past||S.scan)return;const d=T[S.tab];let a;
 const sg=(em,tx,c)=>`<div class="sg" style="--c:${c}"><span class="em">${em}</span><small>${tx}</small></div>`;
 if(S.tab=='veg'){const g=stage(S.ndvi),q=R(9);a=[[480,450,sg(g[0],g[2],'#8ee6a6')]];d.z.forEach(([x,y,r])=>{for(let k=0;k<7;k++){const t=q()*6.283,u=Math.sqrt(q())*r*.9;a.push([x+Math.cos(t)*u,y+Math.sin(t)*u,SPR])}})}
 else if(S.tab=='rot')a=[[480,450,sg('🌱',rank()[0][0],'#8ee6a6')]];
 else if(S.tab=='suelo')a=d.mk.map(([x,y,u,v,c])=>[x,y,`<div class="sg" style="--c:${c}">${u}<small>${v}</small></div>`]);
 else a=d.z.slice(0,5).map(([x,y])=>[x,y,`<span class="em">${d.mk}</span>`]);
 a.forEach(([x,y,h],i)=>{const e=document.createElement('div');e.className='bb';e.dataset.x=x;e.dataset.y=y;e.innerHTML=h;$('world').appendChild(e);setTimeout(()=>e.classList.add('on'),f?0:60+i*30)})}
function render(f){
 const d=T[S.tab],p=S.past;let c=p?3:d.c,h;
 if(S.scan)h=`<div class="lab"><i class="dot"></i>SCANNING THE FIELD</div><div class="ttl" style="font-size:17px">${d.scan}</div><div class="pg"><i id="pgi"></i></div>`;
 else{
  let l='SEEN FROM SATELLITE',t=d.t,a=[d.a,'AREA'],b=[d.p,'OF THE FIELD'],x=d.risk?bars(d.risk,1):'',src=d.src;
  if(p){l='IMAGE FROM 2003 · SENTINEL-2';t='soil with little cover';a=['1.5 ha','AREA'];b=['38%','WITH PLANTS'];x='';src='archive Sentinel-2 images'}
  else if(S.tab=='veg'){const g=stage(S.ndvi);t=g[1];a=[fm(S.ndvi),'NDVI (GREENNESS)'];b=[C[S.crop][0],'CURRENT CROP'];x=g[3]}
  else if(S.tab=='rot'){const r=rank();l='SUGGESTION · NEXT CROP';t='plant '+r[0][0].toLowerCase();a=['1.5 ha','PLOT'];b=[r[0][1]+'%','VIABILITY'];x=bars(r,2)}
  else if(S.tab=='agua'){const g=dry();a=[g.a,'DRY AREA'];b=[g.p+'%','OF THE FIELD']}
  else if(S.tab=='suelo')x=fert();
  h=`<div class="hd"><div style="flex:1"><div class="lab"><i class="dot"></i>${l}</div><div class="ttl">${t}</div></div><span class="inf" tabindex="0" role="button" aria-label="What the display means">!<span class="tt">${p?INFO.past:INFO[S.tab]}</span></span><button class="ib" data-a="more" aria-label="More detail">⤢</button><button class="ib" data-a="x" aria-label="Close">✕</button></div>
 <div class="st"><div><b>${a[0]}</b><small>${a[1]}</small></div><div><b>${b[0]}</b><small>${b[1]}</small></div><button class="cf" data-a="pop"><b style="color:${CC[c]}">${CF[c]}</b><small>HOW SURE IS IT?</small></button></div>
 <div id="pop" hidden><div class="mt">${[1,2,3].map(i=>`<i style="background:${i<=c?CC[c]:'#ffffff30'}"></i>`).join('')}</div>${CT[c]}</div>
 <div class="pcn">${pcn()}</div>
 <div class="xt">${x}</div>
 <div id="more" hidden>Sources: ${src}. This is a hint from the satellite: it does not replace your judgment or walking the field.${S.tab=='veg'&&!p?' NDVI values are indicative: they change depending on the crop.':''}</div>`}
 $('c1b').innerHTML=h;
 $('tabs').innerHTML='<b class="dl">DEMONSTRATION</b>'+Object.keys(T).map(k=>`<button class="${k==S.tab?'on':''}" data-k="${k}">${T[k].ic}<span>${T[k].n}</span></button>`).join('');
 const off=S.scan||p;$('c2').hidden=off;$('wat').hidden=S.tab!='agua';$('ndw').hidden=S.tab!='veg';$('hmw').hidden=S.tab!='agua';$('tip').hidden=!d.tip;if(d.tip){$('tipt').textContent=d.tip;$('tipl').textContent=d.tl||'WHAT TO LOOK FOR IN THE FIELD';$('tip').className=d.imp?'imp':''}
 $('cont').style.opacity=S.tab=='agua'&&!off?1:0;
 $('fp').setAttribute('fill',p?'#8a6d44':ndviColor(S.ndvi));{const w=$('world').style;w.setProperty('--pc','rgb('+ramp(PLT,S.ndvi)+')');w.setProperty('--pg',Math.max(0,S.ndvi-.7)*30+'px');w.setProperty('--pd',(1-Math.min(S.ndvi/.6,1))*40+'deg')}
 if(!f){$('zones').style.opacity=0;setTimeout(()=>{$('zones').innerHTML=S.scan||p||S.tab=='rot'?'':d.z.map(([x,y,r],i)=>`<path d="${blob(x,y,r*1.15,i+3)}" fill="${S.tab=='agua'?humFill():d.col}" stroke="${d.ring}" stroke-width="${S.tab=='suelo'?5:3.5}" class="${S.tab=='plagas'?'wz':''}" style="filter:drop-shadow(0 0 ${S.tab=='suelo'?10:6}px ${d.ring})"/>${S.tab=='suelo'?minerals(x,y,r*1.15,i):''}`).join('');$('zones').style.opacity=1},S.scan?0:180)}
 marks(f);water();
}
function water(){const i=S.day,m=hmm(i),td=i==0,h=S.hum,lv=h<30?'dry':h<60?'medium':'high',mm=String(m);
 $('wl').textContent=td?'TODAY · RECOMMENDED IRRIGATION':'PLANNED · '+D[i].toUpperCase();
 $('wm').textContent=m?mm+' mm':'No irrigation';
 $('ws').textContent=D[i]+(td?' (today)':'')+(m?' · 5:00–8:00 am':' · no need to water');
 $('wn').className=td?'td':'';
 $('wn').innerHTML=td?`<span class="bdg">TODAY</span> Today's recommendation based on soil moisture (${h}%, ${lv} moisture): ${m?'water '+mm+' mm early, between 5:00 and 8:00 am.':'no need to water.'} The drier the soil, the more water is suggested.`:`Planned irrigation for ${D[i]}, calculated with the current moisture (${h}%, ${lv} moisture). It may change when a new satellite image arrives.`;
 $('wk').innerHTML=DS.map((d,k)=>`<button class="${hmm(k)?'':'z'} ${k==i?'sel':''} ${k?'':'td'}" data-k="${k}"><svg viewBox="0 0 24 32"><path d="M12 2C12 2 3 14 3 21a9 9 0 0 0 18 0C21 14 12 2 12 2z"/></svg>${k?d:'today'}</button>`).join('')}
function scan(){S.scan=1;S.t0=performance.now();$('app').classList.add('scn');render()}
$('tabs').onclick=e=>{const b=e.target.closest('button');if(!b)return;S.tab=b.dataset.k;$('left').style.display='';scan()};
$('hm').oninput=e=>{S.hum=+e.target.value;updHum()};
$('wk').onclick=e=>{const b=e.target.closest('button');if(!b)return;S.day=+b.dataset.k;water()};
$('c1').onclick=e=>{const b=e.target.closest('button');if(!b)return;const a=b.dataset.a;if(a=='x')$('left').style.display='none';else{const el=$(a);el.hidden=!el.hidden}};
$('crop').onchange=e=>{S.crop=e.target.value;render()};
$('nd').oninput=e=>{S.ndvi=+e.target.value;render(1)};
$('seg').onclick=e=>{const b=e.target.closest('button');if(!b)return;S.past=+b.dataset.p;const p=S.past;
 [...$('seg').children].forEach(x=>x.classList.toggle('on',x==b));$('app').classList.toggle('past',!!p);terrain(p);
 $('bal').textContent=p?'IMAGE FROM 2003 · SENTINEL-2':'LATEST CLEAR IMAGE';
 $('bat').textContent=p?'This is how the same field looked 23 years ago.':'Compare it with 23 years ago.';render()};
$('zi').onclick=()=>S.tz=cl(S.tz*1.25,.4,2.5);$('zo').onclick=()=>S.tz=cl(S.tz*.8,.4,2.5);
$('loc').onclick=()=>{const fr=Math.cos((S.trz+128)*Math.PI/180)>0,g=fr?52:-128;S.trx=58;S.trz=g+360*Math.round((S.trz-g)/360);S.tz=base();m2t('2D')};
$('cmpb').onclick=()=>S.trz=0;
$('m2').onclick=()=>{if(S.trx>5){S.trx=0;S.trz=0;m2t('3D')}else{S.trx=58;S.trz=-128;m2t('2D')}};
const P=new Map(),ap=$('app');let ld=0;
ap.addEventListener('pointerdown',e=>{if(e.target.closest('.ui'))return;ap.setPointerCapture(e.pointerId);P.set(e.pointerId,[e.clientX,e.clientY]);ld=0});
ap.addEventListener('pointermove',e=>{const o=P.get(e.pointerId);if(!o)return;P.set(e.pointerId,[e.clientX,e.clientY]);
 if(P.size==1){S.trz+=(e.clientX-o[0])*.4;S.trx=cl(S.trx-(e.clientY-o[1])*.3,0,75)}
 else if(P.size==2){const [a,b]=[...P.values()],d=Math.hypot(a[0]-b[0],a[1]-b[1]);if(ld)S.tz=cl(S.tz*d/ld,.4,2.5);ld=d}});
['pointerup','pointercancel'].forEach(t=>ap.addEventListener(t,e=>{P.delete(e.pointerId);ld=0}));
ap.addEventListener('wheel',e=>{if(e.target.closest('#left'))return;e.preventDefault();S.tz=cl(S.tz*Math.exp(-e.deltaY*.0012),.4,2.5)},{passive:false});
addEventListener('resize',()=>S.tz=base());
function loop(t){
 const k=.14;S.rx+=(S.trx-S.rx)*k;S.rz+=(S.trz-S.rz)*k;S.z+=(S.tz-S.z)*k;
 if(S.scan){const q=Math.max(0,(t-S.t0)/DUR);if(q>=1){S.scan=0;$('app').classList.remove('scn');render()}else{S.s=840-740*q;const g=$('pgi');if(g)g.style.width=q*100+'%'}}
 const s=S.s;
 $('world').style.transform=`scale(${S.z}) rotateX(${S.rx}deg) rotateZ(${S.rz}deg)`;
 $('beam').style.transform=`translate3d(${s}px,100px,0) rotateZ(90deg) rotateX(90deg)`;
 $('sat').style.transform=`translate3d(${s}px,136px,235px) rotateZ(${-S.rz}deg) rotateX(${-S.rx}deg) translate(-50%,-50%)`;
 if(S.scan&&window.drawSat)drawSat(S.rx*Math.PI/180,S.rz*Math.PI/180);
 $('band').setAttribute('transform','translate('+s+',0)');$('band').style.opacity=S.scan?1:0;$('rr').setAttribute('x',S.scan?s:0);$('rr').setAttribute('width',S.scan?900-s:900);
 $('cmp').style.transform=`rotate(${S.rz}deg)`;
 {const b=$('loc'),fr=Math.cos((S.rz+128)*Math.PI/180)>0;if(b.classList.contains('tofront')==fr){b.classList.toggle('tofront',!fr);b.dataset.tip=fr?'View back':'View front'}}
 document.querySelectorAll('.bb').forEach(e=>e.style.transform=`translate3d(${e.dataset.x}px,${e.dataset.y}px,26px) rotateZ(${-S.rz}deg) rotateX(${-S.rx}deg) translate(-50%,-100%)`);
 requestAnimationFrame(loop)}
clock();terrain(0);site();scan();requestAnimationFrame(loop);

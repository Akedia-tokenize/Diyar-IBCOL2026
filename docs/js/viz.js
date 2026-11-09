/** DIYAR V5.2 charts. Source driven, visually concise, no alternative tables. */
const E=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const n=x=>Number(x)||0;
const fmt=(v,d=1)=>Number(v).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
const palette=['#3D63F0','#8660D8','#7894AD','#D58DAF'];
const axis=(W,H,L=70,R=38,T=27,B=55)=>({W,H,L,R,T,B,PW:W-L-R,PH:H-T-B});
const sourceName=s=>String(s).includes('gas')?'Anchor gas data':String(s).includes('records')?'Signed records':String(s).includes('building')?'Building readings':String(s).includes('replay')?'Replay evidence':String(s).includes('reports')?'Historical reports':String(s).includes('e1')?'Custody experiment':String(s).includes('e2')?'Calibration experiment':String(s).includes('e3')?'Detection experiment':String(s).includes('e4')?'Review experiment':String(s).includes('summary')?'Reference summary':'Reference data';
const sourceHref=s=>s.startsWith('anchor/')?'./'+s:'./data/'+s;
const wrap=(id,title,subtitle,svg,file,unit='')=>`<figure class="v5-figure v52-figure"><div class="v5-figure-head"><div><span class="eyebrow">${E(id)} · EVIDENCE FIGURE</span><h3>${E(title)}</h3><p>${E(subtitle)}</p></div></div><div class="v5-graphic">${svg}</div><figcaption><span>${E(unit||'Reference evidence')}</span><a class="v52-source-link" href="${E(sourceHref(file))}" target="_blank" rel="noopener" title="${E(file)}">View source ↗</a></figcaption></figure>`;
const grid=(a,high,formatter)=>[0,.25,.5,.75,1].map(z=>`<g><line class="v5-grid" x1="${a.L}" x2="${a.W-a.R}" y1="${a.T+a.PH*(1-z)}" y2="${a.T+a.PH*(1-z)}"/><text class="v5-axis" x="${a.L-14}" y="${a.T+a.PH*(1-z)+4}" text-anchor="end">${E(formatter(high*z))}</text></g>`).join('');
export function bars(id,title,items,file,{max=null,subtitle='',unit='',formatter=x=>fmt(x),h=315}={}){
 if(!Array.isArray(items)||!items.length)return '';
 const a=axis(840,h,80,25,30,66), values=items.map(x=>n(x.value)), high=Math.max(max||0,...values,1)*1.10, step=a.PW/items.length, bw=Math.min(76,step*.67);
 const every=items.length>18?4:items.length>10?2:1;
 const ticks=items.map((x,i)=>{if(!(i%every===0||i===items.length-1))return '';const label=String(x.label);return `<text class="v5-axis" x="${a.L+(i+.5)*step}" y="${a.H-27}" text-anchor="middle">${E(label.length>14?label.slice(0,12)+'…':label)}</text>`}).join('');
 const cols=items.map((x,i)=>{let y=a.T+a.PH*(1-values[i]/high),cx=a.L+(i+.5)*step, isPeak=items.length>=20&&values[i]>=Math.max(...values)*.89;
 const c=x.highlight?'v52-bar-special':isPeak?'v52-bar-peak':items.length>=20&&i<7?'v52-bar-night':'';
 return `<g class="v52-bar-hit"><title>${E(x.label)} · ${E(formatter(values[i]))} ${E(unit)}</title><rect class="v5-bar ${c}" x="${cx-bw/2}" y="${y}" width="${bw}" height="${Math.max(.5,a.T+a.PH-y)}" rx="${Math.min(5,bw/3)}"/><rect x="${cx-step/2}" y="${a.T}" width="${step}" height="${a.PH}" fill="transparent"/>${items.length<=8?`<text class="v5-value" x="${cx}" y="${Math.max(a.T+12,y-10)}" text-anchor="middle">${E(formatter(values[i]))}</text>`:''}</g>`}).join('');
 const svg=`<svg viewBox="0 0 ${a.W} ${a.H}" role="img" aria-label="${E(title)}"><title>${E(title)}</title><desc>${E(subtitle)}. ${items.map(x=>`${x.label}: ${x.value}`).join('; ')}</desc>${grid(a,high,formatter)}${cols}${ticks}</svg>`;
 return wrap(id,title,subtitle,svg,file,unit);
}
export function line(id,title,series,labels,file,{subtitle='',unit='',ymax=null,percent=false,height=310,flagIndices=[]}={}){
 if(!series.length||!labels.length)return '';
 const a=axis(840,height,76,47,35,62),all=series.flatMap(s=>s.values.map(n)),high=ymax||Math.max(...all,1)*1.08;
 const X=i=>a.L+i/Math.max(1,labels.length-1)*a.PW,Y=v=>a.T+a.PH*(1-n(v)/high),Ytext=v=>percent?`${fmt(v*100,0)}%`:fmt(v,0);
 const step=labels.length>40?Math.ceil(labels.length/7):labels.length>14?Math.ceil(labels.length/7):1;
 const ticks=labels.map((x,i)=>i%step===0||i===labels.length-1?`<text class="v5-axis" x="${X(i)}" y="${a.H-27}" text-anchor="middle">${E(x)}</text>`:'').join('');
 const lines=series.map((s,j)=>{let c=s.color||palette[j%palette.length],d=s.values.map((v,i)=>`${i?'L':'M'}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join(' ');
 return `<g><path d="${d}" fill="none" stroke="${c}" stroke-width="${j?2.5:3.5}" stroke-linecap="round" stroke-linejoin="round" ${s.dashed?'stroke-dasharray="7 6"':''}/>${s.values.map((v,i)=>`<circle class="v52-data-point" cx="${X(i)}" cy="${Y(v)}" r="${labels.length<=9?4:3}" fill="${c}"><title>${E(s.label)} · ${E(labels[i])} · ${E(Ytext(n(v)))}</title></circle>`).join('')}</g>`}).join('');
 const flags=flagIndices.filter(i=>i>=0&&i<labels.length).map(i=>`<g><path d="M${X(i)} ${Y(series[0].values[i])-13}l-7 -12h14z" fill="#E7A62C"/><title>Flagged ${E(labels[i])}</title></g>`).join('');
 const key=series.map((s,i)=>`<span><i style="background:${s.color||palette[i%palette.length]}"></i>${E(s.label)}</span>`).join('');
 const svg=`<div class="v5-legend">${key}</div><svg viewBox="0 0 ${a.W} ${a.H}" role="img" aria-label="${E(title)}"><title>${E(title)}</title><desc>${E(subtitle)}. Exact values are available for each plotted point.</desc>${grid(a,high,Ytext)}${lines}${flags}${ticks}</svg>`;
 return wrap(id,title,subtitle,svg,file,unit);
}
export function step(id,title,values,labels,file,subtitle=''){
 const entries=values.map((v,i)=>({label:labels[i],value:n(v),i}));if(!entries.length)return '';
 const first=entries[0],last=entries.at(-1),change=last.value-first.value;
 const cards=entries.map((d,i)=>`<div class="v52-history-stage ${i===entries.length-1?'is-current':''}"><span class="v52-stage-dot"></span><span class="v52-stage-date">${E(d.label)}</span><strong>${fmt(d.value,2)} <small>kWh</small></strong><span class="v52-stage-state">${i===0?'Original report':d.value===first.value?'Original preserved':'New version recorded'}</span></div>`).join('');
 return wrap(id,title,subtitle,`<div class="v52-history"><div class="v52-history-lead"><span>First published <strong>${fmt(first.value,2)}</strong></span><span class="v52-history-arrow">→</span><span>Latest recorded <strong>${fmt(last.value,2)}</strong></span></div><div class="v52-history-track">${cards}</div><div class="v52-history-delta">${change>0?'+':''}${fmt(change,2)} kWh <span>from later signed evidence, not a new original report</span></div></div>`,file,'Historical energy');
}
export function strip(id,title,categories,file,{subtitle=''}={}){
 const total=categories.reduce((a,x)=>a+n(x.value),0)||1;
 return `<div class="v5-stripbox"><div class="v5-strip-head"><span class="eyebrow">${E(id)}</span><h3>${E(title)}</h3><p>${E(subtitle)}</p></div><div class="v5-strip" role="img" aria-label="${E(categories.map(x=>x.label+': '+x.value).join(', '))}">${categories.map((x,i)=>`<span class="v5-strip-segment v5-strip-${i}" style="width:${n(x.value)/total*100}%" title="${E(x.label)} ${E(x.value)}"></span>`).join('')}</div><div class="v5-strip-labels">${categories.map(x=>`<span><b>${E(x.value)}</b> ${E(x.label)}</span>`).join('')}</div><small><a href="${E(sourceHref(file))}" target="_blank" rel="noopener">View source ↗</a></small></div>`;
}
export function chainStrip(ledger=[],results=[]){let verified=results.find(x=>x.id==='chain')?.status==='pass';return `<div class="v5-chain"><span class="eyebrow">C5 · 91 DAY CHAIN · ${verified?'VERIFIED':'NOT YET VERIFIED'}</span><div class="v5-chain-cells" aria-label="${ledger.length} day commitments, ${verified?'verified':'awaiting execution'}">${ledger.map((_,i)=>`<i class="${verified?'is-pass':''}" title="Day ${i+1}"></i>`).join('')}</div><small>Cells confirm only after a real local check.</small></div>`;}

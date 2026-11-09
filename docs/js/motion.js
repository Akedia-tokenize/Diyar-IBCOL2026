/** V5 progressive enhancements. No status animations or invented verification results. */
let observer;
export function enhanceMotion(root=document){
 const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
 observer?.disconnect();
 const els=[...root.querySelectorAll('.section, .v5-figure, .v5-kpi, .flow5-wrap')];
 if(reduced||!('IntersectionObserver' in window)) {els.forEach(el=>el.classList.add('v5-visible'));return;}
 observer=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add('v5-visible');observer.unobserve(e.target);}}),{threshold:.08});
 els.forEach(el=>{el.classList.add('v5-reveal');observer.observe(el)});
}
export function bindRotatingWord(){const e=document.getElementById('v5-rotating-word');if(!e||matchMedia('(prefers-reduced-motion: reduce)').matches)return;
 const words=['evidence.','signature.','grade.','history.'];let i=0;const handle=setInterval(()=>{if(!e.isConnected){clearInterval(handle);return;} if(!e.matches(':hover')){i=(i+1)%words.length;e.textContent=words[i];}},2500);
}
export function flipTable(el){const f=el.closest('.v5-figure');if(!f)return;const svg=f.querySelector('.v5-graphic'),table=f.querySelector('.v5-data-table');let show=table.hidden;table.hidden=!show;svg.hidden=show;el.textContent=show?'Chart ↗':'Table ↗';el.setAttribute('aria-expanded',String(show));}
/** Animate published KPI figures, not cryptographic outcomes. The final value is always available in aria-label. */
export function countPublishedFigures(root=document){
 const els=[...root.querySelectorAll('.v5-kpi-row .value')];
 if(matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window))return;
 const seen=new WeakSet();
 const obs=new IntersectionObserver(entries=>{
   for(const e of entries){if(!e.isIntersecting||seen.has(e.target))continue;
     const el=e.target;seen.add(el);obs.unobserve(el);
     const original=el.textContent.trim();const match=original.match(/^(~?)([0-9,]+)(.*)$/);if(!match)continue;
     const end=Number(match[2].replaceAll(',',''));if(!Number.isFinite(end))continue;
     const prefix=match[1],suffix=match[3],digits=match[2].includes(',');
     const duration=1400;let began;
     el.setAttribute('aria-label',original);
     el.style.minWidth=Math.max(el.getBoundingClientRect().width,32)+'px';
     const frame=ts=>{began??=ts;const fraction=Math.min(1,(ts-began)/duration);const ease=1-Math.pow(1-fraction,3);
       const val=Math.round(end*ease),number=digits?val.toLocaleString('en-US'):String(val);
       el.textContent=prefix+number+suffix;
       if(fraction<1&&el.isConnected)requestAnimationFrame(frame);else{el.textContent=original;el.style.removeProperty('min-width');}
     };
     requestAnimationFrame(frame);
   }
 },{threshold:.5});
 els.forEach(el=>obs.observe(el));
}
/** Progressive disclosure for long explanatory copy; no scientific claims are deleted. */
export function condenseExposition(root=document){
 if(!root?.querySelectorAll||!document.createElement)return;
 const targets=root.querySelectorAll('.result-block > p, .lineage-card > p, .v5-bento-small > p, .trust-explainer p, .card > p, .v5-advanced-workflow > p');
 for(const p of targets){
  const plain=(p.textContent||'').trim();
  if(plain.length<=140||p.closest('details, .notice, .checklist, .check-row, .v52-graph, .v52-time-section'))continue;
  const end=plain.indexOf('. ');
  const brief=(end>30&&end<142)?plain.slice(0,end+1):plain.slice(0,Math.min(118,plain.length)).replace(/\s+\S*$/,'')+'…';
  const details=document.createElement('details');details.className='v52-note v52-expansion';
  const summ=document.createElement('summary');summ.textContent='Method and limits';
  const original=document.createElement('p');original.innerHTML=p.innerHTML;
  details.append(summ,original);p.textContent=brief;p.after(details);
 }
 if(document.createTreeWalker&&typeof NodeFilter!=='undefined'){
  const targets=[root];
  for(const parent of targets){const walker=document.createTreeWalker(parent,NodeFilter.SHOW_TEXT);while(walker.nextNode()){const t=walker.currentNode;if(t.parentElement?.closest('code,pre,.hash, .mono, .record-json, .evidence-drawer'))continue;t.nodeValue=t.nodeValue.replace(/Fox_office_Joy/g,'Fox Office Joy').replace(/Fox_education_Wendell/g,'Fox Education Wendell').replace(/Fox_education_Renna/g,'Fox Education Renna').replace(/meter-000/g,'Meter 000');}}
 }
}

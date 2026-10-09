/* Accessible local SVG charts. All rates/counts come from Python, never browser scoring. */
'use strict';
window.ASRCharts=(()=>{
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const pct=v=>Number.isFinite(v)?(100*v).toFixed(2)+'%':'Not scored';
 const color=(m,i)=>m?.provider==='humain'?'#00878a':m?.provider==='elevenlabs'?'#7662bd':['#00878a','#7662bd'][i%2];
 const short=(s,n)=>s.length>n?s.slice(0,n-1)+'…':s;
 const empty=(el,t)=>el.innerHTML=`<div class="empty-state"><b>No paired scores</b>${esc(t)}</div>`;
 function bars(el,models){
  const good=models.filter(m=>Number.isFinite(m.wer)&&Number.isFinite(m.cer));
  if(!good.length)return empty(el,'Historical results are still listed below. The selected pair has no common successful test cases.');
  const w=Math.max(300,el.clientWidth-28),left=20,right=82,span=w-left-right;
  const cap=Math.max(.05,...good.flatMap(m=>[m.wer,m.cer]))*1.12;
  const height=good.length*107+53;
  let body=`<title>Paired WER and CER. Lower is better.</title><desc>Each bar is based on the same shared reference cases. Exact counts are in the chart-values table.</desc>`;
  good.forEach((m,i)=>{
   const top=26+i*107,c=color(m,i);
   body+=`<circle cx="${left+4}" cy="${top-4}" r="4" fill="${c}"/><text x="${left+17}" y="${top}" class="chart-model-label">${esc(short(m.label,Math.floor((w-55)/7)))}<title>${esc(m.label)}</title></text>`;
   [[m.wer,'WER'],[m.cer,'CER']].forEach(([v,name],j)=>{
    const y=top+15+j*26,bar=span*v/cap;
    body+=`<text x="${left}" y="${y+11}" class="axis-label">${name}</text><rect x="${left+37}" y="${y}" width="${Math.max(0,span-37)}" height="15" rx="3" fill="var(--border)" opacity=".45"/><rect x="${left+37}" y="${y}" width="${Math.max(v?1:0,(span-37)*v/cap)}" height="15" rx="3" fill="${c}" opacity="${j?.55:1}"><title>${esc(m.label)} · ${name} ${pct(v)} · ${m.reference_words} reference words</title></rect><text x="${w-10}" y="${y+12}" text-anchor="end" class="value-label">${pct(v)}</text>`;
   });
   body+=`<text x="${left+37}" y="${top+83}" class="axis-label">${m.counts.S} substitutions · ${m.counts.D} deletions · ${m.counts.I} insertions</text>`;
  });
  const bottom=height-20;
  [0,.5,1].forEach(f=>body+=`<text x="${left+37+(span-37)*f}" y="${bottom}" text-anchor="${f===0?'start':f===1?'end':'middle'}" class="axis-label">${(100*cap*f).toFixed(1)}%</text>`);
  el.innerHTML=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${height}" role="img" aria-label="Paired WER and CER bars">${body}</svg>`;
 }
 function paired(el,cases,models){
  if(!cases.length)return empty(el,'No case is currently shared successfully by this pair. Failures are not scored as zero.');
  const w=Math.max(300,el.clientWidth-28),left=28,right=90,span=w-left-right;
  const cap=Math.max(.05,...cases.flatMap(c=>[c.left.wer,c.right.wer]))*1.12;
  const height=80+cases.length*87;
  let body='<title>Case-by-case WER</title><desc>Grouped bars represent categorical test cases, not time. An amber REVIEW label is a reference warning, not an automatic exclusion.</desc>';
  models.forEach((m,i)=>{body+=`<circle cx="${left}" cy="${15+i*19}" r="4" fill="${color(m,i)}"/><text x="${left+12}" y="${19+i*19}" class="legend-label">${esc(short(m.label,Math.floor((w-55)/7)))}</text>`;});
  cases.forEach((c,i)=>{
   const top=66+i*87;
   body+=`<text x="${left}" y="${top}" class="chart-model-label">Input ${c.audio_number||'text'} · ${esc(c.source_type)} · ref ${esc(c.reference_id.slice(-6))}</text>`;
   if(c.needs_review)body+=`<text x="${w-12}" y="${top}" text-anchor="end" class="review-chart-label">REVIEW</text>`;
   [c.left,c.right].forEach((row,j)=>{
    const y=top+12+j*24,x=left+span*row.wer/cap;
    body+=`<g tabindex="0" role="button" aria-label="Inspect ${esc(row.label)}, input ${c.audio_number}, WER ${pct(row.wer)}" data-case="${esc(row.case_id)}" data-run="${esc(row.run_id)}" data-model="${esc(row.provider_key)}"><title>${esc(row.title)} · ${esc(row.label)} · ${pct(row.wer)} · run ${esc(row.run_id.slice(-6))}</title><rect x="${left}" y="${y}" width="${span}" height="14" rx="3" fill="var(--border)" opacity=".35"/><rect x="${left}" y="${y}" width="${Math.max(0,span*row.wer/cap)}" height="14" rx="3" fill="${color(models[j],j)}"/><circle cx="${x}" cy="${y+7}" r="4" fill="${color(models[j],j)}"/><text x="${w-10}" y="${y+12}" text-anchor="end" class="value-label">${pct(row.wer)}</text></g>`;
   });
  });
  el.innerHTML=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${height}" role="img" aria-label="Shared-case WER, one row per input and reference">${body}</svg>`;
 }
 // Kept for older test/export consumers; the live dashboard calls paired directly.
 function lines(el,rows,models){
  const ids=[...new Set(rows.map(r=>r.clip_id))];
  const cases=ids.map(id=>{const rs=rows.filter(r=>r.clip_id===id&&r.status==='success');return rs.length>=2?{left:rs[0],right:rs[1],reference_id:rs[0].reference_id||id,source_type:rs[0].source_type||'saved',audio_number:rs[0].audio_number}:null;}).filter(Boolean);
  paired(el,cases,models);
 }
 return {bars,paired,lines};
})();

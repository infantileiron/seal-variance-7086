import{store}from'../stores/business.js';import{panel}from'../api/mix.js';import{esc,num}from'../utils/format.js';import{table}from'../components/common/table.js';import{badge}from'../components/common/status.js';
const VERDICT={a_leads:'全程领先',b_leads:'全程落后',tie:'基本持平',flip:'随配比翻转'};
const fmix=m=>Object.entries(m).map(([k,v])=>`${esc(k)} ${num(v,3)}`).join('，');
const utc=s=>esc((s||'').slice(0,19).replace('T',' '));
function pairsBlock(pairs){
    if(!pairs||!pairs.length)return '<p class=empty>本次计算不涉及工艺对。</p>';
    return pairs.map(p=>{
        const head=`<b>${esc(p.a.code)} ↔ ${esc(p.b.code)}</b>`;
        if(p.status!=='ok')return `<div class=pair-row>${head}<span class="pill stale">不出结论</span><p class=small>可能分到份额的批次缺组：${p.missing.map(m=>`${esc(m.lot)} 缺 ${esc(m.process)} 样本组`).join('；')}。</p></div>`;
        return `<div class=pair-row>${head}<span class="pill ${p.verdict==='flip'?'flip':''}">${VERDICT[p.verdict]}</span><span class=pair-range>${num(p.range.min)} ~ ${num(p.range.max)} N</span>${table(['批次','n A/B','均值 A','均值 B','批内差 d'],p.diffs.map(d=>[esc(d.lot),`${d.n_a} / ${d.n_b}`,num(d.mean_a,2),num(d.mean_b,2),num(d.d)]))}<p class=small>达到下限的配比：${fmix(p.min_mix)}<br>达到上限的配比：${fmix(p.max_mix)}</p></div>`;
    }).join('');
}
function resultBlock(result){
    if(!result)return '';
    const lots=result.lots||[];
    return `${result.conclusion?`<p class=notice>${esc(result.conclusion)}</p>`:`<p class=notice>不出结论：${esc(result.no_conclusion_reason||'—')}</p>`}${lots.length?table(['批次','下限','上限','可分得最大份额'],lots.map(l=>[esc(l.lot),num(l.lower,3),num(l.upper,3),num(l.max_share??0,3)])):''}${result.ignored_lots&&result.ignored_lots.length?`<p class=small>未录入占比的批次未参与配比：${result.ignored_lots.map(esc).join('、')}</p>`:''}${pairsBlock(result.pairs)}`;
}
function mixPanel(aid){
    const a=store.assessments.find(x=>x.id===aid),data=store.mix[aid];
    if(!a||!data)return '';
    const editor=store.user.role!=='viewer';
    const{bounds,studies,publications,known_lots,current_fingerprint}=data;
    const slo=bounds.reduce((t,b)=>t+b.lower,0),shi=bounds.reduce((t,b)=>t+b.upper,0);
    const bad=bounds.length&&(slo>1+1e-9||shi<1-1e-9);
    const boundsTable=table(['材料批次','占比下限','占比上限','最近修订',''],bounds.map(b=>[esc(b.lot),num(b.lower,3),num(b.upper,3),`${esc(b.updated_by||'—')}<small>${utc(b.updated_at)} UTC</small>`,editor?`<button class=text-btn data-fill-bound data-lot="${esc(b.lot)}" data-lo=${b.lower} data-hi=${b.upper}>修订</button>`:'']));
    const form=editor?`<form id=mix-bound-form data-aid=${aid}><div class=mix-form><label>材料批次<input name=lot list=known-lots required maxlength=60 placeholder="如 HC-1116"></label><label>占比下限<input name=lower type=number min=0 max=1 step=0.01 required placeholder="0.20"></label><label>占比上限<input name=upper type=number min=0 max=1 step=0.01 required placeholder="0.70"></label><button class=primary>保存占比</button></div><datalist id=known-lots>${known_lots.map(l=>`<option value="${esc(l)}">`).join('')}</datalist></form>`:'';
    const queued=studies.some(s=>['queued','running'].includes(s.status));
    const studyRows=studies.map(s=>`<div class=history-row><span>#${s.id} · ${esc(s.created_by)}<small>${utc(s.created_at)} UTC${s.input_fingerprint?' · 指纹 '+esc(s.input_fingerprint.slice(0,12)):''}${s.error?' · '+esc(s.error):''}</small></span>${badge({status:s.status,approved:false})}${s.status==='completed'&&editor?`<button class=text-btn data-mix-publish="${s.id}:${aid}">发布</button>`:''}</div>`).join('');
    const latest=studies.find(s=>s.status==='completed');
    const result=latest?`<div class=mix-result><h3>最近计算结果 · 任务 #${latest.id}</h3>${resultBlock(latest.result)}${editor?`<button class=primary data-mix-publish="${latest.id}:${aid}">发布此结果</button>`:''}<p class=small>发布前会以现行样本与占比复算校验；若数据已变，发布将被拒绝并保留旧版、标注时效。</p></div>`:'<p class=empty>尚无完成的配比计算。</p>';
    const pubs=publications.map((p,i)=>{
        const drift=p.fingerprint!==current_fingerprint;
        const state=p.stale?'已标注过时':drift?'数据已有修订':'与现行一致';
        return `<div class="history-row ${i===0?'current':''}"><span>v${p.version} · ${esc(p.published_by)}<small>${utc(p.published_at)} UTC · 指纹 ${esc(p.fingerprint.slice(0,12))}</small></span><span class="pill ${p.stale||drift?'stale':''}">${state}</span><button class=text-btn data-mix-view="${p.id}:${aid}">查看</button><button class=text-btn data-mix-export="${p.id}:${aid}:${p.version}">导出</button></div>`;
    }).join('');
    const sel=publications.find(p=>p.id===store.mixView[aid]);
    const report=sel?`<div class=mix-report><h3>报告 v${sel.version}${sel.id===(publications[0]&&publications[0].id)?' · 现行版本':''}</h3>${resultBlock(sel.report)}<p class=method>${esc(sel.report.method||'')}</p><p class=small>报告指纹 SHA-256</p><p class=checksum>${esc(sel.report.fingerprint||'')}</p><button data-mix-export="${sel.id}:${aid}:${sel.version}">导出此版报告 JSON</button></div>`:'<p class=empty>尚未发布任何版本；发布后结论与报告同步切换，历史版本留档。</p>';
    return `<section class=mix-panel><div class=section-title><h2>配比敏感性 · 订单材料占比</h2><span>订单换配比后，同一工艺可能由领先变落后</span></div><div class=mix-grid><div class=mix-block><h3>各批占比上下限</h3>${bounds.length?`<p class="sum-line ${bad?'bad':''}">下限合计 ${num(slo,3)} · 上限合计 ${num(shi,3)}${bad?' · 当前无可行配比（占比无解）':' · 可行配比需合计为 1'}</p>`:''}${boundsTable}${form}<p class=small>计算排队或运行期间也可照常补录和修订占比；修订只影响之后的计算与发布校验。</p></div><div class=mix-block><h3>配比计算</h3>${editor?`<button class=primary data-mix-compute=${aid}>提交配比敏感性计算</button>`:''}${queued?'<p class=small>有任务在队列中，页面每 2 秒自动刷新。</p>':''}${studyRows||'<p class=empty>尚未提交计算。</p>'}</div></div>${result}<h3>已发布版本（留档）</h3>${pubs||'<p class=empty>尚未发布。</p>'}${report}</section>`;
}
function paint(aid){
    const box=document.querySelector('#mix-panel');if(!box)return false;
    const f=box.querySelector('#mix-bound-form');
    const draft=f?{lot:f.elements.lot.value,lower:f.elements.lower.value,upper:f.elements.upper.value}:null;
    box.innerHTML=mixPanel(aid);
    if(draft&&(draft.lot||draft.lower||draft.upper)){const nf=box.querySelector('#mix-bound-form');if(nf){nf.elements.lot.value=draft.lot;nf.elements.lower.value=draft.lower;nf.elements.upper.value=draft.upper;}}
    return true;
}
export async function loadMix(aid){
    const box=document.querySelector('#mix-panel');if(!box)return;
    try{
        store.mix[aid]=await panel(aid);
        const pubs=store.mix[aid].publications;
        if(!store.mixView[aid]||!pubs.some(p=>p.id===store.mixView[aid]))store.mixView[aid]=pubs.length?pubs[0].id:null;
        paint(aid);
    }catch(e){box.innerHTML=`<p class=notice>${esc(e.message)}</p>`;}
}
export function renderMix(aid){paint(aid);}

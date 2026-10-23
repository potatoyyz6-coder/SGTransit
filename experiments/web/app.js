'use strict';
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon = (name) => `<i data-lucide="${name}" aria-hidden="true"></i>`;
const icons = () => lucide.createIcons();
const number = (v) => Number(v).toFixed(1);
const clock = (v) => new Date(v).toLocaleTimeString('zh-CN',{timeZone:'Asia/Singapore',hour:'2-digit',minute:'2-digit',hour12:false});
const dateTime = (v) => new Date(v).toLocaleString('zh-CN',{timeZone:'Asia/Singapore',hour12:false});
const service = (v) => v.split('-D')[0];
const colors = {'173':0,'183':2,'188':1,'41':3,'106':4,'96':5,'151':0,'61':1,'95':2,'970':4,'52':3,'184':5};
const badge = (v) => `<span class="bus-badge c${colors[service(v)]??[...service(v)].reduce((n,c)=>n+c.charCodeAt(0),0)%6}">${esc(service(v))}</span>`;
const services = (values) => `<div class="services">${values.map(badge).join(icon('chevron-right'))}</div>`;
const fallback = {missing:'该站未取得预测',stale:'快照已过时',error:'该站请求失败',service_missing:'该服务缺少预测',beyond_forecast_horizon:'超出快照预测范围',no_future_matching_prediction:'没有后续匹配预测',unusable_or_pattern_mismatch:'方向或预测不匹配',unverified_pattern_binding:'方向信息不足'};
let config, plan, selected, busy = false;

async function api(path, body) {
  const response = await fetch(path, body ? {method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':config.csrf},body:JSON.stringify(body)} : {});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || '请求失败');
  return value;
}
function error(message) { $('error').textContent=message; $('error').hidden=!message; }
function setBusy(value, message='') {
  busy=value;
  document.querySelectorAll('button,select,input').forEach(e=>e.disabled=value);
  $('workspace').setAttribute('aria-busy',String(value));
  $('status').hidden=!message;
  $('status').textContent=message;
  if (!value) syncMode();
}
function currentCase() { return config.cases.find(c=>c.id===$('case').value); }
function syncMode() {
  if (!config) return;
  const saved=$('mode').querySelector('[value="saved"]');
  saved.disabled=$('case').value!=='school'||!config.saved_available;
  if (saved.disabled&&$('mode').value==='saved') $('mode').value='model';
  $('mode').querySelector('[value="live"]').disabled=!config.key_present;
  $('submit').querySelector('span').textContent={model:'计算参考',live:'现在出发',saved:'查看快照'}[$('mode').value];
  $('onward-live').disabled=!config.key_present||plan?.mode==='saved';
  const c=currentCase();
  $('scope').textContent=`${c.origin_name} (${c.origin}) → ${c.destination_name} (${c.destination}) · ${c.stop_count} 个站点的局部路网`;
}
async function consent(caseId=$('case').value) {
  const c=config.cases.find(c=>c.id===caseId);
  $('consent-text').textContent=`本次最多请求 ${c.stop_count} 个站点，每站一次。两轮采集至少间隔 60 秒。`;
  $('consent').returnValue='cancel';
  $('consent').showModal();
  return new Promise(resolve=>$('consent').addEventListener('close',()=>resolve($('consent').returnValue==='confirm'),{once:true}));
}
async function query(event) {
  event?.preventDefault();
  if (busy) return;
  error('');
  const mode=$('mode').value;
  if (mode==='live'&&!await consent()) return;
  setBusy(true,mode==='live'?'正在获取本轮 ETA 并计算路线，请稍候…':'正在计算候选方案…');
  try {
    plan=await api('/api/plan',{case:$('case').value,mode,buffer:Number($('buffer').value),consent:mode==='live'});
    selected=plan.families[0]?.row;
    renderPlan();
    $('onward-results').replaceChildren();
    $('onward-status').textContent='';
    setBusy(false);
    if (plan.info.warning) error(plan.info.warning);
  } catch (e) { setBusy(false); error(e.message); }
}
function renderPlan() {
  $('workspace').hidden=false;
  const c=config.cases.find(c=>c.id===plan.case);
  $('journey-title').textContent=`${c.origin_name} → ${c.destination_name}`;
  const source={model:'纯模型估算',live:'本轮 LTA 预测 + 模型',saved:'历史快照 + 模型'}[plan.mode];
  $('evidence').textContent=`${source} · 参考出发 ${dateTime(plan.decision_at)} SGT · 本次 ${plan.info.requests||0} 次 API 请求${plan.search.complete?'':' · 有界搜索，可能遗漏备选'}`;
  $('count').textContent=`${plan.families.length} 组方案 / ${plan.eligible_count} 个站点变体`;
  renderCards();
  renderDetail();
}
function orderedFamilies() {
  const rows=[...plan.families];
  const metric=r=>$('sort').value==='wait'?r.wait_minutes+r.buffer_minutes:$('sort').value==='transfers'?r.transfers:r.estimated_total_minutes;
  return rows.sort((a,b)=>metric(a.row)-metric(b.row)||a.row.estimated_total_minutes-b.row.estimated_total_minutes);
}
function renderCards() {
  $('route-list').innerHTML=orderedFamilies().map((f,i)=>{
    const r=f.row;
    return `<button type="button" class="route-card ${selected&&f.variants.some(v=>v.id===selected.id)?'selected':''}" data-route="${esc(r.id)}" aria-pressed="${Boolean(selected&&f.variants.some(v=>v.id===selected.id))}"><div class="route-top"><span class="duration">${number(r.estimated_total_minutes)}<small>分钟</small></span><span class="route-tag">${i===0?{time:'预计时间较短',transfers:'换乘较少',wait:'站外等待较少'}[$('sort').value]:'约 '+clock(r.estimated_arrival_at)+' 抵达'}</span></div>${services(r.services)}<div class="route-meta"><span>${r.transfers} 次换乘</span><span>等候含缓冲 ${number(r.wait_minutes+r.buffer_minutes)} 分钟</span></div><div class="route-transfer">${r.legs.slice(0,-1).map(l=>esc(l.alight_name)).join(' · ')||'直达'}</div></button>`;
  }).join('') || `<div class="empty">当前模型与历史运营窗口下，没有默认参考方案。<br>不代表实际没有公交。<p>${esc(JSON.stringify(plan.exclusions))}</p></div>`;
  icons();
}
function sourceTag(l) {
  if(l.timing_source==='same_vehicle_continuation') return '<span class="evidence-tag">同车继续</span>';
  if(l.timing_source==='snapshot_eta') return `<span class="evidence-tag">ETA 预测 · ${l.monitored===true?'监测标记':l.monitored===false?'非监测标记':'标记未知'}</span>`;
  return `<span class="evidence-tag model">模型补估</span> ${esc(fallback[l.fallback_reason]||'固定平均等待')}`;
}
function timeline(r) {
  return `<div class="timeline">${r.legs.map((l,i)=>`<div class="leg"><div class="leg-clock">${clock(l.board_at)}</div><div class="rail"></div><div class="leg-body"><div class="stop-name">${esc(l.board_name)}<span class="stop-code">${esc(l.board_stop)}</span></div><div class="ride-line">${badge(l.service_id)}<span>乘坐约 ${number(l.ride_minutes)} 分钟</span></div><div class="leg-notes">${sourceTag(l)}<br>等待 ${number(l.wait_minutes)} 分钟${l.transfer_minutes?' · 换乘缓冲 '+number(l.transfer_minutes)+' 分钟':''} · 上车延误假设 ${number(l.mean_boarding_delay_minutes)} 分钟</div><div class="alight">${clock(l.alight_at)} 抵达 <strong>${esc(l.alight_name)}</strong><span class="stop-code">${esc(l.alight_stop)}</span></div>${i<r.legs.length-1?`<p class="transfer-note">${icon('repeat-2')}同站换乘 ${badge(r.legs[i+1].service_id)}</p>`:''}</div></div>`).join('')}</div>`;
}
function renderDetail() {
  if (!selected) { $('detail').innerHTML='<div class="empty">暂无路线详情</div>'; $('onward-section').hidden=true; return; }
  const r=selected, family=plan.families.find(f=>f.variants.some(v=>v.id===r.id));
  $('detail').innerHTML=`
    <div class="detail-top"><div><p class="eyebrow">所选方案</p>
      <h2>约 ${number(r.estimated_total_minutes)} 分钟抵达</h2>
      <p class="muted">${clock(plan.decision_at)} → ${clock(r.estimated_arrival_at)} · ${r.transfers} 次换乘</p>
    </div><button type="button" id="back-routes" class="icon-button" title="返回候选方案" aria-label="返回候选方案">${icon('arrow-up')}</button></div>
    <div class="metrics">
      <div class="metric">乘车<strong>${number(r.ride_minutes)} <small>分</small></strong></div>
      <div class="metric">等待<strong>${number(r.wait_minutes)} <small>分</small></strong></div>
      <div class="metric">缓冲<strong>${number(r.buffer_minutes)} <small>分</small></strong></div>
      <div class="metric">延误假设<strong>${number(r.delay_minutes)} <small>分</small></strong></div>
    </div>
    ${family?`<label class="variant-label">换乘站组合 · ${family.variants.length} 个
      <select id="variant" aria-label="换乘站组合">${family.variants.map(v=>`<option value="${esc(v.id)}" ${v.id===r.id?'selected':''}>${esc(v.transfers.join(' → ')||'直达')} · ${number(v.total)} 分钟</option>`).join('')}</select>
    </label>`:''}
    ${timeline(r)}
    ${plan.case==='school'?`<details class="network"><summary>服务路段与共同站点</summary><a href="/network.png" target="_blank" rel="noopener"><img src="/network.png" alt="Blk 18 到 CDE 的九条有向服务路段与共同站点结构图" loading="lazy"></a></details>`:''}`;
  $('point').innerHTML=r.points.map(p=>`<option value="${p.index}">${esc(p.name)} (${p.stop}) · ${esc(service(p.service))}</option>`).join('');
  $('onward-section').hidden=!r.points.length;
  $('onward-results').replaceChildren();
  $('onward-status').textContent=plan.mode==='saved'?'历史推演；不使用当前 ETA。':'';
  icons();
}
async function choose(id) {
  if(busy) return;
  setBusy(true);
  error('');
  try {
    selected=await api('/api/detail',{plan_id:plan.plan_id,route_id:id});
    renderCards();renderDetail();
    if(window.innerWidth<=650) $('detail').scrollIntoView({block:'start'});
  } catch(e) { error(e.message); }
  setBusy(false);
}
async function onward(live=false) {
  if (busy||!selected) return;
  error('');
  if(live&&!await consent(plan.case)) return;
  setBusy(true,live?'正在获取一轮 ETA 并比较后续走法…':'正在比较继续乘坐与换车…');
  try {
    const r=await api('/api/onward',{plan_id:plan.plan_id,route_id:selected.id,point:Number($('point').value),onboard:document.querySelector('[name="onboard"]:checked').value==='yes',live,consent:live});
    $('onward-status').textContent=`${r.name} · ${dateTime(r.at)} SGT · ${r.eligible_count} 个后续变体 · ${r.info.source==='saved_projection'?'历史推演':live?'本轮预测 + 模型':'纯模型估算'} · 本次 ${r.info.requests} 次 API 请求`;
    $('onward-results').innerHTML=r.routes.map(row=>`<article class="onward-row"><header><strong>${row.legs[0]?.timing_source==='same_vehicle_continuation'?'继续坐 '+esc(service(row.services[0])):row.legs.length?'换乘 '+esc(service(row.services[0])):'已到目的地'}</strong><span>剩余约 ${number(row.estimated_total_minutes)} 分钟</span></header>${services(row.services)}<p>新增 ${row.transfers} 次换乘 · 等候含缓冲 ${number(row.wait_minutes+row.buffer_minutes)} 分钟</p><details><summary>后续站点与时间来源</summary>${timeline(row)}</details>${row.can_adopt&&row.legs.length?`<button type="button" class="secondary adopt" data-adopt="${esc(row.id)}">${icon('check')}采用此后续路线</button>`:''}</article>`).join('')||'<p class="empty">没有符合当前历史和模型约束的后续方案。</p>';
    if(r.info.warning) error(r.info.warning);
    icons();
  } catch(e) { error(e.message); }
  setBusy(false);
}
$('query-form').addEventListener('submit',query);
$('case').addEventListener('change',syncMode);
$('mode').addEventListener('change',syncMode);
$('sort').addEventListener('change',()=>{if(plan)renderCards();});
$('route-list').addEventListener('click',e=>{const card=e.target.closest('[data-route]');if(card)choose(card.dataset.route);});
$('detail').addEventListener('change',e=>{if(e.target.id==='variant')choose(e.target.value);});
$('detail').addEventListener('click',e=>{if(e.target.closest('#back-routes')) $('route-list').scrollIntoView({block:'start'});});
$('onward-form').addEventListener('submit',e=>{e.preventDefault();onward(false);});
$('onward-live').addEventListener('click',()=>onward(true));
$('onward-results').addEventListener('click',async e=>{
  const button=e.target.closest('[data-adopt]');
  if(!button||busy)return;
  await choose(button.dataset.adopt);
  $('onward-status').textContent='后续路线已更新；上方仍展示原查询时刻的全程参考。';
});
$('export').addEventListener('click',()=>{
  if(!plan)return;
  const {plan_id,...summary}=plan;
  const url=URL.createObjectURL(new Blob([JSON.stringify(summary,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download=`sg-transit-${plan.case}-reference.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
(async()=>{
  icons();
  try {
    config=await api('/api/config');
    $('case').innerHTML=config.cases.map(c=>`<option value="${esc(c.id)}">${esc(c.label)}</option>`).join('');
    $('key-state').textContent=config.key_present?'LTA 密钥已在后端配置':'未配置 LTA 密钥 · 离线可用';
    syncMode();await query();
  }catch(e){error(e.message);$('status').hidden=true;}
})();

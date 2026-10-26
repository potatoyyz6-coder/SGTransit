'use strict';
let combinationRequest = {}, combinationView;
const actionLabel = {board:'上车',continue:'同车继续 · 不新增等待或换乘',transfer:'换乘 · 等待与缓冲见原路线',path_dependent:'到达时乘车状态不同'};

function switchView(combined) {
  $('combination-panel').hidden=!combined;
  $('individual-panel').hidden=combined;
  $('results-grid').classList.toggle('combination-mode',combined);
  $('tab-combinations').setAttribute('aria-selected',String(combined));
  $('tab-routes').setAttribute('aria-selected',String(!combined));
}
async function resetCombinations() {
  combinationRequest={plan_id:plan.plan_id,selection:[]};
  if(selected) Object.assign(combinationRequest,{origin:selected.origin,destination:selected.destination});
  switchView(true);
  combinationView=null;
  $('combination-graph').replaceChildren();
  $('combination-routes').replaceChildren();
  await fetchCombinations();
}
async function fetchCombinations() {
  combinationView=await api('/api/route-combinations',combinationRequest);
  if(combinationView.origin) Object.assign(combinationRequest,{origin:combinationView.origin,destination:combinationView.destination});
  renderCombinations();
}
async function updateCombinations(changes, clearDetail=false) {
  if(busy) return;
  setBusy(true);error('');
  const previous={...combinationRequest};
  combinationRequest={...combinationRequest,...changes};
  if('selection' in changes || 'choice_page' in changes || 'graph_page' in changes) combinationRequest.inspect=null;
  try {
    await fetchCombinations();
    if(clearDetail) {selected=null;renderCards();renderDetail();}
  } catch(e) {combinationRequest=previous;error(e.message);}
  setBusy(false);
}
function pager(kind, page, pages, label) {
  if(pages<=1) return '';
  return `<nav class="combination-pager" aria-label="${esc(label)}"><button type="button" class="icon-button" data-page-kind="${kind}" data-page="${Math.max(0,page-1)}" ${page===0?'hidden':''} title="上一页" aria-label="${esc(label)}上一页">${icon('chevron-left')}</button><span>${esc(label)} ${page+1} / ${pages}</span><button type="button" class="icon-button" data-page-kind="${kind}" data-page="${page+1}" ${page+1===pages?'hidden':''} title="下一页" aria-label="${esc(label)}下一页">${icon('chevron-right')}</button></nav>`;
}
function renderCombinations() {
  const v=combinationView;
  $('combination-endpoints').innerHTML=v.groups.map((g,i)=>`<option value="${i}" ${g.origin===v.origin&&g.destination===v.destination?'selected':''}>${esc(g.origin_name)} (${esc(g.origin)}) → ${esc(g.destination_name)} (${esc(g.destination)}) · ${g.count}</option>`).join('');
  $('combination-back').hidden=!v.selection.length;
  $('combination-count').textContent=`${v.compatible_count} 条兼容原始路线 · ${v.selection.length} 处分支已选`;
  let lastKind='';
  $('combination-graph').innerHTML=v.nodes.map(n=>{
    const section=n.kind!==lastKind?`<h3 class="graph-section">${{prefix:'共同 / 已选路段',choice:`${esc(v.frontier.name)} · 可选公交`,rejoin:'后续共同路段'}[n.kind]}</h3>`:'';
    lastKind=n.kind;
    const states=n.entry_states;
    const expansion=v.expanded?.segment===n.id?v.expanded:null;
    return `${section}<div class="combination-node ${n.kind}" data-node="${n.id}">
      <div class="combination-rail">${icon(n.kind==='rejoin'?'git-merge':n.kind==='choice'?'git-branch':'move-down')}</div>
      <div class="combination-body"><div class="combination-service">${n.options?n.options.map(o=>`<button type="button" class="branch-select" data-branch="${o.branch}" title="${esc(o.service)} · ${esc(actionLabel[o.action])}" aria-label="选择 ${esc(o.service)} 分支">${badge(o.service)}<span>${o.count} 条 · ${o.action==='continue'?'继续坐':o.action==='transfer'?'换乘':'上车'}</span>${icon('arrow-right')}</button>`).join(''):n.alternatives?n.alternatives.map(o=>`<button type="button" class="service-inspect" data-inspect-service="${esc(o.service)}" data-inspect-segment="${n.id}" title="查看此路段 ${esc(o.service)} 的原始路线" aria-label="查看 ${esc(o.service)} 原始路线">${badge(o.service)}</button>`).join(''):`${badge(n.service)}<span class="direction">${esc(n.service)}</span>`}</div>
        <div class="combination-stops"><strong>${esc(n.start.name)}</strong><span> → ${esc(n.end.name)}</span></div>
        <p class="muted">${n.options?'兼容服务 · 保留方向与原始路线关联':esc(actionLabel[n.action])}</p>
        ${states?`<div class="entry-states">${states.continue_count?`<span>${icon('bus-front')}同车继续 ${states.continue_count} 条 · 不新增等待</span>`:''}${states.transfer_count?`<span>${icon('repeat-2')}换乘上车 ${states.transfer_count} 条 · 另计等待</span>`:''}${states.board_count?`<span>首次上车 ${states.board_count} 条</span>`:''}</div>`:''}
        ${n.alternatives?`<details class="rejoin-states"><summary>各服务到达状态</summary>${n.alternatives.map(o=>`<p>${esc(o.service)} · 同车继续 ${o.continue_count} 条 · 换乘 ${o.transfer_count} 条${o.board_count?' · 首次上车 '+o.board_count+' 条':''}</p>`).join('')}</details>`:''}
        <button type="button" class="stop-expand" data-expand="${n.id}" aria-expanded="${Boolean(expansion)}" title="${expansion?'折叠':'展开'}原始站序">${icon(expansion?'minus':'plus')}${n.stop_count} 个站点</button>
        ${expansion?`<ol class="expanded-stops" start="${expansion.page*24+1}">${expansion.stops.map(s=>`<li>${esc(s.name)} <small>${esc(s.id)}</small></li>`).join('')}</ol>${pager('stop_page',expansion.page,Math.ceil(expansion.total/24),'站序')}`:''}
      </div></div>`;
  }).join('')||(v.terminal&&v.compatible_count?'<p class="empty">起终点为同一站，无需上车。</p>':'<p class="empty">当前默认参考池没有可组合路线。</p>');
  $('combination-pages').innerHTML=pager('choice_page',v.choice_page||0,Math.ceil(v.choice_count/8),'分支')+pager('graph_page',v.graph_page||0,v.graph_pages||1,'图节点')+
    ((v.hidden_choices||v.hidden_nodes)?`<p class="muted">未显示：${v.hidden_choices} 个分支选项，${v.hidden_nodes} 个图节点；原始候选均保留。</p>`:'');
  const wasOpen=$('combination-originals')?.open;
  $('combination-routes').innerHTML=`<details id="combination-originals" ${wasOpen||v.terminal||v.inspected?'open':''}><summary>完整原始路线 · ${v.reference_count} 条${v.inspected?' · 后段 '+esc(v.inspected.service):''}</summary>${v.inspected?`<button type="button" class="secondary" id="clear-inspection">${icon('x')}清除服务筛选</button>`:''}${v.routes.map(r=>`<article class="combination-route">
    <header><strong>${esc(r.id)} · 公交段 ${number(r.estimated_total_minutes)} 分钟</strong><button type="button" class="secondary" data-combination-route="${esc(r.id)}">${icon('check')}采用此路线</button></header>
    ${services(r.services)}<p>${r.transfers} 次换乘 · ${r.legs.slice(0,-1).map(l=>esc(l.alight_name)).join(' → ')||'直达 / 同站'}</p>
    <p class="muted">乘车 ${number(r.ride_minutes)} · 等待 ${number(r.wait_minutes)} · 缓冲 ${number(r.buffer_minutes)} · 延误假设 ${number(r.delay_minutes)} 分钟</p>
    <p class="muted">${r.access_minutes===undefined?'站到站参考 · 不含端点步行':`起端接驳 ${r.access_minutes===null?'未知':number(r.access_minutes)+' 分钟'} · 终端接驳 ${r.egress_minutes===null?'未知':number(r.egress_minutes)+' 分钟'}`}${r.operating_status==='unknown'?' · 运营窗口未知':''} · ${r.snapshot_boardings?'含快照预测与模型':'模型估时'}</p>
  </article>`).join('')}${pager('route_page',v.route_page||0,Math.ceil(v.reference_count/8),'原始路线')}<p class="muted">本页 ${v.routes.length} 条；其余 ${v.hidden_routes} 条保留在其他页。</p></details>`;
  $('combination-boundaries').textContent=`${v.excluded_count} 条候选未进入默认参考池。排除原因：${JSON.stringify(v.exclusions)}。${v.search.complete?'声明约束内搜索完成。':'有界搜索，可能遗漏其他路线。'}共同路段不代表可任意拼接；未选择的组合没有统一总时间。模型估时不是实际到站或赶车保证。`;
  icons();
}
$('tab-combinations').addEventListener('click',()=>switchView(true));
$('tab-routes').addEventListener('click',()=>switchView(false));
$('combination-endpoints').addEventListener('change',()=>{
  const g=combinationView.groups[Number($('combination-endpoints').value)];
  updateCombinations({origin:g.origin,destination:g.destination,selection:[],choice_page:0,route_page:0,graph_page:0,expand:null,stop_page:0},true);
});
$('combination-back').addEventListener('click',()=>updateCombinations({selection:combinationRequest.selection.slice(0,-1),choice_page:0,route_page:0,graph_page:0,expand:null,stop_page:0},true));
$('combination-panel').addEventListener('click',e=>{
  const button=e.target.closest('button');
  if(!button) return;
  if(button.dataset.branch) updateCombinations({selection:[...combinationRequest.selection,Number(button.dataset.branch)],choice_page:0,route_page:0,graph_page:0,expand:null,stop_page:0},true);
  else if(button.dataset.expand!==undefined) updateCombinations({expand:combinationRequest.expand===Number(button.dataset.expand)?null:Number(button.dataset.expand),stop_page:0});
  else if(button.dataset.pageKind) updateCombinations({[button.dataset.pageKind]:Number(button.dataset.page),...(button.dataset.pageKind==='choice_page'||button.dataset.pageKind==='graph_page'?{expand:null,stop_page:0}:{})});
  else if(button.dataset.combinationRoute) choose(button.dataset.combinationRoute);
  else if(button.dataset.inspectService) updateCombinations({inspect:{segment:Number(button.dataset.inspectSegment),service:button.dataset.inspectService},route_page:0});
  else if(button.id==='clear-inspection') updateCombinations({inspect:null,route_page:0});
});

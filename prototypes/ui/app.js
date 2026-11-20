'use strict';
const $ = id => document.getElementById(id);
const views = ['准备任务','运行监控','人工协助','结果与回放','模型与配置'];
const terminal = new Set(['完成','失败','已终止']);
let page = 1, role = 'home', connected = true, adapter = true, stop = '已确认静止';
let requestSerial=0, requestId='', requestError='';
let pending = '', task = null, nextId = 1, savedOrigin = '', goal = false;
let prepared = [false,false], scene = '有效', checked = false, model = 'baseline-v0.1';
let cfg = {version:1, time:300, cap:.25, attempts:3, speed:.005, prefix:1, billLimit:900, scene:'TOPS-01'};
let candidate = 0, selected = null, frame = 0, playing = null, notice = '';
let records = [], commands = new Map();
const active = () => task && !terminal.has(task.state);
const rest = () => adapter && stop === '已确认静止';
const idle = () => !active() && !pending && rest();
const home = () => role === 'home' && connected;
const maintain = () => role === 'maint' && connected;
const canRun = () => active() && ['折叠中','恢复中'].includes(task.state) && !pending && !goal && stop === '执行中';
const money = n => '$' + n.toFixed(3);
function say(text){notice = text}
const reasonMessages = {
  "UNKNOWN": "观测不足，等待停车后检查衣物。",
  "STALE_OBSERVATION": "观测过期，等待新观测。",
  "OLD_GENERATION": "控制代号已更新，旧回复已丢弃。",
  "DECISION_TIMEOUT": "决策超时，取消本次计算。",
  "INVALID_SCHEMA": "字段不兼容，拒绝候选。",
  "NONFINITE": "候选含非有限数值，拒绝候选。",
  "OUT_OF_BOUNDS": "候选动作超出允许范围，拒绝候选。",
  "TOO_MANY_CANDIDATES": "候选超过八个，拒绝整份回复。",
  "NO_SUPPORTED_CANDIDATE": "没有合格候选，停车并求助。",
  "SCORE_UNCALIBRATED": "缺少有效校准，阻止派发并求助。",
  "LOW_SCORE": "评分不足，阻止派发并求助。",
  "BUDGET_EXHAUSTED": "任务预算耗尽，停止执行并保留实际消耗。",
  "STOP_PENDING": "等待设备静止证明，禁止派发。",
  "AUTHORITY_REVOKED": "当前权限已撤回，等待来源校验。",
  "LOG_WRITE_FAILED": "记录写入失败，停止派发并核实。",
  "EXECUTION_UNCERTAIN": "执行结果待核，停止派发并保留已接受次数。",
  "IDEMPOTENCY_CONFLICT": "同一请求标识对应不同内容，拒绝重用。"
};
function reasonGuide(){
  const rows = Object.entries(reasonMessages).map(([code, meaning]) =>
    '<p><code>'+code+'</code>　'+meaning+'</p>');
  return '<details><summary>接口原因码及处理说明</summary>'+rows.join('')+'</details>';
}
function log(text, reasonCode = null, reply = null){
  const message = reasonCode ? text+' ['+reasonCode+']' : text;
  say(message);
  if(task) task.frames.push({
    sequence_no:task.frames.length + 1, reason_code:reasonCode, control_generation:task.gen,
    decision_id:reply?.id ?? null, reply_generation:reply?.generation ?? null,
    event:message, state:task.state, stop, activeSeconds:task.time,
    billedSeconds:task.wall, attempts:task.attempts, generation:task.gen
  });
}
function exportRecord(record){
  return {
    ...record, schema_version:'folding-ui-demo/1', source:'synthetic',
    online_authorized:false, evaluation_eligible:false,
    task_id:record.id, request_id:record.requestId,
    decision_id:null, profile_version:null, policy_version:null,
    capture_wall_monotonic_s:null, sim_time_s:null
  };
}
let nextDecision = 1;
let lastReply = null;
const processedDecisions = new Set();
function clearDecisionCache(){
  processedDecisions.clear();
  lastReply = null;
}
function advanceGeneration(){
  task.gen++;
  task.bad = 0;
  clearDecisionCache();
}
function halt(){if(task)advanceGeneration(); stop = adapter ? '已接受停止请求' : '静止未确认'}
function help(reason, reasonCode = null){
  task.help = true;task.reason = reason; task.state = '等待协助';goal = false;pending = '';
  if(!rest()) halt();
  page = 3;log(reason + '。确认静止后请接管。', reasonCode);
}
function finish(state,reason,requestStop=true,reasonCode=null){
  if(!active())return;
  pending = '';goal = false;task.state = state;task.reason = reason;
  if(requestStop)halt();
  task.end = {time:task.time,wall:task.wall,attempts:task.attempts};
  records.unshift(task);selected = task;frame = 0;page = 4;log(reason, reasonCode);
}
function proof(){
  stop = '已确认静止';log('测试桩已返回本代静止证据：速度达标、队列为空。');
  if(pending === '归还停车')pending = '归还校验';
  if(goal && active())finish('完成','已满足在线目标并确认停止。',false);
}
function validate(pass){
  const origin = pending; pending = '';
  if(origin === '启动校验'){
    if(!pass || !ready()){checked=false;requestError='相机观测超过 1 秒，请重新取景。';scene='相机观测已过期';say(requestId+' 校验失败：'+requestError);return}
    clearDecisionCache();
    task = {id:'F-'+String(nextId++).padStart(3,'0'),requestId,seed:100+requestSerial,goalId:'TOPS-FOLD-01',state:'折叠中',gen:1,cfg:{...cfg},model,time:0,wall:0,attempts:0,bad:0,adjustments:0,help:false,manual:false,quality:'待审核',qualityReason:'等待离线证据',reason:'',frames:[],linked:false};
    stop='执行中';page=2;checked=false;prepared=[false,false];log('任务已创建，已冻结模型及配置。');return
  }
  if(pass && rest()){
    task.state=origin === '继续校验' ? savedOrigin : '折叠中'; stop='执行中';advanceGeneration();page=2;
    log(task.state === '恢复中' ? '校验通过。下一次纠正仍需接受新候选。' : '校验通过，已恢复自动控制。');
  }else{
    task.state=origin === '继续校验' ? '已暂停' : '等待协助';page=origin === '继续校验'?2:3;
    task.reason='衣物超出工作区';log(origin === '继续校验'?'继续校验失败，保持暂停。':'归还校验失败。请重新接管，把衣物移回桌内。');
  }
}
function ready(){return prepared.every(Boolean) && scene==='有效' && rest() && !active()}
function receiveReply(reply){
  if(reply.taskId !== task.id || reply.generation !== task.gen){
    log(reasonMessages.OLD_GENERATION, 'OLD_GENERATION', reply);
    return;
  }
  if(processedDecisions.has(reply.id)){
    log('重复回复，沿用首次处置。', reply.code, reply);
    return;
  }
  processedDecisions.add(reply.id);
  lastReply = reply;
  if(!reply.code){
    task.bad = 0;
    log('收到有效决策，连续无效次数清零。', null, reply);
    return;
  }
  task.bad++;
  log(reasonMessages[reply.code]+' 连续 '+task.bad+'/3 次。', reply.code, reply);
  if(task.bad >= 3) help('本代连续三次独立决策不可用');
}
function demoReply(code, generation = task.gen){
  receiveReply({id:'demo-D'+nextDecision++, taskId:task.id, generation, code});
}
function allocate(sim,wall){
  task.time+=sim;task.wall+=wall;
  if(active() && (task.time>=task.cfg.time || task.wall/3600>=task.cfg.cap || task.wall>=task.cfg.billLimit)){
    finish('失败',task.time>=task.cfg.time?'活动时间耗尽':task.wall/3600>=task.cfg.cap?'计费额度耗尽':'资源分配时限耗尽', true, 'BUDGET_EXHAUSTED');return
  }
  log('已记录活动 '+sim+' 秒、资源占用 '+wall+' 秒。');
}
function pause(){
  savedOrigin=task.state;task.state='已暂停';pending='';goal=false;halt();log('已暂停派发，正在等待设备停车。','STOP_PENDING');
}
function disconnectUI(){
  connected=false;
  if(pending==='启动校验'){pending='';checked=false}
  else if(active()){
    if(pending==='继续校验'){pending='';task.state='已暂停'}
    else if(task.state==='人工控制'||pending.startsWith('归还')){pending='';task.state='等待协助';halt()}
    else if(['折叠中','恢复中'].includes(task.state))pause();
  }
  say('控制会话失联，操作已锁定。重新绑定后仍需显式继续或接管。');
}
function offline(){
  adapter=false;pending='';goal=false;checked=false;stop='静止未确认';
  if(active())finish('失败','设备适配器失联');else {if(task)advanceGeneration();log('设备适配器失联，保留已有结果。')}
  stop='静止未确认';say('设备失联。重连后仍需新的静止证据。');
}
function stopPlay(){clearInterval(playing);playing=null}
function go(n){page=n;stopPlay();notice='';render();if(!$('demo-dialog').open)$('title').focus({preventScroll:true})}
function button(key,label,enabled,act,cls=''){
  commands.set(key,{enabled:!!enabled,act});
  return '<button type="button" id="'+key+'" class="'+cls+'" '+(enabled?'':'disabled')+'>'+label+'</button>';
}
function acts(...items){return '<div class="actions">'+items.join('')+'</div>'}
function rows(items){return items.map(([a,b])=>'<div class="row"><span>'+a+'</span><b>'+b+'</b></div>').join('')}
function card(title,body){return '<article class="card"><h2>'+title+'</h2>'+body+'</article>'}
function note(s){return '<p class="note">'+s+'</p>'}
function grid(a,b){return '<div class="grid">'+a+b+'</div>'}
function status(){
  return rows([['任务状态',pending || task?.state || '待准备'],['设备状态',stop],['恢复次数',task?task.attempts+' / '+task.cfg.attempts:'—'],['模拟活动时间',task?task.time+' / '+task.cfg.time+' 秒':'—'],['模拟 GPU 费用',task?money(task.wall/3600)+' / '+money(task.cfg.cap):'—']]);
}
function eventPicker(record){
  const options = record.frames.map((entry, index) => {
    const selected = index === frame ? ' selected' : '';
    return '<option value="'+index+'"'+selected+'>'+entry.sequence_no+' · '+entry.event+'</option>';
  });
  return '<label class="event-picker">跳到事件<select id="event-select">'+options.join('')+'</select></label>';
}
function terminate(){
 return button('terminate','终止任务',home()&&active(),()=>{if(confirm('终止本次任务并请求停车？已终止的任务无法继续。'))finish('已终止','用户终止任务。')},'danger')
}
function prep(){
 const confirm=['已放好一件展开、无结的上衣','已清空桌面，并了解需要协助时应先接管'].map((v,i)=>'<label><input type="checkbox" id="prep-'+i+'" data-prep="'+i+'" '+(prepared[i]?'checked ':'')+(home()&&!pending&&!active()?'':'disabled')+'><span>'+v+'</span></label>').join('');
 const hint=active()?'已有任务进行中，请进入运行监控。':pending?'正在检查衣物与设备，请稍等。取消后不会创建任务。':!rest()?'设备还未确认静止，暂时不能启动。':scene!=='有效'?'暂时无法启动：'+scene+'。请修正后重新检查。':!prepared.every(Boolean)?'完成这两项确认后，就可以检查设备是否就绪。':checked?'准备就绪，可以开始折叠。':'请点击“检查就绪”，确认可以安全启动。';
 return grid(card('开始前的准备','<p class="lead">将一件展开的上衣放在桌面上，袖子自然摊开。</p><div class="checks">'+confirm+'</div>'+note(hint)+acts(button('check','检查就绪',home()&&!active()&&!pending,()=>{checked=ready();say(checked?'准备就绪，可以开始折叠。':hint)}),button('start','开始折叠',home()&&ready()&&checked&&!pending,()=>{requestId='R-'+String(++requestSerial).padStart(3,'0');pending='启动校验';say('正在检查衣物和设备，尚未创建任务。')},'primary'),button('cancel','取消启动',home()&&pending==='启动校验',()=>{pending='';checked=false;say('已取消，没有创建任务。')}))),card('本次折叠','<p class="garment-name">一件上衣</p><p>当前支持固定桌面上的单件上衣。请勿放入其他物品，也不要同时叠放多件衣物。</p>'+rows([['设备状态',stop],['目标','完成预设上衣折叠']])+'<p class="quiet">遇到异常时会先尝试恢复，需要你帮忙时会明确提示。</p>'));
}
function monitor(){
 if(!task)return card('还没有进行中的任务','<p>准备好衣物后，就可以开始第一次折叠。</p>'+acts(button('to-prepare','准备一件衣物',home(),()=>{page=1},'primary')));
 const hint=task.state==='已暂停'?(rest()?'设备已确认静止。你可以继续折叠，也可以请求协助；接管之前不要调整衣物。':'设备还在停车。请勿触碰衣物，确认静止后才能继续或请求协助。'):'设备工作时，请让双手和其他物品远离桌面。';
 return grid(card('当前任务',rows([['折叠状态',pending||task.state],['设备状态',stop],['自动恢复次数',task.attempts+' / '+task.cfg.attempts]])+note(hint)+acts(button('pause','暂停折叠',home()&&active()&&['折叠中','恢复中'].includes(task.state)&&!pending,pause,'primary'),button('resume','继续折叠',home()&&task.state==='已暂停'&&rest()&&!pending,()=>{pending='继续校验';log('正在检查是否可以继续折叠。')},'primary'),button('ask','我需要调整衣物',home()&&task.state==='已暂停'&&rest()&&!pending,()=>help('用户请求检查衣物')),terminate())),card('本次使用情况',rows([['任务编号',task.id],['活动时间（模拟）',task.time+' 秒 / '+task.cfg.time+' 秒'],['费用（模拟）',money(task.wall/3600)+' / '+money(task.cfg.cap)]])+'<p class="quiet">恢复次数和预算在本次任务内累计。暂停后，已分配的计算资源仍可能计费。</p>'));
}
function assistance(){
 if(!active()||!['人工控制','等待协助'].includes(task.state))return card('暂时不需要人工协助','<p>系统需要你帮忙时，会在这里说明原因和操作步骤。</p>'+acts(button('to-monitor','查看当前任务',home(),()=>{page=task?2:1},'primary')));
 const owned=task.state==='人工控制'&&!pending;
 const step=pending?3:owned?2:rest()?2:1;
 const steps=['等待设备确认静止','接管后调整衣物','归还控制，等待检查'].map((v,i)=>'<li class="'+(i+1===step?'current':i+1<step?'done':'')+'" '+(i+1===step?'aria-current="step"':'')+'>'+v+'</li>').join('');
 const hint=pending?'已收回手动权限，请停止调整。正在重新确认设备静止和衣物状态。':owned?'现在由你控制，可以调整衣物位置。调整完毕后，请点击“归还控制”。':rest()?'设备已确认静止。请先点击“接管”，获得权限后再调整衣物。':'请等待设备完全静止。在确认前，不要触碰衣物。';
 return grid(card('请按提示处理','<ol class="assist-steps" aria-label="人工协助步骤">'+steps+'</ol>'+note(hint)+acts(button('take',task.reason==='衣物超出工作区'&&!pending?'再次接管':'接管',home()&&task.state==='等待协助'&&rest()&&!pending,()=>{task.state='人工控制';task.manual=true;log('已取得手动权限，可以调整衣物。')},'primary'),button('adjust','确认已调整衣物',home()&&owned,()=>{task.adjustments++;stop='执行中';advanceGeneration();log('已记录一次人工调整（交互模拟）。')}),button('return','归还控制',home()&&owned,()=>{pending='归还停车';task.state='等待协助';halt();log('已收回手动权限，正在重新确认静止。','AUTHORITY_REVOKED')},'primary'),terminate())),card('为什么需要你帮忙',(task.reason==='衣物超出工作区'?'<div class="reason-alert"><strong>归还检查未通过</strong>请再次接管，将衣物移回桌面范围内，然后重新归还。</div>':'')+rows([['原因',task.reason],['控制权限',owned?'你已接管':'暂未开放手动操作'],['设备状态',stop]])+'<p class="quiet">归还检查失败时，系统会保持等待。请重新接管、修正问题，再归还控制。</p>'));
}
function verdict(r){
 if(r.state!=='完成'||r.manual||r.help||r.end.time>=r.cfg.time||r.end.wall/3600>=r.cfg.cap||r.quality==='未通过')return '否';
 return r.quality==='通过'?'是（合格试次示例）':'待定';
}
function result(){
 if(!home())return card('记录访问受限',note('请切回本地家庭用户并连接会话以访问自己的任务记录。'));
 if(!records.length)return card('尚无已保存结果',note('任务完成、失败或终止后，可在此查看其过程。'));
 const r=selected||records[0];const f=r.frames[frame]||r.frames[0];
 return grid(card('任务结果','<label>本会话记录 <select id="record">'+records.map(x=>'<option '+(x===r?'selected ':'')+'value="'+x.id+'">'+x.id+' · '+x.state+'</option>').join('')+'</select></label>'+rows([['任务结果',r.state],['人工协助',r.manual?'你曾接管并协助':r.help?'曾请求协助':'未请求协助'],['质量审核（模拟）',r.quality],['独立完成并合格（模拟）',verdict(r)]])+'<details><summary>查看结束原因和使用详情</summary>'+rows([['结束原因',r.reason],['人工调整次数',r.adjustments],['自动恢复次数',r.end.attempts],['活动时间（模拟）',r.time+' 秒'],['费用（模拟）',money(r.wall/3600)],['设备最后状态',r.frames.at(-1).stop],['质量依据',r.qualityReason]])+'</details>'+acts(
 button('export','导出记录',true,()=>{const a=document.createElement('a');const url=URL.createObjectURL(new Blob([JSON.stringify(exportRecord(r),null,2)],{type:'application/json'}));a.href=url;a.download=r.id+'-示例记录.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);say('已生成示例记录。')}),
 button('delete','删除记录',!r.linked&&(r!==task||rest()),()=>{if(!confirm('删除当前示例记录？'))return;records=records.filter(x=>x!==r);if(task===r)task=null;selected=records[0]||null;frame=0;stopPlay();say('已删除选定记录。')},'danger'))+(r.linked?note('存在数据引用，删除已锁定。'):'')+(r.quality==='通过'&&(r.manual||r.help)?note('末态质量通过；本次有求助或人工接管，因此自主成功为“否”。'):'')),card('回看操作过程',note('这是本次交互模拟的历史记录。播放和暂停回放都不会控制设备。')+eventPicker(r)+rows([['事件',(frame+1)+' / '+r.frames.length],['当时状态',f.state],['当时设备',f.stop]])+note(f.event)+'<label>定位事件<input id="scrub" type="range" min="0" max="'+(r.frames.length-1)+'" value="'+frame+'"></label>'+acts(button('play',playing?'暂停回放':'播放事件',r.frames.length>1,()=>{if(playing)stopPlay();else{if(frame===r.frames.length-1)frame=0;playing=setInterval(()=>{if(frame<r.frames.length-1)frame++;else stopPlay();render()},700)}}),button('next','下一事件',frame<r.frames.length-1,()=>{stopPlay();frame++}))));
}
const stages=['等待数据','示范已登记','已批准作业预算','已训练','验证通过并冻结','终测通过','终测失败','已激活'];
let compatible=true,draft=null;
const fields=[['time','活动时间上限（秒）',1,300,1],['cap','GPU 额度（美元）',.001,.25,.001],['attempts','恢复次数上限',1,3,1],['speed','夹爪静止阈值（米/秒）',.001,.005,.001],['prefix','单次动作前缀（示例步数）',1,8,1],['billLimit','最大分配时长（秒）',1,900,1]];
function maintenance(){
 if(!maintain())return card('维护区锁定',note('需要已连接的维护者会话。'));
 const can=idle(); const values=draft||cfg;
 const inputs=fields.map(([key,label,min,max,step])=>'<label class="field">'+label+'<input type="number" id="cfg-'+key+'" value="'+values[key]+'" min="'+min+'" max="'+max+'" step="'+step+'" '+(can?'':'disabled')+'></label>').join('');
 return grid(card('候选模型 · recovery-v0.2',rows([['当前模型',model],['候选状态',stages[candidate]],['数据划分','train-v1 / val-v1 / test-v1'],['接口兼容',compatible?'是':'否']])+note('训练集拟合参数，验证集选择并冻结版本。封存的终测集只评一次。')+acts(
 button('data','登记示范批次',can&&candidate===0,()=>{candidate++;say('示例来源、人工介入与异常标签已核验。')}),
 button('budget','批准示例作业预算',can&&candidate===1,()=>{candidate++;say('已核对示例估算、费率、预算和分配时限。')}),
 button('train','模拟训练完成',can&&candidate===2,()=>{candidate++;say('测试桩已返回训练完成事件。')}),
 button('val','验证并冻结',can&&candidate===3,()=>{candidate++;say('示例验证通过，已冻结候选。')}),
 button('test','读取一次终测报告',can&&candidate===4,()=>{candidate=5;say('封存批次已使用，示例终测通过。')}),
 button('activate','激活候选',can&&candidate===5&&compatible,()=>{model='recovery-v0.2';candidate=7;say('已激活示例候选，后续任务冻结新版本。')},'primary')
 )),card('配置版本 v'+cfg.version,note(can?'固定场景 TOPS-01。请在已注册的示例范围内设置动作、停止和预算参数。':'当前有任务、待处理启动请求或未确认停车。维护变更已锁定。')+inputs+acts(button('savecfg','检查并保存新版本',can,()=>{
   draft={};let error='';for(const [k,label,min,max,step] of fields){const el=$('cfg-'+k);const n=el.valueAsNumber;draft[k]=Number.isFinite(n)?n:'';if(!Number.isFinite(n)||!el.checkValidity())error=label+'须在 '+min+' 至 '+max+' 内，步长 '+step}
   if(error){say(error+'。当前配置仍为 v'+cfg.version);return}
   cfg={...cfg,...draft,version:cfg.version+1};draft=null;checked=false;say('配置已保存为 v'+cfg.version+'，仅供未来任务使用。')
 }))));
}
function harness(){
 const bs=[];const add=(k,s,ok,fn)=>{if(ok)bs.push(button(k,s,true,fn))};
 if(page===1){
  for(const [k,s] of [['good','有效'],['stale','相机观测已过期'],['asset','衣物配置不匹配']])
   add(k,'场景：'+s,!active()&&!pending,()=>{scene=s;checked=false;say('场景已更新，请重新检查就绪。')});
 }
 if(pending.endsWith('校验')){
  add('pass','校验通过',true,()=>validate(true));add('reject','校验失败',true,()=>validate(false));
 }
 if(active()&&page===2&&canRun()){
  for(const [id,label] of [['offset','抓取偏移'],['slip','部分滑移']]){
   add(id,label,true,()=>{task.bad=0;if(task.attempts>=task.cfg.attempts){help(label+'；恢复次数已耗尽');return}
    task.state='恢复中';task.attempts++;log(label+'。DR04 示例候选已获准，已使用一次恢复。')});
  }
  add('clear','偏差已消除',task.state==='恢复中',()=>{task.state='折叠中';task.bad=0;log('复查通过，回到正常折叠。')});
  add('recheckfail','恢复后检查未通过',task.state==='恢复中',()=>help('恢复后仍未确认持有衣物，停车并请求协助。'));
  add('nocandidate','无合格恢复候选',true,()=>help(reasonMessages.NO_SUPPORTED_CANDIDATE,'NO_SUPPORTED_CANDIDATE'));
  add('unknown','观测被遮挡',true,()=>help(reasonMessages.UNKNOWN,'UNKNOWN'));
  add('staleframe','过期观测',true,()=>demoReply('STALE_OBSERVATION'));
  add('late','决策超时',true,()=>demoReply('DECISION_TIMEOUT'));
  add('valid','有效观测',true,()=>demoReply(null));
  add('repeatReply','重送上一条决策回复',lastReply !== null,()=>receiveReply(lastReply));
  add('goal','观测到折叠目标',true,()=>{task.state='折叠中';goal=true;halt();log('DR03 示例通过。停止证据到达后才能记录完成。')});
 }
 if(stop==='已接受停止请求')add('stopping','设备正在停车',adapter,()=>{stop='停车中';log('设备正在减速，尚未取得静止证据。')});
 if(adapter&&!rest()&&stop!=='执行中'){
  add('proof','提交本代静止证据',true,proof);
  add('timeout','停止确认超时',stop!=='静止未确认',()=>{if(active())finish('失败','1 秒内未取得停车证据',false);pending='';goal=false;stop='静止未确认';log('停止超时，维持全局执行锁。')});
 }
 if(task && (active()||!rest())){
  add('old','送达旧代动作结果',true,()=>demoReply('OLD_GENERATION',task.gen-1));
  add('clock','推进 30 秒示例时间',true,()=>allocate((canRun()||(!rest()&&stop!=='执行中'))?30:0,30));
  add('cost','模拟计费额度耗尽',active(),()=>allocate(0,Math.ceil(task.cfg.cap*3600)-task.wall));
 }
 if(page===4&&selected&&home()){
  const r=selected;
  for(const [k,q,why] of [['qpass','通过','离线示例：阶段顺序、标志点及稳定性检查通过'],['qfail','未通过','离线示例：袖口偏差超限'],['qna','无法评估','离线示例：关键点缺失']]){
   add(k,'质量：'+q,true,()=>{r.quality=q;r.qualityReason=why;say('已附加模拟质量报告。')});
  }
  add('link',r.linked?'解除示例引用':'添加示例引用',true,()=>{r.linked=!r.linked;say('引用状态已更新。')});
 }
 if(page===5&&maintain()){
  add('incompatible',compatible?'模拟接口不兼容':'恢复兼容接口',true,()=>{compatible=!compatible;say('兼容检查结果已更新。')});
  add('testfail','终测未通过',idle()&&candidate===4,()=>{candidate=6;say('保留原模型。终测集已使用，需重新登记研究。')});
 }
 add('device',adapter?'设备适配器失联':'设备链路恢复',true,()=>{if(adapter)offline();else{adapter=true;say('链路已恢复。仍需本代静止证据。')}});
 add('session',connected?'控制会话失联':'重新认证并绑定',true,()=>{if(connected)disconnectUI();else{connected=true;say('已重新绑定本地演示会话，请显式操作。')}});
 return bs.join('');
}
function familyGuidance(){
 let heading='准备一件衣物，开始轻松折叠',detail='先确认桌面和衣物准备好，再检查就绪。',tone='normal';
 if(page===2){heading=task?'正在为你折叠':'从准备衣物开始';detail='你可以随时暂停。需要调整衣物时，请先等待设备静止并接管。';}
 if(task&&task.state==='恢复中'&&page===2){heading='正在尝试自动恢复';detail='暂时不需要你操作。恢复后会检查抓持状态，再决定是否继续。';}
 if(task&&task.state==='已暂停'&&page===2){heading=rest()?'折叠已暂停，设备已静止':'折叠已暂停，正在等待设备静止';detail=rest()?'选择继续折叠，或申请接管来调整衣物。':'请勿触碰衣物。任务暂停不代表设备已经停稳。';tone=rest()?'normal':'wait';}
 if(page===3){heading=task?.state==='人工控制'?'已接管，请按提示调整衣物':'需要你帮忙检查衣物';detail=rest()?'先取得手动权限，再调整衣物。':'请等待设备确认静止，暂时不要触碰衣物。';tone='wait';if(!active()){heading='需要协助时，我们会在这里提示';detail='现在无需进行人工操作。';}}
 if(page===3&&task?.state==='人工控制'&&!pending){detail='你已取得手动权限。调整完成后确认，再归还控制。';tone='normal';}
 if(page===3&&task?.reason==='衣物超出工作区'&&!pending&&task.state==='等待协助'){heading='归还检查未通过，请重新接管';detail='自动操作保持暂停。请先再次接管，再把衣物移回桌面范围内。';tone='wait';}
 if(page===4){heading=selected?'查看这次折叠的结果':'你的折叠记录会保存在这里';detail='运行结果、人工协助和质量审核分别记录。回放只查看历史，不控制设备。';}
 if(page===5){heading='维护工作区';detail='配置更改仅用于下一次任务。家庭用户无维护权限。';}
 if(pending){heading=pending==='启动校验'?'正在检查，尚未开始折叠':pending==='继续校验'?'正在检查是否可以继续':'已归还控制，正在重新检查';detail=pending==='启动校验'?'请等待检查结果，也可以取消本次启动。':'请停止手动调整，等待设备静止和校验结果。';tone='wait';}
 if(!adapter||!connected){heading=!adapter?'设备连接中断':'操作会话已断开';detail='当前操作已锁定。请恢复连接并等待设备重新确认安全状态。';tone='wait';}
 $('guidance').className='guidance '+tone;$('guidance').innerHTML='<span class="status-mark" aria-hidden="true">'+(tone==='wait'?'!':String(Math.min(page,4)))+'</span><div><h2>'+heading+'</h2><p>'+detail+'</p></div>';
 $('identity').textContent=role==='maint'?'维护者视图':'家庭用户视图';
 $('demo-next').textContent=pending.endsWith('校验')?'下一步演示：返回“校验通过”或“校验失败”。':!rest()&&stop!=='执行中'?'下一步演示：提交本代静止证据，或演示停车超时。':'这里可注入异常、推进模拟时间或切换角色。';
 $('user-message').textContent=notice.replace(/\s*\[[A-Z_]+\]/g,'').replace(/测试桩已返回本代静止证据：速度达标、队列为空。/g,'设备已确认静止。').replace(/DR\d+/g,'');
}
function render(){
 const focused=document.activeElement?.id; commands.clear();
 for(const control of document.querySelectorAll('[data-role]')){
   control.setAttribute('aria-pressed',String(control.dataset.role===role));
   control.disabled = !connected;
 }
 $('restore-session').hidden=connected;
 document.querySelector('nav').innerHTML=views.map((s,i)=>'<button id="nav'+(i+1)+'" data-page="'+(i+1)+'" aria-current="'+(page===i+1)+'" '+(i===4&&!maintain()?'disabled':'')+'>'+s+'</button>').join('');
 document.body.dataset.role=role; $('sid').textContent=role==='home'?'家庭用户':'维护人员';$('title').textContent=views[page-1];$('identity').textContent=(connected?'会话在线':'会话失联')+' · '+(adapter?'设备在线':'设备离线');
 $('no-maint').hidden=true;
 $('workspace').innerHTML=[prep,monitor,assistance,result,maintenance][page-1]();
 $('technical').innerHTML=reasonGuide()+(task?rows([['任务编号',task.id],['模型版本',task.model],['控制代次',task.gen]]):'');
 $('events').innerHTML=harness();$('msg').textContent=notice; familyGuidance();
 if($('source').dataset.page!==String(page)){$('source').replaceChildren($('ref'+page).content.cloneNode(true));$('source').dataset.page=page}
 if(focused&&document.getElementById(focused))$(focused).focus({preventScroll:true});
}
document.addEventListener('click',e=>{
 const b=e.target.closest('button');if(!b||b.disabled)return;
 if(b.dataset.role){
   if(!connected || role===b.dataset.role)return;
   role=b.dataset.role;
   draft=null;
   let nextPage = selected ? 4 : 1;
   if(active()) nextPage = ['等待协助','人工控制'].includes(task.state) ? 3 : 2;
   go(role==='maint' ? 5 : nextPage);
   return;
 }
 if(b.id==='open-demo'){$('demo-dialog').showModal();return}
 if(b.id==='close-demo'){$('demo-dialog').close();$('open-demo').focus();return}
 if(b.id==='restore-session'){commands.get('session').act();render();return}
 if(b.dataset.page){go(Number(b.dataset.page));return}
 const op=commands.get(b.id);if(op?.enabled){op.act();render()}
});
document.addEventListener('change',e=>{
 const el=e.target;
 if(el.hasAttribute('data-prep')){prepared[Number(el.dataset.prep)]=el.checked;checked=false;notice=''}
 else if(el.id==='record'){selected=records.find(x=>x.id===el.value);frame=0;stopPlay()}
 else if(el.id==='scrub'||el.id==='event-select'){frame=Number(el.value);stopPlay()}
 else return;
 render()
});
render();

$('open-records').addEventListener('click', () => {
  stopPlay();
  render();
});

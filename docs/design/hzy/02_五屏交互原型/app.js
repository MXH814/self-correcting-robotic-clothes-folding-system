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
function log(text){
  say(text);
  if(task) task.frames.push({event:text,state:task.state,stop,activeSeconds:task.time,billedSeconds:task.wall,attempts:task.attempts, generation:task.gen});
}
function halt(){if(task)task.gen++; stop = adapter ? '已接受停止请求' : '静止未确认'}
function help(reason){
  task.help = true;task.reason = reason; task.state = '等待协助';goal = false;pending = '';
  if(!rest()) halt();
  page = 3;log(reason + '。确认静止后请接管。');
}
function finish(state,reason,requestStop=true){
  if(!active())return;
  pending = '';goal = false;task.state = state;task.reason = reason;
  if(requestStop)halt();
  task.end = {time:task.time,wall:task.wall,attempts:task.attempts};
  records.unshift(task);selected = task;frame = 0;page = 4;log(reason);
}
function proof(){
  stop = '已确认静止';log('收到本代静止证据：速度达标、队列为空。');
  if(pending === '归还停车')pending = '归还校验';
  if(goal && active())finish('完成','已满足在线目标并确认停止。',false);
}
function validate(pass){
  const origin = pending; pending = '';
  if(origin === '启动校验'){
    if(!pass || !ready()){checked=false;requestError='相机观测超过 1 秒，请重新取景。';scene='相机观测已过期';say(requestId+' 校验失败：'+requestError);return}
    task = {id:'F-'+String(nextId++).padStart(3,'0'),requestId,seed:100+requestSerial,goalId:'TOPS-FOLD-01',state:'折叠中',gen:1,cfg:{...cfg},model,time:0,wall:0,attempts:0,bad:0,adjustments:0,help:false,manual:false,quality:'待审核',qualityReason:'等待离线证据',reason:'',frames:[],linked:false};
    stop='执行中';page=2;checked=false;prepared=[false,false];log('任务已创建，已冻结模型及配置。');return
  }
  if(pass && rest()){
    task.state=origin === '继续校验' ? savedOrigin : '折叠中'; stop='执行中';task.gen++;task.bad=0;page=2;
    log(task.state === '恢复中' ? '校验通过。下一次纠正仍需接受新候选。' : '校验通过，已恢复自动控制。');
  }else{
    task.state=origin === '继续校验' ? '已暂停' : '等待协助';page=origin === '继续校验'?2:3;
    task.reason='衣物超出工作区';log(origin === '继续校验'?'继续校验失败，保持暂停。':'归还校验失败。请重新接管，把衣物移回桌内。');
  }
}
function ready(){return prepared.every(Boolean) && scene==='有效' && rest() && !active()}
function issue(text){task.bad++;if(task.bad>=3)help('连续三次观测或决策不可用');else log(text+'，已丢弃。连续 '+task.bad+'/3 次，请重新观测。')}
function allocate(sim,wall){
  task.time+=sim;task.wall+=wall;
  if(active() && (task.time>=task.cfg.time || task.wall/3600>=task.cfg.cap || task.wall>=task.cfg.billLimit)){
    finish('失败',task.time>=task.cfg.time?'活动时间耗尽':task.wall/3600>=task.cfg.cap?'计费额度耗尽':'资源分配时限耗尽');return
  }
  log('已记录活动 '+sim+' 秒、资源占用 '+wall+' 秒。');
}
function pause(){
  savedOrigin=task.state;task.state='已暂停';pending='';goal=false;halt();log('已暂停派发，正在等待设备停车。');
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
  if(active())finish('失败','设备适配器失联');else {if(task)task.gen++;log('设备适配器失联，保留已有结果。')}
  stop='静止未确认';say('设备失联。重连后仍需新的静止证据。');
}
function stopPlay(){clearInterval(playing);playing=null}
function go(n){page=n;stopPlay();notice='';render()}
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
  return rows([['任务状态',pending || task?.state || '待准备'],['设备状态',stop],['恢复次数',task?task.attempts+' / '+task.cfg.attempts:'—'],['活动仿真时间',task?task.time+' / '+task.cfg.time+' 秒':'—'],['模拟 GPU 费用',task?money(task.wall/3600)+' / '+money(task.cfg.cap):'—']]);
}
function diagram(state){
 const folded=state==='完成',shift=state==='恢复中'?18:0;
 return '<svg class="scene" viewBox="0 0 360 170" role="img" aria-label="桌面上衣示意图，记录状态：'+state+'"><defs><pattern id="mesh" width="16" height="16" patternUnits="userSpaceOnUse"><path d="M16 0H0V16" fill="none" stroke="#cedacb"/></pattern></defs><rect width="360" height="170" fill="url(#mesh)"/><rect x="80" y="12" width="200" height="143" rx="5" fill="none" stroke="#7b9a7a" stroke-dasharray="5 5"/><g transform="translate('+shift+' 0)"><path d="'+(folded?'M147 66H215V127H147Z':'M151 33L123 43 87 66 105 87 132 72 132 138 228 138 228 72 255 87 273 66 237 43 209 33Q179 55 151 33Z')+'" fill="#aec5ac" stroke="#396448" stroke-width="2"/></g><text x="12" y="155">俯视示意</text></svg>';
}
function terminate(){
 return button('terminate','终止任务',home()&&active(),()=>{if(confirm('终止本次任务并请求停车？已终止的任务无法继续。'))finish('已终止','用户终止任务。')},'danger')
}
function prep(){
 const checkboxes=['已放好一件展开、无结的上衣','桌面没有杂物，已了解人工协助步骤'].map((s,i)=>'<label><input type="checkbox" data-prep="'+i+'" '+(prepared[i]?'checked ':'')+(home()&&!pending&&!active()?'':'disabled')+'> '+s+'</label>').join('');
 const hint=!home()?'请使用已连接的家庭用户会话。':active()?'已有任务，请到运行监控查看。':pending?'等待测试桩返回校验结果，可取消本次启动。':!rest()?'启动已锁定。请等待设备给出新的静止证据。':scene!=='有效'?'修正场景：'+scene+'，然后重新检查。':!prepared.every(Boolean)?'请先确认两项准备条件。':checked?'就绪检查通过，可以启动。':'请检查就绪条件。';
 return grid(card('桌面与衣物',diagram('待准备')+rows([['固定衣物',cfg.scene],['折叠目标','TOPS-FOLD-01'],['已批准模型',model],['当前停车状态',stop]])),card('启动前确认','<div class="checks">'+checkboxes+'</div>'+note(hint)+acts(
 button('check','检查就绪',home()&&!active()&&!pending,()=>{checked=ready();say(checked?'就绪检查通过。':hint)}),
 button('start','开始折叠',home()&&ready()&&checked&&!pending,()=>{requestId='R-'+String(++requestSerial).padStart(3,'0');pending='启动校验';say(requestId+' 已受理。等待 DR01 校验，尚未分配任务。')},'primary'),
 button('cancel','取消启动',home()&&pending==='启动校验',()=>{pending='';checked=false;say('请求已取消。')})
 )));
}
function monitor(){
 if(!task)return card('尚无运行记录',note('请先在准备页启动任务。'));
 return grid(card('桌面观测',diagram(task.state)+rows([['任务编号',task.id],['模型 / 配置',task.model+' / v'+task.cfg.version]])+note(task.frames.at(-1)?.event||'等待观测')),card('运行控制',status()+acts(
 button('pause','暂停',home()&&active()&&['折叠中','恢复中'].includes(task.state)&&!pending,pause),
 button('resume','继续',home()&&task.state==='已暂停'&&rest()&&!pending,()=>{pending='继续校验';log('正在校验原折叠阶段及剩余预算。')}),
 button('ask','请求协助',home()&&task.state==='已暂停'&&rest()&&!pending,()=>help('用户请求检查衣物')),terminate())+note(task.wall/3600>=.8*task.cfg.cap?'费用已使用至少 80%，请留意剩余额度。已分配的 GPU 在等待期间仍计费。':'确认停车后才能继续或求助。已分配的 GPU 在等待期间仍计费。')));
}
function assistance(){
 if(!active()||!['人工控制','等待协助'].includes(task.state))return card('当前没有人工协助请求',note('出现持续异常时系统会求助，也可在运行监控确认暂停后主动求助。'));
 return grid(card('协助请求',rows([['原因',task.reason],['当前状态',pending||task.state],['设备状态',stop],['可用恢复次数',task.cfg.attempts-task.attempts],['已用费用',money(task.wall/3600)]])),card('手动调整',note(pending?'手动权限已撤回。等待新的停车证据与归还校验。':task.state==='人工控制'?'可调整衣物位置或夹持接触，完成后归还控制。':rest()?'已确认静止，请显式接管后调整。':'停止请求已发出。设备确认静止前，手动操作锁定。')+acts(
 button('take','接管',home()&&task.state==='等待协助'&&rest()&&!pending,()=>{task.state='人工控制';task.manual=true;log('已授权本次手动接管。')},'primary'),
 button('adjust','调整衣物位置',home()&&task.state==='人工控制'&&!pending,()=>{task.adjustments++;stop='执行中';task.gen++;log('完成一次示例人工调整。')}),
 button('return','归还控制',home()&&task.state==='人工控制'&&!pending,()=>{pending='归还停车';task.state='等待协助';halt();log('已撤回手动权限，等待本次归还的停车证据。')}),
 terminate())));
}
function verdict(r){
 if(r.state!=='完成'||r.manual||r.help||r.end.time>=r.cfg.time||r.end.wall/3600>=r.cfg.cap||r.quality==='未通过')return '否';
 return r.quality==='通过'?'是（合格试次示例）':'待定';
}
function result(){
 if(!home())return card('记录访问受限',note('请切回本地家庭用户并连接会话以访问自己的任务记录。'));
 if(!records.length)return card('尚无已保存结果',note('任务完成、失败或终止后，可在此查看其过程。'));
 const r=selected||records[0];const f=r.frames[frame]||r.frames[0];
 return grid(card('任务结果','<label>本会话记录 <select id="record">'+records.map(x=>'<option '+(x===r?'selected ':'')+'value="'+x.id+'">'+x.id+' · '+x.state+'</option>').join('')+'</select></label>'+rows([['运行结果',r.state],['结束原因',r.reason],['求助 / 已接管',(r.help?'有':'无')+' / '+(r.manual?'有':'无')],['终态恢复次数',r.end.attempts],['终态活动时间',r.end.time+' 秒'],['累计活动 / 计费',r.time+' 秒 / '+money(r.wall/3600)],['设备最后记录',r.frames.at(-1).stop],['冻结版本',r.model+' / v'+r.cfg.version],['离线质量',r.quality],['依据',r.qualityReason],['示例自主成功',verdict(r)]])+acts(
 button('export','导出记录',true,()=>{const a=document.createElement('a');const url=URL.createObjectURL(new Blob([JSON.stringify(r,null,2)],{type:'application/json'}));a.href=url;a.download=r.id+'-示例记录.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);say('已生成示例记录。')}),
 button('delete','删除记录',!r.linked&&(r!==task||rest()),()=>{if(!confirm('删除当前示例记录？'))return;records=records.filter(x=>x!==r);if(task===r)task=null;selected=records[0]||null;frame=0;stopPlay();say('已删除选定记录。')},'danger'))+(r.linked?note('存在数据引用，删除已锁定。'):'')),card('事件回放 · 只读',diagram(f.state)+rows([['事件',(frame+1)+' / '+r.frames.length],['当时状态',f.state],['当时设备',f.stop]])+note(f.event)+'<label>定位事件<input id="scrub" type="range" min="0" max="'+(r.frames.length-1)+'" value="'+frame+'"></label>'+acts(button('play',playing?'暂停回放':'播放',r.frames.length>1,()=>{if(playing)stopPlay();else{if(frame===r.frames.length-1)frame=0;playing=setInterval(()=>{if(frame<r.frames.length-1)frame++;else stopPlay();render()},700)}}),button('next','下一事件',frame<r.frames.length-1,()=>{stopPlay();frame++}))));
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
  add('nocandidate','无合格恢复候选',true,()=>help('恢复候选未通过动作约束'));
  add('unknown','观测被遮挡',true,()=>help('观测置信度不足，需人工检查'));
  add('staleframe','过期观测',true,()=>issue('观测年龄超过 1 秒'));
  add('late','决策超时',true,()=>issue('决策超过 2 秒'));
  add('valid','有效观测',true,()=>{task.bad=0;log('收到有效观测，连续无效次数清零。')});
  add('goal','观测到折叠目标',true,()=>{task.state='折叠中';goal=true;halt();log('DR03 示例通过。停止证据到达后才能记录完成。')});
 }
 if(stop==='已接受停止请求')add('stopping','设备正在停车',adapter,()=>{stop='停车中';log('设备正在减速，尚未取得静止证据。')});
 if(adapter&&!rest()&&stop!=='执行中'){
  add('proof','提交本代静止证据',true,proof);
  add('timeout','停止确认超时',stop!=='静止未确认',()=>{if(active())finish('失败','1 秒内未取得停车证据',false);pending='';goal=false;stop='静止未确认';log('停止超时，维持全局执行锁。')});
 }
 if(task && (active()||!rest())){
  const staleReply={taskId:task.id,generation:task.gen-1};
  add('old','送达旧代动作结果',true,()=>{
   if(staleReply.taskId!==task.id || staleReply.generation!==task.gen)log('丢弃过期结果：返回代号 '+staleReply.generation+'，当前代号 '+task.gen+'。没有派发动作。');
  });
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
function render(){
 const focused=document.activeElement?.id; commands.clear();
 $('role').value=role;$('role').disabled=!connected;
 document.querySelector('nav').innerHTML=views.map((s,i)=>'<button id="nav'+(i+1)+'" data-page="'+(i+1)+'" aria-current="'+(page===i+1)+'" '+(i===4&&!maintain()?'disabled':'')+'><span>S0'+(i+1)+'</span>'+s+'</button>').join('');
 $('sid').textContent='S0'+page+' / 本地演示';$('title').textContent=views[page-1];$('identity').textContent=(connected?'会话在线':'会话失联')+' · '+(adapter?'设备在线':'设备离线');
 $('workspace').innerHTML=[prep,monitor,assistance,result,maintenance][page-1]();
 $('events').innerHTML=harness();$('msg').textContent=notice;
 if($('source').dataset.page!==String(page)){$('source').replaceChildren($('ref'+page).content.cloneNode(true));$('source').dataset.page=page}
 if(focused&&document.getElementById(focused))$(focused).focus({preventScroll:true});
}
document.addEventListener('click',e=>{
 const b=e.target.closest('button');if(!b||b.disabled)return;
 if(b.dataset.page){go(Number(b.dataset.page));return}
 const op=commands.get(b.id);if(op?.enabled){op.act();render()}
});
document.addEventListener('change',e=>{
 const el=e.target;
 if(el=== $('role')){role=el.value;draft=null;stopPlay();if(page===5&&role==='home')page=1;say('角色已切换。')}
 else if(el.hasAttribute('data-prep')){prepared[Number(el.dataset.prep)]=el.checked;checked=false;notice=''}
 else if(el.id==='record'){selected=records.find(x=>x.id===el.value);frame=0;stopPlay()}
 else if(el.id==='scrub'){frame=Number(el.value);stopPlay()}
 else return;
 render()
});
render();

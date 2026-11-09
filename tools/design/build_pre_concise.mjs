// Editable Assignment 2 presentation. Local fallback after Artifact Session host failure.
import fs from 'node:fs/promises';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const args=process.argv.slice(2);
const arg=(name)=>{const i=args.indexOf(name);if(i<0)throw new Error('Missing '+name);return args[i+1];};
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const BUILD=path.resolve(arg('--build-dir'));
const SOURCE=path.resolve(arg('--source'));
const modules=process.env.RUNTIME_NODE_MODULES;
if(!modules)throw new Error('Set RUNTIME_NODE_MODULES from load_workspace_dependencies');
const {Presentation,PresentationFile,FileBlob}=await import(pathToFileURL(path.join(modules,'@oai/artifact-tool/dist/artifact_tool.mjs')).href);
const {applyPresentationChartFont}=await import(pathToFileURL(path.join(arg('--skill-dir'),'container_tools/artifact_tool_utils.mjs')).href);
const C={ink:'#142D43',teal:'#007B80',muted:'#536878',line:'#C8D5DB',bg:'#FAFCFC',pale:'#E8F3F2',orange:'#AB5422',white:'#FFFFFF'};
const E=path.join(ROOT,'docs/research/zhangmingbo/pre-abc-evidence-20261109');
const IMG=path.join(E,'Z3/关键截图/原始对应帧');
await fs.mkdir(path.join(BUILD,'renders'),{recursive:true});

// Read the actual source with the supported importer before changing its structure.
const imported=await PresentationFile.importPptx(await FileBlob.load(SOURCE));
const src=imported.toProto();
await fs.writeFile(path.join(BUILD,'source-import.json'),JSON.stringify({slides:imported.slides.items.length,source:SOURCE,slideSize:src.slideSize},null,2));
const p=Presentation.create({slideSize:{width:1280,height:720}});
p.theme.defaultFont='Times New Roman';

function text(s,v,x,y,w,h,size=28,color=C.ink,bold=false,align='left'){
  const q=s.shapes.add({geometry:'textbox',name:v.replace(/\n/g,' ').slice(0,45),position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
  q.text=v;q.text.insets=0;q.text.style={fontSize:size,color,bold,alignment:align};return q;
}
function line(s,x1,y1,x2,y2,color=C.line,width=1.5,tip=false){
  if(x2<x1||y2<y1){
    const dx=x2-x1,dy=y2-y1;
    const q=s.shapes.add({geometry:tip?'connector':'line',position:{left:Math.min(x1,x2),top:Math.min(y1,y2),width:Math.abs(dx),height:Math.abs(dy)},fill:'none',line:{fill:color,width},...(tip?{head:{type:'triangle',width:'med',length:'med'}}:{})});return q;
  }
  return s.shapes.add({geometry:tip?'connector':'line',position:{left:x1,top:y1,width:x2-x1,height:y2-y1},fill:'none',line:{fill:color,width},...(tip?{tail:{type:'triangle',width:'med',length:'med'}}:{})});
}
function rect(s,x,y,w,h,fill=C.pale,stroke=C.teal,width=1.5){return s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:stroke,width}});}
function node(s,v,x,y,w,h=90,{fill=C.pale,color=C.ink,size=28,stroke=C.teal}={}){
  const q=rect(s,x,y,w,h,fill,stroke);q.name=v.replace(/\n/g,' ');q.text=v;q.text.insets=10;q.text.style={fontSize:size,color,bold:true,alignment:'center',verticalAlignment:'middle'};return q;
}
function connect(s,a,b,from='right',to='left',color=C.teal){return s.shapes.connect(a,b,{kind:'straight',fromSide:from,toSide:to,line:{fill:color,width:2},tail:{type:'triangle',width:'med',length:'med'}});}
function photo(s,source,x,y,w,h){return s.images.add({blob:new Uint8Array(readFileSync(source)),contentType:'image/png',position:{left:x,top:y,width:w,height:h},fit:'contain',alt:path.basename(source)});}
function slide(n,title,sub='',dark=false){
  const s=p.slides.add();s.background.fill=dark?C.ink:C.bg;
  text(s,title,64,44,1152,65,44,dark?C.white:C.ink,true);
  if(sub)text(s,sub,66,119,1150,42,25,dark?'#BBD6DB':C.muted);
  text(s,String(n).padStart(2,'0'),1166,676,50,26,19,dark?'#BBD6DB':C.muted,false,'right');
  return s;
}
function foot(s,v,dark=false){text(s,v,64,635,1130,36,21,dark?'#BBD6DB':C.muted);}
function table(s,values,x,y,w,h,widths,size=26){
  const q=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,columnWidths:widths,values});
  for(let r=0;r<values.length;r++)for(let c=0;c<values[0].length;c++){
    const cell=q.getCell(r,c);cell.fill=r===0?C.ink:(r%2?'#FFFFFF':'#EFF5F5');cell.text.style={fontSize:size,color:r===0?C.white:C.ink,bold:r===0};
  }
  q.borders.assign({style:'solid',fill:'#CCD8DD',width:1});return q;
}

export const scripts=[
 ['自主纠错型机器人叠衣系统','胡知鱼',8,'大家好，我们汇报自主纠错型机器人叠衣系统的设计，以及检测和恢复的仿真验证。'],
 ['核心方案：异常后恢复并继续','胡知鱼',35,'我们希望机器人遇到抓取偏差或滑移后，能够判断是否恢复，恢复后再检查，然后继续叠衣。项目面向需要机器人叠衣的使用者，当前限定固定桌面上的一类上衣。我们已经有一次RGB告警触发重抓、复检并接续折叠的实跑。这里先区分两层：检测、恢复和复检是任务处理方法；系统层还要管理执行权限、人工协助和记录。接下来按这两个层次说明设计。'],
 ['用户流程与人工接管','胡知鱼',35,'使用者准备衣物并启动，系统运行后给出结果。需要协助时进入人工协助页，用户先等设备确认静止，再显式接管。归还控制权会立即撤回手动权限，取得新的静止证据并校验后才继续，校验失败可再次接管。维护者另有配置和模型入口。这些交互已有可点击原型，事件由测试桩驱动，界面还没有接入实际仿真控制。下面由张介绍系统结构。'],
 ['逻辑架构与执行权限','张茗博',40,'逻辑架构将用户界面、任务协调器、仿真适配器和检测恢复分开。界面提交请求，协调器管理任务状态并统一授权动作，适配器执行并返回观测和测量。检测恢复模块接收上下文、返回告警和动作建议，不直接取得控制权。任务、观测和动作关联记录。集中授权增加检查开销，但能统一处理过期结果、暂停和人工接管。这里描述目标职责，当前实际验证的是后面的检测与恢复开发链。'],
 ['本地部署与技术选择','张茗博',35,'部署基线沿用我的工作站。浏览器运行HTML和JavaScript交互原型，仿真与检测链使用Isaac Sim 4.5、DexGarmentLab及PyTorch。正常折叠沿用GAM加脚本，观测和动作写入本地记录。选择已有环境是因为资产与控制通道已经跑通，依赖环境按兼容要求隔离。采用本地基线减少了环境和资产迁移，界面与仿真联调仍待完成。下面由马说明检测和恢复。'],
 ['持有阶段的视觉异常检测','马祥珲',45,'检测复用FIPER的观测分支思想。固定ResNet18提取图像特征，用正常观测训练RND预测网络，再用过去五帧误差和当前袖子阶段的阈值判断偏离。左右袖阶段来自已经执行的正常控制命令，数据不足或阶段不适用时输出未知。我们选观测分支，因为当前控制器不能提供完整FIPER需要的生成式动作样本。图是B恢复前同一左袖阶段的真实分数，首次越线后发出一次恢复请求，等待期间继续保留告警。分数表示偏离正常观测，不是失败概率。'],
 ['恢复执行与复检','马祥珲',45,'恢复不是收到一份旧告警就直接执行。流程先阻止正常控制继续派发，测量静止和名义路径，再用新图像确认异常，然后执行固定的五步重抓宏。宏后用新的持有窗口复检，通过后建立新代次基线，才允许限定左袖接续。检查失败或缺少必要输入则进入求助。当前B的五步宏实际执行了61条底层指令。宏后和接续的持有判断使用仿真内部几何，原始视觉报告仍保留。这是当前实现的边界。'],
 ['告警恢复实跑','马祥珲',50,'请看这段B实录，视频约29秒。衣物提前脱离后，RGB检测告警，系统完成前检并重新确认，执行重抓，再复检和接续折叠，最后流程完整结束。对照另外两类开发场景，A正常运行没有告警或恢复，C缺少检测包时请求协助，之后没有新派发。这里展示流程已经接通的证据，接续使用仿真几何，叠衣质量和总体恢复效果还需要更多试次评价。'],
 ['设计演进与后续验证','马祥珲',25,'设计中保留原产品要求，细化了两类记录：校验失败要分清来源和原因，报警与停止接受要分开记录。下一步集中验证误报和异常覆盖、最终叠衣质量，以及界面和仿真的联调。课堂反馈会进入最终设计修订。我们的当前成果是系统设计、可交互原型，以及已有实跑证据的检测恢复开发链。谢谢。']
];
const sources=[
 'Project title and members: docs/requirements/SRS_EN.docx. Cover image: docs/research/zhangmingbo/fold-experiments-20261108/stage-3.png, actual simulation.',
 'Scope: SRS §3.4. Current B: PR29 b5e90454, independently reviewed through PR32. Images are original corresponding frames 04/05/07 from Z3. One development case does not establish general success rate. Initial alarm uses RGB; post-recovery holding and continuation use privileged simulation geometry.',
 'prototypes/ui/app.js assistance(), proof(), validate(); ui-contract.md. The five-screen prototype uses synthetic events and is not integrated with simulator control. Diagram shows proposed product interaction, not measured physical stopping. Return withdraws manual permission immediately; new rest proof and validation precede continuation.',
 'docs/design/interfaces.md, recovery-design.md, models/zhang-system-models.md. Diagram simplifies logical roles, not process deployment. Observation gateway and executed-history access are encapsulated within adapter/coordinator context here. Coordinator authority is target product design, not a claimed completed transport implementation.',
 'docs/research/zhangmingbo/environment-feasibility.md; tools/simulation/official_ab_evidence.py and official_pre_adapter.py; PR29–31. Workstation hardware is Windows 11, RTX 4060 Laptop 8 GB, RAM 16 GB. Placement is a development baseline, not a claim that every logical component is a separate process. The UI-to-simulator connection remains unintegrated. No remote host is promised.',
 'Method source: FIPER, Failure Prediction at Runtime for Generative Robot Policies, NeurIPS 2025, https://proceedings.nips.cc/paper_files/paper/2025/hash/0b7cb3b8cc44e652761245537027db44-Abstract-Conference.html . This project adapts observation embeddings/RND and does not reproduce the action-entropy branch or original guarantees. Plot uses B/pre-demo-events.jsonl: generation 0, LEFT_SLEEVE_HOLD, NORMAL/ANOMALY, observed_sim_s and score; 28 consecutive valid reports, five anomalous. Full values remain in source; new native chart/workbook displays six-decimal literals. First abnormal observed time is about 7.033 s. Five pending reports correspond to one request, not five votes or attempts. Package b9df07d4: one normal trial fitting, four calibration; no independent unseen holdout claimed.',
 'docs/design/pre-current-runtime-contract.md, models/pre-diagnostic-models.md, ADR-MA-007; B execution/workflow/geometry evidence. Five macro operations: release, retreat, regrasp, close, lift. One accepted attempt links 61 SDK commands. Post-macro 13 reports = 12 warmup UNKNOWN and one HELD. A separate 13-report new-generation baseline precedes 23 overlapping continuation checks. No independent-success count is inferred. Any required preflight/execution/recheck failure blocks new dispatch and requests help. Diagram abstracts those checks without introducing a new algorithm.',
 'PR29 Z3 original simulation video, B clip frames305–883 from full1014 frames at20fps, 28.95s, no extra speedup. B clip SHA-256 81a1f498e7c15b266c013a4043817299c5b7c457ccc989fe22c01c2f83325951. Click media on this slide and narrate concurrently, no backup-slide jump. A is a normal case, not a matched-fault no-recovery baseline. C missing package blocks later dispatch, not proof of physical rest. Regional proxy A2048/2048, B2002/2048 does not certify SRS quality or autonomy. If media fails use stills on slide2 and source results in backup11.',
 'Accepted-design CR-01/02 in requirements-changes.md and ADR-MA-005; unchanged30 product requirements/18 acceptance tests. CR-02 retains offline human judgement, first alarm and accepted-stop timestamps with clock domains; the slide abbreviates this to the audience-relevant distinction. Remaining issues: ma-risks-and-validation.md. Presentation feedback has not occurred. Full product implementation/validation is Part III; these are planned checks, not new deadlines or passed tests.'
];

let s=slide(1,'','',true);
photo(s,path.join(ROOT,'docs/research/zhangmingbo/fold-experiments-20261108/stage-3.png'),642,0,638,720).fit='cover';
text(s,'Assignment 2  系统设计',64,111,550,40,25,'#8BD3CF');
text(s,'自主纠错型\n机器人叠衣系统',64,200,560,170,60,C.white,true);
text(s,'第三组',66,535,500,35,27,'#BBD6DB');
text(s,'马祥珲  胡知鱼  张茗博',66,586,550,45,27,C.white);

s=slide(2,'核心方案：异常后恢复并继续','固定桌面、一类上衣，处理抓取偏差与部分滑移');
text(s,'已完成一次告警驱动的重抓与接续实跑',64,188,1152,50,34,C.teal,true);
const labels=['RGB告警附近','执行重抓','接续结束'];
const shots=['04_B观测告警.png','05_B重抓执行.png','07_B完整折叠.png'];
for(let i=0;i<3;i++){photo(s,path.join(IMG,shots[i]),64+i*395,254,362,242);text(s,labels[i],64+i*395,505,362,38,27,C.ink,true);}
const core=['检测异常','恢复动作','新观测复检','接续折叠'].map((v,i)=>node(s,v,64+i*300,568,252,62,{size:27}));
for(let i=0;i<3;i++)connect(s,core[i],core[i+1]);

s=slide(3,'用户流程与人工接管','使用者负责准备与协助，维护者管理配置和模型');
const prep=node(s,'准备衣物',64,230,224,96),run=node(s,'运行监控',466,230,260,96),res=node(s,'查看结果',988,230,228,96);
connect(s,prep,run);connect(s,run,res);text(s,'启动',350,250,70,35,24,C.muted);text(s,'结束',823,250,70,35,24,C.muted);
const assist=node(s,'人工协助',466,490,260,90);
line(s,516,326,516,490,C.teal,2,true);text(s,'需要协助',347,387,145,40,25,C.muted);
line(s,676,490,676,326,C.teal,2,true);text(s,'归还并校验',710,387,195,40,25,C.muted);
node(s,'维护入口\n配置与模型',64,485,224,105,{fill:'#F0F3F5',stroke:C.line,size:26});
text(s,'确认静止后显式接管\n归还后重新取证与校验',849,496,367,92,27,C.teal,true);
foot(s,'五屏交互原型已完成，当前由测试事件驱动，尚未接入仿真控制');

s=slide(4,'逻辑架构与执行权限','协调器统一授权，检测恢复模块返回建议');
const ui=node(s,'用户界面\n请求与状态',64,226,230,106),co=node(s,'任务协调器\n状态与执行权限',473,226,300,106),ad=node(s,'仿真适配器\n执行与测量',994,226,222,106);
connect(s,ui,co);text(s,'控制请求',324,238,133,40,24,C.muted);
line(s,773,257,994,257,C.teal,2,true);text(s,'授权动作',817,203,150,36,24,C.muted);
line(s,994,308,773,308,C.teal,2,true);text(s,'观测与反馈',803,339,185,36,24,C.muted);
const det=node(s,'检测与恢复\n异常报告、动作建议',473,486,300,110);
line(s,526,332,526,486,C.teal,2,true);text(s,'观测与上下文',316,390,190,40,25,C.muted);
line(s,720,486,720,332,C.teal,2,true);text(s,'诊断与建议',754,410,185,40,25,C.muted);
text(s,'关联记录',64,496,250,42,28,C.teal,true);text(s,'任务、观测、动作与结果',64,549,370,40,25,C.muted);
foot(s,'取舍：集中授权便于处理过期结果与接管，代价是额外校验开销');

s=slide(5,'本地部署与技术选择','沿用已验证环境，按兼容要求隔离依赖');
rect(s,64,195,1152,385,'#FFFFFF',C.line,1.5);text(s,'张茗博工作站',87,216,760,43,30,C.ink,true);
const browser=node(s,'浏览器原型\nHTML / JavaScript',94,302,292,114,{fill:'#F2F5F6',stroke:C.line,size:28});
const sim=node(s,'仿真与检测链\nIsaac Sim 4.5 / PyTorch',600,302,576,114,{size:29});
line(s,386,359,600,359,C.line,2);text(s,'待联调',430,313,130,36,25,C.orange,true);
text(s,'交互界面',104,453,275,40,26,C.muted);
text(s,'DexGarmentLab 资产与环境\nGAM＋脚本控制，本地观测与动作记录',620,451,548,84,27,C.ink);
foot(s,'选择依据：资产与控制通道已跑通，可直接验证检测和恢复');

s=slide(6,'持有阶段的视觉异常检测','复用 FIPER 观测分支，保持已有正常控制器');
const ds=[node(s,'RGB',64,191,150,78),node(s,'图像特征\nResNet18',294,191,230,78,{size:26}),node(s,'RND误差\n过去五帧',604,191,255,78,{size:26}),node(s,'阶段阈值\n正常 / 异常 / 未知',939,191,277,78,{size:25})];
for(let i=0;i<3;i++)connect(s,ds[i],ds[i+1]);
const events=(await fs.readFile(path.join(E,'B/pre-demo-events.jsonl'),'utf8')).trim().split('\n').map(JSON.parse);
const reports=events.filter(e=>e.kind==='OFFICIAL_DETECTION'&&e.report.generation===0&&e.observation.phase==='LEFT_SLEEVE_HOLD'&&['NORMAL','ANOMALY'].includes(e.report.status)).map(e=>e.report);
if(reports.length!==28||reports.filter(r=>r.status==='ANOMALY').length!==5)throw new Error('Unexpected source slice');
const round=x=>Number(x.toFixed(6));
s.charts.add('scatter',{position:{left:64,top:305,width:768,height:305},series:[
  {name:'RND score',xValues:reports.map(r=>round(r.observed_sim_s)),values:reports.map(r=>round(r.score)),line:{fill:C.teal,width:3},marker:{symbol:'none'},smooth:false},
  {name:'Threshold',xValues:reports.map(r=>round(r.observed_sim_s)),values:reports.map(r=>round(r.threshold)),line:{fill:C.orange,width:2},marker:{symbol:'none'},smooth:false}],
  scatterOptions:{style:'line'},hasLegend:true,legend:{position:'bottom',textStyle:{fontSize:20}},chartFill:'#FFFFFF',
  xAxis:{title:{text:'Simulation time (s)',textStyle:{fontSize:22}},textStyle:{fontSize:20},numberFormatCode:'0.0',min:5.8,max:7.3,majorUnit:0.3},yAxis:{title:{text:'Score',textStyle:{fontSize:22}},textStyle:{fontSize:20},numberFormatCode:'0.0',min:0.8,max:1.4,majorUnit:0.2}});
text(s,'B恢复前\n左袖持有阶段',901,328,303,85,29,C.ink,true);
text(s,'5份告警\n1次恢复请求',901,460,303,90,33,C.teal,true);
foot(s,'左右袖分别校准，未知输入不强判；偏离分数不等于失败概率');

s=slide(7,'恢复执行与复检','先确认执行条件，恢复后用新观测决定是否接续');
const a=node(s,'异常报告',64,231,200,100),b=node(s,'测量前检\n新帧确认',360,231,250,100),c=node(s,'固定重抓宏\n五步操作',706,231,222,100),d=node(s,'新观测\n持有复检',1024,231,192,100);
for(const [u,v]of [[a,b],[b,c],[c,d]])connect(s,u,v);
const help=node(s,'请求协助',493,496,255,90,{fill:'#FAEEE5',stroke:C.orange,color:C.orange,size:28});
const cont=node(s,'新代次基线\n接续折叠',1006,496,210,90,{size:27});
line(s,1149,331,1149,496,C.teal,2,true);text(s,'通过',1162,389,60,40,25,C.teal);
line(s,1063,331,1063,436,C.orange,2);line(s,621,436,1063,436,C.orange,2);line(s,621,436,621,496,C.orange,2,true);
text(s,'未通过',807,447,145,36,25,C.orange);
text(s,'重抓宏：释放、退让、重抓、闭手、抬升',64,179,1152,40,28,C.ink,true);
foot(s,'当前持有复检和限定接续使用仿真几何；必要证据缺失时阻止新派发并求助');

s=slide(8,'告警恢复实跑','B场景：告警触发重抓，复检后接续折叠',true);
photo(s,path.join(BUILD,'B-viewport-poster.png'),64,180,688,499.354839);
text(s,'B  告警恢复',856,192,360,46,33,'#89D8CB',true);
text(s,'实际重抓并接续完成',856,251,360,45,29,C.white);
text(s,'A  正常运行',856,354,360,45,29,C.white,true);
text(s,'0告警，流程完成',856,407,360,40,27,'#C5D6DE');
text(s,'C  缺少检测包',856,499,360,45,29,C.white,true);
text(s,'停止新派发并求助',856,550,360,40,27,'#C5D6DE');
text(s,'本组仿真记录回放',856,633,360,38,23,'#BBD6DB');

s=slide(9,'设计演进与后续验证');
text(s,'已采纳的记录细化',64,188,540,48,33,C.teal,true);
text(s,'校验失败可追溯',64,278,540,42,30,C.ink,true);
text(s,'区分启动、继续与归还的来源和原因',64,336,540,82,27,C.muted);
text(s,'报警与响应分开计时',64,456,540,42,30,C.ink,true);
text(s,'保留人工判断、报警和停止接受时刻',64,515,540,82,27,C.muted);
text(s,'下一步验证',737,188,479,48,33,C.teal,true);
text(s,'误报与异常覆盖\n最终叠衣质量\n界面与仿真联调',737,279,479,238,32,C.ink);
foot(s,'保留原产品要求，课堂反馈纳入最终设计修订');

s=slide(10,'领域对象与记录边界','备份：任务状态、控制权限和离线质量分别记录');
const task=node(s,'FoldingTask\n任务编号、状态、预算',465,197,350,126,{size:29});
const child=[['ControlSession','代次、权限、静止状态'],['Observation','来源、时间、图像引用'],['Dispatch','指令、代次、执行反馈'],['Evaluation','质量结果、自主性判定']];
line(s,640,323,640,376,C.teal,2);line(s,186,376,1094,376,C.teal,2);
for(let i=0;i<4;i++){const x=64+303*i;node(s,child[i].join('\n'),x,450,246,123,{size:25});line(s,x+123,376,x+123,450,C.teal,2);text(s,i===0?'1':'0..*',x+133,397,90,34,23,C.muted);}
foot(s,'任务冻结配置与模型版本，质量审核追加记录，回放不改变控制权限');
s.speakerNotes.text='Source: docs/design/models/zhang-system-models.md, interfaces.md and data-design.md. Editable simplified domain model, not a new wire schema. FoldingTask associates with one ControlSession, multiple Observations and Dispatches, and versioned offline Evaluation records. A terminal runtime outcome and stop evidence are distinct. Follow the full system model for additional fields and ownership. Current diagnostic macro/SDK mapping remains separate.';

s=slide(11,'三场景记录与数据边界','备份：开发案例支持流程可行性，统计效果另验');
table(s,[['场景','检测与控制','结束记录'],['A 正常','0告警，0恢复','流程完成\n区域2048/2048'],['B 提前开手','5份告警，1次宏恢复\n5项操作，61条底层指令','接续完成\n区域2002/2048'],['C 缺少检测包','未知，0恢复\n求助后新增派发0','请求协助']],64,190,1152,346,[235,540,377],26);
text(s,'正常数据：1条拟合、4条校准；当前版本无独立未见留出',64,567,1152,40,26,C.teal,true);
foot(s,'区域点数为开发代理，不替代正式叠衣质量或自主成功率');
s.speakerNotes.text='PR29–32 and docs/reviews/pr30-31-review.md. A normal trial is not a matched injected-fault no-recovery control. B includes 492 main RGB calls plus one preflight refresh, A465; all958 calls reproduced from shared RGB and frozen checkpoint with identical decision fields, score abs tolerance1e-5. normal-03 was used in previous development then reassigned to current calibration, not claimed as independent holdout. Each13-report post-macro/baseline sequence contains12 warmups and1HELD; 23 continuation windows overlap. C0new dispatch does not prove physical rest. Runtime32ms median/63ms max refers only to recorded internal call processing, not full system latency. No success-rate or causal-benefit claim.';

s=slide(12,'方法来源与本组适配','备份：复用成熟方法，聚焦系统接线与异常处理');
text(s,'DexGarmentLab',64,207,720,50,36,C.teal,true);
text(s,'NeurIPS 2025',924,215,292,40,27,C.muted,false,'right');
text(s,'提供衣物仿真环境与资产\n本组沿用已有GAM＋脚本正常流程，加入异常检测与恢复链',64,283,1152,105,29,C.ink);
line(s,64,421,1216,421,C.line,1.5);
text(s,'FIPER',64,463,720,50,36,C.teal,true);
text(s,'NeurIPS 2025',924,470,292,40,27,C.muted,false,'right');
text(s,'借鉴观测嵌入的RND异常检测\n本组适配固定视觉特征、阶段阈值和恢复前后复检',64,539,1152,86,29,C.ink);
s.speakerNotes.text='DexGarmentLab: Wang et al., DexGarmentLab: Dexterous Garment Manipulation Environment with Generalizable Policy, NeurIPS2025. Official source and project links in docs/research/source-register.md and annotated-references.md. FIPER: Failure Prediction at Runtime for Generative Robot Policies, NeurIPS2025, https://proceedings.nips.cc/paper_files/paper/2025/hash/0b7cb3b8cc44e652761245537027db44-Abstract-Conference.html . We adapt the observation branch, not full FIPER or original guarantee. Five-frame window, phase-conditioned thresholds, preflight and privileged geometry are project design choices described in ADR-MA-006/007. No novelty or new research result is claimed in this design presentation.';

for(let i=0;i<9;i++)p.slides.getItem(i).speakerNotes.text='【'+scripts[i][1]+'，预算'+scripts[i][2]+'秒】\n'+scripts[i][3]+'\n\n来源与说明：'+sources[i];
function applyFonts(t){const v=String(t);t.typeface='Times New Roman';t.set(v.split(/([\u2E80-\u9FFF\u3000-\u303F\uFF00-\uFFEF]+)/u).filter(Boolean).map(run=>({run,style:{typeface:/[\u2E80-\u9FFF\u3000-\u303F\uFF00-\uFFEF]/u.test(run)?'SimSun':'Times New Roman'}})));}
for(const sl of p.slides.items){for(const q of sl.shapes.items)if(String(q.text))applyFonts(q.text);for(const tb of sl.tables.items)for(let r=0;r<tb.rowCount;r++)for(let c=0;c<tb.columnCount;c++)applyFonts(tb.getCell(r,c).text);for(const chart of sl.charts.items)applyPresentationChartFont(chart,{fontFamily:'Times New Roman'});}
await (await PresentationFile.exportPptx(p)).save(path.join(BUILD,'candidate.pptx'));
await fs.writeFile(path.join(BUILD,'speaker-script.json'),JSON.stringify(scripts,null,2),'utf8');
await fs.writeFile(path.join(BUILD,'chart-source.json'),JSON.stringify({source:'B/pre-demo-events.jsonl',selection:'generation0 LEFT_SLEEVE_HOLD valid pre-macro reports',reports,displayDecimalPlaces:6},null,2),'utf8');
for(let i=0;i<p.slides.items.length;i++){
  const png=await p.export({slide:p.slides.getItem(i),format:'png',scale:1});await fs.writeFile(path.join(BUILD,'renders/slide-'+(i+1)+'.png'),new Uint8Array(await png.arrayBuffer()));console.log('Rendered '+(i+1)+'/12');
}
console.log(JSON.stringify({slides:12,mainSlides:9,scriptSeconds:scripts.reduce((t,s)=>t+s[2],0),candidate:path.join(BUILD,'candidate.pptx')}));

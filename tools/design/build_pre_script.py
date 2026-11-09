"""Update the Chinese speaking script to the reviewed concise deck, retaining source page setup."""
from pathlib import Path
import sys, json, re
from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

build=Path(sys.argv[1]); source=Path(sys.argv[2])
slides=json.loads((build/'speaker-script.json').read_text(encoding='utf8'))
assert len(slides)==9 and sum(s[2] for s in slides)==318
doc=Document(source)
for child in list(doc.element.body):
    if child.tag!=qn('w:sectPr'):doc.element.body.remove(child)
for style in doc.styles:
    if style.type in (1,2):
        style.font.name='Times New Roman';style.font.color.rgb=RGBColor(0,0,0)
        f=style.element.get_or_add_rPr().get_or_add_rFonts()
        for key,value in [('ascii','Times New Roman'),('hAnsi','Times New Roman'),('eastAsia','SimSun'),('cs','Times New Roman')]:f.set(qn('w:'+key),value)
    for b in list(style.element.findall('.//'+qn('w:pBdr'))):b.getparent().remove(b)
doc.styles['Normal'].font.size=Pt(12)
doc.styles['Normal'].paragraph_format.line_spacing=1.15
doc.styles['Normal'].paragraph_format.space_after=Pt(4)
doc.styles['Title'].font.size=Pt(20)
doc.styles['Heading 1'].font.size=Pt(14)
doc.styles['Heading 1'].paragraph_format.keep_with_next=True
doc.styles['Heading 1'].paragraph_format.space_before=Pt(10)
doc.styles['Heading 1'].paragraph_format.space_after=Pt(4)
doc.styles['Heading 2'].font.size=Pt(12)
doc.styles['Heading 2'].paragraph_format.keep_with_next=True
md=['# 自主纠错型机器人叠衣系统 中文演讲稿','']
doc.add_paragraph('自主纠错型机器人叠衣系统 中文演讲稿','Title')
def para(v):
    p=doc.add_paragraph(v);p.paragraph_format.keep_together=True;md.extend([v,''])
def head(v,level=1):doc.add_heading(v,level);md.extend(['#'*(level+1)+' '+v,''])
para('正文第1—9页，备份第10—12页。胡知鱼第1—3页78秒，张茗博第4—5页75秒，马祥珲第6—9页165秒。口播预算318秒，另留42秒切页交接；第8页视频28.95秒计入该页50秒，点击后同步讲解。实际用时须经全组排练核对。')
for i,(title,who,seconds,body) in enumerate(slides,1):
    head(f'第{i}页 {title}')
    p=doc.add_paragraph(f'{who}  预算{seconds}秒');p.paragraph_format.keep_with_next=True
    md.extend([f'讲解人：{who}　预算：{seconds}秒',''])
    para(body)
head('备份问答')
answers=[
('本组在现成平台上完成了什么','沿用已有GAM加脚本正常控制，加入阶段化视觉检测、恢复前检、固定重抓宏、宏后复检与限定接续。B已有一次告警驱动的完整开发实跑。系统权限、人工接管与记录已有设计和交互原型，完整产品联调另验。'),
('是否完整复现FIPER','只适配观测分支。原文还使用生成式动作样本的熵，当前GAM加脚本控制不能提供相应样本。本组采用固定ResNet18特征、RND误差、五帧窗口和左右袖阈值，不继承原文完整方法或统计保证。'),
('恢复后如何确认可以继续','宏后使用新鲜的仿真材料片与指尖几何建立持有窗口，再建立新代次基线，之后限定左袖接续。视觉报告按原值保留。每段13份报告含12次窗口预热和1份HELD，不能当13次独立通过；23次接续窗口也互相重叠。'),
('现在能否报告恢复成功率','目前是A正常、B告警恢复、C缺包求助三个开发案例，不是多试次效果比较。A与B不是同故障的配对对照。区域点数2048/2048和2002/2048是开发代理，不能替代正式质量或自主成功率。'),
('检测数据与图表如何核验','当前包用1条正常试次拟合、4条校准，原normal-03已转为校准，没有当前版本独立未见留出。第6页只画B恢复前同一左袖持有阶段的28份可判报告，横轴为仿真观测时间。完整A465次、B493次含一次刷新已从原始RGB和冻结权重独立重算，判定一致。'),
('界面和真实控制是否已接通','可点击五屏原型通过测试事件检查交互，尚未接入仿真控制。C求助后没有新派发，只证明该开发路径阻止继续派发，不能据此证明设备已物理停稳。完整产品协调器、持久化、停车与人工接管仍需联调。'),
]
for title,body in answers:head(title,2);para(body)
head('播放与交接')
para('视频为已有B记录的仿真视口裁剪，保留原28.95秒节奏与静帧停留，不额外加速。完整带诊断面板的原视频保留在来源材料中。播放失败时用第2页真实静帧和第11页记录表继续讲解。')
for section in doc.sections:
    for p in section.header.paragraphs:
        p.text=''
    for p in section.footer.paragraphs:
        p.text=''
    footer=section.footer.paragraphs[0];footer.alignment=2
    field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)
for p in doc.paragraphs:
    for run in p.runs:
        run.font.name='Times New Roman'
        f=run._element.get_or_add_rPr().get_or_add_rFonts()
        for key,value in [('ascii','Times New Roman'),('hAnsi','Times New Roman'),('eastAsia','SimSun'),('cs','Times New Roman')]:f.set(qn('w:'+key),value)
    for b in list(p._p.findall('.//'+qn('w:pBdr'))):b.getparent().remove(b)
out=build/'final';out.mkdir(exist_ok=True)
doc.save(out/'第三组_中文逐页演讲稿_实跑修订版.docx')
(out/'第三组_中文逐页演讲稿_实跑修订版.md').write_text('\n'.join(md),encoding='utf8')
print(json.dumps({'main_slides':9,'script_seconds':318,'chinese_characters_by_slide':[len(re.findall(r'[\u4e00-\u9fff]',s[3])) for s in slides],'backup_answers':len(answers)}))

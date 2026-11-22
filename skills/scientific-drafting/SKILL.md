---
name: scientific-drafting
description: Structure, draft, or substantially restructure scientific papers, reviews, grant proposals, and multi-section reports from evidence and research questions. Select genre guidance, map claims to primary sources, load scientific-prose up front to reduce rework, and coordinate bounded editorial or academic review. For standalone prose polishing, local wording edits, or caption refinement on an existing draft, use scientific-prose directly instead.
---

# 科研谋篇与起草

由一位主笔统筹论证结构与权威主稿，依据当前体裁与目标读者交付成文。前置挂载 [科研行文与润色](../scientific-prose/SKILL.md)，在落笔阶段直接落实个人表达规范。

## 体裁路由与定位

从当前请求、已有主稿及后续用户修正获取体裁、读者、核心问题、可用材料、交付范围与主稿位置；仅针对影响写作选择的缺项提问，先完成有确切依据的部分。探索讨论由 `research-ideation` 承接，定题后转入本流程；按当前任务只读取对应模块：

| 任务类型 | 适用模块 |
| --- | --- |
| 叙述性或批判性综述 | [综述综合](references/genres/narrative-review.md) |
| 命题议论文、课程 Essay 或观点评论 | [命题议论与评论](references/genres/argumentative-essay.md) |
| 系统综述、范围综述或 Meta 分析 | [证据综合](references/genres/evidence-synthesis.md) |
| 已完成工作的原始研究 | [原始研究](references/genres/original-research.md) |
| 研究计划、开题或基金申请书 | [申请书论证](references/genres/proposal.md) |
| 方法、模型或理论推导论文 | [方法与理论](references/genres/methods-and-theory.md) |
| 特定章节、图表、讲稿、审稿回复或双语改写 | [章节与载体](references/sections-and-formats.md)（叠加所属体裁） |

学位论文或复合报告按各章实际任务组合体裁模块，由主笔或全局编辑统一梳理跨章关联与总讨论衔接。

## 依据梳理与骨架搭建

若项目维护《决策与淘汰账本》（根目录 `DECISIONS.md` 或 Notion 顶部决策区），起草或重构前先读取已核实硬约束、已淘汰路线死因及导师反馈；未通过 L1 廉价证伪与方向拍板的早期设想，不提前扩写为完整 SOP 或重资产交付物（见 [现实边界、廉价证伪与决策账本](../research-ideation/references/falsification-and-ledger.md)）。

围绕决定论点的关键材料记录四项要素：来源位置、实际比较前提、观察发现及其成立条件、支撑的论证环节，并明确区分一手研究结果、原作者推断、本稿综合判断与拟议假说。

实质性起草或重构前，先明确各节论证任务、核心依据与相邻推进关系；短文可在上下文直接成稿。细节密度与关键条件保留遵循 [共用落位原则](../scientific-prose/SKILL.md#条件保留与细节落位)。修订旧稿前，梳理适用的用户更正、共享定义与核心前提；成稿后对照原稿与一手依据逐个核对研究对象、模型、比较条件与适用范围，具体流程见 [协作与改动传播](references/collaboration.md)。

## 触发检查与协作分工

| 改动场景 | 检查与处理重点 |
| --- | --- |
| 新篇起草或章节论证重构 | 明确体裁任务、证据落位与前后推进；成文后整体校验解释闭环 |
| 全文润色或降密改写 | 从读者理解视角通读修正同类问题，完整保留科学含义与限定边界 |
| 引入陌生术语、缩写或符号 | 在首现所需位置点明实体身份、具体所指及参照，保持基因、蛋白与指标命名精确 |
| 增删数据、改变核心主张或主要基线定义 | 全域追踪摘要、目标、正文推论与对应表图；达到条件时调用 `academic-reviewer` |
| 新增操作阈值、误差边界、退守判据或统计分配 | 按共用落位原则集中维护技术细节；决定论断成立或图表独立可读的条件就近保留 |
| 压缩文本或删并机制解释 | 核实比较条件、对照设计目的、测量参照与关键不确定性仍有清晰落点；压缩重排后必须通读最终导出稿，严禁删出无衔接碎段或砍空议论文立论路标 |
| 重排结构、调整图号或迁移载体 | 逐一核对正文提及与目标补图、方法或推导的一致性，方式见 [章节与载体](references/sections-and-formats.md) |
| 局部措辞调整或双语改写 | 通读必要邻文，保持观点、对比条件、数字、归属与不确定度一致 |
| 正式投稿或交付准备 | 运行 [lint_manuscript.py](scripts/lint_manuscript.py) 与 [check_internal_links.py](scripts/check_internal_links.py) 排查中圆点标题、残留内部标签、Markdown 数字引文乱序与多处同步刷括号；节选传 `--fragment`，TeX 引文另核编译产物，核验图文与实际渲染页面 |

语言、篇章推进与最终定稿由主笔统一维护，**默认不自动增配编辑子代理**。仅当用户明确要求编辑审校，或全文重构伴随密集独立文献对照确需分担时，才按 [协作与改动传播](references/collaboration.md) 增派至多一位只读编辑（不与 `academic-reviewer` 默认并行叠加）；正式科研交付物且涉实质科学判断时，按触发条件调用 [academic-reviewer](../academic-reviewer/SKILL.md) 完成一次独立学术审计。

## 整合、核查与交付

主笔核实意见并统一写入权威主稿，先处理共享前提，再局部润色；按共用落位原则减少重复与防御性补丁。学术审阅的意见分级与轮次上限只按 `academic-reviewer` 执行，不另开复核循环。主要缺陷修复、依赖部位回读与交付核验完成后即交付，简要说明实质修订、凭据不改的意见与剩余缺口。

日常讨论与局部判断直接在聊天中交付；需要正式落盘或排版交付时，读取 [主稿与交付](../scientific-prose/references/notion-tex-workflow.md) 维护唯一真值源。科研图件制作调用 `scientific-visualization`，书目校准与文献表导出调用对应 Zotero 技能。

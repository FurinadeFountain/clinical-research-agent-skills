# 附录：仓库目录、技能模块与静态检查脚本索引

本文档提供全仓文件结构、15 个技能模块内部参考库（`references/`）与静态门禁脚本（`scripts/`）的精确路径索引，便于开发者查阅或交由 Agent 在按需移植时快速定位目标文件。

---

## 一、顶层文件与宿主补充

| 路径 | 职责说明 |
| --- | --- |
| [`AGENTS.md`](../AGENTS.md) | 跨 Harness 共用的全局默认规则核心（Shared Core），定义先行判断、最小复现根因排障、防卡死边界、决策账本与廉价证伪门禁、一手证据定标、体裁路标路由、交付真值源与安全边界 |
| [`hosts/codex.md`](../hosts/codex.md) | Codex 环境下的子代理隔离、`worktree` 并行改码与独立审阅衔接补充示例 |
| [`hosts/antigravity-app.md`](../hosts/antigravity-app.md) | Antigravity 原生客户端环境下的模型继承、`swarm` 协作与 MCP 命令行兜底补充示例 |
| [`hosts/t3-antigravity.md`](../hosts/t3-antigravity.md) | T3 Code / Antigravity 环境下的统一 `delegate_task` 委派、跨家族能力互补与提供方对齐、后台命令防卡死及原子渲染防雷补充示例 |
| [`scripts/lint_agent_configs.py`](../scripts/lint_agent_configs.py) | 仓库自检门禁：校验全局指令字符预算上限、YAML Frontmatter、全仓相对链接完整性与脚本头可移植性 |
| [`.github/workflows/check.yml`](../.github/workflows/check.yml) | GitHub Actions 自动检查工作流：推送至 `main` 分支、提交 Pull Request 或手动触发时在云端运行 `make check` |
| [`docs/workflow-overview.html`](workflow-overview.html) | 技能拓扑与静态门禁架构图的瑞士国际主义排版网页源码（导出成品见 [`docs/assets/skill-architecture.png`](assets/skill-architecture.png)） |
| [`examples/manuscript-review-triage/`](../examples/manuscript-review-triage/README.md) | “主笔初稿 → 独立学术审阅三级分流 → 文稿静态门禁放行”脱敏直观样本与回归测试 |
| [`examples/experimental-unit/`](../examples/experimental-unit/README.md) | “视野行数 vs 实验动物独立单位”离线合成评测案例与复算基准代码 |
| [`README.en.md`](../README.en.md) / [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) | 精炼版英文仓库导览与子模块开源协议声明 |

---

## 二、全流程技能模块明细（`skills/`）

### 1. 问题立意与开放分歧校准

- **[`research-ideation`](../skills/research-ideation/SKILL.md)**：L0 现实约束与问题/平台双路由、L1 廉价证伪与“科学死罪 vs 可修毛病”分离、临床判别盲区切入及一页纸拍板闸门
  - [`references/falsification-and-ledger.md`](../skills/research-ideation/references/falsification-and-ledger.md)：Stage 0 现实约束三态表、问题/平台双路由、L1 廉价证伪门禁、L1 → L2 拍板闸门与项目级《决策与淘汰账本》（`DECISIONS.md`）
  - [`references/ideation-methods.md`](../skills/research-ideation/references/ideation-methods.md)：现象断口拆解、代表作认知边界合围与决定性判别实验设计方法
  - [`references/parallel-collaboration.md`](../skills/research-ideation/references/parallel-collaboration.md)：多模型能力互补分工、三段式最小闭环编排、一手出处回执核验与正式文档对外脱敏规则
  - [`references/evaluation.md`](../skills/research-ideation/references/evaluation.md)：技能维护、规则减法瘦身与五类匿名化历史失效原型回归评测规范
- **[`web-model-consultation`](../skills/web-model-consultation/SKILL.md)**：一手文献核查后仍存重大开放分歧时的跨模型对称质询与证据回溯规程

### 2. 生物医学证据路由、全文获取与单细胞组学

- **[`biomedical-source-router`](../skills/biomedical-source-router/SKILL.md)**：生物医学数据库查询前置路由、本地数据优先原则与数据外传安全边界
  - [`references/source-map.md`](../skills/biomedical-source-router/references/source-map.md)：文献、临床试验、组学、变异、化学、通路与结构数据库分类映射及许可限制
- **[`ncbi-pmc`](../skills/ncbi-pmc/SKILL.md)**：PMCID / PMID / DOI 元数据解析、撤稿核查与开放获取 PMC JATS XML 全文拉取（主脚本 [`scripts/ncbi_pmc.py`](../skills/ncbi-pmc/scripts/ncbi_pmc.py)）
- **[`ncbi-entrez`](../skills/ncbi-entrez/SKILL.md)**：NCBI E-Utilities（PubMed / Gene / Protein / Nucleotide / GEO）命令行检索封装（主脚本 [`scripts/ncbi_entrez.py`](../skills/ncbi-entrez/scripts/ncbi_entrez.py)）
- **[`scvi-tools`](../skills/scvi-tools/SKILL.md)**：单细胞 RNA-seq 概率生成模型（scVI 批次整合、scANVI 标签迁移与贝叶斯差异表达，Apache-2.0）
- **[`scgpt`](../skills/scgpt/SKILL.md)**：单细胞基础模型嵌入表征、零样本/微调注释与基因网络任务规程（Apache-2.0）

### 3. 唯一主笔起草与中英双语行文

- **[`scientific-drafting`](../skills/scientific-drafting/SKILL.md)**：唯一主笔统筹、体裁分流、依据映射与跨节改动同步
  - 体裁指南：[`original-research.md`](../skills/scientific-drafting/references/genres/original-research.md)（原始研究）、[`narrative-review.md`](../skills/scientific-drafting/references/genres/narrative-review.md)（叙述性综述）、[`evidence-synthesis.md`](../skills/scientific-drafting/references/genres/evidence-synthesis.md)（系统综述与证据综合）、[`methods-and-theory.md`](../skills/scientific-drafting/references/genres/methods-and-theory.md)（方法与理论）、[`proposal.md`](../skills/scientific-drafting/references/genres/proposal.md)（基金申请与阶段载体拆分）、[`argumentative-essay.md`](../skills/scientific-drafting/references/genres/argumentative-essay.md)（命题议论文与观点评论）
  - 协作与局部载体：[`collaboration.md`](../skills/scientific-drafting/references/collaboration.md)（默认单主笔、按需增配只读编辑与双向依赖回查）、[`sections-and-formats.md`](../skills/scientific-drafting/references/sections-and-formats.md)（特定章节、审稿回复与双语改写）、[`proposal-examples.md`](../skills/scientific-drafting/references/proposal-examples.md)（标书问题收窄节奏拆解）
  - 静态核查脚本：[`lint_manuscript.py`](../skills/scientific-drafting/scripts/lint_manuscript.py)、[`compare_cited_passages.py`](../skills/scientific-drafting/scripts/compare_cited_passages.py)、[`check_revision_coverage.py`](../skills/scientific-drafting/scripts/check_revision_coverage.py)、[`check_internal_links.py`](../skills/scientific-drafting/scripts/check_internal_links.py)
- **[`scientific-prose`](../skills/scientific-prose/SKILL.md)**：中英文科研表达校准、伞状词还原以及全流程共用的“条件保留与细节落位”原则
  - [`references/complete-research-explanations.md`](../skills/scientific-prose/references/complete-research-explanations.md)：常见研究解释缺环诊断表与正反改写范例库
  - [`references/notion-tex-workflow.md`](../skills/scientific-prose/references/notion-tex-workflow.md)：唯一权威源稿维护、批注回写与 LaTeX 排版交付规范
  - 辅助脚本：[`check_pdf_fonts.py`](../skills/scientific-prose/scripts/check_pdf_fonts.py)、[`extract_pdf_annotations.py`](../skills/scientific-prose/scripts/extract_pdf_annotations.py)、[`notion_browser_helpers.js`](../skills/scientific-prose/scripts/notion_browser_helpers.js)

### 4. 只读编辑审校与完稿独立学术审计

- **[`scientific-editorial-review`](../skills/scientific-editorial-review/SKILL.md)**：重排或压缩后的目标读者视角审校，排查前置概念倒置、指代断层与互为依托前提误删
- **[`academic-reviewer`](../skills/academic-reviewer/SKILL.md)**：正式交付物完稿节点的零历史只读学术审计，“1 轮全审 + 条件触发至多 1 轮局部复核”封顶与三级分流漏斗
  - [`references/audit-rubric.md`](../skills/academic-reviewer/references/audit-rubric.md)：原始证据与补图/勘误逆查、实证数据卫生基线、物理守恒与功能终点核验、独立实验单位及四级审计裁决标准

### 5. 科研制图、学术汇报与核验型题录管理

- **[`scientific-visualization`](../skills/scientific-visualization/SKILL.md)**：1:1 物理尺寸科研制图、双栈代码驱动与视觉审查流程
  - 设计与领域参考库：[`design-preferences.md`](../skills/scientific-visualization/references/design-preferences.md)、[`color-palettes.md`](../skills/scientific-visualization/references/color-palettes.md)、[`data-and-omics-panels.md`](../skills/scientific-visualization/references/data-and-omics-panels.md)、[`advanced-chart-archetypes.md`](../skills/scientific-visualization/references/advanced-chart-archetypes.md)、[`spatial-mechanics.md`](../skills/scientific-visualization/references/spatial-mechanics.md)、[`schematics-and-assembly.md`](../skills/scientific-visualization/references/schematics-and-assembly.md)、[`plot-templates.md`](../skills/scientific-visualization/references/plot-templates.md)、[`figure-review.md`](../skills/scientific-visualization/references/figure-review.md)、[`evaluation.md`](../skills/scientific-visualization/references/evaluation.md)
  - 静态门禁脚本：[`scripts/lint_figure.py`](../skills/scientific-visualization/scripts/lint_figure.py)
- **[`presentation-workflow`](../skills/presentation-workflow/SKILL.md)**：学术幻灯片叙事规划、母版继承、原生可编辑对象保真与秒级结构自检快速交付（含 [`story-and-scope.md`](../skills/presentation-workflow/references/story-and-scope.md)、[`template-and-native.md`](../skills/presentation-workflow/references/template-and-native.md)、[`collaboration.md`](../skills/presentation-workflow/references/collaboration.md)、[`checks.md`](../skills/presentation-workflow/references/checks.md)）
- **[`zotero`](../skills/zotero/SKILL.md)**：零第三方依赖操作本地 Zotero Desktop HTTP 接口（主脚本 [`scripts/zotero.py`](../skills/zotero/scripts/zotero.py)，路由表 [`references/local-api-routes.md`](../skills/zotero/references/local-api-routes.md)）
- **[`zotero-verified-bibliography`](../skills/zotero-verified-bibliography/SKILL.md)**：分层核验型题录管理（常规入库 API 轻量核对 + 投稿定稿全字段回读门禁）与按首引顺序导出参考文献表（规范见 [`references/manifest.md`](../skills/zotero-verified-bibliography/references/manifest.md)，门禁脚本 [`scripts/bibliography_gate.py`](../skills/zotero-verified-bibliography/scripts/bibliography_gate.py)）

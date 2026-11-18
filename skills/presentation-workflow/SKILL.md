---
name: presentation-workflow
description: Create, edit, review or finalize slide-deck artifacts while preserving required templates and native editable objects. Keep local slide edits scoped. Exclude deck explanation, script-only wording and standalone scientific figures.
---

# 幻灯片制作与交付

由一位主代理统筹权威幻灯片源，将叙事推进、模板继承、原生可编辑对象保真与最终交付对齐；尊重用户指定载体、模板、来源与既有工具链。

## 先选任务范围

读取当前请求、现有文稿、模板文件与最新更正，明确汇报受众、语言、时长/页数约束、主讲与备答切分、交付路径及必须保留的对象；仅针对改变制作决策的缺项提问。

| 任务类型 | 执行范围与路由 |
| --- | --- |
| 局部改字、微调对象位置或样式 | 主代理读取目标对象及必要邻页直接修改，仅核对 [核验表](references/checks.md) 受影响条目并保留未改设计 |
| 新建全套、跨页重构或更换模板 | 加载 [讲述与范围](references/story-and-scope.md) 与 [模板与原生对象](references/template-and-native.md)，按 [协作规范](references/collaboration.md) 配一位只读演示审阅者核对全套产出 |
| 单页新增或有限章节修订 | 主代理完成制作与核查；证据复杂或负担独立时增配一位审阅者 |
| 审阅既有 PPT 或排查兼容性故障 | 当前代理以只读方式检查实际文件、渲染图像及必要来源，清晰列出缺陷与未核范围 |
| 格式转换、保存或播放故障修复 | 核查对象保真、页面呈现及播放状态，并复用既有内容审阅 |
| 解读幻灯片内容、润色讲稿或制作独立科学图 | 转交对应说明/行文（`scientific-prose`）或制图（`scientific-visualization`）流程 |

涉单位、实验对比、核心结论或跨页叙事调整的局部修订按实质变更复核前后依赖。新建中文或双语学术幻灯片未指定模板时，优先选用用户本地配置的机构学术 Beamer 模板技能。

## 制作与核验衔接

1. **前置明确每页任务与继承对象**：新建或重构先梳理页面推进关系；套用模板时提前读取真实母版、版式占位符与原生组件；局部调整仅读取关联对象。
2. **制作中先审代表页**：优先跑通关键比较页或复杂机理页的清晰度、模板贴合度与可编辑性，再扩展同构页面。
3. **导出后逐项核验实物**：参照 [逐项核验表](references/checks.md) 记录适用项目的状态（已核 / 待修 / 未核 / 不适用）与实际依据；新稿审看全部页面，小改比较受影响页面并排除意外波及，同时依 [模板与原生对象](references/template-and-native.md) 核验字体、图表工作簿及连接线几何。
4. **统一回写并闭环依赖**：主代理整合意见写回权威源稿，同步讲稿、备注及交叉页码，按要求交付原生文件及目标格式（如 PDF）。

## 完成与交付

原生 PowerPoint 交付需在目标应用中实际执行打开、保存、关闭与重开，确认无修复弹窗与对象退化；当前环境无法访问原生桌面应用时，完成所有可用结构及渲染核查并如实标明应用兼容性“未核”。存在音视频媒体的页面需分别核实资源嵌入/链接、控件进尺及实际声画效果。

最终交付已保存的权威文件及指定导出版本，简明告知适用核查范围与遗留待核事项。科研正文起草与全面审计沿用 `scientific-drafting` 与 `academic-reviewer`；维护本技能自身评测时阅读 [行为测试](references/evaluation.md)。

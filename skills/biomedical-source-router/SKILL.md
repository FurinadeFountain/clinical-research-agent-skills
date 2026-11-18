---
name: biomedical-source-router
description: Choose and use biomedical, clinical, omics, chemistry, genomics, literature, and structural-biology data sources or connectors safely. Use before database lookups, when deciding between PubMed/PMC/ClinicalTrials/GEO/CELLxGENE/ArrayExpress/Ensembl/UniProt/HPA/Reactome/STRING/Zotero, or when source licensing/data-egress risks matter.
---

# 生物医学数据源路由

## 核心原则

直接检索掌握事实的权威来源。当本地文件、官方数据库、连接器或原始数据源可查询时，禁止凭模型记忆回答数据库问题。

## 工作流程

1. **明确检索实体与事实类型。**
   判断用户查询的对象属于文献条目、全文、临床试验、基因、变异、蛋白、通路、药物、化合物、数据集、蛋白结构、序列、表达谱还是文献题录记录。
2. **优先核查本地真实资料。**
   若用户指定了本地仓库、笔记、数据集、PDF、Zotero 文库、输出文件或日志，先直接核查本地资料再执行外部检索。
3. **按能力路由至已连接来源、专用技能或官方 API。**
   先使用当前宿主已连接、能返回所需字段或全文的工具；用户指定路径优先。连接器能力不足时再用下列本地脚本/API。不为同一查询重复调用插件版与本地版，也不只因名称相似同时加载两套技能。
   - **PubMed / Gene / Protein / Nucleotide / GEO (`db=gds`)**：调用 `ncbi-entrez`。
   - **开放获取全文 JATS XML (PMCID / PMID / DOI)**：调用 `ncbi-pmc`（设置 `"fetch_xml": true`；只在 `available` 时读取 XML。`unknown` 表示请求/响应失败，`not_found` 仅表示所查端点未找到，均不能自行推断付费墙；确认无可用全文时再请用户提供 PDF）。
   - **本地参考文献库与 `.bib` 书目**：使用 `zotero` 与 `zotero-verified-bibliography`。
   - **其他生物医学与临床数据源（ClinicalTrials.gov、CELLxGENE、BioStudies/ArrayExpress、Ensembl、UniProt、HPA、Reactome、STRING、ChEMBL、PubChem、OpenAlex、Crossref、bioRxiv、PDB）**：优先使用已连接的对应专用工具；能力不足时通过精简、指定返回字段的 Python/`curl` 请求调用官方 REST API（详见 [references/source-map.md](references/source-map.md)）。
4. **遵守许可协议与数据外传边界。**
   若查询需要将未发表序列、化合物、患者衍生数据或专有结果发送至第三方服务，先征得用户同意。
5. **保留来源溯源并限定解释范围。**
   记录数据库名称、检索式、标识符、检索日期、条目数量以及返回的登录号/PMID/PMCID/DOI/NCT/UniProt ID。

## 参考资料

数据源分类路由与存在许可或访问限制的资源详见 [references/source-map.md](references/source-map.md)。

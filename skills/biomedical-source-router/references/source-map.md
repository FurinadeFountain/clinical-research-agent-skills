# 生物医学数据源映射

## 文献与预印本

- **PubMed / PMC**：生物医学期刊论文、PMID/PMCID、摘要、MeSH 主题词与发表元数据。
- **Crossref**：DOI 元数据与解析。
- **OpenAlex**：学术发现、引文图谱、作者与期刊/会议载体信息。
- **bioRxiv / medRxiv**：预印本库；引用时须标注“预印本”并核查是否已正式发表。

## 临床试验与监管审批

- **ClinicalTrials.gov**：NCT 试验记录、状态、分期、分组、终点、申办方与入排标准。
- **FDA / openFDA / Drugs@FDA**：药品说明书、获批记录、安全性标签与监管文件。
- **指南与专业学会**：现行临床诊疗推荐；须核对发布日期与版本。

## 组学与公共数据仓

- **GEO / SRA / ArrayExpress**：表达谱数据集、样本元数据与登录号层级检索。
- **PRIDE / ProteomeXchange**：蛋白质组学项目与蛋白证据。
- **MetaboLights / MGnify**：代谢组学与微生物组研究数据。

## 基因、变异与蛋白质

- **NCBI Gene / Ensembl / BioMart / MyGene**：基因标识符与跨库映射。
- **ClinVar / gnomAD / dbSNP / GWAS Catalog / eQTL Catalogue**：遗传变异与人群遗传学信息。
- **UniProt / InterPro / Pfam / QuickGO**：蛋白注释、结构域与 GO 功能条目。

## 化学与药物

- **PubChem**：化合物信息、CID、理化性质与安全性摘要。
- **ChEMBL**：作用靶点、生物活性数据、作用机制与药物研发阶段。
- **BindingDB**：结合亲和力测定数据；须核对测定体系上下文与单位。
- **ChEBI / Rhea**：化学本体与生化反应参考库。

## 通路与分子互作

- **Reactome**：人工校正的信号通路与通路映射。
- **STRING / IntAct / ComplexPortal**：蛋白互作网络；将数据库评分视为互作线索，需结合实验依据判断直接作用机制。

## 结构与预测模型

- **RCSB PDB / EMDB**：实验解析结构与冷冻电镜密度图条目。
- **AlphaFold DB / 结构预测输出**：预测结构模型；须检查置信度指标，单独结构预测结果仅作构象参考，不足以推论结合亲和力或生物学功能。
- **ColabFold / MSA 服务与结构预测 API**：在线预测可能向第三方服务器上传序列。

## 存在许可或访问限制的资源

- **KEGG REST**：区分学术与商业使用限制。
- **CADD**：多数场景限非商业用途。
- **PanglaoDB**：自动化抓取与再分发的许可边界尚不明确。
- **部分模型权重**：需签署使用协议或经身份认证后下载。
- **公共 MSA 或预测服务器**：避免上传未发表序列。

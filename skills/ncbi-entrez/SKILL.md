---
name: ncbi-entrez
description: Submit compact NCBI Entrez E-Utilities requests for PubMed, Gene, Protein, Nucleotide, PMC metadata, and GEO metadata workflows. Use when a user wants concise Entrez search, fetch, summary, or link results; save raw JSON or XML only on request.
---

# NCBI Entrez E-Utilities 检索接口

通过 Python 标准库（零第三方依赖）调用官方 NCBI Entrez E-Utilities（`esearch`、`esummary`、`efetch`、`elink`、`einfo`），完成 PubMed 文献、Gene、Protein、Nucleotide 及 GEO 数据集（`db=gds`，详见 [references/geo.md](references/geo.md)）的精简元数据查询。

## 使用边界与证据规范

- **精确限定检索字段与返回条数**：常规 `esearch` / `esummary` 调用建议设置 `retmax=10`、`max_items=10`，避免无过滤的全量倾倒挤占上下文。
- **全文阅读分流至 `ncbi-pmc`**：当需要阅读开放获取论文的实验方法、对照组或图注读数时，转交 `ncbi-pmc` 拉取 JATS XML 全文，避免仅依据 PubMed 摘要推演细节结论。
- **真实记录检索状态**：返回空列表或请求报错时如实说明检索式与返回状态，禁止凭记忆补齐 `PMID`、样本量或基因登录号；高频调用时可在环境变量中配置 `NCBI_EMAIL` 与 `NCBI_API_KEY`。

## 输入与调用方式

脚本从标准输入（`stdin`）读取单个 JSON 对象：
- 必填字段：`endpoint`（限 `esearch`、`esummary`、`efetch`、`elink`、`einfo` 之一）
- 可选字段：`params`（字典，透传 NCBI 查询参数如 `db`、`term`、`id`、`retmode`、`retmax`）、`max_items`（默认 `10`）、`timeout_sec`（默认 `15`）、`save_raw`、`raw_output_path`

```sh
echo '{"endpoint":"esearch","params":{"db":"pubmed","term":"chronic kidney disease[MeSH] AND endothelial dysfunction","retmode":"json","retmax":5},"max_items":5}' \
  | python3 skills/ncbi-entrez/scripts/ncbi_entrez.py
```

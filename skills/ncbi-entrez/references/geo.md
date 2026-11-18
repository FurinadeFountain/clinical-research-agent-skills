# NCBI GEO (Gene Expression Omnibus) 检索说明

在 `ncbi-entrez` 中检索转录组、表观组或单细胞测序公开数据集元数据时，使用 `db="gds"`（GEO DataSets）：

1. **按疾病、物种与数据模态检索 Series (`GSE`)**：
   - 在 `term` 中组合关键词、物种 `[Organism]` 与条目类型 `"gse"[Entry Type]`，例如：
     ```json
     {
       "endpoint": "esearch",
       "params": {
         "db": "gds",
         "term": "(\"liver fibrosis\" OR \"nonalcoholic steatohepatitis\") AND \"Homo sapiens\"[Organism] AND \"gse\"[Entry Type]",
         "retmode": "json",
         "retmax": 10
       },
       "max_items": 10
     }
     ```
2. **获取 GSE 样本规模、测序平台与关联 PMID**：
   - 将 `esearch` 返回的内部数字 UID 传入 `esummary`（`db="gds"`, `retmode="json"`），核对返回的 `Accession`（如 `GSE...`）、`n_samples`、`GPL` 平台编号、`PubMedIds` 与研究摘要。
   - 注意区分数据集 `n_samples`（可能包含同一供体多部位、多时间点或技术重复文库）与独立患者/供体生物学样本数，进入重分析前须核查 `Series Matrix` 或样本 `characteristics_ch1` 元数据。

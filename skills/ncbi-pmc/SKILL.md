---
name: ncbi-pmc
description: Resolve PMCID, PMID, or DOI to PubMed Central (PMC) metadata and optionally retrieve free full-text JATS XML for direct reading. Use for article license/retraction checks or full-text XML verification when connected tools do not provide it; distinguish unavailable resources from failed requests.
---

# NCBI PubMed Central (PMC) 全文与元数据核查

通过 Python 标准库（零第三方依赖）解析 `PMCID`、`PMID` 或 `DOI`，查询公共 PMC Open Access 元数据（许可协议、撤稿或勘误状态），并按需拉取开放获取 **JATS XML 全文**供主会话长上下文直读。

## 使用边界与证据规范

- **优先核对全文方法与对照**：对支撑核心论断的代表性原始研究，设置 `"fetch_xml": true` 拉取 JATS XML 全文，直接核对样本流转分母、对照组设置目的、统计模型与图注读数，避免仅凭摘要概括下结论。
- **严格区分“端点未找到”与“请求失败”**：
  - `fulltext_xml.status == "available"`（`free_xml_available: true`）：已通过 `<article>` 根节点、`PMCID` 身份一致性及非空 `<body>` 校验并保存全文 XML；
  - `fulltext_xml.status == "not_found"`（`free_xml_available: false`）：所查公开端点均返回 `404/410`，仅代表当前公开 XML 端点未收录，不能据此断言论文存在付费墙；
  - `fulltext_xml.status == "unknown"`（`free_xml_available: null`）：网络超时、限流（`429/5xx`）或返回了非目标文章/网关错误页，须如实披露未核状态，确认无可用开放全文后再请用户提供 PDF。
- **配置礼貌请求参数**：高频调用 NCBI 接口时建议在环境变量中设置 `NCBI_EMAIL` 与 `NCBI_API_KEY`。

## 输入与调用方式

脚本从标准输入（`stdin`）读取单个 JSON 对象：
- 必填字段：`params.id`（支持 `PMC1234567`、`PMC1234567.1`、纯数字 `PMID` 或 `10.xxxx/...` 格式 `DOI`）
- 可选字段：`params.retmax`（默认 `5`）、`max_items`（默认 `5`）、`timeout_sec`（默认 `15`）、`fetch_xml`（布尔值）、`xml_output_path`、`save_raw`、`raw_output_path`

```sh
echo '{"params":{"id":"PMC3257301"},"fetch_xml":true,"xml_output_path":"/tmp/PMC3257301.xml"}' \
  | python3 skills/ncbi-pmc/scripts/ncbi_pmc.py
```

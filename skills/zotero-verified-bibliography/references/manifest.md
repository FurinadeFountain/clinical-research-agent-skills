# 核验清单与只读门禁脚本

仅使用 Python 3 标准库即可运行以下门禁校验或导出命令：

```sh
python3 scripts/bibliography_gate.py manifest.json --out /absolute/new-run-directory --check-only
python3 scripts/bibliography_gate.py manifest.json --out /absolute/new-export-directory
```

进行离线写入回读对比时，可追加 `--actual readback.json --check-only`。其中 `readback.json` 须是由 Zotero API 条目对象组成的 JSON 数组，每项需包含 `library`、`key` 与 `data` 字段。离线导出模式额外要求每条记录自带 `bib` 字段，且清单中提供与目标样式及语言相符的 `formatted_with` 声明；正式产出参考文献列表时优先采用在线实时导出。输出目录在运行前必须尚不存在，以防运行失败后目录中仍残留旧版通过结果混淆判断。

清单文件示例（仅作结构示范，实际使用时须全部替换为经来源核实的真实数据）：

```json
{
  "library": {"type": "user", "id": 12345},
  "style": "vancouver",
  "locale": "en-US",
  "numbering": "citation-order",
  "manuscript": {"path": "manuscript-snapshot.md", "sha256": "actual-sha256"},
  "citation_order": ["ref-A", "ref-A", "ref-B"],
  "records": [
    {
      "ref": "ref-A",
      "key": "ABCDEFGH",
      "expected": {
        "itemType": "journalArticle",
        "title": "Actual title",
        "creators": [{"creatorType": "author", "firstName": "Jane", "lastName": "Smith"}],
        "date": "2026-10-07",
        "DOI": "10.example/actual",
        "publicationTitle": "Actual journal",
        "volume": "",
        "issue": "",
        "pages": ""
      },
      "allowed_missing": {
        "volume": "Publisher lists this as online-first, not yet assigned.",
        "issue": "Publisher lists this as online-first, not yet assigned.",
        "pages": "Publisher has not assigned pages or an article number."
      },
      "evidence": [{"source": "https://publisher.example/article", "fields": ["itemType", "title", "creators", "date", "DOI", "publicationTitle", "volume", "issue", "pages"]}],
      "required_collections": ["COLLKEY1"]
    }
  ]
}
```

实际使用时应补齐示例中的 `ref-B` 等全部记录。`citation_order` 按从文稿中提取并核对后的实际出现次序完整列出每次引用；按首次出现顺序去重后的序列必须与 `records` 顺序完全一致。文件哈希（`sha256`）只负责绑定特定手稿快照版本，不能自行证明引文提取过程零遗漏。若仅在入库阶段单独校验题录而搭配 `--check-only`，可省略 `manuscript`、`citation_order`、style、locale 与 numbering 字段。

门禁脚本要求 `records` 中至少给出 `itemType`、`title`、`creators` 与 `date` 的预期值；若为期刊论文（`journalArticle`），还必须提供刊名、卷号（`volume`）、期号（`issue`）与页码（`pages`）预期。所有提交写入或修正的适用字段及标识符均须纳入预期；某项标识符经核实确无分配时，用空字符串显式声明预期并配合 `allowed_missing` 给出具体理由。每个预期字段都必须对应 `evidence` 中的来源覆盖；`evidence` 条目应当指明实际完成字段核查的权威网页或记录，仅记录检索时发现的 URL 列表不算核验。其他条目类型的特定必选字段由调用方按需补齐。

`required_collections` 与 `required_tags` 执行子集包含校验，从而在不干扰既有其他分类与标签的前提下确认目标归属写入成功；面对授权删减旧分类的重组任务，本脚本不负责验证删除边界，须另行比对操作前后的完整集合清单。脚本全程绝不接触认证密钥，也不会向 Zotero 发起写请求。`--api-base` 默认指向本地 Zotero 服务且仅放行回环地址（loopback HTTP）；可选字段 `library.server_id` 用于把读取严格绑定到指定 Zotero 实例。

进程退出码约定：`0` 代表指定校验全部通过；`2` 代表存在字段偏差或清单预期值不合法/不完整，具体失败明细写入输出目录的 `verification.json`。门禁返回 `0` 表示在既定字段规范化规则下预期值与数据库回读一致，而不构成本体科学结论验证。在线导出同时完整保留原始记录快照、机器可读的引文映射表以及当前使用的手稿/样式配置。

字段规范化比对会严格保留人名与题名大小写、作者排列顺序、重音/变音符号与所有数字；对 Unicode 字符组合形式、空白字符及页码连接号（hyphen/en-dash）样式差异予以包容，并对 DOI 的 URL 前缀与字母大小写做统一归一化。许多看似无害的题名大小写出入会被脚本刻意标出交由人工复核，防止在自动放行中漏过化学符号、基因名或单位符号的大小写变化。导出模式下要求单条文献序号标识明确可辨；遇到脚本无法可靠识别的新奇 CSL 版式会主动终止导出，避免误生成重复编号的参考文献列表。

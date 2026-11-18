# Third-Party Notices

Unless otherwise noted below, original configuration templates, skill guides, deterministic linter scripts, architecture diagrams, and synthetic examples in this repository are licensed under the [MIT License](LICENSE) (`Copyright (c) 2026 FurinadeFountain`).

## 1. Apache-2.0 Licensed Skill Adaptations

The following two single-cell analysis skill directories are adapted from upstream Apache-2.0 licensed scientific skill templates (retaining their `license: Apache-2.0` frontmatter declarations) and are distributed under the terms of the Apache License, Version 2.0, bundled in full at [LICENSES/Apache-2.0.txt](LICENSES/Apache-2.0.txt):

- `skills/scvi-tools/` (`SKILL.md` and `kernel.py` — modified to remove proprietary cloud-runner references, add local CPU/GPU execution guidance, and include `anndata` 0.11+ Arrow-string H5AD serialization helpers)
- `skills/scgpt/` (`SKILL.md` — modified to remove proprietary cloud-runner references and document local weight caching and AnnData embedding workflows)

## 2. MIT Licensed Skill Adaptation (`skills/zotero/`)

`skills/zotero/` (`SKILL.md`, `references/local-api-routes.md`, and `scripts/zotero.py`) is adapted from the MIT-licensed OpenAI Zotero plugin skill (`https://github.com/openai/plugins`, `Copyright (c) OpenAI`), modified to update Zotero 7+/10+ Local API read/write verification notes and cross-platform process handling:

```text
MIT License
Copyright (c) OpenAI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 3. External Databases and Upstream Software Packages

External biomedical APIs and software packages referenced in skill documentation (including NCBI Entrez / PubMed Central, Europe PMC, Zotero Desktop, Scanpy, scvi-tools, scGPT, Matplotlib, and R/ggplot2) remain governed by their respective upstream terms of service and open-source licenses.

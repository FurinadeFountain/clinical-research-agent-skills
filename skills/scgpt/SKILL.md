---
name: scgpt
description: >
  Embed and annotate single-cell expression data with scGPT, a foundation model
  for single-cell biology. Use this skill when:
  (1) Producing cell embeddings from an AnnData for clustering/integration,
  (2) Zero-shot or fine-tuned cell-type annotation,
  (3) Gene-level representation for perturbation/GRN tasks.

  For probabilistic single-cell models (scVI etc.), use the scvi-tools
  library.
license: Apache-2.0
metadata:
  category: biomodels
  requirements: [gpu]
  display-name: scGPT
  third_party:
    - kind: weights
      name: scGPT
      provider: Wang Lab (University of Toronto)
      info_url: https://github.com/bowang-lab/scGPT
---

# scGPT — Single-Cell Foundation Model

## Prerequisites

| Requirement | Minimum | Recommended |
| ----------- | ------- | ----------- |
| Python      | 3.10+   | 3.11        |
| CUDA        | 12.1+   | 12.4+       |
| GPU VRAM    | 16 GB   | 24 GB+      |

## How to run

### Loading the vocabulary and checkpoint

scGPT checkpoints are **raw directories** (`args.json`, `best_model.pt`,
`vocab.json`) — not Hugging Face hub repos. Point at the directory, not an HF
repo id.

```python
from scgpt.tokenizer.gene_tokenizer import GeneVocab
gv = GeneVocab.from_file("/path/to/scgpt-human/vocab.json")
print(len(gv))   # 60697 for the released human checkpoint
```

### Embedding an AnnData

```python
import anndata as ad
from scgpt.tasks import embed_data

adata = ad.read_h5ad("dataset.h5ad")        # var must contain a gene-name column
emb = embed_data(
    adata,
    model_dir="/path/to/scgpt-human",
    gene_col="feature_name",
    use_fast_transformer=False,             # see Gotchas
)
# emb is an AnnData with .obsm["X_scGPT"]
```

## Output format

`embed_data` returns an `AnnData` whose `.obsm["X_scGPT"]` is the per-cell
embedding (`n_cells × emb_dim`, 512 by default). Downstream: feed to
`scanpy.pp.neighbors` / `scanpy.tl.umap`.


## Compute & checkpoint setup

- Needs CUDA GPU (`>=16–24 GB` VRAM depending on batch/dataset size) and a downloaded checkpoint directory containing `args.json`, `best_model.pt`, and `vocab.json`.
- Pass that local directory path to `model_dir=`; if `flash_attn` is unavailable in the active Python environment, set `use_fast_transformer=False`.


## Gotchas

- **`use_fast_transformer` default is `True`** but resolves to a FlashAttention
  path that may not import in every env. Pass `use_fast_transformer=False`
  unless you've confirmed `flash_attn` loads cleanly.
- The package historically depended on `torchtext.vocab.Vocab`; in
  environments without torchtext a pure-Python shim provides `Vocab` —
  functionally identical for `GeneVocab`, but if you hit
  `AttributeError: 'Vocab' object has no attribute …`, you're on a stale shim.
- Gene names must match the vocab; unmatched genes are dropped. Set
  `gene_col` to the column in `adata.var` that holds symbols.

## Troubleshooting

| Symptom                                           | Fix                                              |
| ------------------------------------------------- | ------------------------------------------------ |
| `flash_attn is not installed` warning at import   | Harmless; pass `use_fast_transformer=False`      |
| `'Vocab' object has no attribute 'vocab'`         | Env has an old torchtext shim — update the env   |
| Nearly all genes dropped                          | Wrong `gene_col`; check `adata.var.columns`      |

---

**Next**: cluster/annotate the embedding with the scanpy library
(`sc.pp.neighbors` → `sc.tl.leiden` / `sc.tl.umap`), or compare to an
scvi-tools latent space on the same data.

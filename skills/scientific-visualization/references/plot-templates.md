# Python 与 R 1:1 出版级绘图配置模板及本地解释器入口

绘制统计数据图、生理波形或多组学面板时直接复用以下预设，确保物理尺寸 `1:1`、Arial 字体嵌入（`pdf.fonttype = 42`、`svg.fonttype = 'none'`）及洁净坐标轴一致。

## 1. Python（Matplotlib / Seaborn / Marsilea / pyCirclize）1:1 论文印刷预设

```python
import matplotlib as mpl

MM = 1 / 25.4  # e.g., figsize=(174 * MM, 110 * MM) for manuscript double-column

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica"],
    "mathtext.fontset": "custom",
    "mathtext.rm": "Arial",
    "mathtext.it": "Arial:italic",
    "mathtext.bf": "Arial:bold",
    "font.size": 6.5,
    "axes.labelsize": 7.0,
    "axes.titlesize": 6.5,
    "xtick.labelsize": 6.0,
    "ytick.labelsize": 6.0,
    "legend.fontsize": 6.0,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.major.size": 2.5,
    "ytick.major.size": 2.5,
    "lines.linewidth": 1.0,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": False,
    "legend.frameon": False,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
    "savefig.dpi": 600,
})
```

## 2. R（ggplot2 / patchwork / ggdist / ComplexHeatmap / circlize）1:1 论文印刷预设

```r
library(ggplot2)
PT_TO_MM <- 25.4 / 72.27  # geom_text()/annotate() 与 linewidth 按 mm 计，需由此换算

theme_pub_1to1 <- function(base_size = 6.5, base_family = "Arial") {
  lw_axis <- 0.6 * PT_TO_MM
  theme_classic(base_size = base_size, base_family = base_family) +
    theme(
      text = element_text(family = base_family, face = "plain", color = "#1E293B", size = base_size),
      axis.title = element_text(family = base_family, face = "plain", color = "#1E293B", size = 7.0),
      axis.text = element_text(family = base_family, face = "plain", color = "#1E293B", size = 6.0),
      axis.line = element_line(color = "#222222", linewidth = lw_axis),
      axis.ticks = element_line(color = "#222222", linewidth = lw_axis),
      axis.ticks.length = unit(2.5, "pt"),
      legend.background = element_blank(),
      legend.key = element_blank(),
      legend.title = element_text(family = base_family, face = "plain", size = 6.0),
      legend.text = element_text(family = base_family, face = "plain", size = 6.0),
      legend.key.size = unit(3.2, "mm"),
      strip.background = element_blank(),
      strip.text = element_text(family = base_family, face = "plain", color = "#1E293B", size = 6.5),
      plot.tag = element_text(family = base_family, face = "bold", color = "#111827", size = 8.0),
      plot.title = element_blank(),
      plot.subtitle = element_blank(),
      panel.grid = element_blank(),
      plot.margin = margin(3, 3, 2, 2, "mm")
    )
}

pdf_device_pub <- function(file, width, height, ...) {
  if (identical(Sys.info()[["sysname"]], "Darwin")) {
    grDevices::quartz(file = file, type = "pdf", width = width, height = height, family = "Arial")
  } else {
    grDevices::cairo_pdf(file = file, type = "pdf", width = width, height = height, family = "Arial")
  }
}
# 示例导出：ggsave("fig.pdf", p, width = 174, height = 80, units = "mm", device = pdf_device_pub)
# SVG 导出：svglite::svglite("fig.svg", width = 174 / 25.4, height = 80 / 25.4, system_fonts = list(sans = "Arial"))
```

## 3. 本地可用科学绘图解释器入口

若在远端服务器或项目独立虚拟环境运行，改用对应已装包的活动解释器：

- **R（130+ 绘图与生物信息包，含 `ggplot2`、`patchwork`、`ComplexHeatmap`、`circlize`、`ggdist`、`gghalves`、`ggridges`、`ggalluvial`、`ComplexUpset`、`forestploter`、`ggraph`、`aplot`、`scico`、`rms`、`ggsurvfit`、`svglite`）**：`<conda-or-mamba-root>/envs/r/bin/Rscript`（按本地实际 R 环境路径配置）
- **Python 通用及高阶组学绘图（已配 `matplotlib`、`seaborn`、`marsilea`、`legendkit`、`pycirclize`、`upsetplot`、`cmcrameri`、`adjustText`、`plotnine`、`statannotations`）**：
  - 主科研环境：`<conda-or-mamba-root>/envs/python/bin/python3`（或本地主科研 Python 环境）
  - 单细胞专题环境（含 `scanpy`）：`<conda-or-mamba-root>/envs/single-cell/bin/python3`

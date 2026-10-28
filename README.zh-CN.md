# CV 与 GITT 电化学数据分析

[English](README.md) | [简体中文](README.zh-CN.md)

用于**循环伏安（CV）电流分离**与**恒电流间歇滴定（GITT）分析**的 AI Skill 和本地 Python 计算工具。

本项目将 AI 分析流程与确定性数值计算结合，明确记录单位、数据准备、质量标记和模型假设，并导出可在 Excel、Origin 或独立绘图流程中检查的结果。

## 功能

| 任务 | 所需输入 | 脚本输出 |
|---|---|---|
| CV 电流分离 | 按电位对齐的不同扫速电流列 | 逐点 k₁、k₂、R²、变换空间 RMSE、分离电流和残差 |
| CV 电容贡献率 | 按采集顺序排列的同一份 CV 宽表 | 全路径与质量筛选区间的面积贡献比例，以及覆盖率 |
| GITT 计算 | 每个脉冲已确认的电压端点、通电时长及材料参数 | ΔEₛ、ΔEτ、D、log₁₀D 和逐脉冲质量标记 |
| 结果溯源 | 输入文件与明确的命令参数 | 包含输入文件 SHA-256、单位、参数和方法说明的记录文件 |

**数值脚本处理的是已经准备好的数据表。** Skill 指导 AI 完成列映射、单位检查、CV 分支对齐和 GITT 端点核对；脚本本身尚未实现任意仪器文件的自动分段、Excel 导入或绘图。

## 作为 AI Skill 使用

请保留完整的 `cv-gitt-analysis` 文件夹，包括 `SKILL.md`、`scripts/` 和 `references/`。在 Codex 中，将该文件夹放入配置的技能目录；默认用户目录为 `~/.codex/skills/cv-gitt-analysis/`。

调用示例：

```text
使用 $cv-gitt-analysis 分析附件中的 CV 数据。先检查单位、周期选择和
正反扫描分支对齐，再导出 k1/k2 拟合、电容贡献率、质量标记和可复现的方法说明。
```

分析 GITT 时，尽量提供原始时间–电位–电流数据和工步信息，同时说明活性物质质量、摩尔质量、摩尔体积及面积定义。AI 应先确认脉冲边界与端点来源，再调用计算器。

其他 AI 助手也可读取 [SKILL.md](SKILL.md) 及其链接的参考文档作为工作流说明。自动发现技能的方式与调用语法取决于所使用的应用。

## 直接运行 Python 脚本

计算器仅依赖 **Python 3 标准库**，数值计算无需安装第三方 Python 包，也无需联网。

下载或克隆本仓库，在仓库根目录打开终端，查看命令帮助：

```bash
python3 scripts/analyze.py --help
python3 scripts/analyze.py cv --help
python3 scripts/analyze.py gitt --help
```

以下命令均在仓库根目录执行。输出目录必须尚未存在，每次运行请使用新的目录名。如果本机通过 `python` 或 `py` 调用 Python，请相应替换 `python3`。

### CV 示例

将以下**合成演示数据**保存为 `cv_example.csv`。电位单位为 V，电流单位为 mA，三列电流对应 1、4、9 mV/s。

```csv
E_V,I_1mVs,I_4mVs,I_9mVs
0.1,0.05162278,0.14324555,0.27486833
0.2,0.10324555,0.28649111,0.54973666
0.3,0.15486833,0.42973666,0.82460499
```

```bash
python3 scripts/analyze.py cv cv_example.csv --rates 1,4,9 --rate-unit mV/s --current-unit mA --r2-min 0.95 --out cv_results
```

输入要求：

- 使用带表头的 UTF-8 CSV 或制表符分隔文件；第一列必须命名为 `E_V`，后续电流列名称可自定义。
- 至少提供三个不同的正扫速、两行电位数据；`--rates` 的顺序必须与电流列一致。
- 先按电位、周期和扫描分支对齐数据，保留采集顺序；不要将正反扫描全局排序或合并。
- 扫速单位支持 `mV/s`、`V/s`；电流单位支持 `A`、`mA`、`uA`。脚本不直接接受 A/g 等质量或面积归一化电流单位。
- 所有 CV 数值必须有限；格式错误或无效数值会使计算停止。数值有效但拟合质量低的数据仍保留在输出中。

示例第一行应恢复约 k₁ = 0.02 A·s/V、k₂ = 0.001 A·√(s/V)。

### GITT 示例

将以下**合成演示数据**保存为 `gitt_endpoints.csv`：

```csv
pulse_id,tau_s,E0_V,E1_V,E2_V,E3_V
1,120,4.20,4.19,4.09,4.18
2,120,4.18,4.17,4.07,4.16
```

| 列名 | 含义 |
|---|---|
| `pulse_id` | 唯一且非空的脉冲编号 |
| `tau_s` | 恒流通电脉冲时长，单位 s |
| `E0_V` | 本次脉冲前的准平衡电位 |
| `E1_V` | 考虑瞬时 iR 跳变后的脉冲起始电位 |
| `E2_V` | 电流脉冲结束前的电位 |
| `E3_V` | 本次脉冲后静置末端的准平衡电位 |

```bash
python3 scripts/analyze.py gitt gitt_endpoints.csv --mass-g 0.001902 --molar-mass 80 --molar-volume 20.5 --area-cm2 1 --out gitt_results
```

| 参数 | 单位与含义 |
|---|---|
| `--mass-g` | 活性物质质量，g |
| `--molar-mass` | 摩尔质量，g/mol |
| `--molar-volume` | 摩尔体积，cm³/mol |
| `--area-cm2` | 模型使用的面积，cm² |
| `--min-delta-v` | 可选的最小绝对电压变化阈值，V；默认为 0 |

实际使用时必须替换为对应实验的参数，并记录面积采用几何面积还是有效反应面积。**τ 是通电脉冲时长，不是静置时长。** 上述示例的两个脉冲均得到 D ≈ 1.008 × 10⁻¹⁰ cm²/s、log₁₀D ≈ −9.9965。

可以附加 `row_E0`、`row_E1`、`endpoint_method`、`quality_note` 等溯源列，脚本会保留这些字段。不要将 `qc`、`data_row`、`D_cm2_s` 等输出保留字段用作输入列名。端点选择与适用条件详见 [GITT 工作流](references/gitt.md)。

## 计算方法与结果解释

### CV 模型

在每个电位和扫描分支上，对变换后的变量执行带截距普通最小二乘拟合：

$$
i(E,v)=k_1(E)v+k_2(E)\sqrt{v},\qquad
\frac{i}{\sqrt{v}}=k_1\sqrt{v}+k_2.
$$

计算保留原始电流符号，分别报告电容控制项 k₁v 和扩散控制项 k₂√v。R²、RMSE 对应变换空间中的回归。变换后的信号为常数时，R² 未定义；系数为零本身不代表拟合失败。

脚本采用的电容面积贡献率定义为：

$$
f_{\mathrm{cap}}(v)=
\frac{\int |k_1(E)v|\,|dE|}{\int |i(E,v)|\,|dE|}.
$$

积分沿输入路径进行，并显式处理电流过零。筛选后的积分仅纳入两端均通过 R² 阈值的相邻区间，不跨越被拒绝的数据点连线。比例大于 1 时保留并标记，不强制截断。与文献中的贡献百分比比较前，请核对 [CV 方法说明](references/cv.md) 中的积分约定。

### GITT 模型

$$
D=\frac{4}{\pi\tau}
\left(\frac{m_BV_m}{M_BS}\right)^2
\left(\frac{E_3-E_0}{E_2-E_1}\right)^2.
$$

采用上述单位时，D 的单位为 cm²/s；对数输出表示 log₁₀(D / (cm²·s⁻¹))。无效脉冲行保留在结果表中，D/logD 留空并记录原因。共享材料参数无效或数据表结构错误时，计算停止。

端点计算本身不能证明 E–√t 线性、静置充分性或扩散几何假设成立。未充分验证这些条件时，应将结果表述为**表观化学扩散系数**。电压阈值默认为零时，仅排除精确的零差值；可根据仪器分辨率或噪声设置 `--min-delta-v`。

## 输出文件

| 文件 | 内容 |
|---|---|
| `cv_coefficients.csv` | 逐电位系数、R²、变换空间 RMSE、通过标记和质量标记 |
| `cv_components.csv` | 原始、电容控制、扩散控制及重建电流，以及残差 |
| `cv_summary.csv` | 每个扫速的面积贡献比例、保留路径及原始电流面积覆盖率 |
| `gitt_results.csv` | 原始端点字段、电压差、D、logD 和质量标记 |
| `manifest.json` | 输入路径与 SHA-256、计算版本、参数、单位和方法限制 |

CV 汇总表使用小数比例，例如 0.35 表示 35%。`fraction_all` 使用完整输入路径；`fraction_retained` 仅使用保留区间，必须结合覆盖率列解读。CV 的 `accepted` 仅表示通过 R² 检查，不代表物理有效性已经得到确认。GITT 输出始终保留需要原始脉冲验证的提示。

脚本生成数据表与记录文件；AI 助手或其他绘图工具可基于这些文件进一步制作图表。

## 目录结构

```text
cv-gitt-analysis/
├── README.md
├── README.zh-CN.md
├── SKILL.md
├── agents/
│   └── openai.yaml
├── scripts/
│   ├── analyze.py
│   └── test_analyze.py
└── references/
    ├── cv.md
    ├── gitt.md
    ├── website-audit.md
    └── source-manifest.json
```

## 测试

```bash
python3 scripts/test_analyze.py
```

现有七个合成数据测试覆盖：带符号 CV 系数恢复、常数变换信号与零截距、电流过零积分、筛选缺口处理、GITT 公式与尺度关系、无效电压比、单位换算及无效 GITT 行保留。测试用于核对数值行为，不替代真实实验数据上的方法验证。

## 项目来源与参考资料

本项目基于 2026-10-28 对 EditorTan（编辑之谭）[CV 工具](https://www.upub.online/k1v2.6.html)、[GITT 工具](https://www.upub.online/gittV1.html) 及其公开计算脚本的审阅整理，将核心公式实现为 Python，并记录单位、质量处理与端点核对方面的调整。本项目为独立实现，与原网站不存在隶属或背书关系。

- [网页算法审阅](references/website-audit.md)：记录实际行为、发现的局限及合成验证案例。
- [来源记录](references/source-manifest.json)：记录核查的源文件链接及快照哈希。
- [CV 工作流](references/cv.md) 与 [GITT 工作流](references/gitt.md)：详细的数据准备与结果解释说明。当前配套参考文档为中文。
- [Metrohm GITT 应用说明](https://www.metrohm.cn/en/applications/application-notes/autolab-applikationen-anautolab/an-bat-003.html)：脉冲时长与电压变化定义。
- [GITT 理论分析](https://pmc.ncbi.nlm.nih.gov/articles/PMC8252744/) 与 [方法审查](https://www.osti.gov/servlets/purl/1838037)：初始瞬态及模型解释限制。

# CV & GITT Analysis

[English](README.md) | [简体中文](README.zh-CN.md)

An AI skill and local Python toolkit for **cyclic voltammetry (CV) current decomposition** and **galvanostatic intermittent titration technique (GITT) analysis**.

The project combines instructions for an AI assistant with deterministic numerical calculations. It makes units, data preparation, quality flags, and analysis assumptions explicit, and exports results that can be inspected in Excel, Origin, or a separate plotting workflow.

## Features

| Task | Required input | Script output |
|---|---|---|
| CV decomposition | Potential-aligned current columns at different scan rates | Pointwise k₁, k₂, R², transformed-space RMSE, separated currents, and residuals |
| CV capacitive fraction | The same aligned CV table in acquisition order | Full-path and quality-filtered area fractions, with coverage statistics |
| GITT calculation | Confirmed voltage endpoints and duration for each pulse, plus material parameters | ΔEₛ, ΔEτ, D, log₁₀D, and per-pulse quality flags |
| Reproducibility | Input file and explicit command parameters | A manifest containing input SHA-256, units, parameters, and method notes |

**The numerical script processes prepared tables.** The skill guides an AI through column mapping, unit checks, CV branch alignment, and GITT endpoint review. Automatic segmentation of arbitrary instrument files, spreadsheet import, and plotting are not built into the script.

## Use as an AI skill

Keep the complete `cv-gitt-analysis` folder together, including `SKILL.md`, `scripts/`, and `references/`. For Codex, place it in the configured skills directory; the default user directory is `~/.codex/skills/cv-gitt-analysis/`.

Example request:

```text
Use $cv-gitt-analysis to analyze the attached CV data. Check the units,
cycle selection, and scan-branch alignment first. Export the k1/k2 fits,
capacitive fractions, quality flags, and a reproducible methods summary.
```

For GITT, provide raw time–potential–current data and step metadata when available, together with active-material mass, molar mass, molar volume, and the area definition. The assistant should establish pulse boundaries and endpoint provenance before calling the calculator.

Other agents can use [SKILL.md](SKILL.md) and its linked references as workflow instructions. Automatic skill discovery and invocation syntax depend on the host application.

## Run directly with Python

The calculator uses **Python 3 and the standard library only**. No third-party Python packages or network connection are required for calculation.

Download or clone this repository, open a terminal in its root directory, and inspect the commands:

```bash
python3 scripts/analyze.py --help
python3 scripts/analyze.py cv --help
python3 scripts/analyze.py gitt --help
```

All examples below run from the repository root. The output directory must not already exist; use a new name for each run. On systems where Python is invoked as `python` or `py`, substitute that command for `python3`.

### CV example

Save the following **synthetic demonstration data** as `cv_example.csv`. Potential is in V, current is in mA, and the three scan rates are 1, 4, and 9 mV/s.

```csv
E_V,I_1mVs,I_4mVs,I_9mVs
0.1,0.05162278,0.14324555,0.27486833
0.2,0.10324555,0.28649111,0.54973666
0.3,0.15486833,0.42973666,0.82460499
```

```bash
python3 scripts/analyze.py cv cv_example.csv --rates 1,4,9 --rate-unit mV/s --current-unit mA --r2-min 0.95 --out cv_results
```

Input requirements:

- Use a UTF-8 CSV or tab-separated file with a header. The first column must be named `E_V`; subsequent column names may vary.
- Provide at least three distinct positive scan rates and at least two potential rows. The order of `--rates` must match the current columns.
- Align currents by potential, cycle, and scan branch before running. Keep acquisition order; do not globally sort or merge forward and reverse scans.
- Accepted scan-rate units are `mV/s` and `V/s`; current units are `A`, `mA`, and `uA`. The script does not directly accept mass- or area-normalized current units such as A/g.
- Every CV numeric cell must be finite. Malformed tables or invalid numeric cells stop the calculation; low-quality but numerically valid fits remain in the results.

The first demonstration row should recover approximately k₁ = 0.02 A·s/V and k₂ = 0.001 A·√(s/V).

### GITT example

Save the following **synthetic demonstration data** as `gitt_endpoints.csv`:

```csv
pulse_id,tau_s,E0_V,E1_V,E2_V,E3_V
1,120,4.20,4.19,4.09,4.18
2,120,4.18,4.17,4.07,4.16
```

| Column | Meaning |
|---|---|
| `pulse_id` | Unique, nonempty pulse identifier |
| `tau_s` | Applied-current pulse duration in seconds |
| `E0_V` | Quasi-equilibrium potential before the pulse |
| `E1_V` | Pulse-start potential after accounting for the instantaneous iR jump |
| `E2_V` | Potential immediately before the current pulse ends |
| `E3_V` | Quasi-equilibrium potential at the end of the following rest |

```bash
python3 scripts/analyze.py gitt gitt_endpoints.csv --mass-g 0.001902 --molar-mass 80 --molar-volume 20.5 --area-cm2 1 --out gitt_results
```

| Parameter | Unit |
|---|---|
| `--mass-g` | Active-material mass, g |
| `--molar-mass` | Molar mass, g/mol |
| `--molar-volume` | Molar volume, cm³/mol |
| `--area-cm2` | Area used by the model, cm² |
| `--min-delta-v` | Optional minimum absolute voltage change, V; default: 0 |

Replace all example parameters with values appropriate to your experiment. Record whether the area is geometric or an effective reaction area. **τ is the current-pulse duration, not the rest duration.** The example yields D ≈ 1.008 × 10⁻¹⁰ cm²/s and log₁₀D ≈ −9.9965 for both pulses.

Extra provenance columns, such as `row_E0`, `row_E1`, `endpoint_method`, or `quality_note`, are preserved. Do not reuse output-reserved names such as `qc`, `data_row`, or `D_cm2_s` as input columns. See the [GITT workflow](references/gitt.md) for endpoint selection and validity checks.

## Methods and interpretation

### CV model

At each potential and scan branch, the calculator fits ordinary least squares with an intercept in transformed space:

$$
i(E,v)=k_1(E)v+k_2(E)\sqrt{v},\qquad
\frac{i}{\sqrt{v}}=k_1\sqrt{v}+k_2.
$$

The calculation retains the current sign and reports the capacitive term k₁v and diffusion-controlled term k₂√v. R² and RMSE refer to the transformed regression. A constant transformed signal has undefined R²; a zero coefficient alone is not a fitting failure.

The implemented capacitive area fraction is:

$$
f_{\mathrm{cap}}(v)=
\frac{\int |k_1(E)v|\,|dE|}{\int |i(E,v)|\,|dE|}.
$$

Integration follows the supplied path and treats zero crossings explicitly. Filtered integrals include only intervals whose two adjacent endpoints pass the R² threshold; they do not bridge rejected points. Fractions above 1 are flagged rather than clipped. Read [CV methods](references/cv.md) before comparing this convention with published percentages.

### GITT model

$$
D=\frac{4}{\pi\tau}
\left(\frac{m_BV_m}{M_BS}\right)^2
\left(\frac{E_3-E_0}{E_2-E_1}\right)^2.
$$

With the documented units, D is in cm²/s. The logarithmic output represents log₁₀(D / (cm²·s⁻¹)). Invalid pulse rows remain in the result table with blank D/logD and a reason. Invalid shared material parameters or malformed table structure stop the calculation.

Endpoint calculations do not establish E–√t linearity, adequate relaxation, or the suitability of the diffusion geometry. Report the result as an **apparent chemical diffusion coefficient** when these assumptions have not been established. The default voltage threshold of zero rejects exact zero differences only; set `--min-delta-v` using measurement resolution or noise where appropriate.

## Output files

| File | Contents |
|---|---|
| `cv_coefficients.csv` | Per-potential coefficients, R², transformed RMSE, acceptance flag, and quality flags |
| `cv_components.csv` | Measured, capacitive, diffusion-controlled, and reconstructed currents, plus residuals |
| `cv_summary.csv` | Area fractions and retained-path/current-area coverage for each scan rate |
| `gitt_results.csv` | Original endpoint fields, voltage differences, D, logD, and quality flags |
| `manifest.json` | Input path and SHA-256, calculation version, parameters, units, and method limitations |

The CV summary reports fractions as decimals: 0.35 means 35%. `fraction_all` uses the full supplied path; `fraction_retained` uses only retained intervals and must be read with the coverage columns. The CV `accepted` flag checks R² only; it does not certify physical validity. GITT results always include a reminder that raw-pulse validation remains necessary.

The script writes tables and a manifest. An AI assistant or separate plotting tool can use them to generate figures.

## Repository structure

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

## Tests

```bash
python3 scripts/test_analyze.py
```

The seven synthetic-data tests cover signed CV coefficient recovery, constant transformed signals and zero intercepts, zero-crossing integration, rejection gaps, GITT formula and scaling, undefined voltage ratios, unit conversion, and preservation of invalid GITT rows. These checks validate numerical behavior; they do not replace validation on experimental data.

## Background and references

The project was developed after reviewing EditorTan's [CV tool](https://www.upub.online/k1v2.6.html) and [GITT tool](https://www.upub.online/gittV1.html), including their public calculation scripts, on 2026-10-28. It implements the core equations in Python and documents changes to units, quality handling, and endpoint review. It is an independent implementation and is not affiliated with or endorsed by the original website.

- [Website algorithm audit](references/website-audit.md): observed behavior, identified limitations, and synthetic verification cases.
- [Source manifest](references/source-manifest.json): reviewed source URLs and snapshot hashes.
- [CV workflow](references/cv.md) and [GITT workflow](references/gitt.md): detailed preparation and interpretation guidance. These supporting documents are currently in Chinese.
- [Metrohm GITT application note](https://www.metrohm.cn/en/applications/application-notes/autolab-applikationen-anautolab/an-bat-003.html): definitions of pulse duration and voltage changes.
- [GITT theoretical analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC8252744/) and [methodological review](https://www.osti.gov/servlets/purl/1838037): transient effects and interpretation limits.

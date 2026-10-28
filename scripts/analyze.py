#!/usr/bin/env python3
"""Local CV decomposition and GITT endpoint calculation; Python standard library."""
import argparse
import csv
import hashlib
import io
import json
import math
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.0.0"


def finite(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("non-finite numeric value")
    return value


def positive(value):
    value = finite(value)
    if value <= 0:
        raise ValueError("value must be positive")
    return value


def read_table(path):
    text = Path(path).read_text(encoding="utf-8-sig")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("empty input")
    delimiter = "\t" if "\t" in lines[0] else ","
    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    fields = [x.strip() for x in (reader.fieldnames or [])]
    if not fields or len(set(fields)) != len(fields) or any(not x for x in fields):
        raise ValueError("unique, nonempty column headers required")
    reader.fieldnames = fields
    rows = list(reader)
    if not rows:
        raise ValueError("no data rows")
    for n, row in enumerate(rows, 1):
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f"inconsistent column count in data row {n}")
    return fields, rows


def regression(x, y):
    """OLS with intercept in transformed CV space; constant-y R² is undefined."""
    xm, ym = math.fsum(x) / len(x), math.fsum(y) / len(y)
    sxx = math.fsum((v - xm) ** 2 for v in x)
    if sxx == 0:
        raise ValueError("scan rates have no variance")
    scale = max(abs(v) for v in y)
    constant = max(y) - min(y) <= 1e-12 * scale
    if constant:
        k1, k2, r2 = 0.0, ym, None
    else:
        k1 = math.fsum((a - xm) * (b - ym) for a, b in zip(x, y)) / sxx
        k2 = ym - k1 * xm
        sst = math.fsum((v - ym) ** 2 for v in y)
        sse = math.fsum((b - k1 * a - k2) ** 2 for a, b in zip(x, y))
        r2 = min(1.0, max(0.0, 1 - sse / sst))
    rmse = math.sqrt(math.fsum((b - k1 * a - k2) ** 2 for a, b in zip(x, y)) / len(x))
    return k1, k2, r2, rmse


def absolute_linear_area(a, b, width):
    """Exact integral of the absolute value of a linear segment."""
    if a * b < 0:
        return width * (a * a + b * b) / (2 * (abs(a) + abs(b)))
    return width * (abs(a) + abs(b)) / 2


def cv_calculate(potentials, currents, rates, r2_min=0.95):
    if len(rates) < 3 or len(set(rates)) != len(rates) or any(v <= 0 for v in rates):
        raise ValueError("at least three distinct positive scan rates required")
    if len(potentials) < 2 or len(currents) != len(potentials):
        raise ValueError("at least two potential rows required")
    if any(len(row) != len(rates) for row in currents):
        raise ValueError("current columns do not match rates")
    x = [math.sqrt(v) for v in rates]
    coefficients, components, masks, caps = [], [], [], []
    for n, (e, row) in enumerate(zip(potentials, currents), 1):
        k1, k2, r2, rmse = regression(x, [i / s for i, s in zip(row, x)])
        accepted = r2 is not None and r2 >= r2_min
        qc = []
        if r2 is None:
            qc.append("r2_undefined_constant_transformed_current")
        elif not accepted:
            qc.append("low_r2")
        cap = [k1 * v for v in rates]
        diff = [k2 * s for s in x]
        tol = max([abs(i) for i in row] + [1e-300]) * 1e-12
        if any((a * i < 0 and abs(a) > tol and abs(i) > tol)
               for part in (cap, diff) for a, i in zip(part, row)):
            qc.append("component_opposes_measured_current")
        if any(abs(a) > abs(i) + tol for a, i in zip(cap, row)):
            qc.append("capacitive_component_exceeds_measured_current")
        coefficients.append(dict(data_row=n, E_V=e, k1_A_s_per_V=k1,
                                 k2_A_sqrt_s_per_V=k2, r2=r2,
                                 rmse_transformed=rmse, accepted=accepted,
                                 qc=";".join(qc)))
        for v, i, a, b in zip(rates, row, cap, diff):
            components.append(dict(data_row=n, E_V=e, rate_V_s=v, current_A=i,
                                   capacitive_A=a, diffusion_A=b, reconstructed_A=a + b,
                                   residual_A=i - a - b, accepted=accepted))
        masks.append(accepted)
        caps.append(cap)
    summaries = []
    for j, v in enumerate(rates):
        full_i = full_c = kept_i = kept_c = full_path = kept_path = 0.0
        for n in range(1, len(potentials)):
            width = abs(potentials[n] - potentials[n - 1])
            area_i = absolute_linear_area(currents[n - 1][j], currents[n][j], width)
            area_c = absolute_linear_area(caps[n - 1][j], caps[n][j], width)
            full_i += area_i
            full_c += area_c
            full_path += width
            if masks[n - 1] and masks[n]:
                kept_i += area_i
                kept_c += area_c
                kept_path += width
        ratio = full_c / full_i if full_i > 0 else None
        kept_ratio = kept_c / kept_i if kept_i > 0 else None
        flags = []
        if full_i == 0:
            flags.append("zero_current_area")
        if kept_i == 0:
            flags.append("no_retained_current_area")
        if any(r is not None and r > 1 + 1e-10 for r in (ratio, kept_ratio)):
            flags.append("fraction_exceeds_one")
        summaries.append(dict(rate_V_s=v, fraction_all=ratio, fraction_retained=kept_ratio,
                              retained_path_fraction=kept_path / full_path if full_path else None,
                              retained_current_area_fraction=kept_i / full_i if full_i else None,
                              measured_area_A_V=full_i, capacitive_area_A_V=full_c,
                              retained_measured_area_A_V=kept_i,
                              retained_capacitive_area_A_V=kept_c,
                              accepted_points=sum(masks), total_points=len(masks),
                              qc=";".join(flags)))
    return coefficients, components, summaries


def gitt_value(tau, e0, e1, e2, e3, mass, molar_mass, volume, area, min_delta=0):
    for value in (tau, mass, molar_mass, volume, area):
        positive(value)
    for value in (e0, e1, e2, e3, min_delta):
        finite(value)
    if min_delta < 0:
        raise ValueError("min_delta must be nonnegative")
    ds, dt = e3 - e0, e2 - e1
    if abs(dt) <= min_delta:
        raise ValueError("zero_or_unresolved_delta_E_tau")
    if abs(ds) <= min_delta:
        raise ValueError("zero_or_unresolved_delta_E_s")
    # Log-domain computation keeps unit scaling explicit and avoids squaring overflow.
    logd = (math.log10(4 / math.pi) - math.log10(tau)
            + 2 * (math.log10(mass) + math.log10(volume)
                   - math.log10(molar_mass) - math.log10(area))
            + 2 * (math.log10(abs(ds)) - math.log10(abs(dt))))
    d = 10 ** logd
    if not math.isfinite(d) or d <= 0:
        raise ValueError("diffusivity_out_of_numeric_range")
    return ds, dt, d, logd


def write_csv(path, rows):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def manifest(args, **extras):
    data = dict(version=VERSION, mode=args.mode, created_utc=datetime.now(timezone.utc).isoformat(),
                input_path=str(Path(args.input).resolve()),
                input_sha256=hashlib.sha256(Path(args.input).read_bytes()).hexdigest(),
                parameters=vars(args), **extras)
    Path(args.out, "manifest.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def run_cv(args):
    fields, raw = read_table(args.input)
    rates = [positive(v) * {"mV/s": 0.001, "V/s": 1}[args.rate_unit]
             for v in args.rates.split(",")]
    if fields[0] != "E_V" or len(fields) != len(rates) + 1:
        raise ValueError("expected E_V then one current column per scan rate")
    factor = {"A": 1, "mA": 0.001, "uA": 0.000001}[args.current_unit]
    potentials, currents = [], []
    for n, row in enumerate(raw, 1):
        try:
            potentials.append(finite(row[fields[0]]))
            currents.append([finite(row[key]) * factor for key in fields[1:]])
        except ValueError as exc:
            raise ValueError(f"invalid CV data row {n}: {exc}") from exc
    if not math.isfinite(args.r2_min) or not 0 <= args.r2_min <= 1:
        raise ValueError("r2-min must be in [0,1]")
    results = cv_calculate(potentials, currents, rates, args.r2_min)
    Path(args.out).mkdir(parents=True, exist_ok=False)
    for filename, rows in zip(("cv_coefficients.csv", "cv_components.csv", "cv_summary.csv"), results):
        write_csv(Path(args.out, filename), rows)
    manifest(args, units=dict(potential="V", current="A", rate="V/s"),
             column_mapping=dict(zip(fields[1:], rates)),
             fit="OLS i/sqrt(v) versus sqrt(v), including intercept",
             integration="absolute piecewise-linear current over absolute potential increments",
             limitations=["input must already be aligned by cycle and branch",
                          "accepted marks R2 only; inspect other QC flags",
                          "retained integral uses adjacent accepted endpoints only"])


def run_gitt(args):
    fields, raw = read_table(args.input)
    required = {"pulse_id", "tau_s", "E0_V", "E1_V", "E2_V", "E3_V"}
    if not required.issubset(fields):
        raise ValueError(f"missing columns: {sorted(required - set(fields))}")
    added = {"data_row", "delta_E_s_V", "delta_E_tau_V", "D_cm2_s", "log10_D_cm2_s", "qc"}
    if added.intersection(fields):
        raise ValueError("input conflicts with output column names; rename existing result columns")
    pulse_ids = [row["pulse_id"].strip() for row in raw]
    if any(not x for x in pulse_ids) or len(set(pulse_ids)) != len(pulse_ids):
        raise ValueError("pulse_id must be unique and nonempty")
    for value in (args.mass_g, args.molar_mass, args.molar_volume, args.area_cm2):
        positive(value)
    if finite(args.min_delta_v) < 0:
        raise ValueError("min-delta-v must be nonnegative")
    results = []
    for n, row in enumerate(raw, 1):
        out = dict(row, data_row=n, delta_E_s_V=None, delta_E_tau_V=None,
                   D_cm2_s=None, log10_D_cm2_s=None)
        qc = ["endpoint_only_requires_raw_pulse_validation"]
        try:
            tau = positive(row["tau_s"])
            e0, e1, e2, e3 = (finite(row[f"E{i}_V"]) for i in range(4))
            out.update(delta_E_s_V=e3 - e0, delta_E_tau_V=e2 - e1)
            ds, dt, d, logd = gitt_value(tau, e0, e1, e2, e3, args.mass_g,
                                       args.molar_mass, args.molar_volume, args.area_cm2,
                                       args.min_delta_v)
            out.update(D_cm2_s=d, log10_D_cm2_s=logd)
            if ds * dt < 0:
                qc.append("steady_and_transient_voltage_changes_have_opposite_signs")
        except (ValueError, OverflowError) as exc:
            qc.append("invalid:" + str(exc))
        out["qc"] = ";".join(qc)
        results.append(out)
    Path(args.out).mkdir(parents=True, exist_ok=False)
    write_csv(Path(args.out, "gitt_results.csv"), results)
    manifest(args, units=dict(time="s", potential="V", mass="g", molar_mass="g/mol",
                             molar_volume="cm3/mol", area="cm2", D="cm2/s"),
             formula="D=4/(pi*tau)*(mass*molar_volume/(molar_mass*area))^2*((E3-E0)/(E2-E1))^2",
             limitations=["no automatic raw pulse segmentation",
                          "endpoint table does not establish E-sqrt(t) linearity or equilibration",
                          "zero min-delta-v only checks exact zero, not instrumental noise"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    cv = sub.add_parser("cv", help="aligned, headered CV wide table")
    cv.add_argument("input")
    cv.add_argument("--rates", required=True, help="comma-separated, in current-column order")
    cv.add_argument("--rate-unit", required=True, choices=["mV/s", "V/s"])
    cv.add_argument("--current-unit", required=True, choices=["A", "mA", "uA"])
    cv.add_argument("--r2-min", type=float, default=0.95)
    cv.add_argument("--out", required=True, help="new output directory")
    gitt = sub.add_parser("gitt", help="confirmed per-pulse endpoint table")
    gitt.add_argument("input")
    for key in ("mass-g", "molar-mass", "molar-volume", "area-cm2"):
        gitt.add_argument("--" + key, type=float, required=True)
    gitt.add_argument("--min-delta-v", type=float, default=0.0)
    gitt.add_argument("--out", required=True, help="new output directory")
    args = parser.parse_args()
    try:
        (run_cv if args.mode == "cv" else run_gitt)(args)
    except (ValueError, OSError, OverflowError) as exc:
        parser.error(str(exc))
    print(f"Saved {args.mode} results to {args.out}")


if __name__ == "__main__":
    main()

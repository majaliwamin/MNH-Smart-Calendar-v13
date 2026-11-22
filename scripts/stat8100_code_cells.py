"""Verified code cells for the STAT 8100 practical companion.

Every string in CODE is executed in the delivered notebook. The HTML companion
renders the same strings, so the two artefacts cannot drift apart.
"""

from textwrap import dedent

CODE = {}

CODE["setup"] = dedent(r'''
    # Reusable setup — run this once before any question.
    from pathlib import Path
    import json
    import math
    import os
    import warnings

    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns
    import scipy.stats as st
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    from statsmodels.stats.multicomp import pairwise_tukeyhsd
    from statsmodels.stats.proportion import (
        proportion_confint,
        proportions_ztest,
        confint_proportions_2indep,
    )
    from statsmodels.stats.stattools import durbin_watson
    from statsmodels.stats.multitest import multipletests
    from statsmodels.duration.survfunc import SurvfuncRight
    from statsmodels.duration.hazard_regression import PHReg

    %matplotlib inline
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams["figure.dpi"] = 110
    pd.set_option("display.max_columns", 50)
    pd.set_option("display.width", 130)
    warnings.filterwarnings("ignore", category=FutureWarning)

    DATA_FILES = {
        "anc": "anc_cohort.csv",
        "bp": "bp_paired.csv",
        "survival": "postpartum_survival.csv",
    }
    NUMERIC_COLUMNS = {
        "anc": ["age", "parity", "bmi", "anc_visits", "hb", "anaemia",
                "preterm", "gest_age", "birthweight", "low_bw"],
        "bp": ["sbp_booking", "sbp_36wk"],
        "survival": ["time_days", "readmitted", "age"],
    }
    QUESTION_IDS = [f"Q{i}" for i in range(1, 11)]


    def find_data_dir():
        """Find the uploaded CSVs from a notebook opened in several locations."""
        candidates = []
        env_dir = os.environ.get("MNH_DATA_DIR")
        if env_dir:
            candidates.append(Path(env_dir).expanduser().resolve())
        here = Path.cwd().resolve()
        for _ in range(7):
            candidates.extend([
                here / "frontend" / "resources" / "samples",
                here / "resources" / "samples",
                here / "samples",
                here,
            ])
            here = here.parent
        for candidate in candidates:
            if candidate.is_dir() and all((candidate / name).is_file()
                                          for name in DATA_FILES.values()):
                return candidate
        raise FileNotFoundError(
            "Could not find anc_cohort.csv, bp_paired.csv and "
            "postpartum_survival.csv. Set MNH_DATA_DIR to their folder."
        )


    def load_csv(key):
        """Read a CSV while preserving the literal education level 'None'."""
        path = DATA_DIR / DATA_FILES[key]
        frame = pd.read_csv(
            path,
            keep_default_na=False,
            na_values=["", "NA", "N/A", "NaN", "nan", "null", "NULL"],
        )
        for column in frame.select_dtypes(include=["object", "string"]).columns:
            frame[column] = frame[column].str.strip()
        for column in NUMERIC_COLUMNS[key]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame


    DATA_DIR = find_data_dir()
    anc = load_csv("anc")
    bp = load_csv("bp")
    surv = load_csv("survival")

    RESULTS = {}
    PROGRESS = set()


    def _clean_nan(value):
        if isinstance(value, float) and math.isnan(value):
            return None
        return value


    def jsonable(obj):
        """Convert pandas/numpy results into JSON-safe plain Python values."""
        if isinstance(obj, dict):
            return {str(k): jsonable(_clean_nan(v)) for k, v in obj.items()}
        if isinstance(obj, (list, tuple, set)):
            return [jsonable(_clean_nan(v)) for v in obj]
        if isinstance(obj, pd.DataFrame):
            return jsonable(obj.to_dict(orient="records"))
        if isinstance(obj, pd.Series):
            return jsonable(obj.to_dict())
        if isinstance(obj, np.ndarray):
            return jsonable(obj.tolist())
        if isinstance(obj, np.generic):
            return jsonable(obj.item())
        return _clean_nan(obj)


    def record(key, value):
        """Store a verified result for the companion's output panel."""
        RESULTS[key] = jsonable(value)
        return RESULTS[key]


    def show_progress():
        bar = "".join("■" if q in PROGRESS else "□" for q in QUESTION_IDS)
        done = sum(q in PROGRESS for q in QUESTION_IDS)
        print(f"Progress: {bar}  {done}/10 questions covered")


    def mark_done(question_id):
        PROGRESS.add(question_id)
        show_progress()


    print("DATA_DIR:", DATA_DIR)
    print("Simulated teaching datasets loaded:",
          f"anc={anc.shape}, bp={bp.shape}, survival={surv.shape}")
    show_progress()
''').strip() + "\n"

CODE["audit"] = dedent(r'''
    import hashlib

    audit_rows = []
    for key, name in DATA_FILES.items():
        path = DATA_DIR / name
        frame = {"anc": anc, "bp": bp, "survival": surv}[key]
        audit_rows.append({
            "dataset": name,
            "rows": int(frame.shape[0]),
            "columns": int(frame.shape[1]),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
            "missing_cells": int(frame.isna().sum().sum()),
            "duplicate_rows": int(frame.duplicated().sum()),
        })
    audit_table = pd.DataFrame(audit_rows)
    print(audit_table.to_string(index=False))
    print("\nANC column order:", list(anc.columns))
    print("BP column order:", list(bp.columns))
    print("Survival column order:", list(surv.columns))
    print("\nANC missingness:")
    print(anc.isna().sum().to_string())
    print("\nEducation levels:", anc["education"].value_counts(dropna=False).to_dict())
    print("IPTp3 levels:", anc["iptp3"].value_counts(dropna=False).to_dict())
    print("Facility levels:", anc["facility_type"].value_counts(dropna=False).to_dict())

    anaemia_check = (anc["hb"] < 11).astype("Int64") == anc["anaemia"].astype("Int64")
    preterm_check = (anc["gest_age"] < 37).astype("Int64") == anc["preterm"].astype("Int64")
    lowbw_check = (anc["birthweight"] < 2500).astype("Int64") == anc["low_bw"].astype("Int64")
    print("\nDerived-variable checks (mismatches among evaluable rows):")
    print("  anaemia vs hb<11:", int((~anaemia_check.dropna()).sum()),
          "evaluable:", int(anaemia_check.notna().sum()))
    print("  preterm vs gest_age<37:", int((~preterm_check.dropna()).sum()),
          "evaluable:", int(preterm_check.notna().sum()))
    print("  low_bw vs birthweight<2500:", int((~lowbw_check.dropna()).sum()),
          "evaluable:", int(lowbw_check.notna().sum()))
    record("Audit", {
        "datasets": audit_table.to_dict(orient="records"),
        "education_levels": anc["education"].value_counts(dropna=False).to_dict(),
        "anaemia_mismatches": int((~anaemia_check.dropna()).sum()),
        "preterm_mismatches": int((~preterm_check.dropna()).sum()),
        "lowbw_mismatches": int((~lowbw_check.dropna()).sum()),
    })
''').strip() + "\n"

CODE["q1a"] = dedent(r'''
    n_anc = int(anc["preterm"].notna().sum())
    p_preterm = float(anc["preterm"].mean())
    p_lowbw = float(anc["low_bw"].mean())
    q1a_table = pd.DataFrame({
        "event": ["Preterm delivery", "Low birth weight"],
        "count": [int(anc["preterm"].sum()), int(anc["low_bw"].sum())],
        "denominator": [n_anc, n_anc],
        "sample_proportion": [p_preterm, p_lowbw],
    })
    print(q1a_table.to_string(index=False, formatters={
        "sample_proportion": lambda v: f"{v:.4f}"
    }))
    record("Q1a", q1a_table.to_dict(orient="records"))
''').strip() + "\n"

CODE["q1b"] = dedent(r'''
    preterm_group = anc.loc[anc["preterm"] == 1, "low_bw"]
    term_group = anc.loc[anc["preterm"] == 0, "low_bw"]
    p_lb_given_preterm = float(preterm_group.mean())
    p_lb_given_term = float(term_group.mean())
    q1b_table = pd.DataFrame({
        "stratum": ["Preterm (preterm=1)", "Term (preterm=0)"],
        "low_bw_count": [int(preterm_group.sum()), int(term_group.sum())],
        "stratum_n": [int(preterm_group.size), int(term_group.size)],
        "P(low_bw | stratum)": [p_lb_given_preterm, p_lb_given_term],
    })
    contingency_q1 = pd.crosstab(anc["preterm"], anc["low_bw"], margins=True)
    print(q1b_table.to_string(index=False, formatters={
        "P(low_bw | stratum)": lambda v: f"{v:.4f}"
    }))
    print("\nContingency table (rows=preterm, columns=low_bw):")
    print(contingency_q1.to_string())
    print(f"\nRisk difference = {p_lb_given_preterm - p_lb_given_term:+.4f}")
    print(f"Risk ratio = {p_lb_given_preterm / p_lb_given_term:.3f}")
    record("Q1b", {
        "table": q1b_table.to_dict(orient="records"),
        "contingency": contingency_q1.to_dict(),
        "risk_difference": p_lb_given_preterm - p_lb_given_term,
        "risk_ratio": p_lb_given_preterm / p_lb_given_term,
    })
''').strip() + "\n"

CODE["q2b"] = dedent(r'''
    desc_columns = ["age", "bmi", "hb", "gest_age", "birthweight"]
    rows = []
    for column in desc_columns:
        series = anc[column]
        q1, q3 = series.quantile([0.25, 0.75])
        rows.append({
            "variable": column,
            "n_non_missing": int(series.notna().sum()),
            "n_missing": int(series.isna().sum()),
            "mean": series.mean(),
            "sd": series.std(ddof=1),
            "median": series.median(),
            "IQR": q3 - q1,
        })
    q2b_summary = pd.DataFrame(rows)
    print(q2b_summary.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    record("Q2b", q2b_summary.to_dict(orient="records"))
''').strip() + "\n"

CODE["q2c"] = dedent(r'''
    dist_columns = ["birthweight", "gest_age"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    dist_rows = []
    for axis, column in zip(axes, dist_columns):
        values = anc[column].dropna()
        sns.histplot(values, kde=True, bins=24, ax=axis, color="#0b4f8a")
        axis.axvline(values.mean(), color="#d97706", linestyle="--", label="Mean")
        axis.axvline(values.median(), color="#166534", linestyle=":", label="Median")
        axis.set_title(f"Distribution of {column}")
        axis.legend(fontsize=8)
        q1, q3 = values.quantile([0.25, 0.75])
        iqr = q3 - q1
        low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        dist_rows.append({
            "variable": column,
            "n": int(values.size),
            "mean": values.mean(),
            "median": values.median(),
            "sd": values.std(ddof=1),
            "skewness": values.skew(),
            "iqr_outliers_low": int((values < low).sum()),
            "iqr_outliers_high": int((values > high).sum()),
        })
    plt.tight_layout()
    plt.show()
    plt.close("all")
    q2c_summary = pd.DataFrame(dist_rows)
    print(q2c_summary.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    record("Q2c", q2c_summary.to_dict(orient="records"))
''').strip() + "\n"

CODE["q2d"] = dedent(r'''
    corr_data = anc[["gest_age", "birthweight"]].dropna()
    pearson = st.pearsonr(corr_data["gest_age"], corr_data["birthweight"])
    spearman = st.spearmanr(corr_data["gest_age"], corr_data["birthweight"])
    pearson_ci = pearson.confidence_interval(confidence_level=0.95)
    sns.regplot(
        data=corr_data, x="gest_age", y="birthweight",
        scatter_kws={"alpha": 0.55, "s": 24},
        line_kws={"color": "#d97706"}, ax=None,
    )
    plt.title("Gestational age vs birthweight (simulated teaching data)")
    plt.tight_layout()
    plt.show()
    plt.close("all")
    print(f"Pearson r  = {pearson.statistic:.4f}, p = {pearson.pvalue:.4g}, "
          f"95% CI [{pearson_ci.low:.4f}, {pearson_ci.high:.4f}]")
    print(f"Spearman rho = {spearman.statistic:.4f}, p = {spearman.pvalue:.4g}")
    record("Q2d", {
        "n": int(len(corr_data)),
        "pearson_r": float(pearson.statistic),
        "pearson_p": float(pearson.pvalue),
        "pearson_ci": [float(pearson_ci.low), float(pearson_ci.high)],
        "spearman_rho": float(spearman.statistic),
        "spearman_p": float(spearman.pvalue),
    })
''').strip() + "\n"

CODE["q3a"] = dedent(r'''
    bw = anc["birthweight"].dropna()
    n = int(bw.size)
    mean_bw = float(bw.mean())
    sd_bw = float(bw.std(ddof=1))
    se_bw = sd_bw / np.sqrt(n)
    df_bw = n - 1
    t_crit = float(st.t.ppf(0.975, df_bw))
    manual_ci = (mean_bw - t_crit * se_bw, mean_bw + t_crit * se_bw)
    scipy_ci = st.t.interval(0.95, df=df_bw, loc=mean_bw, scale=se_bw)
    steps = pd.DataFrame({
        "quantity": ["Sample mean", "Sample SD", "n", "df", "Standard error",
                     "Critical t (0.975)", "Manual lower", "Manual upper",
                     "SciPy lower", "SciPy upper"],
        "value": [mean_bw, sd_bw, n, df_bw, se_bw, t_crit,
                  manual_ci[0], manual_ci[1], scipy_ci[0], scipy_ci[1]],
    })
    print(steps.to_string(index=False, float_format=lambda v: f"{v:.6f}"))
    print(f"Manual and SciPy endpoints agree to <1e-9: "
          f"{np.allclose(manual_ci, scipy_ci, atol=1e-9)}")
    record("Q3a", {
        "n": n, "mean": mean_bw, "sd": sd_bw, "se": se_bw, "df": df_bw,
        "t_critical": t_crit, "ci": [float(manual_ci[0]), float(manual_ci[1])],
        "scipy_ci": [float(scipy_ci[0]), float(scipy_ci[1])],
    })
''').strip() + "\n"

CODE["q3b"] = dedent(r'''
    anaemia = anc["anaemia"].dropna().astype(int)
    events = int(anaemia.sum())
    denominator = int(anaemia.size)
    prevalence = events / denominator
    wilson_ci = proportion_confint(events, denominator, alpha=0.05, method="wilson")
    print(f"Anaemia events: {events}")
    print(f"Eligible non-missing denominator: {denominator}")
    print(f"Prevalence: {prevalence:.4f} ({prevalence * 100:.2f}%)")
    print(f"Wilson 95% CI: [{wilson_ci[0]:.4f}, {wilson_ci[1]:.4f}]")
    print(f"Records excluded from denominator: {int(anc['anaemia'].isna().sum())}")
    record("Q3b", {
        "events": events, "denominator": denominator,
        "prevalence": float(prevalence),
        "ci": [float(wilson_ci[0]), float(wilson_ci[1])],
        "missing_excluded": int(anc["anaemia"].isna().sum()),
    })
''').strip() + "\n"

CODE["q3d"] = dedent(r'''
    facility_order = ["Urban", "Peri-urban", "Rural"]
    facility_rows = []
    for facility in facility_order:
        values = anc.loc[anc["facility_type"] == facility, "birthweight"].dropna()
        n_f = int(values.size)
        mean_f = float(values.mean())
        sd_f = float(values.std(ddof=1))
        se_f = sd_f / np.sqrt(n_f)
        ci_f = st.t.interval(0.95, df=n_f - 1, loc=mean_f, scale=se_f)
        facility_rows.append({
            "facility_type": facility, "n": n_f, "mean": mean_f, "sd": sd_f,
            "ci_low": ci_f[0], "ci_high": ci_f[1],
        })
    facility_summary = pd.DataFrame(facility_rows)
    print(facility_summary.to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    sns.pointplot(
        data=anc, x="facility_type", y="birthweight", order=facility_order,
        errorbar=("ci", 95), capsize=0.12, linestyles="", color="#0b4f8a",
    )
    plt.title("Mean birthweight by facility type with 95% CIs")
    plt.xlabel("Facility type")
    plt.ylabel("Birthweight (g)")
    plt.tight_layout()
    plt.show()
    plt.close("all")
    record("Q3d", facility_summary.to_dict(orient="records"))
''').strip() + "\n"

CODE["q4"] = dedent(r'''
    yes = anc.loc[anc["iptp3"] == "Yes", "birthweight"].dropna()
    no = anc.loc[anc["iptp3"] == "No", "birthweight"].dropna()
    group_summary = pd.DataFrame({
        "iptp3": ["Yes", "No"],
        "n": [int(yes.size), int(no.size)],
        "mean": [yes.mean(), no.mean()],
        "sd": [yes.std(ddof=1), no.std(ddof=1)],
        "median": [yes.median(), no.median()],
    })
    levene = st.levene(yes, no, center="median")
    welch = st.ttest_ind(yes, no, equal_var=False)
    welch_ci = welch.confidence_interval(confidence_level=0.95)
    mean_diff = yes.mean() - no.mean()
    mann = st.mannwhitneyu(yes, no, alternative="two-sided")
    rank_biserial = 2 * mann.statistic / (yes.size * no.size) - 1

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    sns.boxplot(data=anc, x="iptp3", y="birthweight", order=["No", "Yes"], ax=axes[0])
    axes[0].set_title("Birthweight by IPTp3 status")
    sns.histplot(yes, kde=True, color="#166534", label="IPTp3 Yes", ax=axes[1])
    sns.histplot(no, kde=True, color="#b45309", label="IPTp3 No", ax=axes[1])
    axes[1].set_title("Distribution by group")
    axes[1].legend()
    plt.tight_layout()
    plt.show()
    plt.close("all")

    print(group_summary.to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    print(f"Levene p = {levene.pvalue:.4f}")
    print(f"Welch t = {welch.statistic:.4f}, df = {welch.df:.2f}, "
          f"p = {welch.pvalue:.4g}")
    print(f"Mean difference (Yes - No) = {mean_diff:.2f} g, "
          f"95% CI [{welch_ci.low:.2f}, {welch_ci.high:.2f}]")
    print(f"Wilcoxon rank-sum U = {mann.statistic:.1f}, p = {mann.pvalue:.4g}, "
          f"rank-biserial r = {rank_biserial:.3f}")
    record("Q4", {
        "groups": group_summary.to_dict(orient="records"),
        "levene_p": float(levene.pvalue),
        "welch_t": float(welch.statistic), "welch_df": float(welch.df),
        "welch_p": float(welch.pvalue), "mean_difference": float(mean_diff),
        "welch_ci": [float(welch_ci.low), float(welch_ci.high)],
        "mann_whitney_u": float(mann.statistic),
        "mann_whitney_p": float(mann.pvalue),
        "rank_biserial": float(rank_biserial),
    })
''').strip() + "\n"

CODE["q5"] = dedent(r'''
    paired = bp.copy()
    paired["diff_36wk_minus_booking"] = paired["sbp_36wk"] - paired["sbp_booking"]
    diff = paired["diff_36wk_minus_booking"]
    bp_summary = pd.DataFrame({
        "measure": ["sbp_booking", "sbp_36wk", "paired difference"],
        "n": [int(paired["sbp_booking"].notna().sum()),
              int(paired["sbp_36wk"].notna().sum()), int(diff.notna().sum())],
        "mean": [paired["sbp_booking"].mean(), paired["sbp_36wk"].mean(), diff.mean()],
        "sd": [paired["sbp_booking"].std(ddof=1), paired["sbp_36wk"].std(ddof=1),
               diff.std(ddof=1)],
    })
    shapiro = st.shapiro(diff)
    paired_test = st.ttest_rel(paired["sbp_36wk"], paired["sbp_booking"])
    paired_ci = paired_test.confidence_interval(confidence_level=0.95)
    wrong_independent = st.ttest_ind(
        paired["sbp_36wk"], paired["sbp_booking"], equal_var=False
    )

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    sns.histplot(diff, kde=True, bins=16, ax=axes[0], color="#0b4f8a")
    axes[0].axvline(0, color="#dc2626", linestyle="--")
    axes[0].set_title("Paired differences (36 wk − booking)")
    for _, row in paired.head(20).iterrows():
        axes[1].plot([0, 1], [row["sbp_booking"], row["sbp_36wk"]],
                    marker="o", alpha=0.45, color="#475569")
    axes[1].set_xticks([0, 1], ["Booking", "36 weeks"])
    axes[1].set_title("First 20 paired profiles")
    plt.tight_layout()
    plt.show()
    plt.close("all")

    print(bp_summary.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"Shapiro-Wilk on differences: W = {shapiro.statistic:.4f}, "
          f"p = {shapiro.pvalue:.4f}")
    print(f"Paired t = {paired_test.statistic:.4f}, p = {paired_test.pvalue:.4g}")
    print(f"Mean change = {diff.mean():.3f} mmHg, "
          f"95% CI [{paired_ci.low:.3f}, {paired_ci.high:.3f}]")
    print(f"Incorrect independent Welch t = {wrong_independent.statistic:.4f}, "
          f"p = {wrong_independent.pvalue:.4g}")
    record("Q5", {
        "summary": bp_summary.to_dict(orient="records"),
        "shapiro_w": float(shapiro.statistic), "shapiro_p": float(shapiro.pvalue),
        "paired_t": float(paired_test.statistic), "paired_p": float(paired_test.pvalue),
        "mean_change": float(diff.mean()),
        "ci": [float(paired_ci.low), float(paired_ci.high)],
        "incorrect_independent_t": float(wrong_independent.statistic),
        "incorrect_independent_p": float(wrong_independent.pvalue),
    })
''').strip() + "\n"

CODE["q6"] = dedent(r'''
    facility_order = ["Urban", "Peri-urban", "Rural"]
    hb_groups = [anc.loc[anc["facility_type"] == f, "hb"].dropna()
                 for f in facility_order]
    hb_summary = pd.DataFrame({
        "facility_type": facility_order,
        "n": [int(g.size) for g in hb_groups],
        "mean": [g.mean() for g in hb_groups],
        "sd": [g.std(ddof=1) for g in hb_groups],
        "median": [g.median() for g in hb_groups],
    })
    levene_hb = st.levene(*hb_groups, center="median")
    anova = st.f_oneway(*hb_groups)
    anova_df_between = len(hb_groups) - 1
    anova_df_within = int(anc["hb"].notna().sum()) - len(hb_groups)
    tukey = pairwise_tukeyhsd(
        anc["hb"].dropna(),
        anc.loc[anc["hb"].notna(), "facility_type"],
        alpha=0.05,
    )
    tukey_data = tukey.summary().data
    tukey_df = pd.DataFrame(tukey_data[1:], columns=tukey_data[0])
    kruskal = st.kruskal(*hb_groups)

    temp = anc.loc[anc["hb"].notna(), ["facility_type", "hb"]].copy()
    temp["residual"] = temp["hb"] - temp.groupby("facility_type")["hb"].transform("mean")
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    sns.boxplot(data=temp, x="facility_type", y="hb", order=facility_order, ax=axes[0])
    axes[0].set_title("Haemoglobin by facility")
    sm.qqplot(temp["residual"], line="45", fit=True, ax=axes[1])
    axes[1].set_title("Q-Q plot of ANOVA residuals")
    sns.scatterplot(x=temp.groupby("facility_type")["hb"].transform("mean"),
                    y=temp["residual"], alpha=0.55, ax=axes[2])
    axes[2].axhline(0, color="#dc2626", linestyle="--")
    axes[2].set_xlabel("Fitted group mean")
    axes[2].set_ylabel("Residual")
    axes[2].set_title("Residuals vs fitted")
    plt.tight_layout()
    plt.show()
    plt.close("all")

    print(hb_summary.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"Levene p = {levene_hb.pvalue:.4f}")
    print(f"One-way ANOVA: F({anova_df_between},{anova_df_within}) = "
          f"{anova.statistic:.3f}, p = {anova.pvalue:.4g}")
    print("\nTukey HSD (multiplicity-adjusted):")
    print(tukey_df.to_string(index=False))
    print(f"\nKruskal-Wallis H = {kruskal.statistic:.4f}, p = {kruskal.pvalue:.4g}")
    record("Q6", {
        "groups": hb_summary.to_dict(orient="records"),
        "levene_p": float(levene_hb.pvalue),
        "anova_f": float(anova.statistic), "anova_p": float(anova.pvalue),
        "anova_df_between": int(anova_df_between),
        "anova_df_within": int(anova_df_within),
        "tukey": tukey_df.to_dict(orient="records"),
        "kruskal_h": float(kruskal.statistic), "kruskal_p": float(kruskal.pvalue),
    })
''').strip() + "\n"

CODE["q7a"] = dedent(r'''
    edu_order = ["None", "Primary", "Secondary+"]
    edu = anc.dropna(subset=["education", "anaemia"]).copy()
    edu["education"] = pd.Categorical(edu["education"], categories=edu_order, ordered=True)
    observed = pd.crosstab(edu["education"], edu["anaemia"])
    row_pct = pd.crosstab(edu["education"], edu["anaemia"], normalize="index") * 100
    col_pct = pd.crosstab(edu["education"], edu["anaemia"], normalize="columns") * 100
    chi2, chi_p, chi_df, expected = st.chi2_contingency(observed)
    min_expected = float(expected.min())

    # Deterministic Monte Carlo alternative, used only if expected counts are inadequate.
    mc_p = None
    if min_expected < 5:
        rng = np.random.default_rng(20261122)
        labels = np.repeat(edu["education"].astype(str).to_numpy(), 1)
        outcomes = edu["anaemia"].astype(int).to_numpy()
        statistic = chi2
        exceed = 0
        replicates = 10000
        for _ in range(replicates):
            permuted = rng.permutation(outcomes)
            simulated = pd.crosstab(labels, permuted)
            sim_stat = st.chi2_contingency(simulated)[0]
            exceed += int(sim_stat >= statistic)
        mc_p = (exceed + 1) / (replicates + 1)

    observed.plot(kind="bar", stacked=True, figsize=(7.5, 4.2), color=["#94a3b8", "#0b4f8a"])
    plt.title("Anaemia by education category (simulated teaching data)")
    plt.xlabel("Education")
    plt.ylabel("Count")
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.show()
    plt.close("all")

    print("Observed counts:")
    print(observed.to_string())
    print("\nRow percentages:")
    print(row_pct.round(1).to_string())
    print("\nColumn percentages:")
    print(col_pct.round(1).to_string())
    print("\nExpected counts:")
    print(pd.DataFrame(expected, index=observed.index,
                       columns=observed.columns).round(2).to_string())
    print(f"\nChi-square = {chi2:.4f}, df = {chi_df}, p = {chi_p:.4g}")
    print(f"Minimum expected count = {min_expected:.2f}")
    if mc_p is not None:
        print(f"Monte Carlo permutation p = {mc_p:.4g}")
    record("Q7a", {
        "observed": observed.to_dict(),
        "row_percent": row_pct.round(3).to_dict(),
        "column_percent": col_pct.round(3).to_dict(),
        "expected": expected.tolist(),
        "chi2": float(chi2), "df": int(chi_df), "p": float(chi_p),
        "min_expected": min_expected,
        "monte_carlo_p": mc_p,
    })
''').strip() + "\n"

CODE["q7b"] = dedent(r'''
    anaemia_complete = anc["anaemia"].dropna().astype(int)
    x = int(anaemia_complete.sum())
    n = int(anaemia_complete.size)
    p_hat = x / n
    exact = st.binomtest(x, n, p=0.30, alternative="two-sided")
    wilson = proportion_confint(x, n, alpha=0.05, method="wilson")
    print(f"Observed proportion = {x}/{n} = {p_hat:.4f}")
    print(f"Null proportion = 0.30")
    print(f"Exact binomial p = {exact.pvalue:.4g}")
    print(f"Wilson 95% CI = [{wilson[0]:.4f}, {wilson[1]:.4f}]")
    record("Q7b", {
        "x": x, "n": n, "p_hat": float(p_hat), "null_p": 0.30,
        "exact_p": float(exact.pvalue),
        "ci": [float(wilson[0]), float(wilson[1])],
    })
''').strip() + "\n"

CODE["q7c"] = dedent(r'''
    sub = anc.dropna(subset=["anaemia"]).copy()
    sub["anaemia"] = sub["anaemia"].astype(int)
    exposed = sub.loc[sub["anaemia"] == 1, "preterm"]
    unexposed = sub.loc[sub["anaemia"] == 0, "preterm"]
    x1, n1 = int(exposed.sum()), int(exposed.size)
    x0, n0 = int(unexposed.sum()), int(unexposed.size)
    p1, p0 = x1 / n1, x0 / n0
    z_stat, z_p = proportions_ztest([x1, x0], [n1, n0])
    diff_ci = confint_proportions_2indep(
        x1, n1, x0, n0, compare="diff", method="newcomb"
    )
    fisher = st.fisher_exact([[x1, n1 - x1], [x0, n0 - x0]])
    table = pd.DataFrame({
        "group": ["Anaemia", "No anaemia"],
        "preterm_events": [x1, x0],
        "denominator": [n1, n0],
        "proportion": [p1, p0],
    })
    print(table.to_string(index=False, formatters={"proportion": lambda v: f"{v:.4f}"}))
    print(f"Difference = {p1 - p0:+.4f}")
    print(f"Newcombe 95% CI = [{diff_ci[0]:.4f}, {diff_ci[1]:.4f}]")
    print(f"Two-proportion z = {z_stat:.4f}, p = {z_p:.4g}")
    print(f"Fisher exact p = {fisher.pvalue:.4g}")
    record("Q7c", {
        "groups": table.to_dict(orient="records"),
        "difference": float(p1 - p0),
        "ci": [float(diff_ci[0]), float(diff_ci[1])],
        "z": float(z_stat), "z_p": float(z_p), "fisher_p": float(fisher.pvalue),
    })
''').strip() + "\n"

CODE["q8a"] = dedent(r'''
    model_simple = smf.ols("birthweight ~ gest_age", data=anc).fit()
    simple_ci = model_simple.conf_int()
    simple_terms = pd.DataFrame({
        "term": model_simple.params.index,
        "coefficient": model_simple.params.values,
        "std_error": model_simple.bse.values,
        "ci_low": simple_ci.iloc[:, 0].values,
        "ci_high": simple_ci.iloc[:, 1].values,
        "p_value": model_simple.pvalues.values,
    })
    sns.regplot(data=anc, x="gest_age", y="birthweight",
                scatter_kws={"alpha": 0.5, "s": 24},
                line_kws={"color": "#d97706"})
    plt.title(f"Simple linear regression: birthweight ~ gest_age "
              f"(slope = {model_simple.params['gest_age']:.1f} g/week)")
    plt.tight_layout()
    plt.show()
    plt.close("all")
    print(simple_terms.to_string(index=False, float_format=lambda v: f"{v:.5g}"))
    print(f"R-squared = {model_simple.rsquared:.4f}; n = {int(model_simple.nobs)}")
    record("Q8a", {
        "terms": simple_terms.to_dict(orient="records"),
        "r_squared": float(model_simple.rsquared), "n": int(model_simple.nobs),
    })
''').strip() + "\n"

CODE["q8b"] = dedent(r'''
    anc_model = anc.dropna(subset=["bmi"]).copy()
    formula_base = (
        "birthweight ~ gest_age + bmi + "
        "C(iptp3, Treatment(reference='No')) + anc_visits"
    )
    model_multi = smf.ols(formula_base, data=anc_model).fit()
    multi_ci = model_multi.conf_int()
    multi_terms = pd.DataFrame({
        "term": model_multi.params.index,
        "coefficient": model_multi.params.values,
        "std_error": model_multi.bse.values,
        "ci_low": multi_ci.iloc[:, 0].values,
        "ci_high": multi_ci.iloc[:, 1].values,
        "p_value": model_multi.pvalues.values,
    })
    print(multi_terms.to_string(index=False, float_format=lambda v: f"{v:.5g}"))
    print(f"R-squared = {model_multi.rsquared:.4f}, "
          f"adjusted R-squared = {model_multi.rsquared_adj:.4f}, "
          f"n = {int(model_multi.nobs)}")
    print("Records excluded for missing BMI:", int(anc["bmi"].isna().sum()))
    record("Q8b", {
        "terms": multi_terms.to_dict(orient="records"),
        "r_squared": float(model_multi.rsquared),
        "adj_r_squared": float(model_multi.rsquared_adj),
        "n": int(model_multi.nobs),
        "missing_bmi_excluded": int(anc["bmi"].isna().sum()),
    })
''').strip() + "\n"

CODE["q8c"] = dedent(r'''
    influence = model_multi.get_influence()
    fitted = model_multi.fittedvalues
    residuals = model_multi.resid
    student_resid = influence.resid_studentized_internal
    leverage = influence.hat_matrix_diag
    cooks = pd.Series(influence.cooks_distance[0], index=anc_model.index)
    top_influential = cooks.sort_values(ascending=False).head(5)
    threshold = 4 / int(model_multi.nobs)

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    sns.scatterplot(x=fitted, y=residuals, alpha=0.65, ax=axes[0, 0])
    axes[0, 0].axhline(0, color="#dc2626", linestyle="--")
    axes[0, 0].set(title="Residuals vs fitted", xlabel="Fitted", ylabel="Residual")
    sm.qqplot(residuals, line="45", fit=True, ax=axes[0, 1])
    axes[0, 1].set_title("Normal Q-Q of residuals")
    sns.scatterplot(x=fitted, y=np.sqrt(np.abs(student_resid)), alpha=0.65, ax=axes[1, 0])
    axes[1, 0].set(title="Scale-location", xlabel="Fitted",
                   ylabel="sqrt(|studentised residual|)")
    sns.scatterplot(x=leverage, y=student_resid, size=cooks, sizes=(12, 160),
                    alpha=0.6, ax=axes[1, 1])
    axes[1, 1].axhline(0, color="#dc2626", linestyle="--")
    axes[1, 1].axvline(threshold, color="#d97706", linestyle=":")
    axes[1, 1].set(title="Leverage vs studentised residual (bubble = Cook's D)",
                   xlabel="Leverage", ylabel="Studentised residual")
    plt.tight_layout()
    plt.show()
    plt.close("all")

    print(f"Durbin-Watson statistic = {durbin_watson(residuals):.4f}")
    print(f"Cook's D warning threshold 4/n = {threshold:.5f}")
    print("Largest Cook's D values (row index, value):")
    print(top_influential.round(5).to_string())
    record("Q8c", {
        "durbin_watson": float(durbin_watson(residuals)),
        "cooks_threshold": float(threshold),
        "top_cooks": [float(v) for v in top_influential.values],
    })
''').strip() + "\n"

CODE["q8d"] = dedent(r'''
    formula_extended = formula_base + (
        " + C(facility_type, Treatment(reference='Urban'))"
    )
    model_extended = smf.ols(formula_extended, data=anc_model).fit()
    anova_models = sm.stats.anova_lm(model_multi, model_extended)
    print("Nested-model comparison (base vs + facility_type):")
    print(anova_models.to_string(float_format=lambda v: f"{v:.6g}"))
    print(f"AIC base = {model_multi.aic:.2f}")
    print(f"AIC extended = {model_extended.aic:.2f}")
    print(f"Adjusted R2 base = {model_multi.rsquared_adj:.4f}")
    print(f"Adjusted R2 extended = {model_extended.rsquared_adj:.4f}")
    print(f"Complete-case n used for both models = {int(model_multi.nobs)}")
    record("Q8d", {
        "f_statistic": float(anova_models.loc[1, "F"]),
        "p_value": float(anova_models.loc[1, "Pr(>F)"]),
        "df_diff": int(anova_models.loc[1, "df_diff"]),
        "aic_base": float(model_multi.aic),
        "aic_extended": float(model_extended.aic),
        "adj_r2_base": float(model_multi.rsquared_adj),
        "adj_r2_extended": float(model_extended.rsquared_adj),
        "n": int(model_multi.nobs),
    })
''').strip() + "\n"

CODE["q8e"] = dedent(r'''
    hypothetical = pd.DataFrame({
        "gest_age": [39.0], "bmi": [22.0], "iptp3": ["Yes"], "anc_visits": [5],
    })
    prediction = model_multi.get_prediction(hypothetical).summary_frame(alpha=0.05)
    hypothetical_with_facility = hypothetical.copy()
    hypothetical_with_facility["facility_type"] = "Urban"
    prediction_urban = model_extended.get_prediction(
        hypothetical_with_facility
    ).summary_frame(alpha=0.05)
    print("Model without facility type (Q8b):")
    print(prediction.to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    print("\nModel with facility type, assuming Urban (Q8d):")
    print(prediction_urban.to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    record("Q8e", {
        "model_without_facility": prediction.iloc[0].to_dict(),
        "model_with_facility_urban": prediction_urban.iloc[0].to_dict(),
    })
''').strip() + "\n"

CODE["q9"] = dedent(r'''
    logit_df = anc.dropna(subset=["anaemia"]).copy()
    logit_df["anaemia"] = logit_df["anaemia"].astype(int)
    model_logit = smf.logit(
        "preterm ~ age + anaemia + anc_visits", data=logit_df
    ).fit(disp=False)
    logit_ci = model_logit.conf_int()
    logit_terms = pd.DataFrame({
        "term": model_logit.params.index,
        "coefficient": model_logit.params.values,
        "std_error": model_logit.bse.values,
        "odds_ratio": np.exp(model_logit.params.values),
        "or_ci_low": np.exp(logit_ci.iloc[:, 0].values),
        "or_ci_high": np.exp(logit_ci.iloc[:, 1].values),
        "p_value": model_logit.pvalues.values,
    })
    scenarios = pd.DataFrame({
        "age": [25.0, 25.0], "anaemia": [0, 1], "anc_visits": [4.0, 4.0],
    })
    scenario_probabilities = model_logit.predict(scenarios)

    visits_grid = np.arange(1, 11, dtype=float)
    curve = pd.DataFrame({
        "anc_visits": np.tile(visits_grid, 2),
        "anaemia": np.repeat([0, 1], visits_grid.size),
        "age": 25.0,
    })
    curve["predicted_probability"] = model_logit.predict(curve)
    sns.lineplot(data=curve, x="anc_visits", y="predicted_probability",
                 hue="anaemia", marker="o")
    plt.title("Model-based preterm probability by ANC visits and anaemia (age = 25)")
    plt.ylabel("Predicted probability")
    plt.tight_layout()
    plt.show()
    plt.close("all")

    print(logit_terms.to_string(index=False, float_format=lambda v: f"{v:.5g}"))
    print(f"Pseudo R-squared = {model_logit.prsquared:.4f}; n = {int(model_logit.nobs)}")
    for label, probability in zip(["No anaemia", "Anaemia"], scenario_probabilities):
        print(f"{label}: predicted probability = {probability:.4f}")
    record("Q9", {
        "terms": logit_terms.to_dict(orient="records"),
        "pseudo_r_squared": float(model_logit.prsquared),
        "n": int(model_logit.nobs),
        "scenario_probabilities": {
            "no_anaemia": float(scenario_probabilities.iloc[0]),
            "anaemia": float(scenario_probabilities.iloc[1]),
        },
    })
''').strip() + "\n"

CODE["q10a"] = dedent(r'''
    n_surv = int(surv.shape[0])
    events = int(surv["readmitted"].sum())
    censored = int(n_surv - events)
    censoring_proportion = censored / n_surv
    median_follow_up = float(surv["time_days"].median())
    print(f"Participants: {n_surv}")
    print(f"Readmission events: {events}")
    print(f"Censored: {censored} ({censoring_proportion * 100:.1f}%)")
    print(f"Median observed follow-up time: {median_follow_up:.1f} days")
    print("Median observed follow-up is NOT the same as median survival time.")
    record("Q10a", {
        "participants": n_surv, "events": events, "censored": censored,
        "censoring_proportion": float(censoring_proportion),
        "median_observed_follow_up": median_follow_up,
    })
''').strip() + "\n"

CODE["q10b"] = dedent(r'''
    km_all = SurvfuncRight(surv["time_days"], surv["readmitted"])
    km_times = km_all.surv_times
    km_probs = km_all.surv_prob
    km_se = km_all.surv_prob_se


    def km_survival_at(time_point):
        idx = int(np.searchsorted(km_times, time_point, side="right")) - 1
        return 1.0 if idx < 0 else float(km_probs[idx]), idx


    def km_loglog_ci(time_point):
        probability, idx = km_survival_at(time_point)
        if idx < 0:
            return 1.0, 1.0
        se = float(km_se[idx])
        if probability <= 0 or probability >= 1:
            return probability, probability
        factor = 1.96 * se / (probability * np.log(probability))
        return (float(probability ** np.exp(-factor)),
                float(probability ** np.exp(factor)))


    s90, _ = km_survival_at(90)
    s180, _ = km_survival_at(180)
    ci90 = km_loglog_ci(90)
    ci180 = km_loglog_ci(180)
    try:
        median_survival = float(km_all.quantile(0.5))
        median_ci_raw = km_all.quantile_ci(0.5)
        median_ci = [float(v) for v in median_ci_raw]
    except Exception as exc:  # pragma: no cover - depends on follow-up
        median_survival = None
        median_ci = None

    lower = np.array([km_loglog_ci(float(t))[0] for t in km_times])
    upper = np.array([km_loglog_ci(float(t))[1] for t in km_times])
    fig, (ax, risk_ax) = plt.subplots(
        2, 1, figsize=(9, 6.5), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )
    ax.step(np.r_[0, km_times], np.r_[1, km_probs], where="post",
            color="#0b4f8a", label="Kaplan-Meier")
    ax.fill_between(np.r_[0, km_times], np.r_[1, lower], np.r_[1, upper],
                    step="post", alpha=0.18, color="#0b4f8a",
                    label="95% pointwise CI")
    ax.set_ylim(0, 1.02)
    ax.set_ylabel("Survival probability")
    ax.set_title("Kaplan-Meier estimate of post-partum readmission-free survival")
    ax.legend(loc="lower left")

    risk_times = [0, 90, 180, 270, 365]
    at_risk = [int((surv["time_days"] >= t).sum()) for t in risk_times]
    risk_ax.set_axis_off()
    table = risk_ax.table(
        cellText=[["t (days)"] + [str(t) for t in risk_times],
                  ["at risk"] + [str(v) for v in at_risk]],
        cellLoc="center", loc="top",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.6)
    plt.tight_layout()
    plt.show()
    plt.close("all")

    print(f"Survival at 90 days: {s90:.4f} (95% CI {ci90[0]:.4f} to {ci90[1]:.4f})")
    print(f"Survival at 180 days: {s180:.4f} (95% CI {ci180[0]:.4f} to {ci180[1]:.4f})")
    print(f"Median survival: {median_survival}")
    print("Number at risk at 0/90/180/270/365 days:", at_risk)
    record("Q10b", {
        "survival_90": s90, "ci_90": list(ci90),
        "survival_180": s180, "ci_180": list(ci180),
        "median_survival": median_survival, "median_ci": median_ci,
        "number_at_risk": dict(zip([str(t) for t in risk_times], at_risk)),
    })
''').strip() + "\n"

CODE["q10c"] = dedent(r'''
    strata = ["Anaemia", "No anaemia"]
    km_by_group = {
        group: SurvfuncRight(
            surv.loc[surv["anaemia"] == group, "time_days"],
            surv.loc[surv["anaemia"] == group, "readmitted"],
        )
        for group in strata
    }

    # Standard two-group log-rank test.
    event_times = np.sort(surv.loc[surv["readmitted"] == 1, "time_days"].unique())
    observed = expected = variance = 0.0
    for time_point in event_times:
        at_risk_all = int((surv["time_days"] >= time_point).sum())
        at_risk_a = int(((surv["time_days"] >= time_point) &
                         (surv["anaemia"] == "Anaemia")).sum())
        events_all = int(((surv["time_days"] == time_point) &
                          (surv["readmitted"] == 1)).sum())
        events_a = int(((surv["time_days"] == time_point) &
                        (surv["readmitted"] == 1) &
                        (surv["anaemia"] == "Anaemia")).sum())
        proportion = at_risk_a / at_risk_all
        observed += events_a
        expected += events_all * proportion
        if at_risk_all > 1:
            variance += (events_all * proportion * (1 - proportion) *
                         (at_risk_all - events_all) / (at_risk_all - 1))
    logrank_chi2 = (observed - expected) ** 2 / variance
    logrank_p = float(st.chi2.sf(logrank_chi2, df=1))

    fig, ax = plt.subplots(figsize=(9, 5.2))
    colors = {"Anaemia": "#b45309", "No anaemia": "#0b4f8a"}
    for group in strata:
        km = km_by_group[group]
        ax.step(np.r_[0, km.surv_times], np.r_[1, km.surv_prob], where="post",
                label=group, color=colors[group])
    ax.set(title="Kaplan-Meier curves by anaemia status",
           xlabel="Days post-partum", ylabel="Survival probability")
    ax.set_ylim(0, 1.02)
    ax.legend()
    plt.tight_layout()
    plt.show()
    plt.close("all")

    print(f"Log-rank chi-square(1) = {logrank_chi2:.4f}, p = {logrank_p:.4g}")
    for group in strata:
        km = km_by_group[group]
        idx90 = int(np.searchsorted(km.surv_times, 90, side="right")) - 1
        print(f"{group}: n = {int((surv['anaemia'] == group).sum())}, "
              f"S(90) = {km.surv_prob[idx90]:.4f}" if idx90 >= 0 else group)
    record("Q10c", {
        "logrank_chi2": float(logrank_chi2), "logrank_p": logrank_p,
        "groups": strata,
        "median_survival": {
            group: (float(km_by_group[group].quantile(0.5))
                    if np.isfinite(km_by_group[group].quantile(0.5)) else None)
            for group in strata
        },
    })
''').strip() + "\n"

CODE["q10d"] = dedent(r'''
    total_person_time = float(surv["time_days"].sum())
    rate = events / total_person_time
    rate_per_1000 = rate * 1000
    rate_ci = (
        float(st.chi2.ppf(0.025, 2 * events) / (2 * total_person_time)),
        float(st.chi2.ppf(0.975, 2 * events + 2) / (2 * total_person_time)),
    )
    exponential_s90 = float(np.exp(-rate * 90))
    exponential_s180 = float(np.exp(-rate * 180))
    print(f"Events = {events}")
    print(f"Total person-time = {total_person_time:,.0f} person-days")
    print(f"Rate = {rate:.6f} per person-day = {rate_per_1000:.3f} per 1,000 person-days")
    print(f"Exact Poisson 95% CI = [{rate_ci[0]:.6f}, {rate_ci[1]:.6f}] per person-day")
    print(f"Exponential model S(90) = {exponential_s90:.4f}, "
          f"S(180) = {exponential_s180:.4f}")
    record("Q10d", {
        "events": events, "person_time_days": total_person_time,
        "rate_per_person_day": float(rate),
        "rate_per_1000_person_days": float(rate_per_1000),
        "ci_per_1000_person_days": [rate_ci[0] * 1000, rate_ci[1] * 1000],
        "exponential_s90": exponential_s90,
        "exponential_s180": exponential_s180,
    })
''').strip() + "\n"

CODE["q10e"] = dedent(r'''
    cox_design = pd.DataFrame({
        "anaemia": (surv["anaemia"] == "Anaemia").astype(float),
        "caesarean": (surv["delivery_mode"] == "Caesarean").astype(float),
        "age": surv["age"].astype(float),
    })
    cox_model = PHReg(
        endog=surv["time_days"].to_numpy(dtype=float),
        exog=cox_design.to_numpy(dtype=float),
        status=surv["readmitted"].to_numpy(dtype=int),
    ).fit()
    cox_ci = cox_model.conf_int()
    cox_terms = pd.DataFrame({
        "term": cox_design.columns,
        "coefficient": cox_model.params,
        "hazard_ratio": np.exp(cox_model.params),
        "hr_ci_low": np.exp(cox_ci[:, 0]),
        "hr_ci_high": np.exp(cox_ci[:, 1]),
        "p_value": cox_model.pvalues,
    })
    print(cox_terms.to_string(index=False, float_format=lambda v: f"{v:.5g}"))
    print("\nReference levels: anaemia = No anaemia; delivery_mode = Vaginal; "
          "age = per one-year increase.")
    record("Q10e", cox_terms.to_dict(orient="records"))
''').strip() + "\n"

CODE["q10f"] = dedent(r'''
    schoenfeld = pd.DataFrame(
        cox_model.schoenfeld_residuals, columns=cox_design.columns
    )
    schoenfeld["time_days"] = surv["time_days"].to_numpy()
    plot_data = schoenfeld.dropna(subset=list(cox_design.columns)).copy()
    plot_data["log_time"] = np.log(plot_data["time_days"])

    ph_rows = []
    for term in cox_design.columns:
        rho, p_value = st.spearmanr(plot_data[term], plot_data["log_time"])
        ph_rows.append({
            "term": term,
            "spearman_rho": float(rho),
            "p_value": float(p_value),
        })
    ph_tests = pd.DataFrame(ph_rows)
    reject, p_holm, _, _ = multipletests(ph_tests["p_value"], method="holm")
    ph_tests["p_holm"] = p_holm
    ph_tests["flag_ph_concern"] = reject

    fig, axes = plt.subplots(1, len(cox_design.columns), figsize=(13, 3.8))
    for axis, term in zip(np.atleast_1d(axes), cox_design.columns):
        axis.scatter(plot_data["log_time"], plot_data[term], alpha=0.5, s=18)
        slope, intercept = np.polyfit(plot_data["log_time"], plot_data[term], 1)
        x_line = np.linspace(plot_data["log_time"].min(),
                             plot_data["log_time"].max(), 50)
        axis.plot(x_line, intercept + slope * x_line, color="#dc2626")
        axis.set(title=f"Schoenfeld: {term}", xlabel="log(time)", ylabel="Residual")
    plt.tight_layout()
    plt.show()
    plt.close("all")

    print(ph_tests.to_string(index=False, float_format=lambda v: f"{v:.5g}"))
    print("This is a Schoenfeld-residual screening test using statsmodels 0.15; "
          "it is not an exact R cox.zph replacement.")
    record("Q10f", ph_tests.to_dict(orient="records"))
''').strip() + "\n"

CODE["results"] = dedent(r'''
    print("MNH_VERIFIED_RESULTS_JSON:" +
          json.dumps(RESULTS, ensure_ascii=False, sort_keys=True, default=str))
''').strip() + "\n"

# Which code cells appear inside each navigation card.
QUESTION_CODE = {
    "Q1a": ["q1a"], "Q1b": ["q1b"],
    "Q2a": [], "Q2b": ["q2b"], "Q2c": ["q2c"], "Q2d": ["q2d"],
    "Q3a": ["q3a"], "Q3b": ["q3b"], "Q3c": [], "Q3d": ["q3d"],
    "Q4": ["q4"], "Q5": ["q5"], "Q6": ["q6"],
    "Q7a": ["q7a"], "Q7b": ["q7b"], "Q7c": ["q7c"],
    "Q8a": ["q8a"], "Q8b": ["q8b"], "Q8c": ["q8c"],
    "Q8d": ["q8d"], "Q8e": ["q8e"],
    "Q9": ["q9"],
    "Q10a": ["q10a"], "Q10b": ["q10b"], "Q10c": ["q10c"],
    "Q10d": ["q10d"], "Q10e": ["q10e"], "Q10f": ["q10f"],
}

QUESTION_OF = {
    qid: ("Q" + qid.split("(")[0][1:] if "(" in qid else qid)
    for qid in QUESTION_CODE
}

QUESTION_TITLES = {
    "Q1": "Probability and probability distributions",
    "Q2": "Descriptive statistics and correlation",
    "Q3": "Estimation and confidence intervals",
    "Q4": "Comparing mean birthweight by IPTp3 status",
    "Q5": "Paired t-test for blood pressure",
    "Q6": "ANOVA and non-parametric comparison",
    "Q7": "Categorical data and proportions",
    "Q8": "Linear regression",
    "Q9": "Logistic regression",
    "Q10": "Survival analysis",
}

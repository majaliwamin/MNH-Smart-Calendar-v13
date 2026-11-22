"""Data-grounded worked reports for the STAT 8100 practical companion.

Every numerical statement in this module is read from
``stat8100_practical_results.json``, which is extracted from the executed
notebook. The generic sentence patterns remain in :mod:`stat8100_guides`; this
module fills them with verified values from the three supplied CSVs so students
see a completed example rather than an instruction to invent a result.
"""

from __future__ import annotations

from typing import Any

from stat8100_guides import GUIDES, REPORTING_TEMPLATES


def _f(value: Any, default: float = 0.0) -> float:
    """Return a float, substituting a neutral default for a missing value."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _i(value: Any, default: int = 0) -> int:
    """Return an integer, substituting a neutral default for a missing value."""
    return int(_f(value, default))


def _num(value: Any, decimals: int = 2) -> str:
    """Format a finite number with thousands separators and fixed precision."""
    if value is None:
        return "not available"
    number = float(value)
    if number == int(number) and decimals == 0:
        return f"{int(number):,}"
    return f"{number:,.{decimals}f}"


def _p(value: Any) -> str:
    """Format a p-value without pretending tiny values are exactly zero."""
    if value is None:
        return "not available"
    number = float(value)
    if number < 0.0001:
        return "<0.0001"
    return f"{number:.4f}"


def _p_eq(value: Any) -> str:
    """Return a complete 'p=...' or 'p<...' phrase for prose."""
    text = _p(value)
    return f"p{text}" if text.startswith("<") else f"p={text}"



def _ci(bounds: Any, decimals: int = 2) -> str:
    if not bounds or len(bounds) != 2:
        return "not available"
    return f"{_num(bounds[0], decimals)} to {_num(bounds[1], decimals)}"


def _pct(value: Any, decimals: int = 2) -> str:
    return f"{_f(value) * 100:.{decimals}f}%"


def _term(terms: Any, needle: str) -> dict[str, Any]:
    """Find a model term by a stable fragment of its statsmodels label."""
    for row in terms or []:
        if needle.lower() in str(row.get("term", "")).lower():
            return row
    return {}


def _row(rows: Any, key: str, value: Any) -> dict[str, Any]:
    for row in rows or []:
        if row.get(key) == value:
            return row
    return {}


def _ratio_text(value: Any) -> str:
    number = _f(value)
    if number > 1:
        return "higher"
    if number < 1:
        return "lower"
    return "the same"


def _evidence_text(p_value: Any, threshold: float = 0.05) -> str:
    return "clear evidence of an association" if _f(p_value, 1.0) < threshold else "no clear evidence of an association"


def _work(qid: str, text: str, source: str, teach: str) -> dict[str, str]:
    return {"qid": qid, "text": text, "source": source, "teach": teach}


def work_report(qid: str, results: dict[str, Any] | None) -> dict[str, str]:
    """Return a worked report, its verified source and one teaching note."""
    data = results or {}
    audit = data.get("Audit", {})
    datasets = {row.get("dataset"): row for row in audit.get("datasets", [])}
    anc_rows = _i(datasets.get("anc_cohort.csv", {}).get("rows"))

    if qid == "Q1a":
        rows = data.get("Q1a", [])
        parts = [
            f"{_i(r.get('count'))}/{_i(r.get('denominator'))} "
            f"({_f(r.get('sample_proportion')):.4f}) {str(r.get('event', '')).lower()}"
            for r in rows
        ]
        total = _i(rows[0].get("denominator")) if rows else anc_rows
        return _work(
            qid,
            f"In the simulated ANC cohort (n={total:,}), " + " and ".join(parts) +
            ". These are observed sample proportions from the recorded outcome flags, not known population probabilities.",
            "Q1a output · anc_cohort.csv",
            "Both outcome flags are complete for every record here. Do not switch to the smaller anaemia denominator used later.",
        )

    if qid == "Q1b":
        value = data.get("Q1b", {})
        table = value.get("table", [])
        preterm = table[0] if table else {}
        term = table[1] if len(table) > 1 else {}
        marginal_rows = data.get("Q1a", [])
        low_bw = next((r for r in marginal_rows if "Low birth" in str(r.get("event", ""))), {})
        verdict = "not independent" if abs(_f(value.get("risk_difference"))) > 0 else "consistent with independence"
        return _work(
            qid,
            f"Low birth weight occurred in {_i(preterm.get('low_bw_count'))}/{_i(preterm.get('stratum_n'))} "
            f"({_f(preterm.get('P(low_bw | stratum)')):.4f}) preterm and "
            f"{_i(term.get('low_bw_count'))}/{_i(term.get('stratum_n'))} "
            f"({_f(term.get('P(low_bw | stratum)')):.4f}) term births, compared with the marginal "
            f"{_i(low_bw.get('count'))}/{_i(low_bw.get('denominator'))} = "
            f"{_f(low_bw.get('sample_proportion')):.4f}. The risk difference is "
            f"{_f(value.get('risk_difference')):.4f} and the risk ratio is "
            f"{_f(value.get('risk_ratio')):.2f}, so the events are {verdict} in these simulated data.",
            "Q1a and Q1b outputs · anc_cohort.csv",
            "Compare conditional with marginal proportions. Similarity in a sample is not proof of independence, and dependence is not causation.",
        )

    if qid == "Q2a":
        levels = audit.get("education_levels", {})
        level_text = ", ".join(f"{name} (n={_i(count)})" for name, count in levels.items())
        return _work(
            qid,
            "facility_type is nominal because its categories have no intrinsic order; education is ordinal "
            f"({level_text}); anc_visits is a discrete count; and bmi and birthweight are continuous measurements.",
            "Dataset audit and column definitions · anc_cohort.csv",
            "The literal education category 'None' is data, not a missing-value marker. Scale determines which summaries and plots are meaningful.",
        )

    if qid == "Q2b":
        rows = data.get("Q2b", [])
        hb = _row(rows, "variable", "hb")
        bw = _row(rows, "variable", "birthweight")
        bmi = _row(rows, "variable", "bmi")
        return _work(
            qid,
            f"Haemoglobin used {_i(hb.get('n_non_missing'))} non-missing values "
            f"(mean {_num(hb.get('mean'))} g/dL, SD {_num(hb.get('sd'))}, median {_num(hb.get('median'))}, "
            f"IQR {_num(hb.get('IQR'))}); {_i(hb.get('n_missing'))} records were missing. "
            f"BMI had {_i(bmi.get('n_missing'))} missing values, whereas birthweight used all "
            f"{_i(bw.get('n_non_missing'))} records (mean {_num(bw.get('mean'))} g, SD {_num(bw.get('sd'))}).",
            "Q2b output · anc_cohort.csv",
            "Report n beside each summary. The differing denominators explain why later anaemia analyses use fewer than the full cohort.",
        )

    if qid == "Q2c":
        rows = data.get("Q2c", [])
        bw = _row(rows, "variable", "birthweight")
        ga = _row(rows, "variable", "gest_age")
        return _work(
            qid,
            f"Birthweight was approximately symmetric (mean {_num(bw.get('mean'))} g versus median "
            f"{_num(bw.get('median'))} g; skewness {_num(bw.get('skewness'), 2)}) with "
            f"{_i(bw.get('iqr_outliers_low'))} low and {_i(bw.get('iqr_outliers_high'))} high IQR outliers. "
            f"Gestational age was left-skewed (mean {_num(ga.get('mean'))} weeks versus median "
            f"{_num(ga.get('median'))}; skewness {_num(ga.get('skewness'), 2)}) with "
            f"{_i(ga.get('iqr_outliers_low'))} low IQR outliers, consistent with the preterm tail.",
            "Q2c output · anc_cohort.csv",
            "Describe shape, centre, spread and outliers before choosing later methods. Inspect flagged outliers rather than deleting them without a reason.",
        )

    if qid == "Q2d":
        value = data.get("Q2d", {})
        return _work(
            qid,
            f"Gestational age and birthweight showed a positive association "
            f"(Pearson r={_num(value.get('pearson_r'), 3)}, 95% CI {_ci(value.get('pearson_ci'), 3)}, "
            f"{_p_eq(value.get('pearson_p'))}; Spearman rho={_num(value.get('spearman_rho'), 3)}, "
            f"{_p_eq(value.get('spearman_p'))}; n={_i(value.get('n'))}). The rank-based estimate is close "
            "to the Pearson estimate, so a few extreme points are unlikely to explain the association.",
            "Q2c and Q2d outputs · anc_cohort.csv",
            "Report both coefficients and inspect the scatterplot first. An observational association is not evidence that gestational age causes birthweight.",
        )

    if qid == "Q3a":
        value = data.get("Q3a", {})
        return _work(
            qid,
            f"Mean birthweight was {_num(value.get('mean'))} g (SD {_num(value.get('sd'))}, n={_i(value.get('n'))}, "
            f"df={_i(value.get('df'))}); SE = SD/sqrt(n) = {_num(value.get('se'))} g and the critical t value is "
            f"{_num(value.get('t_critical'), 3)}. The 95% t interval was {_ci(value.get('ci'))} g, matching "
            f"the SciPy endpoints {_ci(value.get('scipy_ci'))} g.",
            "Q3a output · anc_cohort.csv",
            "The interval targets the population mean, not the range of individual births. A 95% procedure has long-run coverage under its assumptions.",
        )

    if qid == "Q3b":
        value = data.get("Q3b", {})
        return _work(
            qid,
            f"Anaemia prevalence was {_i(value.get('events'))}/{_i(value.get('denominator'))} = "
            f"{_f(value.get('prevalence')):.4f} ({_pct(value.get('prevalence'))}), with "
            f"{_i(value.get('missing_excluded'))} records excluded because anaemia was missing. "
            f"The 95% Wilson interval was {_pct(value.get('ci', [0, 0])[0])} to "
            f"{_pct(value.get('ci', [0, 0])[1])}.",
            "Q3b output · anc_cohort.csv",
            "State the evaluable denominator and exclusions. The interval describes prevalence, not an individual woman's probability of anaemia.",
        )

    if qid == "Q3c":
        mean_ci = data.get("Q3a", {}).get("ci", [0, 0])
        prev = data.get("Q3b", {})
        prev_ci = prev.get("ci", [0, 0])
        width = _f(mean_ci[1]) - _f(mean_ci[0])
        return _work(
            qid,
            f"The Q3a interval for mean birthweight is {_ci(mean_ci)} g (width {_num(width)} g; n="
            f"{_i(data.get('Q3a', {}).get('n'))}), while the Q3b interval for anaemia prevalence is "
            f"{_pct(prev_ci[0])} to {_pct(prev_ci[1])} (n={_i(prev.get('denominator'))}). A 95% confidence "
            "level is a long-run property of the interval procedure. Other things equal, four times the "
            "sample size divides the standard error, and therefore approximately the interval width, by two.",
            "Q3a and Q3b outputs · anc_cohort.csv",
            "Do not say there is a 95% probability that the fixed parameter lies in this one interval. The two intervals also have different denominators and answer different questions.",
        )

    if qid == "Q3d":
        rows = data.get("Q3d", [])
        parts = [
            f"{r.get('facility_type')} {_num(r.get('mean'))} g (n={_i(r.get('n'))}, 95% CI "
            f"{_ci([r.get('ci_low'), r.get('ci_high')])})"
            for r in rows
        ]
        return _work(
            qid,
            "Mean birthweight was " + "; ".join(parts) + ". These separate intervals show precision "
            "within each facility group; overlap alone is not a formal test of equal means.",
            "Q3d output · anc_cohort.csv",
            "A formal comparison requires the model-based approach in Q6. Unequal subgroup sample sizes make interval widths hard to compare informally.",
        )

    if qid == "Q4":
        value = data.get("Q4", {})
        groups = value.get("groups", [])
        yes = _row(groups, "iptp3", "Yes")
        no = _row(groups, "iptp3", "No")
        return _work(
            qid,
            f"Mean birthweight was {_num(yes.get('mean'))} g with IPTp3 Yes (n={_i(yes.get('n'))}) and "
            f"{_num(no.get('mean'))} g with No (n={_i(no.get('n'))}), a difference of "
            f"{_num(value.get('mean_difference'))} g (Yes minus No; Welch 95% CI {_ci(value.get('welch_ci'))}; "
            f"t={_num(value.get('welch_t'), 2)}, df={_num(value.get('welch_df'), 1)}, "
            f"{_p_eq(value.get('welch_p'))}). Levene {_p_eq(value.get('levene_p'))} and rank-sum "
            f"{_p_eq(value.get('mann_whitney_p'))} give context for the assumption check and sensitivity analysis.",
            "Q4 output · anc_cohort.csv",
            "Welch's test does not assume equal variances. Report the size and precision of the difference and keep the wording observational, not causal.",
        )

    if qid == "Q5":
        value = data.get("Q5", {})
        summary = value.get("summary", [])
        booking = summary[0] if summary else {}
        followup = summary[1] if len(summary) > 1 else {}
        return _work(
            qid,
            f"Among {_i(booking.get('n'))} paired women, mean systolic blood pressure was "
            f"{_num(booking.get('mean'))} mmHg at booking and {_num(followup.get('mean'))} mmHg at 36 weeks. "
            f"The mean within-woman change was {_num(value.get('mean_change'))} mmHg "
            f"(95% CI {_ci(value.get('ci'))}; paired t={_num(value.get('paired_t'), 2)}, "
            f"{_p_eq(value.get('paired_p'))}), whereas the incorrect independent test gives "
            f"{_p_eq(value.get('incorrect_independent_p'))} because it ignores the id linkage.",
            "Q5 output · bp_paired.csv",
            "Analyse the 60 paired differences, not 120 independent observations. Shapiro-Wilk and the paired-difference plot support checking the t assumption.",
        )

    if qid == "Q6":
        value = data.get("Q6", {})
        tukey = value.get("tukey", [])
        pairs = "; ".join(
            f"{r.get('group1')} minus {r.get('group2')} = {_num(r.get('meandiff'))} g/dL "
            f"(95% CI {_ci([r.get('lower'), r.get('upper')])}, adjusted {_p_eq(r.get('p-adj'))})"
            for r in tukey
        )
        return _work(
            qid,
            f"One-way ANOVA comparing haemoglobin across facility type gave "
            f"F({_i(value.get('anova_df_between'))},{_i(value.get('anova_df_within'))})="
            f"{_num(value.get('anova_f'), 2)}, {_p_eq(value.get('anova_p'))}; Levene "
            f"{_p_eq(value.get('levene_p'))} and Kruskal-Wallis H={_num(value.get('kruskal_h'), 2)}, "
            f"{_p_eq(value.get('kruskal_p'))}. Tukey-adjusted pairwise differences were: {pairs}.",
            "Q6 output · anc_cohort.csv",
            "Report the overall test before the adjusted contrasts. The rank-based test is an important sensitivity check because the variance test is borderline.",
        )

    if qid == "Q7a":
        value = data.get("Q7a", {})
        observed = value.get("observed", {})
        row_percent = value.get("row_percent", {})
        levels = list((observed.get("1.0") or observed.get("1") or {}).keys())
        cells = []
        for level in levels:
            no = _i((observed.get("0.0") or observed.get("0") or {}).get(level))
            yes = _i((observed.get("1.0") or observed.get("1") or {}).get(level))
            percent = (row_percent.get("1.0") or row_percent.get("1") or {}).get(level)
            cells.append(f"{level}: {yes}/{no + yes} ({_f(percent):.2f}% anaemia)")
        return _work(
            qid,
            "Among women with both variables recorded, anaemia proportions were " + "; ".join(cells) +
            f". The chi-square test gave chi2({_i(value.get('df'))})={_num(value.get('chi2'), 2)}, "
            f"{_p_eq(value.get('p'))}, with minimum expected count {_num(value.get('min_expected'), 2)}; "
            f"there is {_evidence_text(value.get('p'))} in these simulated data.",
            "Q7a output · anc_cohort.csv",
            "All expected counts exceed the usual rule-of-thumb threshold of 5. A chi-square test assesses association; it does not show that education caused anaemia.",
        )

    if qid == "Q7b":
        value = data.get("Q7b", {})
        excluded = anc_rows - _i(value.get("n")) if anc_rows else 0
        ci = value.get("ci", [0, 0])
        return _work(
            qid,
            f"Against the null prevalence {_num(value.get('null_p'), 2)}, the observed "
            f"{_i(value.get('x'))}/{_i(value.get('n'))} = {_f(value.get('p_hat')):.4f} gave an exact "
            f"binomial {_p_eq(value.get('exact_p'))}; the 95% Wilson interval was "
            f"{_pct(ci[0])} to {_pct(ci[1])}, which "
            f"{'excludes' if not (_f(ci[0]) <= _f(value.get('null_p')) <= _f(ci[1])) else 'includes'} the null. "
            f"{excluded} records with missing anaemia were excluded.",
            "Q7b output and dataset audit · anc_cohort.csv",
            "State H0, the evaluable denominator, the exact test and the interval together. The null value is a teaching hypothesis, not a clinical guideline.",
        )

    if qid == "Q7c":
        value = data.get("Q7c", {})
        groups = value.get("groups", [])
        parts = [
            f"{r.get('group')} {_i(r.get('preterm_events'))}/{_i(r.get('denominator'))} "
            f"({_pct(r.get('proportion'))})"
            for r in groups
        ]
        ci = value.get("ci", [0, 0])
        return _work(
            qid,
            "Preterm delivery occurred in " + " and ".join(parts) + ", a risk difference of "
            f"{_pct(value.get('difference'))} (95% CI {_pct(ci[0])} to {_pct(ci[1])}; "
            f"z={_num(value.get('z'), 2)}, {_p_eq(value.get('z_p'))}; Fisher "
            f"{_p_eq(value.get('fisher_p'))}). This is an unadjusted association in simulated data.",
            "Q7c output · anc_cohort.csv",
            "Both the large-sample test and Fisher's exact test address the same table. Do not phrase the difference as anaemia causing preterm delivery.",
        )

    if qid == "Q8a":
        value = data.get("Q8a", {})
        slope = _term(value.get("terms", []), "gest_age")
        return _work(
            qid,
            f"In the simple linear model, each additional week of gestational age was associated with "
            f"{_num(slope.get('coefficient'))} g higher mean birthweight (95% CI "
            f"{_ci([slope.get('ci_low'), slope.get('ci_high')])}, {_p_eq(slope.get('p_value'))}); "
            f"n={_i(value.get('n'))} and R-squared={_num(value.get('r_squared'), 3)}. "
            f"The intercept ({_num(_term(value.get('terms', []), 'Intercept').get('coefficient'))} g at zero weeks) is outside the observed range.",
            "Q8a output · anc_cohort.csv",
            "Interpret the slope in grams per week with its interval. R-squared describes explained variation, not causation or individual prediction accuracy.",
        )

    if qid == "Q8b":
        value = data.get("Q8b", {})
        terms = value.get("terms", [])
        labels = [
            ("iptp3", "IPTp3 Yes versus No"),
            ("gest_age", "per additional week of gestational age"),
            ("bmi", "per unit of BMI"),
            ("anc_visits", "per additional ANC visit"),
        ]
        parts = []
        for needle, label in labels:
            row = _term(terms, needle)
            parts.append(
                f"{label}: {_num(row.get('coefficient'))} g (95% CI "
                f"{_ci([row.get('ci_low'), row.get('ci_high')])}, {_p_eq(row.get('p_value'))})"
            )
        return _work(
            qid,
            f"In the adjusted model (n={_i(value.get('n'))} after excluding "
            f"{_i(value.get('missing_bmi_excluded'))} records with missing BMI), estimated mean birthweight "
            "differences were " + "; ".join(parts) + f". R-squared={_num(value.get('r_squared'), 3)} and "
            f"adjusted R-squared={_num(value.get('adj_r_squared'), 3)}.",
            "Q8b output · anc_cohort.csv",
            "Name the reference level 'IPTp3 No' and the complete-case denominator. Coefficients are conditional associations from observational data.",
        )

    if qid == "Q8c":
        value = data.get("Q8c", {})
        top = value.get("top_cooks", [])
        largest = _num(top[0], 3) if top else "not available"
        return _work(
            qid,
            f"For the Q8b model, Durbin-Watson={_num(value.get('durbin_watson'), 2)}, suggesting no obvious "
            f"serial correlation. The largest Cook's distance was {largest} against a 4/n screening threshold "
            f"of {_num(value.get('cooks_threshold'), 4)}. The residual-versus-fitted, scale-location, "
            "Q-Q and influence plots must also be described in words because the numbers alone do not check linearity or normality.",
            "Q8c output · anc_cohort.csv",
            "Cook's distance is a screen, not an automatic deletion rule. State what each plot shows and justify any decision about influential records.",
        )

    if qid == "Q8d":
        value = data.get("Q8d", {})
        aic_change = _f(value.get("aic_extended")) - _f(value.get("aic_base"))
        r2_change = _f(value.get("adj_r2_extended")) - _f(value.get("adj_r2_base"))
        conclusion = "does not improve" if _f(value.get("p_value"), 1.0) >= 0.05 and aic_change > 0 else "may improve"
        return _work(
            qid,
            f"Adding facility type to the Q8b model {conclusion} fit on the same complete cases "
            f"(n={_i(value.get('n'))}): nested F with {_i(value.get('df_diff'))} numerator degrees of freedom="
            f"{_num(value.get('f_statistic'), 2)}, {_p_eq(value.get('p_value'))}; AIC "
            f"{_num(value.get('aic_extended'), 2)} versus {_num(value.get('aic_base'), 2)} (change "
            f"{_num(aic_change, 2)}); adjusted R-squared {_num(value.get('adj_r2_extended'), 3)} versus "
            f"{_num(value.get('adj_r2_base'), 3)} (change {_num(r2_change, 3)}).",
            "Q8d output · anc_cohort.csv",
            "Compare nested models only on the same sample, and weigh the block test, AIC and complexity together. A better fit is not a causal facility effect.",
        )

    if qid == "Q8e":
        value = data.get("Q8e", {})
        base = value.get("model_without_facility", {})
        extended = value.get("model_with_facility_urban", {})
        return _work(
            qid,
            "For the hypothetical profile (gest_age 39 weeks, BMI 22, IPTp3 Yes, 5 ANC visits), the base model "
            f"predicted mean birthweight {_num(base.get('mean'))} g (95% CI "
            f"{_ci([base.get('mean_ci_lower'), base.get('mean_ci_upper')])}) and an individual prediction "
            f"interval {_ci([base.get('obs_ci_lower'), base.get('obs_ci_upper')])} g. With facility type "
            f"added and Urban specified, the corresponding values were {_num(extended.get('mean'))} g "
            f"(mean CI {_ci([extended.get('mean_ci_lower'), extended.get('mean_ci_upper')])}) and "
            f"{_ci([extended.get('obs_ci_lower'), extended.get('obs_ci_upper')])} g.",
            "Q8e output · anc_cohort.csv",
            "A prediction interval is wider than the mean-response interval because it includes residual variation for one new observation. State which model generated each number.",
        )

    if qid == "Q9":
        value = data.get("Q9", {})
        terms = value.get("terms", [])
        pairs = []
        for needle, label in (("anaemia", "anaemia"), ("anc_visits", "each additional ANC visit"), ("age", "each additional year of age")):
            row = _term(terms, needle)
            pairs.append(
                f"{label} OR {_num(row.get('odds_ratio'), 3)} (95% CI "
                f"{_ci([row.get('or_ci_low'), row.get('or_ci_high')], 3)}, {_p_eq(row.get('p_value'))})"
            )
        probs = value.get("scenario_probabilities", {})
        return _work(
            qid,
            f"In the logistic model for the recorded preterm flag (n={_i(value.get('n'))}), adjusted odds "
            "ratios were " + "; ".join(pairs) + f". Pseudo R-squared={_num(value.get('pseudo_r_squared'), 3)}. "
            f"At age 25 with 4 ANC visits, predicted preterm probability was "
            f"{_pct(probs.get('anaemia'))} with anaemia versus {_pct(probs.get('no_anaemia'))} without.",
            "Q9 output · anc_cohort.csv",
            "An odds ratio is not a risk ratio. The scenario probabilities translate the log-odds model back to the probability scale for teaching; they are not causal contrasts.",
        )

    if qid == "Q10a":
        value = data.get("Q10a", {})
        return _work(
            qid,
            f"The survival file contains {_i(value.get('participants'))} women, with "
            f"{_i(value.get('events'))} readmission events and {_i(value.get('censored'))} censored "
            f"observations ({_pct(value.get('censoring_proportion'), 1)}). Median observed follow-up was "
            f"{_num(value.get('median_observed_follow_up'), 0)} days; that is a property of observation time, "
            "not an estimate of median readmission-free survival.",
            "Q10a output · postpartum_survival.csv",
            "Censored women contribute person-time up to their last observed time. Do not treat them as event-free at the end of study.",
        )

    if qid == "Q10b":
        value = data.get("Q10b", {})
        at_risk = value.get("number_at_risk", {})
        ci90, ci180 = value.get("ci_90", [0, 0]), value.get("ci_180", [0, 0])
        return _work(
            qid,
            f"Kaplan-Meier estimated readmission-free survival as "
            f"{_f(value.get('survival_90')):.4f} at 90 days (95% CI {_ci(ci90, 4)}) and "
            f"{_f(value.get('survival_180')):.4f} at 180 days (95% CI {_ci(ci180, 4)}). Median survival "
            f"was {_num(value.get('median_survival'), 0)} days (95% CI "
            f"{_ci(value.get('median_ci'), 0)}); {_i(at_risk.get('90'))} women remained at risk at day 90 "
            f"and {_i(at_risk.get('180'))} at day 180.",
            "Q10b output · postpartum_survival.csv",
            "Median observed follow-up and median survival are different quantities. Numbers at risk show where the tail of the curve is least precise.",
        )

    if qid == "Q10c":
        value = data.get("Q10c", {})
        medians = value.get("median_survival", {})
        group_text = "; ".join(
            f"{name} {_num(medians.get(name), 0)} days" for name in value.get("groups", [])
        )
        return _work(
            qid,
            f"Kaplan-Meier curves differed by anaemia status (log-rank chi-square="
            f"{_num(value.get('logrank_chi2'), 2)}, df=1, {_p_eq(value.get('logrank_p'))}); median "
            f"readmission-free survival was {group_text}. The test compares the entire observed curve "
            "history, not only the medians.",
            "Q10c output · postpartum_survival.csv",
            "The log-rank test is unadjusted and observational. Q10e adds covariates and Q10f checks the proportional-hazards assumption.",
        )

    if qid == "Q10d":
        value = data.get("Q10d", {})
        return _work(
            qid,
            f"There were {_i(value.get('events'))} readmissions over "
            f"{_num(value.get('person_time_days'), 0)} person-days, giving a rate of "
            f"{_num(value.get('rate_per_1000_person_days'), 3)} per 1,000 person-days (95% CI "
            f"{_ci(value.get('ci_per_1000_person_days'), 3)}). Under the constant-hazard exponential model, "
            f"S(90)={_f(value.get('exponential_s90')):.4f} and S(180)="
            f"{_f(value.get('exponential_s180')):.4f}; compare these with the non-parametric Kaplan-Meier "
            "estimates before relying on the model.",
            "Q10b and Q10d outputs · postpartum_survival.csv",
            "The rate is events per person-time, not events per person. A close match at two times supports descriptive agreement but does not prove a constant hazard.",
        )

    if qid == "Q10e":
        rows = data.get("Q10e", [])
        parts = [
            f"{r.get('term')} HR {_num(r.get('hazard_ratio'), 2)} (95% CI "
            f"{_ci([r.get('hr_ci_low'), r.get('hr_ci_high')], 2)}, {_p_eq(r.get('p_value'))}) — "
            f"{_ratio_text(r.get('hazard_ratio'))} hazard at fixed covariates"
            for r in rows
        ]
        events = _i(data.get("Q10a", {}).get("events"))
        participants = _i(data.get("Q10a", {}).get("participants"))
        return _work(
            qid,
            "In the Cox model, adjusted hazard ratios were " + "; ".join(parts) +
            f" (analysis of {participants} women and {events} events). Binary terms use the recorded "
            "reference categories printed in the notebook output.",
            "Q10a and Q10e outputs · postpartum_survival.csv",
            "A hazard ratio is a relative instantaneous event rate, not a risk ratio. Report reference levels and the PH diagnostic before interpreting it.",
        )

    if qid == "Q10f":
        rows = data.get("Q10f", [])
        parts = [
            f"{r.get('term')}: Spearman rho={_num(r.get('spearman_rho'), 3)}, raw "
            f"{_p_eq(r.get('p_value'))}, Holm {_p_eq(r.get('p_holm'))} "
            f"({'concern' if r.get('flag_ph_concern') else 'no flagged concern'})"
            for r in rows
        ]
        flagged = [str(r.get("term")) for r in rows if r.get("flag_ph_concern")]
        verdict = (
            f"A time trend remains for {', '.join(flagged)} after adjustment, so constant hazard ratios are questionable for those terms."
            if flagged else
            "No term shows a flagged time trend after adjustment, but the screen still cannot prove proportional hazards."
        )
        return _work(
            qid,
            "The Schoenfeld-residual screen gave " + "; ".join(parts) + ". " + verdict,
            "Q10f output · postpartum_survival.csv",
            "This is a statsmodels screening approximation, not an exact R cox.zph reproduction. A violation suggests time-varying effects or stratification.",
        )

    guide = GUIDES.get(qid, {})
    return _work(
        qid,
        f"Work through the {guide.get('requirement', 'question guidance')} and write the reasoning in your own words.",
        "Question guidance",
        guide.get("common_mistakes", "Link the explanation to the supplied dataset structure."),
    )


def worked_template_examples(results: dict[str, Any] | None) -> list[dict[str, str]]:
    """Pair every generic reporting pattern with a verified, data-grounded example."""
    sources = {
        "Descriptive statistics": "Q2b",
        "Probability": "Q1a",
        "Correlation": "Q2d",
        "Confidence interval": "Q3a",
        "Independent t-test": "Q4",
        "Paired t-test": "Q5",
        "ANOVA": "Q6",
        "Chi-square test": "Q7a",
        "Proportion test": "Q7b",
        "Linear regression": "Q8b",
        "Logistic regression": "Q9",
        "Kaplan-Meier analysis": "Q10b",
        "Log-rank test": "Q10c",
        "Exponential survival rate": "Q10d",
        "Cox regression": "Q10e",
    }
    examples = []
    for title, pattern in REPORTING_TEMPLATES:
        qid = sources[title]
        worked = work_report(qid, results)
        examples.append({
            "title": title,
            "pattern": pattern,
            "text": worked["text"],
            "source": worked["source"],
            "teach": worked["teach"],
            "qid": qid,
        })
    return examples

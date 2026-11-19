"""Correlation, regression and survival analysis with verified model output."""
from __future__ import annotations

import math
from typing import Any

from .results import MathResult, blocked_result


def _matrix(values: Any, name: str) -> list[list[float]]:
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError(f"{name} must be a non-empty list")
    if isinstance(values[0], (list, tuple)):
        return [[float(v) for v in row] for row in values]
    return [[float(v)] for v in values]


def _vector(values: Any) -> list[float]:
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError("outcome must be a non-empty list")
    return [float(v) for v in values]


def _stats():
    try:
        from scipy import stats
        return stats, None
    except Exception as exc:
        return None, str(exc)


def correlation(x: list[float], y: list[float], method: str = "pearson") -> MathResult:
    stats, error = _stats()
    if stats is None:
        return blocked_result("correlation", f"Correlation needs SciPy: {error}", domain="regression")
    a, b = _vector(x), _vector(y)
    if len(a) != len(b) or len(a) < 3:
        return blocked_result("correlation", "Correlation needs equal-length vectors of at least 3 pairs.", domain="regression")
    key = method.casefold()
    try:
        if key in ("spearman", "rank"):
            result = stats.spearmanr(a, b)
        elif key in ("kendall", "kendall_tau"):
            result = stats.kendalltau(a, b)
        else:
            result = stats.pearsonr(a, b)
            key = "pearson"
    except Exception as exc:
        return blocked_result("correlation", f"Correlation failed: {exc}", domain="regression")
    return MathResult(
        operation="correlation", domain="regression", method=f"{key} correlation",
        inputs={"n": len(a), "method": key},
        assumptions=["Paired observations", "Pearson assumes linearity; Spearman/Kendall are rank-based."],
        steps=[f"Compute the {key} coefficient for {len(a)} paired observations."],
        values={"coefficient": float(result.statistic), "p_value": float(result.pvalue), "n": len(a)},
        latex={"formula": r"r=\frac{\sum(x_i-\bar{x})(y_i-\bar{y})}{\sqrt{\sum(x_i-\bar{x})^2\sum(y_i-\bar{y})^2}}"},
        code=f"from scipy import stats\nstats.{ 'pearsonr' if key == 'pearson' else key + 'r' if key == 'spearman' else 'kendalltau' }(x, y)",
        interpretation="Correlation measures association, not causation.",
    )


def linear_regression(X: Any, y: Any) -> MathResult:
    try:
        import numpy as np
        import statsmodels.api as sm
    except Exception as exc:
        return blocked_result("linear_regression", f"Regression needs NumPy/statsmodels: {exc}", domain="regression")
    try:
        predictors = _matrix(X, "predictors")
        outcome = _vector(y)
        if len(predictors) != len(outcome):
            raise ValueError("predictors and outcome must have the same number of rows")
        design = sm.add_constant(np.asarray(predictors, dtype=float), has_constant="add")
        model = sm.OLS(np.asarray(outcome, dtype=float), design).fit()
    except Exception as exc:
        return blocked_result("linear_regression", f"Regression failed: {exc}", domain="regression")
    conf = model.conf_int(alpha=0.05)
    names = ["intercept"] + [f"x{i + 1}" for i in range(len(predictors[0]))]
    coefficients = []
    for index, name in enumerate(names):
        coefficients.append({
            "term": name, "coefficient": float(model.params[index]),
            "std_error": float(model.bse[index]), "p_value": float(model.pvalues[index]),
            "ci_95": [float(conf[index][0]), float(conf[index][1])],
        })
    return MathResult(
        operation="linear_regression", domain="regression", method="ordinary least squares",
        inputs={"n": len(outcome), "predictors": len(predictors[0])},
        assumptions=["Linearity", "Independent errors", "Homoscedasticity", "Approximately normal errors for small-sample inference"],
        steps=["Add an intercept column.", "Estimate coefficients by ordinary least squares.", "Report robust-aware diagnostics separately."],
        values={
            "coefficients": coefficients, "r_squared": float(model.rsquared),
            "adj_r_squared": float(model.rsquared_adj), "f_statistic": float(model.fvalue),
            "f_pvalue": float(model.f_pvalue), "n": int(model.nobs),
            "df_resid": int(model.df_resid),
            "aic": float(model.aic),
        },
        latex={"model": r"\hat{y}=\beta_0+\beta_1x_1+\cdots+\beta_kx_k"},
        code=("import numpy as np\nimport statsmodels.api as sm\n"
              f"X = sm.add_constant(np.asarray({predictors!r}, dtype=float))\n"
              f"model = sm.OLS(np.asarray({outcome!r}, dtype=float), X).fit()\nprint(model.summary())"),
        interpretation="Coefficients are associations conditional on the other predictors; regression alone does not establish causation.",
    )


def logistic_regression(X: Any, y: Any, multinomial: bool = False) -> MathResult:
    try:
        import numpy as np
        import statsmodels.api as sm
    except Exception as exc:
        return blocked_result("logistic_regression", f"Logistic regression needs NumPy/statsmodels: {exc}", domain="regression")
    try:
        predictors = _matrix(X, "predictors")
        outcome = [int(v) for v in _vector(y)]
        if len(predictors) != len(outcome):
            raise ValueError("predictors and outcome must have the same number of rows")
        design = sm.add_constant(np.asarray(predictors, dtype=float), has_constant="add")
        model = sm.MNLogit(outcome, design).fit(disp=False) if multinomial else sm.Logit(outcome, design).fit(disp=False)
    except Exception as exc:
        return blocked_result("logistic_regression", f"Logistic regression failed: {exc}", domain="regression")
    params = model.params
    pvalues = model.pvalues
    coefficients = []
    for row in range(params.shape[0]):
        for col in range(params.shape[1] if params.ndim > 1 else 1):
            value = params.iloc[row, col] if params.ndim > 1 else params.iloc[row]
            pvalue = pvalues.iloc[row, col] if getattr(pvalues, "ndim", 1) > 1 else pvalues.iloc[row]
            coefficients.append({"outcome_class": col if params.ndim > 1 else None, "term": params.index[row],
                                 "coefficient": float(value), "p_value": float(pvalue),
                                 "odds_ratio": float(math.exp(float(value)))})
    return MathResult(
        operation="logistic_regression", domain="regression",
        method="multinomial logistic regression" if multinomial else "binary logistic regression",
        inputs={"n": len(outcome), "predictors": len(predictors[0])},
        assumptions=["Binary or categorical outcome", "Independence", "No perfect separation", "Correct model link"],
        steps=["Fit the logit model by maximum likelihood.", "Exponentiate coefficients to obtain odds ratios."],
        values={"coefficients": coefficients, "log_likelihood": float(model.llf), "aic": float(model.aic), "converged": bool(model.mle_retvals.get("converged", True))},
        code=("import statsmodels.api as sm\n"
              f"X = sm.add_constant({predictors!r})\nmodel = sm.{'MNLogit' if multinomial else 'Logit'}({outcome!r}, X).fit()"),
        interpretation="Odds ratios above 1 indicate higher odds; they are not risk ratios.",
    )


def count_regression(X: Any, y: Any, model_type: str = "poisson") -> MathResult:
    try:
        import numpy as np
        import statsmodels.api as sm
    except Exception as exc:
        return blocked_result("count_regression", f"Count regression needs NumPy/statsmodels: {exc}", domain="regression")
    try:
        predictors = _matrix(X, "predictors")
        outcome = _vector(y)
        design = sm.add_constant(np.asarray(predictors, dtype=float), has_constant="add")
        family = sm.families.NegativeBinomial() if model_type.casefold().startswith("negative") else sm.families.Poisson()
        model = sm.GLM(outcome, design, family=family).fit()
    except Exception as exc:
        return blocked_result("count_regression", f"Count regression failed: {exc}", domain="regression")
    return MathResult(
        operation="count_regression", domain="regression",
        method=model_type, inputs={"n": len(outcome), "predictors": len(predictors[0])},
        assumptions=["Counts are non-negative", "Poisson assumes mean ≈ variance", "Negative binomial allows overdispersion"],
        steps=["Fit a generalized linear model with log link.", "Exponentiate coefficients to obtain rate ratios."],
        values={"coefficients": [{"term": name, "coefficient": float(model.params[i]),
                                  "p_value": float(model.pvalues[i]), "rate_ratio": float(math.exp(float(model.params[i])))}
                                 for i, name in enumerate(["intercept"] + [f"x{j + 1}" for j in range(len(predictors[0]))])],
                "aic": float(model.aic), "deviance": float(model.deviance)},
        interpretation="Rate ratios describe multiplicative changes in event rates under the selected count model.",
    )


def cox_regression(X: Any, time: list[float], event: list[int]) -> MathResult:
    try:
        import numpy as np
        from statsmodels.duration.hazard_regression import PHReg
    except Exception as exc:
        return blocked_result("cox_regression", f"Cox regression needs statsmodels: {exc}", domain="survival")
    try:
        predictors = _matrix(X, "predictors")
        times = _vector(time)
        events = [int(v) for v in event]
        if not (len(predictors) == len(times) == len(events)):
            raise ValueError("X, time and event must have equal lengths")
        model = PHReg(np.asarray(times, dtype=float), np.asarray(predictors, dtype=float), status=np.asarray(events)).fit()
    except Exception as exc:
        return blocked_result("cox_regression", f"Cox regression failed: {exc}", domain="survival")
    return MathResult(
        operation="cox_regression", domain="survival", method="Cox proportional hazards",
        inputs={"n": len(time), "events": sum(events), "predictors": len(predictors[0])},
        assumptions=["Proportional hazards", "Independent subjects", "Censoring is non-informative"],
        steps=["Estimate hazard ratios by partial likelihood.", "Check the proportional-hazards assumption before causal interpretation."],
        values={"coefficients": [{"term": f"x{i + 1}", "coefficient": float(model.params[i]),
                                  "hazard_ratio": float(math.exp(float(model.params[i]))),
                                  "p_value": float(model.pvalues[i])} for i in range(len(predictors[0]))]},
        interpretation="Hazard ratios are instantaneous rate ratios; they are not risk ratios.",
    )


def kaplan_meier(time: list[float], event: list[int]) -> MathResult:
    try:
        from statsmodels.duration.survfunc import SurvfuncRight
    except Exception as exc:
        return blocked_result("kaplan_meier", f"Survival analysis needs statsmodels: {exc}", domain="survival")
    try:
        times = _vector(time)
        events = [int(v) for v in event]
        if len(times) != len(events) or not times:
            raise ValueError("time and event must have equal non-zero length")
        model = SurvfuncRight(times, events)
        if hasattr(model, "surv_times") and hasattr(model, "surv_prob"):
            curve_times = [float(v) for v in model.surv_times]
            survival = [float(v) for v in model.surv_prob]
        else:
            table = model.survfunc_right
            curve_times = [float(row[0]) for row in table]
            survival = [float(row[1]) for row in table]
        try:
            median = model.quantile(0.5)
            median = float(median[0]) if isinstance(median, (list, tuple)) and median else float(median)
        except Exception:
            median = None
    except Exception as exc:
        return blocked_result("kaplan_meier", f"Kaplan–Meier failed: {exc}", domain="survival")
    return MathResult(
        operation="kaplan_meier", domain="survival", method="Kaplan–Meier product-limit estimator",
        inputs={"n": len(times), "events": sum(events)},
        assumptions=["Independent censoring", "Survival time measured from a defined origin"],
        steps=["Order event times.", "Multiply conditional survival probabilities after each event."],
        values={"time": curve_times, "survival": survival, "median_survival": median},
        chart={"type": "line", "title": "Kaplan–Meier survival curve",
               "labels": [str(round(value, 4)) for value in curve_times],
               "datasets": [{"label": "Survival probability", "data": survival}]},
        interpretation="Survival probabilities are estimated from observed events and censoring; confidence bands should be reported for inference.",
    )

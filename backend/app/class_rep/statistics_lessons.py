"""Manual-first hypothesis-testing lessons for CRARA.

The model is deliberately not used for the core teaching sequence. A student
must see the research reasoning, assumptions, hand calculation, table lookup,
distribution and decision rule before any computational stage is offered. This
module returns deterministic, reproducible lessons and a link to the embedded
interactive lab; Python is emitted only after the manual stage is complete.

The teaching text is intentionally English-only, matching the existing
English-only STAT 8100 companion; this module adds no translation path.
"""
from __future__ import annotations

import math
import re

PROVIDER = "CRARA statistics tutor"
MODEL = "manual-first-v1"
MANUAL_MARKER = "**Manual stage complete**"
LAB_LINK = "[Open the Hypothesis Testing Lab](/resources/hypothesis-testing-lab.html)"

_TEACH_VERBS = re.compile(
    r"\b(?:teach|explain|show|walk(?:\s+me)?(?:\s+through)?|guide|demonstrate|"
    r"steps?|how|work(?:ed)?|solve|calculate|compute|perform|carry\s+out|interpret|"
    r"read|use|introduce|learn|phunzitsa|fotokoza|onetsa|werenger|tanthauza)\b",
    re.I,
)
_STATS_CONTEXT = re.compile(
    r"\b(?:hypothes(?:is|es|is\s+testing)|p[-\s]?values?|critical\s+values?|"
    r"alpha|significan(?:ce|t)|null|alternative|test\s+statistic|z[-\s]?test|"
    r"z[-\s]?table|t[-\s]?test|t[-\s]?table|anova|chi[-\s]?square|"
    r"chi[-\s]?sq|goodness[-\s]?of[-\s]?fit|mann[-\s]?whitney|wilcoxon|"
    r"correlation|regression|standard\s+normal|normal\s+distribution|"
    r"rejection\s+region|degrees?\s+of\s+freedom|df|cdf|ppf)\b",
    re.I,
)
_SCHEDULE_TERMS = re.compile(
    r"\b(?:timetable|calendar|schedule|lecture|session|exam|module|facilitator|"
    r"ndandanda|kalasi|mayeso|mlangizi)\b",
    re.I,
)
_PYTHON_REQUEST = re.compile(
    r"\b(?:python|jupyter|notebook|code|script|scipy|numpy|statsmodels|matplotlib|"
    r"implement|programmatic|run\s+this)\b",
    re.I,
)
_EXPLICIT_LESSON = re.compile(
    r"\b(?:hypothesis\s+testing|hypothesis\s+test|manual\s+calculation|"
    r"statistical\s+tables?|z\s*[-–]?\s*table|t\s*[-–]?\s*table|"
    r"chi\s*[-–]?\s*square\s+table|f\s*[-–]?\s*distribution\s+table|"
    r"normal\s+distribution\s+test|rejection\s+regions?)\b",
    re.I,
)

_TOPICS: list[tuple[str, re.Pattern[str]]] = [
    ("z_test", re.compile(r"\b(?:z[-\s]?test|one[-\s]?sample\s+z|standard\s+normal|z[-\s]?table|birth\s*weight)\b", re.I)),
    ("one_sample_t", re.compile(r"\b(?:one[-\s]?sample\s+t|single[-\s]?sample\s+t|haemoglobin|hemoglobin|t[-\s]?table)\b", re.I)),
    ("independent_t", re.compile(r"\b(?:independent\s+(?:samples?\s+)?t|unpaired\s+t|two[-\s]?sample\s+t|between[-\s]?groups)\b", re.I)),
    ("paired_t", re.compile(r"\b(?:paired\s+t|matched[-\s]?pairs|before\s+and\s+after|blood\s+pressure)\b", re.I)),
    ("anova", re.compile(r"\b(?:anova|analysis\s+of\s+variance|f[-\s]?test|facility\s+type)\b", re.I)),
    ("chi_square_independence", re.compile(r"\b(?:chi[-\s]?(?:square|sq).{0,24}independ|association|contingency|gravidity)\b", re.I)),
    ("chi_square_goodness", re.compile(r"\b(?:goodness[-\s]?of[-\s]?fit|preterm\s+proportion|30\s*%)\b", re.I)),
    ("correlation", re.compile(r"\b(?:correlation|pearson|r[-\s]?value|relationship\s+between)\b", re.I)),
    ("regression", re.compile(r"\b(?:regression|slope|coefficient|predict(?:ion|or)?)\b", re.I)),
    ("mann_whitney", re.compile(r"\b(?:mann[-\s]?whitney|rank[-\s]?sum|non[-\s]?parametric\s+group)\b", re.I)),
    ("wilcoxon", re.compile(r"\b(?:wilcoxon|signed[-\s]?rank)\b", re.I)),
]


def is_hypothesis_teaching_request(message: str) -> bool:
    """Return True only for genuine statistics-teaching turns."""
    text = str(message or "")
    if _SCHEDULE_TERMS.search(text) and not _STATS_CONTEXT.search(text):
        return False
    if _EXPLICIT_LESSON.search(text):
        return True
    return bool(_TEACH_VERBS.search(text) and _STATS_CONTEXT.search(text))


def detect_topic(message: str) -> str:
    for name, pattern in _TOPICS:
        if pattern.search(str(message or "")):
            return name
    return "z_test"


def _history_text(history: list[dict]) -> str:
    parts: list[str] = []
    for item in history or []:
        if not isinstance(item, dict):
            continue
        if item.get("role") in ("assistant", "user"):
            parts.append(str(item.get("content", "")))
    return "\n".join(parts[-6:])


_TOPIC_IN_MARKER = re.compile(re.escape(MANUAL_MARKER) + r"\s+topic=([a-z_]+)")


def _topic_from_history(history: list[dict]) -> str | None:
    """Recover the topic of the most recent manual lesson from chat history."""
    match = _TOPIC_IN_MARKER.search(_history_text(history))
    return match.group(1) if match else None


def wants_python_stage(message: str, history: list[dict]) -> bool:
    """Python is available only after a manual stage has been delivered."""
    if not _PYTHON_REQUEST.search(str(message or "")):
        return False
    return MANUAL_MARKER in _history_text(history)


def answer_lesson(message: str, history: list[dict], response_language: str = "EN") -> tuple[str, str, str] | None:
    """Return a deterministic lesson, or None when the turn is not a lesson."""
    manual_done = MANUAL_MARKER in _history_text(history)
    continuation = manual_done and bool(_PYTHON_REQUEST.search(str(message or "")))
    if not is_hypothesis_teaching_request(message) and not continuation:
        return None
    topic = detect_topic(message)
    if wants_python_stage(message, history):
        # A bare "show Python" after a t/ANOVA/chi-square lesson must reproduce
        # that lesson's example, not silently fall back to the Z example.
        return _python_lesson(_topic_from_history(history) or topic), PROVIDER, MODEL
    return _manual_lesson(topic), PROVIDER, MODEL


def _normal_chart() -> str:
    import json

    xs = [round(-4 + index * 0.25, 2) for index in range(33)]
    data = [round(math.exp(-0.5 * value * value) / math.sqrt(2 * math.pi), 6) for value in xs]
    chart = {
        "type": "line",
        "title": "Standard normal density — two-tailed 5% decision regions",
        "labels": [f"{value:.2f}" for value in xs],
        "datasets": [{
            "label": "Standard normal density φ(z)",
            "data": data,
        }],
    }
    return "```chart\n" + json.dumps(chart, ensure_ascii=False, sort_keys=True) + "\n```"


_LAB_INTRO = r"""## Hypothesis testing, taught manually first

CRARA's rule for this topic is simple: **statistical reasoning comes before code**. Work through the research question, hypotheses, assumptions, hand calculation, table lookup, distribution and decision rule first. Python is a way to reproduce and check that reasoning, not a substitute for it.

[Open the Hypothesis Testing Lab](/resources/hypothesis-testing-lab.html)

The numbers below are a fixed teaching example, not a real patient finding. Use the controls in the lab to change the significance level, test statistic and tail configuration after you understand the hand calculation.
"""


_Z_MANUAL = r"""
### Step 1 — Research question

A researcher asks: **Is the mean birth weight in the study population different from 2,500 g?** This is a two-sided question because a difference in either direction matters.

### Step 2 — Null and alternative hypotheses

\[
H_0: \mu = 2500\text{ g}
\]

\[
H_1: \mu \ne 2500\text{ g}
\]

Here \(\mu\) is the true population mean birth weight. The null hypothesis is the claim being tested; the alternative is the researcher's claim of a difference.

### Step 3 — Choose the test and state assumptions

A **one-sample Z-test** is appropriate here because the population standard deviation is treated as known, the observations are independent, and the sample size is large enough for the sampling distribution of \(\bar{x}\) to be approximately normal.

Given: \(n=36\), \(\bar{x}=2650\text{ g}\), \(\sigma=450\text{ g}\), \(\alpha=0.05\).

### Step 4 — Calculate the standard error by hand

\[
SE=\frac{\sigma}{\sqrt{n}}=\frac{450}{\sqrt{36}}=\frac{450}{6}=75\text{ g}
\]

The standard error is the standard deviation of the sample mean. It tells us how much \(\bar{x}\) would vary from sample to sample if \(H_0\) were true.

### Step 5 — Calculate the test statistic

\[
z=\frac{\bar{x}-\mu_0}{SE}=\frac{2650-2500}{75}=\frac{150}{75}=2.00
\]

The observed mean is **2 standard errors above** the hypothesised mean.

### Step 6 — Read the Z-table physically

Locate row **2.0** and column **0.00** in the standard normal table. The cell is approximately **0.9772**. This is the cumulative probability to the left of \(z=2.00\):

\[
\Phi(2.00)\approx0.9772
\]

The right-tail probability is \(1-0.9772=0.0228\). Because this is a two-tailed test, double it:

\[
p=2(1-0.9772)=0.0456\approx0.0455
\]

The tiny difference between 0.0456 and 0.0455 comes only from four-decimal table rounding; the full-precision value is 0.0455.

### Step 7 — Determine the critical values

At \(\alpha=0.05\) with two tails, divide the risk between the tails:

\[
\frac{\alpha}{2}=0.025
\]

From the Z-table, the value with 0.025 above it is 1.96. Therefore the critical values are:

\[
z_{0.025}=1.96,\qquad \text{critical values}=\pm1.96
\]

### Step 8 — Display the normal distribution and decision regions

The central non-rejection region lies between \(-1.96\) and \(1.96\). The two shaded tails are the rejection regions.

__CHART__

### Step 9 — Make the statistical decision

The observed statistic \(z=2.00\) is larger than the upper critical value \(1.96\). It falls in the right rejection region. Therefore, **reject \(H_0\)** at the 5% significance level.

### Step 10 — Interpret in research language

There is statistically significant evidence, at the 5% level, that the population mean birth weight differs from 2,500 g. The observed sample mean was 150 g higher. Do not call this "clinically important" without a clinical threshold and further evidence; statistical significance answers only whether the observed difference is unlikely under \(H_0\).

### What the lab adds

In the interactive lab you can highlight row 2.0 and column 0.00 yourself, switch to one-tailed testing, change \(\alpha\), and watch the rejection regions move.

MANUAL_MARKER

Ask **"show me the Python stage"** when you are ready to reproduce the same calculation in JupyterLab.
"""


_GENERIC_MANUAL = r"""
### Step 1 — Research question

The teaching example uses simulated maternal and neonatal health data. State the question as a claim about a population parameter, never as a claim about one observed sample.

### Step 2 — Null and alternative hypotheses

Write \(H_0\) as the no-difference/no-association statement and \(H_1\) as the researchers' claim. Decide before calculating whether the test is one-tailed or two-tailed.

### Step 3 — Choose the test and state assumptions

Variable type and study design select the test: continuous outcomes use mean-based tests, categorical outcomes use proportion/association tests, repeated measures use paired methods, and strongly non-normal small samples use rank-based methods.

### Step 4 — Calculate the standard error or test statistic manually

Substitute the observed values into the formula and write every arithmetic step. Do not round intermediate values prematurely.

### Step 5 — Determine degrees of freedom and the critical value

Read the correct table using the significance level, tail configuration and degrees of freedom highlighted in the lab.

### Step 6 — Show the decision regions

Mark the critical value(s) on the relevant distribution and place the observed statistic on the same axis.

### Step 7 — Make the decision and interpret

Reject or fail to reject \(H_0\), then write the conclusion in research language. Separate statistical significance from clinical or programme importance.

MANUAL_MARKER

Open the lab link above for the interactive table and distribution, then ask for the Python stage when ready.
"""


_TOPIC_GUIDANCE: dict[str, str] = {
    "one_sample_t": r"""
**Focus: one-sample t-test (population SD unknown).** Example: maternal haemoglobin among 25 mothers, \(\bar{x}=10.4\) g/dL, \(s=1.5\) g/dL, tested against \(\mu_0=11\) g/dL. Manual work: \(SE=1.5/\sqrt{25}=0.3\), \(t=(10.4-11)/0.3=-2.00\), \(df=24\), two-tailed 5% critical values \(\pm2.064\). Since \(|t|=2.00<2.064\), fail to reject \(H_0\). Use the t-table row 24 and the two-tailed \(\alpha=0.05\) column.
""",
    "independent_t": r"""
**Focus: independent-samples t-test.** Example: mean birth weight between two delivery groups with \(n_1=30\), \(n_2=32\). Manually compute each group mean and variance, pool the variance when the equal-variance assumption is defensible, calculate \(SE=\sqrt{s_p^2(1/n_1+1/n_2)}\), then \(t=(\bar{x}_1-\bar{x}_2)/SE\) with \(df=n_1+n_2-2\). Read the t-table using that df before any code.
""",
    "paired_t": r"""
**Focus: paired t-test.** Example: blood pressure before and after an intervention in the same 20 mothers. Calculate one difference per mother, then analyse the differences: \(\bar{d}\), \(s_d\), \(SE=s_d/\sqrt{n}\), \(t=\bar{d}/SE\), \(df=n-1\). Pairing removes between-subject variation; use the t-table, not an independent-groups formula.
""",
    "anova": r"""
**Focus: one-way ANOVA.** Example: mean birth weight across three facility types. Manually compute between-group and within-group sums of squares, divide by \(df_{\text{between}}=k-1\) and \(df_{\text{within}}=N-k\), then \(F=MS_{\text{between}}/MS_{\text{within}}\). With \(k=3\) and \(N=63\), read the F-table at \(df_1=2\), \(df_2=60\), \(\alpha=0.05\) (critical value about 3.15) before using software.
""",
    "chi_square_independence": r"""
**Focus: chi-square test of independence.** Example: gravidity category (three groups) by preterm outcome (yes/no) in a contingency table. Compute expected counts as \(E_{ij}=R_iC_j/N\), then \(\chi^2=\sum (O-E)^2/E\). Here \(df=(3-1)(2-1)=2\), so the 5% right-tail critical value is 5.991. Check that expected counts are adequate before relying on the table.
""",
    "chi_square_goodness": r"""
**Focus: chi-square goodness-of-fit.** Example: test whether the observed preterm proportion is compatible with a proposed 30% benchmark. Compare observed and expected counts in term/preterm categories, calculate \(\chi^2=\sum (O-E)^2/E\), and use \(df=\text{categories}-1\). With two categories, the 5% critical value is 3.841.
""",
    "correlation": r"""
**Focus: Pearson correlation significance.** Example: association between maternal haemoglobin and birth weight in \(n=30\) records. Compute \(r\) manually, then \(t=r\sqrt{(n-2)/(1-r^2)}\) with \(df=n-2\). Read the t-table before obtaining a software p-value. Correlation strength is not causation.
""",
    "regression": r"""
**Focus: simple linear regression slope test.** Example: predicting birth weight from gestational age. Fit the slope \(b_1\), compute its standard error \(SE(b_1)\), then \(t=b_1/SE(b_1)\) with \(df=n-2\). Interpret the slope in the original units and keep the intercept meaningful only within the observed range.
""",
    "mann_whitney": r"""
**Focus: Mann–Whitney U test.** Example: comparing a skewed neonatal outcome between two independent groups. Combine and rank observations, sum ranks for each group, compute both U statistics, and use the smaller U with the rank-sum table or a tie-corrected normal approximation. Report medians and ranks, not means alone.
""",
    "wilcoxon": r"""
**Focus: Wilcoxon signed-rank test.** Example: paired before/after measurements that are not approximately normal. Calculate paired differences, discard exact zeros, rank absolute differences, restore signs, and compare the smaller signed-rank total with the critical value for \(n\). Report the median difference and the direction of change.
""",
}


def _manual_lesson(topic: str) -> str:
    marker = f"{MANUAL_MARKER} topic={topic}"
    if topic == "z_test":
        body = _Z_MANUAL.replace("__CHART__", _normal_chart()).replace("MANUAL_MARKER", marker)
        return _LAB_INTRO + body
    guidance = _TOPIC_GUIDANCE.get(topic, "")
    return _LAB_INTRO + guidance + "\n" + _GENERIC_MANUAL.replace("MANUAL_MARKER", marker)


_Z_PYTHON = r"""
## Python stage — same values, computational reproduction

Only now that the manual reasoning is complete do we open JupyterLab. Run one cell at a time and compare every number with the hand calculation.

```python
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

# Sample information from the SAME teaching example
n = 36
sample_mean = 2650
mu_0 = 2500
sigma = 450
alpha = 0.05

# Manual quantities reproduced by Python
se = sigma / np.sqrt(n)
z_stat = (sample_mean - mu_0) / se
z_critical = stats.norm.ppf(1 - alpha / 2)
p_value = 2 * stats.norm.sf(abs(z_stat))
decision = "Reject H0" if abs(z_stat) > z_critical else "Fail to reject H0"

print(f"SE = {se:.0f} g")
print(f"z = {z_stat:.2f}")
print(f"critical values = +/-{z_critical:.2f}")
print(f"p-value = {p_value:.4f}")
print(decision)

# Visual check of the rejection regions
x = np.linspace(-4, 4, 400)
plt.plot(x, stats.norm.pdf(x), label="Standard normal density")
plt.axvline(-z_critical, color="orange", linestyle="--", label="Critical values")
plt.axvline(z_critical, color="orange", linestyle="--")
plt.axvline(z_stat, color="red", label="Observed z = 2.00")
plt.fill_between(x, stats.norm.pdf(x), where=x <= -z_critical, alpha=0.35)
plt.fill_between(x, stats.norm.pdf(x), where=x >= z_critical, alpha=0.35)
plt.xlabel("Z-score")
plt.ylabel("Probability density")
plt.legend()
plt.show()
```

### Line-by-line explanation

- `import numpy as np` loads NumPy, the array and numerical library used for \(\sqrt{36}\) and the dense grid of z-values.
- `from scipy import stats` loads SciPy's statistical distributions, including the normal CDF, survival function and inverse CDF.
- `import matplotlib.pyplot as plt` loads the plotting library used to draw the density curve.
- `n`, `sample_mean`, `mu_0`, `sigma` and `alpha` store exactly the values used by hand: 36, 2650 g, 2500 g, 450 g and 0.05.
- `se = sigma / np.sqrt(n)` computes \(450/\sqrt{36}=75\).
- `z_stat = (sample_mean - mu_0) / se` computes \((2650-2500)/75=2.00\).
- `z_critical = stats.norm.ppf(1 - alpha / 2)` asks SciPy for the value with 0.025 above it, giving 1.95996. `ppf` is the inverse CDF.
- `p_value = 2 * stats.norm.sf(abs(z_stat))` doubles the upper-tail survival probability. `sf` is \(1-\text{CDF}\), so it avoids rounding error.
- `decision = ...` applies the same rule used manually: compare \(|z|\) with the critical value.
- The plotting lines draw the same curve, critical lines and shaded rejection regions shown in the lab.

### Manual versus Python comparison

| Statistical component | Manual method | Python method |
| --- | --- | --- |
| Standard error | \(450/\sqrt{36}=75\) | `sigma / np.sqrt(n)` |
| Test statistic | \((2650-2500)/75=2.00\) | `(sample_mean - mu_0) / se` |
| Critical value | Z-table row/col lookup, \(\pm1.96\) | `stats.norm.ppf(1 - alpha / 2)` |
| P-value | Table tail area, about 0.0455 | `2 * stats.norm.sf(abs(z_stat))` |
| Decision | Compare 2.00 with 1.96 | Compare `abs(z_stat)` with `z_critical` |
| Interpretation | Research conclusion about \(\mu\) | Same research conclusion |

Python automates arithmetic and graph drawing. It does **not** choose the hypotheses, justify the assumptions, or write the scientific interpretation. Those remain statistical reasoning tasks.

Return to the [Hypothesis Testing Lab](/resources/hypothesis-testing-lab.html) to repeat the table and distribution steps interactively.
"""


_PYTHON_GUIDANCE: dict[str, tuple[str, str]] = {
    "one_sample_t": (r"""n = 25
mean = 10.4
s = 1.5
mu_0 = 11.0
alpha = 0.05
se = s / np.sqrt(n)
t_stat = (mean - mu_0) / se
df = n - 1
t_crit = stats.t.ppf(1 - alpha / 2, df)
p_value = 2 * stats.t.sf(abs(t_stat), df)
print(f"SE={se:.2f}, t={t_stat:.3f}, df={df}, critical=±{t_crit:.3f}, p={p_value:.4f}")""",
        r"""`se = s / np.sqrt(n)` reproduces \(1.5/5=0.3\). `t_stat` reproduces \(-2.00\). `stats.t.ppf(1 - alpha/2, 24)` gives 2.0639, the table's 2.064, and `stats.t.sf` supplies the two-tailed tail area. Because \(|t|=2.00<2.064\), fail to reject \(H_0\)."""),
    "independent_t": (r"""mean1, mean2 = 2700.0, 2620.0
s1, s2 = 420.0, 390.0
n1, n2 = 30, 32
alpha = 0.05
sp2 = ((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2)
se = np.sqrt(sp2 * (1 / n1 + 1 / n2))
t_stat = (mean1 - mean2) / se
df = n1 + n2 - 2
t_crit = stats.t.ppf(1 - alpha / 2, df)
p_value = 2 * stats.t.sf(abs(t_stat), df)
print(f"t={t_stat:.3f}, df={df}, critical=±{t_crit:.3f}, p={p_value:.4f}")""",
        r"""The pooled variance `sp2` matches the hand formula, `se` is the standard error of the mean difference, and `df = n1 + n2 - 2` selects the t-table row. The decision compares `abs(t_stat)` with `t_crit`.""",
    ),
    "paired_t": (r"""mean_diff = -4.2
s_diff = 6.5
n = 20
alpha = 0.05
se = s_diff / np.sqrt(n)
t_stat = mean_diff / se
df = n - 1
t_crit = stats.t.ppf(1 - alpha / 2, df)
p_value = 2 * stats.t.sf(abs(t_stat), df)
print(f"t={t_stat:.3f}, df={df}, critical=±{t_crit:.3f}, p={p_value:.4f}")""",
        r"""A paired test analyses one difference per subject. `se = s_diff / np.sqrt(n)` and `df = n-1` are the same steps used in the manual calculation; SciPy only supplies the critical value and tail probability.""",
    ),
    "anova": (r"""ss_between = 180000.0
ss_within = 1200000.0
df_between = 2
df_within = 60
alpha = 0.05
ms_between = ss_between / df_between
ms_within = ss_within / df_within
f_stat = ms_between / ms_within
f_crit = stats.f.ppf(1 - alpha, df_between, df_within)
p_value = stats.f.sf(f_stat, df_between, df_within)
print(f"F={f_stat:.3f}, df=({df_between},{df_within}), critical={f_crit:.3f}, p={p_value:.4f}")""",
        r"""`ms_between` and `ms_within` reproduce the hand sums of squares divided by their degrees of freedom. `stats.f.ppf` is the F-table critical value; `stats.f.sf` is the right-tail probability. A significant F must be followed by comparing group means.""",
    ),
    "chi_square_independence": (r"""table = np.array([[42, 18], [35, 25], [23, 37]])
chi2_stat, p_value, df, expected = stats.chi2_contingency(table, correction=False)
alpha = 0.05
chi2_crit = stats.chi2.ppf(1 - alpha, df)
print(f"chi2={chi2_stat:.3f}, df={df}, critical={chi2_crit:.3f}, p={p_value:.4f}")
print("expected counts:", expected.round(1))""",
        r"""The contingency table uses simulated counts. `stats.chi2_contingency` computes expected counts and \(\sum (O-E)^2/E\); `stats.chi2.ppf` reproduces the right-tail table critical value. Expectation for a \(3\times2\) table is \(df=2\), giving 5.991 at 5%.""",
    ),
    "chi_square_goodness": (r"""observed = np.array([280, 120])
expected = np.array([300, 100])
chi2_stat, p_value = stats.chisquare(observed, expected)
alpha = 0.05
chi2_crit = stats.chi2.ppf(1 - alpha, len(observed) - 1)
print(f"chi2={chi2_stat:.3f}, df={len(observed)-1}, critical={chi2_crit:.3f}, p={p_value:.4f}")""",
        r"""Expected counts come from the proposed 30% preterm benchmark in \(n=400\). `stats.chisquare` reproduces \(\sum (O-E)^2/E\); the critical value uses \(df=\text{categories}-1=1\), which is 3.841 at 5%.""",
    ),
    "correlation": (r"""r = 0.35
n = 30
alpha = 0.05
t_stat = r * np.sqrt((n - 2) / (1 - r**2))
df = n - 2
t_crit = stats.t.ppf(1 - alpha / 2, df)
p_value = 2 * stats.t.sf(abs(t_stat), df)
print(f"t={t_stat:.3f}, df={df}, critical=±{t_crit:.3f}, p={p_value:.4f}")""",
        r"""The transformation \(t=r\sqrt{(n-2)/(1-r^2)}\) is computed exactly as in the manual stage. Correlation significance does not establish causation or clinical importance.""",
    ),
    "regression": (r"""slope = 12.5
se_slope = 4.0
n = 30
alpha = 0.05
t_stat = slope / se_slope
df = n - 2
t_crit = stats.t.ppf(1 - alpha / 2, df)
p_value = 2 * stats.t.sf(abs(t_stat), df)
print(f"t={t_stat:.3f}, df={df}, critical=±{t_crit:.3f}, p={p_value:.4f}")""",
        r"""The slope estimate and its standard error are the hand-calculated quantities. `statsmodels` can also produce them from raw data, but the hypothesis test is still \(t=b_1/SE(b_1)\) with \(df=n-2\).""",
    ),
    "mann_whitney": (r"""group_a = np.array([2100, 2350, 2480, 2520, 2680, 2790])
group_b = np.array([1950, 2180, 2290, 2400, 2510, 2620])
stat, p_value = stats.mannwhitneyu(group_a, group_b, alternative="two-sided")
print(f"U={stat:.1f}, p={p_value:.4f}")""",
        r"""These are illustrative teaching measurements. SciPy ranks the combined observations and returns the smaller U statistic. Compare its p-value with the decision reached from the rank-sum table or tie-corrected normal approximation.""",
    ),
    "wilcoxon": (r"""differences = np.array([-6, -4, -3, -1, 0, 2, 3, 5, 6, 8])
stat, p_value = stats.wilcoxon(differences, alternative="two-sided")
print(f"signed-rank statistic={stat:.1f}, p={p_value:.4f}")""",
        r"""Exact-zero differences are handled by SciPy as in the manual method. The signed-rank statistic is compared with the table or p-value; report the median difference and direction, not only the test result.""",
    ),
}


def _python_lesson(topic: str) -> str:
    if topic == "z_test":
        return _Z_PYTHON
    code, explanation = _PYTHON_GUIDANCE.get(topic, next(iter(_PYTHON_GUIDANCE.values())))
    return r"""## Python stage — computational check for the same manual example

Use this stage only after the manual reasoning, table lookup and decision rule are clear. The code matches the illustrative values used in the manual guidance; replace them only when you have a new, verified teaching example.

```python
import numpy as np
from scipy import stats

__CODE__
```

### What each part does

__EXPLANATION__

### Manual versus Python comparison

| Component | Manual | Python |
| --- | --- | --- |
| Test statistic | Formula with substituted values | Arithmetic expression |
| Critical value / table | Statistical table row and column | `stats.<distribution>.ppf(...)` |
| P-value | Table tail area | `sf` or `cdf` |
| Decision | Compare with critical value | Boolean comparison |
| Interpretation | Research conclusion | Same research conclusion |

Return to the [Hypothesis Testing Lab](/resources/hypothesis-testing-lab.html) to practise the manual steps again.
""".replace("__CODE__", code).replace("__EXPLANATION__", explanation)

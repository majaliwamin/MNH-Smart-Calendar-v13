"""Safe, data-grounded statistical visual generation for CRARA.

Only fixed recipes over bundled simulated teaching CSV files are supported.
Submitted code is never executed and no internet source is consulted. Every
answer is computed server-side from the verified file and includes its SHA-256
fingerprint, sample size and an honest simulated-data label.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from app.class_rep import local_knowledge
from app.config import PROJECT_ROOT

PROVIDER = "CRARA local Python library"
MODEL = "verified-simulated-teaching-data-v1"

_VISUAL_INTENT = re.compile(
    r"\b(?:chart|charts|graph|graphs|plot|plots|draw|show|display|visuali[sz]e|visuali[sz]ation|"
    r"distribution|distributions|curve|curves|curbes|density|histogram|kde|scatter|bar\s+chart|"
    r"survival|kaplan|meier|chati|zojambula|jambula|kuwonetsa|kufalikira|mphepete)\b",
    re.I,
)
_SCHEDULE_TERMS = re.compile(
    r"\b(?:timetable|calendar|schedule|class|lecture|session|exam|module|facilitator|"
    r"ndandanda|kalasi|phunziro|mayeso|mlangizi)\b",
    re.I,
)
_STATS_TERMS = re.compile(
    r"\b(?:chart|graph|plot|visuali[sz]|distribution|curve|density|histogram|kde|scatter|"
    r"survival|statistic|statistics|data|dataset|python|library|birthweight|'birth weight'|"
    r"haemoglobin|hemoglobin|blood pressure|\bbp\b|anaemia|anemia|facility|gestational|"
    r"chati|zojambula|kufalikira|deta|deti|kulemera|magazi|chipatala|mimba)\b",
    re.I,
)
_REAL_DATA_TERMS = re.compile(
    r"\b(?:real|actual|patient|patients|clinical|research|personal|my\s+data|"
    r"odwala|enieni|chipatala\s+cha)\b",
    re.I,
)


class VisualError(RuntimeError):
    """A safe visual-generation failure that never exposes file internals."""


def _number(value: Any, digits: int = 4) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return round(result, digits)


def _csv_path(dataset: str) -> tuple[Path, dict[str, Any]]:
    datasets = local_knowledge.knowledge().get("datasets", {})
    meta = datasets.get(dataset)
    if not isinstance(meta, dict):
        raise VisualError("unknown dataset")
    path = (PROJECT_ROOT / str(meta.get("path", ""))).resolve()
    try:
        path.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise VisualError("invalid dataset path") from exc
    if not path.is_file():
        raise VisualError("dataset unavailable")
    raw = path.read_bytes()
    # The generated fingerprints hash canonical LF bytes. Git stores these
    # text files with LF endings, while a Windows checkout may expose CRLF.
    digest = hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()
    if digest != str(meta.get("sha256", "")):
        raise VisualError("dataset integrity check failed")
    return path, meta


def _frame(dataset: str):
    try:
        import pandas as pd
    except ImportError as exc:
        raise VisualError("scientific libraries unavailable") from exc
    path, meta = _csv_path(dataset)
    try:
        frame = pd.read_csv(path, na_values=["NA", "N/A", ""], keep_default_na=True)
    except Exception as exc:
        raise VisualError("dataset could not be read") from exc
    return frame, meta


def _source_note(meta: dict[str, Any], chichewa: bool) -> str:
    if chichewa:
        return (
            f"Gwero: fayilo ya deta yophunzitsira yopangidwa ya Python Command Library "
            f"`{meta.get('path', '')}` (SHA-256 `{meta.get('sha256', '')}`); yowerengedwa pa seva "
            "ndi NumPy, pandas, SciPy kapena statsmodels. Palibe gwero la intaneti kapena "
            "deta ya odwala yomwe yagwiritsidwa ntchito. Izi si zomwe anapeza pa kafukufuku."
        )
    return (
        f"Source: bundled Python Command Library simulated teaching file `{meta.get('path', '')}` "
        f"(SHA-256 `{meta.get('sha256', '')}`); computed server-side with NumPy, pandas, SciPy "
        "or statsmodels. No web source or patient record was used. These are teaching results, "
        "not research findings."
    )


def _chart_block(chart: dict[str, Any]) -> str:
    return "```chart\n" + json.dumps(chart, ensure_ascii=False, indent=2, sort_keys=True) + "\n```"


def _code_block(code: str) -> str:
    return "```python\n" + code.strip() + "\n```"


def _distribution(recipe: dict[str, Any], chichewa: bool) -> tuple[dict[str, Any], str, str]:
    import numpy as np
    import pandas as pd
    from scipy import stats
    from scipy.stats import gaussian_kde

    frame, meta = _frame(recipe["dataset"])
    series = pd.to_numeric(frame[recipe["column"]], errors="coerce").dropna()
    values = series.to_numpy(dtype=float)
    if values.size < 3:
        raise VisualError("not enough complete observations")
    mean, median, sd = float(values.mean()), float(np.median(values)), float(values.std(ddof=1))
    if not math.isfinite(sd) or sd <= 0:
        raise VisualError("zero-variance data cannot form a density curve")
    grid = np.linspace(float(values.min()), float(values.max()), 24)
    try:
        observed = gaussian_kde(values)(grid)
    except Exception:
        observed = stats.norm.pdf(grid, mean, sd)
    fitted = stats.norm.pdf(grid, mean, sd)
    labels = [f"{float(item):.0f}" for item in grid]
    observed_data = [_number(item, 6) for item in observed]
    fitted_data = [_number(item, 6) for item in fitted]
    if any(item is None for item in observed_data + fitted_data):
        raise VisualError("non-finite density value")
    chart = {
        "type": "line",
        "title": recipe["chart_title_ny"] if chichewa else recipe["chart_title_en"],
        "labels": labels,
        "datasets": [
            {"label": recipe["series_ny"][0] if chichewa else recipe["series_en"][0], "data": observed_data},
            {"label": recipe["series_ny"][1] if chichewa else recipe["series_en"][1], "data": fitted_data},
        ],
    }
    unit = "g" if recipe["column"] == "birthweight" else "g/dL" if recipe["column"] == "hb" else ""
    variable = "kulemera kwa mwana" if recipe["column"] == "birthweight" else "haemoglobin"
    if chichewa:
        summary = (
            f"Kuchokera pa zolemba {values.size} zathunthu za deta yophunzitsira, avareji ya "
            f"{variable} ndi {mean:.2f} {unit}, median ndi {median:.2f} {unit}, ndipo sample SD ndi "
            f"{sd:.2f} {unit}. Mphepete yoyamba ikuwonetsa kufalikira kwenikweni kwa deta pogwiritsa "
            "ntchito Gaussian KDE; yachiwiri ndi normal curve yofananira yomwe ili ndi avareji ndi SD "
            "yomweyo. Izi zikufotokoza deta yopangidwa yophunzitsira yokha, osati anthu enieni."
        )
    else:
        summary = (
            f"Using {values.size} complete records from the bundled simulated teaching cohort, the "
            f"mean {variable} is {mean:.2f} {unit}, the median is {median:.2f} {unit}, and the sample "
            f"SD is {sd:.2f} {unit}. The first curve is a Gaussian KDE of the observed values; the "
            "second is a fitted normal density with the same mean and SD. This describes only the "
            "simulated teaching dataset, not a real population."
        )
    code = f'''import pandas as pd
import numpy as np
from scipy import stats
from scipy.stats import gaussian_kde

df = pd.read_csv("{meta.get('path', '')}", na_values=["NA"])
x = pd.to_numeric(df["{recipe['column']}"], errors="coerce").dropna().to_numpy(float)
grid = np.linspace(x.min(), x.max(), 24)
kde = gaussian_kde(x)(grid)
normal = stats.norm.pdf(grid, x.mean(), x.std(ddof=1))
print("n =", len(x), "mean =", round(x.mean(), 2), "SD =", round(x.std(ddof=1), 2))'''
    return chart, summary, code


def _group_mean(recipe: dict[str, Any], chichewa: bool) -> tuple[dict[str, Any], str, str]:
    frame, meta = _frame(recipe["dataset"])
    import pandas as pd

    data = frame[[recipe["group"], recipe["column"]]].copy()
    data[recipe["column"]] = pd.to_numeric(data[recipe["column"]], errors="coerce")
    data = data.dropna().groupby(recipe["group"], sort=True)[recipe["column"]].agg(["mean", "count"])
    data = data.head(24)
    if data.empty:
        raise VisualError("no complete grouped observations")
    labels = [str(item) for item in data.index]
    values = [_number(item, 1) for item in data["mean"]]
    if any(item is None for item in values):
        raise VisualError("non-finite group mean")
    chart = {
        "type": "bar",
        "title": recipe["chart_title_ny"] if chichewa else recipe["chart_title_en"],
        "labels": labels,
        "datasets": [{"label": recipe["series_ny"][0] if chichewa else recipe["series_en"][0], "data": values}],
    }
    detail = "; ".join(f"{label}: {row['mean']:.1f} g (n={int(row['count'])})" for label, row in data.iterrows())
    if chichewa:
        summary = (
            f"Mu deta yopangidwa, avareji ya kulemera kwa makanda ndi {detail}. Mizere ikuwonetsa "
            "avareji za magulu okha; siziyerekeza zotsatira zosinthidwa kapena umboni wa causality."
        )
    else:
        summary = (
            f"In the simulated cohort, mean birth weight is {detail}. The bars are descriptive group "
            "summaries; they are not an adjusted comparison or evidence of causation."
        )
    code = f'''import pandas as pd

df = pd.read_csv("{meta.get('path', '')}", na_values=["NA"])
summary = (
    df[["{recipe['group']}", "{recipe['column']}"]]
    .assign(**{{"{recipe['column']}": pd.to_numeric(df["{recipe['column']}"], errors="coerce")}})
    .dropna()
    .groupby("{recipe['group']}")["{recipe['column']}"]
    .agg(["mean", "count"])
)
print(summary)'''
    return chart, summary, code


def _group_count(recipe: dict[str, Any], chichewa: bool) -> tuple[dict[str, Any], str, str]:
    frame, meta = _frame(recipe["dataset"])
    import pandas as pd

    data = frame[[recipe["group"], recipe["column"]]].copy()
    data[recipe["column"]] = pd.to_numeric(data[recipe["column"]], errors="coerce")
    counts = data[data[recipe["column"]] == 1].groupby(recipe["group"], sort=True).size().head(24)
    if counts.empty:
        raise VisualError("no complete grouped observations")
    chart = {
        "type": "bar",
        "title": recipe["chart_title_ny"] if chichewa else recipe["chart_title_en"],
        "labels": [str(item) for item in counts.index],
        "datasets": [{
            "label": recipe["series_ny"][0] if chichewa else recipe["series_en"][0],
            "data": [int(item) for item in counts],
        }],
    }
    detail = "; ".join(f"{label}: {int(value)}" for label, value in counts.items())
    total = int(len(data.dropna()))
    if chichewa:
        summary = (
            f"Pa zolemba {total} zathunthu za deta yopangidwa, makanda olembedwa kuti low_bw = 1 "
            f"ali ndi chiwerengerochi: {detail}. Ichi ndi chiwerengero chosakonzedwa, osati mwayi "
            "wa gulu lililonse kapena zotsatira za kafukufuku."
        )
    else:
        summary = (
            f"Among {total} complete records in the simulated teaching data, records flagged "
            f"low_bw = 1 are: {detail}. These are raw counts, not group risks or research findings."
        )
    code = f'''import pandas as pd

df = pd.read_csv("{meta.get('path', '')}", na_values=["NA"])
flag = pd.to_numeric(df["{recipe['column']}"], errors="coerce")
counts = df.loc[flag == 1, "{recipe['group']}"].value_counts().sort_index()
print(counts)'''
    return chart, summary, code


def _scatter(recipe: dict[str, Any], chichewa: bool) -> tuple[dict[str, Any], str, str]:
    frame, meta = _frame(recipe["dataset"])
    import pandas as pd
    from scipy import stats

    data = frame[[recipe["x"], recipe["y"]]].copy()
    for column in (recipe["x"], recipe["y"]):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna().head(80)
    if len(data) < 3:
        raise VisualError("not enough complete paired observations")
    x = data[recipe["x"]].to_numpy(dtype=float)
    y = data[recipe["y"]].to_numpy(dtype=float)
    result = stats.pearsonr(x, y)
    chart = {
        "type": "scatter",
        "title": recipe["chart_title_ny"] if chichewa else recipe["chart_title_en"],
        "datasets": [{
            "label": recipe["series_ny"][0] if chichewa else recipe["series_en"][0],
            "data": [{"x": _number(a, 2), "y": _number(b, 1)} for a, b in zip(x, y)],
        }],
    }
    if any(point["x"] is None or point["y"] is None for point in chart["datasets"][0]["data"]):
        raise VisualError("non-finite scatter point")
    r, p = float(result.statistic), float(result.pvalue)
    if chichewa:
        summary = (
            f"Kuchokera pa zolemba {len(data)} zoyamba zathunthu, Pearson r = {r:.3f} ndipo "
            f"p = {p:.4g}. Chati ikuwonetsa ubale wosakonzedwa pakati pa msinkhu wa mimba ndi "
            "kulemera kwa mwana. Ubale si umboni wa causality, ndipo chatiyo siyeso ya significance."
        )
    else:
        summary = (
            f"Using the first {len(data)} complete records, Pearson r = {r:.3f} and p = {p:.4g}. "
            "The plot shows the unadjusted relationship between gestational age and birth weight. "
            "Association is not causation, and the plot alone is not a significance test."
        )
    code = f'''import pandas as pd
from scipy import stats

df = pd.read_csv("{meta.get('path', '')}", na_values=["NA"])
data = df[["{recipe['x']}", "{recipe['y']}"]].apply(pd.to_numeric, errors="coerce").dropna().head(80)
r = stats.pearsonr(data["{recipe['x']}"], data["{recipe['y']}"])
print("n =", len(data), "Pearson r =", round(r.statistic, 3), "p =", round(r.pvalue, 4))'''
    return chart, summary, code


def _paired_mean(recipe: dict[str, Any], chichewa: bool) -> tuple[dict[str, Any], str, str]:
    frame, meta = _frame(recipe["dataset"])
    import pandas as pd
    from scipy import stats

    data = frame[[recipe["before"], recipe["after"]]].apply(pd.to_numeric, errors="coerce").dropna()
    before = data[recipe["before"]].to_numpy(dtype=float)
    after = data[recipe["after"]].to_numpy(dtype=float)
    if len(data) < 3:
        raise VisualError("not enough complete paired observations")
    test = stats.ttest_rel(after, before)
    labels = recipe["labels_ny"] if chichewa else recipe["labels_en"]
    chart = {
        "type": "line",
        "title": recipe["chart_title_ny"] if chichewa else recipe["chart_title_en"],
        "labels": labels,
        "datasets": [{
            "label": recipe["series_ny"][0] if chichewa else recipe["series_en"][0],
            "data": [_number(before.mean(), 1), _number(after.mean(), 1)],
        }],
    }
    change = float((after - before).mean())
    if chichewa:
        summary = (
            f"Pa awiriawiri {len(data)}, avareji ya systolic pressure inali {before.mean():.1f} mmHg "
            f"pa booking ndi {after.mean():.1f} mmHg pa masabata 36; kusintha kwa awiriawiri kunali "
            f"{change:+.1f} mmHg (paired t = {test.statistic:.3f}, p = {test.pvalue:.4g}). Paired "
            "test imagwiritsa ntchito kusiyana kwa munthu aliyense, osati magulu odziyimira pawokha. "
            "Deta iyi ndi yopangidwa yophunzitsira."
        )
    else:
        summary = (
            f"For {len(data)} matched pairs, mean systolic pressure was {before.mean():.1f} mmHg at "
            f"booking and {after.mean():.1f} mmHg at 36 weeks; the paired mean change was "
            f"{change:+.1f} mmHg (paired t = {test.statistic:.3f}, p = {test.pvalue:.4g}). The paired "
            "test uses within-person differences rather than treating the two columns as independent "
            "groups. These are simulated teaching data."
        )
    code = f'''import pandas as pd
from scipy import stats

df = pd.read_csv("{meta.get('path', '')}", na_values=["NA"])
pair = df[["{recipe['before']}", "{recipe['after']}"]].apply(pd.to_numeric, errors="coerce").dropna()
test = stats.ttest_rel(pair["{recipe['after']}"], pair["{recipe['before']}"])
print("n =", len(pair), "mean change =", round((pair.iloc[:, 1] - pair.iloc[:, 0]).mean(), 1))
print("paired t =", round(test.statistic, 3), "p =", round(test.pvalue, 4))'''
    return chart, summary, code


def _survival(recipe: dict[str, Any], chichewa: bool) -> tuple[dict[str, Any], str, str]:
    from statsmodels.duration.survfunc import SurvfuncRight

    frame, meta = _frame(recipe["dataset"])
    import numpy as np
    import pandas as pd

    data = frame[[recipe["time"], recipe["event"], recipe["group"]]].copy()
    data[recipe["time"]] = pd.to_numeric(data[recipe["time"]], errors="coerce")
    data[recipe["event"]] = pd.to_numeric(data[recipe["event"]], errors="coerce")
    data = data.dropna()
    if data.empty:
        raise VisualError("no complete survival observations")
    max_day = float(data[recipe["time"]].max())
    times = np.linspace(0.0, max_day, 13)
    groups = ["Anaemia", "No anaemia"]
    datasets = []
    values_at_end = {}
    for group in groups:
        subset = data[data[recipe["group"]] == group]
        if subset.empty:
            raise VisualError("missing survival group")
        fit = SurvfuncRight(subset[recipe["time"]], subset[recipe["event"]].astype(int))
        # statsmodels 0.15 exposes the step function as paired arrays, not a
        # callable. Evaluate the right-continuous estimate at the chart times.
        index = np.searchsorted(fit.surv_times, times, side="right") - 1
        probabilities = np.ones(len(times), dtype=float)
        after_first_event = index >= 0
        probabilities[after_first_event] = fit.surv_prob[index[after_first_event]]
        series = [_number(item, 4) for item in probabilities]
        if any(item is None for item in series):
            raise VisualError("non-finite survival probability")
        datasets.append({
            "label": (recipe["series_ny"][0] if group == groups[0] else recipe["series_ny"][1])
            if chichewa else group,
            "data": series,
        })
        values_at_end[group] = float(probabilities[-1])
    chart = {
        "type": "line",
        "title": recipe["chart_title_ny"] if chichewa else recipe["chart_title_en"],
        "labels": [f"{float(item):.0f}" for item in times],
        "datasets": datasets,
    }
    events = int(data[recipe["event"]].sum())
    if chichewa:
        summary = (
            f"Kuchokera pa zolemba {len(data)} za deta yopangidwa ndi zochitika {events}, Kaplan-Meier "
            f"pa tsiku {max_day:.0f} inali {values_at_end['Anaemia']:.3f} m'gulu la anaemia ndi "
            f"{values_at_end['No anaemia']:.3f} m'gulu opanda anaemia. Mphepete zikufotokoza mwayi "
            "wosabwerera kuchipatala mu deta yophunzitsira yokha; sizitanthauza zotsatira za "
            "chithandizo kapena kufalikira kwa odwala enieni."
        )
    else:
        summary = (
            f"Using {len(data)} simulated teaching records and {events} recorded events, the "
            f"Kaplan-Meier event-free probability at day {max_day:.0f} was "
            f"{values_at_end['Anaemia']:.3f} in the anaemia group and "
            f"{values_at_end['No anaemia']:.3f} in the no-anaemia group. The curves describe the "
            "teaching dataset only; they are not treatment effects or estimates for a real population."
        )
    code = f'''import numpy as np
import pandas as pd
from statsmodels.duration.survfunc import SurvfuncRight

df = pd.read_csv("{meta.get('path', '')}", na_values=["NA"])
for group in ["Anaemia", "No anaemia"]:
    row = df[df["{recipe['group']}"] == group]
    fit = SurvfuncRight(row["{recipe['time']}"], row["{recipe['event']}"].astype(int))
    end = float(row["{recipe['time']}"].max())
    index = np.searchsorted(fit.surv_times, end, side="right") - 1
    value = float(fit.surv_prob[index]) if index >= 0 else 1.0
    print(group, "event-free at end =", round(value, 3))'''
    return chart, summary, code


_BUILDERS = {
    "distribution": _distribution,
    "group_mean": _group_mean,
    "group_count": _group_count,
    "scatter": _scatter,
    "paired_mean": _paired_mean,
    "survival": _survival,
}


def _recipe_for(message: str) -> dict[str, Any] | None:
    recipes = local_knowledge.knowledge().get("visual_recipes", [])
    folded = message.casefold()
    best: tuple[int, dict[str, Any]] | None = None
    for recipe in recipes:
        score = sum(12 for alias in recipe.get("aliases", []) if str(alias).casefold() in folded)
        if score and (best is None or score > best[0]):
            best = (score, recipe)
    if best is not None:
        return best[1]
    if _VISUAL_INTENT.search(message) and _STATS_TERMS.search(message):
        return next((item for item in recipes if item["id"] == "birthweight_distribution"), None)
    return None


def supported_visual_answer(chichewa: bool) -> tuple[str, str, str]:
    options = (
        "kulemera kwa makanda, haemoglobin, kuthamanga kwa magazi kwa awiriawiri, "
        "kufalikira kwa zaka za mimba, magulu a zipatala, kapena mphepete yakupulumuka."
        if chichewa else
        "birth-weight or haemoglobin distributions, paired blood pressure, gestational-age "
        "scatter, facility group summaries, or a Kaplan-Meier curve."
    )
    if chichewa:
        return (
            "Ndingajambule chati kuchokera ku deta yophunzitsira yopangidwa yomwe ili mu Python "
            "Library: " + options + " Chonde tchulani imene mukufuna. Sindigwiritsa ntchito deta "
            "ya odwala enieni, ndipo palibe chati yojambulidwa chifukwa deta kapena variable "
            "sizinali zomveka.",
            PROVIDER, "supported-visual-options-v1",
        )
    return (
        "I can generate charts only from the verified simulated teaching datasets bundled with the "
        "Python Library: " + options + " Please name the one you want. I cannot use real patient "
        "records here. No chart was drawn because the requested data or variable was not clear.",
        PROVIDER, "supported-visual-options-v1",
    )


def answer_visual(message: str, response_language: str = "EN") -> tuple[str, str, str] | None:
    """Return a complete deterministic chart answer when the turn requests one."""
    chichewa = str(response_language).upper() == "CH"
    if not _VISUAL_INTENT.search(message):
        return None
    if _SCHEDULE_TERMS.search(message) and not _STATS_TERMS.search(message):
        return None
    if _REAL_DATA_TERMS.search(message):
        return supported_visual_answer(chichewa)
    recipe = _recipe_for(message)
    if recipe is None:
        return supported_visual_answer(chichewa)
    builder = _BUILDERS.get(str(recipe.get("kind")))
    if builder is None:
        return supported_visual_answer(chichewa)
    try:
        chart, summary, code = builder(recipe, chichewa)
    except VisualError:
        if chichewa:
            return (
                "Pepani, sindinathe kupanga chati kuchokera ku deta yotsimikizirika chifukwa fayilo "
                "yake ilipo yosowa, yosinthidwa kapena yosakwanira. Palibe nambala kapena chati "
                "yomwe yapangidwa.",
                PROVIDER, "visual-unavailable-v1",
            )
        return (
            "I cannot generate that chart from verified local data because the source file is "
            "missing, changed or incomplete. No values or chart have been invented.",
            PROVIDER, "visual-unavailable-v1",
        )
    heading = "## Chati yochokera ku deta yotsimikizirika" if chichewa else "## Chart from verified local teaching data"
    code_label = "**Khodi yobwerezabwereza**" if chichewa else "**Reproducible code**"
    answer = "\n\n".join([
        heading,
        summary,
        _source_note(local_knowledge.knowledge()["datasets"][recipe["dataset"]], chichewa),
        _chart_block(chart),
        f"{code_label}\n\n{_code_block(code)}",
    ])
    return answer, PROVIDER, MODEL

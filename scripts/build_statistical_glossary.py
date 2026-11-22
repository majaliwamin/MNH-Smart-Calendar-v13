#!/usr/bin/env python3
"""Build the additive bilingual statistical-tests glossary page.

Each glossary card uses the same short structure: term, English definition,
Chichewa explanation, analogy, Python example where applicable, code
explanation, practical application and common misconception. Code-bearing
entries remain self-contained notebook cells with fixed-seed synthetic data;
they are executed here and their real stdout is embedded in the static HTML,
so no clinical threshold, empirical result or invented number is hard-coded.
Conceptual terms may intentionally have no code example.
"""

from __future__ import annotations

import contextlib
import html
import io
import re
import sys
from pathlib import Path
from typing import Any

BUILD = "2026.11.22-statistical-tests-glossary-v42"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend" / "resources" / "python-statistical-tests-glossary.html"

CATEGORIES: list[tuple[str, str, str]] = [
    ("foundations", "1. Thinking before testing", "Kuganiza musanayese"),
    ("groups", "2. Comparing groups", "Kuyerekeza magulu"),
    ("categories", "3. Categories, counts and agreement", "Makategori, kuchuluka ndi kuvomerezana"),
    ("association", "4. Association and correlation", "Ubale ndi kulumikizana"),
    ("regression", "5. Regression and adjustment", "Regression ndi kusintha kwa zinthu"),
    ("advanced", "6. Advanced and robust analysis", "Njira zapamwamba ndi zolimba"),
]

ENTRIES: list[dict[str, Any]] = []


def E(
    *,
    category: str,
    term: str,
    term_ny: str,
    use_en: str,
    use_ny: str,
    assumptions_en: str,
    assumptions_ny: str,
    code: str | None,
    interpretation_en: str,
    interpretation_ny: str,
    limits_en: str,
    limits_ny: str,
    explanation_ny: str,
    analogy_en: str,
    explanation_en: str | None = None,
    analogy_ny: str,
    report_en: str,
    report_ny: str,
    application_en: str,
    application_ny: str,
) -> None:
    """Register one entry after validating and executing its example."""
    if category not in {item[0] for item in CATEGORIES}:
        raise ValueError(f"Unknown category: {category}")
    output = ""
    if code is not None:
        if "SIMULATED TEACHING DATA" not in code:
            raise ValueError(f"{term}: missing simulation label")
        if "default_rng(" not in code:
            raise ValueError(f"{term}: missing fixed-seed generator")
        if "http://" in code or "https://" in code or "requests." in code:
            raise ValueError(f"{term}: network access is not allowed")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exec(compile(code, f"<{term}>", "exec"), {"__name__": "__main__"})
        output = buffer.getvalue().rstrip()
        if not output:
            raise ValueError(f"{term}: example printed no output")
        if re.search(r"\b(?:nan|inf|infinity)\b", output, re.I):
            raise ValueError(f"{term}: example printed a non-finite result")
    ENTRIES.append(
        {
            "category": category,
            "term": term,
            "term_ny": term_ny,
            "use_en": use_en,
            "use_ny": use_ny,
            "assumptions_en": assumptions_en,
            "assumptions_ny": assumptions_ny,
            "code": code.strip() if code is not None else None,
            "output": output or None,
            "interpretation_en": interpretation_en,
            "interpretation_ny": interpretation_ny,
            "limits_en": limits_en,
            "limits_ny": limits_ny,
            "explanation_ny": explanation_ny,
            "explanation_en": explanation_en
            or (
                f"{term} answers a specific design question: {use_en.rstrip('.')}. "
                "The fixed-seed example shows what the method computes and how the "
                "result should be read; it is not a universal decision rule."
            ),
            "analogy_en": analogy_en,
            "analogy_ny": analogy_ny,
            "report_en": report_en,
            "report_ny": report_ny,
            "application_en": application_en,
            "application_ny": application_ny,
        }
    )


E(
    category="foundations",
    term="Hypothesis test and p-value",
    term_ny="Kuyeza mfundo ndi mtengo wa p",
    use_en="Use when you must decide whether observed data are compatible with a stated null model, such as whether a mean differs from a prespecified reference value.",
    use_ny="Gwiritsani ntchito pamene mukufuna kudziwa ngati deta yowonedwa ikugwirizana ndi lingaliro la null, monga kuyerekeza avareji ndi mtengo wokhazikitsidwa kale.",
    assumptions_en="State the null and alternative before looking at data; observations should be independent; the chosen test model should match the outcome type and design. For a one-sample t-test, the mean of reasonably independent measurements should be approximately normal, especially in small samples.",
    assumptions_ny="Lembani null ndi alternative musanayang'ane deta; ma observation azikhala odziyimira pawokha; mtundu wa mayeso ugwirizane ndi mtundu wa deta ndi kapangidwe ka kafukufuku. Pa t-test ya gulu limodzi, avareji iyenera kukhala pafupifupi yofanana ndi normal, makamaka ngati deta ndi yochepa.",
    code='''import numpy as np
from scipy import stats

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112201)
values = rng.normal(loc=9.8, scale=1.6, size=40)

test = stats.ttest_1samp(values, popmean=9.0)
ci = test.confidence_interval(confidence_level=0.95)
print("n =", len(values), "mean =", round(float(values.mean()), 3))
print("t =", round(float(test.statistic), 3), "p =", round(float(test.pvalue), 4))
print("95% CI for mean =", round(float(ci.low), 3), "to", round(float(ci.high), 3))''',
    interpretation_en="The t statistic says how many standard errors the sample mean is from the null value. A small p-value means data this extreme would be unusual if the null were true; it does not prove the alternative or measure importance. The confidence interval shows the plausible range for the mean itself.",
    interpretation_ny="Mtengo wa t ukusonyeza kuti avareji ya sample ili kutali bwanji ndi mtengo wa null potengera standard error. p ikachepa, deta yotere ingakhale yosowa ngati null ili yoona; izi sizikutsimikizira kuti alternative ndi yoona kapena kuti zotsatira ndi zofunika. Confidence interval imasonyeza mtengo womwe ungathe kukhala wa avareji.",
    limits_en="A p-value is not the probability that the null hypothesis is true. Significance depends on sample size; always report the estimate and interval. Multiple testing, selective reporting and violated independence invalidate the usual interpretation.",
    limits_ny="p si mwayi wakuti null ndi yoona. Kufunika kwake kumadalira kuchuluka kwa deta; nthawi zonse nenani mtengo woyerekeza ndi interval. Kuyeza kangapo, kusankha zotsatira zokongola, kapena kuswa independence kumawononga tanthauzo lake.",
    explanation_ny="Mukayesa mfundo, mumayamba mwakhazikitsa lingaliro loti palibe kusiyana. Kenako mumafunsa: ngati lingalirolo lili loona, kodi deta yathu ingakhale yotere? p ikuyankha funso limenelo, osati funso lakuti mfundo yanu ndi yoona kapena ayi.",
    analogy_en="A p-value is like checking how surprising a bus arrival time is under a published timetable. A very late bus is evidence against the timetable, but it does not prove the driver ignored it, and it does not tell you how much the service has changed.",
    analogy_ny="p ndi ngati kuyang'ana nthawi yofika basi potengera ndandanda wolembedwa. Basi ikafika mochedwa kwambiri, izi zikutsutsa ndandandawu, koma sizikutsimikizira kuti dalaivala anyalanyaza ndandanda, komanso sizikuonetsa kuchuluka kwa kusintha kwake.",
    report_en="Report the estimated mean with its 95% CI, the test statistic, p-value, sample size and the prespecified null value. Avoid the phrase 'prove'.",
    report_ny="Fotokozani avareji yoyerekeza ndi 95% CI yake, mtengo wa test, p, kuchuluka kwa deta ndi mtengo wa null wokhazikitsidwa kale. Pewani mawu akuti 'kutsimikizira'.",
    application_en="Comparing a cohort's mean birth weight with a national reference value, provided the reference and measurement method are appropriate.",
    application_ny="Kuyerekeza avareji ya kulemera kwa makanda ndi mtengo wadziko lonse, ngati mtengowo ndi njira yoyezera zikugwirizana.",
)

E(
    category="foundations",
    term="Effect size with confidence interval",
    term_ny="Kukula kwa zotsatira ndi confidence interval",
    use_en="Use when a p-value alone is not enough and you need to communicate how large a difference is and how precisely it has been estimated.",
    use_ny="Gwiritsani ntchito pamene p yokha sikukwanira ndipo mukufuna kusonyeza kukula kwa kusiyana komanso kudziwa bwino kuyerekezako.",
    assumptions_en="The two groups are independent; the outcome is continuous; Cohen's d assumes comparable within-group spread. Welch’s interval does not require equal variances but still relies on approximate normality of the group means.",
    assumptions_ny="Magulu awiri ndi odziyimira pawokha; zotsatira ndi za manambala; Cohen's d imaganizira kufanana kwa kufalikira mkati mwa magulu. Welch interval safuna kuti variances zikhale zofanana koma imadalira kuti avareji azikhala pafupifupi normal.",
    code='''import numpy as np
from scipy import stats

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112202)
control = rng.normal(3100, 420, 60)
exposed = rng.normal(3250, 430, 55)

diff = exposed.mean() - control.mean()
pooled_sd = np.sqrt(((len(control)-1)*control.var(ddof=1) +
                     (len(exposed)-1)*exposed.var(ddof=1)) /
                    (len(control)+len(exposed)-2))
d = diff / pooled_sd
J = 1 - 3/(4*(len(control)+len(exposed))-9)
g = J*d
welch = stats.ttest_ind(exposed, control, equal_var=False)
ci = welch.confidence_interval(0.95)
print("mean difference =", round(float(diff), 1))
print("Welch 95% CI =", round(float(ci.low), 1), "to", round(float(ci.high), 1))
print("Cohen d =", round(float(d), 3), "Hedges g =", round(float(g), 3))''',
    interpretation_en="The mean difference is in the original units, so it is usually the most directly useful number. Cohen's d and Hedges' g standardise the difference; Hedges' g applies a small-sample correction. The CI shows the range of differences compatible with the data under the model.",
    interpretation_ny="Kusiyana kwa avareji kuli mu mayunitsi oyambirira, choncho nthawi zambiri ndi nambala yothandiza kwambiri. Cohen's d ndi Hedges' g zimasintha kusiyana kukhala muyezo wofanana; Hedges' g imakonza pang'ono pazochepa. CI imasonyeza kusiyana kotheka potengera deta ndi model.",
    limits_en="Standardised effects can look larger in homogeneous samples and smaller in heterogeneous ones. They are not universal clinical thresholds. Report the raw units and the population context beside any d or g value.",
    limits_ny="Zotsatira zokhazikika zingawoneke zazikulu mu deta yofanana kwambiri kapena zazing'ono mu deta yosiyana kwambiri. Sizili malire azachipatala omwe amagwiritsidwa ntchito kulikonse. Nenani mayunitsi oyambirira ndi mbiri ya anthu pamodzi ndi d kapena g iliyonse.",
    explanation_ny="Kukula kwa zotsatira kumayankha funso lakuti 'kusiyana n'kukulu bwanji?', pamene p imayankha lakuti 'kodi kusiyana kumeneku kungachitike mwangozi?'. Mafunso onse awiri ndi ofunika koma si ofanana.",
    analogy_en="A mean difference is like saying a harvest is 20 kg larger; Cohen's d is like saying that gain is large relative to the usual variation between harvests. Both descriptions matter.",
    analogy_ny="Kusiyana kwa avareji kuli ngati kunena kuti zokolola ziwonjezeka ndi 20 kg; Cohen's d ili ngati kunena kuti kuwonjezekako n'kukulu poyerekeza ndi kusiyana kwamba pakati pa zokolola. Mafotokozedwe onse awiri ndi ofunika.",
    report_en="State the raw mean difference with 95% CI, then the standardised effect if useful. Name the population, units and group definitions.",
    report_ny="Nenani kusiyana kwa avareji ndi 95% CI, kenako zotsatira zokhazikika ngati zikuthandiza. Tchulani gulu la anthu, mayunitsi ndi matanthauzo a magulu.",
    application_en="Quantifying how much a nutrition intervention changes mean birth weight, alongside the precision of that estimate.",
    application_ny="Kuyeza kuchuluka komwe pulogalamu ya zakudya imasintha avareji ya kulemera kwa makanda, pamodzi ndi kudziwa bwino kwa kuyerekeza kumeneko.",
)

E(
    category="foundations",
    term="Multiple-testing correction",
    term_ny="Kukonza kwa mayeso ambiri",
    use_en="Use when you test several hypotheses in one analysis and must control either the chance of any false positive (FWER) or the expected false-discovery proportion (FDR).",
    use_ny="Gwiritsani ntchito pamene muyeza mfundo zambiri mu kafukufuku umodzi ndipo mukufuna kuchepetsa mwayi wa zotsatira zabodza zilizonse kapena gawo la zopezeka zabodza.",
    assumptions_en="The family of tests should be defined before analysis. p-values must be valid individually. Holm controls family-wise error and is appropriate for a small confirmatory family; Benjamini-Hochberg controls FDR and is common in exploratory screening.",
    assumptions_ny="Gulu la mayeso liyenera kufotokozedwa musanayambe kusanthula. p ya mayeso aliyonse iyenera kukhala yovomerezeka. Holm imachepetsa mwayi wa zolakwika zilizonse; Benjamini-Hochberg imachepetsa gawo la zopezeka zabodza ndipo imagwiritsidwa ntchito kwambiri pakufufuza koyambirira.",
    code='''import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112203)
n = 40
x = rng.normal(0, 1, (8, n))
y = rng.normal(0, 1, (8, n))
y[:2] += 0.8
p_raw = stats.ttest_ind(x, y, axis=1).pvalue

reject_holm, p_holm, _, _ = multipletests(p_raw, method="holm")
reject_bh, p_bh, _, _ = multipletests(p_raw, method="fdr_bh")
out = pd.DataFrame({"test": range(1, 9), "raw_p": p_raw.round(4),
                    "holm_p": p_holm.round(4), "bh_p": p_bh.round(4),
                    "holm_sig": reject_holm, "bh_sig": reject_bh})
print(out.to_string(index=False))''',
    interpretation_en="Raw p-values are too optimistic when many tests are examined. Adjusted p-values are larger; Holm is stricter, while BH allows a controlled proportion of false discoveries. Compare which tests remain flagged under each method.",
    interpretation_ny="p zosakonzedwa zimakhala zolimbikitsa kwambiri ngati mayeso ndi ambiri. p zosinthidwa zimakula; Holm ndi yowuma kwambiri, pamene BH imalola gawo lolamulidwa la zopezeka zabodza. Fananizani mayeso omwe akadakhalabe odziwika pansi pa njira iliyonse.",
    limits_en="Correction does not repair biased tests, poor design or dependence that violates the chosen method's assumptions. Pre-specifying a small primary family is better than correcting an unlimited exploratory fishing expedition.",
    limits_ny="Kukonza sikukonza mayeso olakwika, kapangidwe koyipa, kapena kudalirana komwe kuswa mfundo za njirayo. Kufotokozeratu gulu laling'ono la mayeso oyamba ndikwabwino kukonza kusaka kopanda malire.",
    explanation_ny="Ngati muyeza makiyi ambiri, mwayi wopeza imodzi yabodza ukuwonjezeka. Kukonza kwa mayeso ambiri kumalimbitsa muyezo wotchedwa 'significant' kuti musakhulupirire zopezeka mwangozi.",
    analogy_en="Testing many outcomes is like buying many lottery tickets. If you check enough tickets, one may look lucky; correction raises the standard for calling that luck meaningful.",
    analogy_ny="Kuyeza zotsatira zambiri kuli ngati kugula matikiti ambiri a lotale. Mukayang'ana ambiri, imodzi ingawoneke yamwayi; kukonzako kumakweza muyezo wotchedwa kuti mwayiwo ndi wofunika.",
    report_en="Name the test family, the correction method and whether the analysis was confirmatory or exploratory. Report adjusted p-values and effect estimates.",
    report_ny="Tchulani gulu la mayeso, njira yosinthira ndi kaya kusanthula kunali kotsimikizira kapena kofufuza. Fotokozani p zosinthidwa ndi kuyerekeza kwa zotsatira.",
    application_en="Screening many biomarkers for association with an exposure while limiting misleading discoveries.",
    application_ny="Kusakha ma biomarker ambiri kuti muwone ubale ndi matenda popanda kukhulupirira zopezeka zabodza.",
)

E(
    category="foundations",
    term="Power and sample size",
    term_ny="Mphamvu ya mayeso ndi kukula kwa sample",
    use_en="Use at the design stage to decide how many participants are needed to detect an effect of practical interest with acceptable power, or to calculate the power of a planned sample size.",
    use_ny="Gwiritsani ntchito popanga kafukufuku kuti mudziwe ochita nawo kafukufuku angati omwe akufunika kuti azindikire zotsatira zofunika, kapena kuwerengera mphamvu ya sample yomwe yakonzedwa.",
    assumptions_en="You must specify effect size, alpha, desired power, allocation ratio and the test. Pilot effect estimates are uncertain, so a range of plausible effects should be examined rather than a single optimistic number.",
    assumptions_ny="Muyenera kufotokoza kukula kwa zotsatira, alpha, mphamvu yofunidwa, chiŵerengero cha magulu ndi mayeso. Kuyerekeza kwa pilot sikudziwika bwino, choncho yang'anani zotsatira zosiyanasiyana zotheka osati nambala imodzi yokha.",
    code='''import numpy as np
from statsmodels.stats.power import TTestIndPower
from statsmodels.stats.proportion import proportion_effectsize

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112204)
pilot_control = rng.binomial(1, 0.20, 80)
pilot_treated = rng.binomial(1, 0.32, 80)
effect = abs(proportion_effectsize(pilot_treated.mean(), pilot_control.mean()))
analysis = TTestIndPower()
n_each = analysis.solve_power(effect_size=effect, alpha=0.05,
                              power=0.80, ratio=1.0,
                              alternative="two-sided")
power_60 = analysis.power(effect_size=effect, nobs1=60, alpha=0.05,
                          ratio=1.0, alternative="two-sided")
print("pilot proportions =", round(pilot_control.mean(), 3),
      "and", round(pilot_treated.mean(), 3))
print("standardised effect =", round(float(effect), 3))
print("n per group for 80% power =", int(np.ceil(n_each)))
print("power with 60 per group =", round(float(power_60), 3))''',
    interpretation_en="The pilot proportions provide a crude standardised effect. The required n is per group for a two-sided test at alpha 0.05. If only 60 per group are available, the printed power may be too low, meaning a real effect could easily be missed.",
    interpretation_ny="Zigawo za pilot zimapereka kuyerekeza kwa zotsatira zokhazikika. n yofunikira ndi pa gulu limodzi pa mayeso awiri a alpha 0.05. Ngati magulu 60 okha alipo, mphamvu yosindikizidwa ingakhale yotsika, kotero zotsatira zenizeni zikhoza kuphonya.",
    limits_en="Power calculations are only as good as their assumptions. A pilot-based effect is noisy and often exaggerated. Account for dropout, clustering, non-adherence and the primary endpoint before fixing the final sample size.",
    limits_ny="Kuwerengera mphamvu kumadalira mfundo zomwe mwayika. Zotsatira za pilot zimakhala zaphokoso ndipo nthawi zambiri zimakokomeza. Ganizirani kutayika kwa omwe atengapo mbali, kugwirizana m'magulu, kusamvera malangizo ndi mfundo yayikulu musanatsimikize kukula kwa sample.",
    explanation_ny="Mphamvu ndi mwayi wozindikira kusiyana ngati kusiyana kwenikweni kulipo. Sample ikachepa, ngakhale mankhwala angathandize, kafukufuku angaphonye kuzindikira.",
    analogy_en="Power is like using a net with a certain mesh size. A fine enough net catches small fish; a coarse net may let them escape even when they are present.",
    analogy_ny="Mphamvu ili ngati ukonde wokhala ndi mabowo a kukula kwake. Ukonde wabwino ugwira nsomba zazing'ono; wokhala ndi mabowo akulu ukhoza kuzilola kuthawa ngakhale zilipo.",
    report_en="Document the assumed effect, alpha, power, allocation ratio, software method and allowance for attrition. Treat the result as a design estimate, not a guarantee.",
    report_ny="Lembani zotsatira zomwe zaganiziridwa, alpha, mphamvu, chiŵerengero cha magulu, njira ya pulogalamu ndi kuchuluka kwa omwe angatayeke. Tengani zotsatirapo monga kuyerekeza kwa kapangidwe, osati chitsimikizo.",
    application_en="Planning a two-arm intervention study before recruitment begins.",
    application_ny="Kukonzekera kafukufuku wa magulu awiri musanayambe kusonkhanitsa anthu.",
)

E(
    category="foundations",
    term="Sampling variability and standard error",
    term_ny="Kusiyana kwa sample ndi standard error",
    use_en="Use when you want to understand why two samples from the same population give different estimates, and how much an estimate typically varies across repeated samples.",
    use_ny="Gwiritsani ntchito pamene mukufuna kumvetsetsa chifukwa chake sample ziwiri zachokera ku gulu limodzi zimapereka zotsatira zosiyana, komanso kuchuluka kwa kusiyana kwake.",
    assumptions_en="Samples are independent and drawn from the same population; the statistic has a finite variance. The simulation below uses a known synthetic population so the true value is available for teaching only.",
    assumptions_ny="Ma sample ndi odziyimira pawokha ndipo achokera ku gulu limodzi; chiwerengerocho chili ndi variance yochepa. Kusimulitsa kotsika kumagwiritsa ntchito gulu lopangidwa kuti phindu lenileni lidziwike pophunzitsira kokha.",
    code='''import numpy as np

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112205)
population = rng.lognormal(mean=7.0, sigma=0.35, size=50000)
true_mean = population.mean()
means = np.array([rng.choice(population, size=50, replace=True).mean()
                  for _ in range(2000)])
se_theory = population.std(ddof=1) / np.sqrt(50)
print("true simulated population mean =", round(float(true_mean), 2))
print("mean of 2000 sample means =", round(float(means.mean()), 2))
print("SD of sample means =", round(float(means.std(ddof=1)), 2))
print("theoretical SE =", round(float(se_theory), 2))''',
    interpretation_en="Individual sample means vary, but their average is close to the simulated population mean. The SD of those means is the standard error; the formula-based SE should be close. This is the idea behind confidence intervals and p-values.",
    interpretation_ny="Avareji a sample amasiyana, koma avareji yawo yonse ili pafupi ndi avareji ya gulu lopangidwa. SD ya avareji imeneyo ndi standard error; mtengo wa formula uyenera kukhala pafupi. Ichi ndi maziko a confidence intervals ndi p-values.",
    limits_en="The central limit theorem is an approximation. Very small samples from strongly skewed distributions can behave poorly. Repeated sampling here is simulated teaching data, not a description of an actual cohort.",
    limits_ny="Central limit theorem ndi kuyerekeza chabe. Ma sample ang'onoang'ono ochokera ku deta yopendekerera kwambiri angakhale osadalirika. Kusankhanso sample apa ndi deta yophunzitsira, osati kufotokoza gulu lenileni.",
    explanation_ny="Ngati mutenga magulu ang'onoang'ono ambiri kuchokera ku gulu limodzi, avareji yawo simakhala yofanana nthawi zonse. Kufalikira kwa ma avareji amenewo kumatiuza kuchuluka kwa kusatsimikizika kwa kuyerekeza kumodzi.",
    analogy_en="Standard error is like the spread of repeated spoonfuls from a well-mixed pot. One spoonful may differ, but the average of many spoonfuls is stable.",
    analogy_ny="Standard error ili ngati kusiyana kwa supuni zambiri zotengedwa mu mphika wosakanizidwa bwino. Supuni imodzi ingasiyane, koma avareji ya supuni zambiri imakhala yokhazikika.",
    report_en="Explain that uncertainty comes from sampling, report the SE or CI, and state the sampling design. Do not confuse SD of observations with SE of the mean.",
    report_ny="Fotokozani kusatsimikizika kumachokera ku kusankha sample, nenani SE kapena CI, ndi kufotokoza kapangidwe ka kusankha. Musasokoneze SD ya ma observation ndi SE ya avareji.",
    application_en="Explaining why a single cohort estimate is uncertain and why larger studies give narrower intervals.",
    application_ny="Kufotokoza chifukwa chake kuyerekeza kwa gulu limodzi kusatsimikizika komanso chifukwa chake maphunziro akulu amakhala ndi ma interval opapatiza.",
)

E(
    category="foundations",
    term="Permutation test logic",
    term_ny="Malingaliro a permutation test",
    use_en="Use when you want a distribution-free way to test a sharp null hypothesis, especially with small samples or a statistic whose theoretical distribution is awkward.",
    use_ny="Gwiritsani ntchito pamene mukufuna kuyesa mfundo ya null popanda kudalira mtundu wa kufalikira, makamaka ngati deta ndi yochepa kapena chiwerengerocho chili chovuta kuwerengera.",
    assumptions_en="Under the sharp null, observations are exchangeable between groups. The resampling must respect the design; do not permute paired or clustered observations as if they were independent.",
    assumptions_ny="Pansi pa null yokhwima, ma observation ayenera kusinthana pakati pa magulu. Kusankhanso kuyenera kulemekeza kapangidwe ka kafukufuku; musasinthane ma observation ogwirizana kapena a gulu ngati kuti ndi odziyimira pawokha.",
    code='''import numpy as np

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112206)
group_a = rng.normal(12.0, 2.0, 14)
group_b = rng.normal(14.2, 2.0, 14)
observed = group_b.mean() - group_a.mean()
pooled = np.concatenate([group_a, group_b])
n_a = len(group_a)
count = 0
B = 20000
for _ in range(B):
    shuffled = rng.permutation(pooled)
    stat = shuffled[n_a:].mean() - shuffled[:n_a].mean()
    if abs(stat) >= abs(observed) - 1e-12:
        count += 1
print("observed difference =", round(float(observed), 3))
print("two-sided permutation p =", round((count + 1)/(B + 1), 4))''',
    interpretation_en="The permutation p-value is the fraction of randomly reassigned datasets with a difference at least as extreme as the observed one. It uses the data's own rearrangement as the reference distribution instead of a textbook formula.",
    interpretation_ny="p ya permutation ndi gawo la deta yosinthidwa mwachisawawa yomwe kusiyana kwake kuli kokulirapo kapena kofanana ndi kowonedwa. Imagwiritsa ntchito kusinthasintha kwa deta yeniyeni m'malo mwa formula ya buku.",
    limits_en="Exchangeability is a strong assumption and can fail with unequal variances, time trends or clustering. With very few possible permutations the minimum p-value is coarse. Computation grows quickly with sample size.",
    limits_ny="Kusinthana kungakhale kolimba ndipo kungalephere ngati variances zosiyana, nthawi kapena magulu ogwirizana. Ngati kusinthana kochepa, p yocheperako imakhala yosakhwima. Kuwerengera kumakula msanga ndi kukula kwa deta.",
    explanation_ny="Ngati palibe kusiyana kwenikweni, zilembo za gulu A ndi B ziyenera kusinthasintha mofanana. Timasakaniza zilembowo mobwerezabwereza kuti tiwone kodi kusiyana kwathu kuli kodabwitsa bwanji.",
    analogy_en="It is like shuffling team labels on a list of runners. If the labels do not matter, many shuffles will produce differences as large as the one you saw.",
    analogy_ny="Zili ngati kusakaniza zilembo za magulu a othamanga. Ngati zilembozo sizifunika, kusakaniza kwambiri kudzatulutsa kusiyana kofanana kapena kokulirapo ndi komwe munawona.",
    report_en="State the statistic, number of permutations, exchangeability rationale and whether the test was one- or two-sided.",
    report_ny="Nenani chiwerengero choyesedwa, kuchuluka kwa kusinthana, chifukwa chomwe kusinthana kumavomerezeka ndi kaya mayesowo anali amodzi kapena awiri.",
    application_en="Comparing a small pilot group with a control when a parametric assumption is doubtful.",
    application_ny="Kuyerekeza gulu laling'ono la pilot ndi gulu lolamulira pamene mfundo za parametric zikukayikiridwa.",
)

E(
    category="groups",
    term="Independent samples t-test",
    term_ny="t-test ya magulu odziyimira pawokha",
    use_en="Use Student's independent-samples t-test to compare the means of two unrelated groups when a common within-group variance is a defensible model.",
    use_ny="Gwiritsani ntchito Student's t-test ya magulu odziyimira pawokha poyerekeza avareji a magulu awiri osagwirizana pamene kufalikira kofanana mkati mwa magulu kuli kovomerezeka.",
    assumptions_en="Observations are independent between and within groups; the outcome is continuous; group means are approximately normal, especially with small samples; the two groups have similar variances and no dominant outlier.",
    assumptions_ny="Ma observation ndi odziyimira pawokha mkati ndi pakati pa magulu; zotsatira ndi za manambala; avareji a magulu ali pafupifupi normal, makamaka ngati deta ndi yochepa; magulu awiriwo ali ndi variances zofanana komanso palibe outlier wamkulu.",
    code='''import numpy as np
from scipy import stats

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112240)
standard = rng.normal(3200, 380, 55)
new_care = rng.normal(3330, 390, 48)

res = stats.ttest_ind(new_care, standard, equal_var=True)
ci = res.confidence_interval(0.95)
print("means =", round(float(standard.mean()), 1), "and",
      round(float(new_care.mean()), 1))
print("pooled t =", round(float(res.statistic), 3),
      "df =", round(float(res.df), 1), "p =", round(float(res.pvalue), 4))
print("95% CI for difference =", round(float(ci.low), 1), "to",
      round(float(ci.high), 1))''',
    interpretation_en="equal_var=True asks SciPy to pool the two variances into one common estimate. The t statistic is the mean difference divided by its pooled standard error; the interval shows the plausible size of that difference.",
    interpretation_ny="equal_var=True imauza SciPy kuti igwirizanitse variances ziwirizo kukhala chimodzi. t ndi kusiyana kwa avareji kogawidwa ndi standard error yophatikizidwa; interval imasonyeza kukula kotheka kwa kusiyana.",
    limits_en="If variances differ markedly, Welch’s t-test is usually safer. This test compares means only; it does not adjust for confounding and it is invalid for paired data.",
    limits_ny="Ngati variances zasiyana kwambiri, Welch’s t-test nthawi zambiri ndi yotetezeka. Mayesowa uyerekeza avareji okha; suchotsa zinthu zosokoneza ndipo si woyenera deta yophatikizidwa.",
    explanation_ny="Independent samples t-test imafunsa kuti avareji a magulu awiri osiyana ndi osiyana kwambiri poyerekeza ndi kufalikira kwa deta mkati mwa gulu lililonse. 'Independent' kutanthauza kuti munthu aliyense ali mugulu limodzi lokha.",
    analogy_en="It is like comparing the average harvest of two separate farms. Each farm contributes its own yield once, and the comparison asks whether the difference is larger than ordinary farm-to-farm variation.",
    analogy_ny="Zili ngati kuyerekeza zokolola zapakati pa mafakitale awiri osiyana. Famu iliyonse imapereka zokolola zake kamodzi, ndipo kuyerekezako kumafunsa kuti kusiyana kwake n'kwakukulu kuposa kusiyana kwamba.",
    report_en="Report each group's n, mean and SD, the mean difference with 95% CI, pooled t, df and p. Name the equal-variance assumption.",
    report_ny="Nenani n, avareji ndi SD ya gulu lililonse, kusiyana kwa avareji ndi 95% CI, pooled t, df ndi p. Tchulani mfundo ya variances zofanana.",
    application_en="Comparing mean birth weight between two independently sampled regions when spread is comparable.",
    application_ny="Kuyerekeza avareji ya kulemera kwa makanda pakati pa madera awiri osiyana pamene kufalikira kuli kofanana.",
)

E(
    category="groups",
    term="Welch two-sample t-test",
    term_ny="Welch t-test ya magulu awiri",
    use_en="Use to compare the means of two independent groups when their variances may differ. It is a safer default than Student's equal-variance t-test for most real data.",
    use_ny="Gwiritsani ntchito kuyerekeza avareji a magulu awiri odziyimira pawokha pamene variances zawo zingasiyane. Nthawi zambiri ndi yotetezeka kuposa Student's t-test yofuna variances zofanana.",
    assumptions_en="Independent observations, continuous outcome, approximate normality of each group mean, and no extreme influential outliers. Welch does not assume equal variances.",
    assumptions_ny="Ma observation odziyimira pawokha, zotsatira za manambala, avareji ya gulu iliyonse pafupifupi normal, komanso palibe ma outlier owopsa. Welch saganizira kuti variances zili zofanana.",
    code='''import numpy as np
from scipy import stats

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112207)
standard = rng.normal(3200, 380, 55)
new_care = rng.normal(3330, 520, 48)

res = stats.ttest_ind(new_care, standard, equal_var=False)
ci = res.confidence_interval(0.95)
print("means =", round(float(standard.mean()), 1), "and",
      round(float(new_care.mean()), 1))
print("SDs =", round(float(standard.std(ddof=1)), 1), "and",
      round(float(new_care.std(ddof=1)), 1))
print("Welch t =", round(float(res.statistic), 3),
      "df =", round(float(res.df), 2), "p =", round(float(res.pvalue), 4))
print("95% CI for difference =", round(float(ci.low), 1), "to",
      round(float(ci.high), 1))''',
    interpretation_en="The means and SDs show the direction and spread. Welch’s t and adjusted degrees of freedom account for unequal variances. The p-value tests a zero mean difference; the CI gives the plausible size of the difference.",
    interpretation_ny="Avareji ndi SD zikusonyeza komwe kusiyana kulili komanso kufalikira kwake. Welch t ndi degrees of freedom zosinthidwa zimagwirizana ndi variances zosiyana. p imayesa kusiyana kwa zero; CI imapereka kukula kotheka kwa kusiyana.",
    limits_en="A t-test compares means, not entire distributions. Two groups can differ in shape or spread while having similar means. It does not adjust for confounding and is not a paired analysis.",
    limits_ny="t-test imayerekeza avareji, osati kufalikira kwathunthu. Magulu awiri angasiyane mawonekedwe kapena kufalikira koma avareji yawo ikhale yofanana. Sichotsa zinthu zosokoneza ndipo si yoyenera deta yophatikizidwa.",
    explanation_ny="Welch imafunsa kuti kodi avareji ya magulu awiri odziyimira pawokha ndi yosiyana kwambiri poyerekeza ndi kufalikira kwa deta. Simafuna kuti magulu awiriwo akhale ndi kufalikira kofanana.",
    analogy_en="Comparing two classrooms with different spreads of marks: Welch adjusts for the fact that one class may be much more variable than the other.",
    analogy_ny="Kuyerekeza makalasi awiri omwe mphambu zawo zimafalikira mosiyanasiyana: Welch imaganizira kuti kalasi imodzi ikhoza kukhala yosiyana kwambiri ndi inzake.",
    report_en="Report group means, SDs and n, mean difference with 95% CI, Welch t, df and p. Say 'Welch’s t-test' explicitly.",
    report_ny="Nenani avareji a magulu, SD ndi n, kusiyana kwa avareji ndi 95% CI, Welch t, df ndi p. Tchulani momveka kuti 'Welch’s t-test'.",
    application_en="Comparing mean birth weight between infants from two independently sampled regions.",
    application_ny="Kuyerekeza avareji ya kulemera kwa makanda ochokera kumadera awiri osiyana.",
)

E(
    category="groups",
    term="Paired t-test",
    term_ny="Paired t-test ya deta yophatikizidwa",
    use_en="Use when the same participant is measured twice, or when matched participants are compared, and the outcome is continuous. Analyse the within-pair differences.",
    use_ny="Gwiritsani ntchito pamene munthu yemweyo ayezedwa kawiri, kapena anthu ofanana akuyerekezedwa, ndipo zotsatira ndi manambala. Unikani kusiyana kwa mkati mwa awiriawiri.",
    assumptions_en="Pairs are independent of each other; differences are approximately normal, especially in small samples; pair identity is correct. Do not treat repeated observations as independent observations.",
    assumptions_ny="Awiriawiri ndi odziyimira pawokha pakati pawo; kusiyana kwawo kuli pafupifupi normal, makamaka ngati deta ndi yochepa; zizindikiritso za awiriawiri zili zolondola. Musatenge ma observation obwerezabwereza ngati odziyimira pawokha.",
    code='''import numpy as np
from scipy import stats

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112208)
baseline = rng.normal(118, 14, 45)
follow_up = baseline + rng.normal(-4.5, 9.0, 45)
diff = follow_up - baseline

res = stats.ttest_rel(follow_up, baseline)
ci = res.confidence_interval(0.95)
print("mean change =", round(float(diff.mean()), 2))
print("SD of changes =", round(float(diff.std(ddof=1)), 2))
print("t =", round(float(res.statistic), 3), "p =", round(float(res.pvalue), 4))
print("95% CI for mean change =", round(float(ci.low), 2), "to",
      round(float(ci.high), 2))''',
    interpretation_en="The analysis is on the changes within participants. A negative mean change means the follow-up value is lower on average. The CI shows the plausible average change, and the p-value tests whether that average change is zero.",
    interpretation_ny="Kusanthula kumachitika pa kusiyana kwa mkati mwa munthu aliyense. Kusiyana koyipa kumatanthauza kuti mtengo wotsatira unatsika pafupifupi. CI imasonyeza kusintha kotheka kwa avareji, ndipo p imayesa ngati kusinthako kuli zero.",
    limits_en="A significant average change may hide heterogeneity: some participants can improve while others worsen. Loss to follow-up can bias the result if it is related to the outcome. Check the distribution of differences, not only raw values.",
    limits_ny="Kusintha kwakukulu kwa avareji kukhoza kubisa kusiyana pakati pa anthu: ena angapindule pamene ena akuipira. Kutayika kwa omwe atsatiridwa kungasokoneze zotsatira ngati kugwirizana ndi zotsatirapo. Yang'anani kufalikira kwa kusiyana, osati ma raw value okha.",
    explanation_ny="Pa paired test, munthu aliyense amakhala ngati control wake. Timayang'ana kusiyana pakati pa before ndi after, osati kuyerekeza magulu awiri osiyana.",
    analogy_en="It is like weighing the same patient before and after treatment. The comparison is within the same person, so their usual body size cancels out.",
    analogy_ny="Zili ngati kuyeza wodwala yemweyo asanalandire chithandizo ndi atalandira. Kuyerekezako kumachitika mkati mwa munthu yemweyo, kotero kukula kwake kwamba kumachotsedwa.",
    report_en="Report baseline and follow-up means, mean change with 95% CI, t, df and p. State that the paired analysis used within-person differences.",
    report_ny="Nenani avareji yoyambirira ndi yotsatira, kusintha kwa avareji ndi 95% CI, t, df ndi p. Fotokozani kuti kusanthula kunagwiritsa ntchito kusiyana kwa mkati mwa munthu.",
    application_en="Assessing change in blood pressure before and after an intervention in the same participants.",
    application_ny="Kuwona kusintha kwa kuthamanga kwa magazi musanayambe ndi mutalandira chithandizo mwa omwewo.",
)

E(
    category="groups",
    term="Mann-Whitney U test",
    term_ny="Mann-Whitney U test",
    use_en="Use to compare two independent groups when the outcome is ordinal or continuous but strongly skewed, and you are willing to interpret a stochastic ordering rather than a difference in means.",
    use_ny="Gwiritsani ntchito kuyerekeza magulu awiri odziyimira pawokha pamene zotsatira zili za masanjidwe kapena manambala opendekerera kwambiri, ndipo mukuvomereza kutanthauzira kuyitanidwa kwa ma rank osati kusiyana kwa avareji.",
    assumptions_en="Independent observations; similar distribution shapes if you want to interpret a location shift; ordinal or continuous outcome with meaningful ranks. Ties are handled by average ranks.",
    assumptions_ny="Ma observation odziyimira pawokha; mawonekedwe ofanana a kufalikira ngati mukutanthauzira kusuntha kwa malo; zotsatira zoyenera kupanga ma rank. Ma value ofanana amapatsidwa average rank.",
    code='''import numpy as np
import scipy.stats

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112209)
group1 = rng.lognormal(2.2, 0.8, 40)
group2 = rng.lognormal(2.6, 0.8, 42)

u = scipy.stats.mannwhitneyu(group1, group2)
rank_biserial = 2*u.statistic/(len(group1)*len(group2)) - 1
print("medians =", round(float(np.median(group1)), 2), "and",
      round(float(np.median(group2)), 2))
print("U =", round(float(u.statistic), 1), "p =", round(float(u.pvalue), 4))
print("rank-biserial effect =", round(float(rank_biserial), 3))''',
    interpretation_en="The test asks whether a randomly chosen value from one group tends to exceed a randomly chosen value from the other. The rank-biserial effect describes that tendency. It is not automatically a comparison of medians unless distribution shapes are similar.",
    interpretation_ny="Mayesowo amafunsa kuti mtengo wochokera ku gulu limodzi umakonda kuposa mtengo wochokera ku gulu lina. Rank-biserial effect ikufotokoza kukonda kumeneko. Sichiyerekezo cha medians pokhapokha mawonekedwe a kufalikira atafanana.",
    limits_en="Different shapes can produce a significant result even when medians are equal. It does not adjust for covariates. The test is less efficient than a t-test when t-test assumptions genuinely hold.",
    limits_ny="Mawonekedwe osiyana angapangitse zotsatira kukhala zofunika ngakhale medians zili zofanana. Sichotsa zinthu zosokoneza. Ngati mfundo za t-test zikwaniritsidwa, t-test imakhala yamphamvu kwambiri.",
    explanation_ny="M'malo moyerekeza avareji, Mann-Whitney imasintha ma value kukhala ma rank ndikufunsa kuti gulu liti lili ndi ma rank apamwamba kwambiri. Izi zithandiza ngati deta ili yopendekerera kapena yosanjidwa.",
    analogy_en="Instead of comparing total exam marks, line students up by rank and ask whether one class tends to stand higher in the queue.",
    analogy_ny="M'malo kuyerekeza chiwerengero chonse cha mayeso, ikani ophunzira mzere potengera masanjidwe ndikufunsa kuti gulu limodzi limakonda kukhala patsogolo kuposa linzake.",
    report_en="Report group medians and IQRs, U, p and a rank-based effect size. Describe the estimand as stochastic ordering, not simply 'median difference'.",
    report_ny="Nenani medians ndi IQR za magulu, U, p ndi kukula kwa zotsatira kochokera ku rank. Fotokozani zomwe mukuyerekeza monga kuyitanidwa kwa ma value, osati kungoti 'kusiyana kwa median'.",
    application_en="Comparing ordinal pain scores or skewed biomarker concentrations between two independent groups.",
    application_ny="Kuyerekeza masanjidwe a ululu kapena kuchuluka kwa biomarker kopendekerera pakati pa magulu awiri odziyimira pawokha.",
)

E(
    category="groups",
    term="Wilcoxon signed-rank test",
    term_ny="Wilcoxon signed-rank test",
    use_en="Use for paired or single-sample continuous data when the distribution of differences is not plausibly normal but the differences have a meaningful order and approximate symmetry.",
    use_ny="Gwiritsani ntchito pa deta yophatikizidwa kapena gulu limodzi pamene kusiyana sikuli pafupifupi normal koma kuli dongosolo lomveka komanso kufalikira kofanana mbali zonse.",
    assumptions_en="Pairs are independent; differences are continuous and approximately symmetric around their median; zero differences are handled. It tests a median or symmetry-related hypothesis, not necessarily a mean.",
    assumptions_ny="Awiriawiri odziyimira pawokha; kusiyana kuli kwa manambala ndipo kofalikira mofanana mbali zonse za median; kusiyana kwa zero kumayendetsedwa. Mayesowo amayesa median kapena lingaliro lokhudza symmetry, osati avareji kwenikweni.",
    code='''import numpy as np
import scipy.stats

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112210)
before = rng.lognormal(4.0, 0.5, 36)
after = before * rng.lognormal(-0.18, 0.35, 36)
diff = after - before

res = scipy.stats.wilcoxon(before, after)
print("median change =", round(float(np.median(diff)), 3))
print("W =", round(float(res.statistic), 1), "p =", round(float(res.pvalue), 4))
print("nonzero differences =", int(np.sum(diff != 0)))''',
    interpretation_en="The test ranks the absolute differences and keeps their signs. A small p-value means positive and negative ranks are not balanced as the null would predict. The median change describes the typical direction and size.",
    interpretation_ny="Mayesowo amasankha kukula kwa kusiyana potengera ma rank ndikusunga zizindikiro za + kapena -. p ikachepa, ma rank abwino ndi oyipa sanagawidwe monga momwe null ikunenera. Kusintha kwa median kukufotokoza njira ndi kukula kwamba.",
    limits_en="Strong asymmetry invalidates the signed-rank interpretation. Many zero differences reduce information. It does not model covariates or missing paired observations; complete pairs are required.",
    limits_ny="Kusafanana kwa mbali kumawononga tanthauzo la signed-rank. Kusiyana kochuluka kwa zero kumachepetsa chidziwitso. Sichitsanzo zinthu zosokoneza kapena kusowa kwa mbali imodzi ya awiriwiri; pamafunika awiriawiri athunthu.",
    explanation_ny="Monga paired t-test, imayang'ana kusiyana kwa munthu aliyense. Koma m'malo kugwiritsa ntchito avareji ya kusiyana, imagwiritsa ntchito ma rank ndi zizindikiro, kotero imalolera deta yosakhala normal.",
    analogy_en="It is like ranking who improved most, then noting whether each ranked change was an improvement or a worsening.",
    analogy_ny="Zili ngati kusanja omwe apindula kwambiri, kenako kulemba kuti kusinthako kunali kupindula kapena kuipa.",
    report_en="Report the median paired change, W, p, sample size and the symmetry assumption. State that complete pairs were analysed.",
    report_ny="Nenani kusintha kwa median kwa awiriawiri, W, p, kuchuluka kwa deta ndi mfundo ya symmetry. Fotokozani kuti awiriawiri athunthu ndiwo adasanthulidwa.",
    application_en="Analysing before-after symptom scores when the differences are skewed.",
    application_ny="Kusanthula masanjidwe a zizindikiro musanayambe ndi mutalandira chithandizo pamene kusiyana kuli kopendekerera.",
)

E(
    category="groups",
    term="One-way ANOVA with Tukey follow-up",
    term_ny="One-way ANOVA ndi Tukey yotsatira",
    use_en="Use when comparing means across three or more independent groups and you want an overall test followed by pairwise comparisons that control the family-wise error rate.",
    use_ny="Gwiritsani ntchito poyerekeza avareji a magulu atatu kapena kuposerapo odziyimira pawokha ndipo mukufuna mayeso onse pamodzi ndi kuyerekeza awiri awiri kolamulidwa.",
    assumptions_en="Independent observations; approximately normal residuals within groups; equal variances for classical ANOVA; Tukey assumes the same model and independent group means.",
    assumptions_ny="Ma observation odziyimira pawokha; ma residual pafupifupi normal mkati mwa magulu; variances zofanana pa ANOVA yakale; Tukey imaganizira model yomweyo ndi avareji odziyimira pawokha.",
    code='''import numpy as np
import scipy.stats

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112211)
group1 = rng.normal(3100, 250, 45)
group2 = rng.normal(3250, 250, 45)
group3 = rng.normal(3400, 250, 45)

result = scipy.stats.f_oneway(group1, group2, group3)
print("group means =",
      [round(float(np.mean(g)), 1) for g in (group1, group2, group3)])
print("F =", round(float(result.statistic), 3),
      "p =", format(float(result.pvalue), ".3g"))''',
    interpretation_en="The ANOVA row tests the null that all group means are equal. If it is significant, Tukey intervals identify which pairs differ while controlling the family-wise error rate. Read the direction and magnitude from the group means and intervals, not from the p-value alone.",
    interpretation_ny="Mzere wa ANOVA umayesa lingaliro loti avareji zonse za magulu zili zofanana. Ngati zili zofunika, Tukey imazindikira magulu awiri omwe amasiyana pomwe imalamulira mwayi wa zolakwika zonse. Werengani komwe kusiyana kulili kuchokera ku avareji ndi ma interval, osati p yokha.",
    limits_en="ANOVA compares means and can miss distributional differences. Unbalanced groups, unequal variances or outliers require care; Welch ANOVA or robust methods may be better. Post-hoc tests should follow a meaningful overall question.",
    limits_ny="ANOVA imayerekeza avareji ndipo ikhoza kuphonya kusiyana kwa mawonekedwe a kufalikira. Magulu osalingana, variances osiyana kapena ma outlier zifunika kusamalidwa; Welch ANOVA kapena njira zolimba zikhale bwino. Mayeso otsatira ayenera kutsatira funso lomveka la kafukufuku.",
    explanation_ny="ANOVA imayamba mufunsa ngati pali kusiyana kulikonse pakati pa magulu onse. Tukey imabwera pambuyo pake kudzatiuza kuti makamaka magulu ati awiri amasiyana.",
    analogy_en="ANOVA is the checkpoint asking whether any farm yield differs; Tukey then compares individual farms while keeping the total false-alarm rate controlled.",
    analogy_ny="ANOVA ndi malo ochezera ofunsa kuti zokolola za famu zilizonse zikusiyana; Tukey imayerekeza famu ndi famu pomwe imalamulira chiwopsezo chonse cha chenjezo labodza.",
    report_en="Report group means and SDs, ANOVA F with df and p, then Tukey-adjusted pairwise differences with simultaneous CIs.",
    report_ny="Nenani avareji ndi SD za magulu, F ya ANOVA ndi df ndi p, kenako kusiyana kwa Tukey pakati pa awiri awiri ndi ma interval ogwirizana ndi p zosinthidwa.",
    application_en="Comparing mean birth weight across three antenatal care programmes.",
    application_ny="Kuyerekeza avareji ya kulemera kwa makanda m'mapulogalamu atatu a chisamaliro cha amayi apakati.",
)

E(
    category="groups",
    term="Kruskal-Wallis test",
    term_ny="Kruskal-Wallis test",
    use_en="Use as a rank-based alternative to one-way ANOVA when comparing three or more independent groups with ordinal or skewed continuous outcomes.",
    use_ny="Gwiritsani ntchito m'malo mwa one-way ANOVA potengera ma rank poyerekeza magulu atatu kapena kuposerapo odziyimira pawokha okhala ndi zotsatira zosanjidwa kapena zopendekerera.",
    assumptions_en="Independent groups; observations can be ranked; similar shape if the result is described as a difference in location. It tests whether at least one group tends to have larger ranks.",
    assumptions_ny="Magulu odziyimira pawokha; ma observation akhoza kusanja; mawonekedwe ofanana ngati zotsatira zikufotokozedwa ngati kusintha kwa malo. Mayesowo amayesa kuti gulu lina lili ndi ma rank apamwamba.",
    code='''import numpy as np
from scipy import stats

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112212)
groups = [
    rng.lognormal(2.0, 0.7, 35),
    rng.lognormal(2.2, 0.7, 35),
    rng.lognormal(2.6, 0.7, 35),
]

h = stats.kruskal(*groups)
print("medians =", [round(float(np.median(g)), 2) for g in groups])
print("H =", round(float(h.statistic), 3), "df =", len(groups)-1,
      "p =", round(float(h.pvalue), 5))''',
    interpretation_en="A small p-value says the groups do not all have the same rank distribution. It does not say which groups differ, so follow with clearly planned pairwise comparisons and a multiplicity adjustment.",
    interpretation_ny="p ikachepa, magulu onse alibe kufalikira kwa ma rank kofanana. Sizitiuza kuti magulu ati amasiyana, choncho tsatirani ndi kuyerekeza kwapawiri kokonzedwa ndi kukonza kwa mayeso ambiri.",
    limits_en="Like Mann-Whitney, shape differences can mimic location differences. It does not provide an adjusted mean difference. Pairwise tests must respect the original group structure and correct for multiplicity.",
    limits_ny="Monga Mann-Whitney, kusiyana kwa mawonekedwe kukhoza kuwoneka ngati kusiyana kwa malo. Sipereka kusiyana kwa avareji koyendetsedwa. Mayeso a pawiri ayenera kulemekeza kapangidwe ka magulu ndi kukonza kuchuluka kwa mayeso.",
    explanation_ny="Kruskal-Wallis ndiye mtundu wa ANOVA wogwiritsa ntchito ma rank. Imayang'ana kuti magulu atatu kapena kuposerapo ali ndi ma rank ofanana kapena ayi.",
    analogy_en="It is like ranking all horses from several stables and asking whether the stables are mixed throughout the ranking or clustered at different ends.",
    analogy_ny="Zili ngati kusanja mahatchi onse ochokera m'magulu angapo ndikufunsa kuti maguluwo asanganikirana muzotsatira kapena amaonekera mbali zosiyanasiyana za mzere.",
    report_en="Report group medians and IQRs, H, df, p and the planned post-hoc method. Avoid calling it a test of means.",
    report_ny="Nenani medians ndi IQR za magulu, H, df, p ndi njira yotsatira yokonzedwa. Pewani kuyitcha mayeso wa avareji.",
    application_en="Comparing skewed parasite counts across three treatment arms.",
    application_ny="Kuyerekeza kuchuluka kwa tizirombo topendekerera m'magulu atatu a chithandizo.",
)

E(
    category="groups",
    term="Repeated-measures ANOVA",
    term_ny="ANOVA ya miyeso yobwerezabwereza",
    use_en="Use when the same participants are measured under three or more conditions or time points and you want to test whether the within-person means differ.",
    use_ny="Gwiritsani ntchito pamene omwewo ayezedwa pazochitika kapena nthawi zitatu kapena kuposerapo ndipo mukufuna kuyesa kuti avareji za mkati mwa munthu zimasiyana.",
    assumptions_en="Correct pairing by participant; approximately normal residuals; sphericity for the univariate F-test. If sphericity is doubtful, use a corrected test or a mixed model.",
    assumptions_ny="Kuphatikizidwa kolondola kwa munthu aliyense; ma residual pafupifupi normal; sphericity pa F-test yakale. Ngati sphericity yatsutsika, gwiritsani ntchito mayeso wokonzedwa kapena mixed model.",
    code='''import numpy as np
import pandas as pd
from statsmodels.stats.anova import AnovaRM

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112213)
rows = []
for pid in range(1, 31):
    base = rng.normal(12, 1.8)
    for visit, shift in [("baseline", 0.0), ("week4", 0.35), ("week8", 0.8)]:
        rows.append((pid, visit, base + shift + rng.normal(0, 0.9)))
df = pd.DataFrame(rows, columns=["id", "visit", "biomarker"])

fit = AnovaRM(data=df, depvar="biomarker", subject="id",
              within=["visit"]).fit()
table = fit.anova_table[["F Value", "Pr > F"]].round(4)
print(table.to_string())
print("n participants =", df["id"].nunique())''',
    interpretation_en="The F test asks whether the mean biomarker differs across visits after accounting for the fact that the same participants contributed each row. A small p-value indicates change over time; plot the visit means to see the pattern.",
    interpretation_ny="F imayesa kuti avareji ya biomarker imasiyana pa nthawi poganizira kuti munthu yemweyo anapereka deta nthawi zonse. p ikachepa, zikusonyeza kusintha pakapita nthawi; jambulani ma avareji a nthawi kuti muone mawonekedwe.",
    limits_en="Repeated-measures ANOVA is less flexible than a mixed model for missing visits, unequal spacing or complex covariance. Sphericity violations inflate the F test unless corrected. It does not by itself identify which visits differ.",
    limits_ny="ANOVA yobwerezabwereza si yosinthika ngati mixed model ngati pali nthawi yosowa, mtunda wosiyana kapena mgwirizano wovuta. Kuswa sphericity kumakulitsa F ngati sikukonzedwa. Sizizindikiritsa nthawi zomwe zimasiyana zokha.",
    explanation_ny="Munthu aliyense amabwerezedwa mu nthawi zonse, kotero timagwiritsa ntchito kusiyana kwa mkati mwa munthuyo. Izi zimachepetsa phokoso chifukwa munthu aliyense amakhala control wake.",
    analogy_en="It is like tracking the same plant's height each week. Comparing the same plant with itself removes much of the variation between different plants.",
    analogy_ny="Zili ngati kuyeza kutalika kwa chomera chomwecho sabata iliyonse. Kuyerekeza chomeracho ndi chokha kumachepetsa kusiyana komwe kulipo pakati pa zomera zosiyanasiyana.",
    report_en="Report the within-subject factor, F with corrected df when used, p and visit means. State the handling of sphericity and missing visits.",
    report_ny="Nenani chinthu chobwerezedwa mkati mwa munthu, F ndi df yokonzedwa ngati yagwiritsidwa ntchito, p ndi ma avareji a nthawi. Fotokozani kasamalidwe ka sphericity ndi ma visit osowa.",
    application_en="Testing whether a biomarker changes across baseline, week 4 and week 8 in the same cohort.",
    application_ny="Kuyesa kuti biomarker imasintha pakati pa poyambira, sabata 4 ndi sabata 8 mwa gulu lomwelo.",
)

E(
    category="categories",
    term="2x2 table, risk ratio and odds ratio",
    term_ny="Table 2x2, risk ratio ndi odds ratio",
    use_en="Use for two binary variables. Risk ratio compares event probabilities; odds ratio compares event odds and is the effect measure produced by logistic regression.",
    use_ny="Gwiritsani ntchito pa zinthu ziwiri za binary. Risk ratio uyerekeza mwayi wa zochitika; odds ratio uyerekeza ma odds ndipo ndi muyezo womwe logistic regression imatulutsa.",
    assumptions_en="Counts come from a clearly defined population and time window. The table must be arranged consistently. Cohort data support a risk ratio; case-control data usually do not, but can support an odds ratio.",
    assumptions_ny="Zowerengazo zachokera ku gulu ndi nthawi yofotokozedwa bwino. Table iyenera kukonzedwa mofanana nthawi zonse. Deta ya cohort imathandizira risk ratio; deta ya case-control nthawi zambiri siyithandizira koma imathandizira odds ratio.",
    code='''import numpy as np
from statsmodels.stats.contingency_tables import Table2x2

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112214)
exposed_event = rng.binomial(1, 0.45, 100).sum()
unexposed_event = rng.binomial(1, 0.25, 100).sum()
table = np.array([[exposed_event, 100-exposed_event],
                  [unexposed_event, 100-unexposed_event]])
res = Table2x2(table)

print("table [event, no event] rows: exposed, unexposed")
print(table)
rr_ci = res.riskratio_confint()
or_ci = res.oddsratio_confint()
print("risk ratio =", round(float(res.riskratio), 3),
      "95% CI", round(float(rr_ci[0]), 3), "to", round(float(rr_ci[1]), 3))
print("odds ratio =", round(float(res.oddsratio), 3),
      "95% CI", round(float(or_ci[0]), 3), "to", round(float(or_ci[1]), 3))''',
    interpretation_en="A risk ratio above 1 means a higher event probability in the exposed row. An odds ratio above 1 means higher odds. Odds ratios are farther from 1 than risk ratios when events are common, so they are easy to misread as risks.",
    interpretation_ny="Risk ratio woposa 1 ukutanthauza kuti mwayi wa chochitika ndi wokulirapo m'gulu lowonekera. Odds ratio woposa 1 ukutanthauza ma odds apamwamba. Ma odds ratio amakhala kutali ndi 1 kuposa risk ratio zochitika zikachuluka, choncho n'zosavuta kuzisokoneza ndi zoopsi zenizeni.",
    limits_en="These crude measures do not adjust for confounding. Odds ratio is not risk ratio, especially for common outcomes. Small cells produce wide intervals; case-control sampling cannot estimate a risk ratio without special methods.",
    limits_ny="Muyezo wosakonzedwawu suchotsa zinthu zosokoneza. Odds ratio si risk ratio, makamaka ngati zochitika zili zofala. Makutu ang'ono amapanga ma interval otakata; kusankha kwa case-control sikungayerekeze risk ratio popanda njira zapadera.",
    explanation_ny="Table 2x2 imasonyeza omwe adakumana ndi chinthu ndi omwe adamva zotsatira. Risk ratio imafanizira mwayi, pamene odds ratio imafanizira ma odds; zonse ziwiri zili ndi malo awo koma siziyenera kusokonezedwa.",
    analogy_en="Risk is like the fraction of a group that crosses a finish line; odds are the ratio of crossers to non-crossers. A risk ratio compares fractions, an odds ratio compares those ratios.",
    analogy_ny="Risk ili ngati gawo la gulu lomwe ladutsa mzere womaliza; odds ndi chiŵerengero cha odutsa ndi osadutsa. Risk ratio uyerekeza magawo, odds ratio uyerekeza chiŵerengerocho.",
    report_en="State the table orientation, event definition and time window. Report the chosen effect measure with 95% CI and note whether it is crude or adjusted.",
    report_ny="Fotokozani momwe table yakonzedwera, tanthauzo la chochitika ndi nthawi. Nenani muyezo wosankhidwa ndi 95% CI, ndi kuti ndi wosakonzedwa kapena wosinthidwa.",
    application_en="Summarising the association between an exposure and a binary outcome before fitting logistic regression.",
    application_ny="Kufotokoza ubale pakati pa chinthu chowonekera ndi zotsatira za binary musanayike logistic regression.",
)

E(
    category="categories",
    term="Odds ratio",
    term_ny="Odds ratio",
    use_en="Use an odds ratio to compare the odds of an event between two groups, especially for binary outcomes in case-control studies and logistic regression.",
    use_ny="Gwiritsani ntchito odds ratio poyerekeza ma odds a chochitika pakati pa magulu awiri, makamaka pa zotsatira za binary mu kafukufuku wa case-control ndi logistic regression.",
    assumptions_en="The 2x2 table has a consistent orientation and a defined event and time window. Observations are independent. For adjusted odds ratios, the logistic model must be correctly specified with no separation.",
    assumptions_ny="Table 2x2 ili ndi dongosolo lokhazikika, chochitika chomveka ndi nthawi yofotokozedwa. Ma observation ndi odziyimira pawokha. Pa odds ratio wosinthidwa, model ya logistic iyenera kukhala yolondola popanda kulekanitsa.",
    code='''import numpy as np
from statsmodels.stats.contingency_tables import Table2x2

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112241)
exposed_event = rng.binomial(1, 0.40, 90).sum()
unexposed_event = rng.binomial(1, 0.20, 90).sum()
table = np.array([[exposed_event, 90-exposed_event],
                  [unexposed_event, 90-unexposed_event]])
res = Table2x2(table)
ci = res.oddsratio_confint()

print("table [event, no event] rows: exposed, unexposed")
print(table)
print("odds ratio =", round(float(res.oddsratio), 3),
      "95% CI", round(float(ci[0]), 3), "to", round(float(ci[1]), 3))''',
    interpretation_en="Odds are event count divided by non-event count. The odds ratio divides the exposed odds by the unexposed odds. A value above 1 means higher odds in the exposed row, but it is not the same as a risk ratio when events are common.",
    interpretation_ny="Ma odds ndi kuchuluka kwa zochitika kogawidwa ndi kosachitika. Odds ratio imagawa ma odds a gulu lowonekera ndi a gulu losawonekera. Mtengo woposa 1 ukutanthauza ma odds apamwamba, koma si wofanana ndi risk ratio zochitika zikachuluka.",
    limits_en="A crude odds ratio does not adjust for confounding. It can look farther from 1 than the corresponding risk ratio for common outcomes. Sparse cells give wide intervals and zero cells can make the estimate unstable.",
    limits_ny="Odds ratio yosakonzedwa suchotsa zinthu zosokoneza. Zochitika zikachuluka, imatha kuwoneka kutali ndi 1 kuposa risk ratio. Maselo ochepa amapanga ma interval otakata ndipo selo la zero lingapangitse kuyerekezako kusakhazikika.",
    explanation_ny="Odds ratio uyerekeza ma odds, osati mwayi weniweni. Ngati gulu limodzi lili ndi ma odds apamwamba kawiri, izi sizitanthauza kuti mwayi wochitika unawirikizeka, makamaka ngati chochitikacho chili chofala.",
    analogy_en="Risk is like the fraction of a class that passes; odds are the ratio of passers to non-passers. An odds ratio compares those pass-to-fail ratios, not the pass fractions themselves.",
    analogy_ny="Risk ili ngati gawo la kalasi lomwe ladutsa; ma odds ndi chiŵerengero cha odutsa ndi osadutsa. Odds ratio uyerekeza chiŵerengerocho, osati magawo a odutsa.",
    report_en="State the table orientation, event definition and time window. Report the odds ratio with 95% CI and say whether it is crude or model-adjusted.",
    report_ny="Fotokozani momwe table yakonzedwera, tanthauzo la chochitika ndi nthawi. Nenani odds ratio ndi 95% CI ndi kuti ndi wosakonzedwa kapena wosinthidwa ndi model.",
    application_en="Summarising an exposure-outcome association in a case-control study or reporting a logistic regression coefficient as an adjusted odds ratio.",
    application_ny="Kufotokoza ubale wa exposure ndi zotsatira mu kafukufuku wa case-control kapena kunena coefficient ya logistic regression ngati odds ratio wosinthidwa.",
)

E(
    category="categories",
    term="Chi-square test of independence and Cramer's V",
    term_ny="Chi-square ya ufulu ndi Cramer's V",
    use_en="Use to test whether two categorical variables are associated in a contingency table, and Cramer's V to describe the strength of that association.",
    use_ny="Gwiritsani ntchito kuyesa kuti zinthu ziwiri za makategori zili ndi ubale mu table, ndi Cramer's V kufotokoza mphamvu ya ubalewo.",
    assumptions_en="Independent observations; expected cell counts sufficiently large, commonly at least about 5 for most cells in a simple table. Categories should be mutually exclusive.",
    assumptions_ny="Ma observation odziyimira pawokha; kuchuluka koyembekezeka m'maselo kukhale kokwanira, nthawi zambiri pafupifupi 5 pa maselo ambiri. Makategori asagwirizane.",
    code='''import numpy as np
import pandas as pd
from scipy import stats

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112215)
n = 300
exposure = rng.choice(["none", "low", "high"], n, p=[0.45, 0.35, 0.20])
probs = {"none": [0.75, 0.25], "low": [0.65, 0.35], "high": [0.45, 0.55]}
outcome = np.array([rng.choice(["no", "yes"], p=probs[e]) for e in exposure])
tab = pd.crosstab(exposure, outcome)

chi2, p, dof, expected = stats.chi2_contingency(tab)
n_total = tab.to_numpy().sum()
v = np.sqrt(chi2 / (n_total * (min(tab.shape) - 1)))
print(tab.to_string())
print("minimum expected count =", round(float(expected.min()), 2))
print("chi2 =", round(float(chi2), 3), "df =", dof,
      "p =", round(float(p), 5))
print("Cramer V =", round(float(v), 3))''',
    interpretation_en="A small p-value says the pattern of outcomes differs across exposure categories. Cramer's V ranges from 0 to 1; it describes strength but not direction or causal meaning. Inspect row percentages to understand the pattern.",
    interpretation_ny="p ikachepa, mawonekedwe a zotsatira amasiyana m'magulu owonekera. Cramer's V ili pakati pa 0 ndi 1; imafotokoza mphamvu osati komwe ubale ukupita kapena tanthauzo la causality. Yang'anani ma percent a mzere kuti mumvetse mawonekedwe.",
    limits_en="A large table can produce a significant chi-square with a small V. Expected counts below about 5 make the asymptotic p unreliable; use Fisher or exact methods where appropriate. It does not adjust for other variables.",
    limits_ny="Table yayikulu ikhoza kutulutsa chi-square yofunika koma V yaying'ono. Kuchuluka koyembekezeka pansi pa 5 kumapangitsa p kusadalirika; gwiritsani ntchito Fisher kapena njira zenizeni ngati kuli koyenera. Sichotsa zinthu zina.",
    explanation_ny="Chi-square imafanizira zomwe tawona ndi zomwe tikadayembekezera ngati palibe ubale pakati pa makategori. Cramer's V imatiuza kuti ubalewo ndi wamphamvu bwanji.",
    analogy_en="It is like checking whether drink choices differ by age group more than random mixing would produce. Chi-square flags a pattern; V says how pronounced it is.",
    analogy_ny="Zili ngati kuyang'ana kuti zakumwa zosankhidwa zimasiyana m'magulu azaka kuposa momwe kusakaniza mwachisawawa kungapangire. Chi-square imazindikira mawonekedwe; V imatiuza kuti ndi yamphamvu bwanji.",
    report_en="Report the contingency table, chi-square with df and p, minimum expected count and Cramer's V. Describe the direction using percentages.",
    report_ny="Nenani table, chi-square ndi df ndi p, kuchuluka kochepa koyembekezeka ndi Cramer's V. Fotokozani komwe ubale ukupita pogwiritsa ntchito ma percent.",
    application_en="Testing whether malaria positivity category differs by specimen type.",
    application_ny="Kuyesa kuti gulu la malungo limasiyana ndi mtundu wa zitsanzo.",
)

E(
    category="categories",
    term="Fisher exact test",
    term_ny="Fisher exact test",
    use_en="Use for small 2x2 tables when expected cell counts are too low for the chi-square approximation and you need an exact p-value for independence.",
    use_ny="Gwiritsani ntchito pa table 2x2 yaying'ono pamene kuchuluka koyembekezeka kuli kochepa kwambiri kwa chi-square ndipo mukufuna p yeniyeni ya ufulu.",
    assumptions_en="Fixed margins are assumed under the exact conditional procedure; observations are independent; each participant contributes once to one cell.",
    assumptions_ny="Njira yeniyeni imaganizira kuti m'mphepete mwa table ndi zokhazikika; ma observation odziyimira pawokha; munthu aliyense amangopereka kaundu kamodzi mu selo limodzi.",
    code='''import numpy as np
from scipy import stats

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112216)
a = rng.binomial(1, 0.10, 18).sum()
b = 18 - a
c = rng.binomial(1, 0.35, 16).sum()
d = 16 - c
table = np.array([[a, b], [c, d]])

odds, p = stats.fisher_exact(table, alternative="two-sided")
print("table =", table.tolist())
print("odds ratio =", round(float(odds), 3))
print("Fisher exact two-sided p =", round(float(p), 4))''',
    interpretation_en="The p-value is calculated from all tables with the same margins, not from a large-sample approximation. It answers whether the observed arrangement is unusual under independence. Report the table because the odds ratio can be unstable with sparse cells.",
    interpretation_ny="p imawerengedwa kuchokera ku ma table onse omwe ali ndi m'mphepete lofanana, osati kuchokera ku kuyerekeza kwa deta yayikulu. Imayesa kuti kakonzedwe kowonedwa kali kodabwitsa ngati palibe ubale. Nenani table chifukwa odds ratio ikhoza kukhala yosakhazikika maselo akachepa.",
    limits_en="Exact does not mean automatically better for large tables. Conditional odds ratio may be infinite with zero cells. It does not provide an adjusted effect and can be conservative.",
    limits_ny="Kukhala 'exact' sikutanthauza kuti kuli bwino nthawi zonse pa table yayikulu. Conditional odds ratio ikhoza kukhala yopanda malire ngati selo lili zero. Sipereka zotsatira zosinthidwa ndipo ikhoza kukhala yodziletsa kwambiri.",
    explanation_ny="Ngati makutu ali ochepa, chi-square si yodalirika. Fisher imawerengera mwayi wa table yotere mwachindunji potengera makutu omwe alipo.",
    analogy_en="Instead of approximating with a bell curve, Fisher enumerates all possible arrangements of a small deck and counts how extreme yours is.",
    analogy_ny="M'malo kugwiritsa ntchito kuyerekeza kwa mawonekedwe a belu, Fisher imawerenga makonzedwe onse a makadi ochepa ndikuwerengera kuti anu ndi otani.",
    report_en="Report the raw 2x2 table, exact p-value and, if stable, the odds ratio with an exact or carefully computed interval.",
    report_ny="Nenani table 2x2 yoyambirira, p yeniyeni ndi, ngati yakhazikika, odds ratio ndi interval yowerengedwa mosamala.",
    application_en="Analysing a rare outcome in a small pilot study.",
    application_ny="Kusanthula zotsatira zosowa mu kafukufuku wawung'ono wa pilot.",
)

E(
    category="categories",
    term="McNemar test",
    term_ny="McNemar test",
    use_en="Use for paired binary data, such as the same participants tested before and after an intervention, when the question is whether the proportion of positive results changes.",
    use_ny="Gwiritsani ntchito pa deta ya binary yophatikizidwa, monga omwewo ayezedwa asanayambe ndi atalandira chithandizo, pamene funso ndi kuti gawo la zotsatira zabwino limasintha.",
    assumptions_en="Pairs are independent of each other; each pair has two binary measurements; discordant pairs provide the information. Exact McNemar is preferred when discordant counts are small.",
    assumptions_ny="Awiriawiri odziyimira pawokha; awiriwiri aliyense ali ndi miyeso iwiri ya binary; ma pair osagwirizana ndiwo amapereka chidziwitso. McNemar yeniyeni ndi yabwino pamene kusiyana kuli kochepa.",
    code='''import numpy as np
import pandas as pd
from statsmodels.stats.contingency_tables import mcnemar

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112217)
before = rng.binomial(1, 0.35, 120)
after = before.copy()
flips = rng.choice(120, size=28, replace=False)
after[flips] = 1 - after[flips]
tab = pd.crosstab(before, after)

res = mcnemar(tab.to_numpy(), exact=True)
print(tab.to_string())
print("discordant counts =", int(tab.iloc[0,1]), "and", int(tab.iloc[1,0]))
print("McNemar exact p =", round(float(res.pvalue), 4))''',
    interpretation_en="Concordant pairs cancel out because they do not indicate change. The test compares the two discordant cells. A small p-value means changes in one direction are more frequent than changes in the other.",
    interpretation_ny="Ma pair ogwirizana amachotsedwa chifukwa sawonetsa kusintha. Mayesowo uyerekeza makutu awiri osagwirizana. p ikachepa, kusintha kwa mbali imodzi kumachitika pafupipafupi kuposa mbali ina.",
    limits_en="It tests marginal change, not whether individual predictions are accurate. Missing one member of a pair discards that pair. It does not adjust for covariates and is not an independence test.",
    limits_ny="Umayesa kusintha kwa m'mphepete, osati kuti zolosera za munthu aliyense ndi zolondola. Ngati mbali imodzi ya awiriwiri yasowa, awiriwiriwo amatayika. Sichotsa zinthu zosokoneza ndipo si mayeso wa ufulu.",
    explanation_ny="McNemar imayang'ana anthu omwe zotsatira zawo zinasintha. Omwe sanasinthe sawonjezera chidziwitso pa funso lakuti kuchuluka kwa positive kwasintha kapena ayi.",
    analogy_en="It is like counting only shoppers who switched brands, not those who kept the same brand, to decide whether a campaign shifted preference.",
    analogy_ny="Zili ngati kuwerengera okha ogula omwe adasintha mtundu wa katundu, osati omwe adakhalabe ndi mtundu womwewo, kuti muone ngati kampeni idasintha zokonda.",
    report_en="Report the paired 2x2 table, discordant counts, exact or asymptotic p and the direction of change.",
    report_ny="Nenani table 2x2 yophatikizidwa, kuchuluka kosagwirizana, p yeniyeni kapena yoyerekeza ndi komwe kusintha kunapita.",
    application_en="Comparing test positivity before and after a training programme in the same laboratories.",
    application_ny="Kuyerekeza kuchuluka kwa zotsatira zabwino musanayambe ndi mutalandira maphunziro m'ma laboratory omwewo.",
)

E(
    category="categories",
    term="Cohen's kappa for agreement",
    term_ny="Cohen's kappa wa kuvomerezana",
    use_en="Use when two raters classify the same subjects into categories and you want agreement beyond what chance alone would produce.",
    use_ny="Gwiritsani ntchito pamene owerenga awiri agawira anthu omwewo m'makategori ndipo mukufuna kuvomerezana koposa mwangozi.",
    assumptions_en="The same subjects are rated by both raters; categories are mutually exclusive; raters are independent of each other. Kappa is appropriate for nominal categories with the same scale.",
    assumptions_ny="Anthu omwewo awerengedwa ndi owerenga onse awiri; makategori asagwirizane; owerenga asakhudzane. Kappa ndi yoyenera makategori a nominal omwe ali ndi muyezo womwewo.",
    code='''import numpy as np
from scipy import stats
from statsmodels.stats.inter_rater import cohens_kappa

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112218)
true_class = rng.integers(0, 2, 160)
rater_a = true_class.copy()
rater_b = true_class.copy()
disagree = rng.choice(160, size=34, replace=False)
rater_b[disagree] = 1 - rater_b[disagree]
table = np.zeros((2, 2), dtype=int)
for a, b in zip(rater_a, rater_b):
    table[a, b] += 1

res = cohens_kappa(table)
print("confusion table rows=rater A, cols=rater B")
print(table)
print("observed agreement =", round(float(np.trace(table)/table.sum()), 3))
print("kappa =", round(float(res.kappa), 3))
print("95% CI =", round(float(res.kappa_low), 3), "to",
      round(float(res.kappa_upp), 3))''',
    interpretation_en="Observed agreement can be high simply because one category is common. Kappa subtracts chance agreement. Values near 1 indicate strong agreement; values near 0 indicate agreement no better than chance; negatives indicate systematic disagreement.",
    interpretation_ny="Kuvomerezana kowonedwa kukhoza kukhala kwakukulu chifukwa makategori imodzi ndi yofala. Kappa imachotsa kuvomerezana kwamwayi. Zili pafupi ndi 1 zikusonyeza kuvomerezana kwakukulu; pafupi ndi 0 kuli ngati mwangozi; zoipa zikusonyeza kusagwirizana kwadongosolo.",
    limits_en="Kappa depends on category prevalence and can be surprisingly low when a category is rare. It assumes the same categories and no systematic rater bias in its simplest form. Use weighted kappa for ordered categories.",
    limits_ny="Kappa imadalira kuchuluka kwa makategori ndipo ikhoza kukhala yotsika modabwitsa makategori imodzi ikachepa. Imaganizira makategori ofanana komanso kusakondera kwa owerenga mu mawonekedwe ake osavuta. Gwiritsani ntchito weighted kappa pa makategori oyitanidwa.",
    explanation_ny="Kuvomerezana kokha sikukwanira chifukwa owerenga angavomereze mwangozi. Kappa imafunsa kuti kuvomerezana kwathu kuposa kwa mwangozi ndi kokwanira bwanji.",
    analogy_en="Two weather forecasters may both often say 'no rain'. Raw agreement looks good, but kappa asks whether they agree beyond what that common forecast would predict.",
    analogy_ny="Anyosi awiri angamalengeze kuti 'mvula sigwa' pafupipafupi. Kuvomerezana kowoneka kumakhala kwakukulu, koma kappa imafunsa kuti kuvomerezana kwawo kuposa kwa mwangozi ndi kokwanira.",
    report_en="Report the confusion table, observed agreement, kappa, CI and the rater definitions. State that chance agreement was accounted for.",
    report_ny="Nenani table ya kuvomerezana, kuvomerezana kowonedwa, kappa, CI ndi matanthauzo a owerenga. Fotokozani kuti kuvomerezana kwamwayi kunachotsedwa.",
    application_en="Measuring agreement between two readers classifying malaria slides.",
    application_ny="Kuyeza kuvomerezana pakati pa owerenga awiri pogawira ma slide a malungo.",
)

E(
    category="categories",
    term="Chi-square goodness-of-fit",
    term_ny="Chi-square ya kukwanira kwa kugawa",
    use_en="Use when you have counts in one categorical variable and want to compare the observed distribution with a prespecified expected distribution.",
    use_ny="Gwiritsani ntchito pamene muli ndi kuchuluka kwa makategori imodzi ndipo mukufuna kuyerekeza kagawidwe kowonedwa ndi kagawidwe kokonzedweratu.",
    assumptions_en="Independent observations; mutually exclusive categories; expected counts reasonably large. The expected probabilities must be specified before looking at the data, not chosen to fit it.",
    assumptions_ny="Ma observation odziyimira pawokha; makategori asagwirizane; kuchuluka koyembekezeka kukhale kokwanira. Mwayi woyembekezeka uyenera kufotokozedwa musanayang'ane deta, osati kusankhidwa kuti igwirizane nayo.",
    code='''import numpy as np
from scipy import stats

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112219)
observed = rng.multinomial(240, [0.52, 0.30, 0.18])
expected_probs = np.array([0.50, 0.30, 0.20])
expected = observed.sum() * expected_probs

chi2, p = stats.chisquare(f_obs=observed, f_exp=expected)
print("observed =", observed.tolist())
print("expected =", np.round(expected, 1).tolist())
print("chi2 =", round(float(chi2), 3), "df =", len(observed)-1,
      "p =", round(float(p), 4))''',
    interpretation_en="The test measures how far the observed counts are from the expected counts relative to sampling variation. A large p-value is consistent with the specified distribution; it does not prove the distribution is exactly correct.",
    interpretation_ny="Mayesowo amayeza kuti kuchuluka kowonedwa kuli kutali bwanji ndi koyembekezeka poyerekeza ndi kusiyana kwachibadwa kwa sample. p yayikulu ikugwirizana ndi kagawidwe kofotokozedwa; sikutsimikizira kuti kagawidweko ndi kolondola ndendende.",
    limits_en="With very large samples, trivial deviations become significant. With small expected counts, the approximation is poor. The choice of expected distribution must come from theory or a prespecified standard.",
    limits_ny="Ndi deta yayikulu kwambiri, kusiyana kochepa kumakhala kofunika. Ndi kuchuluka koyembekezeka kochepa, kuyerekezako kumakhala koyipa. Kagawidwe koyembekezeka kayenera kuchokera ku chiphunzitso kapena muyezo wokonzedweratu.",
    explanation_ny="Apa tili ndi gulu limodzi lokha la makategori. Timafanizira kuchuluka komwe tawona ndi kuchuluka komwe tikadayembekezera ngati muyezo wina uli woona.",
    analogy_en="It is like checking whether the colours of candies in a bag match the manufacturer's stated mix, rather than comparing two different bags.",
    analogy_ny="Zili ngati kuyang'ana kuti mitundu ya maswiti m'chikwama ikugwirizana ndi kusakaniza kwalengezedwa ndi wopanga, osati kuyerekeza zikwama ziwiri.",
    report_en="Report observed and expected counts, chi-square, df and p, and explain the source of the expected distribution.",
    report_ny="Nenani kuchuluka kowonedwa ndi koyembekezeka, chi-square, df ndi p, ndi kufotokoza komwe kagawidwe koyembekezeka kunachokera.",
    application_en="Checking whether specimen types in a laboratory log follow an expected quarterly mix.",
    application_ny="Kuyang'ana kuti mitundu ya zitsanzo mu buku la laboratory ikugwirizana ndi kusakaniza koyembekezeka kwa kotala.",
)

E(
    category="association",
    term="Pearson correlation",
    term_ny="Pearson correlation",
    use_en="Use to summarise the strength and direction of a linear relationship between two continuous variables. Always inspect a scatterplot first.",
    use_ny="Gwiritsani ntchito kufotokoza mphamvu ndi njira ya ubale wa mzere pakati pa zinthu ziwiri za manambala. Yang'anani scatterplot kaye.",
    assumptions_en="Pairs are independent; relationship is approximately linear; variables are continuous; no extreme influential outliers. Normality is mainly needed for the p-value and interval in small samples.",
    assumptions_ny="Awiriawiri odziyimira pawokha; ubale uli pafupifupi wa mzere; zinthu zili za manambala; palibe ma outlier owopsa. Normality imafunika makamaka p ndi interval ngati deta ndi yochepa.",
    code='''import numpy as np
import scipy.stats

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112220)
gestational_age = rng.normal(32, 3, 80)  # simulated weeks
birth_weight = 600 + 95*gestational_age + rng.normal(0, 250, 80)  # simulated grams

res = scipy.stats.pearsonr(gestational_age, birth_weight)
ci = res.confidence_interval(0.95)
print("Pearson r =", round(float(res.statistic), 3))
print("95% CI =", round(float(ci.low), 3), "to", round(float(ci.high), 3))
print("p =", round(float(res.pvalue), 6))
print("r squared =", round(float(res.statistic**2), 3))''',
    interpretation_en="r ranges from -1 to 1 and describes linear association only. r squared is the proportion of variance shared in a simple linear model, not proof of causation. The interval shows uncertainty in r.",
    interpretation_ny="r ili pakati pa -1 ndi 1 ndipo imafotokoza ubale wa mzere okha. r squared ndi gawo la kusiyana komwe kugawidwa mu model yosavuta, osati umboni wa causality. Interval ikuwonetsa kusatsimikizika kwa r.",
    limits_en="A strong nonlinear relationship can have r near zero. A single influential point can create or destroy correlation. Correlation does not adjust for confounders and says nothing about agreement between measurement methods.",
    limits_ny="Ubale wamphamvu koma wosakhala wa mzere ukhoza kukhala ndi r pafupi ndi zero. Point imodzi yamphamvu ikhoza kupanga kapena kuwononga correlation. Correlation suchotsa zinthu zosokoneza ndipo sikuonetsa kuvomerezana pakati pa njira zoyezera.",
    explanation_ny="Pearson imayesa kuti zinthu ziwiri zikuyenda limodzi m'njira yowongoka. Ngati imodzi ikwera pamene ina ikukwera, r ndi yabwino; ngati imodzi ikutsika pamene ina ikukwera, r ndi yoipa.",
    analogy_en="It is like checking whether taller students tend to have larger shoe sizes. The pattern can be strong, but height does not 'cause' shoe size in a simple experimental sense.",
    analogy_ny="Zili ngati kuyang'ana kuti ophunzira azitali amakonda kukhala ndi nsapato zazikulu. Ubale ukhoza kukhala wamphamvu, koma kutalika sikumayambitsa kukula kwa nsapato m'njira yosavuta.",
    report_en="Report r, 95% CI, p, n and a scatterplot description. Say 'linear correlation', not 'caused by'.",
    report_ny="Nenani r, 95% CI, p, n ndi kufotokoza kwa scatterplot. Tchulani 'linear correlation', osati kuti 'chinachititsa'.",
    application_en="Exploring the linear association between maternal age and a continuous biomarker before regression.",
    application_ny="Kufufuza ubale wa mzere pakati pa zaka za amayi ndi biomarker ya manambala musanayike regression.",
)

E(
    category="association",
    term="Spearman rank correlation",
    term_ny="Spearman rank correlation",
    use_en="Use for a monotonic relationship when variables are ordinal, skewed, or the relationship is not linear but tends to increase or decrease consistently.",
    use_ny="Gwiritsani ntchito pa ubale wokwera kapena kutsika nthawi zonse pamene zinthu zili zosanjidwa, zopendekerera, kapena ubale si wa mzere koma umakonda kukwera kapena kutsika.",
    assumptions_en="Pairs are independent; at least ordinal measurement; monotonic association; ties are acceptable but reduce precision. It tests association of ranks, not raw means.",
    assumptions_ny="Awiriawiri odziyimira pawokha; muyezo wosanjidwa osachepera; ubale wokwera kapena kutsika; ma value ofanana amavomerezeka koma amachepetsa kulondola. Imayesa ubale wa ma rank, osati avareji yaiwisi.",
    code='''import numpy as np
import scipy.stats

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112221)
variable1 = rng.integers(1, 6, 90)
variable2 = 2.2*variable1 + rng.lognormal(0, 0.5, 90)

res = scipy.stats.spearmanr(variable1, variable2)
rho = float(res.statistic)
z = np.arctanh(rho)
se = 1/np.sqrt(len(variable1)-3)
lo, hi = np.tanh(z - 1.96*se), np.tanh(z + 1.96*se)
print("Spearman rho =", round(rho, 3))
print("approx 95% CI =", round(float(lo), 3), "to", round(float(hi), 3))
print("p =", round(float(res.pvalue), 6))''',
    interpretation_en="Spearman's rho near 1 means higher ranks in one variable tend to accompany higher ranks in the other. It is robust to monotone transformations because it uses ranks, but it ignores the size of gaps between values.",
    interpretation_ny="rho ya Spearman pafupi ndi 1 imatanthauza kuti ma rank apamwamba pa chinthu chimodzi amatsagana ndi ma rank apamwamba pa china. Imalolera kusintha kwa manambala kosawononga dongosolo chifukwa imagwiritsa ntchito ma rank, koma sinyalanyaza kukula kwa mipata pakati pa ma value.",
    limits_en="The Fisher-style interval here is approximate and is least reliable with many ties or small samples. A monotonic but non-linear pattern may still be biologically weak. It does not imply calibration or agreement.",
    limits_ny="Interval yofanana ndi Fisher apa ndi yongoyerekeza ndipo si yodalirika ngati ma value ofanana ndi ambiri kapena deta ili yochepa. Ubale wokwera koma wosakhala wa mzere ukhoza kukhala wofooka mwachilengedwe. Sizitanthauza kuti miyeso ikugwirizana bwino.",
    explanation_ny="Spearman imasintha ma value kukhala ma rank. Choncho ngati munthu wachiwiri ndi wapamwamba kuposa woyamba pa zonse, ubale wake uli pafupi ndi 1 ngakhale kusiyana kwenikweni kuli kosiyana.",
    analogy_en="It is like comparing race finishing positions rather than exact times. The order matters more than how many seconds separated runners.",
    analogy_ny="Zili ngati kuyerekeza malo omwe othamanga adamaliza osati nthawi yeniyeni. Dongosolo ndilo lofunika kwambiri osati masekondi pakati pawo.",
    report_en="Report rho, approximate CI, p, n and the number or proportion of ties. State that ranks were analysed.",
    report_ny="Nenani rho, CI yoyerekeza, p, n ndi kuchuluka kwa ma value ofanana. Fotokozani kuti ma rank ndiwo adasanthulidwa.",
    application_en="Associating an ordinal adherence score with a skewed biomarker.",
    application_ny="Kugwirizanitsa masanjidwe a kumvera malangizo ndi biomarker wopendekerera.",
)

E(
    category="association",
    term="Kendall tau-b",
    term_ny="Kendall tau-b",
    use_en="Use as another rank-based association measure when you want an interpretable concordance probability and have many tied ranks or a modest sample.",
    use_ny="Gwiritsani ntchito ngati muyezo wina wa ma rank pamene mukufuna kumvetsetsa mwayi wogwirizana wa ma pairs ndipo muli ndi ma rank ofanana ambiri kapena deta yochepa.",
    assumptions_en="Pairs are independent; variables are at least ordinal; tau-b adjusts for ties. It measures concordance of pairs rather than distance from a fitted line.",
    assumptions_ny="Awiriawiri odziyimira pawokha; zinthu zili zosanjidwa osachepera; tau-b imasintha ma value ofanana. Imayeza kugwirizana kwa awiriawiri osati mtunda kuchokera ku mzere woyenerera.",
    code='''import numpy as np
from scipy import stats

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112222)
lab_score = rng.integers(0, 4, 70)
clinical_score = np.clip(lab_score + rng.integers(-1, 2, 70), 0, 4)

res = stats.kendalltau(lab_score, clinical_score)
tau = float(res.statistic)
print("Kendall tau-b =", round(tau, 3))
print("p =", round(float(res.pvalue), 5))
print("concordance interpretation: tau = P(concordant) - P(discordant)")''',
    interpretation_en="Positive tau means more pairs are concordant than discordant. It can be read as the difference between the probabilities that a randomly chosen pair is concordant or discordant. It is usually smaller in magnitude than Spearman's rho.",
    interpretation_ny="tau yabwino imatanthauza kuti pali awiriawiri ogwirizana kwambiri kuposa osagwirizana. Itha kuwerengedwa ngati kusiyana pakati pa mwayi woti awiriwiri asankhidwe mwachisawawa agwirizane kapena ayi. Nthawi zambiri imakhala yaying'ono kuposa rho ya Spearman.",
    limits_en="It is not a slope and has no simple units. Different tie structures affect comparison across studies. A significant tau can be small and of little practical relevance.",
    limits_ny="Si slope ndipo ilibe mayunitsi osavuta. Kusiyana kwa ma value ofanana kumakhudza kuyerekeza pakati pa maphunziro. tau yofunika ikhoza kukhala yaying'ono komanso yopanda phindu yaikulu.",
    explanation_ny="Kendall amayang'ana awiriawiri a anthu. Ngati munthu woyamba ali pamwamba pa winayo pa zinthu zonse ziwiri, awiriwiriwo amagwirizana; ngati dongosolo lisinthika, amasagwirizana.",
    analogy_en="It is like asking, for every pair of runners, whether the two judges ranked them in the same order.",
    analogy_ny="Zili ngati kufunsa, pa othamanga awiri alionse, kuti owerenga awiri adawasanja m'dongosolo lomwelo kapena ayi.",
    report_en="Report tau-b, p, sample size and how ties were handled. Avoid comparing tau directly with Pearson r.",
    report_ny="Nenani tau-b, p, kuchuluka kwa deta ndi momwe ma value ofanana adayendetsedwera. Pewani kuyerekeza tau mwachindunji ndi Pearson r.",
    application_en="Comparing two ordinal scoring systems with many repeated scores.",
    application_ny="Kuyerekeza machitidwe awiri a masanjidwe okhala ndi zotsatira zobwerezabwereza.",
)

E(
    category="association",
    term="Partial correlation",
    term_ny="Partial correlation",
    use_en="Use when you want the association between two continuous variables after removing the linear influence of one or more measured covariates.",
    use_ny="Gwiritsani ntchito pamene mukufuna ubale pakati pa zinthu ziwiri za manambala mutachotsa mphamvu ya mzere ya zinthu zina zoyezedwa.",
    assumptions_en="Linear relationships among variables; independent observations; no unmeasured confounder of the paths of interest; covariates measured before or independently of the outcome where possible.",
    assumptions_ny="Ubale wa mzere pakati pa zinthu; ma observation odziyimira pawokha; palibe chinthu chosayezedwa chosokoneza njira zomwe zikufunsidwa; zinthu zosokoneza zoyezedwa kale kapena mosadalira zotsatira ngati kuli kotheka.",
    code='''import numpy as np
import pandas as pd

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112223)
n = 120
age = rng.normal(45, 10, n)
biomarker = 0.5*age + rng.normal(0, 3, n)
outcome = 0.4*biomarker + 0.6*age + rng.normal(0, 2, n)
df = pd.DataFrame({"age": age, "biomarker": biomarker, "outcome": outcome})

def residuals(target, controls):
    X = np.column_stack([np.ones(len(target))] + [df[c].to_numpy() for c in controls])
    beta = np.linalg.lstsq(X, np.asarray(target), rcond=None)[0]
    return np.asarray(target) - X @ beta

rx = residuals(df["biomarker"], ["age"])
ry = residuals(df["outcome"], ["age"])
partial = np.corrcoef(rx, ry)[0, 1]
crude = df["biomarker"].corr(df["outcome"])
print("crude Pearson r =", round(float(crude), 3))
print("partial r controlling age =", round(float(partial), 3))''',
    interpretation_en="The crude correlation mixes the biomarker-outcome relationship with age effects. The partial correlation asks whether variation in biomarker not explained by age still tracks variation in outcome not explained by age. A drop from crude to partial suggests confounding by age.",
    interpretation_ny="Correlation yosakonzedwa imasakaniza ubale wa biomarker ndi zotsatira pamodzi ndi zaka. Partial imafunsa kuti kusiyana kwa biomarker komwe sikufotokozedwa ndi zaka kukugwirizanabe ndi kusiyana kwa zotsatira komwe sikufotokozedwa ndi zaka. Kutsika kuchokera koyipa kupita ku partial kukusonyeza kusokoneza ndi zaka.",
    limits_en="Partial correlation cannot remove unmeasured confounding or reverse causation. It only handles linear adjustment and gives no slope in original units. Regression is usually clearer for effect estimation.",
    limits_ny="Partial correlation singachotse zinthu zosayezedwa kapena kusintha komwe kumayambitsa. Imagwira ntchito yokhayo yosinthidwa mwa mzere ndipo sipereka slope mu mayunitsi oyambirira. Regression nthawi zambiri imamveka bwino pakuyerekeza zotsatira.",
    explanation_ny="Timachotsa zomwe zaka zingafotokoze pa zinthu zonse ziwiri, kenako timayang'ana ngati zotsala zikugwirizanabe. Izi zili ngati kufanizira anthu azaka zomwezo.",
    analogy_en="It is like comparing exam scores after accounting for study hours. You ask whether the remaining difference in scores still follows the remaining difference in the other factor.",
    analogy_ny="Zili ngati kuyerekeza mphambu za mayeso mutaganizira maola ophunzirira. Mumafunsa kuti kusiyana kotsala kwa mphambu kukutsatabe kusiyana kotsala kwa chinthu china.",
    report_en="Report crude and partial correlations, the covariates adjusted for, n and the linear-model assumption. Prefer regression if a slope is needed.",
    report_ny="Nenani correlation yosakonzedwa ndi partial, zinthu zomwe zidasinthidwa, n ndi mfundo ya linear model. Ngati slope ikufunika, khalani ndi regression.",
    application_en="Checking whether a biomarker-outcome association persists after accounting for age.",
    application_ny="Kuyang'ana kuti ubale wa biomarker ndi zotsatira ukupitilizabe mutaganizira zaka.",
)

E(
    category="association",
    term="Correlation matrix with multiplicity control",
    term_ny="Matrix ya correlation ndi kukonza kwa mayeso ambiri",
    use_en="Use when exploring many pairwise correlations and you need to reduce the chance of over-interpreting accidental significant pairs.",
    use_ny="Gwiritsani ntchito poyang'ana ma correlation ambiri pakati pa zinthu ndipo mukufuna kupewa kukhulupirira mwangozi ma pair omwe awoneka ofunika.",
    assumptions_en="Each pair uses complete independent observations; linear correlations are meaningful; the set of tested pairs is defined in advance. Benjamini-Hochberg controls expected false discoveries across the family.",
    assumptions_ny="Pair iliyonse imagwiritsa ntchito ma observation odziyimira pawokha athunthu; ma correlation a mzere ali oyenera; gulu la ma pair lakhazikitsidwa kale. Benjamini-Hochberg imalamulira zopezeka zabodza mu gulu lonse.",
    code='''import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112224)
cols = ["marker_a", "marker_b", "marker_c", "marker_d", "outcome"]
df = pd.DataFrame(rng.normal(size=(90, len(cols))), columns=cols)
df["outcome"] += 0.5*df["marker_a"] - 0.3*df["marker_c"]

rows = []
for i, a in enumerate(cols[:-1]):
    for b in cols[i+1:]:
        r, p = stats.pearsonr(df[a], df[b])
        rows.append((a, b, r, p))
res = pd.DataFrame(rows, columns=["x", "y", "r", "p"])
res["bh_p"] = multipletests(res["p"], method="fdr_bh")[1]
print(res.assign(r=res["r"].round(3), p=res["p"].round(4),
                 bh_p=res["bh_p"].round(4)).to_string(index=False))''',
    interpretation_en="Many correlations produce many p-values. BH-adjusted p-values are larger and indicate which associations survive a controlled false-discovery proportion. The sign and size of r still describe direction and strength.",
    interpretation_ny="Ma correlation ambiri amatulutsa ma p ambiri. p za BH zimakula ndipo zikusonyeza ubale uti womwe wapulumuka gawo lolamulidwa la zopezeka zabodza. Chizindikiro ndi kukula kwa r zikufotokozabe komwe ubale ukupita ndi mphamvu yake.",
    limits_en="Correlation matrices do not imply a network of causal relationships. Correlated predictors make individual p-values hard to interpret. Exploratory findings need validation in independent data.",
    limits_ny="Matrix ya correlation siyitanthauza kuti pali maubale a causality. Zinthu zogwirizana zimapangitsa ma p pa chimodzi chimodzi kukhala ovuta kutanthauzira. Zopezeka poyamba zifunika kutsimikiziridwa ndi deta ina.",
    explanation_ny="Mukayang'ana ma correlation onse nthawi imodzi, mwayi wopeza imodzi yabodza ukuwonjezeka. Kukonza kwa BH kumachepetsa chiopsezo chakuti maubale ambiri omwe mwalengeza ndi amwayi.",
    analogy_en="It is like scanning many security camera feeds. The more screens you watch, the more likely one flicker looks suspicious; a rule is needed to decide what deserves attention.",
    analogy_ny="Zili ngati kuyang'ana makamera ambiri achitetezo. Mukayang'ana zowonerapo zambiri, kung'ambika kumodzi kumakhala kotheka kuoneka kokayikitsa; pamafunika lamulo losankha zoyenera kuyang'ana.",
    report_en="State the number of tested pairs, the correction method and both raw and adjusted p-values where useful. Label the analysis exploratory.",
    report_ny="Nenani kuchuluka kwa ma pair omwe adayesedwa, njira yosinthira ndi p zoyambirira ndi zosinthidwa ngati zikuthandiza. Lembani kusanthula ngati kofufuza.",
    application_en="Screening a panel of biomarkers for associations with a continuous outcome.",
    application_ny="Kusakha gulu la ma biomarker kuti muwone ubale ndi zotsatira za manambala.",
)

E(
    category="regression",
    term="Simple linear regression",
    term_ny="Linear regression yosavuta",
    use_en="Use when the outcome is continuous and you want to estimate how its mean changes per one-unit increase in a single predictor.",
    use_ny="Gwiritsani ntchito pamene zotsatira zili za manambala ndipo mukufuna kuyerekeza kuti avareji yake imasintha bwanji pa kuwonjezeka kwa chinthu chimodzi.",
    assumptions_en="Linearity, independent observations, approximately normal residuals with constant variance for small-sample inference, and no single point dominating the fit. Inspect a residual plot.",
    assumptions_ny="Ubale wa mzere, ma observation odziyimira pawokha, ma residual pafupifupi normal ndi variance yofanana ngati deta ndi yochepa, komanso palibe point imodzi yoyendetsa model. Yang'anani residual plot.",
    code='''import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112225)
gestation = rng.normal(38, 2, 90)
birth_weight = 180 + 78*gestation + rng.normal(0, 120, 90)
df = pd.DataFrame({"gestation": gestation, "birth_weight": birth_weight})

fit = smf.ols("birth_weight ~ gestation", data=df).fit()
ci = fit.conf_int().loc["gestation"]
print("intercept =", round(float(fit.params["Intercept"]), 1))
print("slope =", round(float(fit.params["gestation"]), 2))
print("95% CI for slope =", round(float(ci[0]), 2), "to", round(float(ci[1]), 2))
print("p =", round(float(fit.pvalues["gestation"]), 6))
print("R squared =", round(float(fit.rsquared), 3))''',
    interpretation_en="The slope is the estimated change in the outcome mean for a one-unit increase in the predictor, in the predictor's units. The CI describes uncertainty in that slope. R squared is the proportion of outcome variance explained by this simple model.",
    interpretation_ny="Slope ndi kusintha koyerekeza kwa avareji ya zotsatira pa kuwonjezeka kwa chimodzi kwa chinthu cholosera, mu mayunitsi ake. CI ikufotokoza kusatsimikizika kwa slope. R squared ndi gawo la kusiyana kwa zotsatira lofotokozedwa ndi model yosavutayi.",
    limits_en="Association is not causation. Extrapolation beyond the observed predictor range is unsafe. A significant slope can be small; a non-significant slope can reflect low power. Check residuals and influential points.",
    limits_ny="Ubale si causality. Kuyerekeza kunja kwa mtundu wa predictor wowonedwa n'kotetezeka. Slope yofunika ikhoza kukhala yaying'ono; yosafunika ikhoza kuwonetsa mphamvu yochepa. Yang'anani ma residual ndi ma point owopsa.",
    explanation_ny="Linear regression imajambula mzere wabwino kwambiri wodutsa pa deta. Slope imatiuza kuti zotsatira zikusintha bwanji pamene chinthu cholosera chikuwonjezeka.",
    analogy_en="It is like fitting a straight edge to a scatter of points: the slope tells you how much the line rises for each step sideways.",
    analogy_ny="Zili ngati kuyika mzere wowongoka pamfundo zambiri: slope imatiuza kuti mzerewo ukukwera bwanji pa sitepe iliyonse yopita mbali.",
    report_en="Report the fitted equation, slope with 95% CI and p, R squared, n and diagnostic checks. State units explicitly.",
    report_ny="Nenani equation yoyenerera, slope ndi 95% CI ndi p, R squared, n ndi macheke a diagnostics. Fotokozani mayunitsi momveka.",
    application_en="Estimating the expected change in birth weight associated with gestational age.",
    application_ny="Kuyerekeza kusintha koyembekezeka kwa kulemera kwa makanda mogwirizana ndi msinkhu wa mimba.",
)

E(
    category="regression",
    term="Multiple linear regression and adjustment",
    term_ny="Multiple linear regression ndi kusintha",
    use_en="Use when a continuous outcome has several predictors and you need an adjusted association for one predictor while holding the others fixed in the model.",
    use_ny="Gwiritsani ntchito pamene zotsatira za manambala zili ndi zinthu zolosera zingapo ndipo mukufuna ubale wosinthidwa wa chimodzi pamene zina zakhazikitsidwa mu model.",
    assumptions_en="Linearity in parameters; independent errors; approximately constant residual variance; no severe multicollinearity; confounders chosen from subject knowledge or a causal diagram, not stepwise p-values alone.",
    assumptions_ny="Ubale wa mzere pa magawo; zolakwika zodziyimira pawokha; variance ya residual pafupifupi yofanana; palibe multicollinearity yoopsa; zinthu zosokoneza zimasankhidwa kuchokera ku chidziwitso cha nkhani kapena chithunzi cha causality, osati p za stepwise zokha.",
    code='''import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112226)
n = 140
age = rng.normal(30, 7, n)
bmi = 0.15*age + rng.normal(24, 3, n)
exposure = rng.integers(0, 2, n)
bp = 70 + 0.35*age + 0.8*bmi + 5*exposure + rng.normal(0, 6, n)
df = pd.DataFrame({"age": age, "bmi": bmi,
                   "exposure": exposure, "bp": bp})

crude = smf.ols("bp ~ exposure", data=df).fit()
adjusted = smf.ols("bp ~ exposure + age + bmi", data=df).fit()
for name, fit in [("crude", crude), ("adjusted", adjusted)]:
    ci = fit.conf_int().loc["exposure"]
    print(name, "exposure coefficient =",
          round(float(fit.params["exposure"]), 2),
          "95% CI", round(float(ci[0]), 2), "to", round(float(ci[1]), 2),
          "p =", round(float(fit.pvalues["exposure"]), 4))''',
    interpretation_en="The crude coefficient combines the exposure association with age and BMI differences. The adjusted coefficient estimates the exposure contrast at the same age and BMI. Compare both to understand confounding, not to pick the more impressive number.",
    interpretation_ny="Coefficient yosakonzedwa imaphatikiza ubale wa exposure ndi kusiyana kwa zaka ndi BMI. Coefficient yosinthidwa imayerekeza kusiyana kwa exposure pa zaka ndi BMI zofanana. Fananizani zonse kuti mumvetse kusokoneza, osati kusankha nambala yochititsa chidwi.",
    limits_en="Adjustment can introduce bias if you adjust for colliders or mediators on the causal path. Coefficients depend on the correct functional form. observational adjusted associations are still not automatically causal.",
    limits_ny="Kusintha kungabweretse kukondera ngati musintha collider kapena mediator yomwe ili pa njira ya causality. Ma coefficient amadalira mawonekedwe olondola a model. Ubale wosinthidwa wa observational si wokhawo womwe ungakhale causality.",
    explanation_ny="Mukasintha, mumafanizira anthu ofanana mwa zaka ndi BMI kuti muone kuti exposure yokha imabweretsa kusiyana kotani. Izi zili ngati kufanizira apulo ndi apulo, osati apulo ndi nthochi.",
    analogy_en="It is like comparing salaries after accounting for experience and region. Otherwise a group difference may simply reflect who has worked longer.",
    analogy_ny="Zili ngati kuyerekeza malipiro mutaganizira zokumana nazo ndi dera. Popanda izi, kusiyana kwa magulu kungakhale chifukwa choti ena agwira ntchito nthawi yayitali.",
    report_en="Name the adjustment set and why each covariate was included. Report crude and adjusted coefficients with 95% CIs and diagnostics.",
    report_ny="Tchulani zinthu zosinthidwa ndi chifukwa chake chilichonse chinaphatikizidwa. Nenani coefficient yosakonzedwa ndi yosinthidwa ndi 95% CI ndi diagnostics.",
    application_en="Estimating an exposure-blood pressure association while accounting for age and BMI.",
    application_ny="Kuyerekeza ubale wa exposure ndi kuthamanga kwa magazi pamene zaka ndi BMI zaganiziridwa.",
)

E(
    category="regression",
    term="Logistic regression and odds ratios",
    term_ny="Logistic regression ndi odds ratios",
    use_en="Use when the outcome is binary and you want to model the probability of an event and estimate adjusted odds ratios for predictors.",
    use_ny="Gwiritsani ntchito pamene zotsatira zili za binary ndipo mukufuna kuyerekeza mwayi wa chochitika ndi ma odds ratio osinthidwa a zinthu zolosera.",
    assumptions_en="Independent observations; binary outcome; linearity of continuous predictors in the log-odds; no perfect separation; adequate events per parameter. Check calibration and influential observations.",
    assumptions_ny="Ma observation odziyimira pawokha; zotsatira za binary; zinthu za manambala zikhale zofanana ndi log-odds; palibe kulekanitsa kwangwiro; zochitika zokwanira pa parameter. Yang'anani calibration ndi ma observation owopsa.",
    code='''import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112227)
n = 220
age = rng.normal(32, 8, n)
exposure = rng.integers(0, 2, n)
lin = -3.0 + 0.045*age + 0.85*exposure
prob = 1/(1 + np.exp(-lin))
event = rng.binomial(1, prob)
df = pd.DataFrame({"age": age, "exposure": exposure, "event": event})

fit = smf.logit("event ~ exposure + age", data=df).fit(disp=False)
ci = np.exp(fit.conf_int())
print("event count =", int(df["event"].sum()), "of", n)
for name in ["exposure", "age"]:
    print(name, "OR =", round(float(np.exp(fit.params[name])), 3),
          "95% CI", round(float(ci.loc[name, 0]), 3), "to",
          round(float(ci.loc[name, 1]), 3),
          "p =", round(float(fit.pvalues[name]), 4))''',
    interpretation_en="exp(coefficient) is an odds ratio: the multiplicative change in event odds for a one-unit increase in the predictor, holding others fixed. It is not a risk ratio and should not be described as 'times more likely' for common outcomes.",
    interpretation_ny="exp(coefficient) ndi odds ratio: kuchuluka kwa ma odds a chochitika pa kuwonjezeka kwa chimodzi kwa predictor, zinthu zina zili zofanana. Si risk ratio ndipo sayenera kutchedwa 'katheŵa kuchuluka mwayi' ngati zochitika zili zofala.",
    limits_en="Odds ratios overstate risk ratios for common outcomes. Separation produces huge coefficients and invalid p-values. Logistic regression estimates associations; causal interpretation needs an appropriate design and adjustment set.",
    limits_ny="Ma odds ratio amakokomeza risk ratio ngati zochitika zili zofala. Kulekanitsa kumapanga coefficient zazikulu ndi p zosadalirika. Logistic regression imayerekeza ubale; kutanthauzira kwa causality kumafuna kapangidwe ndi gulu loyenera losinthidwa.",
    explanation_ny="Logistic regression imagwira ntchito ndi mwayi wa chochitika cha binary. M'malo moyerekeza kusiyana kwa manambala, imayerekeza kuti ma odds achulukana kangati.",
    analogy_en="If a treatment changes the odds from 1 in 9 to 2 in 9, the odds ratio is 2, but the risk itself did not double. The odds ratio is about odds, not probability.",
    analogy_ny="Ngati chithandizo chasintha ma odds kuchokera 1 mwa 9 kufika 2 mwa 9, odds ratio ndi 2, koma mwayiwo sunawirikizeke. Odds ratio imayesa ma odds, osati probability.",
    report_en="Report adjusted odds ratios with 95% CIs, the outcome definition, adjustment set and model diagnostics. Avoid converting ORs into risks without a method.",
    report_ny="Nenani ma odds ratio osinthidwa ndi 95% CI, tanthauzo la zotsatira, zinthu zosinthidwa ndi diagnostics. Pewani kusintha OR kukhala zoopsi popanda njira yoyenera.",
    application_en="Modelling the odds of a neonatal outcome after exposure adjustment.",
    application_ny="Kuyerekeza ma odds a zotsatira za makanda pambuyo posintha zinthu zosokoneza.",
)

E(
    category="regression",
    term="Poisson regression for counts",
    term_ny="Poisson regression ya kuchuluka",
    use_en="Use for count outcomes when the mean and variance are expected to be similar and you want rate or count ratios from exposures and offsets.",
    use_ny="Gwiritsani ntchito pa zotsatira za kuchuluka pamene avareji ndi variance zikuyembekezeka kufanana ndipo mukufuna chiŵerengero cha mitengo kapena kuchuluka kuchokera ku exposure ndi offset.",
    assumptions_en="Counts are independent; conditional mean equals conditional variance (equidispersion); log link is appropriate; exposure time or population at risk is included as an offset when denominator differs.",
    assumptions_ny="Kuchuluka kodziyimira pawokha; avareji yoyenerera ikufanana ndi variance; log link ndi yoyenera; nthawi kapena chiwerengero cha anthu chikuphatikizidwa ngati offset ngati denominator ikusiyana.",
    code='''import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112228)
n = 180
group = rng.integers(0, 2, n)
age = rng.normal(45, 10, n)
mu = np.exp(0.7 + 0.4*group + 0.01*age)
visits = rng.poisson(mu)
df = pd.DataFrame({"visits": visits, "group": group, "age": age})

fit = smf.glm("visits ~ group + age", data=df,
              family=sm.families.Poisson()).fit()
for name in ["group", "age"]:
    ci = np.exp(fit.conf_int().loc[name])
    print(name, "rate ratio =", round(float(np.exp(fit.params[name])), 3),
          "95% CI", round(float(ci[0]), 3), "to", round(float(ci[1]), 3))
print("Pearson chi2 / df =", round(float(fit.pearson_chi2/fit.df_resid), 3))''',
    interpretation_en="Exponentiated coefficients are rate or count ratios. The dispersion check near 1 supports the Poisson mean-variance assumption; a much larger value suggests overdispersion and a negative binomial model.",
    interpretation_ny="Ma coefficient otengedwa exp ndi chiŵerengero cha mitengo kapena kuchuluka. Kufufuza dispersion pafupi ndi 1 kumathandizira mfundo ya Poisson yakuti avareji ndi variance zili pafupi; mtengo waukulu kwambiri ukuwonetsa kufalikira kwambiri ndipo kungafune negative binomial.",
    limits_en="Ignoring differing follow-up time or population size produces misleading rates. Overdispersion makes Poisson standard errors too small. Excess zeros may require a zero-inflated model.",
    limits_ny="Kunyalanyaza nthawi yotsatira kapena kuchuluka kwa anthu kumapanga mitengo yolakwika. Kufalikira kwambiri kumapangitsa standard errors za Poisson kukhala zazing'ono. Zeros zochuluka zingafune zero-inflated model.",
    explanation_ny="Poisson imagwiritsidwa ntchito powerengera zinthu monga kuchuluka kwa ma visit. Imayerekeza kuchuluka kwa zinthu ndi kugwiritsa ntchito log kuti zotsatira zisakhale zoipa.",
    analogy_en="It is like modelling the number of buses arriving at a stop per hour: counts cannot be negative, and the model works in log scale to respect that.",
    analogy_ny="Zili ngati kuyerekeza kuchuluka kwa mabasi ofika pa siteshoni pa ola limodzi: kuchuluka sikungakhale koyipa, kotero model imagwiritsa ntchito log kuti ipewe zotsatira zosatheka.",
    report_en="Report rate ratios with 95% CIs, the offset definition, dispersion check and whether an alternative count model was considered.",
    report_ny="Nenani chiŵerengero cha mitengo ndi 95% CI, tanthauzo la offset, kuyang'ana dispersion ndi ngati model ina ya kuchuluka idaganiziridwa.",
    application_en="Modelling monthly clinic visit counts by programme and age.",
    application_ny="Kuyerekeza kuchuluka kwa ma visit a kuchipatala pamwezi mwa pulogalamu ndi zaka.",
)

E(
    category="regression",
    term="Negative binomial regression",
    term_ny="Negative binomial regression",
    use_en="Use for overdispersed count outcomes when the variance is substantially larger than the mean and Poisson standard errors would be too optimistic.",
    use_ny="Gwiritsani ntchito pa kuchuluka kofalikira kwambiri pamene variance ndi yokulirapo kwambiri kuposa avareji ndipo standard errors za Poisson zingakhale zolimbikitsa kwambiri.",
    assumptions_en="Counts are independent; conditional variance is mean plus an overdispersion parameter; log link is suitable. Compare fit with Poisson using AIC on the same data and outcome.",
    assumptions_ny="Kuchuluka kodziyimira pawokha; variance yoyenerera ndi avareji kuphatikiza parameter yofalikira; log link ndi yoyenera. Fananizani kukwanira kwa model ndi Poisson pogwiritsa ntchito AIC pa deta yomweyo.",
    code='''import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112229)
n = 200
group = rng.integers(0, 2, n)
mu = np.exp(1.0 + 0.6*group)
visits = rng.negative_binomial(2, 2/(2 + mu))
df = pd.DataFrame({"visits": visits, "group": group})

poisson = smf.glm("visits ~ group", data=df,
                  family=sm.families.Poisson()).fit()
nb = smf.negativebinomial("visits ~ group", data=df).fit(disp=False)
print("Poisson AIC =", round(float(poisson.aic), 1))
print("NegBin AIC =", round(float(nb.aic), 1))
print("NegBin alpha =", round(float(nb.params["alpha"]), 3))
print("group rate ratio =", round(float(np.exp(nb.params["group"])), 3))''',
    interpretation_en="Lower AIC favours the model with the better trade-off between fit and complexity. The alpha parameter quantifies extra variance beyond Poisson. The exponentiated group coefficient is a rate ratio under the negative binomial model.",
    interpretation_ny="AIC yotsika imakonda model yomwe ili ndi mgwirizano wabwino pakati pa kukwanira ndi kuvuta. Parameter alpha imayeza kusiyana kwowonjezera kuposa Poisson. Coefficient ya group yotengedwa exp ndi chiŵerengero cha mitengo pansi pa model ya negative binomial.",
    limits_en="AIC comparison is not a hypothesis test of causality. If zeros come from a separate process, zero-inflated models may be needed. Large overdispersion may signal missing clustering or predictors.",
    limits_ny="Kuyerekeza kwa AIC si mayeso wa causality. Ngati zeros zili ndi njira yosiyana, zero-inflated models zingafunike. Kufalikira kwakukulu kungasonyeze kuti pali magulu ogwirizana kapena zinthu zosowa mu model.",
    explanation_ny="Poisson ikaganiza kuti avareji ndi variance zili pafupi. Koma kuchuluka kwa ma visit kumasiyana kwambiri, choncho negative binomial imawonjezera parameter yothandizira kufalikira kumeneko.",
    analogy_en="Poisson is like assuming every bus stop has the same unpredictability. Negative binomial allows some stops to be much more erratic than others.",
    analogy_ny="Poisson ili ngati kuganiza kuti mabasi pa siteshoni zilizonse ali ndi kusadziwikiratu kofanana. Negative binomial imalola kuti zina zikhale zosasinthasintha kwambiri kuposa zina.",
    report_en="Report both Poisson and negative binomial AIC if compared, alpha, rate ratios with CIs and the rationale for the chosen count model.",
    report_ny="Nenani AIC ya Poisson ndi negative binomial ngati zidayerekezedwa, alpha, chiŵerengero cha mitengo ndi CI ndi chifukwa chosankha model ya kuchuluka.",
    application_en="Modelling overdispersed infection counts across health facilities.",
    application_ny="Kuyerekeza kuchuluka kwa matenda ofalikira kwambiri m'ma chipatala osiyanasiyana.",
)

E(
    category="regression",
    term="Gamma GLM for positive skewed outcomes",
    term_ny="Gamma GLM ya zotsatira zabwino zopendekerera",
    use_en="Use for continuous positive outcomes with right skew and roughly constant coefficient of variation, such as costs or laboratory concentrations, using a log link.",
    use_ny="Gwiritsani ntchito pa zotsatira za manambala zoposa zero zopendekerera kumanja komanso kukhala ndi coefficient of variation wofanana, monga ndalama kapena kuchuluka kwa labu, pogwiritsa ntchito log link.",
    assumptions_en="Outcome is positive; conditional variance increases with the square of the mean; log link is appropriate; observations independent. It is not for zero-heavy data without a special model.",
    assumptions_ny="Zotsatira ziyenera kukhala zoposa zero; variance yoyenerera imakula ndi sikweya ya avareji; log link ndi yoyenera; ma observation odziyimira pawokha. Si yoyenera deta yochuluka ya zero popanda model yapadera.",
    code='''import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112230)
n = 140
group = rng.integers(0, 2, n)
mean_cost = np.exp(5.0 + 0.25*group)
cost = rng.gamma(shape=4.0, scale=mean_cost/4.0)
df = pd.DataFrame({"cost": cost, "group": group})

fit = smf.glm("cost ~ group", data=df,
              family=sm.families.Gamma(link=sm.families.links.Log())).fit()
ratio = np.exp(fit.params["group"])
ci = np.exp(fit.conf_int().loc["group"])
print("group geometric mean ratio =", round(float(ratio), 3))
print("95% CI =", round(float(ci[0]), 3), "to", round(float(ci[1]), 3))
print("p =", round(float(fit.pvalues["group"]), 4))''',
    interpretation_en="With a log link, exp(group coefficient) is a ratio of geometric means, not a difference in arithmetic means. This is often a better summary for skewed positive data than forcing a normal linear model.",
    interpretation_ny="Ndi log link, exp(group coefficient) ndi chiŵerengero cha avareji za geometric, osati kusiyana kwa avareji za arithmetic. Izi nthawi zambiri zimakhala zabwinoko pa deta yabwino yopendekerera kusiyana ndi kukakamiza linear model ya normal.",
    limits_en="Gamma GLM cannot handle exact zeros. Results depend on the variance function; a log-transformed OLS answers a related but different question. It does not automatically model repeated measures.",
    limits_ny="Gamma GLM singagwire ma zero ndendende. Zotsatira zimadalira ntchito ya variance; OLS yotembenuza log imayankha funso lofanana koma losiyana. Sizimapanga ma repeated measures.",
    explanation_ny="Deta ina monga ndalama kapena kuchuluka kwa labu siyoyenera kuyerekeza ndi avareji yamba chifukwa imakhala ndi mchira wautali. Gamma GLM imaganizira kuti kusiyana kumakula pamene avareji ikukula.",
    analogy_en="It is like comparing household spending: a few very large bills stretch the distribution, so a ratio of typical spending is more stable than a raw mean difference.",
    analogy_ny="Zili ngati kuyerekeza ndalama zapakhomo: mabilu akuluakulu ochepa amatambasula kagawidwe, kotero chiŵerengero cha ndalama zamba chimakhala chokhazikika kuposa kusiyana kwa avareji yaiwisi.",
    report_en="Report the geometric mean ratio with 95% CI, the variance and link functions, and how zeros were handled or why none occurred.",
    report_ny="Nenani chiŵerengero cha avareji za geometric ndi 95% CI, ntchito za variance ndi link, ndi momwe ma zero adayendetsedwera kapena chifukwa chake palibe.",
    application_en="Comparing mean laboratory cost between two care pathways.",
    application_ny="Kuyerekeza mtengo wa labu pakati pa njira ziwiri za chisamaliro.",
)

E(
    category="regression",
    term="Confounding and crude versus adjusted effect",
    term_ny="Kusokoneza ndi zotsatira zosakonzedwa ndi zosinthidwa",
    use_en="Use when an exposure-outcome association may be distorted by a third variable that is associated with the exposure and independently affects the outcome.",
    use_ny="Gwiritsani ntchito pamene ubale wa exposure ndi zotsatira ungakonde kusokonezedwa ndi chinthu chachitatu chogwirizana ndi exposure komanso chokhudza zotsatira palokha.",
    assumptions_en="The confounder is measured before exposure where possible, is not on the causal pathway, and is chosen using subject knowledge or a causal diagram. No unmeasured confounding is assumed for a causal claim.",
    assumptions_ny="Chosokoneza chayezedwa exposure isanachitike ngati kuli kotheka, sichili panjira ya causality, ndipo chinasankhidwa pogwiritsa ntchito chidziwitso kapena chithunzi cha causality. Palibe chosokoneza chosayezedwa chomwe chikuganiziridwa pa mfundo ya causality.",
    code='''import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112231)
n = 200
age = rng.normal(60, 8, n)
exposure = (rng.random(n) < (0.25 + 0.007*(age-60))).astype(int)
lin = -2.5 + 0.04*age + 0.7*exposure
event = rng.binomial(1, 1/(1+np.exp(-lin)))
df = pd.DataFrame({"age": age, "exposure": exposure, "event": event})

crude = smf.logit("event ~ exposure", data=df).fit(disp=False)
adj = smf.logit("event ~ exposure + age", data=df).fit(disp=False)
print("crude OR =", round(float(np.exp(crude.params["exposure"])), 3))
print("age-adjusted OR =", round(float(np.exp(adj.params["exposure"])), 3))
print("age OR =", round(float(np.exp(adj.params["age"])), 3))''',
    interpretation_en="Older participants are more likely to be exposed and to experience the event, so the crude odds ratio is inflated. Adjusting for age removes that part of the association. A change after adjustment suggests confounding, while a small change suggests little confounding in this simulated setting.",
    interpretation_ny="Anthu okalamba amakonda kukhala ndi exposure komanso kukumana ndi chochitika, kotero odds ratio yosakonzedwa imakokomeza. Kusintha ndi zaka kumachotsa gawo la ubalewo. Kusintha pambuyo posintha kukusonyeza kusokoneza, pamene kusintha kochepa kukusonyeza kuti m'kafukufuku wopangidwawu kusokoneza kunali kochepa.",
    limits_en="A big change is not proof that adjustment was correct; adjusting for colliders can create bias. Confounding cannot be removed if the important variable was not measured. Crude and adjusted answers address different questions.",
    limits_ny="Kusintha kwakukulu sikutsimikizira kuti kusinthako kunali kolondola; kusintha collider kungabweretse kukondera. Kusokoneza sikungachotsedwe ngati chinthu chofunika sichina yezedwe. Mayankho osakonzedwa ndi osinthidwa amayankha mafunso osiyana.",
    explanation_ny="Kusokoneza kumachitika ngati chinthu chachitatu chikugwirizana ndi exposure ndi zotsatira. Mwachitsanzo, zaka zingapangitse munthu kukhala ndi exposure komanso kukhala pachiwopsezocho.",
    analogy_en="Ice cream sales and drowning both rise in summer. Summer is the confounder; banning ice cream would not prevent drowning.",
    analogy_ny="Kugulitsa ayisikilimu ndi kumira m'madzi zimawonjezeka chilimwe. Chilimwe ndi chosokoneza; kuletsa ayisikilimu sikungaletse kumira.",
    report_en="Present crude and adjusted effects side by side, name the confounder and justify its inclusion. Do not select confounders by statistical significance alone.",
    report_ny="Ikani zotsatira zosakonzedwa ndi zosinthidwa pafupi, tchulani chosokoneza ndipo mulungitse kuphatikizidwa kwake. Musasankhe zosokoneza potengera kufunika kwa p okha.",
    application_en="Comparing a crude and age-adjusted exposure effect in an observational cohort.",
    application_ny="Kuyerekeza zotsatira za exposure zosakonzedwa ndi zosinthidwa ndi zaka mu gulu la observational.",
)

E(
    category="regression",
    term="Interaction and effect modification",
    term_ny="Kuyanjana ndi kusintha kwa zotsatira",
    use_en="Use when you suspect the exposure effect differs across levels of another variable, such as sex or treatment setting, and you want to test that difference explicitly.",
    use_ny="Gwiritsani ntchito pamene mukukayikira kuti zotsatira za exposure zimasiyana m'magulu ena, monga jenda kapena malo a chithandizo, ndipo mukufuna kuyesa kusiyana kumeneko momveka.",
    assumptions_en="Adequate sample size in each stratum; the model includes both main effects and the product term; interaction is specified before examining many possible subgroups. Continuous predictors should be centred where useful.",
    assumptions_ny="Deta yokwanira mu gulu lililonse; model ikuphatikiza main effects ndi product term; kuyanjana kwafotokozedwa kale musanayang'ane magulu ambiri. Zinthu za manambala zikhoza kuyikidwa pakati ngati zikuthandiza.",
    code='''import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112232)
n = 240
group = rng.integers(0, 2, n)
sex = rng.integers(0, 2, n)
risk = -2.0 + 0.35*group + 0.9*sex + 1.1*group*sex + rng.normal(0, 0.5, n)
event = rng.binomial(1, 1/(1+np.exp(-risk)))
df = pd.DataFrame({"group": group, "sex": sex, "event": event})

fit = smf.logit("event ~ group * sex", data=df).fit(disp=False)
p_int = fit.pvalues["group:sex"]
or_g0 = np.exp(fit.params["group"])
or_g1 = np.exp(fit.params["group"] + fit.params["group:sex"])
print("interaction p =", round(float(p_int), 4))
print("OR in sex=0 =", round(float(or_g0), 3))
print("OR in sex=1 =", round(float(or_g1), 3))''',
    interpretation_en="The product-term p-value tests whether the group effect differs by sex. The stratum-specific ORs describe the effect in each sex. Do not rely only on the interaction p-value; report both strata with their uncertainty.",
    interpretation_ny="p ya product term imayesa kuti zotsatira za gulu zimasiyana ndi jenda. Ma OR a m'magulu amafotokoza zotsatira pa jenda iliyonse. Musadalire p yokha; nenani magulu onse awiri ndi kusatsimikizika kwawo.",
    limits_en="Subgroup analyses are easily overdone and can produce false positives. Lack of a significant interaction does not prove effects are identical. The scale matters: interaction can exist on one scale but not another.",
    limits_ny="Kusanthula magulu ang'ono kungachitidwe mopitirira muyeso ndipo kungatulutse zopezeka zabodza. Kusowa kwa interaction yofunika sikutsimikizira kuti zotsatira zili zofanana. Muyezo womwe wagwiritsidwa ntchito ndi wofunika: interaction ikhoza kuwoneka pa muyezo umodzi osati pa wina.",
    explanation_ny="Interaction imafunsa kuti mankhwala amagwira ntchito mofanana kwa aliyense kapena ayi. Mwachitsanzo, zotsatira zake zikhoza kukhala zazikulu kwa amuna kuposa azimayi.",
    analogy_en="It is like a fertiliser that works well in wet soil but not in dry soil. The average effect hides an important interaction with soil condition.",
    analogy_ny="Zili ngati feteleza wogwira bwino m'nthaka yonyowa koma osagwira m'nthaka youma. Zotsatira za avareji zimabisala kuyanjana kwakukulu ndi mtunda wa nthaka.",
    report_en="Report the interaction term with p and CI, stratum-specific effects with CIs, and whether the subgroup hypothesis was prespecified.",
    report_ny="Nenani product term ndi p ndi CI, zotsatira za gulu lililonse ndi CI, ndi kaya lingaliro la subgroup linali lokonzedweratu.",
    application_en="Testing whether an intervention effect differs by participant group.",
    application_ny="Kuyesa kuti zotsatira za chithandizo zimasiyana ndi gulu la omwe atengapo mbali.",
)

E(
    category="regression",
    term="Multicollinearity and VIF",
    term_ny="Multicollinearity ndi VIF",
    use_en="Use when several predictors are highly correlated and you need to diagnose unstable regression coefficients before interpreting individual terms.",
    use_ny="Gwiritsani ntchito pamene zinthu zolosera zingapo zili ndi ubale wapamtima ndipo mukufuna kuona ngati coefficient za regression zili zosasinthika musanazitanthauzire.",
    assumptions_en="VIF is computed from the linear relationships among predictors. It is a diagnostic, not a test of model correctness. It applies to the planned adjustment set, not to correlations in isolation.",
    assumptions_ny="VIF imawerengedwa kuchokera ku ubale wa mzere pakati pa zinthu zolosera. Ndi chida chowunikira, osati mayeso wakuti model ndi yolondola. Imakhudza gulu la zinthu zomwe zakonzedwa, osati ma correlation okha.",
    code='''import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112233)
n = 100
x1 = rng.normal(0, 1, n)
x2 = 0.92*x1 + rng.normal(0, 0.25, n)
x3 = rng.normal(0, 1, n)
X = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3})
Xc = sm.add_constant(X)
vifs = [variance_inflation_factor(Xc.values, i)
        for i in range(Xc.shape[1])][1:]
print(pd.DataFrame({"predictor": X.columns,
                    "VIF": np.round(vifs, 2)}).to_string(index=False))
print("correlation x1-x2 =", round(float(X["x1"].corr(X["x2"])), 3))''',
    interpretation_en="High VIF means a predictor is largely explained by the others, so its individual coefficient is poorly determined and standard errors are inflated. VIF above roughly 5 or 10 is commonly flagged, but context matters.",
    interpretation_ny="VIF yapamwamba imatanthauza kuti predictor imodzi imafotokozedwa kwambiri ndi ena, kotero coefficient yake payokha siyodalirika ndipo standard errors zimakula. VIF yoposa 5 kapena 10 nthawi zambiri imadziwika, koma nkhani ndi yofunika.",
    limits_en="High VIF does not bias predictions or invalidate the overall model. Dropping a confounder just to lower VIF can introduce bias. Centring helps polynomial terms but not genuine redundancy between distinct variables.",
    limits_ny="VIF yapamwamba siyikondera zolosera kapena kuwononga model yonse. Kuchotsa chinthu chosokoneza kungoti VIF itsike kungabweretse kukondera. Kuyika pakati kumathandiza polynomial koma sikuthandiza kusiyana kwachilengedwe pakati pa zinthu.",
    explanation_ny="Ngati zinthu zolosera ziwiri zikunena pafupifupi zinthu zomwezo, model imavutika kudziwa kuti ndi iti yomwe ikuyambitsa kusintha. VIF imatiuza kuti vutolo lili bwanji.",
    analogy_en="It is like two witnesses who give identical testimony. Their agreement does not give two independent pieces of evidence, and the court cannot tell which one is driving the conclusion.",
    analogy_ny="Zili ngati mboni ziwiri zopereka umboni wofanana. Kuvomerezana kwawo sikupereka umboni wawiri wodziyimira pawokha, ndipo khoti silikudziwa kuti ndani akuyendetsa chigamulo.",
    report_en="Report the VIF table and how collinearity was handled: retain for confounding, combine variables, centre polynomial terms or collect more data. Do not report VIF as a p-value.",
    report_ny="Nenani tebulo la VIF ndi momwe kufanana kumeneku kunayendetsedwera: kusunga chosokoneza, kuphatikiza zinthu, kuyika pakati polynomial kapena kusonkhanitsa deta yambiri. Musanene VIF ngati p.",
    application_en="Checking correlated predictors before interpreting an adjusted regression model.",
    application_ny="Kuyang'ana zinthu zolosera zogwirizana musanatanthauzire model ya regression yosinthidwa.",
)

E(
    category="advanced",
    term="Mixed-effects model",
    term_ny="Mixed-effects model",
    use_en="Use for repeated or clustered continuous outcomes when observations within the same participant or site are correlated and you want both fixed effects and random variation between clusters.",
    use_ny="Gwiritsani ntchito pa zotsatira za manambala zobwerezabwereza kapena zogwirizana pamene deta ya munthu yemweyo kapena malo imodzi ili ndi ubale ndipo mukufuna fixed effects ndi kusiyana kwapakati pa magulu.",
    assumptions_en="Correct cluster identity; approximately normal random effects and residuals; correctly specified within-cluster covariance; missing outcomes assumed missing at random conditional on the model.",
    assumptions_ny="Zizindikiritso za gulu ndi zolondola; random effects ndi ma residual pafupifupi normal; covariance mkati mwa gulu yafotokozedwa moyenera; zotsatira zosowa zikuganiziridwa kuti zosowa mwangozi potengera model.",
    code='''import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112234)
rows = []
for pid in range(1, 41):
    intercept = rng.normal(12, 1.8)
    for week in [0, 4, 8]:
        rows.append((pid, week, intercept + 0.18*week +
                     rng.normal(0, 0.9)))
df = pd.DataFrame(rows, columns=["id", "week", "value"])

fit = smf.mixedlm("value ~ week", df, groups=df["id"]).fit(reml=True)
print("fixed intercept =", round(float(fit.fe_params["Intercept"]), 3))
print("fixed week slope =", round(float(fit.fe_params["week"]), 3))
print("between-person variance =",
      round(float(fit.cov_re.iloc[0, 0]), 3))
print("within-person variance =", round(float(fit.scale), 3))''',
    interpretation_en="The fixed week slope is the average change over time. The random-effect variance describes how much participants differ in their baseline level; the residual variance describes within-person noise. This respects the repeated structure instead of pretending all rows are independent.",
    interpretation_ny="Slope ya week ndi kusintha kwamba pakapita nthawi. Random-effect variance ikufotokoza kusiyana kwa anthu pa poyambira; residual variance ikufotokoza phokoso mkati mwa munthu. Izi zilemekeza kapangidwe kobwerezabwereza m'malo kunamiza kuti mizere yonse ndi yodziyimira pawokha.",
    limits_en="A random-intercept model assumes the same time slope for everyone; random slopes need more data. Convergence problems are common with few clusters. It does not automatically solve informative dropout.",
    limits_ny="Random-intercept imaganizira kuti slope ya nthawi ndi yofanana kwa aliyense; random slopes zifuna deta yambiri. Mavuto a convergence amapezeka ngati magulu ndi ochepa. Sikuthetsa kutayika kwa deta komwe kumakhudza zotsatira.",
    explanation_ny="Munthu aliyense ali ndi poyambira payekha, kotero mizere yake siyodziyimira pawokha. Mixed model imapereka aliyense poyambira payekha pamene imayerekeza kusintha kwamba kwa nthawi.",
    analogy_en="It is like tracking several plants: each plant starts at a different height, but you can still estimate the average weekly growth while allowing each plant its own starting point.",
    analogy_ny="Zili ngati kuyang'ana zomera zambiri: chilichonse chimayamba kutalika kosiyana, koma mumathabe kuyerekeza kukula kwamba pa sabata pamene malola chilichonse kukhala ndi poyambira chake.",
    report_en="Report fixed effects with CIs, random-effect variances, the covariance structure, number of clusters and convergence checks.",
    report_ny="Nenani fixed effects ndi CI, ma variance a random effect, kapangidwe ka covariance, kuchuluka kwa magulu ndi macheke a convergence.",
    application_en="Analysing repeated biomarker measurements from the same participants.",
    application_ny="Kusanthula ma biomarker obwerezabwereza kuchokera kwa omwewo.",
)

E(
    category="advanced",
    term="GEE for correlated binary outcomes",
    term_ny="GEE ya zotsatira za binary zogwirizana",
    use_en="Use for repeated binary outcomes when your main interest is the population-average effect and you need standard errors that account for within-person correlation.",
    use_ny="Gwiritsani ntchito pa zotsatira za binary zobwerezabwereza pamene chidwi chachikulu ndi zotsatira za gulu lonse ndipo mukufuna standard errors zomwe ziganizira ubale wa mkati mwa munthu.",
    assumptions_en="Cluster identity is correct; outcome model has the correct mean structure; working correlation need not be perfect for consistency but affects efficiency. Clusters should be independent of each other.",
    assumptions_ny="Zizindikiritso za gulu ndizolondola; model ya zotsatira ili ndi kapangidwe koyenera ka avareji; working correlation siyenera kukhala yangwiro koma imakhudza mphamvu. Magulu akhale odziyimira pawokha pakati pawo.",
    code='''import numpy as np
import pandas as pd
import statsmodels.api as sm

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112235)
rows = []
for pid in range(1, 61):
    base = rng.normal(0, 0.6)
    for visit in [0, 1, 2]:
        group = pid % 2
        lin = -0.8 + base + 0.45*visit + 0.4*group
        prob = 1/(1+np.exp(-lin))
        rows.append((pid, visit, group, rng.binomial(1, prob)))
df = pd.DataFrame(rows, columns=["id", "visit", "group", "event"])

gee = sm.GEE.from_formula("event ~ visit + group", groups="id",
                          data=df, family=sm.families.Binomial()).fit()
for name in ["visit", "group"]:
    print(name, "log-OR =", round(float(gee.params[name]), 3),
          "p =", round(float(gee.pvalues[name]), 4))
print("n clusters =", df["id"].nunique())''',
    interpretation_en="GEE estimates a marginal, population-average log-odds ratio. Its SEs are wider than a naive logistic regression that treats each visit as independent. It answers a different question from a subject-specific mixed model.",
    interpretation_ny="GEE imayerekeza log-odds ratio ya gulu lonse. Standard errors zake ndi zazikulu kuposa logistic regression yonamiza kuti ma visit ndi odziyimira pawokha. Imayankha funso losiyana ndi mixed model ya munthu payekha.",
    limits_en="GEE needs enough clusters for reliable SEs. It is less efficient than a correctly specified mixed model. It does not model cluster-specific random effects and is not ideal for cluster-level exposure questions.",
    limits_ny="GEE ifuna magulu okwanira kuti SE zikhale zodalirika. Si yamphamvu ngati mixed model yoyenerera. Sikhazikitsa random effects pa gulu ndipo si yabwino pa mafunso okhudza gulu lokha.",
    explanation_ny="GEE imazindikira kuti munthu yemweyo amapereka deta kangapo. Imasintha standard errors kuti zisakhale zazing'ono mwangozi, koma imayang'ana zotsatira za gulu lonse osati za munthu aliyense.",
    analogy_en="It is like surveying the same households repeatedly. You still want the city-wide average, but you must not count each household reply as fully independent evidence.",
    analogy_ny="Zili ngati kufunsa mabanja omwewo mobwerezabwereza. Mukufabe avareji ya mzinda wonse, koma simuyenera kuwerengera yankho lililonse ngati umboni wodziyimira pawokha.",
    report_en="State that GEE was used, the working correlation, number of clusters and whether effects are population-average. Report exponents with CIs if odds ratios are desired.",
    report_ny="Fotokozani kuti GEE idagwiritsidwa ntchito, working correlation, kuchuluka kwa magulu ndi kuti zotsatira ndi za gulu lonse. Nenani ma exponent ndi CI ngati ma odds ratio akufunika.",
    application_en="Estimating population-average change in repeated test positivity.",
    application_ny="Kuyerekeza kusintha kwa kuchuluka kwa zotsatira zabwino mwa gulu lonse.",
)

E(
    category="advanced",
    term="Survival analysis",
    term_ny="Kusanthula kwa nthawi mpaka chochitika",
    use_en="Use survival analysis for time-to-event outcomes, especially when some participants are censored before the event of interest is observed.",
    use_ny="Gwiritsani ntchito kusanthula kwa nthawi mpaka chochitika pamene chochitika chimatenga nthawi kuchitika, makamaka ngati ena atayika asanachitike chochitikacho.",
    assumptions_en="Time zero and the event must be defined consistently. Censoring should be independent of event risk conditional on the variables in the model. The chosen method must match the question: description, comparison or adjusted modelling.",
    assumptions_ny="Nthawi yoyambira ndi chochitika ziyenera kufotokozedwa mofanana. Kutayika kwa deta kuyenera kukhala kosagwirizana ndi chiopsezo potengera zinthu zili mu model. Njira yosankhidwa igwirizane ndi funso: kufotokoza, kuyerekeza kapena kuyimba model.",
    code=None,
    interpretation_en="No standalone code is needed for this umbrella term. The Kaplan-Meier entry estimates the event-free curve, while the Cox regression entry estimates adjusted hazard ratios from the same kind of time-to-event data.",
    interpretation_ny="Mawu akuluwa safuna code payokha. Cholemba cha Kaplan-Meier chimayerekeza mphepete yopanda chochitika, pamene cholemba cha Cox chimayerekeza ma hazard ratio osinthidwa kuchokera ku deta yamtunduwu.",
    limits_en="Ignoring censoring or treating censored participants as event-free forever biases the estimate. A survival method does not by itself establish causation, and competing events need explicit handling.",
    limits_ny="Kunyalanyaza kutayika kwa deta kapena kuona omwe atayika ngati opanda chochitika mpaka kalekale kumakondera zotsatira. Njira yopulumuka yokha sikutsimikizira causality, ndipo zochitika zopikisana zifunika kuyendetsedwa momveka.",
    explanation_ny="Survival analysis siyongotanthauza imfa. Imaphunzira nthawi kuyambira poyambira mpaka chochitika, monga kutuluka m'chipatala, kuyambiranso kwa matenda kapena kulephera kwa chida. Anthu omwe sanachitike chochitika mpaka kafukufuku utha amadziwika kuti censored.",
    analogy_en="It is like following a cohort of light bulbs until each fails, while some bulbs are still working when the study ends. Those still working do not count as failures, but they do contribute their observed working time.",
    analogy_ny="Zili ngati kutsata gulu la mababu mpaka awonongeke, pamene ena akadagwira ntchito kafukufuku akatha. Omwe akadagwira ntchito sawerengedwa kuti awonongeka, koma nthawi yawo yogwira ntchito imathandizira.",
    report_en="Define time zero, the event and censoring. Name the method used and report estimates with uncertainty and numbers at risk or events.",
    report_ny="Fotokozani nthawi yoyambira, chochitika ndi kutayika kwa deta. Tchulani njira yomwe mugwiritsa ntchito ndipo nenani zoyerekeza ndi kusatsimikizika komanso kuchuluka kwa omwe ali pachiwopsezo kapena zochitika.",
    application_en="Time from treatment start to relapse, from birth to a neonatal outcome, or from device insertion to failure.",
    application_ny="Nthawi kuchokera pachiyambi cha chithandizo mpaka matenda abwerera, kuchokera pakubadwa mpaka zotsatira za makanda, kapena kuchokera kuikidwa kwa chida mpaka chawonongeka.",
)

E(
    category="advanced",
    term="Kaplan-Meier survival estimate",
    term_ny="Kaplan-Meier survival estimate",
    use_en="Use to estimate the probability of remaining event-free over time when some participants are censored before the event occurs.",
    use_ny="Gwiritsani ntchito kuyerekeza mwayi wokhalabe popanda chochitika pakapita nthawi pamene ena adatayika asanachitike chochitika.",
    assumptions_en="Censoring is independent of event risk conditional on any modelled covariates; event times are accurately recorded; participants enter at a well-defined time zero. The unadjusted curve describes the whole group, not subgroup effects.",
    assumptions_ny="Kutayika kwa deta sikugwirizana ndi chiopsezo cha chochitika potengera zinthu zomwe zili mu model; nthawi za chochitika zalembedwa bwino; munthu aliyense ali ndi zero yomveka bwino. Mphepete yosasintha imafotokoza gulu lonse, osati zotsatira za magulu.",
    code='''import numpy as np
import pandas as pd
from statsmodels.duration.survfunc import SurvfuncRight

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112236)
n = 160
event_time = rng.exponential(scale=12, size=n)
censor_time = rng.uniform(3, 18, size=n)
duration = np.minimum(event_time, censor_time)
event = (event_time <= censor_time).astype(int)
df = pd.DataFrame({"duration": duration, "event": event})

sf = SurvfuncRight(df["duration"], df["event"])
print("participants =", len(df), "events =", int(df["event"].sum()))
for month in [3, 6, 12]:
    idx = max(0, int(np.searchsorted(sf.surv_times, month,
                                     side="right")) - 1)
    print("survival at month", month, "=",
          round(float(sf.surv_prob[idx]), 3))''',
    interpretation_en="The curve drops only at observed event times; censored participants contribute until their last known time. The printed values are the estimated proportions still event-free at 3, 6 and 12 months in this simulated cohort.",
    interpretation_ny="Mphepete imatsika pokhapo pa nthawi zomwe chochitika chinachitika; omwe atayika amathandizira mpaka nthawi yawo yomaliza yodziwika. Manambala osindikizidwa ndi gawo loyerekeza lopanda chochitika pa miyezi 3, 6 ndi 12 mu gulu lopangidwali.",
    limits_en="A curve does not adjust for confounders and comparing curves informally can be misleading. Censoring that depends on prognosis biases the estimate. Median survival may be undefined if fewer than half the participants experience an event.",
    limits_ny="Mphepete silisinthidwa ndi zinthu zosokoneza ndipo kuyerekeza ma curve mwachisawawa kungasokeretse. Kutayika kogwirizana ndi chiopsezo kumakondera kuyerekezako. Median survival ikhoza kusadziwika ngati osachepera theka la anthu akumana ndi chochitika.",
    explanation_ny="Kaplan-Meier imayesa kuti ndi gawo liti la anthu omwe akadali popanda chochitika pa nthawi iliyonse. Imalola anthu omwe atayika kutengapo mbali mpaka nthawi yomwe adaonekera komaliza.",
    analogy_en="It is like tracking how many runners are still uninjured at each mile, while allowing that some runners leave the study for reasons unrelated to injury.",
    analogy_ny="Zili ngati kuyang'ana othamanga angati omwe alibe kuvulala pa mailo iliyonse, ndikuvomereza kuti ena amachoka mu kafukufuku pazifukwa zosagwirizana ndi kuvulala.",
    report_en="Report survival probabilities at prespecified times with CIs, numbers at risk, event count and the censoring definition. Do not report a curve as a causal treatment effect.",
    report_ny="Nenani mwayi wopulumuka pa nthawi zokonzedweratu ndi CI, kuchuluka kwa omwe ali pachiwopsezo, kuchuluka kwa zochitika ndi tanthauzo la kutayika. Musanene mphepete ngati zotsatira za causality.",
    application_en="Estimating event-free survival after a defined starting time.",
    application_ny="Kuyerekeza kukhala popanda chochitika pambuyo pa poyambira pomveka.",
)

E(
    category="advanced",
    term="Cox proportional hazards regression",
    term_ny="Cox proportional hazards regression",
    use_en="Use for time-to-event outcomes when you want a hazard ratio for predictors while allowing the baseline hazard to remain unspecified.",
    use_ny="Gwiritsani ntchito pa zotsatira za nthawi mpaka chochitika pamene mukufuna hazard ratio ya zinthu zolosera popanda kufotokoza mawonekedwe a baseline hazard.",
    assumptions_en="Proportional hazards over time; independent censoring; correct event-time and status coding; linear form for continuous predictors in the log-hazard. Check proportionality rather than assuming it.",
    assumptions_ny="Kuchuluka kwa ngozi kukhala kofanana pakapita nthawi; kutayika kodziyimira pawokha; kulembedwa bwino kwa nthawi ndi status; mawonekedwe a mzere pa zinthu zopitirira mu log-hazard. Yang'anani proportionality musanaganizire.",
    code='''import numpy as np
import pandas as pd
from statsmodels.duration.hazard_regression import PHReg

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112237)
n = 180
age = rng.normal(60, 8, n)
group = rng.integers(0, 2, n)
lp = 0.035*(age-60) + 0.55*group
event_time = rng.exponential(np.exp(-lp)*12)
censor_time = rng.uniform(3, 18, n)
duration = np.minimum(event_time, censor_time)
event = (event_time <= censor_time).astype(int)
df = pd.DataFrame({"duration": duration, "event": event,
                   "age": age, "group": group})

fit = PHReg(df["duration"], df[["age", "group"]],
            status=df["event"]).fit(disp=False)
for i, name in enumerate(["age", "group"]):
    print(name, "HR =", round(float(np.exp(fit.params[i])), 3),
          "p =", round(float(fit.pvalues[i]), 4))
print("events =", int(df["event"].sum()))''',
    interpretation_en="A hazard ratio above 1 means a higher instantaneous event rate at a given time, assuming proportional hazards. It is not a risk ratio or a survival-time ratio; the hazard is a rate, not a probability.",
    interpretation_ny="Hazard ratio woposa 1 ukutanthauza kuchuluka kwa zochitika pa nthawi inayake, ngati kuchuluka kwa ngozi kuli kofanana pakapita nthawi. Si risk ratio kapena chiŵerengero cha nthawi yopulumuka; hazard ndi mtengo, osati mwayi.",
    limits_en="If hazards are not proportional, a single HR can be misleading. Cox does not estimate the baseline survival curve without extra steps. Competing risks and time-varying exposures need specialised handling.",
    limits_ny="Ngati kuchuluka kwa ngozi sikufanana pakapita nthawi, HR imodzi ikhoza kusokeretsa. Cox siyerekeza baseline survival popanda njira zina. Zochitika zopikisana ndi zinthu zosinthika pakapita nthawi zifunika njira zapadera.",
    explanation_ny="Cox imayerekeza kuti gulu lina lili ndi chiopsezo chachikulu bwanji chakumana ndi chochitika pa nthawi iliyonse. Simafuna kudziwa mawonekedwe enieni a chiopsekozo kwa nthawi yonse.",
    analogy_en="It is like comparing two groups' chances of a breakdown at any given mile of a journey, assuming one group's relative risk stays constant throughout the trip.",
    analogy_ny="Zili ngati kuyerekeza mwayi wakuti magulu awiri awonongeke pa mailo iliyonse ya ulendo, poganiza kuti kusiyana kwawo kumakhalabe kofanana pa ulendo wonse.",
    report_en="Report HRs with 95% CIs, event count, adjustment set and how proportional hazards was assessed. Avoid calling HR a probability ratio.",
    report_ny="Nenani ma HR ndi 95% CI, kuchuluka kwa zochitika, zinthu zosinthidwa ndi momwe proportionality idawunikidwira. Pewani kuyitcha HR kuti chiŵerengero cha mwayi.",
    application_en="Modelling time to an event after adjustment for age and group.",
    application_ny="Kuyerekeza nthawi mpaka chochitika mutasintha zaka ndi gulu.",
)

E(
    category="advanced",
    term="Hazard ratio",
    term_ny="Hazard ratio",
    use_en="Use a hazard ratio to summarise the relative instantaneous event rate between groups in a proportional-hazards model, usually a Cox regression.",
    use_ny="Gwiritsani ntchito hazard ratio kufotokoza kuchuluka kwa chiopsezo cha chochitika pakati pa magulu mu model ya proportional-hazards, nthawi zambiri Cox regression.",
    assumptions_en="Hazards are proportional over follow-up; censoring is independent; event status and time are coded correctly. The hazard ratio is a rate ratio, not a probability ratio.",
    assumptions_ny="Kuchuluka kwa ngozi kumafanana pa nthawi yotsatira; kutayika kwa deta kodziyimira pawokha; nthawi ndi status za chochitika zalembedwa bwino. Hazard ratio ndi chiŵerengero cha mitengo, osati cha mwayi.",
    code=None,
    interpretation_en="No standalone code is needed here. In the Cox regression entry, each hazard ratio is obtained as exp(coefficient); the sign and size of the coefficient describe the relative hazard while the baseline hazard stays unspecified.",
    interpretation_ny="Apa palibe code payokha. Mu cholemba cha Cox regression, hazard ratio iliyonse imapezeka ngati exp(coefficient); chizindikiro ndi kukula kwa coefficient zikufotokoza chiopsezo chofanana pamene baseline hazard sinafotokozedwe.",
    limits_en="If hazards cross or change over time, one hazard ratio can hide the true pattern. It is not a risk ratio, an odds ratio or a ratio of median survival times. Competing risks require different methods.",
    limits_ny="Ngati ma hazard adutsana kapena kusintha pakapita nthawi, hazard ratio imodzi ikhoza kubisa mawonekedwe enieni. Si risk ratio, odds ratio kapena chiŵerengero cha median survival. Zochitika zopikisana zifunika njira zina.",
    explanation_ny="Hazard ndi chiopsezo chachindunji chakumana ndi chochitika pa nthawi inayake, ngati munthu wafika pa nthawiyo popanda chochitika. Hazard ratio uyerekeza chiopsekochi pakati pa magulu awiri.",
    analogy_en="Imagine two cars on the same road. The hazard ratio compares their instant-by-instant risk of a breakdown, assuming that relative risk stays constant throughout the journey.",
    analogy_ny="Tangoganizani magalimoto awiri panjira imodzi. Hazard ratio uyerekeza chiopsezo chawo cha kuwonongeka pa nthawi iliyonse, poganiza kuti kusiyana kwawo kumakhalabe kofanana pa ulendo wonse.",
    report_en="Report the hazard ratio with 95% CI, the event count, the adjustment set and how proportional hazards was checked. Never call it a probability ratio.",
    report_ny="Nenani hazard ratio ndi 95% CI, kuchuluka kwa zochitika, zinthu zosinthidwa ndi momwe proportionality idayesedwera. Musayitchule kuti chiŵerengero cha mwayi.",
    application_en="Comparing time to relapse between treatment groups after adjusting for baseline prognosis.",
    application_ny="Kuyerekeza nthawi mpaka matenda abwerera pakati pa magulu a chithandizo mutasintha zinthu zoyambirira zokhudza zotsatira.",
)

E(
    category="advanced",
    term="Bootstrap confidence interval",
    term_ny="Bootstrap confidence interval",
    use_en="Use when the sampling distribution of a statistic is awkward or you want a nonparametric interval without deriving a standard error formula.",
    use_ny="Gwiritsani ntchito pamene kagawidwe ka sample ka chiwerengero kuli kovuta kapena mukufuna interval popanda kupeza formula ya standard error.",
    assumptions_en="The sample represents the population; observations are independent; resampling must respect the design, for example stratifying by group. Percentile intervals need a reasonably smooth statistic and enough resamples.",
    assumptions_ny="Sample imayimira gulu; ma observation odziyimira pawokha; kusankhanso kuyenera kulemekeza kapangidwe, monga kugawa ndi gulu. Percentile interval ifuna chiwerengero chokhazikika komanso kusankhanso kokwanira.",
    code='''import numpy as np

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112238)
control = rng.lognormal(5.0, 0.6, 60)
treated = rng.lognormal(5.2, 0.6, 55)
observed = np.median(treated) - np.median(control)
B = 5000
boot = np.empty(B)
for i in range(B):
    bc = rng.choice(control, size=len(control), replace=True)
    bt = rng.choice(treated, size=len(treated), replace=True)
    boot[i] = np.median(bt) - np.median(bc)
lo, hi = np.percentile(boot, [2.5, 97.5])
print("observed median difference =", round(float(observed), 3))
print("bootstrap 95% percentile CI =", round(float(lo), 3),
      "to", round(float(hi), 3))
print("resamples =", B)''',
    interpretation_en="The interval is formed from the middle 95% of bootstrap statistics. It describes sampling uncertainty for this statistic under resampling. It is not a Bayesian credible interval and does not fix bias from a non-representative sample.",
    interpretation_ny="Interval imapangidwa kuchokera pakati pa 95% ya ma statistic obwerezedwa. Imafotokoza kusatsimikizika kwa sample pa chiwerengerochi. Si Bayesian credible interval ndipo sikukonza kukondera kochokera ku sample yosayimira gulu.",
    limits_en="Bootstrap fails with tiny samples, rare events, strong dependence or extreme statistics such as the maximum. Percentile intervals can be biased; BCa is an alternative. Always report the resampling scheme and count.",
    limits_ny="Bootstrap yalephera ndi ma sample ang'ono, zochitika zosowa, kudalirana kwakukulu kapena ziwerengero zapadera monga mtengo wapamwamba. Percentile interval ikhoza kukondera; BCa ndi njira ina. Nenani njira yosankhanso ndi kuchuluka kwake.",
    explanation_ny="Bootstrap imatenga deta yomwe ilipo ndikuisankhanso mobwerezabwereza kuti iyonetse kuti chiwerengero chathu chingasinthike bwanji ngati tikanatenganso sample ina kuchokera ku gulu lomwelo.",
    analogy_en="It is like repeatedly drawing new handfuls from the same bag of beads to see how much the proportion of colours varies, without going back to the factory.",
    analogy_ny="Zili ngati kutenga mikono yatsopano mobwerezabwereza kuchokera m'thumba la mikanda kuti muone kuchuluka kwa mitundu kumasiyana bwanji, popanda kubwerera ku fakitale.",
    report_en="Report the statistic, observed value, CI type, number of resamples, resampling scheme and seed or reproducibility method.",
    report_ny="Nenani chiwerengero choyerekeza, mtengo wowonedwa, mtundu wa CI, kuchuluka kwa kusankhanso, njira ndi seed kapena njira yobwerezera.",
    application_en="Estimating uncertainty for a skewed biomarker median when a formula is not convenient.",
    application_ny="Kuyerekeza kusatsimikizika kwa median ya biomarker wopendekerera pamene formula si yosavuta.",
)

E(
    category="advanced",
    term="ROC curve, AUC and Youden threshold",
    term_ny="ROC curve, AUC ndi Youden threshold",
    use_en="Use when a continuous marker or model score is used to discriminate between two groups and you want to summarise discrimination and examine a candidate cut-off.",
    use_ny="Gwiritsani ntchito pamene chiwerengero chosalekeza kapena model score chikugwiritsidwa ntchito kusiyanitsa magulu awiri ndipo mukufuna kufotokoza kusiyanitsa ndi kuyang'ana malire oti mugwiritse ntchito.",
    assumptions_en="Binary reference standard; scores computed in the intended population; validation in independent data or cross-validation. The chosen threshold must reflect the relative cost of false positives and false negatives.",
    assumptions_ny="Muyezo wawiri wa reference; ma score awerengedwe mu gulu lomwe lingagwiritsidwe ntchito; kutsimikizira ndi deta yodziyimira pawokha kapena cross-validation. Malire osankhidwa ayenera kuganizira mtengo wa zolakwika zamtundu uliwonse.",
    code='''import numpy as np
from sklearn.metrics import roc_curve, auc, confusion_matrix

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112239)
y = np.r_[np.zeros(160, dtype=int), np.ones(140, dtype=int)]
score = np.r_[rng.normal(0.8, 0.5, 160), rng.normal(1.7, 0.6, 140)]

fpr, tpr, thresholds = roc_curve(y, score)
auc_value = auc(fpr, tpr)
j = tpr - fpr
best = int(np.argmax(j))
cut = thresholds[best]
pred = (score >= cut).astype(int)
tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
print("AUC =", round(float(auc_value), 3))
print("Youden J =", round(float(j[best]), 3))
print("candidate threshold =", round(float(cut), 3))
print("sensitivity =", round(tp/(tp+fn), 3),
      "specificity =", round(tn/(tn+fp), 3))
print("confusion matrix [[TN, FP], [FN, TP]] =",
      [[int(tn), int(fp)], [int(fn), int(tp)]])''',
    interpretation_en="AUC is the probability that a randomly chosen positive case scores above a randomly chosen negative case. Youden's J chooses the threshold maximising sensitivity plus specificity minus one. The optimal teaching threshold is not automatically the right clinical cut-off.",
    interpretation_ny="AUC ndi mwayi wakuti munthu wabwino asankhidwe ndi score yapamwamba kuposa munthu woipa. Youden's J imasankha malire omwe akulitsa sensitivity ndi specificity pamodzi. Malire abwino pophunzitsira si malire azachipatala okha.",
    limits_en="AUC ignores calibration and the clinical consequences of errors. A threshold tuned on the same data is optimistically biased. Spectrum bias and verification bias can make discrimination look better than it is.",
    limits_ny="AUC sinyalanyaza kulinganiza kwa zolosera ndi zotsatira za zolakwika. Malire osinthidwa pa deta yomweyo amakhala otsika mtengo kwambiri. Kusankha kwa anthu ndi kutsimikizira kungapangitse kusiyanitsa kuoneke kwabwinoko kuposa momwe kuli.",
    explanation_ny="ROC imajambula kusinthanitsa pakati pa kuzindikira matenda (sensitivity) ndi kupewa chenjezo labodza (specificity). AUC imatiuza ngati score imasiyanitsa bwino; Youden ndi imodzi mwa njira zosankha malire.",
    analogy_en="It is like a metal detector: sensitivity is how often it finds real metal, specificity is how often it stays quiet for harmless objects, and the threshold controls how beep-happy it is.",
    analogy_ny="Zili ngati chida chozindikira zitsulo: sensitivity ndi kuchuluka kwa zitsulo zenizeni zomwe chazipeza, specificity ndi kuchuluka kwa zinthu zopanda vuto zomwe chakhala chete, ndipo malire amalamulira kuchuluka kwa kubweep.",
    report_en="Report AUC with CI, the validation approach, threshold rationale, sensitivity, specificity, PPV/NPV where relevant and the confusion matrix.",
    report_ny="Nenani AUC ndi CI, njira yotsimikizira, chifukwa cha malire, sensitivity, specificity, PPV/NPV ngati zikugwirizana ndi confusion matrix.",
    application_en="Evaluating a biomarker score for classifying a binary outcome.",
    application_ny="Kuwunika score ya biomarker pogawira zotsatira za binary.",
)

E(
    category="advanced",
    term="Cross-validation for predictive models",
    term_ny="Cross-validation ya predictive models",
    use_en="Use to estimate how well a modelling pipeline generalises to new data when you cannot afford a separate large test set.",
    use_ny="Gwiritsani ntchito kuyerekeza kuti model pipeline igwira ntchito bwanji pa deta yatsopano pamene simungapeze gulu lalikulu la test.",
    assumptions_en="All preprocessing that learns from data must be inside the pipeline and fitted only on training folds. Folds should reflect the data structure; use stratified folds for imbalanced classes and grouped folds for repeated measures.",
    assumptions_ny="Njira zonse zophunzira kuchokera ku deta ziyenera kukhala mu pipeline ndipo ziyenerane kungophunzitsidwa pa magulu a training okha. Magulu ayenera kuwonetsa kapangidwe ka deta; gwiritsani ntchito stratified ngati makategori ali osalingana ndi grouped ngati pali miyeso yobwerezabwereza.",
    code='''import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import RepeatedStratifiedKFold, cross_val_score

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112240)
n = 240
x1 = rng.normal(0, 1, n)
x2 = 0.5*x1 + rng.normal(0, 1, n)
y = (0.8*x1 - 0.4*x2 + rng.normal(0, 1, n) > 0).astype(int)
df = pd.DataFrame({"x1": x1, "x2": x2, "y": y})

pipe = Pipeline([("scale", StandardScaler()),
                 ("model", LogisticRegression(max_iter=1000))])
cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=3,
                             random_state=2026112240)
scores = cross_val_score(pipe, df[["x1", "x2"]], df["y"],
                         cv=cv, scoring="roc_auc")
print("folds =", len(scores))
print("mean CV AUC =", round(float(scores.mean()), 3))
print("SD across folds =", round(float(scores.std(ddof=1)), 3))''',
    interpretation_en="The mean is the estimated performance across repeated held-out folds; the SD shows variability. Because scaling and model fitting happen inside each fold, the estimate avoids leakage from using the full dataset's information.",
    interpretation_ny="Avareji ndi kagwiridwe koyerekeza pamagulu obisidwa obwerezabwereza; SD ikuwonetsa kusiyana. Popeza scaling ndi kuyika model zimachitika mkati mwa gulu lililonse, kuyerekezako kumapewa kutulutsa zidziwitso kuchokera ku deta yonse.",
    limits_en="Cross-validation is not a substitute for an external validation cohort. Overlapping folds are not fully independent. Tuning many models on the same folds can overfit the validation procedure itself.",
    limits_ny="Cross-validation silo lowa m'malo mwa gulu lotsimikizira lakunja. Magulu ophatikizana si odziyimira pawokha kwathunthu. Kusankha ma model ambiri pa magulu omwewo kungayikitse njira yotsimikizira yokha.",
    explanation_ny="Cross-validation imagawa deta kukhala magulu, imaphunzitsa pa ena ndikuyesa pa otsala. Izi zimatsanzira kugwiritsa ntchito model pa deta yatsopano popanda kuwononga deta yoyesera.",
    analogy_en="It is like practising several mock exams with different question sets, rather than memorising one practice paper and then sitting the same paper again.",
    analogy_ny="Zili ngati kuchita mayeso oyerekeza ambiri ndi mafunso osiyanasiyana, osati kukumbukira pepala limodzi la maphunziro kenako ndikuchitanso pepala lomwelo.",
    report_en="Report the resampling scheme, number of folds and repeats, preprocessing inside the pipeline, metric with variability and any final external validation.",
    report_ny="Nenani njira yosankhanso magulu, kuchuluka kwa magulu ndi kubwereza, preprocessing mkati mwa pipeline, muyezo ndi kusiyana kwake ndi kutsimikizira kwakunja kulikonse.",
    application_en="Estimating discrimination of a predictive model before external validation.",
    application_ny="Kuyerekeza kusiyanitsa kwa model yolosera musanatsimikiziridwe ndi deta yakunja.",
)

E(
    category="advanced",
    term="Mediation analysis",
    term_ny="Kusanthula kwa mediation",
    use_en="Use when you want to ask whether part of an exposure effect operates through an intermediate variable, and you can defend the causal ordering and assumptions.",
    use_ny="Gwiritsani ntchito pamene mukufuna kufunsa kuti gawo la zotsatira za exposure limadutsa pa chinthu chapakati, ndipo mutha kuteteza dongosolo ndi mfundo za causality.",
    assumptions_en="Exposure precedes mediator, mediator precedes outcome; no unmeasured exposure-outcome confounding, mediator-outcome confounding, or exposure-induced mediator-outcome confounding; correct models. These are strong and often unrealistic outside a designed study.",
    assumptions_ny="Exposure imachitika mediator isanachitike, mediator imachitika zotsatira zisanachitike; palibe chosokoneza chosayezedwa cha exposure-zotsatira, mediator-zotsatira, kapena chosokoneza cha mediator-zotsatira choyambitsidwa ndi exposure; ma model olondola. Izi ndi mfundo zamphamvu zomwe nthawi zambiri zimakhala zovuta kukwaniritsa.",
    code='''import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112241)
n = 220
x = rng.binomial(1, 0.5, n)
c = rng.normal(0, 1, n)
m = 0.6*x + 0.3*c + rng.normal(0, 0.8, n)
y = 0.4*m + 0.3*x + 0.2*c + rng.normal(0, 0.9, n)
df = pd.DataFrame({"x": x, "m": m, "y": y, "c": c})

a = smf.ols("m ~ x + c", data=df).fit().params["x"]
b = smf.ols("y ~ m + x + c", data=df).fit().params["m"]
cp = smf.ols("y ~ x + c", data=df).fit().params["x"]
indirect = a*b
print("a path =", round(float(a), 3))
print("b path =", round(float(b), 3))
print("indirect effect a*b =", round(float(indirect), 3))
print("direct effect c-prime =", round(float(cp), 3))
print("total effect =", round(float(indirect + cp), 3))''',
    interpretation_en="The indirect component is the product of the exposure-mediator and mediator-outcome paths. The direct component is the remaining exposure association with the mediator held fixed. Their sum approximates the total effect in a linear setting.",
    interpretation_ny="Gawo losadziwika ndi kuchulukitsa kwa njira ya exposure-mediator ndi mediator-zotsatira. Gawo lolunjika ndi ubale wa exposure wotsala pamene mediator wakhazikitsidwa. Kuchuluka kwake kuli pafupi ndi zotsatira zonse mu model ya mzere.",
    limits_en="Product-of-coefficients intervals need bootstrap and are sensitive to model misspecification. Mediation is not established by a significant indirect effect alone. Causal language requires the assumptions above and a suitable design.",
    limits_ny="Ma interval a kuchulukitsa kwa coefficient amafuna bootstrap ndipo amadalira model yoyenera. Mediation sikutsimikiziridwa ndi indirect effect yofunika yokha. Mawu a causality amafuna mfundo zomwe zili pamwambapa ndi kapangidwe koyenera.",
    explanation_ny="Mediation imafunsa kuti kodi exposure imakhudza zotsatira mwachindunji kapena imadutsa pa chinthu chapakati. Mwachitsanzo, maphunziro angakhudze ndalama, ndipo ndalama zikhudze thanzi.",
    analogy_en="It is like asking whether exercise improves sleep directly or through reducing stress. You must measure stress at the right time and rule out other influences before claiming the pathway.",
    analogy_ny="Zili ngati kufunsa kuti kuchita masewera kumapangitsa kugona bwino mwachindunji kapena kudzera kuchepetsa nkhawa. Muyenera kuyeza nkhawa pa nthawi yoyenera ndikuchotsa zinthu zina musananene kuti njirayo ndi yoona.",
    report_en="State the causal ordering and assumptions, report a, b, indirect and direct effects with bootstrap CIs, and avoid causal wording if assumptions are not defensible.",
    report_ny="Fotokozani dongosolo la causality ndi mfundo zake, nenani a, b, zotsatira zosadziwika ndi zolunjika ndi bootstrap CI, ndipo pewani mawu a causality ngati mfundo sizitsimikizika.",
    application_en="Exploring whether an intervention acts through an intermediate behavioural measure.",
    application_ny="Kufufuza kuti chithandizo chikugwira ntchito kudzera pa muyeso wapakati wa khalidwe.",
)

E(
    category="advanced",
    term="Missing-data sensitivity analysis",
    term_ny="Kusanthula kwa kusowa kwa deta mosiyanasiyana",
    use_en="Use when conclusions may depend on how missing outcomes are handled, so you can show how the estimate changes under plausible assumptions rather than presenting one imputation as definitive.",
    use_ny="Gwiritsani ntchito pamene zotsatira zingadalire momwe deta yosowa yayendetsedwera, kuti muwonetse kuyerekezako kumasintha bwanji pansi pa mfundo zotheka osati kungopereka imputation imodzi ngati yotsimikizika.",
    assumptions_en="The observed-data analysis is clearly defined; delta values are transparent assumptions, not clinical facts. The approach here is a simple teaching sensitivity check, not a full multiple-imputation analysis.",
    assumptions_ny="Kusanthula kwa deta yowonedwa kufotokozedwa momveka; ma delta ndi mfundo zowonekera, osati zowona zachipatala. Njira iyi ndi yophunzitsira yosavuta, osati multiple imputation yathunthu.",
    code='''import numpy as np
import pandas as pd

# SIMULATED TEACHING DATA — not real patient records.
rng = np.random.default_rng(2026112242)
n = 200
group = rng.integers(0, 2, n)
true_value = 10 + 1.5*group + rng.normal(0, 2, n)
observed = true_value.copy()
missing_prob = np.where(group == 1, 0.30, 0.10)
missing = rng.random(n) < missing_prob
observed[missing] = np.nan
df = pd.DataFrame({"group": group, "value": observed})

def diff_after_delta(delta):
    filled = df.copy()
    for g in [0, 1]:
        median_g = filled.loc[filled["group"] == g, "value"].median()
        mask = (filled["group"] == g) & filled["value"].isna()
        filled.loc[mask, "value"] = median_g + delta*g
    return filled.loc[filled["group"] == 1, "value"].mean() - \
           filled.loc[filled["group"] == 0, "value"].mean()

complete = df.dropna()
cc_diff = complete.loc[complete["group"] == 1, "value"].mean() - \\
          complete.loc[complete["group"] == 0, "value"].mean()
print("missing rate by group =",
      df.groupby("group")["value"].apply(lambda s: round(s.isna().mean(), 3)).to_dict())
print("complete-case difference =", round(float(cc_diff), 3))
for delta in [-1.0, 0.0, 1.0]:
    print("delta scenario", delta, "difference =",
          round(float(diff_after_delta(delta)), 3))''',
    interpretation_en="The complete-case estimate uses only participants with observed outcomes. Sensitivity scenarios shift imputed values in one group to explore how strong a missing-data bias would need to be to change the conclusion. This is a stress test, not a corrected truth.",
    interpretation_ny="Kuyerekeza kwa complete-case kugwiritsa ntchito omwe ali ndi zotsatira zowonedwa okha. Zochitika za sensitivity zimasintha ma value oyikidwa mu gulu limodzi kuti ziwone kukondera kofunika kusintha chigamulo. Izi ndi kuyesa kupanikizika, osati choonadi chokonzedwa.",
    limits_en="Delta values are assumptions and must be justified from subject knowledge. This simple median fill does not preserve uncertainty or relationships among variables. Severe missingness requires principled methods such as multiple imputation or joint modelling.",
    limits_ny="Ma delta ndi mfundo zomwe ziyenera kutetezedwa ndi chidziwitso cha nkhani. Kudzaza ndi median sikusunga kusatsimikizika kapena ubale pakati pa zinthu. Kusowa kwakukulu kumafuna njira zolimba monga multiple imputation kapena joint modelling.",
    explanation_ny="Deta ikasowa, kuyankha kumodzi kungakhale kokondera. Sensitivity analysis imatiwonetsa ngati chigamulochi chingasinthe pamene tipanga mfundo zosiyanasiyana zokhudza anthu omwe sanapereke deta.",
    analogy_en="It is like checking whether a survey conclusion survives if non-respondents would have answered somewhat differently. You do not know their answers, so you test a range of reasonable possibilities.",
    analogy_ny="Zili ngati kuyang'ana kuti chigamulo cha kafukufuku chikapitilizabe ngati omwe sanayankhe akanayankha mosiyana pang'ono. Simudziwa mayankho awo, choncho muyesa zotheka zingapo zomveka.",
    report_en="Report missingness by group, the primary analysis, each delta assumption and the resulting estimates. Say explicitly that this is a sensitivity analysis.",
    report_ny="Nenani kusowa kwa deta ndi gulu, kusanthula koyamba, mfundo iliyonse ya delta ndi zotsatira zake. Fotokozani momveka kuti uwu ndi kusanthula kwa sensitivity.",
    application_en="Testing whether a group comparison depends on missing outcome assumptions.",
    application_ny="Kuyesa kuti kuyerekeza kwa magulu kumadalira mfundo za zotsatira zosowa.",
)

TERM_RENAMES: dict[str, tuple[str, str]] = {
    "Welch two-sample t-test": ("Welch’s t-test", "Welch’s t-test ya magulu awiri"),
    "Paired t-test": ("Paired samples t-test", "t-test ya deta yophatikizidwa"),
    "Mann-Whitney U test": ("Mann–Whitney U Test", "Mann–Whitney U Test"),
    "One-way ANOVA with Tukey follow-up": (
        "Analysis of Variance (ANOVA)",
        "Kusanthula kwa Kusiyana (ANOVA)",
    ),
    "Wilcoxon signed-rank test": (
        "Wilcoxon Signed-Rank Test",
        "Wilcoxon Signed-Rank Test",
    ),
    "2x2 table, risk ratio and odds ratio": ("Risk ratio", "Risk ratio"),
    "Chi-square test of independence and Cramer's V": (
        "Chi-square test",
        "Chi-square test",
    ),
    "Fisher exact test": ("Fisher’s exact test", "Fisher’s exact test"),
    "Simple linear regression": ("Linear regression", "Linear regression"),
    "Logistic regression and odds ratios": ("Logistic regression", "Logistic regression"),
    "Confounding and crude versus adjusted effect": ("Confounding", "Kusokoneza"),
    "Interaction and effect modification": ("Interaction", "Kuyanjana"),
    "Multicollinearity and VIF": ("Multicollinearity", "Multicollinearity"),
    "Pearson correlation": ("Pearson Correlation", "Pearson Correlation"),
    "Spearman rank correlation": (
        "Spearman Rank Correlation",
        "Spearman Rank Correlation",
    ),
}

ALIASES: dict[str, list[str]] = {
    "Independent samples t-test": [
        "student t test", "student's t test", "equal variance t test",
        "two sample t test", "independent t test",
    ],
    "Paired samples t-test": [
        "dependent t test", "within subject t test", "before after t test",
    ],
    "Welch’s t-test": [
        "welch t test", "welch's t-test", "unequal variance t test",
        "independent t test",
    ],
    "Chi-square test": [
        "chi square", "chi-squared", "contingency table test",
        "test of independence", "cramer v",
    ],
    "Fisher’s exact test": [
        "fisher exact", "fisher's exact test", "exact test", "small table",
    ],
    "Analysis of Variance (ANOVA)": [
        "anova", "analysis of variance", "analysis of variance (anova)",
        "one way anova", "f test", "tukey",
    ],
    "Mann–Whitney U Test": [
        "mann whitney", "mann-whitney", "mann–whitney u test",
        "wilcoxon rank sum", "rank sum test",
    ],
    "Wilcoxon Signed-Rank Test": [
        "wilcoxon signed rank", "wilcoxon signed-rank test", "signed rank",
        "paired rank test",
    ],
    "Pearson Correlation": [
        "pearson correlation", "pearson r", "linear correlation", "r",
    ],
    "Spearman Rank Correlation": [
        "spearman correlation", "spearman rho", "spearman rank",
        "rank correlation",
    ],
    "Linear regression": [
        "simple linear regression", "ols", "slope", "least squares",
    ],
    "Logistic regression": [
        "logit", "binary regression", "log odds", "adjusted odds ratio",
    ],
    "Odds ratio": ["or", "odds", "case control", "2x2 table"],
    "Risk ratio": [
        "relative risk", "rr", "cohort", "2x2 table",
    ],
    "Hazard ratio": [
        "hr", "cox", "proportional hazards", "instantaneous rate",
    ],
    "Confounding": [
        "confounder", "crude", "adjusted", "third variable",
    ],
    "Interaction": [
        "effect modification", "product term", "subgroup", "effect modifier",
    ],
    "Multicollinearity": [
        "vif", "variance inflation factor", "correlated predictors",
    ],
    "Survival analysis": [
        "time to event", "censoring", "kaplan meier", "cox regression",
    ],
}

FIELD_OVERRIDES: dict[str, dict[str, str]] = {
    "Independent samples t-test": {
        "definition_en": "Student's independent-samples t-test compares the means of two unrelated groups by dividing their mean difference by a pooled standard error. It assumes a common within-group variance.",
        "explanation_ny": "Mayesowa uyerekeza avareji a magulu awiri osiyana. 'Independent' kutanthauza kuti munthu aliyense ali mugulu limodzi lokha, kotero palibe awiriawiri ofanana pakati pa maguluwo. Umagwiritsa ntchito kufalikira kwa magulu onse kuti uone kusiyana kwa avareji kuli kwakukulu kuposa phokoso la deta.",
        "analogy_en": "Like comparing the average harvest of two separate farms: each farm contributes one yield per plot, and the question is whether the gap exceeds ordinary variation between plots.",
        "analogy_ny": "Zili ngati kuyerekeza zokolola zapakati pa mafakitale awiri osiyana: famu iliyonse imapereka zokolola kamodzi pa malo aliwonse, ndipo funso ndi kuti kusiyana kwake kuli kwakukulu kuposa kusiyana kwamba.",
        "code_explanation_en": "equal_var=True pools the two variances. ttest_ind returns the t statistic, degrees of freedom and p-value; confidence_interval() adds the plausible range for the mean difference.",
        "code_explanation_ny": "equal_var=True imaphatikiza variances ziwirizo kukhala chimodzi. ttest_ind imapereka t, degrees of freedom ndi p; confidence_interval() imawonjezera mtunda wotheka wa kusiyana kwa avareji.",
        "application_en": "Comparing mean birth weight between two independently sampled regions when their spreads are similar.",
        "application_ny": "Kuyerekeza avareji ya kulemera kwa makanda pakati pa madera awiri osiyana pamene kufalikira kwawo kuli kofanana.",
        "misconception_en": "It is not a paired test, and equal variances are an assumption rather than a guaranteed fact. A significant result does not prove that the groups differ for causal reasons.",
        "misconception_ny": "Si paired test, ndipo variances zofanana ndi mfundo yongoganizira, osati yotsimikizika. Zotsatira zofunika sizikutsimikizira kuti kusiyana kunachitika chifukwa cha chinthu chinachake.",
    },
    "Paired samples t-test": {
        "definition_en": "The paired samples t-test tests whether the mean of within-pair differences is zero. It is used when the same units are measured twice or when units are deliberately matched.",
        "explanation_ny": "Pa paired t-test, munthu aliyense amakhala control wake. Timayang'ana kusiyana pakati pa before ndi after, osati kuyerekeza magulu awiri osiyana. Izi zimachotsa kusiyana kwachilengedwe pakati pa anthu.",
        "analogy_en": "Weighing the same patient before and after treatment: the patient's usual body size cancels out, leaving the change to be studied.",
        "analogy_ny": "Kuyeza wodwala yemweyo asanalandire chithandizo ndi atalandira: kukula kwake kwamba kumachotsedwa, kotero kusintha kokha kumatsala kuti kuunikidwe.",
        "code_explanation_en": "diff stores follow_up minus baseline. ttest_rel performs the one-sample t-test on those differences; the reported mean change and CI describe the paired effect.",
        "code_explanation_ny": "diff imasunga follow_up opanda baseline. ttest_rel imachita t-test ya gulu limodzi pa kusiyana kumeneko; kusintha kwa avareji ndi CI zikufotokoza zotsatira za awiriawiri.",
        "application_en": "Assessing change in blood pressure before and after an intervention in the same participants.",
        "application_ny": "Kuwona kusintha kwa kuthamanga kwa magazi musanayambe ndi mutalandira chithandizo mwa omwewo.",
        "misconception_en": "The unit of analysis is the pair, not each separate measurement. Treating repeated observations as independent observations produces invalid standard errors.",
        "misconception_ny": "Chinthu chowunikiridwa ndi awiriwiri, osati miyeso yosiyana. Kutenga ma observation obwerezabwereza ngati odziyimira pawokha kumapanga standard errors zolakwika.",
    },
    "Welch’s t-test": {
        "definition_en": "Welch’s t-test compares the means of two independent groups without assuming equal variances. It adjusts the degrees of freedom to account for unequal spread.",
        "explanation_ny": "Welch imafunsa kuti avareji ya magulu awiri odziyimira pawokha ndi yosiyana kwambiri poyerekeza ndi kufalikira kwa deta. Simafuna kuti magulu awiriwo akhale ndi variances zofanana, choncho ndi yotetezeka pa deta yeniyeni.",
        "analogy_en": "Comparing two classrooms with different spreads of marks: Welch adjusts for the fact that one class may be much more variable than the other.",
        "analogy_ny": "Kuyerekeza makalasi awiri omwe mphambu zawo zimafalikira mosiyanasiyana: Welch imaganizira kuti kalasi imodzi ikhoza kukhala yosiyana kwambiri ndi inzake.",
        "code_explanation_en": "equal_var=False switches off pooling. SciPy computes Welch’s adjusted df and a confidence interval for the mean difference using the two separate variances.",
        "code_explanation_ny": "equal_var=False imaletsa kuphatikiza variances. SciPy imawerengera df yosinthidwa ya Welch ndi CI ya kusiyana kwa avareji pogwiritsa ntchito variances ziwiri zosiyana.",
        "application_en": "Comparing mean birth weight between infants from two independently sampled regions with unequal spread.",
        "application_ny": "Kuyerekeza avareji ya kulemera kwa makanda ochokera kumadera awiri osiyana omwe kufalikira kwawo kusiyana.",
        "misconception_en": "Welch compares means, not whole distributions. Two groups can differ in shape or spread while having similar means, and the test does not adjust for confounding.",
        "misconception_ny": "Welch uyerekeza avareji, osati kufalikira kwathunthu. Magulu awiri angasiyane mawonekedwe kapena kufalikira koma avareji yawo ikhale yofanana, ndipo mayesowo suchotsa zinthu zosokoneza.",
    },
    "Chi-square test": {
        "definition_en": "A chi-square test of independence assesses whether two categorical variables are associated by comparing observed contingency-table counts with counts expected under independence.",
        "explanation_ny": "Chi-square imafanizira zomwe tawona ndi zomwe tikadayembekezera ngati palibe ubale pakati pa makategori. Ngati kusiyana kwake kuli kwakukulu, p imachepa ndipo tikukayikira kuti palibe ubale. Cramer's V imatiuza mphamvu ya ubalewo.",
        "analogy_en": "Checking whether drink choices differ by age group more than random mixing would produce. Chi-square flags the pattern; Cramer's V says how pronounced it is.",
        "analogy_ny": "Kuyang'ana kuti zakumwa zosankhidwa zimasiyana m'magulu azaka kuposa momwe kusakaniza mwachisawawa kungapangire. Chi-square imazindikira mawonekedwe; Cramer's V imatiuza kuti ndi yamphamvu bwanji.",
        "code_explanation_en": "crosstab() builds the table. chi2_contingency() returns the statistic, p-value, degrees of freedom and expected counts. Cramer's V is computed from chi-square and sample size as a 0–1 strength measure.",
        "code_explanation_ny": "crosstab() imapanga table. chi2_contingency() imapereka chi-square, p, degrees of freedom ndi kuchuluka koyembekezeka. Cramer's V imawerengedwa kuchokera ku chi-square ndi kuchuluka kwa deta ngati muyezo wa 0–1.",
        "application_en": "Testing whether malaria positivity category differs by specimen type.",
        "application_ny": "Kuyesa kuti gulu la malungo limasiyana ndi mtundu wa zitsanzo.",
        "misconception_en": "A small p-value does not prove causation or describe strength. Expected counts that are too small make the asymptotic p unreliable; use an exact method when needed.",
        "misconception_ny": "p yochepa sikutsimikizira causality kapena kufotokoza mphamvu ya ubale. Kuchuluka koyembekezeka kochepa kumapangitsa p kusadalirika; gwiritsani ntchito njira yeniyeni ngati kuli koyenera.",
    },
    "Fisher’s exact test": {
        "definition_en": "Fisher’s exact test computes an exact p-value for association in a 2x2 table by enumerating tables with the same margins, rather than relying on a large-sample approximation.",
        "explanation_ny": "Ngati makutu ali ochepa, chi-square si yodalirika. Fisher imawerengera mwayi wa table yotere mwachindunji potengera makutu omwe alipo, osati kugwiritsa ntchito mawonekedwe a belu.",
        "analogy_en": "Instead of approximating with a bell curve, Fisher enumerates all possible arrangements of a small deck and counts how extreme yours is.",
        "analogy_ny": "M'malo kugwiritsa ntchito kuyerekeza kwa mawonekedwe a belu, Fisher imawerenga makonzedwe onse a makadi ochepa ndikuwerengera kuti anu ndi otani.",
        "code_explanation_en": "fisher_exact(table) uses the fixed margins to enumerate arrangements and returns the conditional odds ratio and two-sided p-value. The raw table is printed because sparse odds ratios can be unstable.",
        "code_explanation_ny": "fisher_exact(table) imagwiritsa ntchito m'mphepete lokhazikika kuwerenga makonzedwe onse ndikupereka conditional odds ratio ndi p ya mbali ziwiri. Table yoyambirira imasindikizidwa chifukwa ma odds ratio a makutu ochepa angakhale osakhazikika.",
        "application_en": "Analysing a rare outcome in a small pilot study.",
        "application_ny": "Kusanthula zotsatira zosowa mu kafukufuku wawung'ono wa pilot.",
        "misconception_en": "Exact does not mean automatically better for large tables. It gives an unadjusted association and can be conservative; a zero cell can make the odds ratio infinite.",
        "misconception_ny": "Kukhala 'exact' sikutanthauza kuti kuli bwino nthawi zonse pa table yayikulu. Sipereka zotsatira zosinthidwa ndipo ikhoza kukhala yodziletsa kwambiri; selo la zero lingapangitse odds ratio kukhala yopanda malire.",
    },
    "Analysis of Variance (ANOVA)": {
        "definition_en": "A statistical method used to compare the means of three or more independent groups.",
        "explanation_ny": "ANOVA imathandiza kufufuza ngati pali kusiyana kwakukulu pakati pa ma average a magulu atatu kapena kuposerapo.",
        "analogy_en": "Comparing the average examination scores of students from three different classes.",
        "analogy_ny": "Kuyerekeza avareji a mphambu za mayeso za ophunzira ochokera m'makalasi atatu osiyana.",
        "code_explanation_en": "scipy.stats.f_oneway(group1, group2, group3) runs the one-way ANOVA F test. F is the ratio of the between-group mean square to the within-group mean square, and the p-value tests the null that all means are equal.",
        "code_explanation_ny": "scipy.stats.f_oneway(group1, group2, group3) imayesa ANOVA ya magulu atatu. F ndi chiŵerengero cha mean square yapakati pa magulu ndi ya mkati mwa magulu; p imayesa lingaliro loti avareji zonse zili zofanana.",
        "application_en": "Testing whether mean birth weight differs across standard, low-dose and high-dose care groups.",
        "application_ny": "Kuyesa kuti avareji ya kulemera kwa makanda imasiyana pakati pa chisamaliro cha standard, low-dose ndi high-dose.",
        "misconception_en": "A significant ANOVA result does not tell us exactly which groups differ. Post-hoc comparisons may be needed.",
        "misconception_ny": "Zotsatira za ANOVA zofunika siziuza momveka kuti magulu ati akusiyana. Pangafunike mayeso otsatira a post-hoc kuti adziwe.",
    },
    "Mann–Whitney U Test": {
        "definition_en": "A non-parametric test for comparing two independent groups using the ranks of their observations.",
        "explanation_ny": "Mayesowa amafananitsa magulu awiri osadalirana pogwiritsa ntchito malo amene ma observations awo ali nawo akasanjidwa kuyambira pa ochepa kufika pa ambiri.",
        "analogy_en": "Comparing the rankings of two groups rather than comparing their raw averages.",
        "analogy_ny": "Kuyerekeza masanjidwe a magulu awiri m'malo moyerekeza avareji awo osasinthidwa.",
        "code_explanation_en": "scipy.stats.mannwhitneyu(group1, group2) ranks the pooled observations and returns U with a two-sided p-value. The rank-biserial effect describes how often a group1 value exceeds a group2 value.",
        "code_explanation_ny": "scipy.stats.mannwhitneyu(group1, group2) imasintha ma value onse kukhala ma rank ndikupereka U ndi p ya mbali ziwiri. Rank-biserial imafotokoza kuchuluka komwe mtengo wa group1 umaposa wa group2.",
        "application_en": "Comparing ordinal pain scores or skewed biomarker concentrations between two independent groups.",
        "application_ny": "Kuyerekeza masanjidwe a ululu kapena kuchuluka kwa biomarker kopendekerera pakati pa magulu awiri odziyimira pawokha.",
        "misconception_en": "It is not automatically a test of differences in medians; its interpretation depends on the distributions.",
        "misconception_ny": "Si mayeso wa kusiyana kwa medians nthawi zonse; kutanthauzira kwake kumadalira mawonekedwe a kufalikira kwa deta.",
    },
    "Wilcoxon Signed-Rank Test": {
        "definition_en": "A non-parametric test for comparing two related measurements.",
        "explanation_ny": "Mayesowa amafananitsa miyeso iwiri yokhudzana, monga kulemera kwa mwana asanalandire chithandizo ndi pambuyo pake, pogwiritsa ntchito kusiyana ndi ma rank ake.",
        "analogy_en": "Examining how each participant's measurement changes rather than treating the two groups as unrelated.",
        "analogy_ny": "Kuyang'ana mmene muyeso wa munthu aliyense umasinthira, osati kuona magulu awiri ngati osagwirizana.",
        "code_explanation_en": "scipy.stats.wilcoxon(before, after) ranks the absolute paired differences and keeps their signs. W and p test whether positive and negative ranks are balanced; the median change shows the typical direction.",
        "code_explanation_ny": "scipy.stats.wilcoxon(before, after) imasankha kukula kwa kusiyana kwa awiriawiri ndikusunga zizindikiro. W ndi p zimayesa kuti ma rank abwino ndi oyipa ali oyenerana; kusintha kwa median kukusonyeza njira yamba.",
        "application_en": "Analysing before-after symptom scores when the differences are skewed.",
        "application_ny": "Kusanthula masanjidwe a zizindikiro musanayambe ndi mutalandira chithandizo pamene kusiyana kuli kopendekerera.",
        "misconception_en": "It is not suitable for two independent groups.",
        "misconception_ny": "Si yoyenera magulu awiri odziyimira pawokha; pamafunika awiriawiri kapena muyeso wobwerezabwereza pa chinthu chimodzi.",
    },
    "Pearson Correlation": {
        "definition_en": "Measures the strength and direction of a linear relationship between two continuous variables.",
        "explanation_ny": "Pearson correlation imasonyeza mmene variables ziwiri zimayendera limodzi pa ubale wa mzere wowongoka (linear relationship), komanso mphamvu ndi direction ya ubalewo.",
        "analogy_en": "Examining whether birth weight tends to increase as gestational age increases.",
        "analogy_ny": "Kuyang'ana kuti kulemera kwa mwana kumakonda kuwonjezeka pamene msinkhu wa mimba ukukwera.",
        "code_explanation_en": "scipy.stats.pearsonr(gestational_age, birth_weight) returns r, its p-value and a 95% confidence interval. r ranges from -1 to 1; r squared is shared variance in a simple linear model, not a causal measure.",
        "code_explanation_ny": "scipy.stats.pearsonr(gestational_age, birth_weight) imapereka r, p ndi 95% CI. r ili pakati pa -1 ndi 1; r squared ndi gawo la kusiyana lomwe limagawidwa mu model yosavuta, osati muyezo wa causality.",
        "application_en": "Exploring whether birth weight rises with gestational age in a cohort before fitting a regression model.",
        "application_ny": "Kufufuza kuti kulemera kwa makanda kumakwera ndi msinkhu wa mimba mu gulu la kafukufuku musanayike regression.",
        "misconception_en": "Correlation does not establish causation.",
        "misconception_ny": "Ubale (correlation) sikutsimikizira kuti chinthu chimodzi chinayambitsa chinacho (causation).",
    },
    "Spearman Rank Correlation": {
        "definition_en": "Measures the strength and direction of a monotonic relationship using ranked observations.",
        "explanation_ny": "Spearman correlation imagwiritsa ntchito ma rank a observations kuti ifufuze ngati variable imodzi imakonda kukwera kapena kutsika pamene ina ikusintha.",
        "analogy_en": "Comparing participants' positions in two rankings rather than their actual numerical measurements.",
        "analogy_ny": "Kuyerekeza malo a omwe atengapo mbali mu mindandanda iwiri ya masanjidwe, osati miyeso yao yeniyeni.",
        "code_explanation_en": "scipy.stats.spearmanr(variable1, variable2) computes rho from the ranks of the two variables. The Fisher-style z interval is approximate and is less reliable with many ties or small samples.",
        "code_explanation_ny": "scipy.stats.spearmanr(variable1, variable2) imawerengera rho kuchokera ku ma rank a zinthu ziwirizo. Interval ya Fisher z ndi yongoyerekeza ndipo si yodalirika ngati ma value ofanana ndi ambiri kapena deta ili yochepa.",
        "application_en": "Associating an ordinal adherence score with a skewed biomarker.",
        "application_ny": "Kugwirizanitsa masanjidwe a kumvera malangizo ndi biomarker wopendekerera.",
        "misconception_en": "Spearman correlation does not require a linear relationship, but it still does not prove causation.",
        "misconception_ny": "Spearman correlation safuna ubale wa mzere wowongoka, koma sikutsimikizirabe kuti chinthu chimodzi chinayambitsa chinacho.",
    },
    "Linear regression": {
        "definition_en": "Linear regression models the mean of a continuous outcome as a linear function of one or more predictors. A coefficient estimates the expected change in the outcome for a one-unit change in its predictor, holding other terms fixed.",
        "explanation_ny": "Linear regression imajambula mzere wabwino kwambiri wodutsa pa deta. Slope imatiuza kuti zotsatira zikusintha bwanji pamene chinthu cholosera chikuwonjezeka, pamene zinthu zina zakhazikitsidwa.",
        "analogy_en": "Fitting a straight edge to a scatter of points: the slope tells you how much the line rises for each step sideways.",
        "analogy_ny": "Kuyika mzere wowongoka pamfundo zambiri: slope imatiuza kuti mzerewo ukukwera bwanji pa sitepe iliyonse yopita mbali.",
        "code_explanation_en": "ols() fits the straight-line model. The slope, its confidence interval and p-value describe the predictor association; R squared describes the proportion of outcome variance explained.",
        "code_explanation_ny": "ols() imayika model ya mzere wowongoka. Slope, CI ndi p zikufotokoza ubale wa predictor; R squared ikufotokoza gawo la kusiyana kwa zotsatira lofotokozedwa.",
        "application_en": "Estimating the expected change in birth weight associated with gestational age.",
        "application_ny": "Kuyerekeza kusintha koyembekezeka kwa kulemera kwa makanda mogwirizana ndi msinkhu wa mimba.",
        "misconception_en": "Association is not causation. Extrapolation beyond the observed predictor range is unsafe, and a significant slope can still be small. Residual diagnostics matter.",
        "misconception_ny": "Ubale si causality. Kuyerekeza kunja kwa mtundu wa predictor wowonedwa n'kotetezeka, ndipo slope yofunika ikhoza kukhala yaying'ono. Macheke a residual ndi ofunika.",
    },
    "Logistic regression": {
        "definition_en": "Logistic regression models the probability of a binary outcome by fitting a linear model to the log-odds. Exponentiating a coefficient gives an odds ratio for a one-unit predictor increase.",
        "explanation_ny": "Logistic regression imagwira ntchito ndi mwayi wa chochitika cha binary. M'malo moyerekeza kusiyana kwa manambala, imayerekeza kuti ma odds achulukana kangati zinthu zina zili zofanana.",
        "analogy_en": "If a treatment changes the odds from 1 in 9 to 2 in 9, the odds ratio is 2, but the risk itself did not double. Odds and probability are different scales.",
        "analogy_ny": "Ngati chithandizo chasintha ma odds kuchokera 1 mwa 9 kufika 2 mwa 9, odds ratio ndi 2, koma mwayiwo sunawirikizeke. Ma odds ndi probability zili pa miyezo yosiyana.",
        "code_explanation_en": "logit() fits the log-odds model. np.exp(coefficient) converts each coefficient to an adjusted odds ratio; np.exp(conf_int()) converts its interval to the same scale.",
        "code_explanation_ny": "logit() imayika model ya log-odds. np.exp(coefficient) imasintha coefficient kukhala odds ratio wosinthidwa; np.exp(conf_int()) imasintha interval yake ku muyezo womwewo.",
        "application_en": "Modelling the odds of a neonatal outcome after exposure adjustment.",
        "application_ny": "Kuyerekeza ma odds a zotsatira za makanda pambuyo posintha zinthu zosokoneza.",
        "misconception_en": "An odds ratio is not a risk ratio, especially for common outcomes. Separation produces huge coefficients and invalid p-values; model estimates are associations unless the design supports causality.",
        "misconception_ny": "Odds ratio si risk ratio, makamaka ngati zochitika zili zofala. Kulekanitsa kumapanga coefficient zazikulu ndi p zosadalirika; zotsatira za model ndi ubale pokhapokha kapangidwe kathandizira causality.",
    },
    "Odds ratio": {
        "definition_en": "An odds ratio is the ratio of the odds of an event in one group to the odds in another. Odds are event count divided by non-event count, so the measure is not the same as a risk ratio.",
        "explanation_ny": "Odds ratio uyerekeza ma odds, osati mwayi weniweni. Ngati gulu limodzi lili ndi ma odds apamwamba kawiri, izi sizitanthauza kuti mwayi wochitika unawirikizeka, makamaka ngati chochitikacho chili chofala.",
        "analogy_en": "Risk is the fraction of a class that passes; odds are passers divided by non-passers. An odds ratio compares pass-to-fail ratios, not pass fractions.",
        "analogy_ny": "Risk ndi gawo la kalasi lomwe ladutsa; ma odds ndi odutsa ogawidwa ndi osadutsa. Odds ratio uyerekeza chiŵerengerocho, osati magawo a odutsa.",
        "code_explanation_en": "Table2x2(table) treats rows as exposure groups and columns as event/no event. riskratio and oddsratio_confint() return the two different effect measures from the same counts.",
        "code_explanation_ny": "Table2x2(table) imatenga mizere ngati magulu a exposure ndi mizati ngati chochitika/chosachitika. riskratio ndi oddsratio_confint() zimapereka miyezo iwiri yosiyana kuchokera ku makutu omwewo.",
        "application_en": "Summarising an exposure-outcome association in a case-control study or reporting an adjusted logistic regression coefficient.",
        "application_ny": "Kufotokoza ubale wa exposure ndi zotsatira mu kafukufuku wa case-control kapena kunena coefficient ya logistic regression wosinthidwa.",
        "misconception_en": "Do not call an odds ratio 'times more likely' for a common outcome. Crude odds ratios do not adjust for confounding, and sparse cells give unstable estimates.",
        "misconception_ny": "Musatchule odds ratio kuti 'katheŵa kuchuluka mwayi' ngati chochitika chili chofala. Odds ratio yosakonzedwa suchotsa zosokoneza, ndipo makutu ochepa amapanga kuyerekeza kosakhazikika.",
    },
    "Risk ratio": {
        "definition_en": "A risk ratio, or relative risk, is the probability of an event in one group divided by the probability in another. It is a direct comparison of event risks over a defined time window.",
        "explanation_ny": "Risk ratio uyerekeza mwayi weniweni wa chochitika m'magulu awiri. Ngati RR ili 2, chochitikacho chimachitika kawiri pafupipafupi m'gulu loyamba pa nthawi yofotokozedwa, osati kuti ma odds anakwera kawiri.",
        "analogy_en": "Risk is the fraction of a group that crosses a finish line; a risk ratio compares those fractions directly.",
        "analogy_ny": "Risk ndi gawo la gulu lomwe ladutsa mzere womaliza; risk ratio uyerekeza magawo amenewo mwachindunji.",
        "code_explanation_en": "Table2x2(table) computes riskratio from the event probability in each row. riskratio_confint() returns its interval; odds ratio is printed beside it to highlight the distinction.",
        "code_explanation_ny": "Table2x2(table) imawerengera riskratio kuchokera ku mwayi wa chochitika mu mzere uliwonse. riskratio_confint() imapereka interval; odds ratio imasindikizidwa pafupi kusonyeza kusiyana.",
        "application_en": "Comparing event risk between exposed and unexposed groups in a cohort with a fixed follow-up window.",
        "application_ny": "Kuyerekeza chiopsezo cha chochitika pakati pa gulu lowonekera ndi losawonekera mu kafukufuku wa cohort ndi nthawi yotsatira yokhazikika.",
        "misconception_en": "A case-control study usually cannot estimate a risk ratio directly because group sizes are fixed by sampling. A crude risk ratio also does not adjust for confounding.",
        "misconception_ny": "Kafukufuku wa case-control nthawi zambiri sungathe kuyerekeza risk ratio mwachindunji chifukua kuchuluka kwa magulu kumakhazikitsidwa ndi kusankha. Risk ratio yosakonzedwa suchotsanso zosokoneza.",
    },
    "Hazard ratio": {
        "definition_en": "A hazard ratio is the ratio of two instantaneous event rates under a proportional-hazards model. It is usually obtained as exp(coefficient) from a Cox regression.",
        "explanation_ny": "Hazard ndi chiopsezo chachindunji chakumana ndi chochitika pa nthawi inayake, ngati munthu wafika pa nthawiyo popanda chochitika. Hazard ratio uyerekeza chiopsekochi pakati pa magulu awiri.",
        "analogy_en": "Two cars on the same road: the hazard ratio compares their instant-by-instant risk of a breakdown, assuming that relative risk stays constant throughout the journey.",
        "analogy_ny": "Magalimoto awiri panjira imodzi: hazard ratio uyerekeza chiopsezo chawo cha kuwonongeka pa nthawi iliyonse, poganiza kuti kusiyana kwawo kumakhalabe kofanana pa ulendo wonse.",
        "code_explanation_en": "No standalone code is needed for this definition. In the Cox regression entry, exp(coefficient) produces each hazard ratio while the baseline hazard remains unspecified.",
        "code_explanation_ny": "Apa palibe code payokha. Mu cholemba cha Cox regression, exp(coefficient) imapereka hazard ratio iliyonse pamene baseline hazard sinafotokozedwe.",
        "application_en": "Comparing time to relapse between treatment groups after adjusting for baseline prognosis.",
        "application_ny": "Kuyerekeza nthawi mpaka matenda abwerera pakati pa magulu a chithandizo mutasintha zinthu zoyambirira zokhudza zotsatira.",
        "misconception_en": "A hazard ratio is not a risk ratio, odds ratio or ratio of median survival times. If hazards change over time, one summary ratio can be misleading.",
        "misconception_ny": "Hazard ratio si risk ratio, odds ratio kapena chiŵerengero cha median survival. Ngati ma hazard asintha pakapita nthawi, chiŵerengero chimodzi chikhoza kusokeretsa.",
    },
    "Confounding": {
        "definition_en": "Confounding occurs when a third variable is associated with the exposure and independently affects the outcome, causing the crude exposure-outcome association to be distorted.",
        "explanation_ny": "Kusokoneza kumachitika ngati chinthu chachitatu chikugwirizana ndi exposure ndi zotsatira. Mwachitsanzo, zaka zingapangitse munthu kukhala ndi exposure komanso kukhala pachiwopsezocho, kotero kusiyana kowonedwa kungakhale kwa zaka osati kwa exposure.",
        "analogy_en": "Ice cream sales and drowning both rise in summer. Summer is the confounder; banning ice cream would not prevent drowning.",
        "analogy_ny": "Kugulitsa ayisikilimu ndi kumira m'madzi zimawonjezeka chilimwe. Chilimwe ndi chosokoneza; kuletsa ayisikilimu sikungaletse kumira.",
        "code_explanation_en": "The crude logistic model contains exposure only; the adjusted model adds age. Comparing the two odds ratios shows how much of the crude association was explained by age in this simulated cohort.",
        "code_explanation_ny": "Model ya logistic yosakonzedwa ili ndi exposure yokha; yosinthidwa imawonjezera zaka. Kuyerekeza ma odds ratio awiri kukusonyeza kuchuluka kwa ubale wosakonzedwa womwe unafotokozedwa ndi zaka mu gulu lopangidwali.",
        "application_en": "Comparing crude and age-adjusted exposure effects in an observational cohort.",
        "application_ny": "Kuyerekeza zotsatira za exposure zosakonzedwa ndi zosinthidwa ndi zaka mu gulu la observational.",
        "misconception_en": "Not every third variable is a confounder. Adjusting for a collider or mediator can create bias, and unmeasured confounders cannot be fixed by a model. Choose variables from subject knowledge or a causal diagram.",
        "misconception_ny": "Si chinthu chilichonse chachitatu chomwe ndi chosokoneza. Kusintha collider kapena mediator kungabweretse kukondera, ndipo chosokoneza chosayezedwa sizingakonzedwe ndi model. Sankhani zinthu pogwiritsa ntchito chidziwitso kapena chithunzi cha causality.",
    },
    "Interaction": {
        "definition_en": "Interaction, or effect modification, means that the effect of one predictor on the outcome differs according to the level of another predictor. It is modelled with a product term in addition to main effects.",
        "explanation_ny": "Interaction imafunsa kuti mankhwala amagwira ntchito mofanana kwa aliyense kapena ayi. Mwachitsanzo, zotsatira zake zikhoza kukhala zazikulu kwa amuna kuposa azimayi, kotero avareji imodzi imabisala kusiyana kofunika.",
        "analogy_en": "A fertiliser that works well in wet soil but not in dry soil. The average effect hides an important interaction with soil condition.",
        "analogy_ny": "Feteleza wogwira bwino m'nthaka yonyowa koma osagwira m'nthaka youma. Zotsatira za avareji zimabisala kuyanjana kwakukulu ndi mtunda wa nthaka.",
        "code_explanation_en": "The model formula group * sex adds both main effects and the group:sex product term. Its p-value tests whether the group effect differs by sex; exp() converts coefficients and sums to stratum-specific odds ratios.",
        "code_explanation_ny": "Fomula group * sex imawonjezera main effects ndi product term group:sex. p yake imayesa kuti zotsatira za gulu zimasiyana ndi jenda; exp() imasintha coefficient ndi kuchuluka kwawo kukhala odds ratio za gulu lililonse.",
        "application_en": "Testing whether an intervention effect differs by participant group or sex.",
        "application_ny": "Kuyesa kuti zotsatira za chithandizo zimasiyana ndi gulu la omwe atengapo mbali kapena jenda.",
        "misconception_en": "A non-significant interaction does not prove effects are identical. Interaction is scale-dependent, and mining many subgroups without a prespecified hypothesis produces false positives.",
        "misconception_ny": "Kusowa kwa interaction yofunika sikutsimikizira kuti zotsatira zili zofanana. Kuyanjana kumadalira muyezo wogwiritsidwa ntchito, ndipo kusaka magulu ambiri popanda lingaliro lokonzedweratu kumapanga zopezeka zabodza.",
    },
    "Multicollinearity": {
        "definition_en": "Multicollinearity is a situation in which predictors in a regression model are highly linearly related, making individual coefficients unstable and their standard errors large even when predictions may be adequate.",
        "explanation_ny": "Ngati zinthu zolosera ziwiri zikunena pafupifupi zinthu zomwezo, model imavutika kudziwa kuti ndi iti yomwe ikuyambitsa kusintha. VIF imatiuza kuti vutolo lili bwanji.",
        "analogy_en": "Two witnesses who give identical testimony. Their agreement does not provide two independent pieces of evidence, and the court cannot tell which one drives the conclusion.",
        "analogy_ny": "Mboni ziwiri zopereka umboni wofanana. Kuvomerezana kwawo sikupereka umboni wawiri wodziyimira pawokha, ndipo khoti silikudziwa kuti ndani akuyendetsa chigamulo.",
        "code_explanation_en": "variance_inflation_factor() regresses each predictor on the others. A high VIF means that predictor is largely redundant, so its individual coefficient is poorly determined.",
        "code_explanation_ny": "variance_inflation_factor() imayika predictor iliyonse pa ena. VIF yapamwamba imatanthauza kuti predictor imodzi imafotokozedwa kwambiri ndi ena, kotero coefficient yake payokha siyodalirika.",
        "application_en": "Checking correlated predictors before interpreting an adjusted regression model.",
        "application_ny": "Kuyang'ana zinthu zolosera zogwirizana musanatanthauzire model ya regression yosinthidwa.",
        "misconception_en": "High VIF does not bias predictions or invalidate the overall model. Dropping a confounder merely to lower VIF can introduce bias; centring helps polynomial terms, not genuine redundancy.",
        "misconception_ny": "VIF yapamwamba siyikondera zolosera kapena kuwononga model yonse. Kuchotsa chinthu chosokoneza kungoti VIF itsike kungabweretse kukondera; kuyika pakati kumathandiza polynomial, osati kusiyana kwachilengedwe.",
    },
    "Survival analysis": {
        "definition_en": "Survival analysis is the set of methods for analysing time-to-event data, where the outcome is the time until an event and some subjects may be censored before that event is observed.",
        "explanation_ny": "Survival analysis siyongotanthauza imfa. Imaphunzira nthawi kuyambira poyambira mpaka chochitika, monga kutuluka m'chipatala kapena kuyambiranso kwa matenda. Anthu omwe sanachitike chochitika mpaka kafukufuku utha amadziwika kuti censored.",
        "analogy_en": "Following light bulbs until each fails, while some bulbs are still working when the study ends. Those still working do not count as failures, but their observed working time still contributes.",
        "analogy_ny": "Kutsata mababu mpaka awonongeke, pamene ena akadagwira ntchito kafukufuku akatha. Omwe akadagwira ntchito sawerengedwa kuti awonongeka, koma nthawi yawo yogwira ntchito imathandizira.",
        "code_explanation_en": "No standalone code is needed for this umbrella term. The Kaplan-Meier entry uses SurvfuncRight for the event-free curve; the Cox entry uses PHReg for adjusted hazard ratios.",
        "code_explanation_ny": "Mawu akuluwa safuna code payokha. Cholemba cha Kaplan-Meier chimagwiritsa ntchito SurvfuncRight pa mphepete yopanda chochitika; cholemba cha Cox chimagwiritsa ntchito PHReg pa ma hazard ratio osinthidwa.",
        "application_en": "Time from treatment start to relapse, from birth to a neonatal outcome, or from device insertion to failure.",
        "application_ny": "Nthawi kuchokera pachiyambi cha chithandizo mpaka matenda abwerera, kuchokera pakubadwa mpaka zotsatira za makanda, kapena kuchokera kuikidwa kwa chida mpaka chawonongeka.",
        "misconception_en": "Ignoring censoring, or treating censored subjects as event-free forever, biases the estimate. A survival curve alone is not a causal effect, and competing events need explicit methods.",
        "misconception_ny": "Kunyalanyaza kutayika kwa deta, kapena kuona omwe atayika ngati opanda chochitika mpaka kalekale, kumakondera zotsatira. Mphepete yokha si zotsatira za causality, ndipo zochitika zopikisana zifunika njira zapadera.",
    },
}


def first_sentences(text: str, count: int) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:count])


def normalise_entry(entry: dict[str, Any]) -> dict[str, Any]:
    old_term = entry["term"]
    term, term_ny = TERM_RENAMES.get(old_term, (old_term, entry["term_ny"]))
    override = FIELD_OVERRIDES.get(term, {})
    explanation_ny = override.get(
        "explanation_ny",
        first_sentences(entry["explanation_ny"] + " " + entry["use_ny"], 3),
    )
    aliases = ALIASES.get(term, [])
    return {
        "category": entry["category"],
        "term": term,
        "term_ny": term_ny,
        "definition_en": override.get(
            "definition_en", first_sentences(entry["use_en"], 2)
        ),
        "explanation_ny": explanation_ny,
        "analogy_en": override.get("analogy_en", entry["analogy_en"]),
        "analogy_ny": override.get("analogy_ny", entry["analogy_ny"]),
        "code": entry["code"],
        "output": entry["output"],
        "code_explanation_en": override.get(
            "code_explanation_en",
            first_sentences(entry["interpretation_en"], 2),
        ),
        "code_explanation_ny": override.get(
            "code_explanation_ny",
            first_sentences(entry["interpretation_ny"], 2),
        ),
        "application_en": override.get(
            "application_en", first_sentences(entry["application_en"], 1)
        ),
        "application_ny": override.get(
            "application_ny", first_sentences(entry["application_ny"], 1)
        ),
        "misconception_en": override.get(
            "misconception_en", first_sentences(entry["limits_en"], 2)
        ),
        "misconception_ny": override.get(
            "misconception_ny", first_sentences(entry["limits_ny"], 2)
        ),
        "aliases": aliases,
    }


def field_pair(label_en: str, label_ny: str, en: str, ny: str) -> str:
    return f"""<p class="field"><span class="field-label"><span class="lang en">{html.escape(label_en)}</span><span class="lang ny">{html.escape(label_ny)}</span></span>
<span class="lang en">{html.escape(en)}</span><span class="lang ny">{html.escape(ny)}</span></p>"""


def field_lang(lang: str, label: str, text: str) -> str:
    return f"""<p class="field lang {lang}"><span class="field-label">{html.escape(label)}</span>{html.escape(text)}</p>"""


def render_entry(entry: dict[str, Any], index: int) -> str:
    category_title = next(
        (title for key, title, _ in CATEGORIES if key == entry["category"]), ""
    )
    values = [
        entry["term"], entry["term_ny"], entry["definition_en"],
        entry["explanation_ny"], entry["analogy_en"], entry["analogy_ny"],
        entry["code_explanation_en"], entry["code_explanation_ny"],
        entry["application_en"], entry["application_ny"],
        entry["misconception_en"], entry["misconception_ny"],
        *entry["aliases"], category_title,
    ]
    searchable = re.sub(r"\s+", " ", " ".join(str(v) for v in values)).lower()
    code_html = ""
    if entry["code"] and entry["output"]:
        code_id = f"code-{index}"
        code_html = f"""  <div class="code-wrap">
    <div class="code-head"><span class="lang en">Python example</span><span class="lang ny">Chitsanzo cha Python</span><button class="copy-btn" type="button" data-target="{code_id}" aria-label="Copy example code">⧉ <span class="lang en">Copy</span><span class="lang ny">Koperani</span></button></div>
    <pre id="{code_id}"><code>{html.escape(entry['code'])}</code></pre>
  </div>
  <div class="output-wrap">
    <div class="out-head"><span class="lang en">Actual output from the fixed-seed example</span><span class="lang ny">Zotsatira zenizeni za chitsanzo chokhala ndi seed yokhazikika</span></div>
    <pre>{html.escape(entry['output'])}</pre>
  </div>
"""
    return f"""<article class="entry" data-category="{html.escape(entry['category'])}" data-search="{html.escape(searchable, quote=True)}">
  <div class="entry-head">
    <div>
      <div class="eyebrow">{html.escape(category_title)}</div>
      <h3 id="term-{index}"><span class="lang en">{html.escape(entry['term'])}</span><span class="lang ny">{html.escape(entry['term_ny'])}</span></h3>
    </div>
    <span class="num">{index:02d}</span>
  </div>
  {field_lang('en', 'English definition', entry['definition_en'])}
  {field_lang('ny', 'Kufotokozera mu Chichewa', entry['explanation_ny'])}
  {field_pair('Analogy', 'Fanizo', entry['analogy_en'], entry['analogy_ny'])}
{code_html}  {field_pair('Code explanation', 'Kufotokozera kwa code', entry['code_explanation_en'], entry['code_explanation_ny'])}
  {field_pair('Practical application', 'Kugwiritsa ntchito', entry['application_en'], entry['application_ny'])}
  {field_pair('Common misconception', 'Chikhulupiriro chofala cholakwika', entry['misconception_en'], entry['misconception_ny'])}
</article>"""


def render_page() -> str:
    glossary_entries = [normalise_entry(entry) for entry in ENTRIES]
    counts = {key: 0 for key, _, _ in CATEGORIES}
    for entry in glossary_entries:
        counts[entry["category"]] += 1
    nav = "\n".join(
        f'<a href="#cat-{key}"><span class="lang en">{html.escape(title)}</span><span class="lang ny">{html.escape(ny_title)}</span><b>{counts[key]}</b></a>'
        for key, title, ny_title in CATEGORIES
    )
    body_parts: list[str] = []
    index_offset = 0
    for category_key, _, _ in CATEGORIES:
        category_entries = [e for e in glossary_entries if e["category"] == category_key]
        cards = "\n".join(
            render_entry(entry, index_offset + i + 1)
            for i, entry in enumerate(category_entries)
        )
        index_offset += len(category_entries)
        category_title = next(t for k, t, _ in CATEGORIES if k == category_key)
        category_ny = next(t for k, _, t in CATEGORIES if k == category_key)
        body_parts.append(
            f'<section class="category" id="cat-{category_key}"><h2><span class="lang en">{html.escape(category_title)}</span><span class="lang ny">{html.escape(category_ny)}</span></h2>{cards}</section>'
        )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="dark">
<title>Statistical tests and modelling — bilingual glossary</title>
<style>
:root{{--bg:#070b12;--panel:#101827;--panel2:#0d1420;--line:#26344a;--ink:#eef4ff;--muted:#aebbd0;--gold:#f5c451;--gold2:#ffe19a;--teal:#6ee7d2;--danger:#ff9e9e}}
*{{box-sizing:border-box}}
html,body{{margin:0;min-height:100%;background:var(--bg);color:var(--ink);font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;line-height:1.55}}
body{{padding-bottom:env(safe-area-inset-bottom)}}
a{{color:var(--gold2)}}
.topbar{{position:sticky;top:0;z-index:20;background:rgba(7,11,18,.96);backdrop-filter:blur(10px);border-bottom:1px solid var(--line);padding:12px max(16px,env(safe-area-inset-left)) 12px max(16px,env(safe-area-inset-right));display:flex;gap:12px;align-items:center;flex-wrap:wrap}}
.brand{{font-weight:800;letter-spacing:.02em;color:var(--gold);margin-right:auto}}
.brand small{{display:block;color:var(--muted);font-weight:500;letter-spacing:0}}
.controls{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
input,select,button{{font:inherit}}
input[type=search]{{width:min(300px,60vw);padding:9px 12px;border-radius:10px;border:1px solid var(--line);background:#0a111c;color:var(--ink)}}
select,button{{padding:9px 11px;border-radius:10px;border:1px solid var(--line);background:#0a111c;color:var(--ink)}}
button{{cursor:pointer}}
button:hover,select:hover{{border-color:var(--gold)}}
main{{max-width:1180px;margin:0 auto;padding:28px 18px 72px}}
.hero{{border:1px solid var(--line);border-radius:18px;background:linear-gradient(135deg,#101827,#0b1220);padding:24px;margin-bottom:22px}}
.hero h1{{margin:0 0 8px;font-size:clamp(1.5rem,3vw,2.3rem);line-height:1.2}}
.hero p{{margin:6px 0;color:var(--muted)}}
.badge{{display:inline-block;border:1px solid #6b5420;background:#2a220f;color:var(--gold2);border-radius:999px;padding:4px 10px;font-size:.8rem;margin-bottom:10px}}
.categories{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-bottom:26px}}
.categories a{{display:flex;justify-content:space-between;gap:8px;text-decoration:none;color:var(--ink);border:1px solid var(--line);background:var(--panel2);border-radius:12px;padding:11px 13px}}
.categories a:hover{{border-color:var(--gold);background:#131e2f}}
.categories b{{color:var(--gold)}}
.category{{margin:34px 0 46px;scroll-margin-top:90px}}
.category>h2{{font-size:1.4rem;border-bottom:1px solid var(--line);padding-bottom:9px;margin:0 0 16px;color:var(--gold2)}}
.entry{{border:1px solid var(--line);border-radius:16px;background:var(--panel);padding:18px;margin:0 0 16px;box-shadow:0 10px 30px rgba(0,0,0,.2)}}
.entry-head{{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;border-bottom:1px solid var(--line);padding-bottom:12px;margin-bottom:12px}}
.eyebrow{{color:var(--teal);font-size:.76rem;text-transform:uppercase;letter-spacing:.08em;margin-bottom:3px}}
.entry h3{{margin:0;font-size:1.15rem;line-height:1.35}}
.num{{font-variant-numeric:tabular-nums;color:var(--gold);font-weight:800;opacity:.85}}
.field{{margin:9px 0}}
.field-label{{display:block;color:var(--gold);font-weight:700;font-size:.85rem;text-transform:uppercase;letter-spacing:.04em;margin-bottom:2px}}
.lang{{display:block}}
body[data-lang="en"] .lang.ny,body[data-lang="ny"] .lang.en{{display:none}}
.code-wrap,.output-wrap{{border:1px solid var(--line);border-radius:12px;overflow:hidden;margin:12px 0;background:#060a11}}
.code-head,.out-head{{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:8px 12px;background:#111c2b;color:var(--muted);font-size:.82rem;border-bottom:1px solid var(--line)}}
.copy-btn{{padding:4px 9px;font-size:.8rem;color:var(--gold2);background:#0a111c}}
pre{{margin:0;padding:13px;overflow:auto;white-space:pre-wrap;word-break:break-word;font-family:ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace;font-size:.86rem;line-height:1.5}}
.output-wrap pre{{color:#c9f7e8;background:#07120f}}
.empty{{display:none;border:1px dashed var(--line);border-radius:14px;padding:24px;text-align:center;color:var(--muted)}}
.result-count{{color:var(--muted);font-size:.85rem;margin:8px 0 0;font-variant-numeric:tabular-nums}}
footer{{border-top:1px solid var(--line);color:var(--muted);font-size:.85rem;padding-top:18px;margin-top:34px}}
@media(max-width:640px){{main{{padding:18px 12px 60px}}.topbar{{padding:10px 12px}}.brand{{width:100%;margin-right:0}}input[type=search]{{width:100%}}.controls{{width:100%}}.entry{{padding:14px}}}}
@media print{{.topbar,.categories,.copy-btn{{display:none}}body{{background:#fff;color:#111}}.entry,.hero{{background:#fff;color:#111;border-color:#aaa}}.field-label,.eyebrow{{color:#5b4600}}.output-wrap pre{{background:#f5f5f5;color:#111}}}}
</style>
</head>
<body data-lang="both">
<header class="topbar">
  <div class="brand">Statistical tests and modelling<small>Bilingual glossary · fixed-seed simulated teaching data</small></div>
  <div class="controls">
    <input id="search" type="search" placeholder="Search terms / Sakani mawu" aria-label="Search statistical entries">
    <select id="lang" aria-label="Choose language">
      <option value="both">English + Chichewa</option>
      <option value="en">English only</option>
      <option value="ny">Chichewa only</option>
    </select>
    <button id="back" type="button">Back</button>
  </div>
</header>
<main>
  <section class="hero">
    <span class="badge">{BUILD}</span>
    <p id="result-count" class="result-count" aria-live="polite" aria-atomic="true"><span class="lang en">Showing 46 of 46 terms</span><span class="lang ny">Kuwonetsa mawu 46 pa 46</span></p>
    <h1><span class="lang en">Statistical tests and modelling glossary</span><span class="lang ny">Mndandanda wa mawu a ziwerengero ndi kuyerekeza</span></h1>
    <p class="lang en">This is a searchable glossary, not a textbook. Each term has an English definition, a natural Chichewa explanation, an analogy, a short Python example where applicable, a code explanation, a practical use and a common misconception. Conceptual umbrella terms may omit code.</p>
    <p class="lang ny">Uwu ndi mndandanda wa mawu wosakika, osati buku la phunziro. Mawu aliwonse ali ndi tanthauzo mu Chingerezi, kufotokozera kwachilengedwe mu Chichewa, fanizo, chitsanzo chachifupi cha Python ngati chikugwiritsidwa ntchito, kufotokozera kwa code, kagwiritsidwe ntchito ndi chikhulupiriro chofala cholakwika. Mawu akulu a lingaliro angakhale opanda code.</p>
    <p class="lang en">This resource is additive. It does not change the Chapter 0 setup lab, the command interpreter allow-list, CRARA, the install gate, navigation order or any earlier build behavior.</p>
    <p class="lang ny">Chothandizira ichi ndi chowonjezera chokha. Sichisintha labu ya Chapter 0, mndandanda wa malamulo ovomerezeka, CRARA, chipata cha install, dongosolo la navigation kapena machitidwe a ma build akale.</p>
  </section>
  <nav class="categories" aria-label="Statistical categories">{nav}</nav>
  <div id="entries">
{chr(10).join(body_parts)}
  </div>
  <div class="empty" id="empty"><span class="lang en">No entries match that search.</span><span class="lang ny">Palibe zolemba zogwirizana ndi sakani.</span></div>
  <footer>
    <span class="lang en">Generated by <code>scripts/build_statistical_glossary.py</code>. Code-bearing cards were executed at build time with fixed-seed simulated teaching data; conceptual cards are intentionally code-free. Outputs are not biomedical findings. Free/open-source Python packages only.</span>
    <span class="lang ny">Zopangidwa ndi <code>scripts/build_statistical_glossary.py</code>. Makadi okhala ndi code anayendetsedwa popanga tsamba ndi seed yokhazikika ndi deta yophunzitsira; makadi a lingaliro alibe code mwadala. Zotsatira sizomwe anapeza pa odwala. Mapaketi a Python aulere ndi otseguka okha.</span>
  </footer>
</main>
<script>
(function(){{
  var body=document.body;
  var search=document.getElementById('search');
  var lang=document.getElementById('lang');
  var empty=document.getElementById('empty');
  var count=document.getElementById('result-count');
  var countEn=count.querySelector('.lang.en');
  var countNy=count.querySelector('.lang.ny');
  var entries=Array.prototype.slice.call(document.querySelectorAll('.entry'));
  function apply(){{
    var q=(search.value||'').trim().toLowerCase();
    var terms=q? q.split(/\\s+/):[];
    var shown=0;
    entries.forEach(function(card){{
      var hay=card.getAttribute('data-search')||'';
      var ok=terms.every(function(t){{return hay.indexOf(t)!==-1;}});
      card.style.display=ok?'':'none';
      if(ok) shown++;
    }});
    document.querySelectorAll('.category').forEach(function(sec){{
      var any=Array.prototype.slice.call(sec.querySelectorAll('.entry')).some(function(c){{return c.style.display!=='none';}});
      sec.style.display=any?'':'none';
    }});
    empty.style.display=shown?'none':'block';
    countEn.textContent='Showing '+shown+' of '+entries.length+' terms';
    countNy.textContent='Kuwonetsa mawu '+shown+' pa '+entries.length;
  }}
  search.addEventListener('input',apply);
  lang.addEventListener('change',function(){{body.setAttribute('data-lang',lang.value);}});
  apply();
  document.addEventListener('click',function(ev){{
    var btn=ev.target.closest('.copy-btn');
    if(!btn) return;
    var target=document.getElementById(btn.getAttribute('data-target'));
    if(!target) return;
    var text=target.innerText||target.textContent;
    function done(){{var old=btn.innerHTML;btn.textContent='✓';setTimeout(function(){{btn.innerHTML=old;}},1200);}}
    if(navigator.clipboard&&navigator.clipboard.writeText){{
      navigator.clipboard.writeText(text).then(done,function(){{}});
    }} else {{
      var ta=document.createElement('textarea');ta.value=text;document.body.appendChild(ta);ta.select();document.execCommand('copy');document.body.removeChild(ta);done();
    }}
  }});
  document.getElementById('back').addEventListener('click',function(){{
    if(history.length>1) history.back(); else location.href='/';
  }});
}})();
</script>
</body>
</html>
"""


def main() -> None:
    glossary_entries = [normalise_entry(entry) for entry in ENTRIES]
    if len(glossary_entries) != 46:
        raise SystemExit(f"Expected 46 entries, found {len(glossary_entries)}")

    requested = [
        "Independent samples t-test",
        "Paired samples t-test",
        "Welch’s t-test",
        "Chi-square test",
        "Fisher’s exact test",
        "Analysis of Variance (ANOVA)",
        "Mann–Whitney U Test",
        "Wilcoxon Signed-Rank Test",
        "Pearson Correlation",
        "Spearman Rank Correlation",
        "Linear regression",
        "Logistic regression",
        "Odds ratio",
        "Risk ratio",
        "Hazard ratio",
        "Confounding",
        "Interaction",
        "Multicollinearity",
        "Survival analysis",
    ]
    terms = {entry["term"] for entry in glossary_entries}
    missing = [term for term in requested if term not in terms]
    if missing:
        raise SystemExit(f"Missing requested glossary terms: {missing}")
    leftover_grouped = [term for term in TERM_RENAMES if term in terms]
    if leftover_grouped:
        raise SystemExit(f"Grouped lesson titles remain: {leftover_grouped}")
    if sum(1 for entry in glossary_entries if not entry["code"]) < 2:
        raise SystemExit("At least two conceptual entries should be code-free")

    required_fields = (
        "term", "term_ny", "definition_en", "explanation_ny", "analogy_en",
        "analogy_ny", "code_explanation_en", "code_explanation_ny",
        "application_en", "application_ny", "misconception_en",
        "misconception_ny",
    )
    for entry in glossary_entries:
        for field in required_fields:
            if not str(entry[field]).strip():
                raise SystemExit(f"{entry['term']}: empty field {field}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render_page(), encoding="utf-8")
    code_count = sum(1 for entry in glossary_entries if entry["code"])
    print(
        f"Wrote {OUTPUT.name} with {len(glossary_entries)} glossary "
        f"entries ({code_count} with executed code) ({BUILD})."
    )


if __name__ == "__main__":
    main()

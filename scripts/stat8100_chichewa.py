"""Natural Chichewa (Chinyanja) translation layer for the STAT 8100 companion.

The module translates student guidance, worked reports, reporting templates,
audit facts and interface labels while preserving numbers, percentages,
identifiers, file names, placeholders, p/CI abbreviations and mathematical
notation exactly as they appear in the English source.

Terminology follows the established teaching glossary: risk ratio, odds ratio,
confidence interval, chi-square, Kaplan-Meier, hazard ratio and standard error
are retained, while explanatory prose uses natural Chichewa (for example
``kubadwa msanga``, ``kulemera kochepa pakubadwa`` and ``kuchepa kwa magazi``).
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

from build_stat8100_practical import AUDIT_FACTS
from stat8100_guides import GUIDES, REPORTING_TEMPLATES
from stat8100_reporting import work_report, worked_template_examples


# ---------------------------------------------------------------------------
# Interface strings
# ---------------------------------------------------------------------------

UI: dict[str, str] = {
    "STAT 8100 Practical Companion": "STAT 8100 Practical Companion (Chichewa)",
    "STAT 8100 Biostatistics &amp; Epidemiology Practical Companion":
        "STAT 8100 — Biostatistics &amp; Epidemiology Practical Companion (Chichewa)",
    "STAT 8100 Biostatistics & Epidemiology Practical Companion":
        "STAT 8100 — Biostatistics & Epidemiology Practical Companion (Chichewa)",
    "STAT 8100 — Biostatistics and Epidemiology Practical Companion":
        "STAT 8100 — Biostatistics ndi Epidemiology Practical Companion (Chichewa)",
    "STAT 8100 Biostatistics and Epidemiology Practical Companion":
        "STAT 8100 — Biostatistics ndi Epidemiology Practical Companion (Chichewa)",
    "Practical index": "Mndandanda wa practical",
    "Search all questions, code and guidance…": "Sakani mafunso, code ndi malangizo onse…",
    "Search practical": "Sakani practical",
    "All": "Zonse",
    "Code": "Code",
    "Calculation": "Kuwerengera",
    "Mixed": "Kusakaniza",
    "Conceptual": "Lingaliro",
    "Interpretation": "Kutanthauzira",
    "Reporting": "Kunena zotsatira",
    "0 of 28 subquestions marked complete.":
        "0 mwa 28 mafunso ang'onoang'ono zalembedwa kuti zamalizidwa.",
    "{n} of {cards.length} subquestions marked complete.":
        "{n} mwa {cards.length} mafunso ang'onoang'ono alembedwa kuti amalizidwa.",
    "{shown} of {cards.length} subquestions visible.":
        "{shown} mwa {cards.length} mafunso ang'onoang'ono akuoneka.",
    "Companion theme": "Mutu wa companion",
    "White": "Woyera",
    "Dark": "Wakuda",
    "Download the notebook": "Tsitsani notebook",
    "Download verified results": "Tsitsani zotsatira zotsimikizidwa",
    "Jump to full navigation table": "Lumphani ku tebulo lonse la navigation",
    "Before running question code:": "Musanathamangitse code ya funso:",
    "Reusable setup cell": "Selo la setup logwiritsidwanso ntchito",
    "Data audit completed before implementation": "Kuwunika kwa deta kwachitika musanapange zonse",
    "Source fingerprints": "Zizindikiro za chiyambi cha deta",
    "Required navigation table — every subquestion":
        "Tebulo lofunika la navigation — funso lililonse laling'ono",
    "Question/Subquestion": "Funso/Funso laling'ono",
    "Practical requirement": "Zofunikira pa practical",
    "Task classification": "Gulu la ntchito",
    "Jupyter action": "Zochita mu Jupyter",
    "Output to inspect": "Zotuluka zoyenera kuyang'ana",
    "Interpretation guidance": "Malangizo otanthauzira",
    "Reporting guidance": "Malangizo onena zotsatira",
    "Code required:": "Code yofunikira:",
    "Jupyter action:": "Zochita mu Jupyter:",
    "Learning guide — the ten questions answered":
        "Kalozera wophunzirira — mafunso khumi ayankhidwa",
    "Verified output from the executed notebook":
        "Zotuluka zotsimikizidwa kuchokera ku notebook yothamangitsidwa",
    "Worked report — verified from the executed notebook":
        "Lipoti lathunthu — lotsimikizidwa kuchokera ku notebook yothamangitsidwa",
    "Verified source:": "Chiyambi chotsimikizidwa:",
    "Teaching note:": "Cholembo cha mphunzitsi:",
    "Common mistakes": "Zolakwika zofala",
    "Compare with the reporting templates": "Yerekezerani ndi ma template onena zotsatira",
    "Notebook section {qid}": "Gawo la notebook {qid}",
    "Mark complete": "Lemba kuti lamalizidwa",
    "Completed ✓": "Lamalizidwa ✓",
    "Copy setup + cell": "Koperani setup + selo",
    "Copy cell only": "Koperani selo yokha",
    "Copy code": "Koperani code",
    "Copied ✓": "Koperedwa ✓",
    "Copy failed": "Kukopera kwalephera",
    "Run setup first:": "Thamangani setup poyamba:",
    "No code cell is required for this task.": "Ntchitoyi safuna selo ya code.",
    "Reporting templates with worked verified examples":
        "Ma template onena zotsatira ndi zitsanzo zotsimikizidwa",
    "Each generic pattern keeps placeholders as a reusable sentence frame. "
    "Directly underneath, a worked example fills every placeholder with values "
    "from the executed notebook; the same examples also appear in the individual "
    "question cards.":
        "Chitsanzo chilichonse chachikulu chimasunga ma placeholder ngati mawonekedwe "
        "a chiganizo ogwiritsidwanso ntchito. Pansi pake, chitsanzo chathunthu "
        "chimadzaza ma placeholder onse ndi makhalidwe ochokera ku notebook "
        "yothamangitsidwa; zitsanzo zomwezi zimawonekeranso m'makhadi a mafunso.",
    "Limitations": "Zolephera",
    "STAT 8100 companion · generated from the same verified code cells as the "
    "delivered Jupyter notebook.":
        "Companion wa STAT 8100 · wopangidwa kuchokera ku ma code cell omwewo "
        "otsimikizidwa ndi notebook ya Jupyter yoperekedwa.",
    "Chichewa version": "Mtundu wa Chichewa",
    "English version": "Mtundu wa Chingelezi",
    "Code cell": "Selo la code",
    "· requires Reusable setup": "· imafuna Selo la setup logwiritsidwanso ntchito",
    "the reusable setup cell creates": "selo la setup logwiritsidwanso ntchito limapanga",
    ". “Copy setup + cell” includes it automatically.":
        ". “Koperani setup + selo” limaphatikizapo izi zokha.",
    "Variable": "Zinthu",
    "Scale": "Sikelo",
    "Why": "Chifukwa",
    "Verified evidence": "Umboni wotsimikizidwa",
    "Reusable pattern": "Chitsanzo chogwiritsidwanso ntchito",
    "reproduction.": "kubwerezabwereza.",
}


# ---------------------------------------------------------------------------
# Exact learning-point translations (part 1)
# ---------------------------------------------------------------------------

LEARNING_OVERRIDES: dict[str, str] = {
    "What is being asked? Estimate two unconditional probabilities using the supplied outcome flags.":
        "Kodi funso likufunsa chiyani? Yerekezerani mwayi wiwiri wopanda mikhalidwe pogwiritsa ntchito zizindikiro za zotsatira zomwe zaperekedwa.",
    "Statistical concept: A sample proportion estimates a population probability; it is not a theoretical probability.":
        "Lingaliro la ziwerengero: Gawo la sample limayerekeza mwayi wa gulu lonse; si mwayi wongolingalira.",
    "Do you need to write code? Yes — one short calculation cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yaifupi yowerengera.",
    "What to do in Jupyter: Run Q1(a), then compare the counts with the denominators.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q1(a), kenaka yerekezerani kuchuluka ndi ma denominator.",
    "Code to use: Use the verified Q1(a) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q1(a) yotsimikizidwa.",
    "Output to inspect: A table with event count, denominator and sample proportion for each outcome.":
        "Zotuluka zoyenera kuyang'ana: Tebulo lokhala ndi kuchuluka kwa chochitika, denominator ndi gawo la sample pa chotsatira chilichonse.",
    "Important values or observations: 47/400 preterm and 43/400 low birth weight in the actual file.":
        "Makhalidwe kapena zowoneratu zofunika: 47/400 kubadwa msanga ndi 43/400 kulemera kochepa pakubadwa m'fayilo yeniyeni.",
    "How to interpret it: These are observed sample proportions from simulated teaching data, not known population truths.":
        "Momwe mungatanthauzire: Izi ndi magawo a sample owonedwa kuchokera ku deta yofananizidwa, osati zowona zodziwika za gulu lonse.",
    "What to report: State the numerator, denominator and resulting proportion for each event.":
        "Zoyenera kunena mu lipoti: Nenani numerator, denominator ndi gawo lomwe lapangidwa pa chochitika chilichonse.",
    "Common mistakes to avoid: Do not use 382 as the denominator here; preterm and low_bw are complete for all 400 records.":
        "Zolakwika zofunika kupewa: Musagwiritse ntchito 382 ngati denominator apa; preterm ndi low_bw zili zathunthu pa zolemba zonse 400.",

    "What is being asked? Compare low-birth-weight risk in preterm and term babies and judge whether the events look independent.":
        "Kodi funso likufunsa chiyani? Yerekezerani mwayi wa kulemera kochepa pakubadwa mwa makanda obadwa msanga ndi obadwa pa nthawi, ndipo muwone ngati zochitikazo zikuwoneka zodziyimira pawokha.",
    "Statistical concept: Conditional probability restricts the denominator to a stratum; independence requires the conditional probability to equal the marginal probability.":
        "Lingaliro la ziwerengero: Mwayi wapamikhalidwe umachepetsa denominator kukhala gulu limodzi; kudziyimira pawokha kumafuna kuti mwayi wapamikhalidwe ufanane ndi mwayi wamba.",
    "Do you need to write code? Yes — one calculation cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yowerengera.",
    "What to do in Jupyter: Run Q1(b), then read the contingency table and conditional proportions.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q1(b), kenaka werengani tebulo la contingency ndi magawo apamikhalidwe.",
    "Code to use: Use the verified Q1(b) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q1(b) yotsimikizidwa.",
    "Output to inspect: Stratum counts, denominators, conditional probabilities, risk difference and risk ratio.":
        "Zotuluka zoyenera kuyang'ana: Kuchuluka kwa magulu, ma denominator, mwayi wapamikhalidwe, kusiyana kwa mwayi wachochitika ndi risk ratio.",
    "Important values or observations: P(low_bw | preterm) versus P(low_bw | term) and the marginal P(low_bw).":
        "Makhalidwe kapena zowoneratu zofunika: P(low_bw | preterm) poyerekeza ndi P(low_bw | term) komanso P(low_bw) wamba.",
    "How to interpret it: Large differences suggest dependence; similar values are consistent with independence but do not prove it.":
        "Momwe mungatanthauzire: Kusiyana kwakukulu kukusonyeza kugwirizana; makhalidwe ofanana akugwirizana ndi kudziyimira pawokha koma sikutsimikizira.",
    "What to report: Report both conditional probabilities and describe the direction and size of the difference.":
        "Zoyenera kunena mu lipoti: Nenani mwayi wonse wapamikhalidwe ndipo fotokozani komwe kusiyana kukupita komanso kukula kwake.",
    "Common mistakes to avoid: Never declare independence solely because a test is non-significant, and never infer causation.":
        "Zolakwika zofunika kupewa: Musanene kuti zinthu zodziyimira pawokha chifukwa chabe mayeso sanapeze kusiyana, ndipo musanene kuti chinachake chinayambitsa china.",

    "What is being asked? Identify the correct measurement scale for five variables.":
        "Kodi funso likufunsa chiyani? Dziwani sikelo yoyezera yoyenera ya zinthu zisanu zosiyanasiyana.",
    "Statistical concept: Nominal categories have no order; ordinal categories have order; counts are discrete; measurements such as BMI and birthweight are continuous.":
        "Lingaliro la ziwerengero: Magulu a nominal alibe dongosolo; magulu a ordinal ali ndi dongosolo; kuchuluka ndi discrete; miyeso monga BMI ndi kulemera kwa mwana pakubadwa ndi continuous.",
    "Do you need to write code? No — this is conceptual.":
        "Kodi muyenera kulemba code? Ayi — iyi ndi funso la lingaliro.",
    "What to do in Jupyter: Read the concise classification table and explain each choice in your own words.":
        "Zoyenera kuchita mu Jupyter: Werengani tebulo lofupika la magulu ndipo fotokozani chisankho chilichonse ndi mawonekedwe anu.",
    "Code to use: No code is needed; use the table in the practical.":
        "Code yoyenera kugwiritsa ntchito: Palibe code yofunikira; gwiritsani ntchito tebulo lomwe lili mu practical.",
    "Output to inspect: A five-row table with variable, scale and justification.":
        "Zotuluka zoyenera kuyang'ana: Tebulo la mizere isanu lokhala ndi zinthu, sikelo ndi chifukwa.",
    "Important values or observations: education is ordinal (None < Primary < Secondary+); anc_visits is a count; bmi and birthweight are continuous.":
        "Makhalidwe kapena zowoneratu zofunika: education ndi ordinal (None < Primary < Secondary+); anc_visits ndi kuchuluka; bmi ndi kulemera kwa mwana pakubadwa ndi continuous.",
    "How to interpret it: The scale determines which summaries and plots are meaningful.":
        "Momwe mungatanthauzire: Sikelo imatsimikizira kuti ndi chidule ndi ma plot ati omwe ali oyenera.",
    "What to report: Report the scale and a one-sentence justification for each variable.":
        "Zoyenera kunena mu lipoti: Nenani sikelo ndi chifukwa cha chiganizo chimodzi pa chinthu chilichonse.",
    "Common mistakes to avoid: Do not call facility_type ordinal, and do not treat anc_visits as continuous merely because it is numeric.":
        "Zolakwika zofunika kupewa: Musanene kuti facility_type ndi ordinal, ndipo musachite anc_visits ngati continuous chifukwa chabe ili ndi manambala.",

    "What is being asked? Produce a transparent descriptive summary for five continuous variables.":
        "Kodi funso likufunsa chiyani? Pangani chidule chomveka cha zinthu zisanu zoyezera mosalekeza.",
    "Statistical concept: Mean and SD describe centre and spread; median and IQR are robust; missingness changes the effective sample size.":
        "Lingaliro la ziwerengero: Avareji ndi SD zikufotokoza pakati ndi kufalikira; median ndi IQR sakhudzidwa mosavuta; kusowa kwa deta kumasintha kukula kwa sample yogwiritsidwa ntchito.",
    "Do you need to write code? Yes — one reusable summary loop.":
        "Kodi muyenera kulemba code? Inde — lupu imodzi yobwerezabwereza yopanga chidule.",
    "What to do in Jupyter: Run Q2(b) and note which variables have fewer non-missing observations.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q2(b) ndipo lembani zinthu zomwe zili ndi zowoneratu zochepa zomwe zilipo.",
    "Code to use: Use the verified Q2(b) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q2(b) yotsimikizidwa.",
    "Output to inspect: A table with n non-missing, n missing, mean, SD, median and IQR.":
        "Zotuluka zoyenera kuyang'ana: Tebulo lokhala ndi n yomwe ilipo, n yosowa, avareji, SD, median ndi IQR.",
    "Important values or observations: bmi has 10 missing; hb has 18 missing; age, gest_age and birthweight have 400 observations.":
        "Makhalidwe kapena zowoneratu zofunika: bmi ili ndi 10 zosowa; hb ili ndi 18 zosowa; age, gest_age ndi kulemera kwa mwana pakubadwa zili ndi zowoneratu 400.",
    "How to interpret it: Do not pretend every summary used the same 400 women.":
        "Momwe mungatanthauzire: Musaganize kuti chidule chilichonse chinagwiritsa ntchito amayi 400 omwewo.",
    "What to report: Report each variable's n alongside its summary statistics.":
        "Zoyenera kunena mu lipoti: Nenani n ya chinthu chilichonse pamodzi ndi chidule chake.",
    "Common mistakes to avoid: Dropping missing values silently or reporting one common sample size for all variables.":
        "Zolakwika zofunika kupewa: Kuchotsa makhalidwe osowa popanda kuwuza, kapena kunena kukula kwa sample kumodzi kwa zinthu zonse.",

    "What is being asked? Assess shape, symmetry, outliers and normal approximation for two variables.":
        "Kodi funso likufunsa chiyani? Unikani mawonekedwe, kufanana, ma outlier ndi kuyerekeza kwa normal pa zinthu ziwiri.",
    "Statistical concept: Histograms, KDE curves, skewness and mean-versus-median comparisons describe distributional shape.":
        "Lingaliro la ziwerengero: Ma histogramu, ma curve a KDE, kupendekera ndi kuyerekeza avareji ndi median zikufotokoza mawonekedwe a kugawa.",
    "Do you need to write code? Yes — one plotting cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yopanga ma plot.",
    "What to do in Jupyter: Run Q2(c) and look at each histogram, mean line, median line and skewness value.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q2(c) ndipo yang'anani histogramu iliyonse, mzere wa avareji, mzere wa median ndi mtengo wa kupendekera.",
    "Code to use: Use the verified Q2(c) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q2(c) yotsimikizidwa.",
    "Output to inspect: Two distribution plots plus skewness, mean, median and IQR-outlier counts.":
        "Zotuluka zoyenera kuyang'ana: Ma plot awiri a kugawa kuphatikizapo kupendekera, avareji, median ndi kuchuluka kwa ma outlier a IQR.",
    "Important values or observations: Gest_age has a left tail from preterm births; birthweight has a few low and high IQR outliers.":
        "Makhalidwe kapena zowoneratu zofunika: Gest_age ili ndi mchira wakumanzere chifukwa cha kubadwa kwa preterm; kulemera kwa mwana pakubadwa kuli ndi ma outlier a IQR ochepa kumunsi ndi kumwamba.",
    "How to interpret it: Approximate normality is a judgement, not a binary fact from one plot.":
        "Momwe mungatanthauzire: Kufanana ndi normal ndiko kulingalira kwa munthu, osati chinthu chotsimikizika ndi plot imodzi.",
    "What to report: Describe shape, centre, spread and outliers before choosing later methods.":
        "Zoyenera kunena mu lipoti: Fotokozani mawonekedwe, pakati, kufalikira ndi ma outlier musanasankhe njira zotsatira.",
    "Common mistakes to avoid: Assuming normality solely because a histogram looks vaguely bell-shaped, or deleting outliers without justification.":
        "Zolakwika zofunika kupewa: Kuganiza kuti deta ndi normal chifukwa histogramu ikuoneka ngati belu, kapena kufufuta ma outlier popanda chifukwa.",

    "What is being asked? Quantify and interpret the association between gestational age and birthweight.":
        "Kodi funso likufunsa chiyani? Yesa ndi kutanthauzira ubale pakati pa zaka za mimba ndi kulemera kwa mwana pakubadwa.",
    "Statistical concept: Pearson measures linear association; Spearman measures monotone association using ranks.":
        "Lingaliro la ziwerengero: Pearson amayeza ubale wowongoka; Spearman amayeza ubale wosasintha njira pogwiritsa ntchito masanjidwe.",
    "Do you need to write code? Yes — one plotting and calculation cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yopanga plot ndi kuwerengera.",
    "What to do in Jupyter: Run Q2(d) and read the scatterplot before the correlation numbers.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q2(d) ndipo werengani scatterplot musanawerenge manambala a correlation.",
    "Code to use: Use the verified Q2(d) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q2(d) yotsimikizidwa.",
    "Output to inspect: A scatterplot with fitted line, Pearson r with CI and p-value, and Spearman rho with p-value.":
        "Zotuluka zoyenera kuyang'ana: Scatterplot yokhala ndi mzere wokwanira, Pearson r ndi CI ndi p-value, komanso Spearman rho ndi p-value.",
    "Important values or observations: The sign and size of both coefficients, plus any visible curvature or influential points.":
        "Makhalidwe kapena zowoneratu zofunika: Chizindikiro ndi kukula kwa ma coefficient onse awiri, komanso kupindika kulikonse kowoneka kapena mfundo zomwe zimakhudza kwambiri.",
    "How to interpret it: Choose the coefficient that matches the observed relationship and the question of interest.":
        "Momwe mungatanthauzire: Sankhani coefficient yomwe ikugwirizana ndi ubale wowonedwa komanso funso lofunsidwa.",
    "What to report: Report both coefficients, then state which is more appropriate and why.":
        "Zoyenera kunena mu lipoti: Nenani ma coefficient onse awiri, kenaka fotokozani kuti ndi iti yoyenera komanso chifukwa chiyani.",
    "Common mistakes to avoid: Interpreting correlation as causation, or choosing Pearson without looking at the scatterplot.":
        "Zolakwika zofunika kupewa: Kutanthauzira correlation ngati chifukwa, kapena kusankha Pearson osayang'ana scatterplot.",

    "What is being asked? Build a t-based confidence interval step by step and verify it in SciPy.":
        "Kodi funso likufunsa chiyani? Pangani confidence interval yokhazikika pa t sitepe ndi sitepe ndipo itsimikizireni mu SciPy.",
    "Statistical concept: The standard error is SD/sqrt(n); the critical value comes from t with n-1 degrees of freedom.":
        "Lingaliro la ziwerengero: Standard error ndi SD/sqrt(n); mtengo wofunikira umachokera ku t yokhala ndi n-1 degrees of freedom.",
    "Do you need to write code? Yes — one manual calculation cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yowerengera pamanja.",
    "What to do in Jupyter: Run Q3(a) and read each intermediate quantity in the table.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q3(a) ndipo werengani kuchuluka kwapakati kulikonse mu tebulo.",
    "Code to use: Use the verified Q3(a) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q3(a) yotsimikizidwa.",
    "Output to inspect: A table of mean, SD, n, df, SE, critical t and both pairs of CI endpoints.":
        "Zotuluka zoyenera kuyang'ana: Tebulo la avareji, SD, n, df, SE, critical t ndi mapeto onse a CI.",
    "Important values or observations: Manual lower/upper and SciPy lower/upper agree within numerical precision.":
        "Makhalidwe kapena zowoneratu zofunika: Malire a pansi/apa opangidwa pamanja ndi a SciPy akugwirizana mkati mwa kulondola kwa manambala.",
    "How to interpret it: This is an interval for the population mean, estimated from the sample.":
        "Momwe mungatanthauzire: Uwu ndi interval ya avareji ya gulu lonse, yoyerekeza kuchokera ku sample.",
    "What to report: Report the mean, SE, df, critical value and the 95% CI.":
        "Zoyenera kunena mu lipoti: Nenani avareji, SE, df, mtengo wofunikira ndi CI ya 95%.",
    "Common mistakes to avoid: Using z instead of t without justification, or saying there is a 95% chance the true mean lies in this fixed interval.":
        "Zolakwika zofunika kupewa: Kugwiritsa ntchito z m'malo mwa t popanda chifukwa, kapena kunena kuti pali mwayi wa 95% kuti avareji yeniyeni ili mkati mwa interval yokhazikikayi.",

    "What is being asked? Estimate a binary outcome prevalence with an appropriate binomial interval.":
        "Kodi funso likufunsa chiyani? Yerekezerani kufala kwa zotsatira za binary pogwiritsa ntchito interval ya binomial yoyenera.",
    "Statistical concept: The denominator is the number of non-missing anaemia records; Wilson is suitable for proportions.":
        "Lingaliro la ziwerengero: Denominator ndi chiwerengero cha zolemba za kuchepa kwa magazi zomwe zilipo; Wilson ndi yoyenera pa magawo.",
    "Do you need to write code? Yes — one calculation cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yowerengera.",
    "What to do in Jupyter: Run Q3(b) and read the event count, denominator and Wilson interval.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q3(b) ndipo werengani kuchuluka kwa chochitika, denominator ndi interval ya Wilson.",
    "Code to use: Use the verified Q3(b) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q3(b) yotsimikizidwa.",
    "Output to inspect: Event count, eligible denominator, prevalence, Wilson CI and number excluded.":
        "Zotuluka zoyenera kuyang'ana: Kuchuluka kwa chochitika, denominator woyenera, kufala, Wilson CI ndi chiwerengero chomwe chinachotsedwa.",
    "Important values or observations: 139 events out of 382 evaluable records; 18 records excluded because anaemia is missing.":
        "Makhalidwe kapena zowoneratu zofunika: Zochitika 139 pa zolemba 382 zoyesedwa; zolemba 18 zachotsedwa chifukwa deta ya kuchepa kwa magazi ilibe.",
    "How to interpret it: Missingness must be reported so the denominator is auditable.":
        "Momwe mungatanthauzire: Kusowa kwa deta kuyenera kunenedwa kuti denominator iwerengedwe momveka bwino.",
    "What to report: Report the numerator, denominator, prevalence and CI method.":
        "Zoyenera kunena mu lipoti: Nenani numerator, denominator, kufala ndi njira ya CI.",
    "Common mistakes to avoid: Using all 400 as the denominator, or using a normal approximation without checking counts.":
        "Zolakwika zofunika kupewa: Kugwiritsa ntchito 400 yonse ngati denominator, kapena kugwiritsa ntchito kuyerekeza kwa normal osawona kuchuluka kwake.",

    "What is being asked? Interpret what a 95% confidence interval does and does not mean.":
        "Kodi funso likufunsa chiyani? Tanthauzirani zomwe confidence interval ya 95% imatanthauza komanso zomwe isatanthauze.",
    "Statistical concept: Confidence level refers to the long-run performance of the interval procedure; width shrinks roughly with 1/sqrt(n).":
        "Lingaliro la ziwerengero: Mulingo wa confidence ukutanthauza momwe njira ya interval imagwirira ntchito kwa nthawi yaitali; m'lifupi limachepa pafupifupi ndi 1/sqrt(n).",
    "Do you need to write code? No — this is interpretation.":
        "Kodi muyenera kulemba code? Ayi — iyi ndi ntchito yotanthauzira.",
    "What to do in Jupyter: Write a short explanation using the Q3(a) and Q3(b) intervals as examples.":
        "Zoyenera kuchita mu Jupyter: Lembani kufotokoza kwaifupi pogwiritsa ntchito ma interval a Q3(a) ndi Q3(b) monga zitsanzo.",
    "Code to use: No new code is required; reuse the verified outputs.":
        "Code yoyenera kugwiritsa ntchito: Palibe code yatsopano yofunikira; gwiritsani ntchito zotuluka zotsimikizidwa kale.",
    "Output to inspect: Your written interpretation, not a new table.":
        "Zotuluka zoyenera kuyang'ana: Kutanthauzira kwanu komwe mwalemba, osati tebulo latsopano.",
    "Important values or observations: The interval width and the sample sizes from Q3(a) and Q3(b).":
        "Makhalidwe kapena zowoneratu zofunika: M'lifupi la interval ndi kukula kwa sample kuchokera ku Q3(a) ndi Q3(b).",
    "How to interpret it: A larger sample gives a narrower interval, all else equal; four times n roughly halves the width.":
        "Momwe mungatanthauzire: Sample yokulirapo imapereka interval yopapatiza, zinthu zonse zikafanana; kukulitsa n kanayi kumachepetsa m'lifupi pafupifupi theka.",
    "What to report: Report a correct frequentist interpretation and a precision statement.":
        "Zoyenera kunena mu lipoti: Nenani kutanthauzira koyenera kwa njira ya frequentist ndi mawonekedwe a kulondola.",
    "Common mistakes to avoid: Reversing the logic of confidence, or promising that quadrupling n always halves width exactly.":
        "Zolakwika zofunika kupewa: Kusinthasintha malingaliro a confidence, kapena kulonjeza kuti kukulitsa n kanayi kumachepetsa m'lifupi ndendende theka nthawi zonse.",

    "What is being asked? Compare subgroup means and their uncertainty without over-reading interval overlap.":
        "Kodi funso likufunsa chiyani? Yerekezerani ma avareji a magulu ang'ono ndi kusatsimikizika kwawo musanawerenge kwambiri kudzigwirizana kwa ma interval.",
    "Statistical concept: Separate t intervals describe each subgroup mean; overlap is not a formal test of equality.":
        "Lingaliro la ziwerengero: Ma interval a t olekanitsa akufotokoza avareji ya gulu lililonse; kudzigwirizana kwawo si mayeso ovomerezeka a kufanana.",
    "Do you need to write code? Yes — one estimation and plotting cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yoyerekeza ndi kupanga plot.",
    "What to do in Jupyter: Run Q3(d) and compare Urban, Peri-urban and Rural estimates and interval widths.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q3(d) ndipo yerekezerani zoyerekeza za Urban, Peri-urban ndi Rural komanso m'lifupi la ma interval.",
    "Code to use: Use the verified Q3(d) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q3(d) yotsimikizidwa.",
    "Output to inspect: A subgroup summary table and a point plot with 95% CIs.":
        "Zotuluka zoyenera kuyang'ana: Tebulo lachidule la magulu ang'ono ndi point plot yokhala ndi 95% CIs.",
    "Important values or observations: Subgroup n, means and interval endpoints.":
        "Makhalidwe kapena zowoneratu zofunika: n ya magulu ang'ono, ma avareji ndi mapeto a interval.",
    "How to interpret it: Intervals that overlap do not prove means are equal, and non-overlap is not the only way to detect a difference.":
        "Momwe mungatanthauzire: Ma interval odzigwirizana satsimikizira kuti ma avareji ndi ofanana, ndipo kusadzigwirizana sikokha njira yodziwira kusiyana.",
    "What to report: Report each subgroup estimate with n and CI, then describe patterns cautiously.":
        "Zoyenera kunena mu lipoti: Nenani zoyerekeza za gulu lililonse ndi n ndi CI, kenaka fotokozani mawonekedwe mosamala.",
    "Common mistakes to avoid: Using interval overlap as a significance test, or ignoring unequal subgroup sizes.":
        "Zolakwika zofunika kupewa: Kugwiritsa ntchito kudzigwirizana kwa interval ngati mayeso a kufunika, kapena kunyalanyaza kukula kosafanana kwa magulu ang'ono.",

    "What is being asked? Analyse an independent two-group observational comparison.":
        "Kodi funso likufunsa chiyani? Unikani kuyerekeza kwa magulu awiri odziyimira pawokha mu deta yowunikira.",
    "Statistical concept: Welch's t-test compares means without assuming equal variances; Wilcoxon rank-sum compares distributions/ranks.":
        "Lingaliro la ziwerengero: Welch's t-test imayerekeza ma avareji osaganiza kuti ma variance ndi ofanana; Wilcoxon rank-sum imayerekeza kugawa kapena masanjidwe.",
    "Do you need to write code? Yes — one comprehensive analysis cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yonse yowunika.",
    "What to do in Jupyter: Run Q4 and read each output block in order.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q4 ndipo werengani gawo lililonse la zotuluka motsatira dongosolo.",
    "Code to use: Use the verified Q4 code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q4 yotsimikizidwa.",
    "Output to inspect: Group summaries, boxplot/histograms, Levene p, Welch t/df/p/CI and rank-sum result.":
        "Zotuluka zoyenera kuyang'ana: Chidule cha magulu, boxplot kapena histogramu, Levene p, Welch t/df/p/CI ndi zotsatira za rank-sum.",
    "Important values or observations: Mean difference, its CI and whether the p-value is small; Levene result informs the t-test choice.":
        "Makhalidwe kapena zowoneratu zofunika: Kusiyana kwa avareji, CI yake ndi ngati p-value ili yochepa; zotsatira za Levene zimathandiza kusankha t-test.",
    "How to interpret it: Statistical significance does not imply clinical importance, and an observational comparison is not causal.":
        "Momwe mungatanthauzire: Kufunika kwa ziwerengero sikukutanthauza kufunikira kwa zachipatala, ndipo kuyerekeza kwa deta yowunikira si chifukwa.",
    "What to report: Report group n/mean/SD, the Welch difference with CI and p, and the sensitivity analysis.":
        "Zoyenera kunena mu lipoti: Nenani n/avareji/SD ya magulu, kusiyana kwa Welch ndi CI ndi p, komanso kuwunika kwa sensitivity.",
    "Common mistakes to avoid: Calling rank-sum automatically a median test, or claiming IPTp3 caused a birthweight change.":
        "Zolakwika zofunika kupewa: Kunena kuti rank-sum ndi mayeso a median nthawi zonse, kapena kunena kuti IPTp3 inayambitsa kusintha kwa kulemera kwa mwana pakubadwa.",

    "What is being asked? Analyse two measurements taken on the same women.":
        "Kodi funso likufunsa chiyani? Unikani miyeso iwiri yotengedwa kwa amayi omwewo.",
    "Statistical concept: Pairing removes between-woman variability by analysing within-woman differences.":
        "Lingaliro la ziwerengero: Kuphatikiza deta ya munthu yemweyo kumachotsa kusiyana pakati pa amayi poyang'ana kusiyana mkati mwa mkazi aliyense.",
    "Do you need to write code? Yes — one paired-analysis cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yowunikira deta yofananizidwa.",
    "What to do in Jupyter: Run Q5 and compare the paired result with the deliberately incorrect independent result.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q5 ndipo yerekezerani zotsatira zophatikizidwa ndi zotsatira zolakwika za magulu odziyimira pawokha zomwe zapangidwa mwadala.",
    "Code to use: Use the verified Q5 code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q5 yotsimikizidwa.",
    "Output to inspect: Summaries, difference histogram, paired profiles, Shapiro result, paired t/CI/p and incorrect independent test.":
        "Zotuluka zoyenera kuyang'ana: Chidule, histogramu ya kusiyana, mbiri ya deta yofananizidwa, zotsatira za Shapiro, paired t/CI/p ndi mayeso olakwika a magulu odziyimira pawokha.",
    "Important values or observations: Mean change, CI, p-value and the difference between the correct and incorrect standard errors.":
        "Makhalidwe kapena zowoneratu zofunika: Kusintha kwa avareji, CI, p-value ndi kusiyana pakati pa standard error yolondola ndi yolakwika.",
    "How to interpret it: A bigger mean at 36 weeks is an average within-woman change in this simulated cohort.":
        "Momwe mungatanthauzire: Avareji yokulirapo pa masabata 36 ndi kusintha kwapakati mkati mwa mkazi aliyense mu gulu la kafukufuku lofananizidwali.",
    "What to report: Report the mean paired change with CI and p-value, and explain why pairing is required.":
        "Zoyenera kunena mu lipoti: Nenani kusintha kwapakati kwa deta yofananizidwa ndi CI ndi p-value, ndipo fotokozani chifukwa chake kufananiza kuli kofunikira.",
    "Common mistakes to avoid: Using an independent-samples test for the final inference or ignoring the id linkage.":
        "Zolakwika zofunika kupewa: Kugwiritsa ntchito mayeso a zitsanzo zodziyimira pawokha pa zotsatira zomaliza, kapena kunyalanyaza kugwirizana kwa id.",

    "What is being asked? Compare three independent groups and handle multiplicity.":
        "Kodi funso likufunsa chiyani? Yerekezerani magulu atatu odziyimira pawokha ndi ANOVA ndipo samalirani kuyesa kangapo.",
    "Statistical concept: One-way ANOVA compares means; Kruskal-Wallis compares distributions/ranks; Tukey HSD adjusts pairwise comparisons.":
        "Lingaliro la ziwerengero: One-way ANOVA imayerekeza ma avareji; Kruskal-Wallis imayerekeza kugawa kapena masanjidwe; Tukey HSD imasintha kuyerekeza kwa ma pair.",
    "Do you need to write code? Yes — one comparison cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yoyerekeza.",
    "What to do in Jupyter: Run Q6 and read the boxplot, residual plot, Levene, ANOVA, Tukey table and Kruskal result.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q6 ndipo werengani boxplot, plot ya residual, Levene, ANOVA, tebulo la Tukey ndi zotsatira za Kruskal.",
    "Code to use: Use the verified Q6 code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q6 yotsimikizidwa.",
    "Output to inspect: Group summaries, diagnostic plots, Levene p, ANOVA F/df/p, Tukey adjusted comparisons and Kruskal H/p.":
        "Zotuluka zoyenera kuyang'ana: Chidule cha magulu, ma plot owunikira, Levene p, ANOVA F/df/p, kuyerekeza kwa Tukey kosinthidwa ndi Kruskal H/p.",
    "Important values or observations: The overall p-value, which Tukey pairs differ and whether variance/normality checks raise concerns.":
        "Makhalidwe kapena zowoneratu zofunika: p-value yonse, ma pair a Tukey omwe akusiyana komanso ngati kuwunika kwa variance kapena normality kwabweretsa nkhawa.",
    "How to interpret it: A significant overall test does not say which groups differ; post-hoc tests must account for multiplicity.":
        "Momwe mungatanthauzire: Mayeso onse ofunika sakuuza kuti ndi magulu ati omwe akusiyana; mayeso a post-hoc ayenera kuganizira kuyesa kangapo.",
    "What to report: Report the overall test first, then adjusted pairwise differences only if warranted.":
        "Zoyenera kunena mu lipoti: Nenani mayeso onse poyamba, kenaka kusiyana kwa ma pair kosinthidwa pokhapokha ngati kuli koyenera.",
    "Common mistakes to avoid: Running unadjusted pairwise t-tests and calling them pre-planned, or ignoring assumption checks.":
        "Zolakwika zofunika kupewa: Kuthamangitsa ma t-test a ma pair osasintha n'kuwati akonzedweratu, kapena kunyalanyaza kuwunika kwa malingaliro.",

    "What is being asked? Test whether two categorical variables are associated.":
        "Kodi funso likufunsa chiyani? Yesani ndi mayeso a chi-square ngati zinthu ziwiri za gulu zikugwirizana.",
    "Statistical concept: The chi-square test compares observed and expected counts under independence.":
        "Lingaliro la ziwerengero: Mayeso a chi-square amayerekeza kuchuluka kowonedwa ndi komwe kuyembekezeredwa ngati zinthu zodziyimira pawokha.",
    "Do you need to write code? Yes — one categorical-analysis cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yowunikira zinthu za gulu.",
    "What to do in Jupyter: Run Q7(a) and read the observed table, row percentages and expected counts.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q7(a) ndipo werengani tebulo lowonedwa, magawo a mizere ndi kuchuluka komwe kuyembekezeredwa.",
    "Code to use: Use the verified Q7(a) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q7(a) yotsimikizidwa.",
    "Output to inspect: Contingency table, row/column percentages, expected counts, chi-square, df and p-value.":
        "Zotuluka zoyenera kuyang'ana: Tebulo la contingency, magawo a mizere kapena mizati, kuchuluka koyembekezeredwa, chi-square, df ndi p-value.",
    "Important values or observations: Whether all expected counts are at least 5 and the pattern of row percentages.":
        "Makhalidwe kapena zowoneratu zofunika: Kodi kuchuluka konse koyembekezeredwa kuli osachepera 5 komanso mawonekedwe a magawo a mizere.",
    "How to interpret it: An association does not imply that education caused anaemia.":
        "Momwe mungatanthauzire: Ubale sikutanthauza kuti maphunziro anayambitsa kuchepa kwa magazi.",
    "What to report: Report the table, test statistic, df, p and a contextual association statement.":
        "Zoyenera kunena mu lipoti: Nenani tebulo, mtengo wa mayeso, df, p ndi mawonekedwe a ubale potengera nkhaniyi.",
    "Common mistakes to avoid: Using the chi-square approximation when expected counts are too small, or interpreting association causally.":
        "Zolakwika zofunika kupewa: Kugwiritsa ntchito kuyerekeza kwa chi-square pamene kuchuluka koyembekezeredwa kuli kochepa kwambiri, kapena kutanthauzira ubale ngati chifukwa.",

    "What is being asked? Compare one observed proportion with a specified null value.":
        "Kodi funso likufunsa chiyani? Yerekezerani gawo limodzi lowonedwa ndi mtengo wa null wofotokozedwa.",
    "Statistical concept: An exact binomial test is appropriate when counts are modest or approximation assumptions are uncertain.":
        "Lingaliro la ziwerengero: Mayeso enieni a binomial ndi oyenera pamene kuchuluka kuli kochepa kapena malingaliro a kuyerekeza sakudziwika bwino.",
    "Do you need to write code? Yes — one proportion-test cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yoyesa gawo.",
    "What to do in Jupyter: Run Q7(b) and state the hypotheses before reading the output.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q7(b) ndipo nenani malingaliro a H0 ndi H1 musanawerenge zotuluka.",
    "Code to use: Use the verified Q7(b) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q7(b) yotsimikizidwa.",
    "Output to inspect: Observed proportion, null value, exact p-value and 95% Wilson CI.":
        "Zotuluka zoyenera kuyang'ana: Gawo lowonedwa, mtengo wa null, p-value yeniyeni ndi Wilson CI ya 95%.",
    "Important values or observations: Whether 0.30 lies inside the interval and the exact p-value.":
        "Makhalidwe kapena zowoneratu zofunika: Kodi 0.30 ili mkati mwa interval komanso p-value yeniyeni.",
    "How to interpret it: The test concerns the simulated cohort's underlying proportion, not a real population guideline.":
        "Momwe mungatanthauzire: Mayesowa ukukhudza gawo lalikulu la gulu la kafukufuku lofananizidwa, osati malangizo a gulu lenileni.",
    "What to report: Report H0/H1, x/n, p-value, CI and a contextual conclusion.":
        "Zoyenera kunena mu lipoti: Nenani H0/H1, x/n, p-value, CI ndi zotsatira potengera nkhaniyi.",
    "Common mistakes to avoid: Using an inappropriate normal approximation without checking expected counts.":
        "Zolakwika zofunika kupewa: Kugwiritsa ntchito kuyerekeza kwa normal kosayenera popanda kuwona kuchuluka koyembekezeredwa.",

    "What is being asked? Compare two independent proportions and quantify the difference.":
        "Kodi funso likufunsa chiyani? Yerekezerani magawo awiri odziyimira pawokha ndipo yesani kusiyana kwake.",
    "Statistical concept: A two-proportion z test assesses the difference; an interval describes its plausible size.":
        "Lingaliro la ziwerengero: z test ya magawo awiri imawunika kusiyana; interval imafotokoza kukula kwake koyenera.",
    "Do you need to write code? Yes — one two-proportion cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi ya magawo awiri.",
    "What to do in Jupyter: Run Q7(c) and read the group table, difference, CI and p-values.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q7(c) ndipo werengani tebulo la magulu, kusiyana, CI ndi ma p-value.",
    "Code to use: Use the verified Q7(c) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q7(c) yotsimikizidwa.",
    "Output to inspect: Group counts/denominators/proportions, risk difference, Newcombe CI, z test and Fisher exact p.":
        "Zotuluka zoyenera kuyang'ana: Kuchuluka kwa magulu, ma denominator, magawo, kusiyana kwa mwayi wachochitika, Newcombe CI, z test ndi Fisher exact p.",
    "Important values or observations: The size and direction of the difference and consistency between tests.":
        "Makhalidwe kapena zowoneratu zofunika: Kukula ndi komwe kusiyana kukupita komanso kugwirizana pakati pa mayeso.",
    "How to interpret it: This is an observational association; anaemia is not randomly assigned.":
        "Momwe mungatanthauzire: Uwu ndi ubale wowonedwa mu deta yowunikira; kuchepa kwa magazi sikunaperekedwe mwachisawawa.",
    "What to report: Report both group proportions, the difference with CI and the p-value.":
        "Zoyenera kunena mu lipoti: Nenani magawo a magulu onse awiri, kusiyana ndi CI ndi p-value.",
    "Common mistakes to avoid: Interpreting association as causation or omitting denominators.":
        "Zolakwika zofunika kupewa: Kutanthauzira ubale ngati chifukwa kapena kusiya ma denominator.",

    "What is being asked? Model birthweight as a linear function of gestational age.":
        "Kodi funso likufunsa chiyani? Fotokozani kulemera kwa mwana pakubadwa ngati ntchito yowongoka ya zaka za mimba.",
    "Statistical concept: Simple linear regression estimates an average change in the outcome per one-unit change in the predictor.":
        "Lingaliro la ziwerengero: Linear regression yosavuta imayerekeza kusintha kwapakati kwa zotsatira pa kusintha kwa unit imodzi kwa chinthu cholosera.",
    "Do you need to write code? Yes — one model-and-plot cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yopanga chitsanzo ndi plot.",
    "What to do in Jupyter: Run Q8(a), then read the scatterplot before the coefficient table.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q8(a), kenaka werengani scatterplot musanawerenge tebulo la coefficient.",
    "Code to use: Use the verified Q8(a) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q8(a) yotsimikizidwa.",
    "Output to inspect: Coefficients with SEs, CIs and p-values, R-squared and a fitted-line plot.":
        "Zotuluka zoyenera kuyang'ana: Ma coefficient ndi ma SE, CIs ndi ma p-value, R-squared ndi plot ya mzere wokwanira.",
    "Important values or observations: The gest_age slope, its CI and R-squared.":
        "Makhalidwe kapena zowoneratu zofunika: Slope ya gest_age, CI yake ndi R-squared.",
    "How to interpret it: The slope is an average association, not a causal effect.":
        "Momwe mungatanthauzire: Slope ndi ubale wapakati, osati zotsatira za chifukwa.",
    "What to report: Report the fitted equation, slope with CI/p and R-squared.":
        "Zoyenera kunena mu lipoti: Nenani equation yokwanira, slope ndi CI/p ndi R-squared.",
    "Common mistakes to avoid: Interpreting the intercept outside the observed range or treating R-squared as causation.":
        "Zolakwika zofunika kupewa: Kutanthauzira intercept kunja kwa malire owonedwa kapena kuganiza kuti R-squared ndi chifukwa.",

    "What is being asked? Estimate adjusted associations with several predictors.":
        "Kodi funso likufunsa chiyani? Yerekezerani ubale wosinthidwa pogwiritsa ntchito zinthu zolosera zingapo.",
    "Statistical concept: Multiple regression estimates each coefficient conditional on the other predictors in the model.":
        "Lingaliro la ziwerengero: Multiple regression imayerekeza coefficient iliyonse potengera zinthu zina zolosera mu chitsanzo.",
    "Do you need to write code? Yes — one model cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi ya chitsanzo.",
    "What to do in Jupyter: Run Q8(b) and note the complete-case n after BMI missingness.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q8(b) ndipo lembani n ya deta yathunthu pambuyo pa kusowa kwa BMI.",
    "Code to use: Use the verified Q8(b) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q8(b) yotsimikizidwa.",
    "Output to inspect: Adjusted coefficient table with SEs, CIs and p-values, plus R-squared and adjusted R-squared.":
        "Zotuluka zoyenera kuyang'ana: Tebulo la coefficient yosinthidwa ndi ma SE, CIs ndi ma p-value, kuphatikiza R-squared ndi adjusted R-squared.",
    "Important values or observations: Adjusted coefficients, especially the IPTp3 term and the reduction in n.":
        "Makhalidwe kapena zowoneratu zofunika: Ma coefficient osinthidwa, makamaka nthawi ya IPTp3 ndi kuchepa kwa n.",
    "How to interpret it: Adjusted coefficients answer a different question from crude group differences.":
        "Momwe mungatanthauzire: Ma coefficient osinthidwa akuyankha funso losiyana ndi kusiyana kwagulu kosasintha.",
    "What to report: Report each adjusted coefficient with CI/p and the complete-case denominator.":
        "Zoyenera kunena mu lipoti: Nenani coefficient iliyonse yosinthidwa ndi CI/p komanso denominator ya deta yathunthu.",
    "Common mistakes to avoid: Comparing models fitted on different samples without saying so.":
        "Zolakwika zofunika kupewa: Kuyerekeza zitsanzo zopangidwa kuchokera ku deta yosiyana popanda kufotokoza.",

    "What is being asked? Check whether the regression model's assumptions are plausible.":
        "Kodi funso likufunsa chiyani? Onani ngati malingaliro a chitsanzo cha regression ndi omveka.",
    "Statistical concept: Residual plots reveal non-linearity and unequal spread; Q-Q plots assess normality; influence measures find influential records.":
        "Lingaliro la ziwerengero: Ma plot a residual amavumbula kusalunjika ndi kufalikira kosafanana; ma plot a Q-Q amawunika normality; miyeso ya mphamvu imapeza zolemba zomwe zimakhudza kwambiri.",
    "Do you need to write code? Yes — one diagnostic plotting cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yopanga ma plot owunikira.",
    "What to do in Jupyter: Run Q8(c) and examine each panel rather than only the Durbin-Watson number.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q8(c) ndipo onani gulu lililonse la plot, osati nambala ya Durbin-Watson yokha.",
    "Code to use: Use the verified Q8(c) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q8(c) yotsimikizidwa.",
    "Output to inspect: Four diagnostic plots, Durbin-Watson, Cook's D threshold and top influential rows.":
        "Zotuluka zoyenera kuyang'ana: Ma plot owunikira anayi, Durbin-Watson, malire a Cook's D ndi mizere yomwe imakhudza kwambiri.",
    "Important values or observations: Pattern in residuals vs fitted, Q-Q departures, funnel shapes and large Cook's D values.":
        "Makhalidwe kapena zowoneratu zofunika: Mawonekedwe a residual poyerekeza ndi zokwanira, kutsauka kwa Q-Q, mawonekedwe a funnel ndi makhalidwe akulu a Cook's D.",
    "How to interpret it: Independence is mainly justified by the study design here because each id is one woman.":
        "Momwe mungatanthauzire: Kudziyimira pawokha kumatsimikiziridwa makamaka ndi kapangidwe ka kafukufuku chifukwa id iliyonse ndi mkazi mmodzi.",
    "What to report: Report what each plot assesses and whether any concern is visible.":
        "Zoyenera kunena mu lipoti: Nenani zomwe plot iliyonse imawunika komanso ngati pali nkhawa yowoneka.",
    "Common mistakes to avoid: Declaring assumptions 'passed' from one plot, or deleting influential points solely because they are influential.":
        "Zolakwika zofunika kupewa: Kunena kuti malingaliro 'adutsa' kuchokera ku plot imodzi, kapena kufufuta mfundo zomwe zimakhudza kwambiri chifukwa chabe zimakhudza.",

    "What is being asked? Assess whether facility type improves the model after the existing predictors.":
        "Kodi funso likufunsa chiyani? Unikani ngati mtundu wa malo operekera chithandizo ukusintha chitsanzo pambuyo pa zinthu zolosera zomwe zilipo.",
    "Statistical concept: Nested-model comparison tests whether the added block explains additional variation beyond the base model.":
        "Lingaliro la ziwerengero: Kuyerekeza zitsanzo zokhazikika kumayesa ngati gulu lomwe lawonjezeredwa likufotokoza kusiyana kowonjezera kuposa chitsanzo choyambirira.",
    "Do you need to write code? Yes — one model-comparison cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yoyerekeza zitsanzo.",
    "What to do in Jupyter: Run Q8(d) and confirm both models used the same complete-case sample.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q8(d) ndipo tsimikizirani kuti zitsanzo zonse ziwiri zinagwiritsa ntchito deta yathunthu yomweyo.",
    "Code to use: Use the verified Q8(d) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q8(d) yotsimikizidwa.",
    "Output to inspect: Nested F test, AIC, adjusted R-squared and complete-case n.":
        "Zotuluka zoyenera kuyang'ana: Nested F test, AIC, adjusted R-squared ndi n ya deta yathunthu.",
    "Important values or observations: The block p-value, AIC change and whether adjusted R-squared improves.":
        "Makhalidwe kapena zowoneratu zofunika: p-value ya gulu, kusintha kwa AIC komanso ngati adjusted R-squared wapita patsogolo.",
    "How to interpret it: A better fit does not establish a causal facility effect.":
        "Momwe mungatanthauzire: Chitsanzo chokwanira bwino sikhazikitsa kuti malo operekera chithandizo ndi chifukwa.",
    "What to report: Report the comparison statistics and state whether facility type adds explanatory value.":
        "Zoyenera kunena mu lipoti: Nenani ziwerengero zoyerekeza ndipo fotokozani ngati mtundu wa malo ukuwonjezera kufotokoza.",
    "Common mistakes to avoid: Comparing AIC across different samples or ignoring model complexity.":
        "Zolakwika zofunika kupewa: Kuyerekeza AIC pakati pa zitsanzo zosiyana kapena kunyalanyaza zovuta za chitsanzo.",

    "What is being asked? Use a fitted model to predict and distinguish two interval types.":
        "Kodi funso likufunsa chiyani? Gwiritsani ntchito chitsanzo chokwanira kulosera ndikusiyanitsa mitundu iwiri ya interval.",
    "Statistical concept: A confidence interval targets the mean response; a prediction interval includes individual residual variability.":
        "Lingaliro la ziwerengero: Confidence interval imayang'ana yankho lapakati; prediction interval imaphatikizapo kusiyana kwa residual kwa munthu aliyense.",
    "Do you need to write code? Yes — one prediction cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yopanga prediction.",
    "What to do in Jupyter: Run Q8(e) and note which model and facility assumption each prediction uses.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q8(e) ndipo lembani chitsanzo ndi malingaliro a malo omwe prediction iliyonse imagwiritsa ntchito.",
    "Code to use: Use the verified Q8(e) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q8(e) yotsimikizidwa.",
    "Output to inspect: Predicted mean with 95% CI and 95% prediction interval for an individual.":
        "Zotuluka zoyenera kuyang'ana: Avareji yoloseredwa ndi 95% CI komanso 95% prediction interval ya munthu mmodzi.",
    "Important values or observations: The prediction interval must be wider than the mean-response CI.":
        "Makhalidwe kapena zowoneratu zofunika: Prediction interval iyenera kukhala yokulirapo kuposa CI ya yankho lapakati.",
    "How to interpret it: Predictions are model-based estimates for a hypothetical profile, not observed data.":
        "Momwe mungatanthauzire: Zolosera ndi zoyerekeza zochokera ku chitsanzo za mbiri yongoganizira, osati deta yowonedwa.",
    "What to report: Report the fitted model, covariates, prediction and both intervals.":
        "Zoyenera kunena mu lipoti: Nenani chitsanzo chokwanira, ma covariate, zolosera ndi ma interval onse awiri.",
    "Common mistakes to avoid: Confusing the two interval types or omitting the facility assumption when using the extended model.":
        "Zolakwika zofunika kupewa: Kusokoneza mitundu iwiri ya interval kapena kusiya malingaliro a malo pogwiritsa ntchito chitsanzo chowonjezeredwa.",

    "What is being asked? Model a binary outcome and interpret adjusted odds ratios.":
        "Kodi funso likufunsa chiyani? Pangani chitsanzo cha zotsatira za binary ndipo tanthauzirani ma odds ratio osinthidwa.",
    "Statistical concept: Logistic regression models the log-odds; exponentiating coefficients gives odds ratios.":
        "Lingaliro la ziwerengero: Logistic regression imapanga chitsanzo cha log-odds; kukweza ma coefficient kumapereka odds ratios.",
    "Do you need to write code? Yes — one model and prediction cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi ya chitsanzo ndi prediction.",
    "What to do in Jupyter: Run Q9 and read the coefficient table before the scenario plot.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q9 ndipo werengani tebulo la coefficient musanawone plot ya zochitika.",
    "Code to use: Use the verified Q9 code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q9 yotsimikizidwa.",
    "Output to inspect: Coefficients, ORs with CIs and p-values, pseudo R-squared, two scenario probabilities and a stratified plot.":
        "Zotuluka zoyenera kuyang'ana: Ma coefficient, OR ndi ma CI ndi ma p-value, pseudo R-squared, mwayi wa zochitika ziwiri ndi plot yogawidwa.",
    "Important values or observations: The anaemia OR and the predicted probabilities for age 25 and ANC 4.":
        "Makhalidwe kapena zowoneratu zofunika: OR ya kuchepa kwa magazi ndi mwayi woloseredwa wa zaka 25 ndi ANC 4.",
    "How to interpret it: Odds ratios are not risk ratios, and the data are observational.":
        "Momwe mungatanthauzire: Ma odds ratio si ma risk ratio, ndipo deta ndi yowunikira.",
    "What to report: Report adjusted ORs with CIs/p, the scenario probabilities and non-causal wording.":
        "Zoyenera kunena mu lipoti: Nenani ma OR osinthidwa ndi ma CI/p, mwayi wa zochitika ndi mawonekedwe osanena za chifukwa.",
    "Common mistakes to avoid: Calling an odds ratio a risk ratio or converting it directly into a probability change.":
        "Zolakwika zofunika kupewa: Kunena kuti odds ratio ndi risk ratio kapena kuisintha mwachindunji kukhala kusintha kwa mwayi.",

    "What is being asked? Summarise a time-to-event dataset correctly.":
        "Kodi funso likufunsa chiyani? Fotokozani mwachidule deta ya nthawi mpaka chochitika moyenera.",
    "Statistical concept: Censoring means the event was not observed by the end of follow-up for that participant.":
        "Lingaliro la ziwerengero: Censoring zikutanthauza kuti chochitika sichinaonekere mpaka kutha kwa kutsatira kwa munthuyo.",
    "Do you need to write code? Yes — one descriptive cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yofotokozera deta.",
    "What to do in Jupyter: Run Q10(a) and separate median observed follow-up from median survival.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q10(a) ndipo siyanitsani median yotsatira yowonedwa ndi median survival.",
    "Code to use: Use the verified Q10(a) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q10(a) yotsimikizidwa.",
    "Output to inspect: Participant count, event count, censored count/proportion and median observed follow-up.":
        "Zotuluka zoyenera kuyang'ana: Chiwerengero cha otenga nawo mbali, cha zochitika, chochepetsedwa ndi gawo lake komanso median yotsatira yowonedwa.",
    "Important values or observations: 209 events, 291 censored and median observed follow-up of 119 days.":
        "Makhalidwe kapena zowoneratu zofunika: Zochitika 209, zochepetsedwa 291 ndi median yotsatira yowonedwa ya masiku 119.",
    "How to interpret it: Median observed follow-up is not an estimate of the median event-free survival time.":
        "Momwe mungatanthauzire: Median yotsatira yowonedwa si kuyerekeza kwa nthawi yapakati yopulumuka popanda chochitika.",
    "What to report: Report n, events, censoring proportion and the correct label for follow-up time.":
        "Zoyenera kunena mu lipoti: Nenani n, zochitika, gawo la censoring ndi dzina lolondola la nthawi yotsatira.",
    "Common mistakes to avoid: Equating median follow-up with median survival.":
        "Zolakwika zofunika kupewa: Kuyerekeza median yotsatira ndi median survival.",

    "What is being asked? Estimate event-free survival while handling censoring.":
        "Kodi funso likufunsa chiyani? Yerekezerani kupulumuka popanda chochitika pamene mukusamalira censoring.",
    "Statistical concept: Kaplan-Meier multiplies conditional survival probabilities at each event time.":
        "Lingaliro la ziwerengero: Kaplan-Meier imachulukitsa mwayi wapamikhalidwe wopulumuka pa nthawi iliyonse ya chochitika.",
    "Do you need to write code? Yes — one estimation and plotting cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yoyerekeza ndi kupanga plot.",
    "What to do in Jupyter: Run Q10(b) and read the curve, pointwise CIs and risk table.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q10(b) ndipo werengani curve, ma CI pa mfundo iliyonse ndi tebulo la chiwopsezo.",
    "Code to use: Use the verified Q10(b) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q10(b) yotsimikizidwa.",
    "Output to inspect: KM curve, 95% CI band, S(90), S(180), median survival and numbers at risk.":
        "Zotuluka zoyenera kuyang'ana: KM curve, gulu la 95% CI, S(90), S(180), median survival ndi chiwerengero cha anthu pachiwopsezo.",
    "Important values or observations: Survival probabilities at 90 and 180 days and whether the median is estimable.":
        "Makhalidwe kapena zowoneratu zofunika: Mwayi wopulumuka pa masiku 90 ndi 180 komanso ngati median ingayerekezedwe.",
    "How to interpret it: The KM curve describes readmission-free survival in this simulated cohort.":
        "Momwe mungatanthauzire: KM curve ikufotokoza kupulumuka popanda kubwereranso kuchipitali mu gulu la kafukufuku lofananizidwali.",
    "What to report: Report S(90), S(180), median if estimable and the risk-table interpretation.":
        "Zoyenera kunena mu lipoti: Nenani S(90), S(180), median ngati ingayerekezedwe ndi kutanthauzira tebulo la chiwopsezo.",
    "Common mistakes to avoid: Treating censored records as events or dropping them from the risk set.":
        "Zolakwika zofunika kupewa: Kuganiza kuti zolemba zochepetsedwa ndi zochitika kapena kuzichotsa mu gulu la chiwopsezo.",

    "What is being asked? Compare two censored survival experiences.":
        "Kodi funso likufunsa chiyani? Yerekezerani zochitika ziwiri zopulumuka zochepetsedwa.",
    "Statistical concept: The log-rank test compares observed and expected events across event times under equal survival.":
        "Lingaliro la ziwerengero: Mayeso a log-rank amayerekeza zochitika zowonedwa ndi zoyembekezeredwa pa nthawi za chochitika ngati kupulumuka kuli kofanana.",
    "Do you need to write code? Yes — one comparison cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yoyerekeza.",
    "What to do in Jupyter: Run Q10(c) and compare curve separation with the log-rank p-value.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q10(c) ndipo yerekezerani kulekanitsidwa kwa ma curve ndi p-value ya log-rank.",
    "Code to use: Use the verified Q10(c) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q10(c) yotsimikizidwa.",
    "Output to inspect: Two KM curves, group medians where estimable and log-rank chi-square/p.":
        "Zotuluka zoyenera kuyang'ana: Ma curve a KM awiri, ma median a magulu pamene angayerekezedwe ndi log-rank chi-square/p.",
    "Important values or observations: Curve separation and the log-rank statistic/p-value.":
        "Makhalidwe kapena zowoneratu zofunika: Kulekanitsidwa kwa ma curve ndi chiwerengero cha log-rank ndi p-value yake.",
    "How to interpret it: The test is association-only; it does not adjust for other covariates.":
        "Momwe mungatanthauzire: Mayesowa umangoyang'ana ubale; susintha ma covariate ena.",
    "What to report: Report the two group curves, any estimable group medians and the log-rank results.":
        "Zoyenera kunena mu lipoti: Nenani ma curve a magulu awiri, ma median omwe angayerekezedwe ndi zotsatira za log-rank.",
    "Common mistakes to avoid: Assuming crossing curves satisfy the log-rank assumptions without checking.":
        "Zolakwika zofunika kupewa: Kuganiza kuti ma curve odutsana akwaniritsa malingaliro a log-rank popanda kuwona.",

    "What is being asked? Estimate a readmission rate under an exponential survival model.":
        "Kodi funso likufunsa chiyani? Yerekezerani mtengo wa kubwereranso kuchipitali pogwiritsa ntchito chitsanzo cha kupulumuka cha exponential.",
    "Statistical concept: The exponential model assumes a constant hazard; the rate is events divided by total person-time.":
        "Lingaliro la ziwerengero: Chitsanzo cha exponential chikuganiza kuti hazard ndi yosasinthika; mtengo wake ndi zochitika zogawidwa ndi person-time yonse.",
    "Do you need to write code? Yes — one rate calculation cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yowerengera mtengo.",
    "What to do in Jupyter: Run Q10(d) and compare S(90)/S(180) with the earlier KM values.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q10(d) ndipo yerekezerani S(90)/S(180) ndi makhalidwe a KM akale.",
    "Code to use: Use the verified Q10(d) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q10(d) yotsimikizidwa.",
    "Output to inspect: Events, person-time, rate, per-1,000 rate, exact CI and exponential S(90)/S(180).":
        "Zotuluka zoyenera kuyang'ana: Zochitika, person-time, mtengo, mtengo pa 1,000, CI yeniyeni ndi exponential S(90)/S(180).",
    "Important values or observations: Whether the exponential probabilities are close to the KM probabilities.":
        "Makhalidwe kapena zowoneratu zofunika: Kodi mwayi wa exponential uli pafupi ndi mwayi wa KM.",
    "How to interpret it: The constant-hazard assumption is strong and should be checked against the KM curve.":
        "Momwe mungatanthauzire: Malingaliro a hazard yosasinthika ndi amphamvu ndipo ayenera kufufuzidwa pogwiritsa ntchito KM curve.",
    "What to report: Report the rate with person-time and CI, then compare with KM.":
        "Zoyenera kunena mu lipoti: Nenani mtengo ndi person-time ndi CI, kenaka yerekezerani ndi KM.",
    "Common mistakes to avoid: Using events/population instead of events/person-time, or ignoring the constant-hazard assumption.":
        "Zolakwika zofunika kupewa: Kugwiritsa ntchito zochitika/population m'malo mwa zochitika/person-time, kapena kunyalanyaza malingaliro a hazard yosasinthika.",

    "What is being asked? Model the hazard of readmission with covariates.":
        "Kodi funso likufunsa chiyani? Pangani chitsanzo cha hazard ya kubwereranso kuchipitali pogwiritsa ntchito ma covariate.",
    "Statistical concept: A hazard ratio is a relative instantaneous event rate; an adjusted HR holds the other covariates fixed.":
        "Lingaliro la ziwerengero: Hazard ratio ndi mtengo wachochitika wanthawi yomweyo wofananizira; HR yosinthidwa imasunga ma covariate ena osasintha.",
    "Do you need to write code? Yes — one Cox model cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi ya chitsanzo cha Cox.",
    "What to do in Jupyter: Run Q10(e) and identify the reference group for each categorical term.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q10(e) ndipo dziwani gulu lotchulidwa pa nthawi iliyonse ya gulu.",
    "Code to use: Use the verified Q10(e) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q10(e) yotsimikizidwa.",
    "Output to inspect: Coefficients, HRs, 95% CIs and p-values for anaemia, caesarean and age.":
        "Zotuluka zoyenera kuyang'ana: Ma coefficient, HR, 95% CIs ndi ma p-value a kuchepa kwa magazi, opaleshoni ndi zaka.",
    "Important values or observations: The adjusted HRs and whether their CIs exclude 1.":
        "Makhalidwe kapena zowoneratu zofunika: Ma HR osinthidwa komanso ngati ma CI awo sakuphatikiza 1.",
    "How to interpret it: HR is not a risk ratio, and observational HRs are not causal effects.":
        "Momwe mungatanthauzire: HR si risk ratio, ndipo ma HR ochokera ku deta yowunikira si zotsatira za chifukwa.",
    "What to report: Report adjusted HRs with CIs/p and reference levels.":
        "Zoyenera kunena mu lipoti: Nenani ma HR osinthidwa ndi ma CI/p komanso magulu otchulidwa.",
    "Common mistakes to avoid: Calling HR a risk ratio or omitting reference categories.":
        "Zolakwika zofunika kupewa: Kunena kuti HR ndi risk ratio kapena kusiya magulu otchulidwa.",

    "What is being asked? Check whether the Cox proportional hazards assumption is plausible.":
        "Kodi funso likufunsa chiyani? Onani ngati malingaliro a proportional hazards a Cox ndi omveka.",
    "Statistical concept: Proportional hazards means covariate hazard ratios are constant over follow-up; Schoenfeld residuals should show no time trend.":
        "Lingaliro la ziwerengero: Proportional hazards kutanthauza kuti ma hazard ratio a covariate ndi osasintha panthawi yotsatira; Schoenfeld residuals sayenera kuwonetsa kusintha ndi nthawi.",
    "Do you need to write code? Yes — one diagnostic cell.":
        "Kodi muyenera kulemba code? Inde — selo imodzi yowunikira.",
    "What to do in Jupyter: Run Q10(f) and look for trends in each residual plot.":
        "Zoyenera kuchita mu Jupyter: Thamangani Q10(f) ndipo yang'anani kusintha kwa nthawi mu plot iliyonse ya residual.",
    "Code to use: Use the verified Q10(f) code cell.":
        "Code yoyenera kugwiritsa ntchito: Gwiritsani ntchito selo ya code ya Q10(f) yotsimikizidwa.",
    "Output to inspect: Schoenfeld residual plots, correlations with log(time), p-values and Holm-adjusted p-values.":
        "Zotuluka zoyenera kuyang'ana: Ma plot a Schoenfeld residual, kugwirizana ndi log(time), ma p-value ndi ma p-value osinthidwa ndi Holm.",
    "Important values or observations: Any significant time trend after multiplicity adjustment.":
        "Makhalidwe kapena zowoneratu zofunika: Kusintha kulikonse kwakukulu ndi nthawi pambuyo posintha kuyesa kangapo.",
    "How to interpret it: This statsmodels-based screen is an approximation, not an exact R cox.zph replacement.":
        "Momwe mungatanthauzire: Kuwunika kumeneku kochokera ku statsmodels ndi kuyerekeza, osati m'malo mwake wa R cox.zph.",
    "What to report: Report the diagnostic method, p-values and what a violation would imply.":
        "Zoyenera kunena mu lipoti: Nenani njira yowunikira, ma p-value ndi zomwe kuswa malingaliro kungatanthauze.",
    "Common mistakes to avoid: Declaring PH validated solely because one plot looks flat, or ignoring a clear time trend.":
        "Zolakwika zofunika kupewa: Kunena kuti PH yatsimikiziridwa chifukwa plot imodzi ikuoneka yathyathyathya, kapena kunyalanyaza kusintha koonekeratu ndi nthawi.",
}

# ---------------------------------------------------------------------------
# Exact report-template, audit and guide-field translations
# ---------------------------------------------------------------------------

TEXT_OVERRIDES: dict[str, str] = {}
TEXT_OVERRIDES.update(UI)
TEXT_OVERRIDES.update(LEARNING_OVERRIDES)

TEXT_OVERRIDES.update({
    "Estimate marginal probabilities": "Yerekezerani mwayi wamba",
    "Conditional probability and independence": "Mwayi wapamikhalidwe ndi kudziyimira pawokha",
    "Measurement scales": "Masikelo oyezera",
    "Descriptive summary with missingness": "Chidule chofotokoza ndi deta yosowa",
    "Distribution plots": "Ma plot a kugawa",
    "Correlation": "Correlation",
    "CI for a mean": "CI ya avareji",
    "CI for a prevalence": "CI ya kufala",
    "Interpret a confidence interval": "Tanthauzirani confidence interval",
    "Facility-specific estimates": "Zoyerekeza za malo aliwonse",
    "IPTp3 and birthweight": "IPTp3 ndi kulemera kwa mwana pakubadwa",
    "Paired blood-pressure test": "Mayeso a kuthamanga kwa magazi ophatikizidwa",
    "ANOVA and non-parametric comparison": "ANOVA ndi kuyerekeza kosagwiritsa ntchito parameter",
    "Education and anaemia": "Maphunziro ndi kuchepa kwa magazi",
    "Anaemia prevalence versus 30%": "Kufala kwa kuchepa kwa magazi poyerekeza ndi 30%",
    "Preterm proportions by anaemia": "Magawo a kubadwa msanga (preterm) potengera kuchepa kwa magazi",
    "Simple linear regression": "Linear regression yosavuta",
    "Multiple linear regression": "Multiple linear regression",
    "Linear regression diagnostics": "Kuwunika kwa linear regression",
    "Add facility type": "Onjezani mtundu wa malo",
    "Prediction with intervals": "Kulosera ndi ma interval",
    "Logistic regression": "Logistic regression",
    "Survival data description": "Kufotokoza deta ya nthawi mpaka chochitika",
    "Kaplan-Meier estimation": "Kuyerekeza kwa Kaplan-Meier",
    "Compare survival curves": "Yerekezerani ma curve a kupulumuka",
    "Exponential rate": "Mtengo wa exponential",
    "Cox proportional hazards": "Cox proportional hazards",
    "Proportional hazards check": "Kuwunika kwa proportional hazards",
    "Calculation": "Kuwerengera",
    "Conceptual": "Lingaliro",
    "Interpretation": "Kutanthauzira",
    "Mixed": "Kusakaniza",
    "Reporting": "Kunena zotsatira",
    "Yes": "Inde",
    "No": "Ayi",

    "Estimate P(preterm) and P(low birth weight) from anc_cohort.csv.":
        "Yerekezerani P(preterm) ndi P(low birth weight) kuchokera ku anc_cohort.csv.",
    "Run the Q1(a) cell and read the counts, denominators and sample proportions.":
        "Thamangani selo ya Q1(a) ndipo werengani kuchuluka, ma denominator ndi magawo a sample.",
    "Event counts, denominator 400 and the two sample proportions.":
        "Kuchuluka kwa zochitika, denominator 400 ndi magawo awiri a sample.",
    "Treat each proportion as an estimate with sampling variability; only a confidence interval quantifies that variability.":
        "Tengani gawo lililonse ngati kuyerekeza kokhala ndi kusiyana kwa sample; confidence interval yokha ndiyo imayesa kusiyana kumeneku.",
    "Report 'In the simulated ANC cohort, 47/400 (0.1175) were preterm and 43/400 (0.1075) had low birth weight.'":
        "Nenani kuti 'Mu gulu la kafukufuku wa ANC lofananizidwa, 47/400 (0.1175) anali obadwa msanga ndipo 43/400 (0.1075) anali ndi kulemera kochepa pakubadwa.'",
    "Confusing sample proportion with theoretical probability, or silently changing the denominator.":
        "Kusokoneza gawo la sample ndi mwayi wongolingalira, kapena kusintha denominator popanda kuwuza.",
})

TEXT_OVERRIDES.update({
    "In the simulated teaching cohort, {variable} had n={n} non-missing observations (mean={mean}, SD={sd}, median={median}, IQR={iqr}). {n_missing} records were missing.":
        "Mu gulu la kafukufuku lopangidwa kuchokera ku deta yofananizidwa, {variable} anali ndi n={n} zowoneratu zomwe zilipo (mean={mean}, SD={sd}, median={median}, IQR={iqr}). Zolemba {n_missing} zinali zosowa.",
    "The sample proportion of {event} was {x}/{n} = {p:.4f}. This estimates the underlying probability but is not itself a theoretical probability.":
        "Gawo la sample la {event} linali {x}/{n} = {p:.4f}. Izi zikuyerekeza mwayi weniweni, koma palokha si mwayi wongolingalira.",
    "{x} and {y} showed {strength} {direction} association (Pearson r={r}, p={p}; Spearman rho={rho}). Because the data are observational, this is not causal.":
        "{x} ndi {y} zinawonetsa ubale wa {strength} {direction} (Pearson r={r}, p={p}; Spearman rho={rho}). Chifukwa deta ndi yowunikira, ubalewu si wachifukwa.",
    "The estimated {parameter} was {estimate} with a 95% confidence interval of ({low}, {high}), computed using {method}.":
        "Mtengo woyerekeza wa {parameter} unali {estimate} ndi confidence interval ya 95% ya ({low}, {high}), wowerengedwa pogwiritsa ntchito {method}.",
    "Mean {outcome} was {mean1} in {group1} (n={n1}) and {mean2} in {group2} (n={n2}). Welch's t-test gave a mean difference of {diff} (95% CI {low} to {high}), t={t}, df={df}, p={p}.":
        "Avareji ya {outcome} inali {mean1} mu {group1} (n={n1}) ndi {mean2} mu {group2} (n={n2}). Welch's t-test inapereka kusiyana kwa avareji kwa {diff} (95% CI {low} kufika {high}), t={t}, df={df}, p={p}.",
    "Among {n} paired women, mean {outcome} changed by {change} (95% CI {low} to {high}); paired t={t}, p={p}.":
        "Mwa amayi {n} ogwirizanitsidwa, avareji ya {outcome} yasintha ndi {change} (95% CI {low} kufika {high}); paired t={t}, p={p}.",
    "One-way ANOVA comparing {outcome} across {groups} gave F({df_between},{df_within})={F}, p={p}. Tukey-adjusted pairwise comparisons are reported with 95% CIs and adjusted p-values.":
        "One-way ANOVA yoyerekeza {outcome} m'magulu {groups} inapereka F({df_between},{df_within})={F}, p={p}. Kuyerekeza kwa ma pair kosinthidwa ndi Tukey kumaperekedwa ndi 95% CIs ndi ma p-value osinthidwa.",
    "The association between {variable1} and {variable2} was examined in a {r}x{c} table (minimum expected count={min_expected}). Chi-square={chi2}, df={df}, p={p}.":
        "Ubale pakati pa {variable1} ndi {variable2} unayesedwa mu tebulo la {r}x{c} (kuchuluka kochepa koyembekezeredwa={min_expected}). Chi-square={chi2}, df={df}, p={p}.",
    "The observed proportion was {x}/{n}={p_hat:.4f}. Against the null value {p0}, {test} gave p={p_value}; the 95% {ci_method} interval was ({low}, {high}).":
        "Gawo lopezeka linali {x}/{n}={p_hat:.4f}. Poyerekeza ndi mtengo wa null {p0}, {test} inapereka p={p_value}; interval ya 95% {ci_method} inali ({low}, {high}).",
    "In the model {formula}, the adjusted coefficient for {term} was {coef} (95% CI {low} to {high}, p={p}). R-squared={r2} and adjusted R-squared={adj_r2}; n={n}.":
        "Mu chitsanzo {formula}, coefficient yosinthidwa ya {term} inali {coef} (95% CI {low} kufika {high}, p={p}). R-squared={r2} ndipo adjusted R-squared={adj_r2}; n={n}.",
    "In the logistic model {formula}, {term} had an adjusted odds ratio of {or} (95% CI {low} to {high}, p={p}). Odds ratios are not risk ratios; the data are observational.":
        "Mu chitsanzo cha logistic {formula}, {term} anali ndi adjusted odds ratio ya {or} (95% CI {low} kufika {high}, p={p}). Ma odds ratio si ma risk ratio; deta ndi yowunikira.",
    "Kaplan-Meier estimated event-free survival of {s1:.4f} at {t1} days (95% CI {l1} to {u1}) and {s2:.4f} at {t2} days (95% CI {l2} to {u2}). Median survival was {median}.":
        "Kaplan-Meier inayerekeza kupulumuka kopanda chochitika kwa {s1:.4f} pa masiku {t1} (95% CI {l1} kufika {u1}) ndi {s2:.4f} pa masiku {t2} (95% CI {l2} kufika {u2}). Median survival inali {median}.",
    "Survival curves differed by {grouping} (log-rank chi-square={chi2}, df={df}, p={p}). This unadjusted test does not establish causation.":
        "Ma curve a kupulumuka anasiyana ndi {grouping} (log-rank chi-square={chi2}, df={df}, p={p}). Kuyesa kosinthidwa kumeneku sikukhazikitsa chifukwa.",
    "There were {events} events over {person_time} person-days, giving a rate of {rate:.6f} per person-day ({rate1000:.2f} per 1,000 person-days; 95% CI {low} to {high}). This assumes a constant hazard.":
        "Panali zochitika {events} pa {person_time} person-days, zomwe zinapereka mtengo wa {rate:.6f} pa person-day ({rate1000:.2f} pa 1,000 person-days; 95% CI {low} kufika {high}). Izi zikuganiza kuti hazard ndi yosasinthika.",
    "In the Cox model {formula}, {term} had an adjusted hazard ratio of {hr} (95% CI {low} to {high}, p={p}). A hazard ratio is not a risk ratio.":
        "Mu chitsanzo cha Cox {formula}, {term} anali ndi adjusted hazard ratio ya {hr} (95% CI {low} kufika {high}, p={p}). Hazard ratio si risk ratio.",
})

TEXT_OVERRIDES.update({
    "All three CSVs load successfully.": "Mafayilo onse atatu a CSV atsegulidwa bwino.",
    "anc_cohort.csv is 400×14, bp_paired.csv is 60×3 and postpartum_survival.csv is 500×6.":
        "anc_cohort.csv ndi 400×14, bp_paired.csv ndi 60×3 ndipo postpartum_survival.csv ndi 500×6.",
    "Required columns are present.": "Mizati yofunikira ilipo.",
    "No expected analysis variable is absent. bp_paired.csv also contains an id column, which is useful for confirming the pairing.":
        "Palibe chinthu chofunikira chowunikira chomwe chikusowa. bp_paired.csv ilinso ndi mzati wa id, womwe ndi wothandiza kutsimikizira kufananizidwa kwa deta.",
    "Missingness is variable-specific.": "Kusowa kwa deta kumasiyana ndi chinthu chilichonse.",
    "ANC: education 55, bmi 10, hb 18, anaemia 18; all other ANC variables complete. BP and survival datasets have no missing values.":
        "ANC: education 55, bmi 10, hb 18, anaemia 18; zinthu zina zonse za ANC zili zathunthu. Deta ya BP ndi ya nthawi mpaka chochitika ilibe zosowa.",
    "Education uses a literal category name.": "Education imagwiritsa ntchito dzina la gulu lenileni.",
    "The 55 'None' values are a real education level, not missing data. The loader uses keep_default_na=False so pandas does not silently convert them to NaN.":
        "Makhalidwe 55 a 'None' ndi mlingo weniweni wa maphunziro, osati deta yosowa. Chosegera deta chimagwiritsa ntchito keep_default_na=False kuti pandas isawasinthe kukhala NaN popanda kuwuza.",
    "Binary coding is consistent.": "Kulemba kwa binary kuli kogwirizana.",
    "iptp3 uses Yes/No; preterm, low_bw and readmitted use 1/0 with the meanings stated in the practical.":
        "iptp3 imagwiritsa ntchito Yes/No; preterm, low_bw ndi readmitted zimagwiritsa ntchito 1/0 ndi matanthauzo omwe afotokozedwa mu practical.",
    "Anaemia and low birth weight are internally consistent.": "Kuchepa kwa magazi ndi kulemera kochepa pakubadwa zili zogwirizana mkati mwazo.",
    "(hb < 11) matches anaemia for all 382 evaluable records; (birthweight < 2500) matches low_bw for all 400 records.":
        "(hb < 11) ikugwirizana ndi kuchepa kwa magazi pa zolemba zonse 382 zoyesedwa; (birthweight < 2500) ikugwirizana ndi low_bw pa zolemba zonse 400.",
    "Preterm has a documented definition discrepancy.": "Preterm ili ndi kusiyana kwa tanthauzo komwe kwalembedwa.",
    "Nine records have gest_age between 36.1 and 36.8 weeks but preterm = 0. The supplied preterm flag is used as the primary outcome; interpret it as the recorded clinical flag, not an exact recoding of decimal gest_age.":
        "Zolemba zisanu ndi zinayi zili ndi gest_age pakati pa 36.1 ndi 36.8 masabata koma preterm = 0. Chizindikiro cha preterm choperekedwa chimagwiritsidwa ntchito ngati zotsatira zoyamba; chitanthauzireni ngati chizindikiro cha clinical cholembedwa, osati kusintha ndendende kwa decimal gest_age.",
    "No duplicate identifiers or duplicate rows were found.": "Palibe zizindikiro zobwerezabwereza kapena mizere yobwerezabwereza yomwe yapezeka.",
    "ANC ids W001–W400, BP ids B01–B60 and survival ids P001–P500 are unique.":
        "Ma id a ANC W001–W400, ma id a BP B01–B60 ndi ma id a nthawi mpaka chochitika P001–P500 ndi apadera.",
    "Outliers are plausible and retained.": "Ma outlier ndi oyenera ndipo asungidwa.",
    "Gestational age has a left tail, birthweight has a few low/high IQR outliers and BP has a few extreme measurements. They are inspected, not deleted.":
        "Zaka za mimba zili ndi mchira wakumanzere, kulemera kwa mwana pakubadwa kuli ndi ma outlier a IQR ochepa kumunsi/kumwamba ndipo BP ili ndi miyeso yochepa yopitilira malire. Zayang'aniridwa, osafufutidwa.",
    "These are simulated teaching data.": "Awa ndi deta yofananizidwa yophunzitsira.",
    "They are not real patient records and must not be used for clinical or public-health decisions.":
        "Si zolemba za odwala enieni ndipo siziyenera kugwiritsidwa ntchito popanga zisankho za zachipatala kapena za thanzi la anthu.",

    "Three unordered categories.": "Magulu atatu osalongosoka.",
    "Levels not verified": "Milingo sinatsimikizidwe",
    "Ordered attainment, but gaps are not numeric distances.":
        "Milingo yamaphunziro yalongosoka, koma mipata si mtunda wa manambala.",
    "Discrete count": "Kuchuluka kwa discrete",
    "Non-negative whole-number visit count.": "Kuchuluka kwa maulendo osachepera zero popanda decimal.",
    "Numeric column in the {anc_rows}-row ANC file.": "Mzati wa manambala mu fayilo ya ANC ya mizere {anc_rows}.",
    "Continuous": "Continuous",
    "Measured quantity with meaningful decimals.": "Kuchuluka koyezedwa komwe ma decimal ali ndi tanthauzo.",
    "10 missing values; summarise on 390 evaluable records.": "10 makhalidwe osowa; fotokozani pa zolemba 390 zoyesedwa.",
    "Complete for all {anc_rows} records.": "Yathunthu pa zolemba zonse {anc_rows}.",
    "Nominal": "Nominal",
    "Ordinal": "Ordinal",
    "See code cell ": "Onani selo ya code ",
    "Not required — conceptual/interpretation task.": "Sikofunikira — ntchito ya lingaliro kapena kutanthauzira.",
})

# ---------------------------------------------------------------------------
# Exact worked-report translations
# ---------------------------------------------------------------------------

TEXT_OVERRIDES.update({
    "In the simulated ANC cohort (n=400), 47/400 (0.1175) preterm delivery and 43/400 (0.1075) low birth weight. These are observed sample proportions from the recorded outcome flags, not known population probabilities.":
        "Mu gulu la kafukufuku wa ANC lofananizidwa (n=400), 47/400 (0.1175) kubadwa msanga ndi 43/400 (0.1075) kulemera kochepa pakubadwa. Izi ndi magawo a sample owonedwa kuchokera ku zizindikiro za zotsatira zolembedwa, osati mwayi wodziwika wa gulu lonse.",
    "Both outcome flags are complete for every record here. Do not switch to the smaller anaemia denominator used later.":
        "Zizindikiro zonse ziwiri za zotsatira zili zathunthu pa zolemba zonse apa. Musasinthire ku denominator yochepa ya kuchepa kwa magazi yomwe idzagwiritsidwa ntchito pambuyo pake.",

    "Low birth weight occurred in 14/47 (0.2979) preterm and 29/353 (0.0822) term births, compared with the marginal 43/400 = 0.1075. The risk difference is 0.2157 and the risk ratio is 3.63, so the events are not independent in these simulated data.":
        "Kulemera kochepa pakubadwa kunachitika mu 14/47 (0.2979) kubadwa msanga ndi 29/353 (0.0822) kubadwa pa nthawi, poyerekeza ndi 43/400 = 0.1075 wamba. Kusiyana kwa mwayi wachochitika ndi 0.2157 ndipo risk ratio ndi 3.63, choncho zochitikazo sizodziyimira pawokha mu deta yofananizidwai.",
    "Compare conditional with marginal proportions. Similarity in a sample is not proof of independence, and dependence is not causation.":
        "Yerekezerani magawo apamikhalidwe ndi wamba. Kufanana mu sample si umboni wa kudziyimira pawokha, ndipo kugwirizana si chifukwa.",

    "Haemoglobin used 382 non-missing values (mean 11.49 g/dL, SD 1.42, median 11.50, IQR 1.97); 18 records were missing. BMI had 10 missing values, whereas birthweight used all 400 records (mean 3,046.89 g, SD 442.44).":
        "Haemoglobin inagwiritsa ntchito makhalidwe 382 omwe alipo (mean 11.49 g/dL, SD 1.42, median 11.50, IQR 1.97); zolemba 18 zinali zosowa. BMI inali ndi makhalidwe 10 osowa, pamene kulemera kwa mwana pakubadwa kunagwiritsa ntchito zolemba zonse 400 (mean 3,046.89 g, SD 442.44).",
    "Report n beside each summary. The differing denominators explain why later anaemia analyses use fewer than the full cohort.":
        "Nenani n pafupi ndi chidule chilichonse. Ma denominator osiyana akufotokoza chifukwa chake kusanthula kwa kuchepa kwa magazi pambuyo pake kumagwiritsa ntchito ochepa kuposa gulu lonse.",

    "Birthweight was approximately symmetric (mean 3,046.89 g versus median 3,040.50 g; skewness -0.31) with 5 low and 1 high IQR outliers. Gestational age was left-skewed (mean 38.56 weeks versus median 39.20; skewness -1.94) with 36 low IQR outliers, consistent with the preterm tail.":
        "Kulemera kwa mwana pakubadwa kunalikutanthauza pafupi kofanana (mean 3,046.89 g poyerekeza ndi median 3,040.50 g; skewness -0.31) ndi ma outlier a IQR 5 kumunsi ndi 1 kumwamba. Zaka za mimba zinali zopendekerera kumanzere (mean 38.56 masabata poyerekeza ndi median 39.20; skewness -1.94) ndi ma outlier a IQR 36 kumunsi, mogwirizana ndi mchira wa kubadwa msanga.",
    "Describe shape, centre, spread and outliers before choosing later methods. Inspect flagged outliers rather than deleting them without a reason.":
        "Fotokozani mawonekedwe, pakati, kufalikira ndi ma outlier musanasankhe njira zotsatira. Yang'anani ma outlier omwe alembedwa m'malo mowafufuta popanda chifukwa.",

    "Gestational age and birthweight showed a positive association (Pearson r=0.365, 95% CI 0.277 to 0.447, p<0.0001; Spearman rho=0.331, p<0.0001; n=400). The rank-based estimate is close to the Pearson estimate, so a few extreme points are unlikely to explain the association.":
        "Zaka za mimba ndi kulemera kwa mwana pakubadwa zinawonetsa ubale wabwino (Pearson r=0.365, 95% CI 0.277 kufika 0.447, p<0.0001; Spearman rho=0.331, p<0.0001; n=400). Kuyerekeza kochokera ku masanjidwe kuli pafupi ndi koyerekeza kwa Pearson, choncho mfundo zochepa zapamwamba sizingafotokoze ubalewu.",
    "Report both coefficients and inspect the scatterplot first. An observational association is not evidence that gestational age causes birthweight.":
        "Nenani ma coefficient onse awiri ndipo yang'anani scatterplot poyamba. Ubale wowonedwa mu deta yowunikira si umboni kuti zaka za mimba zimayambitsa kulemera kwa mwana pakubadwa.",

    "Mean birthweight was 3,046.89 g (SD 442.44, n=400, df=399); SE = SD/sqrt(n) = 22.12 g and the critical t value is 1.966. The 95% t interval was 3,003.40 to 3,090.38 g, matching the SciPy endpoints 3,003.40 to 3,090.38 g.":
        "Avareji ya kulemera kwa mwana pakubadwa inali 3,046.89 g (SD 442.44, n=400, df=399); SE = SD/sqrt(n) = 22.12 g ndipo mtengo wa critical t ndi 1.966. Interval ya t ya 95% inali 3,003.40 kufika 3,090.38 g, yogwirizana ndi mapeto a SciPy 3,003.40 kufika 3,090.38 g.",
    "The interval targets the population mean, not the range of individual births. A 95% procedure has long-run coverage under its assumptions.":
        "Interval iyi imayang'ana avareji ya gulu lonse, osati malire a kubadwa kwa munthu aliyense. Njira ya 95% imaphimba kwa nthawi yaitali ngati malingaliro ake akwaniritsidwa.",

    "Anaemia prevalence was 139/382 = 0.3639 (36.39%), with 18 records excluded because anaemia was missing. The 95% Wilson interval was 31.72% to 41.33%.":
        "Kufala kwa kuchepa kwa magazi kunali 139/382 = 0.3639 (36.39%), ndi zolemba 18 zomwe zachotsedwa chifukwa deta ya kuchepa kwa magazi inalibe. Wilson interval ya 95% inali 31.72% kufika 41.33%.",
    "State the evaluable denominator and exclusions. The interval describes prevalence, not an individual woman's probability of anaemia.":
        "Nenani denominator woyesedwa ndi zolemba zomwe zachotsedwa. Interval iyi ikufotokoza kufala, osati mwayi wa mkazi mmodzi wokhala ndi kuchepa kwa magazi.",

    "Mean birthweight was Urban 3,110.44 g (n=154, 95% CI 3,038.47 to 3,182.41); Peri-urban 2,989.60 g (n=133, 95% CI 2,915.44 to 3,063.77); Rural 3,027.72 g (n=113, 95% CI 2,946.90 to 3,108.53). These separate intervals show precision within each facility group; overlap alone is not a formal test of equal means.":
        "Avareji ya kulemera kwa mwana pakubadwa inali Urban 3,110.44 g (n=154, 95% CI 3,038.47 kufika 3,182.41); Peri-urban 2,989.60 g (n=133, 95% CI 2,915.44 kufika 3,063.77); Rural 3,027.72 g (n=113, 95% CI 2,946.90 kufika 3,108.53). Ma interval olekanitsa awa akuonetsa kulondola mkati mwa gulu lililonse la malo; kudzigwirizana kokha si mayeso ovomerezeka a ma avareji ofanana.",
    "A formal comparison requires the model-based approach in Q6. Unequal subgroup sample sizes make interval widths hard to compare informally.":
        "Kuyerekeza kovomerezeka kumafuna njira yochokera ku chitsanzo ya Q6. Kukula kosafanana kwa magulu ang'ono kumapangitsa m'lifupi la ma interval kukhala lovuta kuyerekeza mwachisawawa.",

    "Mean birthweight was 3,125.79 g with IPTp3 Yes (n=243) and 2,924.78 g with No (n=157), a difference of 201.00 g (Yes minus No; Welch 95% CI 112.76 to 289.24; t=4.48, df=317.4, p<0.0001). Levene p=0.8128 and rank-sum p<0.0001 give context for the assumption check and sensitivity analysis.":
        "Avareji ya kulemera kwa mwana pakubadwa inali 3,125.79 g ndi IPTp3 Yes (n=243) ndi 2,924.78 g ndi No (n=157), kusiyana kwa 201.00 g (Yes kuchotsa No; Welch 95% CI 112.76 kufika 289.24; t=4.48, df=317.4, p<0.0001). Levene p=0.8128 ndi rank-sum p<0.0001 zimapereka nkhani yowunika malingaliro ndi kusanthula kwa sensitivity.",
    "Welch's test does not assume equal variances. Report the size and precision of the difference and keep the wording observational, not causal.":
        "Mayeso a Welch saganiza kuti ma variance ndi ofanana. Nenani kukula ndi kulondola kwa kusiyana ndipo sungani mawonekedwe owunikira, osati a chifukwa.",

    "Among 60 paired women, mean systolic blood pressure was 112.20 mmHg at booking and 115.87 mmHg at 36 weeks. The mean within-woman change was 3.67 mmHg (95% CI 1.36 to 5.98; paired t=3.17, p=0.0024), whereas the incorrect independent test gives p=0.0848 because it ignores the id linkage.":
        "Mwa amayi 60 ogwirizanitsidwa, avareji ya kuthamanga kwa magazi ya systolic inali 112.20 mmHg pa nthawi yolembetsa ndi 115.87 mmHg pa masabata 36. Kusintha kwapakati mkati mwa mkazi kunali 3.67 mmHg (95% CI 1.36 kufika 5.98; paired t=3.17, p=0.0024), pamene mayeso olakwika a magulu odziyimira pawokha umapereka p=0.0848 chifukwa unosyalanya kugwirizana kwa id.",
    "Analyse the 60 paired differences, not 120 independent observations. Shapiro-Wilk and the paired-difference plot support checking the t assumption.":
        "Unikani kusiyana 60 kwa deta yofananizidwa, osati zowoneratu 120 zodziyimira pawokha. Shapiro-Wilk ndi plot ya kusiyana kwa deta yofananizidwa zikuthandizira kuwunika malingaliro a t.",
})

TEXT_OVERRIDES.update({
    "One-way ANOVA comparing haemoglobin across facility type gave F(2,379)=11.36, p<0.0001; Levene p=0.0433 and Kruskal-Wallis H=18.54, p<0.0001. Tukey-adjusted pairwise differences were: Peri-urban minus Rural = -0.11 g/dL (95% CI -0.53 to 0.32, adjusted p=0.8222); Peri-urban minus Urban = 0.64 g/dL (95% CI 0.24 to 1.03, adjusted p=0.0005); Rural minus Urban = 0.75 g/dL (95% CI 0.33 to 1.16, adjusted p=0.0001).":
        "One-way ANOVA yoyerekeza haemoglobin potengera mtundu wa malo inapereka F(2,379)=11.36, p<0.0001; Levene p=0.0433 ndi Kruskal-Wallis H=18.54, p<0.0001. Kusiyana kwa ma pair kosinthidwa ndi Tukey kunali: Peri-urban kuchotsa Rural = -0.11 g/dL (95% CI -0.53 kufika 0.32, p yosinthidwa=0.8222); Peri-urban kuchotsa Urban = 0.64 g/dL (95% CI 0.24 kufika 1.03, p yosinthidwa=0.0005); Rural kuchotsa Urban = 0.75 g/dL (95% CI 0.33 kufika 1.16, p yosinthidwa=0.0001).",
    "Report the overall test before the adjusted contrasts. The rank-based test is an important sensitivity check because the variance test is borderline.":
        "Nenani mayeso onse musanapereke kusiyana kosinthidwa. Mayeso ochokera ku masanjidwe ndi kuwunika kofunikira kwa sensitivity chifukwa mayeso a variance ali pafupi ndi malire.",

    "Among women with both variables recorded, anaemia proportions were None: 24/53 (45.28% anaemia); Primary: 67/201 (33.33% anaemia); Secondary+: 48/128 (37.50% anaemia). The chi-square test gave chi2(2)=2.69, p=0.2605, with minimum expected count 19.29; there is no clear evidence of an association in these simulated data.":
        "Mwa amayi omwe zinthu zonse ziwiri zinalembedwa, magawo a kuchepa kwa magazi anali None: 24/53 (45.28% kuchepa kwa magazi); Primary: 67/201 (33.33% kuchepa kwa magazi); Secondary+: 48/128 (37.50% kuchepa kwa magazi). Mayeso a chi-square anapereka chi2(2)=2.69, p=0.2605, ndi kuchuluka kochepa koyembekezeredwa 19.29; palibe umboni womveka wa ubale mu deta yofananizidwai.",
    "All expected counts exceed the usual rule-of-thumb threshold of 5. A chi-square test assesses association; it does not show that education caused anaemia.":
        "Kuchuluka konse koyembekezeredwa kuposa malire wamba wa 5. Mayeso a chi-square amawunika ubale; sasonyeza kuti maphunziro anayambitsa kuchepa kwa magazi.",

    "Against the null prevalence 0.30, the observed 139/382 = 0.3639 gave an exact binomial p=0.0073; the 95% Wilson interval was 31.72% to 41.33%, which excludes the null. 18 records with missing anaemia were excluded.":
        "Poyerekeza ndi kufala kwa null 0.30, 139/382 = 0.3639 yowonedwa inapereka p yeniyeni ya binomial p=0.0073; Wilson interval ya 95% inali 31.72% kufika 41.33%, yomwe sikuphatikiza mtengo wa null. Zolemba 18 zokhala ndi deta yosowa ya kuchepa kwa magazi zachotsedwa.",
    "State H0, the evaluable denominator, the exact test and the interval together. The null value is a teaching hypothesis, not a clinical guideline.":
        "Nenani H0, denominator woyesedwa, mayeso enieni ndi interval pamodzi. Mtengo wa null ndi lingaliro lophunzitsira, osati malangizo a zachipatala.",

    "Preterm delivery occurred in Anaemia 25/139 (17.99%) and No anaemia 22/243 (9.05%), a risk difference of 8.93% (95% CI 1.97% to 16.75%; z=2.56, p=0.0106; Fisher p=0.0146). This is an unadjusted association in simulated data.":
        "Kubadwa msanga kunachitika mu Anaemia 25/139 (17.99%) ndi No anaemia 22/243 (9.05%), kusiyana kwa mwayi wachochitika kwa 8.93% (95% CI 1.97% kufika 16.75%; z=2.56, p=0.0106; Fisher p=0.0146). Uwu ndi ubale wosasinthidwa mu deta yofananizidwa.",
    "Both the large-sample test and Fisher's exact test address the same table. Do not phrase the difference as anaemia causing preterm delivery.":
        "Mayeso a zitsanzo zazikulu ndi a Fisher enieni onse amayankha tebulo lomwelo. Musafotokoze kusiyana ngati kuchepa kwa magazi kochititsa kubadwa msanga.",

    "In the simple linear model, each additional week of gestational age was associated with 65.64 g higher mean birthweight (95% CI 49.13 to 82.16, p<0.0001); n=400 and R-squared=0.133. The intercept (515.69 g at zero weeks) is outside the observed range.":
        "Mu chitsanzo chosavuta cha linear, sabata lililonse lowonjezera la zaka za mimba linkagwirizana ndi kulemera kwa mwana pakubadwa kokulirapo ndi 65.64 g (95% CI 49.13 kufika 82.16, p<0.0001); n=400 ndipo R-squared=0.133. Intercept (515.69 g pa masabata zero) ili kunja kwa malire owonedwa.",
    "Interpret the slope in grams per week with its interval. R-squared describes explained variation, not causation or individual prediction accuracy.":
        "Tanthauzirani slope mu magalamu pa sabata ndi interval yake. R-squared ikufotokoza kusiyana kofotokozedwa, osati chifukwa kapena kulondola kwa kulosera kwa munthu aliyense.",

    "In the adjusted model (n=390 after excluding 10 records with missing BMI), estimated mean birthweight differences were IPTp3 Yes versus No: 177.16 g (95% CI 94.46 to 259.86, p<0.0001); per additional week of gestational age: 57.40 g (95% CI 40.77 to 74.03, p<0.0001); per unit of BMI: 12.16 g (95% CI 1.76 to 22.55, p=0.0220); per additional ANC visit: 23.62 g (95% CI 2.46 to 44.77, p=0.0287). R-squared=0.183 and adjusted R-squared=0.174.":
        "Mu chitsanzo chosinthidwa (n=390 pambuyo pochotsa zolemba 10 zokhala ndi BMI yosowa), kusiyana kwa avareji ya kulemera kwa mwana pakubadwa kunali IPTp3 Yes poyerekeza ndi No: 177.16 g (95% CI 94.46 kufika 259.86, p<0.0001); pa sabata lililonse lowonjezera la zaka za mimba: 57.40 g (95% CI 40.77 kufika 74.03, p<0.0001); pa unit imodzi ya BMI: 12.16 g (95% CI 1.76 kufika 22.55, p=0.0220); pa ulendo uliwonse wowonjezera wa ANC: 23.62 g (95% CI 2.46 kufika 44.77, p=0.0287). R-squared=0.183 ndipo adjusted R-squared=0.174.",
    "Name the reference level 'IPTp3 No' and the complete-case denominator. Coefficients are conditional associations from observational data.":
        "Tchulani mlingo wotchulidwa 'IPTp3 No' ndi denominator ya deta yathunthu. Ma coefficient ndi ubale wapamikhalidwe ochokera ku deta yowunikira.",

    "For the Q8b model, Durbin-Watson=1.99, suggesting no obvious serial correlation. The largest Cook's distance was 0.049 against a 4/n screening threshold of 0.0103. The residual-versus-fitted, scale-location, Q-Q and influence plots must also be described in words because the numbers alone do not check linearity or normality.":
        "Pa chitsanzo cha Q8b, Durbin-Watson=1.99, kusonyeza kuti palibe kugwirizana koonekeratu kotsatira. Cook's distance yaikulu kwambiri inali 0.049 poyerekeza ndi malire owunikira a 4/n a 0.0103. Ma plot a residual-versus-fitted, scale-location, Q-Q ndi influence ayeneranso kufotokozedwa ndi mawonekedwe chifukwa manambala okha sakuwunika kusalunjika kapena normality.",
    "Cook's distance is a screen, not an automatic deletion rule. State what each plot shows and justify any decision about influential records.":
        "Cook's distance ndi chowunikira, osati lamulo lodzidzimutsa lofufutira. Nenani zomwe plot iliyonse ikuwonetsa ndipo perekani chifukwa pa chisankho chilichonse chokhudza zolemba zomwe zimakhudza kwambiri.",
})

TEXT_OVERRIDES.update({
    "Adding facility type to the Q8b model does not improve fit on the same complete cases (n=390): nested F with 2 numerator degrees of freedom=1.84, p=0.1594; AIC 5,787.02 versus 5,786.76 (change 0.26); adjusted R-squared 0.178 versus 0.174 (change 0.004).":
        "Kuwonjezera mtundu wa malo ku chitsanzo cha Q8b sikusintha kukwanira pa deta yathunthu yomweyo (n=390): nested F yokhala ndi 2 numerator degrees of freedom=1.84, p=0.1594; AIC 5,787.02 poyerekeza ndi 5,786.76 (kusintha 0.26); adjusted R-squared 0.178 poyerekeza ndi 0.174 (kusintha 0.004).",
    "Compare nested models only on the same sample, and weigh the block test, AIC and complexity together. A better fit is not a causal facility effect.":
        "Yerekezerani zitsanzo zokhazikika pa deta yomweyo yokha, ndipo ganizirani mayeso a gulu, AIC ndi zovuta pamodzi. Kukwanira bwino si zotsatira za chifukwa cha malo.",

    "For the hypothetical profile (gest_age 39 weeks, BMI 22, IPTp3 Yes, 5 ANC visits), the base model predicted mean birthweight 3,130.85 g (95% CI 3,078.57 to 3,183.13) and an individual prediction interval 2,340.97 to 3,920.73 g. With facility type added and Urban specified, the corresponding values were 3,175.03 g (mean CI 3,102.69 to 3,247.38) and 2,385.27 to 3,964.79 g.":
        "Pa mbiri yongoganizira (gest_age 39 masabata, BMI 22, IPTp3 Yes, maulendo 5 a ANC), chitsanzo choyambirira chinalosera kulemera kwa mwana pakubadwa kwa 3,130.85 g (95% CI 3,078.57 kufika 3,183.13) ndi prediction interval ya munthu mmodzi 2,340.97 kufika 3,920.73 g. Pambuyo powonjezera mtundu wa malo ndikutchula Urban, makhalidwe ofanana anali 3,175.03 g (CI ya avareji 3,102.69 kufika 3,247.38) ndi 2,385.27 kufika 3,964.79 g.",
    "A prediction interval is wider than the mean-response interval because it includes residual variation for one new observation. State which model generated each number.":
        "Prediction interval ndi yokulirapo kuposa interval ya yankho lapakati chifukwa imaphatikizapo kusiyana kwa residual kwa zowoneratu chatsopano cha munthu mmodzi. Nenani chitsanzo chomwe chinapanga nambala iliyonse.",

    "In the logistic model for the recorded preterm flag (n=382), adjusted odds ratios were anaemia OR 2.200 (95% CI 1.183 to 4.093, p=0.0127); each additional ANC visit OR 0.833 (95% CI 0.700 to 0.990, p=0.0385); each additional year of age OR 0.998 (95% CI 0.946 to 1.051, p=0.9274). Pseudo R-squared=0.038. At age 25 with 4 ANC visits, predicted preterm probability was 20.90% with anaemia versus 10.72% without.":
        "Mu chitsanzo cha logistic cha chizindikiro cha preterm cholembedwa (n=382), ma odds ratio osinthidwa anali kuchepa kwa magazi OR 2.200 (95% CI 1.183 kufika 4.093, p=0.0127); ulendo uliwonse wowonjezera wa ANC OR 0.833 (95% CI 0.700 kufika 0.990, p=0.0385); chaka chilichonse chowonjezera cha zaka OR 0.998 (95% CI 0.946 kufika 1.051, p=0.9274). Pseudo R-squared=0.038. Pa zaka 25 ndi maulendo 4 a ANC, mwayi woloseredwa wa kubadwa msanga unali 20.90% ndi kuchepa kwa magazi poyerekeza ndi 10.72% popanda.",
    "An odds ratio is not a risk ratio. The scenario probabilities translate the log-odds model back to the probability scale for teaching; they are not causal contrasts.":
        "Odds ratio si risk ratio. Mwayi wa zochitika umabweretsa chitsanzo cha log-odds ku sikelo ya mwayi kuti kuphunzitsa; si kusiyana kwa chifukwa.",

    "The survival file contains 500 women, with 209 readmission events and 291 censored observations (58.2%). Median observed follow-up was 119 days; that is a property of observation time, not an estimate of median readmission-free survival.":
        "Fayilo ya nthawi mpaka chochitika ili ndi amayi 500, okhala ndi zochitika 209 za kubwereranso kuchipitali ndi zowoneratu 291 zochepetsedwa (58.2%). Median yotsatira yowonedwa inali masiku 119; umu ndi mawonekedwe a nthawi yowonera, osati kuyerekeza kwa median yopulumuka popanda kubwereranso kuchipitali.",
    "Censored women contribute person-time up to their last observed time. Do not treat them as event-free at the end of study.":
        "Amayi ochepetsedwa amathandizira person-time mpaka nthawi yawo yomaliza yowonedwa. Musawagwire ngati opanda chochitika mpaka kumapeto kwa kafukufuku.",

    "Kaplan-Meier estimated readmission-free survival as 0.7637 at 90 days (95% CI 0.7225 to 0.7996) and 0.5894 at 180 days (95% CI 0.5377 to 0.6374). Median survival was 233 days (95% CI 202 to 260); 313 women remained at risk at day 90 and 152 at day 180.":
        "Kaplan-Meier inayerekeza kupulumuka popanda kubwereranso kuchipitali kwa 0.7637 pa masiku 90 (95% CI 0.7225 kufika 0.7996) ndi 0.5894 pa masiku 180 (95% CI 0.5377 kufika 0.6374). Median survival inali masiku 233 (95% CI 202 kufika 260); amayi 313 adakali pachiwopsezo pa tsiku 90 ndipo 152 pa tsiku 180.",
    "Median observed follow-up and median survival are different quantities. Numbers at risk show where the tail of the curve is least precise.":
        "Median yotsatira yowonedwa ndi median survival ndi zinthu zosiyana. Chiwerengero cha anthu pachiwopsezo chikusonyeza komwe mchira wa curve uli wosadziwika bwino.",
})

TEXT_OVERRIDES.update({
    "Kaplan-Meier curves differed by anaemia status (log-rank chi-square=22.57, df=1, p<0.0001); median readmission-free survival was Anaemia 169 days; No anaemia 311 days. The test compares the entire observed curve history, not only the medians.":
        "Ma curve a Kaplan-Meier anasiyana potengera kuchepa kwa magazi (log-rank chi-square=22.57, df=1, p<0.0001); median yopulumuka popanda kubwereranso kuchipitali inali Anaemia masiku 169; No anaemia masiku 311. Mayesowa akuyerekeza mbiri yonse ya curve yowonedwa, osati ma median okha.",
    "The log-rank test is unadjusted and observational. Q10e adds covariates and Q10f checks the proportional-hazards assumption.":
        "Mayeso a log-rank ndi osasintha komanso owunikira. Q10e imawonjezera ma covariate ndipo Q10f imawunika malingaliro a proportional-hazards.",

    "There were 209 readmissions over 68,841 person-days, giving a rate of 3.036 per 1,000 person-days (95% CI 2.638 to 3.477). Under the constant-hazard exponential model, S(90)=0.7609 and S(180)=0.5790; compare these with the non-parametric Kaplan-Meier estimates before relying on the model.":
        "Panali kubwereranso kuchipitali 209 pa 68,841 person-days, zomwe zinapereka mtengo wa 3.036 pa 1,000 person-days (95% CI 2.638 kufika 3.477). Pansi pa chitsanzo cha exponential cha hazard yosasinthika, S(90)=0.7609 ndi S(180)=0.5790; yerekezerani izi ndi zoyerekeza za Kaplan-Meier zosagwiritsa ntchito parameter musanadalire chitsanzocho.",
    "The rate is events per person-time, not events per person. A close match at two times supports descriptive agreement but does not prove a constant hazard.":
        "Mtengo wake ndi zochitika pa person-time, osati zochitika pa munthu. Kufanana kwapafupi pa nthawi ziwiri kumathandizira kugwirizana kofotokoza koma sikutsimikizira hazard yosasinthika.",

    "In the Cox model, adjusted hazard ratios were anaemia HR 1.89 (95% CI 1.44 to 2.49, p<0.0001) — higher hazard at fixed covariates; caesarean HR 1.57 (95% CI 1.18 to 2.10, p=0.0022) — higher hazard at fixed covariates; age HR 1.02 (95% CI 1.00 to 1.04, p=0.0816) — higher hazard at fixed covariates (analysis of 500 women and 209 events). Binary terms use the recorded reference categories printed in the notebook output.":
        "Mu chitsanzo cha Cox, ma hazard ratio osinthidwa anali kuchepa kwa magazi HR 1.89 (95% CI 1.44 kufika 2.49, p<0.0001) — hazard yapamwamba ma covariate atakhazikika; opaleshoni HR 1.57 (95% CI 1.18 kufika 2.10, p=0.0022) — hazard yapamwamba ma covariate atakhazikika; zaka HR 1.02 (95% CI 1.00 kufika 1.04, p=0.0816) — hazard yapamwamba ma covariate atakhazikika (kusanthula amayi 500 ndi zochitika 209). Ma binary amagwiritsa ntchito magulu otchulidwa omwe alembewa mu zotuluka za notebook.",
    "A hazard ratio is a relative instantaneous event rate, not a risk ratio. Report reference levels and the PH diagnostic before interpreting it.":
        "Hazard ratio ndi mtengo wachochitika wanthawi yomweyo wofananizira, osati risk ratio. Nenani milingo yotchulidwa ndi kuwunika kwa PH musanatanthauzire.",

    "The Schoenfeld-residual screen gave anaemia: Spearman rho=0.424, raw p<0.0001, Holm p<0.0001 (concern); caesarean: Spearman rho=0.501, raw p<0.0001, Holm p<0.0001 (concern); age: Spearman rho=-0.023, raw p=0.7358, Holm p=0.7358 (no flagged concern). A time trend remains for anaemia, caesarean after adjustment, so constant hazard ratios are questionable for those terms.":
        "Kuwunika kwa Schoenfeld residual kunapereka kuchepa kwa magazi: Spearman rho=0.424, p yaiwisi p<0.0001, Holm p<0.0001 (pali nkhawa); opaleshoni: Spearman rho=0.501, p yaiwisi p<0.0001, Holm p<0.0001 (pali nkhawa); zaka: Spearman rho=-0.023, p yaiwisi p=0.7358, Holm p=0.7358 (palibe nkhawa yalembedwa). Kusintha ndi nthawi kukadalipo kwa kuchepa kwa magazi ndi opaleshoni pambuyo posintha, choncho ma hazard ratio osasintha ndi okayikitsa pa nthawi zimenezo.",
    "This is a statsmodels screening approximation, not an exact R cox.zph reproduction. A violation suggests time-varying effects or stratification.":
        "Uku ndi kuyerekeza kowunikira kwa statsmodels, osati kutsanzira ndendende kwa R cox.zph. Kuswa malingaliro kukusonyeza zotsatira zosintha ndi nthawi kapena stratification.",
})

TEXT_OVERRIDES.update({
    "Estimate P(low birth weight | preterm) and P(low birth weight | term), then assess independence.":
        "Yerekezerani P(low birth weight | preterm) ndi P(low birth weight | term), kenaka muwone kudziyimira pawokha.",
    "Run Q1(b), inspect the conditional proportions and compare them with the marginal probability.":
        "Thamangani Q1(b), yang'anani magawo apamikhalidwe ndipo yerekezerani ndi mwayi wamba.",
    "Conditional proportions across the two preterm strata and the risk difference/ratio.":
        "Magawo apamikhalidwe m'magulu awiri a kubadwa msanga komanso kusiyana kwa mwayi wachochitika kapena risk ratio.",
    "If the conditional probabilities differ materially from each other and from the marginal probability, the events are not independent in this sample.":
        "Ngati mwayi wapamikhalidwe ukusiyana kwambiri wina ndi mnzake komanso ndi mwayi wamba, zochitikazo sizodziyimira pawokha mu sample iyi.",
    "Report each conditional probability and say whether they are close, with the observed risk difference.":
        "Nenani mwayi wapamikhalidwe uliwonse ndi fotokozani ngati uli pafupi, pamodzi ndi kusiyana kwa mwayi wachochitika kowonedwa.",
    "Using the wrong denominator, or treating similarity as proof of independence.":
        "Kugwiritsa ntchito denominator wolakwika, kapena kutenga kufanana ngati umboni wa kudziyimira pawokha.",

    "Classify facility_type, education, anc_visits, bmi and birthweight by measurement scale.":
        "Gawani facility_type, education, anc_visits, bmi ndi kulemera kwa mwana pakubadwa potengera sikelo yoyezera.",
    "Study the table; no analysis cell is required.": "Werengani tebulo; palibe selo yowunikira yofunikira.",
    "The classification table only.": "Tebulo la magulu lokha.",
    "Measurement scale guides the choice of summaries, plots and statistical models.":
        "Sikelo yoyezera imatsogolera kusankha chidule, ma plot ndi zitsanzo za ziwerengero.",
    "Use the table language, but write the justification yourself.":
        "Gwiritsani ntchito mawonekedwe a tebulo, koma lembani chifukwacho nokha.",
    "Calling a numeric count continuous, or assuming ordered categories are numeric distances.":
        "Kunena kuti kuchuluka kwa manambala ndi continuous, kapena kuganiza kuti magulu olongosoka ndi mtunda wa manambala.",

    "Summarise age, bmi, hb, gest_age and birthweight with n, missing, mean, SD, median and IQR.":
        "Fotokozani mwachidule age, bmi, hb, gest_age ndi kulemera kwa mwana pakubadwa ndi n, zosowa, avareji, SD, median ndi IQR.",
    "Run Q2(b) and compare the non-missing counts across variables.":
        "Thamangani Q2(b) ndipo yerekezerani kuchuluka kwa zomwe zilipo pakati pa zinthu.",
    "The six-column summary table, especially the differing n values.":
        "Tebulo lachidule la mizati isanu ndi umodzi, makamaka makhalidwe a n osiyana.",
    "Where missingness differs, comparisons across summaries must acknowledge the different denominators.":
        "Kumene kusowa kwa deta kuli kosiyanasiyana, kuyerekeza pakati pa zidule za deta kuyenera kuvomereza ma denominator osiyana.",
    "Report a compact table and explicitly state where the sample size differs.":
        "Nenani tebulo lofupika ndipo fotokozani momveka bwino kumene kukula kwa sample kuli kosiyanasiyana.",
    "Using mean without SD, or omitting the missing-data count.":
        "Kugwiritsa ntchito avareji popanda SD, kapena kusiya chiwerengero cha deta yosowa.",

    "Plot and describe the distributions of birthweight and gest_age.":
        "Pangani ma plot ndipo fotokozani kugawa kwa kulemera kwa mwana pakubadwa ndi gest_age.",
    "Run Q2(c), inspect both histograms/KDE curves and the summary table.":
        "Thamangani Q2(c), yang'anani ma histogramu ndi ma curve a KDE onse awiri komanso tebulo lachidule.",
    "Both plots and the distribution summary table.": "Ma plot onse awiri ndi tebulo lachidule la kugawa.",
    "A pronounced tail or marked mean-median gap weakens a normal approximation; robust methods may help.":
        "Mchira woonekeratu kapena kusiyana kwakukulu pakati pa avareji ndi median kumafooketsa kuyerekeza kwa normal; njira zolimba zingathandize.",
    "Write a short paragraph for each variable describing shape, outliers and mean versus median.":
        "Lembani ndime yaifupi pa chinthu chilichonse yofotokoza mawonekedwe, ma outlier ndi avareji poyerekeza ndi median.",
    "Calling every skew 'severe', or ignoring a visible tail.":
        "Kunena kuti kupendekera kulikonse ndi 'koopsa', kapena kunyalanyaza mchira wowoneka.",

    "Examine the relationship between gest_age and birthweight with a scatterplot and two correlations.":
        "Unikani ubale pakati pa gest_age ndi kulemera kwa mwana pakubadwa pogwiritsa ntchito scatterplot ndi ma correlation awiri.",
    "Run Q2(d), inspect the scatterplot and compare Pearson and Spearman estimates.":
        "Thamangani Q2(d), yang'anani scatterplot ndipo yerekezerani zoyerekeza za Pearson ndi Spearman.",
    "Scatterplot and both correlation coefficients.": "Scatterplot ndi ma coefficient onse awiri a correlation.",
    "A strong positive association means longer gestation tends to accompany higher birthweight in these data; it is not causal proof.":
        "Ubale wabwino wamphamvu ukutanthauza kuti mimba yayitali imakonda kutsagana ndi kulemera kukulu kwa mwana mu deta iyi; si umboni wa chifukwa.",
    "Report the coefficient(s), p-values if required, and a contextual sentence.":
        "Nenani ma coefficient, ma p-value ngati afunikira, ndi chiganizo chogwirizana ndi nkhaniyi.",
    "Saying correlation proves that gestational age causes birthweight.":
        "Kunena kuti correlation imatsimikizira kuti zaka za mimba zimayambitsa kulemera kwa mwana pakubadwa.",

    "Calculate and verify the 95% CI for mean birthweight using the t distribution.":
        "Werengani ndipo tsimikizirani CI ya 95% ya avareji ya kulemera kwa mwana pakubadwa pogwiritsa ntchito kugawa kwa t.",
    "Run Q3(a) and confirm the manual and SciPy endpoints match.":
        "Thamangani Q3(a) ndipo tsimikizirani kuti mapeto opangidwa pamanja ndi a SciPy akugwirizana.",
    "All intermediate quantities and matching endpoints.": "Kuchuluka konse kwapakati ndi mapeto ogwirizana.",
    "A 95% confidence procedure captures the true mean in 95% of repeated samples under its assumptions.":
        "Njira ya confidence ya 95% imaphimba avareji yeniyeni mu 95% ya zitsanzo zobwerezedwa ngati malingaliro ake akwaniritsidwa.",
    "Report the interval with the sample mean and state the confidence level correctly.":
        "Nenani interval pamodzi ndi avareji ya sample ndipo fotokozani mulingo wa confidence molondola.",
    "The common '95% probability the fixed interval contains the mean' misinterpretation.":
        "Kutanthauzira kolakwika kofala kwa 'mwayi wa 95% kuti interval yokhazikika ili ndi avareji'.",

    "Estimate anaemia prevalence and a 95% binomial confidence interval.":
        "Yerekezerani kufala kwa kuchepa kwa magazi ndi confidence interval ya binomial ya 95%.",
    "Run Q3(b) and note the eligible denominator and excluded records.":
        "Thamangani Q3(b) ndipo lembani denominator woyenera ndi zolemba zomwe zachotsedwa.",
    "Numerator, denominator, prevalence and Wilson CI.": "Numerator, denominator, kufala ndi Wilson CI.",
    "The interval reflects binomial sampling variability among evaluable records.":
        "Interval iyi ikuwonetsa kusiyana kwa sample ya binomial pakati pa zolemba zoyesedwa.",
    "State the prevalence with numerator, denominator and interval method.":
        "Nenani kufala ndi numerator, denominator ndi njira ya interval.",
    "Hiding the 18 missing observations.": "Kubisa zowoneratu 18 zosowa.",

    "Explain confidence intervals, precision and the effect of a fourfold sample size.":
        "Fotokozani ma confidence interval, kulondola ndi zotsatira za kukulitsa sample kanayi.",
    "Read the guidance and write your answer; no new code is required.":
        "Werengani malangizo ndipo lembani yankho lanu; palibe code yatsopano yofunikira.",
    "No new output; interpret earlier intervals.": "Palibe zotuluka zatsopano; tanthauzirani ma interval akale.",
    "Confidence describes procedure reliability across repeated samples, not posterior probability for one fixed interval.":
        "Confidence imafotokoza kudalirika kwa njira mu zitsanzo zobwerezedwa, osati mwayi wa posterior wa interval imodzi yokhazikika.",
    "Use the template but write the interpretation in your own words.":
        "Gwiritsani ntchito template koma lembani kutanthauzira ndi mawonekedwe anu.",
    "The '95% chance the true value is in this interval' wording.":
        "Mawonekedwe a 'mwayi wa 95% kuti mtengo weniyeni uli mu interval iyi'.",

    "Estimate mean birthweight and 95% CIs by facility type and compare them visually.":
        "Yerekezerani avareji ya kulemera kwa mwana pakubadwa ndi 95% CIs potengera mtundu wa malo ndipo yerekezerani maso.",
    "Run Q3(d), inspect the table and the point estimate/CI plot.":
        "Thamangani Q3(d), yang'anani tebulo ndi plot ya point estimate kapena CI.",
    "Three subgroup estimates with CIs and the comparison plot.":
        "Zoyerekeza zitatu za magulu ang'ono ndi CIs ndi plot yoyerekeza.",
    "Subgroup CIs show precision; a formal comparison requires an appropriate model or test.":
        "Ma CI a magulu ang'ono akuonetsa kulondola; kuyerekeza kovomerezeka kumafuna chitsanzo kapena mayeso oyenera.",
    "Report the three estimates and avoid a definitive equality/difference claim from overlap alone.":
        "Nenani zoyerekeza zitatu ndipo pewani kunena kuti zofanana kapena zosiyana ndendende potengera kudzigwirizana kokha.",
    "Treating overlapping CIs as proof of no difference.":
        "Kutenga ma CI odzigwirizana ngati umboni wakuti palibe kusiyana.",

    "Compare birthweight between IPTp3 Yes and No groups using Welch's t-test and a rank-sum analysis.":
        "Yerekezerani kulemera kwa mwana pakubadwa pakati pa magulu a IPTp3 Yes ndi No pogwiritsa ntchito Welch's t-test ndi kusanthula kwa rank-sum.",
    "Run Q4, inspect group summaries, plots, Levene, Welch and Wilcoxon outputs.":
        "Thamangani Q4, yang'anani chidule cha magulu, ma plot ndi zotuluka za Levene, Welch ndi Wilcoxon.",
    "All group, assumption-check and test outputs.":
        "Zotuluka zonse za magulu, kuwunika malingaliro ndi mayeso.",
    "Focus on the size and precision of the mean difference, not only the p-value.":
        "Yang'ananani kukula ndi kulondola kwa kusiyana kwa avareji, osati p-value yokha.",
    "Use the independent-groups template and add the observational limitation.":
        "Gwiritsani ntchito template ya magulu odziyimira pawokha ndipo onjezani malire a deta yowunikira.",
    "Using Student's pooled t-test despite unequal variances, or making a causal claim.":
        "Kugwiritsa ntchito Student's pooled t-test ngakhale ma variance osafanana, kapena kunena za chifukwa.",
})

TEXT_OVERRIDES.update({
    "Compare booking and 36-week systolic BP using a paired analysis.":
        "Yerekezerani BP ya systolic pa nthawi yolembetsa ndi pa masabata 36 pogwiritsa ntchito kusanthula kwa deta yofananizidwa.",
    "Run Q5, inspect the paired difference plot, normality check and paired t result.":
        "Thamangani Q5, yang'anani plot ya kusiyana kwa deta yofananizidwa, kuwunika normality ndi zotsatira za paired t.",
    "Paired difference output and the contrast with the incorrect independent test.":
        "Zotuluka za kusiyana kwa deta yofananizidwa ndi kuyerekeza ndi mayeso olakwika a magulu odziyimira pawokha.",
    "The paired test asks whether the mean within-person difference differs from zero.":
        "Mayeso ophatikizidwa amafunsa ngati kusiyana kwapakati mkati mwa munthu kuli kosiyana ndi zero.",
    "Report booking mean, 36-week mean, mean change, CI and p-value.":
        "Nenani avareji ya nthawi yolembetsa, avareji ya masabata 36, kusintha kwa avareji, CI ndi p-value.",
    "Treating 120 observations as independent when there are only 60 women.":
        "Kutenga zowoneratu 120 ngati zodziyimira pawokha pamene pali amayi 60 okha.",

    "Compare haemoglobin across facility types with ANOVA, Tukey HSD and Kruskal-Wallis.":
        "Yerekezerani haemoglobin m'magulu a mtundu wa malo pogwiritsa ntchito ANOVA, Tukey HSD ndi Kruskal-Wallis.",
    "Run Q6, inspect assumptions, overall tests and adjusted pairwise comparisons.":
        "Thamangani Q6, yang'anani malingaliro, mayeso onse ndi kuyerekeza kwa ma pair kosinthidwa.",
    "All ANOVA, diagnostic and post-hoc outputs.": "Zotuluka zonse za ANOVA, zowunikira ndi post-hoc.",
    "Use the overall test to justify post-hoc comparisons and report adjusted p-values.":
        "Gwiritsani ntchito mayeso onse kuti mutsimikizire kuyerekeza kwa post-hoc ndipo nenani ma p-value osinthidwa.",
    "Report F, df, p, then Tukey differences with CIs and adjusted p-values where relevant.":
        "Nenani F, df, p, kenaka kusiyana kwa Tukey ndi CIs ndi ma p-value osinthidwa pakafunika.",
    "Treating each pairwise comparison as an independent primary question.":
        "Kutenga kuyerekeza kulikonse kwa ma pair ngati funso loyamba lodziyimira pawokha.",

    "Examine the association between education and anaemia with a contingency table and chi-square test.":
        "Unikani ubale pakati pa maphunziro ndi kuchepa kwa magazi pogwiritsa ntchito tebulo la contingency ndi mayeso a chi-square.",
    "Run Q7(a), inspect counts, percentages, expected counts and the chi-square result.":
        "Thamangani Q7(a), yang'anani kuchuluka, magawo, kuchuluka koyembekezeredwa ndi zotsatira za chi-square.",
    "Observed/expected tables and chi-square output.":
        "Matebulo owonedwa ndi oyembekezeredwa ndi zotuluka za chi-square.",
    "Large deviations from expected counts indicate association; the p-value quantifies evidence against independence.":
        "Kusiyana kwakukulu kuchokera ku kuchuluka koyembekezeredwa kukusonyeza ubale; p-value imayesa umboni wotsutsana ndi kudziyimira pawokha.",
    "Report counts, percentages and the chi-square result with assumptions.":
        "Nenani kuchuluka, magawo ndi zotsatira za chi-square pamodzi ndi malingaliro.",
    "Ignoring small expected counts or claiming causation.":
        "Kunyalanyaza kuchuluka kochepa koyembekezeredwa kapena kunena za chifukwa.",

    "Test whether observed anaemia prevalence differs from a hypothesised 30%.":
        "Yesani ngati kufala kwa kuchepa kwa magazi kowonedwa kuli kosiyana ndi 30% yongoganizira.",
    "Run Q7(b) and read the exact binomial test and Wilson interval.":
        "Thamangani Q7(b) ndipo werengani mayeso enieni a binomial ndi Wilson interval.",
    "Exact binomial p-value and Wilson CI.": "p-value yeniyeni ya binomial ndi Wilson CI.",
    "If the null value lies outside the interval, the two-sided test will typically be significant.":
        "Ngati mtengo wa null uli kunja kwa interval, mayeso a mbali ziwiri nthawi zambiri amakhala ofunika.",
    "Report the test and interval together with the direction of the difference.":
        "Nenani mayeso ndi interval pamodzi ndi komwe kusiyana kukupita.",
    "Forgetting to state the null hypothesis or using the wrong denominator.":
        "Kuiwala kunena mfundo ya null kapena kugwiritsa ntchito denominator wolakwika.",

    "Compare preterm delivery proportions between anaemic and non-anaemic women.":
        "Yerekezerani magawo a kubadwa msanga (preterm) pakati pa amayi omwe ali ndi kuchepa kwa magazi ndi omwe alibe.",
    "Run Q7(c), inspect group counts, difference CI and test p-values.":
        "Thamangani Q7(c), yang'anani kuchuluka kwa magulu, CI ya kusiyana ndi ma p-value a mayeso.",
    "Group table, difference, CI and p-values.": "Tebulo la magulu, kusiyana, CI ndi ma p-value.",
    "A positive difference means preterm was more common in the anaemia group in this sample.":
        "Kusiyana kwabwino kukutanthauza kuti preterm kunali kofala kwambiri m'gulu la kuchepa kwa magazi mu sample iyi.",
    "Use the proportion-test template and add a non-causal interpretation.":
        "Gwiritsani ntchito template ya mayeso a gawo ndipo onjezani kutanthauzira kosanena za chifukwa.",
    "Saying anaemia caused preterm delivery.": "Kunena kuti kuchepa kwa magazi kunayambitsa kubadwa msanga (preterm).",

    "Fit birthweight ~ gest_age and interpret slope, intercept and R-squared.":
        "Kwaniritsani birthweight ~ gest_age ndipo tanthauzirani slope, intercept ndi R-squared.",
    "Run Q8(a), inspect the coefficient table and regression plot.":
        "Thamangani Q8(a), yang'anani tebulo la coefficient ndi plot ya regression.",
    "Coefficient table, R-squared and plot.": "Tebulo la coefficient, R-squared ndi plot.",
    "A one-week increase in gestational age is associated with about the fitted slope increase in mean birthweight.":
        "Kuwonjezeka kwa sabata imodzi ya zaka za mimba kumagwirizana ndi kuwonjezeka kopangidwa ndi slope kwa avareji ya kulemera kwa mwana pakubadwa.",
    "Report the slope in grams per week with CI and p-value.":
        "Nenani slope mu magalamu pa sabata ndi CI ndi p-value.",
    "Extrapolating to gestational age zero or claiming causality.":
        "Kutambasula zotsatira mpaka zaka za mimba zero kapena kunena za chifukwa.",

    "Fit birthweight ~ gest_age + bmi + iptp3 + anc_visits with categorical handling.":
        "Kwaniritsani birthweight ~ gest_age + bmi + iptp3 + anc_visits ndipo samalirani magulu a categorical.",
    "Run Q8(b), inspect complete-case size and adjusted coefficients.":
        "Thamangani Q8(b), yang'anani kukula kwa deta yathunthu ndi ma coefficient osinthidwa.",
    "Adjusted coefficient table and model fit statistics.":
        "Tebulo la coefficient yosinthidwa ndi ziwerengero zokwanira za chitsanzo.",
    "Conditional on the other predictors, each coefficient describes the associated change in mean birthweight.":
        "Poganizira zinthu zina zolosera, coefficient iliyonse ikufotokoza kusintha kogwirizana kwa avareji ya kulemera kwa mwana pakubadwa.",
    "Use the regression template with explicit reference levels.":
        "Gwiritsani ntchito template ya regression ndi milingo yotchulidwa momveka bwino.",
    "Forgetting which category is the reference or ignoring missing-data exclusions.":
        "Kuiwala gulu liti lomwe litchulidwa kapena kunyalanyaza zolemba zosowa zomwe zachotsedwa.",
})

TEXT_OVERRIDES.update({
    "Assess linearity, residual normality, homoscedasticity, independence and influence.":
        "Unikani kusalunjika, normality ya residual, homoscedasticity, kudziyimira pawokha ndi mphamvu ya zolemba.",
    "Run Q8(c) and interpret each of the four diagnostic panels.":
        "Thamangani Q8(c) ndipo tanthauzirani gulu lililonse la ma plot owunikira anayi.",
    "Four plots plus numeric influence summary.": "Ma plot anayi ndi chidule cha manambala cha mphamvu ya zolemba.",
    "Diagnostics guide model trustworthiness and possible refinement; they are not mechanical pass/fail tests.":
        "Kuwunika kumatsogolera kudalirika kwa chitsanzo ndi kusintha komwe kungachitike; si mayeso a makina a kudutsa kapena kulephera.",
    "Describe each plot briefly and state any limitation.":
        "Fotokozani plot iliyonse mwachidule ndipo nenani zolephera zilizonse.",
    "Treating a single high Cook's D as automatic proof of an error.":
        "Kutenga Cook's D imodzi yokwera ngati umboni wokha wokhala ndi cholakwika.",

    "Extend the regression with facility_type and compare nested models.":
        "Wonjezerani regression ndi facility_type ndipo yerekezerani zitsanzo zokhazikika.",
    "Run Q8(d) and compare the F test, AIC and adjusted R-squared on the same complete cases.":
        "Thamangani Q8(d) ndipo yerekezerani mayeso a F, AIC ndi adjusted R-squared pa deta yathunthu yomweyo.",
    "Nested F test, AIC and adjusted R-squared.": "Nested F test, AIC ndi adjusted R-squared.",
    "A small p-value suggests the added facility terms explain extra variation in this sample.":
        "p-value yochepa ikusonyeza kuti nthawi za malo zomwe zinawonjezeredwa zikufotokoza kusiyana kowonjezera mu sample iyi.",
    "Report F, df, p, AIC difference and adjusted R-squared difference.":
        "Nenani F, df, p, kusintha kwa AIC ndi kusintha kwa adjusted R-squared.",
    "Claiming the facility coefficient is causal.": "Kunena kuti coefficient ya malo ndi ya chifukwa.",

    "Predict birthweight for BMI=22, ANC=5, IPTp3=Yes, gest_age=39 and explain interval types.":
        "Loserani kulemera kwa mwana pakubadwa kwa BMI=22, ANC=5, IPTp3=Yes, gest_age=39 ndipo fotokozani mitundu ya interval.",
    "Run Q8(e) and compare the mean-response CI with the individual prediction interval.":
        "Thamangani Q8(e) ndipo yerekezerani CI ya yankho lapakati ndi prediction interval ya munthu aliyense.",
    "Prediction table for both models.": "Tebulo la zolosera la zitsanzo zonse ziwiri.",
    "The prediction interval is wider because it adds uncertainty for a new individual observation.":
        "Prediction interval ndi yokulirapo chifukwa imawonjezera kusatsimikizika kwa zowoneratu chatsopano cha munthu aliyense.",
    "Report the point prediction, mean CI and individual PI with the model used.":
        "Nenani zolosera pa mfundo, CI ya avareji ndi PI ya munthu aliyense pamodzi ndi chitsanzo chomwe chinagwiritsidwa ntchito.",
    "Calling the prediction interval a confidence interval for the mean.":
        "Kunena kuti prediction interval ndi confidence interval ya avareji.",

    "Fit preterm ~ age + anaemia + anc_visits, report odds ratios and model-based predictions.":
        "Kwaniritsani preterm ~ age + anaemia + anc_visits, nenani ma odds ratio ndi zolosera zochokera ku chitsanzo.",
    "Run Q9, inspect coefficients/odds ratios, scenario probabilities and the prediction plot.":
        "Thamangani Q9, yang'anani ma coefficient kapena odds ratio, mwayi wa zochitika ndi plot ya zolosera.",
    "Coefficient/OR table, scenario probabilities and plot.":
        "Tebulo la coefficient kapena OR, mwayi wa zochitika ndi plot.",
    "An OR above 1 means higher odds of preterm for the exposed group at fixed age and ANC visits.":
        "OR yoposa 1 ikutanthauza mwayi wokulirapo wa kubadwa msanga kwa gulu lokhudzidwa zaka ndi maulendo a ANC zitakhazikika.",
    "Use the logistic template and explicitly compare odds with probability.":
        "Gwiritsani ntchito template ya logistic ndipo yerekezerani odds ndi mwayi momveka bwino.",
    "Ignoring the 18 missing anaemia records or saying OR=2 means double the risk.":
        "Kunyalanyaza zolemba 18 zosowa za kuchepa kwa magazi kapena kunena kuti OR=2 kutanthauza kuwirikiza mwayi.",

    "Describe participants, events, censoring and distinguish follow-up time from survival time.":
        "Fotokozani otenga nawo mbali, zochitika, censoring ndi siyanitsani nthawi yotsatira ndi nthawi yopulumuka.",
    "Run Q10(a) and state the event/censoring counts clearly.":
        "Thamangani Q10(a) ndipo nenani kuchuluka kwa zochitika kapena censoring momveka bwino.",
    "Counts, censoring proportion and median observed follow-up.":
        "Kuchuluka, gawo la censoring ndi median yotsatira yowonedwa.",
    "Censored records contribute person-time up to their last known time but no event.":
        "Zolemba zochepetsedwa zimathandizira person-time mpaka nthawi yawo yomaliza yodziwika koma osapereka chochitika.",
    "Report the descriptive survival-data summary with careful terminology.":
        "Nenani chidule chofotokoza deta ya nthawi mpaka chochitika pogwiritsa ntchito mawonekedwe osamala.",
    "Treating censored observations as event-free at the end of study.":
        "Kutenga zowoneratu zochepetsedwa ngati zopanda chochitika mpaka kumapeto kwa kafukufuku.",

    "Estimate the survival curve, CIs, S(90), S(180) and median survival where estimable.":
        "Yerekezerani curve ya kupulumuka, ma CI, S(90), S(180) ndi median survival pamene ingayerekezedwe.",
    "Run Q10(b), inspect the step curve, confidence band, risk table and numeric estimates.":
        "Thamangani Q10(b), yang'anani curve ya sitepe, gulu la confidence, tebulo la chiwopsezo ndi zoyerekeza za manambala.",
    "KM plot, CIs, risk table and numeric survival estimates.":
        "KM plot, ma CI, tebulo la chiwopsezo ndi zoyerekeza za kupulumuka ndi manambala.",
    "A higher curve means a higher estimated probability of remaining readmission-free to that time.":
        "Curve yokulirapo ikutanthauza mwayi wokulirapo woyerekeza wokhalabe wopanda kubwereranso kuchipitali mpaka nthawi imeneyo.",
    "Use the Kaplan-Meier template with time-specific estimates.":
        "Gwiritsani ntchito template ya Kaplan-Meier ndi zoyerekeza za nthawi inayake.",
    "Reading a point on the curve as an individual's guaranteed outcome.":
        "Kuwerenga mfundo ya curve ngati zotsatira zotsimikizika za munthu aliyense.",

    "Compare Kaplan-Meier curves by anaemia status and perform a log-rank test.":
        "Yerekezerani ma curve a Kaplan-Meier potengera kuchepa kwa magazi ndipo chamangani mayeso a log-rank.",
    "Run Q10(c), inspect both curves and the log-rank result.":
        "Thamangani Q10(c), yang'anani ma curve onse awiri ndi zotsatira za log-rank.",
    "Stratified KM plot and log-rank output.": "KM plot yogawidwa ndi zotuluka za log-rank.",
    "A small p-value suggests different readmission-free survival distributions between groups.":
        "p-value yochepa ikusonyeza kugawa kosiyana kwa kupulumuka popanda kubwereranso kuchipitali pakati pa magulu.",
    "Use the log-rank template and avoid causal wording.":
        "Gwiritsani ntchito template ya log-rank ndipo pewani mawonekedwe a chifukwa.",
    "Claiming anaemia caused the difference based on an unadjusted curve comparison.":
        "Kunena kuti kuchepa kwa magazi kunayambitsa kusiyana potengera kuyerekeza ma curve kosasintha.",
})

TEXT_OVERRIDES.update({
    "Estimate the constant-hazard rate from events and person-time.":
        "Yerekezerani mtengo wa hazard yosasinthika kuchokera ku zochitika ndi person-time.",
    "Run Q10(d) and compare exponential survival with the KM estimates.":
        "Thamangani Q10(d) ndipo yerekezerani kupulumuka kwa exponential ndi zoyerekeza za KM.",
    "Person-time, rate, CI and exponential-versus-KM comparison.":
        "Person-time, mtengo, CI ndi kuyerekeza kwa exponential ndi KM.",
    "A close numerical match at selected times supports descriptive agreement, not proof of constant hazard.":
        "Kufanana kwa manambala pa nthawi zosankhidwa kumathandizira kugwirizana kofotokoza, osati umboni wa hazard yosasinthika.",
    "Use the exponential-rate template with the assumption stated.":
        "Gwiritsani ntchito template ya mtengo wa exponential ndi malingaliro omwe afotokozedwa.",
    "Treating the rate as a probability or ignoring censoring.":
        "Kutenga mtengo ngati mwayi kapena kunyalanyaza censoring.",

    "Fit readmitted ~ anaemia + delivery_mode + age and interpret adjusted hazard ratios.":
        "Kwaniritsani readmitted ~ anaemia + delivery_mode + age ndipo tanthauzirani ma hazard ratio osinthidwa.",
    "Run Q10(e), inspect HRs, CIs and p-values with the stated reference levels.":
        "Thamangani Q10(e), yang'anani ma HR, ma CI ndi ma p-value pamodzi ndi milingo yotchulidwa.",
    "Cox coefficient/HR table.": "Tebulo la Cox coefficient kapena HR.",
    "An HR above 1 means a higher instantaneous readmission hazard at fixed covariates.":
        "HR yoposa 1 ikutanthauza hazard yapamwamba yanthawi yomweyo yobwereranso kuchipitali ma covariate atakhazikika.",
    "Use the Cox template with explicit reference levels and non-causal wording.":
        "Gwiritsani ntchito template ya Cox ndi milingo yotchulidwa momveka bwino ndi mawonekedwe osanena za chifukwa.",
    "Ignoring the proportional hazards assumption.": "Kunyalanyaza malingaliro a proportional hazards.",

    "Assess proportional hazards using Schoenfeld residual diagnostics.":
        "Unikani proportional hazards pogwiritsa ntchito kuwunika kwa Schoenfeld residual.",
    "Run Q10(f), inspect residual plots and the screening tests.":
        "Thamangani Q10(f), yang'anani ma plot a residual ndi mayeso owunikira.",
    "Residual plots and screening-test table.": "Ma plot a residual ndi tebulo la mayeso owunikira.",
    "A time trend suggests the hazard ratio may change over follow-up.":
        "Kusintha ndi nthawi kukusonyeza kuti hazard ratio ikhoza kusintha panthawi yotsatira.",
    "Report the screen, its limitation and possible remedies such as time-varying effects or stratification.":
        "Nenani kuwunika kumeneku, malire ake ndi njira zotheka monga zotsatira zosintha ndi nthawi kapena stratification.",
    "Claiming the assumption is proven, or using cox.zph wording as if R were used.":
        "Kunena kuti malingaliro atsimikiziridwa, kapena kugwiritsa ntchito mawonekedwe a cox.zph ngati R inagwiritsidwa ntchito.",
})

TEXT_OVERRIDES.update({
    "Numeric column in the 400-row ANC file.":
        "Mzati wa manambala mu fayilo ya ANC ya mizere 400.",
    "Complete for all 400 records.": "Yathunthu pa zolemba zonse 400.",

    "Q1a output · anc_cohort.csv": "Zotuluka za Q1a · anc_cohort.csv",
    "Q2b output · anc_cohort.csv": "Zotuluka za Q2b · anc_cohort.csv",
    "Q2c and Q2d outputs · anc_cohort.csv": "Zotuluka za Q2c ndi Q2d · anc_cohort.csv",
    "Q3a output · anc_cohort.csv": "Zotuluka za Q3a · anc_cohort.csv",
    "Q4 output · anc_cohort.csv": "Zotuluka za Q4 · anc_cohort.csv",
    "Q5 output · bp_paired.csv": "Zotuluka za Q5 · bp_paired.csv",
    "Q6 output · anc_cohort.csv": "Zotuluka za Q6 · anc_cohort.csv",
    "Q7a output · anc_cohort.csv": "Zotuluka za Q7a · anc_cohort.csv",
    "Q7b output and dataset audit · anc_cohort.csv":
        "Zotuluka za Q7b ndi kuwunika kwa deta · anc_cohort.csv",
    "Q8b output · anc_cohort.csv": "Zotuluka za Q8b · anc_cohort.csv",
    "Q9 output · anc_cohort.csv": "Zotuluka za Q9 · anc_cohort.csv",
    "Q10b output · postpartum_survival.csv":
        "Zotuluka za Q10b · postpartum_survival.csv",
    "Q10c output · postpartum_survival.csv":
        "Zotuluka za Q10c · postpartum_survival.csv",
    "Q10b and Q10d outputs · postpartum_survival.csv":
        "Zotuluka za Q10b ndi Q10d · postpartum_survival.csv",
    "Q10a and Q10e outputs · postpartum_survival.csv":
        "Zotuluka za Q10a ndi Q10e · postpartum_survival.csv",
})

TEXT_OVERRIDES.update({
    "Descriptive statistics": "Ziwerengero zofotokoza",
    "Probability": "Mwayi",
    "Correlation": "Correlation",
    "Confidence interval": "Confidence interval",
    "Independent t-test": "t-test ya magulu odziyimira pawokha",
    "Paired t-test": "t-test ya deta yofananizidwa",
    "ANOVA": "ANOVA",
    "Chi-square test": "mayeso a chi-square",
    "Proportion test": "mayeso a gawo",
    "Linear regression": "Linear regression",
    "Logistic regression": "Logistic regression",
    "Kaplan-Meier analysis": "kusanthula kwa Kaplan-Meier",
    "Log-rank test": "mayeso a log-rank",
    "Exponential survival rate": "mtengo wopulumuka wa exponential",
    "Cox regression": "Cox regression",
})

TEXT_OVERRIDES.update({
    "The supplied Drive files and bundled sample files have identical LF-normalised content. These are simulated teaching datasets, not real patient records.":
        "Mafayilo a Drive omwe aperekedwa ndi mafayilo otsitsa omwe ali mu pulojekiti ali ndi zofanana zikatsukidwa kuti LF ikhale yofanana. Awa ndi deta yofananizidwa yophunzitsira, osati zolemba za odwala enieni.",
    "Compare booking and 36-week systolic BP using a paired analysis.":
        "Yerekezerani systolic BP pa nthawi yolembetsa ndi pa masabata 36 pogwiritsa ntchito deta yofananizidwa.",
    "Run Q5, inspect the paired difference plot, normality check and paired t result.":
        "Thamangani Q5, yang'anani plot ya kusiyana kwa deta yofananizidwa, kuwunika normality ndi zotsatira za paired t.",
    "Paired difference output and the contrast with the incorrect independent test.":
        "Zotuluka za kusiyana kwa deta yofananizidwa ndi kuyerekeza ndi mayeso olakwika a magulu odziyimira pawokha.",
    "Extend the regression with facility_type and compare nested models.":
        "Wonjezerani regression ndi facility_type ndipo yerekezerani mitundu yoyikidwa mkati mwa inzake.",
    "Counts, censoring proportion and median observed follow-up.":
        "Kuchuluka, gawo la censoring ndi median ya nthawi yotsatira yowonedwa.",
    "group summaries": "chidule cha magulu",
    "summaries": "chidule",
    "Scale determines which summaries and plots are meaningful.":
        "Sikelo imatsimikizira kuti ndi chidule ndi ma plot ati omwe ali oyenera.",
    "The literal education category 'None' is data, not a missing-value marker. Scale determines which summaries and plots are meaningful.":
        "Gulu la maphunziro lotchedwa 'None' ndi deta, si chizindikiro cha deta yosowa. Sikelo imatsimikizira kuti ndi chidule ndi ma plot ati omwe ali oyenera.",
    "Worked example from": "Chitsanzo chathunthu chochokera",
    "Fixed-seed simulated teaching data; no real patient records.":
        "Deta yofananizidwa yophunzitsira yokhala ndi mbewu yokhazikika; palibe zolemba za odwala enieni.",
    "The recorded": "Chizindikiro cholembedwa",
    "flag differs from literal decimal": "chikusiyana ndi decimal yeniyeni",
    "for nine records and is used as the primary outcome.":
        "pa zolemba zisanu ndi zinayi ndipo amagwiritsidwa ntchito ngati zotsatira zoyamba.",
    "Survival analysis uses statsmodels plus a transparent log-rank implementation;":
        "Kusanthula kwa nthawi mpaka chochitika kumagwiritsa ntchito statsmodels ndi log-rank yowonekera;",
    "is unavailable. The PH check is a Schoenfeld-residual screen, not an exact":
        "sikupezeka. Kuwunika kwa PH ndi kuwunika kwa Schoenfeld residual, si ndendende",
    "reproduction.": "kubwerezabwereza.",
    "Observational associations are not causal effects.":
        "Ubale wowunikira si zotsatira za chifukwa.",
})

# ---------------------------------------------------------------------------
# Translation rules
# ---------------------------------------------------------------------------

NAVIGATION_HEADERS: list[str] = [
    "Question/Subquestion",
    "Practical requirement",
    "Task classification",
    "Jupyter action",
    "Code",
    "Output to inspect",
    "Interpretation guidance",
    "Reporting guidance",
]

LEARNING_PREFIXES: dict[str, str] = {
    "What is being asked?": "Kodi funso likufunsa chiyani?",
    "Statistical concept:": "Lingaliro la ziwerengero:",
    "Do you need to write code?": "Kodi muyenera kulemba code?",
    "What to do in Jupyter:": "Zoyenera kuchita mu Jupyter:",
    "Code to use:": "Code yoyenera kugwiritsa ntchito:",
    "Output to inspect:": "Zotuluka zoyenera kuyang'ana:",
    "Important values or observations:": "Makhalidwe kapena zowoneratu zofunika:",
    "How to interpret it:": "Momwe mungatanthauzire:",
    "What to report:": "Zoyenera kunena mu lipoti:",
    "Common mistakes to avoid:": "Zolakwika zofunika kupewa:",
}

TERMS: dict[str, str] = {
    "what is being asked?": "Kodi funso likufunsa chiyani?",
    "statistical concept:": "Lingaliro la ziwerengero:",
    "do you need to write code?": "Kodi muyenera kulemba code?",
    "what to do in jupyter:": "Zoyenera kuchita mu Jupyter:",
    "code to use:": "Code yoyenera kugwiritsa ntchito:",
    "output to inspect:": "Zotuluka zoyenera kuyang'ana:",
    "important values or observations:": "Makhalidwe kapena zowoneratu zofunika:",
    "how to interpret it:": "Momwe mungatanthauzire:",
    "what to report:": "Zoyenera kunena mu lipoti:",
    "common mistakes to avoid:": "Zolakwika zofunika kupewa:",
    "one-way anova": "one-way ANOVA",
    "two-sided": "ya mbali ziwiri",
    "fourfold": "kanayi",
    "survival analysis": "kuyerekeza kwa nthawi mpaka chochitika",
    "survival curve": "curve ya kupulumuka",
    "survival time": "nthawi yopulumuka",
    "event-free survival": "kupulumuka kopanda chochitika",
    "readmission-free survival": "kupulumuka popanda kubwereranso kuchipitali",
    "time-to-event": "nthawi mpaka chochitika",
    "time to event": "nthawi mpaka chochitika",
    "follow-up": "kutsatira",
    "follow up": "kutsatira",
    "risk set": "gulu la chiwopsezo",
    "person-time": "person-time",
    "person-days": "person-days",
    "constant hazard": "hazard yosasinthika",
    "constant-hazard": "ya hazard yosasinthika",
    "proportional hazards": "proportional hazards",
    "time-varying effects": "zotsatira zosintha ndi nthawi",
    "sampling variability": "kusiyana kwa sample",
    "sample proportion": "gawo la sample",
    "population probability": "mwayi wa gulu lonse",
    "theoretical probability": "mwayi wongolingalira",
    "conditional probability": "mwayi wapamikhalidwe",
    "marginal probability": "mwayi wamba",
    "unconditional probabilities": "mwayi wopanda mikhalidwe",
    "confidence interval": "confidence interval",
    "confidence level": "mulingo wa confidence",
    "standard error": "standard error",
    "measurement scale": "sikelo yoyezera",
    "missing values": "makhalidwe osowa",
    "missing data": "deta yosowa",
    "non-missing observations": "zowoneratu zomwe zilipo",
    "non-missing": "yomwe ilipo",
    "sample size": "kukula kwa sample",
    "effective sample size": "kukula kwa sample yogwiritsa ntchito",
    "effect size": "kukula kwa zotsatira",
    "point estimate": "point estimate",
    "fitted model": "chitsanzo chokwanira",
    "fitted line": "mzere wokwanira",
    "posterior probability": "mwayi wa posterior",
    "exact test": "mayeso enieni",
    "null hypothesis": "mfundo ya null",
    "null value": "mtengo wa null",
    "expected counts": "kuchuluka koyembekezeredwa",
    "observed counts": "kuchuluka kowonedwa",
    "contingency table": "tebulo la contingency",
    "row percentages": "magawo a mizere",
    "column percentages": "magawo a mizati",
    "group summaries": "chidule cha magulu",
    "complete-case denominator": "denominator ya deta yathunthu",
    "complete cases": "deta yathunthu",
    "complete-case": "ya deta yathunthu",
    "sensitivity analysis": "kusanthula kwa sensitivity",
    "assumption checks": "kuwunika malingaliro",
    "assumption check": "kuwunika malingaliro",
    "reference levels": "milingo yotchulidwa",
    "reference level": "mlingo wotchulidwa",
    "reference categories": "magulu otchulidwa",
    "reference category": "gulu lotchulidwa",
    "binary outcome": "zotsatira za binary",
    "predicted probabilities": "mwayi woloseredwa",
    "scenario probabilities": "mwayi wa zochitika",
    "probability change": "kusintha kwa mwayi",
    "exposed group": "gulu lokhudzidwa",
    "final inference": "zotsatira zomaliza",
    "study design": "kapangidwe ka kafukufuku",
    "nested models": "zitsanzo zokhazikika",
    "nested model": "chitsanzo chokhazikika",
    "model fit": "kukwanira kwa chitsanzo",
    "AIC difference": "kusintha kwa AIC",
    "degrees of freedom": "degrees of freedom",
    "critical value": "mtengo wofunikira",
    "repeated samples": "zitsanzo zobwerezedwa",
    "long-run": "kwa nthawi yaitali",
    "influential records": "zolemba zomwe zimakhudza kwambiri",
    "influential points": "mfundo zomwe zimakhudza kwambiri",
    "extreme points": "mfundo zapamwamba",
    "missingness": "kusowa kwa deta",
    "normal approximation": "kuyerekeza kwa normal",
    "low birth weight": "kulemera kochepa pakubadwa",
    "birth weight": "kulemera kwa mwana pakubadwa",
    "birthweight": "kulemera kwa mwana pakubadwa",
    "gestational age": "zaka za mimba",
    "term births": "kubadwa pa nthawi",
    "risk difference": "kusiyana kwa mwayi wachochitika",
    "confidence": "confidence",
    "frequentist": "frequentist",
    "independent": "odziyimira pawokha",
    "independence": "kudziyimira pawokha",
    "dependence": "kugwirizana",
    "dependent": "ogwirizana",
    "association": "ubale",
    "associated": "ogwirizana",
    "causation": "chifukwa",
    "causality": "chifukwa",
    "causal claim": "kunena za chifukwa",
    "causal effect": "zotsatira za chifukwa",
    "causal": "cha chifukwa",
    "non-causal": "kosanena za chifukwa",
    "observational": "yowunikira",
    "randomly assigned": "naperekedwa mwachisawawa",
    "simulated teaching data": "deta yofananizidwa",
    "simulated cohort": "gulu la kafukufuku lofananizidwa",
    "simulated": "yofananizidwa",
    "teaching data": "deta yophunzitsira",
    "cohort": "gulu la kafukufuku",
    "population": "gulu lonse",
    "participants": "otenga nawo mbali",
    "participant": "munthu wotenga nawo mbali",
    "women": "amayi",
    "woman": "mkazi",
    "probability": "mwayi",
    "probabilities": "mwayi",
    "estimate": "yerekeza",
    "estimates": "kuyerekeza",
    "estimated": "koyerekeza",
    "estimation": "kuyerekeza",
    "preterm": "kubadwa msanga",
    "anaemia": "kuchepa kwa magazi",
    "anaemic": "wodwala kuchepa kwa magazi",
    "non-anaemic": "wopanda kuchepa kwa magazi",
    "readmission": "kubwereranso kuchipitali",
    "readmissions": "kubwereranso kuchipitali",
    "censoring": "censoring",
    "censored": "zochepetsedwa",
    "survival": "kupulumuka",
    "event": "chochitika",
    "events": "zochitika",
    "event time": "nthawi ya chochitika",
    "hazard": "hazard",
    "prevalence": "kufala",
    "binary": "binary",
    "predictor": "chinthu cholosera",
    "predictors": "zinthu zolosera",
    "covariate": "covariate",
    "covariates": "ma covariate",
    "outcome": "zotsatira",
    "outcomes": "zotsatira",
    "coefficient": "coefficient",
    "coefficients": "ma coefficient",
    "residual": "residual",
    "residuals": "ma residual",
    "assumption": "malingaliro",
    "assumptions": "malingaliro",
    "significance": "kufunika",
    "significant": "kofunika",
    "non-significant": "kosafunika",
    "p-value": "p-value",
    "test": "mayeso",
    "tests": "mayeso",
    "analysis": "kusanthula",
    "analyse": "unikani",
    "analyze": "unikani",
    "check": "onani",
    "checked": "oyaonapo",
    "choose": "sankhani",
    "choosing": "kusankha",
    "avoid": "kupewa",
    "state": "nenani",
    "describe": "fotokozani",
    "explain": "fotokozani",
    "write": "lembani",
    "written": "yolembedwa",
    "use": "gwiritsani ntchito",
    "using": "pogwiritsa ntchito",
    "used": "ogwiritsidwa ntchito",
    "need": "kufunika",
    "needed": "kofunikira",
    "required": "kofunikira",
    "require": "kufuna",
    "should": "yenera",
    "must": "kuyenera",
    "complete": "yathunthu",
    "excluded": "zachotsedwa",
    "exclude": "chotsani",
    "eligible": "oyenera",
    "evaluable": "oyesedwa",
    "denominator": "denominator",
    "numerator": "numerator",
    "proportion": "gawo",
    "proportions": "magawo",
    "ratio": "ratio",
    "difference": "kusiyana",
    "direction": "komwe ikupita",
    "size": "kukula",
    "sign": "chizindikiro",
    "magnitude": "kukula",
    "curvature": "kupindika",
    "tail": "mchira",
    "skewness": "kupendekera",
    "normality": "normality",
    "histograms": "ma histogramu",
    "histogram": "histogramu",
    "scatterplot": "scatterplot",
    "boxplot": "boxplot",
    "plots": "ma plot",
    "plot": "plot",
    "tables": "matebulo",
    "table": "tebulo",
    "summaries": "zidule",
    "summary": "chidule",
    "summarise": "fotokozani mwachidule",
    "summarize": "fotokozani mwachidule",
    "justification": "chifukwa",
    "justify": "kupereka chifukwa",
    "choice": "chisankho",
    "meaningful": "yomveka",
    "model": "chitsanzo",
    "models": "zitsanzo",
    "diagnostics": "kuwunika",
    "diagnostic": "kuwunikira",
    "outliers": "ma outlier",
    "outlier": "outlier",
    "question": "funso",
    "questions": "mafunso",
    "subquestions": "mafunso ang'onoang'ono",
    "subquestion": "funso laling'ono",
    "answer": "yankho",
    "answers": "mayankho",
    "guidance": "malangizo",
    "mistakes": "zolakwika",
    "mistake": "cholakwika",
    "silently": "popanda kuwuza",
    "explicitly": "momveka bwino",
    "cautiously": "mosamala",
    "visually": "maso",
    "step by step": "sitepe ndi sitepe",
    "in your own words": "ndi mawonekedwe anu",
    "short": "yaifupi",
    "paragraph": "ndime",
    "cell": "selo",
    "cells": "ma selo",
    "notebook": "notebook",
    "file": "fayilo",
    "actual file": "fayilo yeniyeni",
    "supplied": "zoperekedwa",
    "and": "ndi",
    "or": "kapena",
    "but": "koma",
    "with": "ndi",
    "without": "popanda",
    "from": "kuchokera",
    "in": "mu",
    "on": "pa",
    "at": "pa",
    "by": "ndi",
    "for": "pa",
    "of": "wa",
    "as": "ngati",
    "is": "ndi",
    "are": "ndi",
    "was": "inali",
    "were": "inali",
    "be": "kukhala",
    "this": "izi",
    "these": "izi",
    "that": "kuti",
    "it": "ichi",
    "its": "yake",
    "their": "yawo",
    "your": "yanu",
    "each": "chilichonse",
    "every": "chilichonse",
    "all": "zonse",
    "both": "onse awiri",
    "same": "yomweyo",
    "other": "ina",
    "another": "inanso",
    "more": "kwambiri",
    "less": "kochepa",
    "large": "kwakukulu",
    "small": "yaing'ono",
    "one": "imodzi",
    "two": "iwiri",
    "three": "zitatu",
    "four": "zinayi",
    "five": "zisanu",
    "six": "asanu ndi limodzi",
    "ten": "khumi",
    "because": "chifukwa",
    "therefore": "choncho",
    "however": "komabe",
    "instead": "m'malo mwake",
    "only": "kokha",
    "also": "komanso",
    "before": "musana",
    "after": "pambuyo",
    "during": "panthawi",
    "until": "mpaka",
    "per": "pa",
    "versus": "poyerekeza ndi",
    "against": "poyerekeza ndi",
    "across": "m'magulu a",
    "within": "mkati mwa",
    "between": "pakati pa",
    "among": "mwa",
    "not": "si",
    "do not": "musa",
    "does not": "sikuti",
    "did not": "sina",
    "cannot": "sangathe",
    "keep": "sungani",
    "preserve": "sungani",
    "unchanged": "osasinthika",
    "exactly": "ndendende",
    "output": "zotuluka",
    "the": "",
    "a": "",
    "an": "",
}

_TERM_KEYS = sorted(TERMS, key=len, reverse=True)
_TERM_RE = re.compile(
    r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(k) for k in _TERM_KEYS) + r")(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_TERM_LOOKUP = {k.lower(): v for k, v in TERMS.items()}

_PROTECTED_TOKENS: set[str] = {
    "anc", "low_bw", "gest_age", "hb", "bmi", "birthweight", "iptp3", "preterm",
    "readmitted", "facility_type", "anc_visits", "delivery_mode",
    "education", "id", "q1a", "q1b", "q2a", "q2b", "q2c", "q2d",
    "q3a", "q3b", "q3c", "q3d", "q4", "q5", "q6", "q7a", "q7b", "q7c",
    "q8a", "q8b", "q8c", "q8d", "q8e", "q9", "q10a", "q10b", "q10c",
    "q10d", "q10e", "q10f", "n", "p", "p-value", "CI", "CIs", "SE",
    "SD", "df", "IQR", "OR", "HR", "AIC", "ANOVA", "BMI", "ANC",
    "IPTp3", "R-squared", "R", "H0", "H1", "PH", "KDE", "KM", "NaN",
    "True", "False", "keep_default_na", "Yes", "No", "None", "Primary",
    "Secondary+", "Urban", "Peri-urban", "Rural", "Anaemia",
    "No anaemia", "IPTp3 Yes", "IPTp3 No", "Welch", "Welch's",
    "Wilcoxon", "Levene", "Shapiro", "Shapiro-Wilk", "Tukey",
    "Kruskal-Wallis", "Kaplan-Meier", "Cox", "Schoenfeld", "Holm",
    "Pearson", "Spearman", "Fisher", "Newcombe", "Wilson",
    "Durbin-Watson", "Cook's", "Cook's D", "SciPy", "statsmodels",
    "Jupyter", "pandas", "numpy", "g", "g/dL", "mmHg", "person-day",
    "person-days", "cox.zph", "log(time)", "SD/sqrt(n)", "4/n", "1/sqrt(n)",
}

_PROTECT_PATTERNS = [
    r"\{[^{}\n]+\}",
    r"<[^>\n]+>",
    r"`[^`\n]+`",
    r"\b[\w.-]+\.(?:csv|json|ipynb|html|py|txt)\b",
    r"\bQ\d{1,2}(?:\([a-z]\)|[a-z])?\b",
    r"\b[A-Za-z_][A-Za-z0-9_]*\s*~\s*[^,;.\n]+",
    r"\b[A-Za-z_][A-Za-z0-9_]*\s*(?:==|!=|<=|>=|=)\s*[^\s,;]+",
    r"\b(?:P|S|F|t|chi2|HR|OR)\s*\([^()\n]*\)",
    r"(?<![A-Za-z0-9_])\d[\d,]*(?:\.\d+)?%?(?:/\d[\d,]*(?:\.\d+)?)?(?![A-Za-z0-9_])",
]
_TOKEN_ALT = "|".join(re.escape(t) for t in sorted(_PROTECTED_TOKENS, key=len, reverse=True))
_PROTECT_RE = re.compile("|".join(_PROTECT_PATTERNS + [r"(?<![A-Za-z0-9_])(?:" + _TOKEN_ALT + r")(?![A-Za-z0-9_])"]))
_TOKEN_RE = re.compile("\uE000(\\d+)\uE001")


def _is_code_like(text: str) -> bool:
    """Return True for code, JSON or a fragment made entirely of HTML tags."""
    stripped = text.strip()
    if "```" in stripped:
        return True
    if stripped.startswith("{") and stripped.endswith("}") and ('"' in stripped or "'" in stripped):
        return True
    if "\n" in stripped and re.search(r"\b(?:import|from|def|return|print|for|if)\b", stripped):
        return True
    tags = re.findall(r"<[^>]+>", stripped)
    return bool(tags) and re.sub(r"<[^>]+>", "", stripped).strip() == ""


def _protect(text: str) -> tuple[str, list[str]]:
    saved: list[str] = []

    def replace(match: re.Match[str]) -> str:
        saved.append(match.group(0))
        return f"\uE000{len(saved) - 1}\uE001"

    return _PROTECT_RE.sub(replace, text), saved


def _restore(text: str, saved: Iterable[str]) -> str:
    values = list(saved)
    return _TOKEN_RE.sub(lambda m: values[int(m.group(1))], text)


def _phrase_translate(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        original = match.group(0)
        value = _TERM_LOOKUP.get(original.lower(), original)
        if original[:1].isupper() and value and value[:1].islower():
            value = value[0].upper() + value[1:]
        return value

    return _TERM_RE.sub(replace, text)


def translate(text: str) -> str:
    """Translate English companion text into natural Chichewa.

    Exact overrides are applied first.  Otherwise recurring teaching phrases
    are translated while numbers, identifiers, file names, placeholders and
    mathematical notation are protected from alteration.
    """
    if not isinstance(text, str):
        return text  # type: ignore[return-value]
    source = text.strip()
    if source in TEXT_OVERRIDES:
        return TEXT_OVERRIDES[source]
    if _is_code_like(source):
        return text
    if re.fullmatch(r"See [A-Za-z0-9_]+", source):
        return "Ona " + source[4:]
    if re.fullmatch(r"Notebook section Q\d+", source):
        return "Gawo la notebook " + source[len("Notebook section "):]

    for prefix in sorted(LEARNING_PREFIXES, key=len, reverse=True):
        if source.startswith(prefix):
            remainder = source[len(prefix):].lstrip()
            protected, saved = _protect(remainder)
            body = _restore(_phrase_translate(protected), saved)
            body = re.sub(r"[ \t]+", " ", body).strip()
            return f"{LEARNING_PREFIXES[prefix]} {body}".strip()

    protected, saved = _protect(source)
    translated = _restore(_phrase_translate(protected), saved)
    translated = re.sub(r"[ \t]+", " ", translated).strip()
    return translated


def guide_ny(qid: str) -> dict[str, Any]:
    """Return one GUIDES entry with every prose field translated."""
    guide = GUIDES[qid]
    return {
        "id": guide["id"],
        "title": translate(guide["title"]),
        "requirement": translate(guide["requirement"]),
        "classification": translate(guide["classification"]),
        "jupyter_action": translate(guide["jupyter_action"]),
        "code_required": guide["code_required"],
        "learning": [translate(point) for point in guide["learning"]],
        "output_to_inspect": translate(guide["output_to_inspect"]),
        "interpretation": translate(guide["interpretation"]),
        "reporting": translate(guide["reporting"]),
        "common_mistakes": translate(guide["common_mistakes"]),
    }


def report_ny(qid: str, report: dict[str, Any]) -> dict[str, Any]:
    """Translate a worked report while keeping its structure and qid context."""
    if report is None:
        report = work_report(qid, {})
    keys = ("text", "source", "teach")
    if all(key in report for key in keys):
        return {
            key: translate(report[key]) if isinstance(report[key], str) else report[key]
            for key in keys
        }
    return {
        key: translate(value) if isinstance(value, str) else value
        for key, value in report.items()
    }


def template_ny(example: Any) -> dict[str, Any]:
    """Translate a reporting template from GUIDES or worked_template_examples()."""
    if isinstance(example, dict):
        return {
            key: translate(value) if isinstance(value, str) else value
            for key, value in example.items()
        }
    if isinstance(example, (tuple, list)) and len(example) >= 2:
        title, pattern = str(example[0]), str(example[1])
        title_ny, pattern_ny = translate(title), translate(pattern)
        return {
            "title": title_ny,
            "name": title_ny,
            "pattern": pattern_ny,
            "template": pattern_ny,
            "text": pattern_ny,
        }
    raise TypeError("template_ny expects a (title, template) pair or a worked-example dict")


def audit_facts_ny() -> list[tuple[str, str]]:
    """Translate the verified dataset-audit facts."""
    return [(translate(verification), translate(finding)) for verification, finding in AUDIT_FACTS]


def navigation_headers_ny() -> list[str]:
    """Translate the required navigation-table headers."""
    return [translate(header) for header in NAVIGATION_HEADERS]


def classification_rows_ny(rows: Iterable[Iterable[Any]]) -> list[list[Any]]:
    """Translate Q2(a) classification rows without changing identifiers or numbers."""
    return [
        [translate(cell) if isinstance(cell, str) else cell for cell in row]
        for row in rows
    ]


def coverage_report() -> dict[str, Any]:
    """Report translation coverage for guides, learning points and templates."""
    unmapped: list[str] = []
    guide_fields = (
        "title", "requirement", "classification", "jupyter_action",
        "output_to_inspect", "interpretation", "reporting", "common_mistakes",
    )

    for qid, guide in GUIDES.items():
        for index, point in enumerate(guide["learning"], start=1):
            label = f"{qid}.learning[{index}]"
            if point not in TEXT_OVERRIDES and translate(point) == point:
                unmapped.append(label)
        for field in guide_fields:
            source = guide[field]
            label = f"{qid}.{field}"
            if source not in TEXT_OVERRIDES and translate(source) == source:
                unmapped.append(label)

    for title, pattern in REPORTING_TEMPLATES:
        if pattern not in TEXT_OVERRIDES and translate(pattern) == pattern:
            unmapped.append(f"template:{title}")

    for index, (verification, finding) in enumerate(AUDIT_FACTS, start=1):
        for text, kind in ((verification, "verification"), (finding, "finding")):
            if text not in TEXT_OVERRIDES and translate(text) == text:
                unmapped.append(f"audit[{index}].{kind}")

    return {
        "guides": len(GUIDES),
        "learning_points": sum(len(guide["learning"]) for guide in GUIDES.values()),
        "templates": len(REPORTING_TEMPLATES),
        "unmapped": unmapped,
    }


if __name__ == "__main__":
    report = coverage_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["unmapped"]:
        raise SystemExit(1)


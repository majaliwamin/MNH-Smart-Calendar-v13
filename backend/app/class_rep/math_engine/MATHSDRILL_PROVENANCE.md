# MathsDrill complement: scope and provenance

## Source

- Repository: <https://github.com/majaliwamin/mathsdrill>
- Reviewed commit: `67e170f478be5383ad1fbdb2a0112121b2b1811d`
- Integration branch: `feature/crara-mathsdrill-complement`
- Implementation: `backend/app/class_rep/math_engine/mathsdrill.py`

The deterministic routines in `mathsdrill.py` were independently implemented in
Python from standard mathematical formulae after reviewing MathsDrill's capability
inventory. JavaScript source from MathsDrill was **not copied**. The repository
has no explicit licence or attribution field, so no source code was vendored and
no licence grant is assumed. CRARA's existing engine remains the primary
calculation engine.

## What was added

This additive complement only handles school-mathematics topics that CRARA's
existing SymPy/SciPy routing did not already cover as first-class operations:

- arithmetic and geometric sequence terms and sums;
- coordinate translations, reflections, rotations and enlargements;
- mensuration for rectangles, triangles, circles, trapezia, cylinders, cones,
  spheres and cuboids;
- chord, tangent, arc-length and sector-area circle geometry;
- similarity scale factors and length/area/volume ratios;
- loci as perpendicular bisectors;
- bearings and distances from Cartesian coordinates;
- two-variable linear programming;
- linear modelling from fixed/initial value and constant rate;
- graph reading from two points;
- curated step justifications (the MathsDrill “reasons” idea) attached to every
  result as `step_reasons`.

All results use CRARA's existing `MathResult` contract, so validation, evidence
injection, deterministic fallback and the `/api/class-rep/chat` API contract are
unchanged.

## Explicit exclusions

Nothing from the following areas was added to this complement:

- epidemiology;
- biostatistics;
- clinical or medical statistics;
- hypothesis testing, p-values and confidence intervals;
- survival analysis;
- diagnostic accuracy and ROC/AUC;
- sample-size and power calculations;
- patient-facing or treatment-related reasoning.

`mathsdrill.solve()` returns `None` immediately when those contexts are detected,
so such requests stay on CRARA's existing biomedical and statistical paths.

## Routing guarantees

- `engine.capabilities()` gains a separate `mathsdrill_complement` category; no
  existing capability category is removed or renamed.
- `mathsdrill.solve()` is called after symbol/formula lookups and before the
  existing computation branches, but it returns `None` unless a narrow school
  cue and explicit parameters are present.
- Existing arithmetic, algebra, calculus, matrix/vector, probability,
  descriptive statistics, inferential statistics, regression and biostatistics
  routes remain ahead of or independent from this complement.
- Malformed or incomplete school prompts return explicit `blocked` records; they
  never invent missing values.

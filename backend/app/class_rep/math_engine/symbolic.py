"""Symbolic algebra, calculus, linear algebra and numerical computation."""
from __future__ import annotations

import math
import re
from typing import Any

from .results import MathResult, blocked_result

_BLOCKED_TOKENS = ("__", "import", "eval", "exec", "open", "lambda", "globals", "locals", "subprocess", "os.")
_TOKEN_RE = re.compile(
    r"\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|[A-Za-z_][A-Za-z0-9_]*|<=|>=|!=|==|[+\-*/^(),=<>%!]|\s+"
)
_INPUT_SYMBOLS = {
    "x", "y", "t", "n", "a", "b", "c", "d", "k", "r", "m", "z", "s", "u", "v", "w", "p", "q",
    "f", "g", "h", "i", "j", "l", "e", "pi", "oo", "infinity", "sum", "product", "diff", "integrate",
}


def _sympy():
    try:
        import sympy as sp
        return sp, None
    except Exception as exc:
        return None, str(exc)


def _parse(expression: str, sp: Any) -> Any:
    text = str(expression or "").strip()
    if not text or len(text) > 400:
        raise ValueError("expression is empty or too long")
    text = text.replace("π", "pi").replace("≤", "<=").replace("≥", ">=").replace("≠", "!=")
    folded = text.casefold()
    if any(token in folded for token in _BLOCKED_TOKENS):
        raise ValueError("expression contains a disallowed token")
    local = {
        "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
        "exp": sp.exp, "log": sp.log, "ln": sp.log, "sqrt": sp.sqrt, "abs": sp.Abs, "factorial": sp.factorial,
        "pi": sp.pi, "E": sp.E, "I": sp.I, "oo": sp.oo, "infinity": sp.oo,
        "Sum": sp.Sum, "Product": sp.Product, "diff": sp.diff, "integrate": sp.integrate,
    }
    allowed_names = {name.casefold() for name in local} | _INPUT_SYMBOLS
    position = 0
    for match in _TOKEN_RE.finditer(text):
        if text[position:match.start()].strip():
            raise ValueError("expression contains a disallowed character")
        token = match.group()
        if token[0].isalpha() or token[0] == "_":
            if token.casefold() not in allowed_names:
                raise ValueError("expression contains a disallowed name")
        position = match.end()
    if text[position:].strip():
        raise ValueError("expression contains a disallowed character")
    from sympy.parsing.sympy_parser import (
        convert_xor, implicit_multiplication_application, parse_expr, standard_transformations,
    )
    return parse_expr(
        text.replace("^", "**"),
        local_dict=local,
        global_dict={
            "__builtins__": {},
            "Integer": sp.Integer, "Float": sp.Float, "Rational": sp.Rational,
            "Symbol": sp.Symbol, "Function": sp.Function, "S": sp.S,
        },
        transformations=standard_transformations + (implicit_multiplication_application, convert_xor),
        evaluate=True,
    )


def _latex(sp: Any, value: Any) -> str:
    try:
        return sp.latex(value)
    except Exception:
        return str(value)


def _native_number(value: Any) -> Any:
    """Convert a scalar SymPy number to a JSON-friendly Python number."""
    if getattr(value, "is_number", False) and not getattr(value, "is_matrix", False):
        try:
            return float(value)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def _result(operation: str, method: str, expression: str, values: dict[str, Any], latex: dict[str, str],
            steps: list[str], interpretation: str, code: str = "") -> MathResult:
    return MathResult(
        operation=operation, domain="mathematics", method=method, inputs={"expression": expression},
        assumptions=["Symbols and functions are interpreted with standard mathematical conventions."],
        steps=steps, values=values, latex=latex, code=code, interpretation=interpretation,
    )


def simplify(expression: str) -> MathResult:
    sp, error = _sympy()
    if sp is None:
        return blocked_result("simplify", f"Symbolic maths needs SymPy: {error}", domain="mathematics")
    try:
        expr = _parse(expression, sp)
        simplified = sp.simplify(expr)
    except Exception as exc:
        return blocked_result("simplify", f"Could not parse expression: {exc}", domain="mathematics")
    return _result("simplify", "SymPy simplification", expression,
                   {"input": str(expr), "result": str(simplified)}, {"input": _latex(sp, expr), "result": _latex(sp, simplified)},
                   [f"Simplify {expr} to {simplified}."], f"The simplified expression is {simplified}.",
                   f"import sympy as sp\nx = sp.symbols('x')\nsp.simplify({expression!r})")


def solve(expression: str, variable: str = "x") -> MathResult:
    sp, error = _sympy()
    if sp is None:
        return blocked_result("equation", f"Equation solving needs SymPy: {error}", domain="mathematics")
    try:
        symbol = sp.Symbol(variable)
        parts = [part.strip() for part in re.split(r"[;,]", expression) if part.strip()]
        if not parts:
            raise ValueError("no equation supplied")
        equations = []
        for part in parts:
            if "=" in part:
                left, right = part.split("=", 1)
                equations.append(sp.Eq(_parse(left, sp), _parse(right, sp)))
            else:
                equations.append(_parse(part, sp))
        symbols = [sp.Symbol(name.strip()) for name in re.findall(r"[A-Za-z]\w*", expression) if name.strip() != variable]
        unknowns = [symbol] + symbols
        solutions = sp.solve(equations, unknowns[: len(equations)] if len(equations) > 1 else symbol, dict=True)
    except Exception as exc:
        return blocked_result("equation", f"Could not solve the equation: {exc}", domain="mathematics")
    return _result("equation", "SymPy exact/algebraic solve", expression,
                   {"solutions": [str(item) for item in solutions]},
                   {"expression": _latex(sp, equations[0])},
                   [f"Set up {len(equations)} equation(s) and solve for the unknown(s)."],
                   "Solutions are exact where possible; verify they satisfy the original constraints.",
                   f"import sympy as sp\n{variable} = sp.symbols('{variable}')\nsp.solve({expression!r}, {variable})")


def differentiate(expression: str, variable: str = "x", order: int = 1) -> MathResult:
    sp, error = _sympy()
    if sp is None or order < 1:
        return blocked_result("differentiation", f"Differentiation needs SymPy and positive order: {error}", domain="mathematics")
    try:
        symbol = sp.Symbol(variable)
        expr = _parse(expression, sp)
        derivative = sp.diff(expr, symbol, order)
    except Exception as exc:
        return blocked_result("differentiation", f"Could not differentiate: {exc}", domain="mathematics")
    return _result("differentiation", "symbolic differentiation", expression,
                   {"derivative": str(derivative)}, {"expression": _latex(sp, derivative)},
                   [f"Apply the derivative operator {order} time(s) with respect to {variable}."],
                   f"d^{order}/{variable}^{order} of the expression is {derivative}.",
                   f"import sympy as sp\nsp.diff({expression!r}, sp.Symbol('{variable}'), {order})")


def integrate(expression: str, variable: str = "x", lower: str | None = None, upper: str | None = None) -> MathResult:
    sp, error = _sympy()
    if sp is None:
        return blocked_result("integration", f"Integration needs SymPy: {error}", domain="mathematics")
    try:
        symbol = sp.Symbol(variable)
        expr = _parse(expression, sp)
        if lower is not None and upper is not None:
            value = sp.integrate(expr, (symbol, _parse(lower, sp), _parse(upper, sp)))
            steps = [f"Integrate {expr} with respect to {variable} from {lower} to {upper}."]
        else:
            value = sp.integrate(expr, symbol)
            steps = [f"Find the antiderivative of {expr} with respect to {variable}."]
    except Exception as exc:
        return blocked_result("integration", f"Could not integrate: {exc}", domain="mathematics")
    return _result("integration", "symbolic integration", expression,
                   {"integral": str(value)}, {"expression": _latex(sp, value)}, steps,
                   f"The integral is {value}.", f"import sympy as sp\nsp.integrate({expression!r}, sp.Symbol('{variable}'))")


def limit(expression: str, variable: str = "x", tends_to: str = "0") -> MathResult:
    sp, error = _sympy()
    if sp is None:
        return blocked_result("limit", f"Limits need SymPy: {error}", domain="mathematics")
    try:
        symbol = sp.Symbol(variable)
        value = sp.limit(_parse(expression, sp), symbol, _parse(tends_to, sp))
    except Exception as exc:
        return blocked_result("limit", f"Could not evaluate limit: {exc}", domain="mathematics")
    return _result("limit", "symbolic limit", expression, {"limit": str(value)},
                   {"expression": _latex(sp, value)}, [f"Take the limit as {variable} → {tends_to}."],
                   f"The limit is {value}.")


def matrix_operation(rows: list[list[float]], operation: str = "determinant") -> MathResult:
    sp, error = _sympy()
    if sp is None:
        return blocked_result("matrix", f"Matrix operations need SymPy: {error}", domain="mathematics")
    try:
        matrix = sp.Matrix(rows)
        key = operation.casefold()
        if key in ("determinant", "det"):
            value = sp.Matrix(matrix).det()
            label = "determinant"
        elif key in ("inverse", "inv"):
            value = matrix.inv()
            label = "inverse"
        elif key in ("transpose", "t"):
            value = matrix.T
            label = "transpose"
        elif key in ("eigen", "eigenvalues"):
            value = matrix.eigenvals()
            label = "eigenvalues"
        elif key in ("rref", "reduced"):
            value, _ = matrix.rref()
            label = "reduced row echelon form"
        else:
            return blocked_result("matrix", f"Unsupported matrix operation: {operation}", domain="mathematics")
    except Exception as exc:
        return blocked_result("matrix", f"Matrix operation failed: {exc}", domain="mathematics")
    return _result("matrix", label, str(rows), {"result": _native_number(value)}, {"expression": _latex(sp, value)},
                   [f"Compute the {label} of the supplied matrix."], f"The {label} is {value}.")


def vector_operation(a: list[float], b: list[float] | None = None, operation: str = "dot") -> MathResult:
    sp, error = _sympy()
    if sp is None:
        return blocked_result("vector", f"Vector operations need SymPy: {error}", domain="mathematics")
    try:
        va = sp.Matrix([float(v) for v in a])
        key = operation.casefold()
        if key in ("dot", "inner"):
            if b is None:
                raise ValueError("dot product needs a second vector")
            value = va.dot(sp.Matrix([float(v) for v in b]))
        elif key in ("cross", "outer"):
            if b is None:
                raise ValueError("cross product needs a second vector")
            value = va.cross(sp.Matrix([float(v) for v in b]))
        elif key in ("norm", "magnitude"):
            value = va.norm()
        elif key in ("unit", "normalize"):
            value = va / va.norm()
        else:
            return blocked_result("vector", f"Unsupported vector operation: {operation}", domain="mathematics")
    except Exception as exc:
        return blocked_result("vector", f"Vector operation failed: {exc}", domain="mathematics")
    return _result("vector", operation, f"{a}, {b}", {"result": _native_number(value)}, {"expression": _latex(sp, value)},
                   [f"Compute the {operation} of the supplied vector(s)."], f"Result: {value}.")


def numerical_root(expression: str, guess: float = 0.0) -> MathResult:
    sp, error = _sympy()
    if sp is None:
        return blocked_result("numerical_root", f"Root finding needs SymPy: {error}", domain="mathematics")
    try:
        symbol = sp.Symbol("x")
        expr = _parse(expression, sp)
        root = sp.nsolve(expr, symbol, guess)
    except Exception as exc:
        return blocked_result("numerical_root", f"Root finding failed: {exc}", domain="mathematics")
    return _result("numerical_root", "Newton/numerical root", expression, {"root": float(root)},
                   {"expression": _latex(sp, expr)}, [f"Solve {expr} = 0 numerically from x₀ = {guess}."],
                   f"Approximate root x = {float(root):.10g}.")


def optimize(expression: str, variable: str = "x", kind: str = "minimum") -> MathResult:
    sp, error = _sympy()
    if sp is None:
        return blocked_result("optimization", f"Optimization needs SymPy: {error}", domain="mathematics")
    try:
        symbol = sp.Symbol(variable)
        expr = _parse(expression, sp)
        critical = sp.solve(sp.diff(expr, symbol), symbol)
        candidates = []
        for point in critical:
            if point.is_real:
                second = sp.diff(expr, symbol, 2).subs(symbol, point)
                candidates.append({"x": str(point), "f_x": str(expr.subs(symbol, point)),
                                   "second_derivative": str(second),
                                   "classification": "minimum" if second > 0 else "maximum" if second < 0 else "inconclusive"})
    except Exception as exc:
        return blocked_result("optimization", f"Optimization failed: {exc}", domain="mathematics")
    wanted = "minimum" if "min" in kind.casefold() else "maximum"
    chosen = next((c for c in candidates if c["classification"] == wanted), candidates[0] if candidates else None)
    return _result("optimization", "stationary-point optimisation", expression,
                   {"critical_points": candidates, "selected": chosen}, {"expression": _latex(sp, expr)},
                   ["Set the first derivative to zero.", "Classify stationary points with the second derivative."],
                   f"Selected {wanted}: {chosen}." if chosen else "No real stationary point was found.")


def differential_equation(equation: str) -> MathResult:
    sp, error = _sympy()
    if sp is None:
        return blocked_result("differential_equation", f"ODE solving needs SymPy: {error}", domain="mathematics")
    try:
        x = sp.Symbol("x")
        f = sp.Function("f")
        parts = equation.split("=", 1)
        lhs = _parse(parts[0], sp).subs(sp.Symbol("f(x)"), f(x)) if len(parts) == 2 else _parse(equation, sp)
        rhs = _parse(parts[1], sp) if len(parts) == 2 else sp.S.Zero
        solution = sp.dsolve(lhs - rhs, f(x))
    except Exception as exc:
        return blocked_result("differential_equation", f"Could not solve ODE: {exc}", domain="mathematics")
    return _result("differential_equation", "SymPy dsolve", equation, {"solution": str(solution)},
                   {"expression": _latex(sp, solution)}, ["Set up the differential equation and solve symbolically."],
                   f"The general solution is {solution}.")


def complex_operation(expression: str, operation: str = "simplify") -> MathResult:
    sp, error = _sympy()
    if sp is None:
        return blocked_result("complex_numbers", f"Complex numbers need SymPy: {error}", domain="mathematics")
    try:
        value = _parse(expression, sp)
        key = operation.casefold()
        if key in ("modulus", "abs"):
            output = sp.Abs(value)
        elif key in ("argument", "arg"):
            output = sp.arg(value)
        elif key in ("conjugate", "conj"):
            output = sp.conjugate(value)
        else:
            output = sp.expand_complex(value)
    except Exception as exc:
        return blocked_result("complex_numbers", f"Complex operation failed: {exc}", domain="mathematics")
    return _result("complex_numbers", operation, expression, {"result": str(output)},
                   {"expression": _latex(sp, output)}, [f"Apply {operation} in the complex plane."], f"Result: {output}.")


def inequality(expression: str, variable: str = "x") -> MathResult:
    """Solve a univariate inequality such as ``2*x + 3 > 11``."""
    sp, error = _sympy()
    if sp is None:
        return blocked_result("inequality", f"Inequalities need SymPy: {error}", domain="mathematics")
    try:
        symbol = sp.Symbol(variable, real=True)
        from sympy.parsing.sympy_parser import parse_expr
        relation = parse_expr(expression.replace("^", "**"), local_dict={variable: symbol}, evaluate=True)
        if not getattr(relation, "is_Relational", False):
            raise ValueError("the expression is not an inequality")
        solution = sp.solve_univariate_inequality(relation, symbol, relational=False)
    except Exception as exc:
        return blocked_result("inequality", f"Could not solve inequality: {exc}", domain="mathematics")
    return _result("inequality", "SymPy univariate inequality solve", expression,
                   {"solution_set": str(solution)}, {"expression": _latex(sp, relation), "solution": _latex(sp, solution)},
                   [f"Solve {relation} over the real numbers."],
                   f"The solution set is {solution}.",
                   f"import sympy as sp\nx = sp.Symbol('x', real=True)\nsp.solve_univariate_inequality({expression!r}, x)")


def combinatorics(n: int, r: int | None = None, operation: str = "combination") -> MathResult:
    """Compute factorials, combinations and permutations exactly."""
    if n < 0 or (r is not None and (r < 0 or r > n)):
        return blocked_result("combinatorics", "n and r must be non-negative, with r ≤ n.", domain="mathematics")
    key = operation.casefold()
    try:
        if key in ("factorial", "!"):
            value = math.factorial(n)
            label = f"{n}!"
            latex = rf"{n}!"
        elif key in ("permutation", "permutations", "npr", "arrangement"):
            if r is None:
                raise ValueError("permutations need r")
            value = math.factorial(n) // math.factorial(n - r)
            label = f"P({n},{r})"
            latex = rf"P({n},{r})=\frac{{{n}!}}{{({n}-{r})!}}"
        else:
            if r is None:
                raise ValueError("combinations need r")
            value = math.comb(n, r)
            label = f"C({n},{r})"
            latex = rf"\binom{{{n}}}{{{r}}}=\frac{{{n}!}}{{{r}!({n}-{r})!}}"
    except Exception as exc:
        return blocked_result("combinatorics", f"Combinatorics calculation failed: {exc}", domain="mathematics")
    return _result("combinatorics", label, f"n={n}, r={r}", {"value": value}, {"expression": latex},
                   [f"Apply the {key} counting rule."], f"{label} = {value}.")


def coordinate_geometry(point_a: tuple[float, float], point_b: tuple[float, float],
                        operation: str = "distance") -> MathResult:
    """Distance, midpoint and slope between two Cartesian points."""
    (x1, y1), (x2, y2) = point_a, point_b
    key = operation.casefold()
    try:
        if key in ("midpoint", "mid-point", "centre", "center"):
            value = {"x": (x1 + x2) / 2, "y": (y1 + y2) / 2}
            latex = rf"M=\left(\frac{{{x1:g}+{x2:g}}}{{2}},\frac{{{y1:g}+{y2:g}}}{{2}}\right)"
        elif key in ("slope", "gradient"):
            if x1 == x2:
                return blocked_result("coordinate_geometry", "Slope is undefined for a vertical line.", domain="mathematics")
            value = {"slope": (y2 - y1) / (x2 - x1)}
            latex = rf"m=\frac{{{y2:g}-({y1:g})}}{{{x2:g}-({x1:g})}}"
        else:
            value = {"distance": math.hypot(x2 - x1, y2 - y1)}
            latex = rf"d=\sqrt{{({x2:g}-({x1:g}))^2+({y2:g}-({y1:g}))^2}}"
    except Exception as exc:
        return blocked_result("coordinate_geometry", f"Geometry calculation failed: {exc}", domain="mathematics")
    return _result("coordinate_geometry", key, f"{point_a}, {point_b}", value, {"expression": latex},
                   [f"Apply the {key} formula to the two supplied points."], f"Result: {value}.")

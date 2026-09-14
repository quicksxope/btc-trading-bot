"""Safe entry-rule DSL v2 (no eval)."""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

_TOKEN = re.compile(
    r"cross_above|cross_below|and|or|not|\>=|\<=|>|<|==|!=|[\w.]+|\(|\)|,"
)


@dataclass
class RuleSet:
    long_when: str = ""
    short_when: str = ""


def _tokenize(expr: str) -> list[str]:
    expr = expr.strip()
    if not expr:
        return []
    tokens: list[str] = []
    pos = 0
    while pos < len(expr):
        if expr[pos].isspace():
            pos += 1
            continue
        m = _TOKEN.match(expr, pos)
        if not m:
            raise ValueError(f"Invalid token near: {expr[pos:pos+20]}")
        tokens.append(m.group(0))
        pos = m.end()
    return tokens


class _Parser:
    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.i = 0

    def parse(self) -> "_Node":
        return self._or_expr()

    def _peek(self) -> str | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _eat(self, tok: str | None = None) -> str:
        t = self._peek()
        if t is None:
            raise ValueError("Unexpected end of expression")
        if tok and t != tok:
            raise ValueError(f"Expected {tok}, got {t}")
        self.i += 1
        return t

    def _or_expr(self) -> "_Node":
        left = self._and_expr()
        while self._peek() == "or":
            self._eat("or")
            left = _Node("or", left, self._and_expr())
        return left

    def _and_expr(self) -> "_Node":
        left = self._not_expr()
        while self._peek() == "and":
            self._eat("and")
            left = _Node("and", left, self._not_expr())
        return left

    def _not_expr(self) -> "_Node":
        if self._peek() == "not":
            self._eat("not")
            return _Node("not", self._primary(), None)
        return self._primary()

    def _primary(self) -> "_Node":
        t = self._peek()
        if t == "(":
            self._eat("(")
            n = self._or_expr()
            self._eat(")")
            return n
        if t in ("cross_above", "cross_below"):
            fn = self._eat()
            self._eat("(")
            a = self._eat()
            self._eat(",")
            b = self._eat()
            self._eat(")")
            return _Node(fn, _Node("ref", a, None), _Node("ref", b, None))
        return self._comparison()

    def _comparison(self) -> "_Node":
        left = self._eat()
        op = self._peek()
        if op in (">", "<", ">=", "<=", "==", "!="):
            self._eat()
            right = self._eat()
            return _Node("cmp", _Node("ref", left, None), _Node("ref", right, None), op=op)
        return _Node("ref", left, None)


class _Node:
    def __init__(self, kind: str, a: "_Node | str | None", b: "_Node | str | None", op: str | None = None):
        self.kind = kind
        self.a = a
        self.b = b
        self.op = op


def _parse(expr: str) -> _Node:
    tokens = _tokenize(expr)
    if not tokens:
        return _Node("const", "0", None)
    return _Parser(tokens).parse()


def _ref_value(name: str, i: int, ctx: dict[str, np.ndarray], prev_ctx: dict[str, np.ndarray]) -> float:
    key = name.lower()
    if key in ("true", "1"):
        return 1.0
    if key in ("false", "0"):
        return 0.0
    try:
        return float(name)
    except ValueError:
        pass
    arr = ctx.get(name)
    if arr is None:
        arr = ctx.get(name.upper())
    if arr is None:
        arr = ctx.get(name.lower())
    if arr is None:
        raise KeyError(f"Unknown ref: {name}")
    if i >= len(arr) or np.isnan(arr[i]):
        return float("nan")
    return float(arr[i])


def _eval_node(
    node: _Node,
    i: int,
    ctx: dict[str, np.ndarray],
    prev_ctx: dict[str, np.ndarray],
) -> bool:
    if node.kind == "const":
        return bool(float(node.a))  # type: ignore[arg-type]
    if node.kind == "ref":
        v = _ref_value(str(node.a), i, ctx, prev_ctx)
        return bool(v) and not np.isnan(v)
    if node.kind == "not":
        return not _eval_node(node.a, i, ctx, prev_ctx)  # type: ignore[arg-type]
    if node.kind == "and":
        return _eval_node(node.a, i, ctx, prev_ctx) and _eval_node(node.b, i, ctx, prev_ctx)  # type: ignore[arg-type]
    if node.kind == "or":
        return _eval_node(node.a, i, ctx, prev_ctx) or _eval_node(node.b, i, ctx, prev_ctx)  # type: ignore[arg-type]
    if node.kind == "cross_above":
        la = str(node.a.a)  # type: ignore[union-attr]
        lb = str(node.b.a)  # type: ignore[union-attr]
        a0, b0 = _ref_value(la, i - 1, ctx, prev_ctx), _ref_value(lb, i - 1, ctx, prev_ctx)
        a1, b1 = _ref_value(la, i, ctx, prev_ctx), _ref_value(lb, i, ctx, prev_ctx)
        if i < 1 or any(np.isnan(x) for x in (a0, b0, a1, b1)):
            return False
        return a0 <= b0 and a1 > b1
    if node.kind == "cross_below":
        la = str(node.a.a)  # type: ignore[union-attr]
        lb = str(node.b.a)  # type: ignore[union-attr]
        a0, b0 = _ref_value(la, i - 1, ctx, prev_ctx), _ref_value(lb, i - 1, ctx, prev_ctx)
        a1, b1 = _ref_value(la, i, ctx, prev_ctx), _ref_value(lb, i, ctx, prev_ctx)
        if i < 1 or any(np.isnan(x) for x in (a0, b0, a1, b1)):
            return False
        return a0 >= b0 and a1 < b1
    if node.kind == "cmp":
        op = node.op or ">"
        left = _ref_value(str(node.a.a), i, ctx, prev_ctx)  # type: ignore[union-attr]
        right = _ref_value(str(node.b.a), i, ctx, prev_ctx)  # type: ignore[union-attr]
        if np.isnan(left) or np.isnan(right):
            return False
        if op == ">":
            return left > right
        if op == "<":
            return left < right
        if op == ">=":
            return left >= right
        if op == "<=":
            return left <= right
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
    return False


def validate_expression(expr: str) -> None:
    _parse(expr)


def build_series_context(
    primary: pd.DataFrame,
    context_frames: dict[str, pd.DataFrame],
    context_idx: dict[str, pd.Series],
    indicator_specs: list[dict],
) -> dict[str, np.ndarray]:
    from engine.indicators import compute_indicator_outputs

    ctx_arrays: dict[str, np.ndarray] = {}
    n = len(primary)
    ctx_arrays["primary_close"] = primary["close"].to_numpy(dtype=float)

    for spec in indicator_specs:
        name = spec.get("name", "RSI")
        tf = spec.get("timeframe", "primary")
        params = spec.get("params", {})
        output = spec.get("output")
        df = primary if tf == "primary" else context_frames.get(tf, primary)
        outputs = compute_indicator_outputs(name, df, params)
        if output and output in outputs:
            series = outputs[output]
        else:
            series = next(iter(outputs.values()))
        if tf != "primary":
            aligned = series.iloc[context_idx[tf].clip(lower=0).values].reset_index(drop=True)
            base = aligned.to_numpy(dtype=float)
        else:
            base = series.to_numpy(dtype=float)
        prefix = f"{tf}_{name.upper()}"
        for out_name, ser in outputs.items():
            if tf != "primary":
                arr = ser.iloc[context_idx[tf].clip(lower=0).values].reset_index(drop=True).to_numpy(dtype=float)
            else:
                arr = ser.to_numpy(dtype=float)
            ctx_arrays[f"{prefix}_{out_name}"] = arr
        if len(outputs) == 1:
            ctx_arrays[f"{prefix}_value"] = base

    return ctx_arrays


def signals_from_rules(
    rules: RuleSet,
    primary: pd.DataFrame,
    context_frames: dict[str, pd.DataFrame],
    context_idx: dict[str, pd.Series],
    indicator_specs: list[dict],
) -> pd.Series:
    if rules.long_when:
        validate_expression(rules.long_when)
    if rules.short_when:
        validate_expression(rules.short_when)
    long_root = _parse(rules.long_when) if rules.long_when else None
    short_root = _parse(rules.short_when) if rules.short_when else None
    ctx = build_series_context(primary, context_frames, context_idx, indicator_specs)
    prev_ctx = ctx
    n = len(primary)
    out = np.zeros(n, dtype=int)
    state = 0
    for i in range(n):
        if long_root and _eval_node(long_root, i, ctx, prev_ctx):
            state = 1
        elif short_root and _eval_node(short_root, i, ctx, prev_ctx):
            state = -1
        out[i] = state
    return pd.Series(out, index=primary.index)

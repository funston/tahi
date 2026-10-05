"""
Static detector for silent-degradation defects in RAG evaluation code.

A silent-degradation defect is code that, on failure or misuse, substitutes a
weaker component or a wrong measurement and *returns successfully*. The output
is indistinguishable from a correct run, so the defect is invisible to unit
tests, invisible to CI, and silently confounds any A/B comparison.

Each detector below corresponds to a defect observed in a real codebase. The
analysis is AST-based rather than regex-based because the distinguishing feature
is almost always structural -- a `return` inside an `except` handler, a
comparison operator inside a function whose name claims exactness -- and regex
over source text produces too many false positives to support a prevalence claim.

Usage:
    python detector.py /path/to/repo [/path/to/another ...] --json out.json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCHEMA_VERSION = "1.0"


@dataclass
class Finding:
    defect: str
    severity: str          # "confounding" | "misleading" | "suspicious"
    repo: str
    file: str
    line: int
    function: str
    evidence: str
    rationale: str

    def key(self) -> tuple:
        return (self.repo, self.file, self.line, self.defect)


@dataclass
class RepoReport:
    repo: str
    files_scanned: int = 0
    lines_scanned: int = 0
    findings: list[Finding] = field(default_factory=list)
    parse_failures: list[str] = field(default_factory=list)

    def defect_types(self) -> set[str]:
        return {f.defect for f in self.findings}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _name_of(node: ast.AST) -> str:
    """Best-effort dotted name for a call target or attribute chain."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_name_of(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return _name_of(node.func)
    return ""


def _src(node: ast.AST, lines: list[str]) -> str:
    lineno = getattr(node, "lineno", 0)
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1].strip()[:200]
    return ""


def _returns_in_handler(handler: ast.ExceptHandler) -> list[ast.Return]:
    return [n for n in ast.walk(handler) if isinstance(n, ast.Return) and n.value is not None]


def _is_broad(handler: ast.ExceptHandler) -> bool:
    """True for `except:` or `except Exception:` / `except BaseException:`."""
    if handler.type is None:
        return True
    names = {_name_of(handler.type)}
    if isinstance(handler.type, ast.Tuple):
        names = {_name_of(e) for e in handler.type.elts}
    return bool(names & {"Exception", "BaseException"})


def _fn_name_matches(fn: str, *fragments: str) -> bool:
    """Token-level match on a snake_case function name.

    Substring matching is unusable here: the fragment `_em` matches `embedding`,
    `system`, and `item`, which in a first pass over eight repositories produced
    a ~90% false-positive rate and a meaningless prevalence figure. Names are
    split into tokens and matched whole.
    """
    tokens = set(re.split(r"[_\W]+", fn.lower())) - {""}
    joined = fn.lower()
    for frag in fragments:
        f = frag.strip("_").lower()
        if f in tokens:
            return True
        # multi-word fragments ("exact_match") match as an adjacent sequence
        if "_" in frag and frag.strip("_").lower() in joined:
            return True
    return False


# --------------------------------------------------------------------------
# Detectors
# --------------------------------------------------------------------------

class Visitor(ast.NodeVisitor):
    def __init__(self, repo: str, path: str, lines: list[str]):
        self.repo, self.path, self.lines = repo, path, lines
        self.findings: list[Finding] = []
        self._fn_stack: list[str] = []

    @property
    def _fn(self) -> str:
        return self._fn_stack[-1] if self._fn_stack else "<module>"

    def _add(self, defect, severity, node, rationale):
        self.findings.append(Finding(
            defect=defect, severity=severity, repo=self.repo, file=self.path,
            line=getattr(node, "lineno", 0), function=self._fn,
            evidence=_src(node, self.lines), rationale=rationale,
        ))

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._fn_stack.append(node.name)
        self._check_fallback_generator(node)
        self._check_substring_em(node)
        self._check_set_based_f1(node)
        self._check_wallclock_ttft(node)
        self.generic_visit(node)
        self._fn_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    # D0 -- a function whose whole job is to emit placeholder model output
    def _check_fallback_generator(self, node):
        if not _fn_name_matches(node.name, "fallback", "_stub", "dummy_complete",
                                "mock_complete", "offline_complete"):
            return
        for ret in [n for n in ast.walk(node) if isinstance(n, ast.Return) and n.value]:
            for const in [c for c in ast.walk(ret) if isinstance(c, ast.Constant)]:
                if isinstance(const.value, str) and len(const.value) > 12:
                    self._add(
                        "placeholder_output_on_error", "confounding", ret,
                        "A fallback path returns placeholder text where model output "
                        "is expected, without raising. A misconfigured run then "
                        "produces a complete, well-formed results file containing no "
                        "model output at all.",
                    )
                    return

    # D1 -- substring "exact match"
    def _check_substring_em(self, node):
        if not _fn_name_matches(node.name, "exact_match", "exactmatch", "_em",
                                "em_score", "compute_em", "match_score"):
            return
        pred_like = ("pred", "prediction", "hypothesis", "answer", "output",
                     "response", "candidate", "generated")
        ref_like = ("ref", "reference", "gold", "target", "truth", "expected",
                    "ground")
        for cmp_node in [n for n in ast.walk(node) if isinstance(n, ast.Compare)]:
            if any(isinstance(op, ast.In) for op in cmp_node.ops):
                names = " ".join(
                    _name_of(x).lower() for x in ast.walk(cmp_node)
                    if isinstance(x, (ast.Name, ast.Attribute))
                )
                if not (any(p in names for p in pred_like)
                        and any(r in names for r in ref_like)):
                    continue
                self._add(
                    "substring_exact_match", "misleading", cmp_node,
                    "A containment test (`in`) inside a function named for exact "
                    "match. Yields EM=1.0 for predictions that merely contain the "
                    "reference, so EM can exceed F1 -- a mathematically impossible "
                    "pairing that is nonetheless reported.",
                )
                return

    # D2 -- set-based token F1 (ignores multiplicity)
    def _check_set_based_f1(self, node):
        if not _fn_name_matches(node.name, "f1", "token_f1", "compute_f1", "_f1_"):
            return
        for call in [n for n in ast.walk(node) if isinstance(n, ast.Call)]:
            if _name_of(call.func) == "set":
                self._add(
                    "set_based_token_f1", "misleading", call,
                    "Token F1 computed over sets discards multiplicity, so a "
                    "prediction repeating one correct token scores as though it "
                    "produced many. Reference implementations use a multiset "
                    "(collections.Counter).",
                )
                return

    # D3 -- total latency reported as time-to-first-token
    def _check_wallclock_ttft(self, node):
        assigns = [n for n in ast.walk(node) if isinstance(n, ast.Assign)]
        ttft_targets = []
        for a in assigns:
            for t in a.targets:
                nm = _name_of(t).lower()
                if "ttft" in nm or "time_to_first" in nm:
                    ttft_targets.append(a)
        if not ttft_targets:
            return
        # Streaming implies iteration over a response; its absence means the
        # value can only be total latency.
        has_stream = any(
            isinstance(n, (ast.For, ast.AsyncFor)) for n in ast.walk(node)
        ) or any(
            "stream" in _name_of(k).lower() or (isinstance(k, ast.keyword) and k.arg == "stream")
            for k in ast.walk(node) if isinstance(k, ast.keyword)
        )
        if not has_stream:
            for a in ttft_targets:
                self._add(
                    "wallclock_as_ttft", "misleading", a,
                    "A value named TTFT assigned without any streaming iteration. "
                    "Total non-streaming latency scales with OUTPUT LENGTH, so a "
                    "system that answers more tersely appears to have faster "
                    "prefill when prefill did not change.",
                )

    # D4/D5/D6 -- silent substitution inside broad exception handlers
    def visit_Try(self, node: ast.Try):
        for handler in node.handlers:
            if not _is_broad(handler):
                continue
            returns = _returns_in_handler(handler)

            # Substitution by ASSIGNMENT, not return -- the common cache-populating
            # shape: `except Exception: _CACHE[key] = WeakerThing()`
            for assign in [n for n in ast.walk(handler) if isinstance(n, ast.Assign)]:
                rhs = _name_of(assign.value).lower()
                if any(k in rhs for k in ("hashencoder", "hashedtoken", "fallback",
                                          "dummy", "mock", "stub", "naive")):
                    self._add(
                        "silent_component_fallback", "confounding", assign,
                        "A broad exception handler assigns a substitute component "
                        "(commonly into a module-level cache). Every later caller "
                        "silently receives the substitute, and no error is raised at "
                        "any point.",
                    )
                    break

            for ret in returns:
                target = _name_of(ret.value).lower()
                rv = ret.value

                # Encoder / embedding model substitution
                if any(k in target for k in ("hashencoder", "hashedtoken", "fallback",
                                             "dummy", "mock", "stub", "naive")):
                    self._add(
                        "silent_component_fallback", "confounding", ret,
                        "A broad exception handler returns a substitute component. "
                        "The caller cannot distinguish the substitute from the real "
                        "one, so a dependency failure silently changes what is being "
                        "measured while the run reports success.",
                    )
                # Placeholder string returned where model output is expected
                elif isinstance(rv, (ast.Constant, ast.JoinedStr)):
                    val = rv.value if isinstance(rv, ast.Constant) else ""
                    if isinstance(val, str) and len(val) > 8:
                        self._add(
                            "placeholder_output_on_error", "confounding", ret,
                            "A broad handler returns placeholder text where model "
                            "output is expected. Downstream scoring treats it as a "
                            "real generation, producing a results file that is "
                            "structurally indistinguishable from a valid run.",
                        )

            # Device downgrade masked as a memory error
            for n in ast.walk(handler):
                if isinstance(n, ast.Call):
                    nm = _name_of(n).lower()
                    if nm.endswith(".cpu") or nm.endswith("to") and "cpu" in _src(n, self.lines).lower():
                        self._add(
                            "silent_device_downgrade", "suspicious", n,
                            "A broad handler falls back to CPU. If the message "
                            "attributes this to memory, it will mask unrelated "
                            "faults (driver mismatch, an occupied device), and the "
                            "resulting run reports zero VRAM as though normal.",
                        )
                        break
        self.generic_visit(node)


# D7 -- type-compatible semantic substitution (the TAHI defect)
def check_dimension_matched_override(tree: ast.AST, repo: str, path: str,
                                     lines: list[str]) -> list[Finding]:
    """An optional caller-supplied vector that overrides an internal encoder.

    The defect: the override is accepted whenever it is not None, and because a
    hash embedding can be generated at the encoder's own width, the shapes match
    and nothing raises. Semantic retrieval silently becomes hash retrieval.
    """
    out: list[Finding] = []
    for fn in [n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        args = [a.arg for a in fn.args.args + fn.args.kwonlyargs]
        override = [a for a in args
                    if any(k in a.lower() for k in
                           ("query_embedding", "query_vector", "precomputed_embedding",
                            "embedding_override", "query_emb"))]
        if not override:
            continue
        for test in [n for n in ast.walk(fn) if isinstance(n, ast.IfExp)] + \
                    [n.test for n in ast.walk(fn) if isinstance(n, ast.If)]:
            txt = ast.dump(test)
            if any(o in txt for o in override) and "encode" in ast.dump(fn):
                out.append(Finding(
                    defect="dimension_matched_override", severity="confounding",
                    repo=repo, file=path, line=getattr(test, "lineno", fn.lineno),
                    function=fn.name, evidence=_src(test, lines),
                    rationale=(
                        "A caller-supplied embedding overrides the internal encoder "
                        "on a bare not-None test. Any same-width vector is accepted, "
                        "including a non-semantic one, with no error. Two arms of an "
                        "A/B can then retrieve by different mechanisms while sharing "
                        "an index -- the defect found in TAHI, where the graph arm "
                        "retrieved by character-sum hash and the baseline by "
                        "sentence-transformer."
                    ),
                ))
                break
    return out


SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "build",
             "dist", ".tox", ".mypy_cache", "site-packages", ".pytest_cache",
             # Tests assert containment as a matter of course and examples are
             # demonstrations, not measurement code. Including either inflates
             # the prevalence figure with findings that confound nothing.
             "tests", "test", "testing", "examples", "example", "docs",
             "benchmarks_legacy", "scripts", "notebooks"}


def _is_test_file(rel: str) -> bool:
    base = rel.rsplit("/", 1)[-1]
    return base.startswith("test_") or base.endswith("_test.py") or "/tests/" in rel


def scan_repo(root: Path, name: str | None = None) -> RepoReport:
    repo = name or root.name
    report = RepoReport(repo=repo)
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if _is_test_file(path.relative_to(root).as_posix()):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        report.files_scanned += 1
        lines = source.splitlines()
        report.lines_scanned += len(lines)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            report.parse_failures.append(rel)
            continue
        v = Visitor(repo, rel, lines)
        v.visit(tree)
        report.findings.extend(v.findings)
        report.findings.extend(check_dimension_matched_override(tree, repo, rel, lines))

    # De-duplicate: one finding per (file, line, defect).
    seen, unique = set(), []
    for f in report.findings:
        if f.key() not in seen:
            seen.add(f.key())
            unique.append(f)
    report.findings = unique
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="Repository roots to scan")
    ap.add_argument("--json", help="Write full findings to this path")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    reports = [scan_repo(Path(p).resolve()) for p in args.paths]

    print(f"{'repository':<34} {'files':>6} {'kloc':>7} {'defects':>8}  types")
    print("-" * 96)
    for r in sorted(reports, key=lambda x: -len(x.findings)):
        types = ",".join(sorted(t[:18] for t in r.defect_types())) or "-"
        print(f"{r.repo:<34} {r.files_scanned:>6} {r.lines_scanned/1000:>7.1f} "
              f"{len(r.findings):>8}  {types}")

    affected = [r for r in reports if r.findings]
    print("-" * 96)
    print(f"{len(affected)} of {len(reports)} repositories contain at least one "
          f"silent-degradation defect.")

    by_defect: dict[str, int] = {}
    for r in reports:
        for d in r.defect_types():
            by_defect[d] = by_defect.get(d, 0) + 1
    if by_defect:
        print("\nprevalence by defect (repositories affected):")
        for d, c in sorted(by_defect.items(), key=lambda kv: -kv[1]):
            print(f"  {d:<34} {c:>3} / {len(reports)}")

    if not args.quiet:
        for r in affected:
            for f in r.findings:
                print(f"\n[{f.severity}] {f.defect}\n  {f.repo}/{f.file}:{f.line} "
                      f"in {f.function}()\n  > {f.evidence}")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "n_repos": len(reports),
            "n_affected": len(affected),
            "prevalence_by_defect": by_defect,
            "reports": [
                {**asdict(r), "findings": [asdict(f) for f in r.findings]}
                for r in reports
            ],
        }, indent=2), encoding="utf-8")
        print(f"\nWrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

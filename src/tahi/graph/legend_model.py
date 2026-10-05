"""
Legend/Pure model loader — classes, properties, and their types.

A Legend model is already a typed graph: classes carry properties, each property
has a type and a multiplicity, and a property whose type is another class is an
edge. Nothing here is extracted or inferred by a language model; this is a parse
of the `.pure` source that Legend Studio itself round-trips.

Pure's domain grammar for a class, reduced to what this needs::

    Class <<profile.stereotype>> {doc.doc = '...'} pkg::sub::Name extends Other
    {
        firstName : String[1];
        manager   : Person[0..1];
        fullName() { ... } : String[1];      <- derived, skipped
    }

The full grammar lives in legend-engine's ANTLR sources
(`DomainParserGrammar.g4`). This reader deliberately handles only class and
property declarations, because that is the whole vocabulary a decode-time
constraint needs: the set of identifiers a query is allowed to name.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["LegendModel", "LegendClass", "LegendProperty"]

# `Class` with optional stereotypes <<...>> and tagged values {...}, then the
# qualified name, then an optional `extends`.
_CLASS = re.compile(
    r"\bClass\s+"
    r"(?:<<[^>]*>>\s*)?"                       # stereotypes
    r"(?:\{[^{}]*\}\s*)?"                      # tagged values
    r"(?P<name>[A-Za-z_][\w]*(?:::[A-Za-z_][\w]*)*)"
    r"(?:\s+extends\s+(?P<parent>[\w:]+))?"
    r"\s*\{",
    re.M,
)

# `name : Type[mult];` — a plain property. Derived properties carry `()` before
# the colon and are excluded: they are functions, not part of the stored shape.
_PROP = re.compile(
    r"^\s*(?:<<[^>]*>>\s*)?(?:\{[^{}]*\}\s*)?"
    r"(?P<name>[A-Za-z_][\w]*)\s*"
    r":\s*(?P<type>[\w:]+)\s*"
    r"\[(?P<mult>[^\]]*)\]\s*;",
    re.M,
)

_PRIMITIVES = {
    "String", "Integer", "Float", "Decimal", "Boolean", "Date", "DateTime",
    "StrictDate", "LatestDate", "Number", "Byte", "Binary", "Any",
}


@dataclass(frozen=True)
class LegendProperty:
    name: str
    type: str
    multiplicity: str

    @property
    def is_primitive(self) -> bool:
        return self.type.split("::")[-1] in _PRIMITIVES


@dataclass
class LegendClass:
    name: str                                   # fully qualified, pkg::Name
    parent: str | None = None
    properties: list[LegendProperty] = field(default_factory=list)
    source: str = ""

    @property
    def short_name(self) -> str:
        return self.name.split("::")[-1]

    @property
    def property_names(self) -> list[str]:
        return [p.name for p in self.properties]


class LegendModel:
    """Every class and property found in a set of `.pure` files."""

    def __init__(self, paths: list[Path] | None = None):
        self.classes: dict[str, LegendClass] = {}
        for p in paths or []:
            self.add_file(p)

    # ------------------------------------------------------------------ load
    def add_file(self, path: Path) -> int:
        text = path.read_text(encoding="utf-8", errors="replace")
        found = 0
        for m in _CLASS.finditer(text):
            body = _balanced_body(text, m.end() - 1)
            if body is None:
                continue
            cls = LegendClass(name=m.group("name"), parent=m.group("parent"),
                              source=path.name)
            seen: set[str] = set()
            for pm in _PROP.finditer(body):
                nm = pm.group("name")
                if nm in seen:
                    continue
                seen.add(nm)
                cls.properties.append(
                    LegendProperty(nm, pm.group("type"), pm.group("mult")))
            if cls.properties:
                # later files win only if they carry more detail
                prev = self.classes.get(cls.name)
                if prev is None or len(cls.properties) > len(prev.properties):
                    self.classes[cls.name] = cls
                found += 1
        return found

    # --------------------------------------------------------------- vocabulary
    @property
    def property_vocabulary(self) -> set[str]:
        """Every property name declared anywhere in the model.

        This is the allowed set for a decode-time constraint: a query may name
        a property only if some class in the model declares it.
        """
        return {p.name for c in self.classes.values() for p in c.properties}

    @property
    def class_vocabulary(self) -> set[str]:
        names = set(self.classes)
        names |= {c.short_name for c in self.classes.values()}
        return names

    def properties_of(self, class_name: str, *, inherited: bool = True) -> list[str]:
        """Declared property names, walking `extends` when `inherited`."""
        out: list[str] = []
        seen: set[str] = set()
        cur = self.classes.get(class_name)
        depth = 0
        while cur is not None and depth < 20:
            for p in cur.properties:
                if p.name not in seen:
                    seen.add(p.name)
                    out.append(p.name)
            if not inherited or not cur.parent:
                break
            cur = self.classes.get(cur.parent)
            depth += 1
        return out

    # ------------------------------------------------------------------ query
    def resolve(self, name: str, *, context: str | None = None) -> LegendClass | None:
        """Find a class by fully-qualified name, or by short name.

        Pure resolves a bare type name inside the referring element's own
        namespace, so `context` matters. The protocol metamodel ships once per
        released version, which means a short name like `SourceInformation`
        exists in ten packages at once; without context it is ambiguous and
        every one of those 261 references would be treated as a dangling edge.

        Order: exact match, then the longest shared package prefix with
        `context`, then an unambiguous global short name.
        """
        if name in self.classes:
            return self.classes[name]
        hits = [c for c in self.classes.values() if c.short_name == name]
        if not hits:
            return None
        if len(hits) == 1:
            return hits[0]
        if context:
            ctx = context.split("::")[:-1]
            best, best_score = None, -1
            for c in hits:
                pkg = c.name.split("::")[:-1]
                score = 0
                for a, b in zip(ctx, pkg, strict=False):
                    if a != b:
                        break
                    score += 1
                if score > best_score:
                    best, best_score = c, score
            if best_score > 0:
                return best
        return None

    def neighbours(self, class_name: str) -> list[tuple[str, str]]:
        """`(property, target class)` for properties whose type is a class here.

        These are the edges. A property typed `String` is an attribute; a
        property typed `Firm` is a traversable relationship.
        """
        cls = self.resolve(class_name)
        if cls is None:
            return []
        out = []
        for prop in cls.properties:
            if prop.is_primitive:
                continue
            tgt = self.resolve(prop.type, context=cls.name)
            if tgt is not None:
                out.append((prop.name, tgt.name))
        return out

    def walk(self, start: str, path: list[str]) -> str | None:
        """Follow a property path, e.g. ``["firm", "employees"]``.

        Returns the fully-qualified class reached, or None if any step is not a
        declared property of the class currently in hand. This is the check a
        query planner needs: `$x.firm.legalName` is valid only if `firm` is a
        property of the start class and `legalName` is a property of its type.
        """
        cur = self.resolve(start)
        if cur is None:
            return None
        for step in path:
            prop = next((p for p in self.properties_of_class(cur.name)
                         if p.name == step), None)
            if prop is None:
                return None
            nxt = self.resolve(prop.type, context=cur.name)
            if nxt is None:
                return prop.type          # primitive or unresolved leaf
            cur = nxt
        return cur.name

    def properties_of_class(self, class_name: str,
                            *, inherited: bool = True) -> list[LegendProperty]:
        """Full `LegendProperty` objects, walking `extends` when `inherited`."""
        out: list[LegendProperty] = []
        seen: set[str] = set()
        cur = self.resolve(class_name)
        depth = 0
        while cur is not None and depth < 20:
            for prop in cur.properties:
                if prop.name not in seen:
                    seen.add(prop.name)
                    out.append(prop)
            if not inherited or not cur.parent:
                break
            cur = self.resolve(cur.parent, context=cur.name)
            depth += 1
        return out

    def validate_path(self, start: str, path: list[str]) -> tuple[bool, str]:
        """Is `start.path[0].path[1]...` legal? Returns (ok, explanation).

        The explanation is written to be handed straight back to a model, in the
        same shape the MetaQA correction loop uses: name what is wrong, and what
        was available instead.
        """
        cur = self.resolve(start)
        if cur is None:
            return False, f"No class named '{start}' in this model."
        walked = [cur.name]
        for step in path:
            props = self.properties_of_class(cur.name)
            prop = next((p for p in props if p.name == step), None)
            if prop is None:
                names = ", ".join(sorted(p.name for p in props)[:15])
                return False, (f"Class {cur.name} has no property '{step}'. "
                               f"It declares: {names}")
            nxt = self.resolve(prop.type, context=cur.name)
            if nxt is None:
                walked.append(prop.type)
                return True, " -> ".join(walked)
            cur = nxt
            walked.append(cur.name)
        return True, " -> ".join(walked)

    def edges(self) -> list[tuple[str, str, str]]:
        """Every `(source class, property, target class)` edge in the model."""
        out = []
        for name in self.classes:
            for prop, tgt in self.neighbours(name):
                out.append((name, prop, tgt))
        return out

    def __len__(self) -> int:
        return len(self.classes)

    def stats(self) -> dict[str, int]:
        props = [len(c.properties) for c in self.classes.values()]
        return {
            "classes": len(self.classes),
            "properties": sum(props),
            "distinct_property_names": len(self.property_vocabulary),
            "max_properties_on_a_class": max(props, default=0),
        }


def _balanced_body(text: str, open_brace: int) -> str | None:
    """Slice from `{` to its matching `}`. Returns None if unbalanced."""
    depth = 0
    for i in range(open_brace, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace + 1:i]
    return None

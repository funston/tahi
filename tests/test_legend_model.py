"""
Tests for the Legend/Pure model reader.

Two kinds of test here, deliberately separated:

  * Parser tests use small inline `.pure` fixtures, so the expected result is
    visible in the test itself and does not depend on a download.
  * Corpus tests run against the real `finos/legend-engine` sources in
    `data/legend/pure`, and are skipped when that directory is absent. Their
    assertions are properties that must hold of any sane parse (edges resolve,
    no class is empty, walks terminate) rather than counts that would break
    every time upstream adds a file.
"""
from __future__ import annotations

import sys
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tahi.graph.legend_model import LegendModel  # noqa: E402

CORPUS = Path(__file__).resolve().parent.parent / "data" / "legend" / "pure"


def _model(source: str, tmp: Path) -> LegendModel:
    f = tmp / "t.pure"
    f.write_text(textwrap.dedent(source))
    return LegendModel([f])


class ParserTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._d = tempfile.TemporaryDirectory()
        self.tmp = Path(self._d.name)

    def tearDown(self):
        self._d.cleanup()

    def test_class_and_properties(self):
        m = _model("""
            Class demo::Person
            {
              firstName: String[1];
              lastName: String[1];
              age: Integer[0..1];
            }
            """, self.tmp)
        self.assertEqual(len(m), 1)
        self.assertEqual(m.properties_of("demo::Person"),
                         ["firstName", "lastName", "age"])

    def test_multiplicity_and_type_are_captured(self):
        m = _model("""
            Class demo::Firm
            {
              legalName: String[1];
              employees: demo::Person[*];
            }
            Class demo::Person { firstName: String[1]; }
            """, self.tmp)
        props = {p.name: p for p in m.resolve("demo::Firm").properties}
        self.assertEqual(props["employees"].type, "demo::Person")
        self.assertEqual(props["employees"].multiplicity, "*")
        self.assertEqual(props["legalName"].multiplicity, "1")
        self.assertTrue(props["legalName"].is_primitive)
        self.assertFalse(props["employees"].is_primitive)

    def test_derived_properties_are_excluded(self):
        """`fullName()` is a function, not part of the stored shape."""
        m = _model("""
            Class demo::Person
            {
              firstName: String[1];
              fullName() { $this.firstName } : String[1];
            }
            """, self.tmp)
        self.assertEqual(m.properties_of("demo::Person"), ["firstName"])

    def test_stereotypes_and_tagged_values_do_not_break_the_class_header(self):
        m = _model("""
            Class <<temporal.businesstemporal>> {doc.doc = 'a firm'} demo::Firm
            {
              legalName: String[1];
            }
            """, self.tmp)
        self.assertIsNotNone(m.resolve("demo::Firm"))
        self.assertEqual(m.properties_of("demo::Firm"), ["legalName"])

    def test_inheritance_is_walked(self):
        m = _model("""
            Class demo::Base { id: String[1]; }
            Class demo::Sub extends demo::Base { name: String[1]; }
            """, self.tmp)
        self.assertEqual(set(m.properties_of("demo::Sub")), {"id", "name"})
        self.assertEqual(m.properties_of("demo::Sub", inherited=False), ["name"])

    def test_inheritance_cycle_terminates(self):
        m = _model("""
            Class demo::A extends demo::B { a: String[1]; }
            Class demo::B extends demo::A { b: String[1]; }
            """, self.tmp)
        self.assertEqual(set(m.properties_of("demo::A")), {"a", "b"})

    def test_nested_braces_do_not_truncate_the_class_body(self):
        """A `{...}` inside the body must not be read as the closing brace."""
        m = _model("""
            Class demo::Thing
            {
              first: String[1];
              derived() { if(true, |1, |2) } : Integer[1];
              last: String[1];
            }
            """, self.tmp)
        self.assertEqual(m.properties_of("demo::Thing"), ["first", "last"])


class QueryTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._d = tempfile.TemporaryDirectory()
        self.m = _model("""
            Class model::Firm
            {
              legalName: String[1];
              employees: model::Person[*];
            }
            Class model::Person
            {
              firstName: String[1];
              lastName: String[1];
              firm: model::Firm[0..1];
            }
            """, Path(self._d.name))

    def tearDown(self):
        self._d.cleanup()

    def test_neighbours_are_only_class_typed_properties(self):
        self.assertEqual(self.m.neighbours("model::Firm"),
                         [("employees", "model::Person")])

    def test_resolve_by_short_name(self):
        self.assertEqual(self.m.resolve("Firm").name, "model::Firm")
        self.assertIsNone(self.m.resolve("Nope"))

    def test_ambiguous_short_name_resolves_within_the_referring_package(self):
        """The protocol metamodel ships one copy per released version, so a bare
        short name is ambiguous globally but unambiguous inside its own tree."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            m = _model("""
                Class a::v1::Info { x: String[1]; }
                Class a::v2::Info { x: String[1]; }
                Class a::v1::Holder { info: Info[1]; }
                """, Path(d))
            self.assertIsNone(m.resolve("Info"))                       # ambiguous
            self.assertEqual(m.resolve("Info", context="a::v1::Holder").name,
                             "a::v1::Info")
            self.assertEqual(m.neighbours("a::v1::Holder"),
                             [("info", "a::v1::Info")])

    def test_walk_follows_a_property_path(self):
        self.assertEqual(self.m.walk("model::Firm", ["employees"]), "model::Person")
        self.assertEqual(self.m.walk("model::Firm", ["employees", "firm"]),
                         "model::Firm")

    def test_walk_returns_the_leaf_type_for_a_primitive(self):
        self.assertEqual(self.m.walk("model::Firm", ["employees", "firstName"]),
                         "String")

    def test_walk_rejects_a_property_that_does_not_exist(self):
        self.assertIsNone(self.m.walk("model::Firm", ["employees", "salary"]))

    def test_validate_path_explains_what_was_available(self):
        ok, why = self.m.validate_path("model::Person", ["firm", "name"])
        self.assertFalse(ok)
        self.assertIn("has no property 'name'", why)
        self.assertIn("legalName", why)      # what it should have used

    def test_validate_path_accepts_a_real_path(self):
        ok, why = self.m.validate_path("model::Person", ["firm", "legalName"])
        self.assertTrue(ok)
        self.assertIn("model::Firm", why)

    def test_unknown_start_class_is_reported(self):
        ok, why = self.m.validate_path("model::Ghost", ["x"])
        self.assertFalse(ok)
        self.assertIn("No class named", why)


@unittest.skipUnless(CORPUS.is_dir() and any(CORPUS.glob("*.pure")),
                     "legend corpus not downloaded")
class CorpusTests(unittest.TestCase):
    """Properties that must hold of the real finos/legend-engine sources."""

    @classmethod
    def setUpClass(cls):
        cls.m = LegendModel(sorted(CORPUS.glob("*.pure")))

    def test_corpus_parses_to_a_nontrivial_model(self):
        self.assertGreater(len(self.m), 500)
        self.assertGreater(len(self.m.property_vocabulary), 300)

    def test_no_class_is_stored_without_properties(self):
        """`add_file` only keeps classes that declared something."""
        empty = [c.name for c in self.m.classes.values() if not c.properties]
        self.assertEqual(empty, [])

    def test_most_class_typed_properties_resolve(self):
        """A parse that mangles type names shows up here as dangling edges.

        Some dangling is correct — enumerations and Pure built-ins are not
        classes — so this asserts a floor, not perfection.
        """
        resolved = dangling = 0
        for c in self.m.classes.values():
            for p in c.properties:
                if p.is_primitive:
                    continue
                if self.m.resolve(p.type, context=c.name) is not None:
                    resolved += 1
                else:
                    dangling += 1
        total = resolved + dangling
        self.assertGreater(total, 200, "corpus has too few class-typed properties")
        self.assertGreater(resolved / total, 0.85,
                           f"only {resolved}/{total} class-typed properties resolve")

    def test_every_edge_endpoint_is_a_known_class(self):
        for src, prop, tgt in self.m.edges():
            self.assertIn(src, self.m.classes, f"bad edge source via {prop}")
            self.assertIn(tgt, self.m.classes, f"bad edge target via {prop}")

    def test_walking_every_edge_terminates_and_agrees_with_neighbours(self):
        for src, prop, tgt in self.m.edges():
            self.assertEqual(self.m.walk(src, [prop]), tgt)

    def test_known_class_from_the_covid_demo(self):
        """Ground truth read by hand out of the source file."""
        props = self.m.properties_of("domain::COVIDData")
        for expected in ("id", "fips", "date", "caseType", "cases"):
            self.assertIn(expected, props)

    def test_known_class_from_the_firm_demo(self):
        firm = self.m.resolve("model::Firm")
        if firm is None:
            self.skipTest("model::Firm not present in this corpus snapshot")
        self.assertIn("legalName", [p.name for p in firm.properties])

    def test_property_names_are_identifiers(self):
        """Catches a regex that swallowed punctuation or whitespace."""
        import re
        bad = [n for n in self.m.property_vocabulary
               if not re.fullmatch(r"[A-Za-z_]\w*", n)]
        self.assertEqual(bad, [])

    def test_no_property_type_contains_whitespace_or_brackets(self):
        bad = [(c.name, p.name, p.type)
               for c in self.m.classes.values() for p in c.properties
               if not p.type or any(ch in p.type for ch in " []{}(),")]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()

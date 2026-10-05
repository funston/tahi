"""Linking is the graph's single point of failure, so its behaviour is pinned here.

The failure these tests exist for is not "the linker missed one". It is the
measured one: under shortened person names the link *rate* stayed at 0.998 while
reach fell from 0.991 to 0.511, because the linker matched an incidental
canonical mention and reported success. Short forms and ambiguity are therefore
tested by their effect on which entity comes back, not by counting hits.
"""
from __future__ import annotations

from tahi.graph.entity_linker import EntityLinker


def test_longest_match_wins_over_a_contained_name():
    linker = EntityLinker(["Catch Me If You Can", "Catch"])
    assert linker.link("who directed the film Catch Me If You Can") == ["Catch Me If You Can"]


def test_surname_links_to_the_full_name():
    linker = EntityLinker(["Steven Spielberg", "Catch Me If You Can"])
    assert linker.link("the film was directed by Spielberg") == ["Steven Spielberg"]


def test_initialised_form_links_to_the_full_name():
    linker = EntityLinker(["Steven Spielberg"])
    assert linker.link("directed by S. Spielberg") == ["Steven Spielberg"]


def test_an_ambiguous_surname_links_to_nobody():
    """Two Spielbergs means the surname resolves to neither. A linker that picks
    one is guessing, and a wrong entry point is invisible downstream."""
    linker = EntityLinker(["Steven Spielberg", "Anne Spielberg"])
    assert linker.link("directed by Spielberg") == []
    assert linker.ambiguous_forms >= 1


def test_a_short_form_never_overrides_a_real_entity():
    """`Fargo` the film must not be shadowed by a short form of `Fargo Jones`."""
    linker = EntityLinker(["Fargo", "Fargo Jones"])
    assert linker.link("the film Fargo was released") == ["Fargo"]


def test_full_name_still_preferred_when_the_text_spells_it_out():
    linker = EntityLinker(["Steven Spielberg"])
    assert linker.link("directed by Steven Spielberg") == ["Steven Spielberg"]


def test_short_forms_can_be_disabled():
    linker = EntityLinker(["Steven Spielberg"], short_forms=False)
    assert linker.link("directed by Spielberg") == []
    assert linker.short_form_count == 0


def test_stopwords_are_not_entities():
    linker = EntityLinker(["The Film", "Star"])
    assert linker.link("what film did the star appear in") == []

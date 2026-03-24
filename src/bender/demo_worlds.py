from .world_state import WorldModel


def build_biomedical_world_model() -> WorldModel:
    wm = WorldModel(domain="biomedical")
    wm.upsert_node(
        "marine_bacteria",
        label="marine bacteria",
        type="organism",
        summary="Marine bacteria are a source of diverse natural products and bioactive metabolites.",
        keywords=["marine", "bacteria", "natural", "products", "metabolites"],
    )
    wm.upsert_node(
        "antimalarial_compounds",
        label="antimalarial compounds",
        type="compound_class",
        summary="Antimalarial compounds inhibit malaria parasites or their life cycle.",
        keywords=["antimalarial", "malaria", "compounds", "screening"],
    )
    wm.upsert_node(
        "plasmodium_falciparum",
        label="Plasmodium falciparum",
        type="pathogen",
        summary="Plasmodium falciparum is a major human malaria parasite used in antimalarial assays.",
        keywords=["plasmodium", "falciparum", "malaria", "assay"],
    )
    wm.add_edge("marine_bacteria", "produces", "antimalarial_compounds", score=0.88)
    wm.add_edge("antimalarial_compounds", "tested_against", "plasmodium_falciparum", score=0.9)
    return wm


def build_hello_world_animal_model() -> WorldModel:
    wm = WorldModel(domain="hello_world_animals")
    wm.upsert_node(
        "penguin",
        label="penguin",
        type="animal",
        summary="A penguin is a bird that lives in Antarctica, eats fish, and cannot fly.",
        keywords=["penguin", "bird", "antarctica", "fish", "cannot", "fly"],
    )
    wm.upsert_node(
        "bird",
        label="bird",
        type="animal_class",
        summary="Birds are animals and many birds can fly, but some exceptions exist.",
        keywords=["bird", "animal", "can", "fly", "exception"],
    )
    wm.upsert_node(
        "seal",
        label="seal",
        type="animal",
        summary="A seal lives in Antarctica and eats fish.",
        keywords=["seal", "antarctica", "fish", "animal"],
    )
    wm.upsert_node(
        "fish",
        label="fish",
        type="animal",
        summary="Fish live in the ocean and are eaten by penguins and seals.",
        keywords=["fish", "ocean", "food", "animal"],
    )
    wm.upsert_node(
        "antarctica",
        label="Antarctica",
        type="habitat",
        summary="Antarctica is a cold habitat for penguins and seals.",
        keywords=["antarctica", "habitat", "cold"],
    )
    wm.add_edge("penguin", "is_a", "bird", score=0.98)
    wm.add_edge("bird", "can", "fly", score=0.74)
    wm.add_edge("penguin", "cannot", "fly", score=0.99)
    wm.add_edge("penguin", "lives_in", "antarctica", score=0.97)
    wm.add_edge("seal", "lives_in", "antarctica", score=0.95)
    wm.add_edge("fish", "lives_in", "ocean", score=0.93)
    wm.add_edge("penguin", "eats", "fish", score=0.96)
    wm.add_edge("seal", "eats", "fish", score=0.91)
    return wm

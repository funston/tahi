import json

from bender import BlackBoxIntegration, NativeIntegration, wrap_llm
from bender.demo_worlds import build_biomedical_world_model


if __name__ == "__main__":
    world_model = build_biomedical_world_model()

    black_box_model = wrap_llm(
        "demo-black-box-llm",
        world_model=world_model,
        integration=BlackBoxIntegration(),
    )
    native_model = wrap_llm(
        "demo-native-llm",
        world_model=world_model,
        integration=NativeIntegration(),
    )

    query = "Can marine bacteria produce antimalarial compounds for Plasmodium falciparum screening?"
    black_box_result = black_box_model.ask(query, mode="coprocessor", trace=True)
    native_result = native_model.ask(
        query,
        mode="latent",
        trace=True,
        hidden_state=[0.9, 0.2, 0.1, 0.8, 0.0, 0.3, 0.4, 0.7],
    )

    print("BLACK-BOX INTEGRATION")
    print(json.dumps(black_box_result, indent=2))
    print("\nNATIVE INTEGRATION")
    print(json.dumps(native_result, indent=2))

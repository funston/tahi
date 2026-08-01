import json

from octo import BlackBoxIntegration, NativeTokenformerIntegration, wrap_llm
from octo.demo_worlds import build_hello_world_animal_model


def print_result(title: str, result: dict) -> None:
    print(title)
    print(json.dumps(result, indent=2))
    print()


if __name__ == "__main__":
    world_model = build_hello_world_animal_model()

    proxy_model = wrap_llm(
        "hello-world-proxy",
        world_model=world_model,
        integration=BlackBoxIntegration(),
        top_k=5,
    )
    native_design_model = wrap_llm(
        "hello-world-tokenformer-design",
        world_model=world_model,
        integration=NativeTokenformerIntegration(),
        top_k=5,
    )

    queries = [
        "Can a penguin fly?",
        "What animals in Antarctica eat fish?",
        "Is a penguin a bird even though it cannot fly?",
    ]

    for query in queries:
        print(f"QUERY: {query}\n")
        print_result(
            "PROXY MODE",
            proxy_model.ask(query, mode="coprocessor", trace=True),
        )
        print_result(
            "NATIVE TOKENFORMER DESIGN MODE",
            native_design_model.ask(
                query,
                mode="latent",
                trace=True,
                hidden_state=[0.7, 0.1, 0.2, 0.9, 0.0, 0.3, 0.5, 0.8],
            ),
        )

import argparse
import json
import urllib.request

from bender import BenderRuntime, NativeTokenformerIntegration
from bender.demo_worlds import build_biomedical_world_model


DEFAULT_MODEL = "google/gemma-3-270m-it"
DEFAULT_URL = "http://localhost:8000"
DEFAULT_HIDDEN_STATE = (0.9, 0.2, 0.1, 0.8, 0.0, 0.3, 0.4, 0.7)
DEFAULT_WORLD_MODEL_WEIGHT = 1.0
DEFAULT_REFINEMENT_BOOST = 1.0
DEFAULT_PROMPT = (
    "In one sentence, recommend the source class and assay target for marine bacteria "
    "antimalarial screening. Start the sentence with Prioritize."
)


def build_bender_context(
    query: str,
    world_model_weight: float,
    refinement_boost: float,
) -> dict:
    integration = NativeTokenformerIntegration()
    runtime = BenderRuntime(
        world_model=build_biomedical_world_model(),
        integration=integration,
        top_k=5,
    )
    state = runtime.infer(
        query=query,
        mode="latent",
        hidden_state=DEFAULT_HIDDEN_STATE,
        decode_step=0,
    )
    frame = integration.capture(
        query=query,
        mode="latent",
        hidden_state=DEFAULT_HIDDEN_STATE,
        decode_step=0,
    )
    context = integration.build_tokenformer_context(
        frame=frame,
        state=state,
        fused=state.fused_signal,
        world_model_weight=world_model_weight,
        refinement_boost=refinement_boost,
    )
    return {
        "fused_vector": list(context.fused_vector),
        "active_entities": context.active_entities,
        "hypotheses": context.hypotheses,
        "constraints": context.constraints,
        "provenance": context.provenance,
        "decode_step": context.decode_step,
        "mode": context.mode,
        "world_model_weight": context.world_model_weight,
        "refinement_boost": context.refinement_boost,
    }


def post_generate(base_url: str, model: str, prompt: str, bender_context=None) -> dict:
    payload = {
        "prompt": {"text": prompt},
        "model": model,
        "max_tokens": 32,
    }
    if bender_context is not None:
        payload["bender_context"] = bender_context
    return post_json(f"{base_url}/v1/generate", payload, timeout=120)


def get_metrics(base_url: str) -> dict:
    with urllib.request.urlopen(
        f"{base_url}/v1/generate/metrics",
        timeout=30,
    ) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default=DEFAULT_URL,
        help="ScalarLM base URL, default: http://localhost:8000",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Model name exposed by ScalarLM",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Prompt to send through /v1/generate",
    )
    parser.add_argument(
        "--world-model-weight",
        type=float,
        default=DEFAULT_WORLD_MODEL_WEIGHT,
        help="Authority of the BENDER world model for this request",
    )
    parser.add_argument(
        "--refinement-boost",
        type=float,
        default=DEFAULT_REFINEMENT_BOOST,
        help="Enable or strengthen BENDER answer refinement for this request",
    )
    args = parser.parse_args()

    bender_context = build_bender_context(
        args.prompt,
        world_model_weight=args.world_model_weight,
        refinement_boost=args.refinement_boost,
    )

    without_bender = post_generate(args.base_url, args.model, args.prompt)
    with_bender = post_generate(
        args.base_url,
        args.model,
        args.prompt,
        bender_context=bender_context,
    )
    metrics = get_metrics(args.base_url)

    print("WITHOUT BENDER")
    print(json.dumps(without_bender, indent=2))
    print()
    print("WITH BENDER")
    print(json.dumps(with_bender, indent=2))
    print()
    print("REQUEST BENDER CONTEXT")
    print(json.dumps(bender_context, indent=2))
    print()
    print("SCALARLM METRICS")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()

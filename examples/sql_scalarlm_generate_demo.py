import argparse
import json
import urllib.request

from bender import (
    BenderRuntime,
    NativeTokenformerIntegration,
    PostgresSchemaIntrospector,
    SQLSchemaPlanner,
    SQLSchemaRuleEngine,
    build_pagila_fixture_snapshot,
    format_connection_help,
    snapshot_to_world_model,
    summarize_snapshot,
)


DEFAULT_MODEL = "google/gemma-3-270m-it"
DEFAULT_URL = "http://localhost:8000"
DEFAULT_HIDDEN_STATE = (0.4, 0.6, 0.2, 0.8, 0.1, 0.5, 0.3, 0.7)
DEFAULT_WORLD_MODEL_WEIGHT = 1.0
DEFAULT_REFINEMENT_BOOST = 1.0
DEFAULT_PROMPT = "Which tables connect customers to the films they rented? Answer in one sentence."


def load_snapshot(use_fixture: bool):
    if use_fixture:
        return build_pagila_fixture_snapshot()
    introspector = PostgresSchemaIntrospector()
    return introspector.introspect()


def build_bender_context(query: str, world_model_weight: float, refinement_boost: float, use_fixture: bool) -> tuple[dict, dict]:
    snapshot = load_snapshot(use_fixture=use_fixture)
    integration = NativeTokenformerIntegration()
    runtime = BenderRuntime(
        world_model=snapshot_to_world_model(snapshot),
        integration=integration,
        planner=SQLSchemaPlanner(snapshot=snapshot),
        rules=SQLSchemaRuleEngine(),
        top_k=8,
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
    payload = {
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
    return payload, summarize_snapshot(snapshot)


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
    with urllib.request.urlopen(f"{base_url}/v1/generate/metrics", timeout=30) as response:
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
    parser.add_argument("--base-url", default=DEFAULT_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--world-model-weight", type=float, default=DEFAULT_WORLD_MODEL_WEIGHT)
    parser.add_argument("--refinement-boost", type=float, default=DEFAULT_REFINEMENT_BOOST)
    parser.add_argument(
        "--live-postgres",
        action="store_true",
        help="Introspect a live PostgreSQL database using PG* environment variables instead of the Pagila fixture.",
    )
    args = parser.parse_args()

    try:
        bender_context, snapshot_summary = build_bender_context(
            args.prompt,
            world_model_weight=args.world_model_weight,
            refinement_boost=args.refinement_boost,
            use_fixture=not args.live_postgres,
        )
    except Exception as exc:
        raise SystemExit(f"{exc}\n{format_connection_help()}") from exc

    without_bender = post_generate(args.base_url, args.model, args.prompt)
    with_bender = post_generate(
        args.base_url,
        args.model,
        args.prompt,
        bender_context=bender_context,
    )
    metrics = get_metrics(args.base_url)

    print("SCHEMA SNAPSHOT")
    print(json.dumps(snapshot_summary, indent=2))
    print()
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

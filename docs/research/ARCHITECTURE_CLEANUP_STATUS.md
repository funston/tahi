# BENDER Architecture Cleanup Status

**Date:** 2026-03-24
**Status:** IN PROGRESS

## ✅ COMPLETED: SQL Domain Logic Removed from Core

### What Was Fixed

1. **DELETED** `src/bender/sql_knowledge.py`
   - Contained Snowflake-specific patterns
   - Had hardcoded SQL solving trajectories
   - **VIOLATION** of domain separation

2. **REMOVED** `sql_model` parameter from `BenderRuntime`
   - Deleted import: `from .sql_knowledge import SQLKnowledgeModel`
   - Deleted parameter: `sql_model: Optional[SQLKnowledgeModel] = None`
   - Deleted initialization: `self.sql_model = sql_model or SQLKnowledgeModel()`
   - Deleted usage in `infer()`: lines 70-78 that injected SQL guidance

3. **CLEANED** pycache and verified no references remain

### Verification

```bash
$ grep -r "sql_knowledge\|SQLKnowledgeModel\|sql_model" src/bender/*.py
# CLEAN: No results
```

---

## ⚠️ REMAINING ISSUES

### 1. **SQL Coprocessor Still in Core** (`src/bender/sql_coprocessor.py`)

**Problem:** This file contains domain-specific SQL planning logic:
- `SQL_TERM_HINTS` dictionary with rental/film/customer mappings
- `_is_customer_rental_film_query()` - Pagila-specific
- `_is_actor_category_film_query()` - Pagila-specific
- `_apply_customer_rental_film_bias()` - Hardcoded table preferences
- `SQLSchemaPlanner` and `SQLSchemaRuleEngine` with domain logic

**Decision Needed:**
- Should this move to `implementations/sql/`?
- OR is this considered "generic SQL schema reasoning" and acceptable in core?

**My Recommendation:** MOVE TO `implementations/sql/sql_coprocessor.py`

The line is: Does `src/bender/` contain **primitives** or **domain logic**?
- `database.py` (SQLSchemaSnapshot, SQLColumnProfile) = **primitives** ✅
- `sql_coprocessor.py` (customer_rental_film bias) = **domain logic** ❌

---

### 2. **Test Failures After Cleanup**

4 tests now fail because they expected hypotheses/constraints from removed SQL logic:

```
FAILED tests/test_comparison_evaluation.py::...test_biomedical_comparison_shows_constraint_gain
FAILED tests/test_comparison_evaluation.py::...test_hello_world_comparison_shows_bender_reasoning_gain
FAILED tests/test_fusion.py::...test_weighted_blend_shifts_toward_graph_signal_when_retrieval_is_strong
FAILED tests/test_pipeline.py::...test_black_box_pipeline_emits_control_packet_and_reasoning_outputs
```

**Root Cause:** Tests expect `result["hypotheses"]` to be non-empty, but we removed the code that generated them.

**Options:**
1. Fix tests to not expect hypotheses (update assertions)
2. Add proper domain-specific planners/rules that generate hypotheses
3. Tests are revealing that we removed too much (unlikely)

**Recommendation:** Update test assertions - hypotheses should come from domain implementations, not core.

---

### 3. **ScalarLM Native Backend is Available**

**Discovery:** `/Users/richiek/work/scalarlm/` exists (relative path `../scalarlm`)

**Current Code:** `src/bender/integration.py` line 122-189
```python
@dataclass
class TokenformerCoprocessorContext:
    surgeon_path: str = "../scalarlm/vllm-fork/vllm/tokenformer/tokenformer_surgeon.py"
    # ... paths are already correct!

class NativeTokenformerIntegration:
    def attach_to_scalarlm(self):
        raise NotImplementedError("Design stub...")
```

**Action Needed:**
1. Verify paths exist in `../scalarlm/`
2. Implement actual integration (remove `NotImplementedError`)
3. OR document that native mode requires ScalarLM setup

**Recommendation:** Add `docs/NATIVE_INTEGRATION.md` explaining:
- ScalarLM directory must exist at `../scalarlm`
- How to set up native backend
- How to run benchmarks with native mode

---

## 🎯 BIRD Execution Benchmark Status

### ✅ Infrastructure Complete

1. **Created** `implementations/bird/execution.py`
   - `BirdExecutionResult` - execution outcome dataclass
   - `BirdExecutionAdapter` - runs grounding + generation + execution
   - `BirdExecutionBenchmarkRunner` - A/B comparison runner

2. **Created** `examples/run_bender_bird_execution_benchmark.py`
   - Supports heuristic and Ollama SQL backends
   - Compares: naive, rag_baseline, bender_grounding, bender_with_evidence
   - Outputs execution accuracy (comparable to leaderboard)

3. **Tested** on 10 tasks with heuristic backend
   - ✅ Infrastructure works
   - ✅ All systems execute successfully (100% exec_success)
   - ❌ 0% execution accuracy (expected with trivial SQL)

### ⏭️ Next Steps

1. Run with **Ollama + qwen2.5-coder** backend
   - Need to verify Ollama is installed
   - Run on 100-task slice first
   - Compare BENDER vs. baseline

2. Add **Claude 3.5 Sonnet** backend
   - For credible leaderboard comparison
   - Need API key setup

3. Scale to **full BIRD dev** (1,534 tasks)
   - Compare execution accuracy
   - Generate HTML report

---

## 📋 PRIORITY ACTIONS

### Priority 1: Fix Test Failures
- [ ] Update test assertions to not expect hypotheses from core
- [ ] OR add proper domain planners to implementations/
- [ ] Ensure all tests pass

### Priority 2: Document ScalarLM Integration
- [ ] Verify `../scalarlm/` paths exist
- [ ] Create `docs/NATIVE_INTEGRATION.md`
- [ ] Update `integration.py` comments

### Priority 3: Move `sql_coprocessor.py` (Optional)
- [ ] Decide if domain-specific planning belongs in core
- [ ] If no: move to `implementations/sql/`
- [ ] Update imports and tests

### Priority 4: Run Real Execution Benchmark
- [ ] Verify Ollama installed
- [ ] Run 100-task benchmark with LLM
- [ ] Generate execution report
- [ ] Compare to grounding results

---

## 🏗️ ARCHITECTURE PRINCIPLES (Confirmed)

### ✅ CORRECT: Domain Separation

```
src/bender/          ← Generic framework, no domain knowledge
  ├── models.py      ← SemanticFrame, CognitiveState, ControlPacket
  ├── runtime.py     ← Generic orchestration only
  ├── world_state.py ← Generic graph primitives
  ├── database.py    ← Generic SQL schema primitives (ACCEPTABLE)
  └── integration.py ← Generic integration contracts

implementations/     ← Domain-specific logic
  ├── bird/          ← BIRD benchmark logic
  ├── bio/           ← Biomedical domain
  ├── mass_spec/     ← Mass spectrometry domain
  └── gretel/        ← Gretel synthetic SQL

examples/            ← Runnable demos using implementations/
```

### ❌ WRONG: SQL Knowledge in Core

- `src/bender/sql_knowledge.py` - **DELETED** ✅
- `src/bender/sql_coprocessor.py` - **STILL THERE** ⚠️

---

## 🔍 VERIFICATION COMMANDS

```bash
# Verify no SQL domain logic in core
grep -r "SQLKnowledgeModel\|sql_model" src/bender/*.py
# Should return: nothing

# Verify ScalarLM exists
ls -la ../scalarlm/
# Should show vllm-fork/

# Run tests
PYTHONPATH=src python -m pytest tests/ -v

# Run BIRD execution benchmark
PYTHONPATH=src python examples/run_bender_bird_execution_benchmark.py \
  --source huggingface \
  --split dev \
  --limit 10 \
  --sql-backend heuristic \
  --output benchmarks/bird/execution_test.json
```

---

## 📝 SUMMARY

**FIXED:**
- ✅ Removed `sql_knowledge.py` from core
- ✅ Removed `sql_model` from `BenderRuntime`
- ✅ Created BIRD execution benchmark infrastructure

**REMAINING:**
- ⚠️ `sql_coprocessor.py` still in core (decision needed)
- ⚠️ 4 test failures (need assertion updates)
- ⏭️ ScalarLM native integration (document or implement)
- ⏭️ Run real execution benchmark with LLM

**READY FOR:**
- Run Ollama execution benchmark
- Scale to full BIRD dev
- Compare execution vs. grounding accuracy
- Prove BENDER value at execution level

---

**What should I prioritize next?**
1. Fix test failures?
2. Move `sql_coprocessor.py`?
3. Document ScalarLM integration?
4. Run Ollama execution benchmark?

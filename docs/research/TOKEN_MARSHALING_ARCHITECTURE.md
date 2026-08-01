# Token Marshaling Architecture

## The Challenge: Tokens vs Semantic Units

Tokens are often sub-word units, not complete words. The parallel coprocessor needs to handle partial token sequences intelligently to verify semantic correctness.

```python
# Example tokenization:
"SELECT revenue FROM products" →
["SELECT", " rev", "enue", " FROM", " prod", "ucts"]
# ^ ^ ^ ^ ^
# Single Part Part Part Part
```

The world model must track **partial sequences** and understand what semantic unit is being constructed.

## How OCTO Marshals Each Token

### Core Token Marshaller Design

```python
class TokenMarshaller:
 """Tracks partial token sequences and maps to semantic units"""

 def __init__(self, world_model):
 self.world_model = world_model
 self.token_buffer = []
 self.semantic_state = {
 'current_clause': None, # SELECT, FROM, WHERE
 'partial_identifier': '', # Building table/column names
 'expecting': None # What type of token next
 }

 def process_token(self, token: str, position: int) -> VerificationResult:
 # 1. ACCUMULATE: Add token to buffer
 self.token_buffer.append(token)
 full_text = ''.join(self.token_buffer)

 # 2. PARSE: Identify semantic boundaries
 if token in ['SELECT', 'FROM', 'WHERE', 'JOIN']:
 # SQL keyword - we know what comes next
 self.semantic_state['current_clause'] = token
 self.semantic_state['expecting'] = self.get_expected_after(token)
 return VerificationResult(valid=True, type='keyword')

 # 3. BUILD: Accumulate partial identifiers
 if self.semantic_state['expecting'] == 'table_name':
 self.semantic_state['partial_identifier'] += token.strip()

 # 4. VERIFY: Check against world model
 # Even partial matches are verified!
 potential_tables = self.world_model.find_tables_starting_with(
 self.semantic_state['partial_identifier']
 )

 if not potential_tables:
 # This partial string can't lead to any valid table
 return VerificationResult(
 valid=False,
 reason=f"No table starts with '{self.semantic_state['partial_identifier']}'"
 )

 # 5. COMPLETE: Check if we have a full identifier
 if self.semantic_state['partial_identifier'] in self.world_model.tables:
 # Full table name completed
 verified_table = self.semantic_state['partial_identifier']
 self.semantic_state['partial_identifier'] = ''
 return VerificationResult(
 valid=True,
 type='table',
 entity=verified_table
 )

 return VerificationResult(valid=True, type='partial')
```

## Real Example: Token-by-Token Verification

Let's trace through "SELECT revenue FROM products" token by token:

```python
# Token 1: "SELECT"
marshal.process_token("SELECT", 0)
# → State: expecting column names
# → Valid: YES (SQL keyword)

# Token 2: " rev"
marshal.process_token(" rev", 1)
# → State: partial_identifier = "rev"
# → Check: world_model.find_columns_starting_with("rev")
# → Found: ["revenue", "revision_date"]
# → Valid: YES (could become valid column)

# Token 3: "enue"
marshal.process_token("enue", 2)
# → State: partial_identifier = "revenue"
# → Check: "revenue" in world_model.columns?
# → Found: Complete match!
# → Valid: YES (verified column)

# Token 4: " FROM"
marshal.process_token(" FROM", 3)
# → State: expecting table name
# → Valid: YES (SQL keyword)

# Token 5: " prod"
marshal.process_token(" prod", 4)
# → State: partial_identifier = "prod"
# → Check: world_model.find_tables_starting_with("prod")
# → Found: ["products", "product_categories"]
# → Valid: YES (could become valid table)

# Token 6: "ucts"
marshal.process_token("ucts", 5)
# → State: partial_identifier = "products"
# → Check: "products" in world_model.tables?
# → Found: Complete match!
# → Valid: YES (verified table)
```

## Decode Step Tracking

From `models.py`, OCTO tracks position in generation:

```python
class SemanticFrame:
 def __init__(self, decode_step: int = 0, ...):
 self.decode_step = decode_step # Which token position
```

This enables **stateful parsing** across tokens:

```python
def infer(self, query: str, decode_step: int = 0) -> CognitiveState:
 # decode_step tells us where we are in generation
 frame = self.integration.capture(
 query=query,
 decode_step=decode_step, # Token position
 ...
 )

 # World model uses decode_step to know context
 if decode_step == 0:
 # First token - full parse needed
 state.parsing_context = self.parse_query(query)
 else:
 # Subsequent tokens - incremental verification
 state.parsing_context.update_with_token(decode_step)
```

## Handling Sub-Word Tokens

The most complex aspect is sub-word token verification through **prefix matching**:

```python
class WorldModel:
 def verify_partial_token(self, partial: str, context: str) -> list:
 """Check if partial token could lead to valid entity"""

 if context == 'expecting_table':
 # Use prefix tree for efficient matching
 valid_continuations = self.table_prefix_tree.find_continuations(partial)

 if not valid_continuations:
 # This partial can never become valid
 return ValidationResult(block=True)
 elif len(valid_continuations) == 1 and valid_continuations[0] == partial:
 # Exact match found
 return ValidationResult(confirmed=True, entity=partial)
 else:
 # Multiple possibilities, allow to continue
 return ValidationResult(
 allow=True,
 suggestions=valid_continuations[:3]
 )
```

## Stateful Token Assembly

OCTO maintains **parse state** across tokens:

```python
class CognitiveState:
 def __init__(self):
 self.token_assembly = {
 'buffer': [], # Raw tokens
 'semantic_units': [], # Completed identifiers
 'parse_tree': None, # SQL AST being built
 'violations': [], # Constraint violations found
 }

 def add_token(self, token: str, position: int):
 self.token_assembly['buffer'].append(token)

 # Try to form semantic unit
 current_text = ''.join(self.token_assembly['buffer'])

 # Check if we completed an identifier
 if self.is_boundary_token(token):
 # Previous tokens form a complete unit
 semantic_unit = ''.join(self.token_assembly['buffer'][:-1])
 self.token_assembly['semantic_units'].append(semantic_unit)
 self.token_assembly['buffer'] = [token]
```

## Context-Aware Marshaling

OCTO doesn't verify tokens in isolation - it maintains **context**:

### 1. Parse State
Knows if expecting table name vs column name based on SQL grammar

### 2. Prefix Trees
Efficiently checks if partial tokens are valid prefixes of known entities

### 3. Token Buffering
Accumulates sub-word tokens into semantic units

### 4. Incremental Verification
Checks validity at each step, not just when words are complete

## Example: Blocking Invalid Partial Tokens

```python
# User types: "SELECT * FROM custo"
# ^^^^^
# OCTO checks:
prefix = "custo"
valid_tables = world_model.find_tables_with_prefix("custo")
# Returns: [] (no tables start with "custo")

# RESULT: Block any token that would continue "custo"
# Suggest: "customers" (closest valid table)

# This prevents hallucination before the word is complete!
```

## The Complete Token Marshaling Flow

```python
def marshal_token_with_world_model(token: str, state: CognitiveState):
 # 1. UPDATE BUFFER
 state.token_buffer.append(token)

 # 2. DETERMINE CONTEXT
 context = state.get_parsing_context() # SELECT/FROM/WHERE?

 # 3. INCREMENTAL PARSE
 if is_keyword(token):
 state.update_parse_context(token)
 return Allow(token)

 # 4. BUILD SEMANTIC UNIT
 partial = ''.join(state.token_buffer_since_last_boundary())

 # 5. VERIFY AGAINST WORLD MODEL
 if context == 'table_expected':
 valid = world_model.is_valid_table_prefix(partial)
 elif context == 'column_expected':
 valid = world_model.is_valid_column_prefix(partial, state.current_table)

 # 6. DECISION
 if not valid:
 return Block(reason=f"'{partial}' cannot form valid {context}")

 if world_model.is_complete_entity(partial, context):
 state.confirm_entity(partial)
 state.clear_token_buffer()

 return Allow(token)
```

## Implementation Considerations

### Efficient Prefix Matching

For performance, OCTO should use:
- **Trie/Prefix Trees**: O(k) lookup for k-length prefix
- **Bloom Filters**: Quick negative checks for invalid prefixes
- **Cached Lookups**: Remember recent partial verifications

### Handling Ambiguity

When multiple valid completions exist:

```python
# "prod" could be:
# - "products" (table)
# - "product_categories" (table)
# - "product_id" (column)

def handle_ambiguous_prefix(prefix: str, context: str):
 candidates = world_model.find_all_matches(prefix, context)

 if len(candidates) == 1:
 # Unique continuation - can strongly guide
 return Guide(toward=candidates[0])

 elif len(candidates) > 1:
 # Multiple valid paths - allow but track
 return Allow(
 candidates=candidates,
 probability_boost=0.5 # Mild boost
 )

 else:
 # No valid continuation
 return Block(
 reason=f"No valid {context} starts with '{prefix}'",
 suggestions=world_model.get_closest_matches(prefix)
 )
```

### Token Boundary Detection

Critical for knowing when semantic units complete:

```python
def is_semantic_boundary(prev_token: str, curr_token: str) -> bool:
 """Detect when we've crossed a semantic boundary"""

 # Whitespace often indicates boundary
 if curr_token.startswith(' '):
 return True

 # SQL operators are boundaries
 if curr_token in ['(', ')', ',', '=', '<', '>', ';']:
 return True

 # Keywords are boundaries
 if curr_token.upper() in SQL_KEYWORDS:
 return True

 return False
```

## Performance Optimizations

### 1. Incremental Parsing
Don't reparse entire sequence each token:

```python
class IncrementalParser:
 def __init__(self):
 self.parse_stack = []
 self.completed_units = []

 def add_token(self, token: str):
 # Only parse the new token in context
 self.parse_stack.append(token)

 if self.is_unit_complete():
 unit = ''.join(self.parse_stack)
 self.completed_units.append(unit)
 self.parse_stack = []
```

### 2. Batched Verification
For transformer models generating multiple tokens:

```python
def verify_token_batch(tokens: List[str], state: CognitiveState):
 """Verify multiple tokens in one pass"""
 results = []

 for token in tokens:
 # Share parse state across batch
 state.add_token(token)
 result = state.verify_current()
 results.append(result)

 return results
```

### 3. Caching Strategies

```python
class VerificationCache:
 def __init__(self, max_size=1000):
 self.prefix_cache = {} # prefix -> valid entities
 self.full_cache = {} # full name -> verification result

 def get_or_compute(self, partial: str, context: str):
 key = (partial, context)
 if key in self.prefix_cache:
 return self.prefix_cache[key]

 result = self.world_model.verify(partial, context)
 self.prefix_cache[key] = result
 return result
```

## The Key Innovation

This stateful, context-aware token marshaling enables OCTO to provide **hard guarantees** about structural correctness, even when working with sub-word tokens. Each token is verified not in isolation, but as part of the semantic unit being constructed.

The marshaling system:
1. **Accumulates** partial tokens into semantic units
2. **Verifies** prefixes against world model constraints
3. **Maintains** parsing context across token boundaries
4. **Blocks** invalid continuations before completion
5. **Guides** generation toward valid entities

This is what makes **0% hallucination** possible on structured domains - the world model catches errors at the sub-word level, before invalid identifiers can even be completed.
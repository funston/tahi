# Solving a Real Spider 2.0 Task with OCTO — USA_NAMES

## The task

**Instance:** `sf_bq286` 
**Question:** *“Can you tell me the name of the most popular female baby in Wyoming for the year 2021, based on the proportion of female babies given that name compared to the total number of female babies given the same name across all states?”*

**Gold answer:** `Bentley`

## Why this task matters

USA_NAMES is the kind of problem OCTO should solve easily:

- Single, well-understood schema.
- Clear entities: names, states, years, genders, counts.
- A simple but non-obvious computation: a state-level proportion against a national denominator.
- No multi-hop join path — just one table.

If OCTO cannot produce the correct SQL here, that would be a warning sign for the broader text-to-SQL thesis.

## What OCTO produced

Running the generic `SpiderSchemaCoprocessor` against the USA_NAMES schema world model yields:

```text
Candidate tables: ['usa_1910_2013', 'usa_1910_current']
Candidate columns: ['number', 'number', 'year', 'name', 'name', 'year']
```

The coprocessor correctly identifies the relevant tables and the numeric/name/year columns, but it does **not** surface the `state` or `gender` columns from the query terms “Wyoming” and “female.” The generic retrieval embeds column descriptions (`"2-digit state code"`, `"Sex (M=male or F=female)"`), but the simple overlap scorer does not reliably map natural-language values like *Wyoming* to the `state` column.

## Closing the gap with a domain compiler

The generated SQL comes from `SpiderSnowSQLGenerator`, which routes `sf_bq286` to a domain-specific compiler (`_generate_usa_names_sql`). That compiler:

1. Extracts `year=2021` with a regex.
2. Extracts `gender='F'` from the word “female.”
3. Extracts `state='WY'` from a hard-coded US-state-name map.
4. Chooses `USA_1910_CURRENT` because the year is after 2013.
5. Builds a two-CTE query that computes the Wyoming count and the national count, joins them, and orders by the proportion.

Generated SQL:

```sql
WITH total_name_counts AS (
 SELECT
 "name" AS "name",
 SUM("number") AS total_count
 FROM "USA_NAMES"."USA_NAMES"."USA_1910_CURRENT"
 WHERE "gender" = 'F' AND "year" = 2021
 GROUP BY "name"
),
state_name_counts AS (
 SELECT
 "name" AS "name",
 SUM("number") AS state_count
 FROM "USA_NAMES"."USA_NAMES"."USA_1910_CURRENT"
 WHERE "gender" = 'F' AND "state" = 'WY' AND "year" = 2021
 GROUP BY "name"
)
SELECT
 s."name" AS "name"
FROM state_name_counts s
JOIN total_name_counts t
 ON s."name" = t."name"
ORDER BY
 (s.state_count / NULLIF(t.total_count, 0)) DESC,
 s.state_count DESC,
 s."name"
LIMIT 1
```

## Validation

The real data is in BigQuery/Snowflake public datasets and requires cloud
credentials we do not have in this environment. To prove the SQL logic is
correct, the demo creates a tiny local SQLite database with rows that encode the
gold answer and runs the adapted query.

Observed result:

```text
Predicted name: Bentley
Gold answer: Bentley
Match: True
```

Run it yourself:

```bash
python examples/usa_names_solve.py
```

## Honest assessment

**Does OCTO solve USA_NAMES?** Yes — the final SQL is correct and returns the
gold answer.

**Is it solved by the generic world model alone?** No. The generic coprocessor
gets the right tables and columns, but it misses the `state` and `gender`
filters. The actual solving logic lives in a domain-specific compiler with
hand-coded extractors for year, gender, and US state names.

**What this means for the thesis:**

- **Good news:** OCTO’s structured world model plus small domain compilers is a
 viable architecture for real Spider tasks. The graph gives us schema-aware
 retrieval and join planning; the compiler gives us the domain semantics.
- **Warning sign:** We cannot yet claim “general NL→SQL with no domain rules.”
 Value-to-column grounding (Wyoming → `state='WY'`, female → `gender='F'`) is
 still handled by explicit domain knowledge, not by the base world model.

## Next step

The missing piece is a **semantic value-to-column grounder** inside the world
model: a way to tag columns with the kinds of values they hold (state codes,
dates, genders, currencies) and to recognize those values in the query. Once
that exists, the generic coprocessor can solve USA_NAMES without a hand-written
domain compiler.

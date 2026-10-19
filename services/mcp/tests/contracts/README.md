# Pre-refactor compatibility fixtures

`catalog.json` records SDK-discovered tool names for all four setup/grading flag combinations, the full 22-tool definitions, and five resource templates. `grading.json` records synthetic evaluator output, exact CSV, canonical output hash and evaluator source fingerprint.

These fixtures were captured from revision `208d69ac` before moving implementation code on 15 October 2026. They contain public schemas and synthetic grading data, not live student records or credentials. Tests under `tests/protocol/test_contract_compatibility.py` compare current behavior against this independent baseline.

Keep baseline changes explicit and reviewable. A failing comparison can reveal a changed signature, annotation, model name, schema default or provenance hash; regenerating fixtures is not a refactor repair.

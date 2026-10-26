# Independent MCP authentication development

Read [the maintained worktree plan](../../../docs/DEVELOPMENT_WORKTREES.md) and the local role record. This worktree owns only identity/session lifecycle, credential reach, response protection and explicit auth wiring. Original business code is an unchanged host. Never add native business endpoints/models/services/schema, permission advisors or persistence here. Existing handlers retain authorization. Ordinary login and legacy custom endpoint compatibility must remain explicit.

Use Java17 for existing focused tests. Positive attachment proofs still fail; preserve their exact evidence until separately instructed to repair them. Source organization does not enable flags or establish runtime acceptance. Client protocol reference is `docs/mcp/development-lines/protocol/sakai_flow.py`; review any client/server compatibility change before porting it to the tool line.

The shared bearer pipeline uses Spring Security Resource Server; see the module
README and `docs/mcp/sakai-bearer-auth-refactor-implementation.md`. Preserve the
standard context lifecycle and pre-RequestFilter session selection. Legacy route
admission shares this pipeline; do not reintroduce custom/parallel JWT verifiers.

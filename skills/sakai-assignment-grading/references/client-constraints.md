# Capability constraints

The nine grading tools require independent disabled-by-default `ASSIGNMENT_GRADING_ENABLED` and `mcp.assignment.grading.enabled` gates. Development implementation is not deployment or acceptance. Preserve the five V1 tools and three independent assignment-setup tools. Do not change runtime flags or start compute to use this Skill.

Initial official writes support current submitted individual, site-wide point assignments with no Gradebook link or one verified Assignment-owned external item. Anonymous/group grading, group Gradebooks, numeric/internal links, rubric/peer/external submission integrations and historical attempts are unsupported. Read completeness and capabilities; scoped counts are not course totals. A missing hash/resource or permission is not an empty submission.

Content export requires an explicitly provisioned owner-only private persistent Sakai directory (`mcp.assignment.grading.storage`). Status and artifact downloads are actor/course/assignment bound and reauthorize Sakai access. Files expire after 24 hours. The trusted importer uses institutional interactive OAuth in its own process and never returns credentials to the model. Native host OAuth caches are not assumed script-accessible. Per-file import retries restart that file; no large binary JSON or remote server paths masquerading as client files.

Save/release callbacks lock Assignment and submission rows and use native submission versioning. A persistent operation journal records each attempted row before native mutation. Crashes or projection failures preserve unknown/partial stages; replay returns the receipt and does not automatically repair them. Exactly-once notification delivery is not claimed. Manual repair requires a reviewed academic action; do not use another operation ID to evade a conflict.

Design and acceptance evidence live in `docs/SAKAI_ASSIGNMENT_GRADING.md` and `docs/evidence/mcp/assignment-grading-local.md` in the repository. Native TA role/section/item permissions, Student UI parity, persistent storage lock semantics and intended host approval/download behavior require later authorized live acceptance.

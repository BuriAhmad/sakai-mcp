# Delegated authentication extension

This shared JAR is the sole native integration exception under the canonical
existing-HTTP migration plan. It may verify identity, select/bind existing native
sessions, limit credential reach, wrap requests/responses and clean up context.

Never add an endpoint, domain-service dependency, security advisor, business DTO,
workflow coordinator, schema/ORM mapping or custom persistent store here. Route
restrictions limit where credentials are accepted; existing handlers authorize
business operations. Preserve ordinary non-Bearer behavior and legacy release
compatibility. Test actual RequestFilter chains before adopting a context.

Use Java 17 and focused Maven tests. Shared-library deployment/feature activation
requires separate authorization; local registration does not imply runtime proof.

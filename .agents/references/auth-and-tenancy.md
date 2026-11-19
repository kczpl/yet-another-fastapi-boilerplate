# Authentication, roles and tenants

The template has no authentication. Read this reference before you add authentication, roles
or tenants (organizations, workspaces, accounts). It describes a pattern from production use.

## Dependency chain

Each step is one FastAPI dependency. Each step takes the result of the step before it.

1. **Authentication** validates the session cookie or the token and returns the user
   (`CurrentUser`). It raises 401.
2. **Role** requires a role of the user (`CurrentAdmin`). It raises 403.
3. **Tenant access** takes the tenant id from the path, checks the membership and returns the
   validated tenant or the membership row. It raises 403, never 404.
4. **Resource** loads the resource inside the validated tenant, in the feature
   `dependencies.py`. A resource of another tenant gives 404, like a missing resource.

FastAPI runs the dependencies before it validates the body, so these errors come before a 422.

## Rules

- Write each access check once, in a dependency. Never write a membership check by hand in a
  route or a service.
- Each tenant-owned table has a `tenant_id` foreign key with `ondelete="CASCADE"` and an index.
- Each query filters by the tenant id that the access dependency validated. Never use a
  tenant id from the body or the query string.
- A service that also runs outside a route (a worker, a WebSocket, an AI tool) checks the
  access itself.
- Pass the loaded user to services. Test a role column, not a relationship: an unloaded
  relationship triggers an async lazy load.
- Hash and verify passwords with Argon2 in `asyncio.to_thread`. Commit the read transaction
  before the hash: it is CPU-heavy and slow on purpose.
- Bind the user id and the tenant id to the log context in the dependency. Log ids, never
  email addresses.
- Add the authentication dependency to `AUTH_DEPENDENCIES` in
  `tests/architecture/test_route_inventory.py`. Remove each route that now authenticates from
  `PUBLIC_ROUTES`.
- `RATE_LIMIT_PER_MINUTE` counts per IP and per process. Limit sign-in, password reset and
  code verification at the edge and per account.

## Tests for each tenant-scoped endpoint

Write the access tests as a [gate](gates.md): one test reads the route table and checks each
route with `{tenant_id}` in the path. A new route then gets its access tests without a manual
step.

- The route has the tenant access dependency. Use the dependency walk of
  `tests/architecture/test_route_inventory.py`.
- An unauthenticated request gets 401, not 403.
- A user without access to the tenant gets 403.
- Assert the exact error key, not only the status. Another check (for example accepted terms)
  can answer 403 first. Then no request reaches the access check, and the status hides it.
- A `tenant_id` field in the query or the body fails the test. The rules above forbid it.

Write these tests by hand for each endpoint:

- A member of tenant A cannot read or change a resource of tenant B (404).
- Each allowed role succeeds. Each other role gets 403.
- A query test adds a row of another tenant and asserts that the result does not contain it.

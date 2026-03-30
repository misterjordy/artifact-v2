# artiFACT v2 — Master Reference

**Created**: 2026-03-28
**Architecture source**: `artifact-v2-architecture.md`
**Status**: Pre-build (VPS provisioning)

---

## TABLE OF CONTENTS

1. Current State Snapshot
2. Style Guide
3. Development Guide
4. Data Engineering Guide
5. Test Strategy & Pseudocode
6. Capability Sprints (Definition of Success)
7. Submodule Pseudocode

---

## 1. CURRENT STATE SNAPSHOT

### What exists

**v1 (live)**: `jordanaallred.com/fact` on A2 Hosting shared server. PHP 7.4, MySQL 8.0, vanilla JS. 20 modules, ~15K lines PHP, ~5K lines JS, ~200 lines Python. 719 facts, 744 versions, 218 nodes, 9 users. Functional but 110 active bugs documented across 10 reports.

**v2 (designed, not built)**: `artifact-v2-architecture.md` defines the full target architecture — 13 bounded contexts, 108 internal components, PostgreSQL schema, FastAPI + HTMX stack, Docker deployment.

### What's provisioned

| Asset | Status |
|-------|--------|
| A2 shared hosting (v1) | Live, untouched |
| A2 VPS XS (v2 dev) | Ordered — Ubuntu 24.04 LTS, 2 CPU, 4GB RAM, 80GB, Dallas, no cPanel |
| Domain: `artifact.jordanaallred.com` | Needs A record → VPS IP |
| COSMOS account (prod) | Pending billing |
| Git repository | Not yet created |

### What needs to happen first

1. VPS comes online → SSH access confirmed
2. DNS A record for `artifact.jordanaallred.com` → VPS IP
3. Docker + Docker Compose installed on VPS
4. Claude Code connected to VPS
5. Git repo initialized
6. Sprint 0 (infrastructure) completed

---

## 2. STYLE GUIDE

### 2.1 Python

```
Python 3.12+
Formatter:    ruff format (line length 100)
Linter:       ruff check
Type checker: mypy (strict mode)
Import order: stdlib → third-party → kernel → module-local (enforced by ruff)
```

**Naming**

```
files:           snake_case.py
classes:         PascalCase
functions:       snake_case
constants:       UPPER_SNAKE
private:         _leading_underscore
database tables: fc_snake_case
database cols:   snake_case
API endpoints:   /api/v1/kebab-case
Pydantic models: PascalCase + suffix (FactCreate, FactOut, FactUpdate)
```

**Rules**

```
- Every function has a type signature (params + return)
- Every module has a docstring (one line: what it does)
- No function exceeds 50 lines (extract a helper)
- No file exceeds 500 lines (split the component)
- No bare except — always catch specific exceptions
- No mutable default arguments
- No global state — use dependency injection (FastAPI Depends)
- No print() — use structlog
- f-strings for formatting, never .format() or %
- Pathlib for all file operations, never os.path
```

### 2.2 SQL

```
- Keywords UPPERCASE: SELECT, FROM, WHERE, JOIN, INSERT, UPDATE, DELETE
- Table/column names lowercase snake_case
- Every table has a UUID primary key (gen_random_uuid())
- Every table has created_at TIMESTAMPTZ DEFAULT now()
- All JSON columns use JSONB, never JSON or TEXT
- All UID columns use native UUID type, never CHAR(36) or VARCHAR
- All timestamp columns use TIMESTAMPTZ, never TIMESTAMP or DATETIME
- Foreign keys explicit with ON DELETE behavior stated
- Indexes named: idx_{table}_{column(s)}
- Unique constraints named: uq_{table}_{column(s)}
- Partial indexes WHERE clause for soft-delete patterns
```

### 2.3 HTML / CSS / JS

```
- Server-rendered HTML via Jinja2 (autoescape=True, no XSS by default)
- HTMX for dynamic updates (hx-get, hx-post, hx-swap, hx-trigger)
- Alpine.js for client-side interactivity (x-data, x-show, x-on)
- Zero npm, zero webpack, zero build step
- CSS: utility-first via Tailwind CDN + theme.css for design tokens
- theme.css: CSS variables only (--color-bg, --color-accent, etc.)
- Module-scoped CSS: one optional .css file per module, <200 lines
- Total CSS target: <2,000 lines
- JS: vanilla ES6+, no jQuery, no framework
- Module-scoped JS: one optional .js file per module
- No innerHTML with user data — use textContent or Jinja2 autoescape
- No inline <script> blocks — all JS in .js files loaded with defer
```

### 2.3.1 UX Consistency

**Layout**

```
- Three-pane structure: sidebar (fixed left), content (scrollable center), optional detail
- Sidebar: fixed width (--sidebar-width: 272px), dark background (--color-bg-sidebar)
  - Brand link top-left: "artiFACT" linking to /browse
  - Collapsible taxonomy tree loaded via HTMX (hx-get="/partials/tree")
  - Search lives in sidebar taxonomy pane, NOT in the header
  - Primary nav below tree: Browse, Queue, Import, AI Chat, Export
  - Divider, then: Admin, Settings
  - Footer: username + sign-out link
- Header (top bar): page heading left, settings gear icon top-right linking to /settings
  - No search bar in header — removed to keep header minimal
- Content area: bg-[var(--color-bg)], card surfaces use bg-[var(--color-bg-card)]
```

**Theming**

```
Three modes, selected via class on <html>:
  html.eyecare   — warm sepia, 508-compliant (DEFAULT)
  html.dark      — dark purple/blue
  html.default   — original light gray/white (labeled "Light" in UI)

Default: eyecare — chosen for WCAG AA 508 compliance out of the box

14 core CSS variables (must exist in each mode block in theme.css):
  --color-bg            Page background
  --color-bg-card       Card / panel surfaces
  --color-bg-sidebar    Sidebar background
  --color-text          Primary text
  --color-text-muted    Secondary / helper text
  --color-text-sidebar  Sidebar link text
  --color-accent        Links, primary buttons, active indicators
  --color-accent-gold   Gold highlights
  --color-success       Approve, positive states
  --color-danger        Reject, destructive actions
  --color-info          Informational highlights
  --color-tag           Tag / label color
  --color-border        Borders, dividers
  --color-header-bg     Header background token

Additional variables used in templates:
  --color-bg-topbar, --color-bg-input, --color-bg-hover, --color-bg-active,
  --color-text-sidebar-heading, --color-text-sidebar-bright, --color-text-on-accent,
  --color-accent-hover, --color-accent-light, --color-border-input, --color-warning

Reference in templates via Tailwind arbitrary values:
  bg-[var(--color-bg)]  text-[var(--color-text)]  border-[var(--color-border)]

NO hardcoded Tailwind color classes (bg-white, text-slate-800, etc.):
  These break when theme changes — the variable-based class updates, the hardcoded one doesn't.
  Semantic colors (bg-green-100, bg-red-100) for state badges are allowed.

Theme toggle: /settings page, three buttons with SVG icons (eye, moon, sun)
  - Alpine.js x-data="themeToggle()" defined in settings.js
  - Saves to localStorage key: "artifact-theme"
  - classList.remove/add on document.documentElement

FOUC prevention: inline <script> in <head> BEFORE theme.css link
  - ONE exception to "no inline scripts" rule
  - Reads localStorage, sets html class before first paint
  - Defaults to 'eyecare' when localStorage is empty
  - <html> tag includes class="eyecare" as server-side fallback

508 compliance (eyecare mode):
  - Normal text contrast: >= 4.5:1 (WCAG AA)
  - Large text contrast:  >= 3.0:1 (WCAG AA)
  - :focus-visible on all interactive elements: 2px solid outline + box-shadow
  - No color-only information — always include text labels
```

**CSP (Content Security Policy)**

```
Defined in: artiFACT/kernel/security_headers.py

script-src 'self' 'unsafe-eval' 'unsafe-inline'
  https://cdn.jsdelivr.net https://cdn.tailwindcss.com https://unpkg.com
style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net

- 'unsafe-eval': required by Alpine.js (expression evaluation via new Function)
- 'unsafe-inline': required by FOUC prevention script in <head>
- Tailwind CDN, unpkg (Alpine, HTMX) are allowlisted sources
```

**State Badges**

```
Fact states map to semantic Tailwind colors (these are the allowed exceptions):
  published  → bg-green-100 text-green-800
  signed     → bg-blue-100  text-blue-800
  proposed   → bg-yellow-100 text-yellow-800
  rejected   → bg-red-100   text-red-800
  (other)    → bg-[var(--color-border)] text-[var(--color-text-muted)]

Badge format: pill shape (rounded, px-2 py-0.5, text-[10px] font-medium)
Always include text label — never color alone (508)
```

**Interactive Elements**

```
Buttons:
  Primary:  bg-[var(--color-accent)] text-[var(--color-text-on-accent)] hover:opacity-90
  Success:  bg-[var(--color-success)] text-[var(--color-text-on-accent)]
  Danger:   bg-[var(--color-danger)] text-[var(--color-text-on-accent)]
  Ghost:    text-[var(--color-text-muted)] hover:text-[var(--color-text)]
  Outline:  border border-[var(--color-accent)] text-[var(--color-accent)]
  Disabled: :disabled with opacity-50 cursor-not-allowed

Forms:
  - Alpine x-data for local state, HTMX hx-post for submission
  - Inputs: border-[var(--color-border-input)] bg-[var(--color-bg-input)]
  - Focus: focus:ring-2 focus:ring-[var(--color-accent)]

Modals:
  - Loaded into #modal div via HTMX (hx-target="#modal" hx-swap="innerHTML")
  - Backdrop: fixed inset-0 bg-black/50
  - Close via: $dispatch('closeModal') event, Escape key, click-outside
  - Cancel buttons must call $dispatch('closeModal')
  - browse.js listens for closeModal event and clears #modal innerHTML

Errors:
  - Inline display near the form, not alert()
  - Color: text-[var(--color-danger)]
  - Alpine x-show with error message variable
```

**Navigation**

```
Sidebar nav order: Browse, Queue, Import, AI Chat, Export | Admin, Settings
Active page: active_nav template variable, highlights with:
  bg-[var(--color-bg-active)] text-[var(--color-text-sidebar-bright)] font-medium
Inactive: text-[var(--color-text-sidebar)] hover:bg-[var(--color-bg-hover)]

Queue badge: span#nav-badge with badge_total count, bg-[var(--color-accent)]
Breadcrumbs: nav element, items separated by "/" span
Page title format: "Section | artiFACT" (pipe separator, not em dash)
```

**Permission-Aware UI**

```
- Hide buttons the user cannot use — do not show then return 403
- Tree sidebar: +node / +fact buttons only shown when can_manage_uids / can_contribute_uids
- Browse node view: "+ Node" button gated by can_manage, "+ Fact" by can_contribute
- These are computed server-side via kernel.permissions and passed to templates
- Never check global_role directly in templates (exception: admin nav visibility)
```

**JS Patterns**

```
- All JS in artiFACT/static/js/*.js, loaded via {% block head_scripts %} with defer
- Alpine.js x-data functions defined in module .js files (settingsApp, queuePage, etc.)
  Exception: simple boolean toggles (x-data="{ open: true }") may be inline
- HTMX CSRF injection: htmx:configRequest listener in browse.js injects X-CSRF-Token header
- Custom events: refreshTree, refreshNode, closeModal dispatched on document.body
- No innerHTML with user data — use textContent or Jinja2 autoescape
```

### 2.4 Git

```
Branch naming: {type}/{short-description}
  feature/queue-scope-check
  fix/csrf-header-mismatch
  infra/docker-compose-redis

Commit messages: imperative, <72 chars
  "Add scope check to queue reject endpoint"
  "Fix CSRF header name in feedback module"
  NOT: "Added...", "Fixing...", "Updated..."

Merge strategy: squash merge to main (clean history)
Tags: v0.1.0, v0.2.0, etc. (semver)
```

### 2.5 API Design

```
- All endpoints under /api/v1/
- RESTful: nouns not verbs (GET /facts, not GET /getFacts)
- Exception: action endpoints use POST with verb (POST /facts/{uid}/retire)
- Pagination: ?offset=0&limit=50 (default limit=50, max=200)
- Filtering: ?state=published&node_uid=xxx
- Sorting: ?sort=created_at&order=desc
- Responses: {"data": [...], "total": 150, "offset": 0, "limit": 50}
- Errors: {"detail": "Human-readable message", "code": "FACT_NOT_FOUND"}
- Status codes: 200 OK, 201 Created, 400 Bad Request, 401 Unauthorized,
                403 Forbidden, 404 Not Found, 409 Conflict, 422 Validation Error,
                429 Rate Limited, 500 Internal Server Error
- CSRF: X-CSRF-Token header on all POST/PUT/PATCH/DELETE
- Auth: session cookie (browser) or Authorization: Bearer (API key)
```

---

## 3. DEVELOPMENT GUIDE

### 3.1 Project Structure Rules

```
artiFACT/
├── kernel/           ← ONLY shared import allowed across modules
├── modules/
│   └── {context}/
│       ├── router.py     ← PUBLIC: FastAPI router (the only entry point)
│       ├── schemas.py    ← PUBLIC: Pydantic input/output models
│       ├── service.py    ← PRIVATE: business logic
│       ├── *.py          ← PRIVATE: internal components
│       └── tests/        ← Tests for this context only
├── static/           ← Shared frontend assets
├── templates/        ← Jinja2 HTML templates
├── migrations/       ← Alembic migration scripts
└── tests/            ← Integration + E2E tests
```

### 3.2 Module Creation Checklist

When adding a new module:

```
1. Create directory: modules/{name}/
2. Create router.py with FastAPI APIRouter(prefix="/api/v1/{name}", tags=["{name}"])
3. Create schemas.py with Pydantic models for all inputs and outputs
4. Create service.py with business logic functions
5. Create tests/ directory with at least one test file
6. Register router in main.py: app.include_router(name.router.router)
7. Add health check endpoint: GET /api/v1/{name}/health
8. Add to admin module_health.py check list
```

### 3.3 Dependency Injection Pattern

Every handler receives its dependencies through FastAPI's `Depends`:

```python
# CORRECT — dependencies injected
@router.post("/facts")
async def create_fact(
    body: FactCreate,                          # Pydantic validates input
    user: User = Depends(get_current_user),    # Auth middleware
    db: AsyncSession = Depends(get_db),        # Database session
    perms: PermissionService = Depends(),      # Permission resolver
):
    if not await perms.can(user, 'contribute', body.node_uid):
        raise Forbidden("Cannot create facts in this node")
    ...

# WRONG — importing and calling directly
from modules.auth_admin.service import get_user  # NEVER cross-import
```

### 3.4 Error Handling Pattern

```python
# kernel/exceptions.py — all custom exceptions
class AppError(HTTPException): ...
class NotFound(AppError):    status_code = 404
class Forbidden(AppError):   status_code = 403
class Conflict(AppError):    status_code = 409
class RateLimited(AppError): status_code = 429

# In service code — raise specific exceptions
fact = await db.get(Fact, fact_uid)
if not fact:
    raise NotFound("Fact not found", code="FACT_NOT_FOUND")

# In router — FastAPI catches and returns JSON automatically
# No try/except in routers unless you need to transform the error
```

### 3.5 Transaction Pattern

```python
# Every write operation is wrapped in a transaction
async def approve_fact(db: AsyncSession, version_uid: UUID, actor: User):
    async with db.begin():  # transaction starts
        version = await db.get(FactVersion, version_uid)
        if not version:
            raise NotFound("Version not found")
        version.state = 'published'
        version.published_at = utcnow()
        fact = await db.get(Fact, version.fact_uid)
        fact.current_published_version_uid = version_uid
        # If ANYTHING above throws, the transaction rolls back automatically
    # Transaction committed here
    await events.publish('fact.published', {...})  # After commit only
```

### 3.6 Event Bus Pattern

```python
# kernel/events.py
_subscribers: dict[str, list[Callable]] = {}

def subscribe(event_type: str, handler: Callable):
    _subscribers.setdefault(event_type, []).append(handler)

async def publish(event_type: str, payload: dict):
    for handler in _subscribers.get(event_type, []):
        await handler(payload)

# In audit/recorder.py (module startup)
subscribe('fact.published', record_fact_published)
subscribe('fact.retired', record_fact_retired)
subscribe('version.approved', record_version_approved)

# In queue/badge_counter.py
subscribe('version.approved', invalidate_badge_cache)
subscribe('version.rejected', invalidate_badge_cache)
```

### 3.7 Adding a New Endpoint Checklist

```
1. Define Pydantic input schema in schemas.py
2. Define Pydantic output schema in schemas.py
3. Add business logic function in service.py (or appropriate component)
4. Add route in router.py with:
   - Type-annotated params
   - Depends(get_current_user) for auth
   - Depends(get_db) for database
   - Permission check as first line of handler
5. Write test in tests/
6. Run: pytest modules/{name}/tests/ -x
7. Run: ruff check modules/{name}/
8. Run: mypy modules/{name}/
```

---

## 4. DATA ENGINEERING GUIDE

### 4.1 Schema Management

```
Tool: Alembic
Config: alembic.ini (points to DATABASE_URL env var)
Migrations: migrations/versions/{hash}_{description}.py

# Create migration from model changes
alembic revision --autogenerate -m "add expires_at to fc_signature"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1

# Show current state
alembic current

# Show migration history
alembic history
```

**Migration rules**:

```
- NEVER hand-edit an applied migration
- NEVER delete a migration that's been applied to test or prod
- Always review autogenerated migrations — they're a starting point
- Additive changes only in normal deploys (add column with default, add table, add index)
- Destructive changes in two phases:
    Phase 1: Stop writing to old column, deploy, verify
    Phase 2: Next release drops the column
- Every migration must be reversible (implement downgrade)
- Test both upgrade AND downgrade locally before pushing
```

### 4.2 Connection Management

```python
# kernel/db.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,              # Max persistent connections
    max_overflow=5,            # Burst connections above pool_size
    pool_timeout=30,           # Wait for connection before error
    pool_recycle=3600,         # Recycle connections after 1 hour
    echo=settings.SQL_ECHO,   # Log SQL in dev, not prod
)

async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session
```

### 4.3 Query Patterns

```python
# SINGLE ROW — raise if missing
fact = await db.get(Fact, fact_uid)
if not fact:
    raise NotFound("Fact not found")

# FILTERED LIST — with pagination
stmt = (
    select(Fact)
    .where(Fact.node_uid == node_uid, Fact.is_retired == False)
    .order_by(Fact.created_at.desc())
    .offset(offset)
    .limit(limit)
)
result = await db.execute(stmt)
facts = result.scalars().all()

# COUNT — for pagination total
count_stmt = select(func.count()).select_from(Fact).where(...)
total = (await db.execute(count_stmt)).scalar()

# RECURSIVE CTE — descendants (ONE implementation in kernel)
# kernel/tree/descendants.py
async def get_descendants(db: AsyncSession, root_uid: UUID) -> list[UUID]:
    cte = (
        select(Node.node_uid)
        .where(Node.node_uid == root_uid)
        .cte(name="tree", recursive=True)
    )
    cte = cte.union_all(
        select(Node.node_uid)
        .join(cte, Node.parent_node_uid == cte.c.node_uid)
    )
    result = await db.execute(select(cte.c.node_uid))
    return [row[0] for row in result.all()]

# FULL-TEXT SEARCH — using generated tsvector column
stmt = (
    select(FactVersion)
    .where(FactVersion.search_vector.match(query))
    .order_by(func.ts_rank(FactVersion.search_vector, func.plainto_tsquery(query)).desc())
    .limit(50)
)
```

### 4.4 Caching Strategy

```
Layer 1: Per-request (Python dict on the request context)
  - User grants: fetched once per request, reused in all permission checks
  - Node tree: fetched once per request for breadcrumbs, tree rendering

Layer 2: Redis (shared across requests, TTL-based)
  - Permission resolution: key="perm:{user_uid}:{node_uid}", TTL=300s
  - Queue badge count: key="badge:{user_uid}", TTL=60s
  - Node tree: key="tree:full", TTL=600s (invalidated on node change)
  - Search acronyms: key="acronyms", TTL=3600s (invalidated on fact publish)

Layer 3: PostgreSQL (source of truth)
  - Everything falls through to the database if cache misses

Cache invalidation events:
  node.created / node.moved / node.archived  → flush tree:full
  grant.created / grant.revoked              → flush perm:{user_uid}:*
  version.approved / version.rejected        → flush badge:{user_uid}
  fact.published                             → flush acronyms
```

### 4.5 Backup & Recovery

```
DEV (VPS):
  - docker-compose volume for PostgreSQL data
  - Manual pg_dump before risky changes
  - docker-compose down / up to reset

TEST (COSMOS):
  - RDS automated snapshots, 7-day retention
  - Alembic downgrade for schema rollback

PROD (COSMOS):
  - RDS Multi-AZ, automated backups, 35-day retention
  - Point-in-time recovery (PITR) to any second in the last 35 days
  - S3 versioning on all buckets (30-day retention for deleted objects)
  - Admin-triggered pg_dump to S3 via admin/snapshot_manager.py
```

### 4.6 Data Migration from v1

```python
# One-time script: migrate_v1_to_v2.py
# Reads: MySQL dump (techstat_factcorpus.sql)
# Writes: PostgreSQL (v2 schema)

# Mapping:
#   CHAR(36) UIDs       → native UUID
#   DATETIME             → TIMESTAMPTZ (assume UTC, add +00:00)
#   JSON TEXT columns    → JSONB
#   fc_fact.created_by_user_uid NULL → backfill from earliest fc_fact_version
#   fc_fact_version.published_at NULL → backfill from fc_event_log approved_published
#   fc_node.node_depth   → compute from parent chain
#   search_vector         → auto-generated by PostgreSQL (no action needed)

# Tables to skip:
#   fc_ownership          → dead table
#   fc_telem_*            → telemetry excluded from v2
#   fc_session            → sessions are Redis in v2
#   fc_rate_limit         → rate limiting is Redis in v2 (table dropped)
#   fc_feedback_event     → merged into fc_event_log (entity_type='feedback')

# Validation:
#   assert v2_fact_count == v1_fact_count
#   assert v2_version_count == v1_version_count
#   assert v2_node_count == v1_node_count
#   assert every fact has a non-NULL created_by_uid
#   assert every published version has a non-NULL published_at
```

---

## 5. TEST STRATEGY & PSEUDOCODE

### 5.1 Test Pyramid

```
                    ┌─────────┐
                    │  E2E    │  ~10 tests (Playwright, full browser)
                   ┌┴─────────┴┐
                   │ Integration │  ~30 tests (real DB, real Redis, HTTP calls)
                  ┌┴─────────────┴┐
                  │   Unit Tests   │  ~200 tests (per-component, mocked deps)
                  └────────────────┘

Coverage target: 80% overall, 95% on kernel/
```

### 5.2 Test Infrastructure

```python
# tests/conftest.py

@pytest.fixture(scope="session")
async def db_engine():
    """Create test database, run migrations, yield engine, drop database."""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def db(db_engine):
    """Per-test database session with automatic rollback."""
    async with AsyncSession(db_engine) as session:
        async with session.begin():
            yield session
            await session.rollback()  # Every test starts clean

@pytest.fixture
async def client(db):
    """Test HTTP client."""
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
def admin_user(db):
    """Pre-created admin user."""
    user = User(display_name="Test Admin", global_role="admin", cac_dn="CN=test")
    db.add(user)
    return user

@pytest.fixture
def contributor_user(db):
    """Pre-created contributor user."""
    user = User(display_name="Test Contributor", global_role="contributor", cac_dn="CN=contrib")
    db.add(user)
    return user

@pytest.fixture
def sample_tree(db):
    """Pre-created taxonomy: root → branch → twig with 5 facts."""
    root = Node(title="Program A", node_depth=0)
    branch = Node(title="System Config", parent_node_uid=root.node_uid, node_depth=1)
    twig = Node(title="Interfaces", parent_node_uid=branch.node_uid, node_depth=2)
    db.add_all([root, branch, twig])
    facts = [make_fact(twig.node_uid, f"Fact {i}") for i in range(5)]
    db.add_all(facts)
    return {"root": root, "branch": branch, "twig": twig, "facts": facts}
```

### 5.3 Unit Test Pseudocode

```python
# --- kernel/permissions/test_resolver.py ---

async def test_admin_can_do_everything(db, admin_user, sample_tree):
    """Admin global_role grants all permissions regardless of node grants."""
    assert await can(admin_user, 'admin', sample_tree["twig"].node_uid) == True

async def test_contributor_cannot_approve(db, contributor_user, sample_tree):
    """Contributor without node grant cannot approve."""
    assert await can(contributor_user, 'approve', sample_tree["twig"].node_uid) == False

async def test_node_grant_overrides_global_role(db, contributor_user, sample_tree):
    """Per-node approver grant overrides contributor global_role."""
    # Grant approver on branch → inherits to twig
    await create_grant(db, contributor_user, sample_tree["branch"], role="approver")
    assert await can(contributor_user, 'approve', sample_tree["twig"].node_uid) == True

async def test_revoked_grant_not_honored(db, contributor_user, sample_tree):
    """Revoked grant does not grant access."""
    grant = await create_grant(db, contributor_user, sample_tree["branch"], role="approver")
    await revoke_grant(db, grant)
    assert await can(contributor_user, 'approve', sample_tree["twig"].node_uid) == False

async def test_grant_on_parent_inherits_to_descendants(db, contributor_user, sample_tree):
    """Grant on root inherits to branch and twig."""
    await create_grant(db, contributor_user, sample_tree["root"], role="signatory")
    assert await can(contributor_user, 'sign', sample_tree["twig"].node_uid) == True


# --- kernel/tree/test_descendants.py ---

async def test_descendants_returns_full_subtree(db, sample_tree):
    """get_descendants(root) returns root + branch + twig."""
    desc = await get_descendants(db, sample_tree["root"].node_uid)
    assert len(desc) == 3
    assert sample_tree["twig"].node_uid in desc

async def test_descendants_of_leaf_returns_only_self(db, sample_tree):
    """Leaf node has no descendants beyond itself."""
    desc = await get_descendants(db, sample_tree["twig"].node_uid)
    assert desc == [sample_tree["twig"].node_uid]


# --- modules/facts/tests/test_state_machine.py ---

async def test_proposed_can_transition_to_published(db, sample_tree):
    """proposed → published is a valid transition."""
    version = make_version(sample_tree["facts"][0], state="proposed")
    await transition(db, version, "published", actor=admin_user)
    assert version.state == "published"
    assert version.published_at is not None

async def test_signed_cannot_transition_to_proposed(db, sample_tree):
    """signed → proposed is forbidden."""
    version = make_version(sample_tree["facts"][0], state="signed")
    with pytest.raises(Conflict, match="Invalid state transition"):
        await transition(db, version, "proposed", actor=admin_user)

async def test_publish_always_sets_published_at(db, sample_tree):
    """Every publish path sets published_at — no NULL values."""
    version = make_version(sample_tree["facts"][0], state="proposed")
    await transition(db, version, "published", actor=admin_user)
    assert version.published_at is not None
    # Verify the v1 bug (S-BUG-01) is impossible
    stmt = select(FactVersion).where(
        FactVersion.state == 'published',
        FactVersion.published_at == None
    )
    orphans = (await db.execute(stmt)).scalars().all()
    assert len(orphans) == 0


# --- modules/facts/tests/test_create.py ---

async def test_create_fact_sets_created_by(db, contributor_user, sample_tree):
    """created_by_uid is always set — never NULL (fixing v1 F-DATA-01)."""
    fact = await create_fact(db, node_uid=sample_tree["twig"].node_uid,
                             sentence="Test fact", actor=contributor_user)
    assert fact.created_by_uid == contributor_user.user_uid

async def test_create_fact_without_permission_forbidden(db, contributor_user):
    """Cannot create fact in node without at least contributor permission."""
    other_node = Node(title="Restricted", node_depth=0)
    db.add(other_node)
    with pytest.raises(Forbidden):
        await create_fact(db, node_uid=other_node.node_uid,
                         sentence="Test", actor=contributor_user)


# --- modules/queue/tests/test_scope_enforcement.py ---

async def test_subapprover_cannot_reject_outside_scope(db, sample_tree):
    """Subapprover on Node A cannot reject proposal from Node B (fixing v1 Q-SEC-01)."""
    user = make_user(global_role="contributor")
    node_a = make_node("Node A")
    node_b = make_node("Node B")
    await create_grant(db, user, node_a, role="subapprover")
    proposal = make_proposal(node_b)
    with pytest.raises(Forbidden, match="outside your scope"):
        await reject_proposal(db, proposal.version_uid, actor=user)

async def test_subapprover_can_reject_within_scope(db, sample_tree):
    """Subapprover on Node A can reject proposal from Node A."""
    user = make_user(global_role="contributor")
    node_a = make_node("Node A")
    await create_grant(db, user, node_a, role="subapprover")
    proposal = make_proposal(node_a)
    await reject_proposal(db, proposal.version_uid, actor=user)
    assert proposal.state == "rejected"


# --- modules/audit/tests/test_undo_permissions.py ---

async def test_undo_requires_current_permission(db, sample_tree):
    """User who lost permission cannot undo their earlier action (fixing v1 U-SEC-02)."""
    user = make_user(global_role="contributor")
    grant = await create_grant(db, user, sample_tree["branch"], role="approver")
    # User approves a fact while they have permission
    event = await approve_and_record(db, sample_tree["facts"][0], actor=user)
    # Permission revoked
    await revoke_grant(db, grant)
    # Undo attempt should fail
    with pytest.raises(Forbidden, match="no longer have permission"):
        await undo_event(db, event.event_uid, actor=user)

async def test_no_public_undo_record_endpoint(client):
    """POST /api/v1/audit/undo/record does not exist (fixing v1 U-SEC-01)."""
    resp = await client.post("/api/v1/audit/undo/record", json={"anything": "here"})
    assert resp.status_code in (404, 405)


# --- modules/ai_chat/tests/test_token_counting.py ---

async def test_prompt_never_truncated_mid_sentence():
    """System prompt stops adding facts at token limit, never byte-truncates (fixing v1 A-SEC-01)."""
    facts = [f"This is fact number {i} with some content." for i in range(500)]
    prompt = build_system_prompt(facts, max_tokens=4000)
    # Verify last line is a complete sentence
    last_line = prompt.strip().split('\n')[-1]
    assert last_line.endswith('.')
    # Verify token count is under limit
    assert count_tokens(prompt) <= 4000
```

### 5.4 Integration Test Pseudocode

```python
# --- tests/integration/test_full_lifecycle.py ---

async def test_fact_lifecycle_propose_approve_sign(client, admin_headers):
    """Full lifecycle: create → propose → approve → sign."""
    # Create node
    node = await client.post("/api/v1/nodes", json={"title": "Test Program"},
                             headers=admin_headers)
    node_uid = node.json()["data"]["node_uid"]

    # Create fact (auto-published because admin)
    fact = await client.post("/api/v1/facts",
                             json={"node_uid": node_uid, "sentence": "System is Navy-owned."},
                             headers=admin_headers)
    assert fact.status_code == 201
    fact_uid = fact.json()["data"]["fact_uid"]

    # Verify published_at is set
    detail = await client.get(f"/api/v1/facts/{fact_uid}", headers=admin_headers)
    assert detail.json()["data"]["current_version"]["published_at"] is not None

    # Sign
    sig = await client.post(f"/api/v1/signatures/node/{node_uid}",
                            headers=admin_headers)
    assert sig.status_code == 201

    # Verify signed state
    detail2 = await client.get(f"/api/v1/facts/{fact_uid}", headers=admin_headers)
    assert detail2.json()["data"]["current_version"]["state"] == "signed"


async def test_csrf_required_on_all_writes(client, auth_headers):
    """Every POST/PUT/PATCH/DELETE returns 403 without CSRF token."""
    write_endpoints = [
        ("POST", "/api/v1/facts", {"node_uid": "...", "sentence": "..."}),
        ("POST", "/api/v1/nodes", {"title": "Test"}),
        ("POST", "/api/v1/grants", {"user_uid": "...", "node_uid": "...", "role": "viewer"}),
    ]
    for method, path, body in write_endpoints:
        headers = {**auth_headers}
        headers.pop("X-CSRF-Token", None)  # Remove CSRF
        resp = await client.request(method, path, json=body, headers=headers)
        assert resp.status_code == 403, f"{method} {path} allowed without CSRF"


async def test_unauthenticated_blocked_on_all_endpoints(client):
    """Every endpoint returns 401 without auth (fixing v1 D-SEC-01, I-LOW-03)."""
    endpoints = [
        "/api/v1/facts", "/api/v1/nodes", "/api/v1/export/factsheet",
        "/api/v1/queue/proposals", "/api/v1/audit/events",
    ]
    for path in endpoints:
        resp = await client.get(path)
        assert resp.status_code == 401, f"{path} accessible without auth"
```

### 5.5 E2E Test Pseudocode

```python
# --- tests/e2e/test_approval_flow.py ---

async def test_contributor_propose_approver_approve(browser):
    """Contributor submits a fact, approver sees it in queue and approves."""
    # Login as contributor
    contributor_page = await login_as(browser, "contributor")
    await contributor_page.goto("/new")
    await contributor_page.select("node_uid", "Program A > Interfaces")
    await contributor_page.fill("sentence", "The system operates at IL-4.")
    await contributor_page.click("Create fact")
    await expect(contributor_page.locator(".success")).to_be_visible()

    # Login as approver
    approver_page = await login_as(browser, "approver")
    await approver_page.goto("/queue")
    proposal = approver_page.locator("text=The system operates at IL-4.")
    await expect(proposal).to_be_visible()
    await proposal.locator("button:has-text('Approve')").click()
    await expect(proposal).not_to_be_visible()  # Removed from queue

    # Verify fact is published in browse
    await approver_page.goto("/browse?node=interfaces")
    await expect(approver_page.locator("text=The system operates at IL-4.")).to_be_visible()
```

---

## 6. CAPABILITY SPRINTS

Each sprint delivers a shippable capability. Sprints are ordered by dependency — Sprint N depends only on Sprint N-1 or earlier. Each has a **Definition of Success (DoS)** that is binary: it either works or it doesn't.

### Sprint 0: Infrastructure

**Capability**: A developer can SSH into the VPS, run `docker-compose up`, visit `artifact.jordanaallred.com` in a browser, and see a health check JSON response.

**Definition of Success**:
- VPS accessible via SSH
- Docker + Docker Compose installed
- Git repo initialized with project skeleton
- `docker-compose up` starts 4 containers (web, worker, postgres, redis)
- `curl https://artifact.jordanaallred.com/api/v1/health` returns `{"status": "healthy"}`
- HTTPS via Let's Encrypt (certbot)
- Claude Code connected and can edit/run code on VPS

**Delivers**: `docker-compose.yml`, `Dockerfile`, `Dockerfile.worker`, nginx config, `pyproject.toml`, `alembic.ini`, project skeleton, CI lint config

---

### Sprint 1: Kernel + Auth

**Capability**: A user can authenticate (dev mode: username/password; prod: CAC), receive a session, and have their identity persist across requests. The permission system resolves roles correctly for any user on any node.

**Definition of Success**:
- `POST /api/v1/auth/login` returns a session cookie (dev mode)
- `GET /api/v1/users/me` returns the authenticated user's profile
- Unauthenticated requests to any endpoint return 401
- CSRF token is set on login, validated on all writes
- `kernel/permissions/resolver.py` passes all unit tests:
  - Admin can do everything
  - Node grant overrides global_role
  - Grant on parent inherits to children
  - Revoked grant is not honored
- Rate limiter blocks after threshold
- All kernel unit tests pass

**Delivers**: `kernel/` (all 18 components), `modules/auth_admin/` (cac_mapper, service, router), Alembic migration for `fc_user`, `fc_node_permission`, `fc_system_config`, `fc_api_key`. Also: `docs/rmf/boundary-diagram.md`, `docs/rmf/data-flow.md` (updated each subsequent sprint)

---

### Sprint 2: Taxonomy

**Capability**: An authenticated user can view the full node tree, and an admin can create, rename, reparent, and archive nodes. The tree renders in <100ms regardless of depth.

**Definition of Success**:
- `GET /api/v1/nodes` returns the full tree in both flat and nested JSON formats
- `POST /api/v1/nodes` creates a node with correct `node_depth`
- `PUT /api/v1/nodes/{uid}` renames, reorders
- `POST /api/v1/nodes/{uid}/move` reparents and recomputes depth for all descendants
- Circular reparent is rejected with 409
- Tree response is cached in Redis, invalidated on change
- Browser renders collapsible tree in left pane (HTMX partial)
- All taxonomy unit tests pass

**Delivers**: `modules/taxonomy/` (5 components), Alembic migration for `fc_node`, left-pane template, tree JS

---

### Sprint 3: Facts Core

**Capability**: An authenticated user can create, edit, and retire facts. Versions are tracked. The state machine enforces valid transitions. Every mutation records an audit event.

**Definition of Success**:
- `POST /api/v1/facts` creates a fact + initial version
- Contributor creates → version state = `proposed`
- Approver creates → version state = `published`, `published_at` is set
- `PUT /api/v1/facts/{uid}` creates a new version (supersedes previous)
- `POST /api/v1/facts/{uid}/retire` sets `is_retired = true`
- State machine rejects invalid transitions (signed → proposed, retired → published)
- `created_by_uid` is set on both `fc_fact` and `fc_fact_version` (never NULL)
- Every mutation emits an event that `audit/recorder.py` captures
- `GET /api/v1/facts/{uid}/versions` returns full version history
- Browse page renders facts grouped by node
- All fact unit tests pass, including state machine edge cases

**Delivers**: `modules/facts/` (8 components), `modules/audit/` (6 components), Alembic migration for `fc_fact`, `fc_fact_version`, `fc_event_log`, browse template

---

### Sprint 4: Queue + Approval

**Capability**: Contributors propose facts. Approvers see proposals scoped to their nodes and can approve, reject, or revise. Badge counts appear in the nav. All scope checks are enforced.

**Definition of Success**:
- Proposed facts appear in the queue for users with `subapprover+` on that node
- Subapprover on Node A CANNOT see or act on proposals from Node B
- `POST /api/v1/queue/approve/{uid}` publishes the version (within transaction)
- `POST /api/v1/queue/reject/{uid}` rejects with optional note
- "Revise language" approve path: reject original + publish revised (atomic)
- Queue badge count in nav is accurate, updates within 60s of change
- All scope enforcement tests pass (the Q-SEC-01/02 regression tests)

**Delivers**: `modules/queue/` (7 components), queue page template, badge counter integration

---

### Sprint 5: Signing

**Capability**: A signatory can sign all published facts under a node. Signatures are recorded with optional expiration. The sign action is batched (one query, not per-fact).

**Definition of Success**:
- `POST /api/v1/signatures/node/{uid}` signs all published facts under that node
- Permission uses resolved role, not global_role
- Batch UPDATE runs as one query inside a transaction
- Signature record created with fact count
- `GET /api/v1/signatures` lists signatures filtered by node/signer
- Sign pane in queue shows only nodes within user's scope
- All signing unit tests pass

**Delivers**: `modules/signing/` (5 components), sign pane template

---

### Sprint 6: Search

**Capability**: Users can search facts by text. Results include breadcrumbs. Acronyms are mined from the corpus.

**Definition of Success**:
- `GET /api/v1/search?q=system+owner` returns ranked results with breadcrumbs
- Search uses PostgreSQL tsvector (no N+1 CTEs per result)
- Breadcrumbs resolved from cached in-memory tree
- `GET /api/v1/search/acronyms` returns mined acronyms from correct columns
- Search works for all authenticated users (not blocked by auth like v1)
- Results render in the center pane (HTMX swap)

**Delivers**: `modules/search/` (4 components), search input + results template

---

### Sprint 7: Per-User AI + Chat

**Capability**: Users can configure their own GenAI API key, then ask corpus-grounded questions. The system loads facts with proper token counting, streams responses, and filters output.

**Definition of Success**:
- Settings page allows CRUD for AI API keys (encrypted at rest)
- `POST /api/v1/ai/chat` streams a response grounded in the user's accessible facts
- System prompt is token-counted (never byte-truncated)
- Actual loaded fact count reported to client
- Context endpoint scoped to user's readable nodes (not full taxonomy)
- Input sanitization includes Unicode NFKC normalization
- Output filter catches bulk fact dumps
- Rate limited per user
- Chat works with OpenAI and Anthropic providers
- All AI safety tests pass

**Delivers**: `modules/ai_chat/` (7 + 3 safety components), `modules/auth_admin/ai_key_manager.py`, chat UI template

---

### Sprint 8: Import Pipeline

**Capability**: Users can upload a document, trigger AI extraction, review staged facts, and propose them into the corpus. Long-running analysis runs as a background task with progress streaming.

**Definition of Success**:
- Upload accepts DOCX, PPTX, PDF, TXT with size validation
- Upload stored in S3 (MinIO on VPS)
- Analysis runs as Celery background task (does not block web worker)
- SSE endpoint streams progress to client
- Staged facts displayed for user review with accept/reject per-fact
- Propose creates real facts (all-or-nothing transaction)
- Duplicate detection flags similar existing facts
- CSRF enforced on all endpoints
- Rate limited on both upload and analyze

**Delivers**: `modules/import_pipeline/` (9 + 5 extractor components), import UI template, Celery task registration

---

### Sprint 9: Export

**Capability**: Authenticated users can download the corpus as structured data (TXT/JSON/CSV) or generate a DOCX document. Generated files are stored in S3 with signed download URLs.

**Definition of Success**:
- `GET /api/v1/export/factsheet` requires auth (anonymous returns 401)
- Factsheet export supports TXT, JSON, NDJSON, CSV formats
- DOCX generation runs as background task with SSE progress
- Generated files stored in S3 with 24-hour expiration
- Download URL is user-bound (other users can't download your file)
- Two-pass section assignment (no first-section-gets-first-pick bias)
- All export tests pass

**Delivers**: `modules/export/` (7 + 2 template components), export page template

---

### Sprint 10: Feedback

**Capability**: Anyone (including anonymous users) can submit feedback. Admins manage feedback in a kanban board.

**Definition of Success**:
- `POST /api/v1/feedback` works without auth (rate limited by IP)
- Admin sees feedback in kanban view grouped by category
- Admin can move, comment, edit, close feedback items
- CSRF uses consistent header name (kernel middleware)
- All feedback tests pass

**Delivers**: `modules/feedback/` (5 components), feedback form + admin kanban template

---

### Sprint 11: Presentation

**Capability**: The briefing mode displays a full-screen animated presentation with slides, narration, and beat-driven progression. Tour mode does NOT fire real AI calls.

**Definition of Success**:
- Presentation modal opens from nav icon
- Slides render with beat timing and narration
- VCR controls (play, pause, step, mute) work
- Tour mode uses canned responses instead of real AI calls
- Mobile touch navigation works
- Presentation forces dark theme regardless of app theme

**Delivers**: `modules/presentation/` (4 components), static assets (JS/CSS/audio)

---

### Sprint 12: Admin Dashboard

**Capability**: System admins can view health metrics, manage users, toggle features, flush caches, and trigger snapshots from a single dashboard.

**Definition of Success**:
- Dashboard shows user count, fact count, error rate, active users
- User management: list, search, change role, deactivate/reactivate
- Module health: per-module DB/Redis/S3 connectivity status
- Feature flags: toggle any flag from UI, changes take effect immediately
- Cache: view stats, flush all or by category
- Snapshot: trigger pg_dump to S3, list available snapshots
- All admin endpoints require `global_role = 'admin'`

**Delivers**: `modules/admin/` (8 components), admin dashboard template

---

### Sprint 13: Polish + Harden + RMF

**Capability**: The platform is production-ready with security headers, rate limiting tuned, error pages styled, all E2E tests passing, RMF compliance artifacts drafted, and an incident response runbook written.

**Definition of Success**:
- Security headers on all responses (CSP, X-Frame-Options, HSTS, nosniff)
- Rate limits tuned per endpoint
- Custom 401, 403, 404, 500 error pages
- All 56 unit test files pass
- All integration tests pass
- All E2E tests pass
- `ruff check` and `mypy` clean
- Coverage ≥ 80%
- OpenAPI spec at `/api/v1/openapi.json` is complete and valid
- Load test: 50 concurrent users, p95 < 2s response time
- SSP skeleton complete (`docs/rmf/ssp.md`)
- Control implementation statements drafted (`docs/rmf/control-implementations.md`)
- Boundary diagram and data flow diagram finalized
- Incident response runbook written (`docs/runbook.md`)
- SBOM archived with release tag

**Delivers**: Security middleware, error pages, final test suite, OpenAPI validation, load test results, SSP skeleton, control implementation statements, incident runbook, SBOM

---

### Sprint 14: COSMOS Port

**Capability**: The exact Docker images running on the VPS are deployed to COSMOS GovCloud via Terraform. CAC authentication replaces dev-mode login. Data is migrated from v1.

**Definition of Success**:
- `terraform apply` creates all COSMOS infrastructure (RDS, ECS, Redis, S3, ALB)
- Docker images pushed to ECR, ECS runs them
- CAC login works end-to-end (SAML assertion → session)
- v1 data migrated to v2 PostgreSQL with zero data loss
- All integration tests pass against COSMOS environment
- `artifact.cosmos.navy.mil` serves the production app
- Blue/green deployment tested: push a change, zero downtime

**Delivers**: `terraform/` configs, COSMOS-specific env vars, v1→v2 migration script, CAC SAML integration, production deployment runbook

---

## 7. SUBMODULE PSEUDOCODE

### 7.0 Kernel

#### kernel/auth/middleware.py
```
FUNCTION get_current_user(request):
    cookie = request.cookies.get("session_id")
    IF cookie:
        session = redis.get(f"session:{cookie}")
        IF session:
            user = deserialize(session)
            # ZT CONTINUOUS AUTH: re-validate every 15 min
            IF session.last_validated_at < now() - 15min:
                db_user = db.get(User, user.uid)
                IF NOT db_user OR NOT db_user.is_active:
                    redis.delete(f"session:{cookie}")  # kill stale session
                    RAISE 401 "Session revoked"
                session.last_validated_at = now()
                redis.set(f"session:{cookie}", serialize(session), keepttl=True)
            RETURN user
    
    bearer = request.headers.get("Authorization")
    IF bearer and bearer.startswith("Bearer "):
        token = bearer[7:]
        key_hash = sha256(token)
        api_key = db.query(ApiKey).filter(key_hash=key_hash, expired=False).first()
        IF api_key:
            UPDATE api_key.last_used_at = now()
            RETURN api_key.user
    
    RAISE 401 Unauthorized
```

#### kernel/auth/csrf.py
```
FUNCTION csrf_middleware(request, call_next):
    IF request.method IN (POST, PUT, PATCH, DELETE):
        token = request.headers.get("X-CSRF-Token")
        expected = request.cookies.get("csrf_token")
        IF NOT token OR NOT constant_time_compare(token, expected):
            RAISE 403 "CSRF validation failed"
    RETURN await call_next(request)
```

#### kernel/permissions/resolver.py
```
FUNCTION resolve_role(user, node_uid):
    cache_key = f"perm:{user.uid}:{node_uid}"
    cached = redis.get(cache_key)
    IF cached: RETURN cached

    grants = get_user_grants(user.uid)          # {node_uid: role} from DB, cached per-request
    ancestors = get_ancestors(node_uid)          # [self, parent, grandparent, ...] via CTE

    best = user.global_role
    FOR ancestor IN ancestors:
        IF ancestor IN grants:
            IF role_gte(grants[ancestor], best):
                best = grants[ancestor]

    redis.set(cache_key, best, ttl=300)
    RETURN best

FUNCTION can(user, action, node_uid):
    role = resolve_role(user, node_uid)
    RETURN role_gte(role, REQUIRED_ROLES[action])
```

#### kernel/tree/descendants.py
```
FUNCTION get_descendants(db, root_uid):
    # Single recursive CTE — replaces 5 iterative copies from v1
    WITH RECURSIVE tree AS (
        SELECT node_uid FROM fc_node WHERE node_uid = root_uid
        UNION ALL
        SELECT n.node_uid FROM fc_node n JOIN tree t ON n.parent_node_uid = t.node_uid
    )
    SELECT node_uid FROM tree
    RETURN list of UUIDs
```

#### kernel/ai/provider.py
```
CLASS AIProvider:
    FUNCTION complete(user, messages, response_format=None, stream=False, timeout=120):
        key_record = db.get_ai_key(user.uid)
        IF NOT key_record:
            RAISE 400 "No AI API key configured"

        plaintext_key = decrypt(key_record.encrypted_key)

        IF key_record.provider == "openai":
            RETURN call_openai(plaintext_key, messages, response_format, stream, timeout)
        ELIF key_record.provider == "anthropic":
            RETURN call_anthropic(plaintext_key, messages, stream, timeout)
        ELIF key_record.provider == "azure_openai":
            RETURN call_azure(plaintext_key, messages, response_format, stream, timeout)
```

#### kernel/events.py
```
subscribers = {}

FUNCTION subscribe(event_type, handler):
    subscribers[event_type].append(handler)

FUNCTION publish(event_type, payload):
    FOR handler IN subscribers[event_type]:
        await handler(payload)
```

#### kernel/rate_limiter.py
```
FUNCTION check_rate(user_uid_or_ip, action):
    key = f"rate:{action}:{user_uid_or_ip}"
    config = get_config(f"security.rate_limit.{action}")
    window = 3600  # 1 hour
    
    count = redis.get(key) or 0
    IF count >= config.max:
        RAISE 429 f"Rate limited: {config.max} per hour"
    
    redis.incr(key)
    redis.expire(key, window)
```

#### kernel/access_logger.py (ZT Pillar 5 — Data Access Logging)
```
FUNCTION log_data_access(user, action, detail):
    """Log data-exfiltration-relevant access events. Non-blocking (background task)."""
    event = EventLog(
        entity_type='access',
        entity_uid=user.uid,
        event_type=f'access.{action}',   # access.export, access.ai_chat, access.sync
        payload=detail,                    # {format: 'json', node_filter: [...], count: 150}
        actor_uid=user.uid,
    )
    db.add(event)

# Called from:
#   export/factsheet.py     → log_data_access(user, 'export', {format, node_uids, count})
#   ai_chat/service.py      → log_data_access(user, 'ai_chat', {topic, facts_loaded})
#   export/sync.py           → log_data_access(user, 'sync_delta', {cursor, count})
#   export/sync.py           → log_data_access(user, 'sync_full', {total_count})
# NOT called from: page views, search, tree browse (noise)
```

#### kernel/anomaly_detector.py (ZT Pillar 6+7 — Detect & Auto-Remediate)
```
FUNCTION check_anomaly(user_uid):
    """Run after every data-access event. Uses Redis counters."""
    
    # Rule 1: Export flood (>10 exports in 30 min)
    export_key = f"anomaly:export:{user_uid}"
    export_count = redis.incr(export_key)
    IF export_count == 1: redis.expire(export_key, 1800)
    IF export_count > 10: trigger_anomaly(user_uid, 'export_flood', export_count)
    
    # Rule 2: AI mining (>50 AI calls in 1 hr)  
    ai_key = f"anomaly:ai:{user_uid}"
    ai_count = redis.incr(ai_key)
    IF ai_count == 1: redis.expire(ai_key, 3600)
    IF ai_count > 50: trigger_anomaly(user_uid, 'ai_mining', ai_count)
    
    # Rule 3: Rapid 403s (>10 in 10 min) — scope escalation attempt
    deny_key = f"anomaly:deny:{user_uid}"
    deny_count = redis.incr(deny_key)
    IF deny_count == 1: redis.expire(deny_key, 600)
    IF deny_count > 10: trigger_anomaly(user_uid, 'scope_escalation', deny_count)

FUNCTION trigger_anomaly(user_uid, rule, count):
    # 1. Log the anomaly
    event = EventLog(entity_type='anomaly', entity_uid=user_uid,
                     event_type=f'anomaly.{rule}', payload={count, triggered_at: now()})
    db.add(event)
    
    # 2. Auto-expire all sessions (force re-CAC)
    force_destroy_user_sessions(user_uid)
    
    # 3. Alert admin via SSE / dashboard flag
    redis.publish('admin:alerts', json({user_uid, rule, count, time: now()}))
```

---

### 7.1 Taxonomy

#### modules/taxonomy/service.py
```
FUNCTION create_node(db, title, parent_uid, sort_order, actor):
    IF parent_uid:
        parent = db.get(Node, parent_uid)
        IF NOT parent: RAISE NotFound
        IF NOT can(actor, 'manage_node', parent_uid): RAISE Forbidden
        depth = parent.node_depth + 1
    ELSE:
        IF NOT actor.global_role == 'admin': RAISE Forbidden
        depth = 0

    validate_title_unique_among_siblings(db, title, parent_uid)
    IF depth > 5: RAISE Conflict("Maximum tree depth exceeded")

    slug = slugify(title)
    node = Node(title=title, parent_node_uid=parent_uid, slug=slug,
                node_depth=depth, sort_order=sort_order, created_by_uid=actor.uid)
    db.add(node)
    await db.flush()
    
    redis.delete("tree:full")
    await publish('node.created', {node_uid: node.uid, actor_uid: actor.uid})
    RETURN node

FUNCTION move_node(db, node_uid, new_parent_uid, actor):
    node = db.get(Node, node_uid)
    IF NOT node: RAISE NotFound
    IF NOT can(actor, 'manage_node', node_uid): RAISE Forbidden

    # Prevent circular reference
    descendants = get_descendants(db, node_uid)
    IF new_parent_uid IN descendants: RAISE Conflict("Circular reparent")

    new_depth = (db.get(Node, new_parent_uid).node_depth + 1) IF new_parent_uid ELSE 0
    depth_delta = new_depth - node.node_depth

    node.parent_node_uid = new_parent_uid
    node.node_depth = new_depth

    # Update all descendant depths
    FOR desc_uid IN descendants:
        IF desc_uid != node_uid:
            desc = db.get(Node, desc_uid)
            desc.node_depth += depth_delta

    redis.delete("tree:full")
    await publish('node.moved', {node_uid: node_uid, actor_uid: actor.uid})
```

#### modules/taxonomy/tree_serializer.py
```
FUNCTION build_nested_tree(flat_nodes):
    by_uid = {n.uid: {**n, children: []} FOR n IN flat_nodes}
    roots = []
    FOR n IN flat_nodes:
        IF n.parent_uid AND n.parent_uid IN by_uid:
            by_uid[n.parent_uid]["children"].append(by_uid[n.uid])
        ELSE:
            roots.append(by_uid[n.uid])
    RETURN roots

FUNCTION get_breadcrumb(flat_nodes, node_uid):
    path = []
    current = node_uid
    by_uid = {n.uid: n FOR n IN flat_nodes}
    WHILE current:
        path.insert(0, by_uid[current])
        current = by_uid[current].parent_uid
    RETURN path
```

---

### 7.2 Facts

#### modules/facts/state_machine.py
```
ALLOWED_TRANSITIONS = {
    'proposed':   ['published', 'rejected', 'withdrawn'],
    'challenged': ['accepted', 'rejected'],
    'accepted':   ['published'],
    'rejected':   [],            # terminal
    'published':  ['signed', 'retired'],
    'signed':     ['retired'],
    'withdrawn':  [],            # terminal
    'retired':    [],            # terminal
}

FUNCTION transition(db, version, new_state, actor):
    IF new_state NOT IN ALLOWED_TRANSITIONS[version.state]:
        RAISE Conflict(f"Cannot transition from {version.state} to {new_state}")

    version.state = new_state

    IF new_state == 'published':
        version.published_at = utcnow()      # ALWAYS set — fixes v1 S-BUG-01
    IF new_state == 'signed':
        version.signed_at = utcnow()

    await publish(f'version.{new_state}', {
        version_uid: version.uid,
        fact_uid: version.fact_uid,
        actor_uid: actor.uid,
    })
```

#### modules/facts/versioning.py
```
FUNCTION create_version(db, fact, sentence, metadata, actor, change_summary=None):
    version = FactVersion(
        fact_uid=fact.uid,
        display_sentence=sentence,
        metadata_tags=metadata.tags,
        source_reference=metadata.source,
        effective_date=metadata.effective_date,
        classification=metadata.classification,
        change_summary=change_summary,
        supersedes_version_uid=fact.current_published_version_uid,
        created_by_uid=actor.uid,                # ALWAYS set — fixes v1 F-DATA-01
    )

    IF can(actor, 'approve', fact.node_uid):
        version.state = 'published'
        version.published_at = utcnow()          # ALWAYS set — fixes v1 S-BUG-01
        fact.current_published_version_uid = version.uid
    ELSE:
        version.state = 'proposed'

    db.add(version)
    RETURN version
```

#### modules/facts/reassign.py
```
FUNCTION reassign_fact(db, fact_uid, target_node_uid, actor):
    fact = db.get(Fact, fact_uid)
    IF NOT fact: RAISE NotFound
    
    # Must have permission on BOTH source AND target
    IF NOT can(actor, 'approve', fact.node_uid): RAISE Forbidden("No permission on source")
    IF NOT can(actor, 'approve', target_node_uid): RAISE Forbidden("No permission on target")

    target = db.get(Node, target_node_uid)
    IF NOT target: RAISE NotFound("Target node not found")

    old_node = fact.node_uid
    fact.node_uid = target_node_uid

    await publish('fact.moved', {
        fact_uid: fact_uid,
        old_node_uid: old_node,
        new_node_uid: target_node_uid,
        actor_uid: actor.uid,
    })
```

---

### 7.3 Auth Admin

#### modules/auth_admin/cac_mapper.py
```
FUNCTION map_saml_to_user(db, saml_assertion):
    edipi = extract_edipi(saml_assertion)
    dn = extract_dn(saml_assertion)
    email = extract_email(saml_assertion)
    display_name = extract_name(saml_assertion)

    user = db.query(User).filter(User.edipi == edipi).first()

    IF NOT user:
        user = User(
            edipi=edipi,
            cac_dn=dn,
            email=email,
            display_name=display_name,
            global_role='viewer',              # Default role for new users
        )
        db.add(user)
    ELSE:
        user.last_login_at = utcnow()
        user.cac_dn = dn                      # Update in case DN changed (re-cert)

    RETURN user
```

#### modules/auth_admin/ai_key_manager.py
```
FUNCTION save_ai_key(db, user, provider, plaintext_key):
    # Validate key format
    IF provider == "openai" AND NOT plaintext_key.startswith("sk-"):
        RAISE ValidationError("OpenAI keys start with 'sk-'")

    encrypted = encrypt_api_key(plaintext_key)
    prefix = plaintext_key[:10] + "..."

    existing = db.query(UserAIKey).filter(user_uid=user.uid, provider=provider).first()
    IF existing:
        existing.encrypted_key = encrypted
        existing.key_prefix = prefix
    ELSE:
        key = UserAIKey(user_uid=user.uid, provider=provider,
                        encrypted_key=encrypted, key_prefix=prefix)
        db.add(key)

FUNCTION get_ai_key(db, user_uid, provider=None):
    query = db.query(UserAIKey).filter(user_uid=user_uid)
    IF provider:
        query = query.filter(provider=provider)
    key = query.first()
    IF NOT key: RETURN None
    key.last_used_at = utcnow()
    RETURN key
```

---

### 7.4 Audit

#### modules/audit/recorder.py
```
# Subscribe to all events at module startup
subscribe('fact.created', record_fact_event)
subscribe('fact.published', record_fact_event)
subscribe('fact.retired', record_fact_event)
subscribe('fact.moved', record_move_event)
subscribe('version.approved', record_version_event)
subscribe('version.rejected', record_version_event)
subscribe('signature.created', record_signature_event)
subscribe('node.created', record_node_event)
subscribe('node.moved', record_node_event)

FUNCTION record_fact_event(payload):
    # Compute reverse_payload from CURRENT state (before this event applied)
    reverse = compute_reverse(payload)
    
    event = EventLog(
        entity_type='fact',
        entity_uid=payload.fact_uid,
        event_type=payload.event_type,
        payload=payload,
        actor_uid=payload.actor_uid,
        reversible=reverse is not None,
        reverse_payload=reverse,
    )
    db.add(event)

FUNCTION compute_reverse(payload):
    IF payload.event_type == 'fact.retired':
        RETURN {"action": "unretire", "fact_uid": payload.fact_uid}
    IF payload.event_type == 'fact.moved':
        RETURN {"action": "move", "fact_uid": payload.fact_uid,
                "target_node_uid": payload.old_node_uid}
    IF payload.event_type == 'version.rejected':
        RETURN {"action": "unreject", "version_uid": payload.version_uid,
                "restore_state": "proposed"}
    # Published and signed are NOT reversible
    RETURN None
```

#### modules/audit/undo_engine.py
```
FUNCTION undo_event(db, event_uid, actor):
    event = db.get(EventLog, event_uid)
    IF NOT event: RAISE NotFound
    IF NOT event.reversible: RAISE Conflict("This action is not reversible")
    IF event.actor_uid != actor.uid AND actor.global_role != 'admin':
        RAISE Forbidden("Can only undo your own actions")

    # Check CURRENT permission — not the permission at event time
    entity = resolve_entity(db, event)
    IF NOT can(actor, 'approve', entity.node_uid):
        RAISE Forbidden("You no longer have permission on this entity")

    # Check collision — entity must still be in expected state
    check_collision(db, event)

    # Execute the reverse through the owning module (NOT raw SQL)
    reverse = event.reverse_payload
    IF reverse.action == "unretire":
        fact_service.unretire(db, reverse.fact_uid, actor)
    ELIF reverse.action == "move":
        fact_service.reassign(db, reverse.fact_uid, reverse.target_node_uid, actor)
    ELIF reverse.action == "unreject":
        version = db.get(FactVersion, reverse.version_uid)
        state_machine.transition(db, version, reverse.restore_state, actor)

    # Mark event as undone
    event.state = 'undone'
    event.undone_at = utcnow()
```

---

### 7.5 Queue

#### modules/queue/scope_resolver.py
```
FUNCTION get_approvable_nodes(db, user):
    # Cached per-request via functools.lru_cache or request-scoped dict
    IF user.global_role == 'admin':
        RETURN {n.uid: 'admin' FOR n IN db.query(Node).all()}

    grants = get_user_grants(user.uid)
    result = {}
    FOR node_uid, role IN grants.items():
        IF role_gte(role, 'subapprover'):
            descendants = get_descendants(db, node_uid)
            FOR desc IN descendants:
                IF desc NOT IN result OR role_gte(role, result[desc]):
                    result[desc] = role
    RETURN result
```

#### modules/queue/service.py
```
FUNCTION approve_proposal(db, version_uid, actor):
    version = db.get(FactVersion, version_uid)
    IF NOT version: RAISE NotFound
    IF version.state != 'proposed': RAISE Conflict("Not a pending proposal")

    fact = db.get(Fact, version.fact_uid)
    approvable = get_approvable_nodes(db, actor)
    IF fact.node_uid NOT IN approvable:
        RAISE Forbidden("This fact is outside your approval scope")

    async with db.begin():
        state_machine.transition(db, version, 'published', actor)
        fact.current_published_version_uid = version.uid

    await publish('version.approved', {version_uid, fact_uid, actor_uid})
    invalidate_badge_cache(actor.uid)

FUNCTION reject_proposal(db, version_uid, actor, note=None):
    version = db.get(FactVersion, version_uid)
    IF NOT version: RAISE NotFound
    IF version.state != 'proposed': RAISE Conflict("Not a pending proposal")

    fact = db.get(Fact, version.fact_uid)
    approvable = get_approvable_nodes(db, actor)
    IF fact.node_uid NOT IN approvable:
        RAISE Forbidden("This fact is outside your approval scope")  # Fixes v1 Q-SEC-01

    async with db.begin():
        state_machine.transition(db, version, 'rejected', actor)

    await publish('version.rejected', {version_uid, fact_uid, actor_uid, note})
    invalidate_badge_cache(actor.uid)
```

---

### 7.6 Signing

#### modules/signing/batch_signer.py
```
FUNCTION sign_node(db, node_uid, actor, note=None, expires_at=None):
    IF NOT can(actor, 'sign', node_uid):
        RAISE Forbidden("No signatory permission on this node")

    descendants = get_descendants(db, node_uid)

    async with db.begin():
        # One query to get all publishable versions
        versions = db.query(FactVersion).join(Fact).filter(
            Fact.node_uid.in_(descendants),
            Fact.is_retired == False,
            FactVersion.version_uid == Fact.current_published_version_uid,
            FactVersion.state == 'published',
        ).all()

        IF NOT versions:
            RAISE Conflict("No published facts to sign")

        version_uids = [v.uid FOR v IN versions]

        # One batch UPDATE for versions
        db.execute(
            UPDATE FactVersion SET state='signed', signed_at=utcnow()
            WHERE version_uid IN version_uids
        )

        # One batch UPDATE for facts
        FOR v IN versions:
            db.execute(
                UPDATE Fact SET current_signed_version_uid = v.uid
                WHERE fact_uid = v.fact_uid
            )

        # Create signature record
        sig = Signature(
            node_uid=node_uid, signed_by_uid=actor.uid,
            fact_count=len(versions), note=note, expires_at=expires_at
        )
        db.add(sig)

    await publish('signature.created', {node_uid, actor_uid, fact_count: len(versions)})
    RETURN sig
```

---

### 7.7 Import Pipeline

#### modules/import_pipeline/upload_handler.py
```
FUNCTION handle_upload(db, file, program_node_uid, effective_date, actor):
    IF NOT can(actor, 'contribute', program_node_uid):
        RAISE Forbidden

    IF file.size > MAX_FILE_SIZE:
        RAISE ValidationError(f"File too large (max {MAX_FILE_SIZE} bytes)")

    ext = file.filename.rsplit('.', 1)[-1].lower()
    IF ext NOT IN ('docx', 'pptx', 'pdf', 'txt', 'md'):
        RAISE ValidationError("Unsupported file type")

    content = await file.read()
    file_hash = sha256(content)

    # Check for duplicate upload
    existing = db.query(ImportSession).filter(source_hash=file_hash, status='proposed').first()
    IF existing:
        RAISE Conflict("This file was already uploaded and is pending review")

    # Upload to S3
    s3_key = f"imports/{actor.uid}/{file_hash}/{file.filename}"
    await s3.put_object(s3_key, content)

    session = ImportSession(
        program_node_uid=program_node_uid,
        source_filename=file.filename,
        source_hash=file_hash,
        source_s3_key=s3_key,
        effective_date=effective_date,
        created_by_uid=actor.uid,
    )
    db.add(session)
    RETURN session
```

#### modules/import_pipeline/analyzer.py
```
@celery_task
FUNCTION analyze_document(session_uid):
    session = db.get(ImportSession, session_uid)
    session.status = 'analyzing'
    db.commit()

    TRY:
        # Download from S3
        content = await s3.get_object(session.source_s3_key)

        # Extract text using appropriate extractor
        extractor = get_extractor(session.source_filename)
        text = extractor.extract(content)

        publish_progress(session_uid, "Extracted text", 10)

        # Chunk text
        chunks = chunk_text(text, max_chars=3000)
        publish_progress(session_uid, f"Split into {len(chunks)} chunks", 20)

        # AI extraction — calls kernel/ai/provider.py (NOT direct curl)
        user = db.get(User, session.created_by_uid)
        ai = AIProvider()
        all_facts = []

        FOR i, chunk IN enumerate(chunks):
            response = await ai.complete(user, [
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": chunk},
            ], response_format="json_object", timeout=120)

            facts = parse_extracted_facts(response)
            all_facts.extend(facts)
            pct = 20 + (60 * (i + 1) / len(chunks))
            publish_progress(session_uid, f"Extracted from chunk {i+1}/{len(chunks)}", pct)

        # Deduplicate against existing corpus
        existing = get_existing_facts(db, session.program_node_uid)
        deduped = deduplicate(all_facts, existing)
        publish_progress(session_uid, f"{len(deduped)} unique facts found", 90)

        # Stage to S3
        staged_key = f"imports/{session_uid}/staged.json"
        await s3.put_object(staged_key, json.dumps(deduped))

        session.staged_facts_s3 = staged_key
        session.status = 'staged'
        publish_progress(session_uid, "Ready for review", 100)

    EXCEPT Exception as e:
        session.status = 'failed'
        session.error_message = str(e)
        publish_progress(session_uid, f"Failed: {e}", -1)

    db.commit()
```

#### modules/import_pipeline/deduplicator.py
```
FUNCTION tokenize(text):
    RETURN set(text.lower().split())

FUNCTION jaccard(set_a, set_b):
    IF NOT set_a OR NOT set_b: RETURN 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    RETURN intersection / union

FUNCTION deduplicate(new_facts, existing_facts, threshold=0.85):
    existing_tokens = [(f, tokenize(f.sentence)) FOR f IN existing_facts]
    results = []

    FOR new IN new_facts:
        new_tokens = tokenize(new.sentence)
        is_dup = False
        FOR existing, ex_tokens IN existing_tokens:
            IF jaccard(new_tokens, ex_tokens) >= threshold:
                new.duplicate_of = existing.uid
                new.similarity = jaccard(new_tokens, ex_tokens)
                is_dup = True
                BREAK
        results.append(new)

    RETURN results
```

---

### 7.8 Export

#### modules/export/factsheet.py
```
FUNCTION export_facts(db, format, node_uids, state_filter, actor):
    IF NOT any(can(actor, 'read', uid) FOR uid IN node_uids):
        RAISE Forbidden

    facts = db.query(FactVersion).join(Fact).filter(
        Fact.node_uid.in_(expand_nodes(db, node_uids)),
        Fact.is_retired == False,
        FactVersion.state.in_(state_filter),
        FactVersion.version_uid == Fact.current_published_version_uid,
    ).all()

    IF format == 'json':
        RETURN StreamingResponse(stream_json(facts))
    ELIF format == 'ndjson':
        RETURN StreamingResponse(stream_ndjson(facts))
    ELIF format == 'csv':
        RETURN StreamingResponse(stream_csv(facts))
    ELIF format == 'txt':
        RETURN StreamingResponse(stream_txt(facts))
```

#### modules/export/docgen/orchestrator.py
```
@celery_task
FUNCTION generate_document(session_uid, node_uids, template_name, actor_uid):
    sections = TEMPLATE_SECTIONS[template_name]  # e.g., 8 SEP sections
    user = db.get(User, actor_uid)
    ai = AIProvider()

    all_facts = load_facts_for_nodes(db, node_uids)
    used_uids = set()
    section_outputs = {}

    # TWO-PASS: score all sections simultaneously, then assign
    affinity_scores = {}
    FOR section IN sections:
        scores = await prefilter(ai, user, all_facts, section)
        affinity_scores[section.key] = scores

    assignments = assign_facts_to_sections(affinity_scores)  # Global optimization

    FOR i, section IN enumerate(sections):
        assigned_facts = assignments[section.key]
        publish_progress(session_uid, f"Writing {section.title}", (i / len(sections)) * 100)

        text = await synthesize(ai, user, assigned_facts, section.prompt)
        section_outputs[section.key] = text

    # Build DOCX
    docx_bytes = build_docx(section_outputs, template_name)

    # Upload to S3 with signed URL
    s3_key = f"exports/{actor_uid}/{session_uid}.docx"
    await s3.put_object(s3_key, docx_bytes)

    download_url = s3.generate_presigned_url(s3_key, expires_in=3600)
    publish_progress(session_uid, "Document ready", 100, download_url=download_url)
```

---

### 7.9 AI Chat

#### modules/ai_chat/prompt_builder.py
```
FUNCTION build_system_prompt(facts, max_tokens=6000):
    header = SYSTEM_INSTRUCTIONS           # immutable rules, ~500 tokens
    token_budget = max_tokens - count_tokens(header) - 200

    included = []
    used_tokens = 0
    FOR fact IN facts:
        fact_line = f"- {fact.sentence}"
        tokens = count_tokens(fact_line)
        IF used_tokens + tokens > token_budget:
            BREAK
        included.append(fact_line)
        used_tokens += tokens

    prompt = header + "\n\nFACTS (" + str(len(included)) + " loaded):\n" + "\n".join(included)
    RETURN prompt, len(included), len(facts)    # loaded, total
```

#### modules/ai_chat/safety/input_filter.py
```
FUNCTION check_input(text):
    # Normalize Unicode (NFKC + confusable mapping)
    normalized = unicodedata.normalize('NFKC', text)
    normalized = map_confusables(normalized)       # Cyrillic а → Latin a, etc.

    flags = []
    FOR pattern IN INJECTION_PATTERNS:
        IF pattern.search(normalized):
            flags.append(pattern.name)

    RETURN InputCheckResult(
        clean=len(flags) == 0,
        flags=flags,
        normalized=normalized,
    )
    # NOTE: flags but does NOT block — Layer 2 (system prompt) handles defense
```

#### modules/ai_chat/context_provider.py
```
FUNCTION get_available_context(db, user):
    # Only return nodes the user can read — fixes v1 A-SEC-03
    all_nodes = get_full_tree(db)
    readable = []
    FOR node IN all_nodes:
        IF can(user, 'read', node.uid):
            readable.append(node)
    
    # Group into programs (trunks) and topics (branches)
    programs = [n FOR n IN readable IF n.node_depth == 0]
    topics = {p.uid: [n FOR n IN readable IF is_descendant(n, p)] FOR p IN programs}
    
    RETURN {"programs": programs, "topics": topics}
```

---

### 7.10 Search

#### modules/search/service.py
```
FUNCTION search_facts(db, query, limit=50):
    tree = get_cached_tree(db)

    results = db.execute(
        SELECT FactVersion.*, Fact.node_uid,
               ts_rank(search_vector, plainto_tsquery(query)) AS rank
        FROM fc_fact_version
        JOIN fc_fact ON fc_fact.fact_uid = fc_fact_version.fact_uid
        WHERE search_vector @@ plainto_tsquery(query)
          AND fc_fact.is_retired = False
          AND fc_fact_version.state IN ('published', 'signed')
        ORDER BY rank DESC
        LIMIT limit
    )

    FOR result IN results:
        result.breadcrumb = build_breadcrumb_from_tree(tree, result.node_uid)

    RETURN results
```

---

### 7.11 Feedback

#### modules/feedback/service.py
```
FUNCTION submit_feedback(db, name, body, category, ip_address):
    ip_hash = sha256(ip_address + FEEDBACK_SALT)

    check_rate(ip_hash, 'feedback')   # 1 per minute per IP

    IF NOT name: name = generate_random_name()    # "Grumpy Iguana" style
    IF category NOT IN get_categories(): category = 'other'

    feedback = Feedback(
        display_name=name, body=body, category=category,
        source='web', ip_hash=ip_hash
    )
    db.add(feedback)
    RETURN feedback
```

---

### 7.12 Presentation

#### modules/presentation/slide_data.py
```
FUNCTION get_slides():
    RETURN [
        Slide(id=1, title="artiFACT", type="title_card", beats=[
            Beat(text="Welcome to artiFACT", audio="1-1.mp3", sfx="0.mp3"),
            Beat(text="The atomic fact corpus", audio="1-2.mp3"),
        ]),
        Slide(id=2, title="The Problem", type="content", beats=[
            Beat(text="71 engineering artifacts", audio="2-1.mp3"),
            Beat(text="30% duplicative content", audio="2-2.mp3", hotspots=[...]),
        ]),
        # ... slides 3-6
    ]

FUNCTION get_dynamic_stats(db):
    RETURN {
        "user_count": db.query(func.count(User.uid)).scalar(),
        "fact_count": db.query(func.count(Fact.uid)).filter(is_retired=False).scalar(),
        "node_count": db.query(func.count(Node.uid)).scalar(),
    }
```

---

### 7.13 Admin

#### modules/admin/dashboard.py
```
FUNCTION get_dashboard(db):
    RETURN {
        "users": {
            "total": count(User),
            "active_24h": count(User WHERE last_login_at > now() - 24h),
            "by_role": group_count(User, 'global_role'),
        },
        "facts": {
            "total": count(Fact WHERE NOT is_retired),
            "by_state": group_count(FactVersion, 'state'),
            "created_7d": count(Fact WHERE created_at > now() - 7d),
        },
        "queue": {
            "pending_proposals": count(FactVersion WHERE state='proposed'),
            "pending_moves": count(EventLog WHERE event_type='move_proposed'),
        },
        "system": {
            "version": get_app_version(),
            "deploy_sha": get_deploy_sha(),
            "uptime": get_uptime(),
            "db_size": get_db_size(),
        },
    }
```

#### modules/admin/snapshot_manager.py
```
@celery_task
FUNCTION trigger_snapshot(actor_uid):
    timestamp = utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f"snapshots/artifact_{timestamp}.dump"

    # Run pg_dump
    result = subprocess.run([
        'pg_dump', '--no-owner', '--no-acl', '-Fc',
        DATABASE_URL
    ], capture_output=True)

    IF result.returncode != 0:
        RAISE RuntimeError(f"pg_dump failed: {result.stderr}")

    # Upload to S3
    await s3.put_object(filename, result.stdout)

    # Record in event log
    await publish('admin.snapshot', {filename, actor_uid, size: len(result.stdout)})

    RETURN {"filename": filename, "size": len(result.stdout)}
```

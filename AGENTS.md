# AGENTS.md

Primary source of truth for AI-agent behavior in projects scaffolded by `django-mindoff`.

## S1. Goal

Build correct, maintainable features with minimal token usage by reusing Mindoff framework tools and documented patterns.

## S2. Read Order (Token Efficient)

1. Read project `AGENTS.md` first.
2. Open only the required files under `docs/`.
3. Validate behavior from code before implementing.

Do not scan the entire `docs/` tree when one focused page is enough.

## S3. Source of Truth

- Runtime behavior: repository code.
- Agent rules: project `AGENTS.md`.
- Framework usage guidance: project `docs/`.

If code and docs conflict, ask the user which to follow, then update the other side in the same task.

## S4. Docs Source (Mandatory)

`django-mindoff` documentation is available only inside the installed package:

`.../site-packages/django_mindoff/docs/` (venv or global Python install).

To locate docs, resolve `django_mindoff.__file__` and navigate to its sibling `docs/` folder.

If installed docs are unavailable, rely on project `AGENTS.md` and local code, and ask the user before assuming undocumented behavior.

## S4.1 Docs Topic Map (Use Only What You Need)

Prefer these pages based on task type:

- API implementation: `docs/architecture/api-kit.md`, `docs/developer_guide/api-development.md`
- CRUD/data flow: `docs/architecture/crud-kit.md`, `docs/developer_guide/data-operations-crud.md`
- Polars usage: `docs/architecture/polars-kit.md`, `docs/developer_guide/polars-utilities.md`
- Validation: `docs/architecture/validation-kit.md`, `docs/developer_guide/validations.md`
- Responses: `docs/architecture/response-kit.md`, `docs/developer_guide/responses.md`
- Queue workflows: `docs/developer_guide/queued-api-processing.md`
- Testing: `docs/architecture/tdd-kit.md`, `docs/developer_guide/test-driven-development.md`
- CLI/scaffolding: `docs/architecture/management-kit.md`
- Contribution/commit rules: `docs/community/contribution-guide.md`

## S4.2 Expected Project Structure (Keep Aligned)

Agents must keep generated and edited code aligned with Mindoff project structure:

- `apps/<app_name>/apis/`
- `apps/<app_name>/components/`
- `apps/<app_name>/tests/`
- `apps/<app_name>/models.py`
- `apps/<app_name>/urls.py`
- `config/settings.py`
- `config/urls.py`
- `config/responses.csv` (response code registry)
- `pytest.ini` (root-level test runner configuration)
- `mindoff.py` (manager command entrypoint)

Do not manually invent alternative structure for scaffolded components unless the user explicitly requests a custom layout.

## S5. Framework-First Implementation Rules

- Prefer Mindoff kits over custom plumbing.
- Keep request handlers thin; place reusable logic in components/services.
- Use `MindoffAPIMixin` for API classes unless explicitly asked otherwise.
- Use `mo_validation_kit` for validation flows.
- Use `mo_response_kit` for consistent response format.
- Use `mo_crud_kit` + `mo_polars_kit` for bulk/tabular data work.
- Preserve backward compatibility unless explicitly asked for breaking changes.

## S5.1 Manager Commands for Scaffolding (Mandatory)

For scaffolding tasks, agents must use manager commands with explicit arguments instead of creating/editing scaffold files manually.

Do not use interactive `create` or `delete` flows for agent automation. Use the direct commands below:

- Create app(s):
  `python mindoff.py createapp <app_name> [<app_name_2> ...]`
- Create API:
  `python mindoff.py createapi <app_name>/<api_name> [--url <path_1> <path_2> ...]`
- Create model:
  `python mindoff.py createmodel <app_name>/<ModelName>`
- Create foreign key field (model field):
  `python mindoff.py create_model_field <app_name>/<ModelName> <field_name> --to <parent_app>/<ParentModel>`
- Delete app(s):
  `python mindoff.py deleteapp <app_name> [<app_name_2> ...]`

AI agents must not use `django-mindoff` CLI commands. Use `python mindoff.py ...` manager commands only.

Why mandatory:

- These commands enforce Mindoff scaffolding contracts and route/settings wiring.
- Manual file creation can misalign with framework-generated structure.
- Use manual edits only when the user explicitly asks for a custom/non-standard layout.

Post-scaffold required steps:

- After `createmodel` and `create_model_field`, run:
  `python manage.py makemigrations`
  `python manage.py migrate`

## S6. Data and Polars Rules

- Use vectorized operations; avoid Python row loops for bulk transforms.
- Prefer lazy/streaming strategy for large datasets.
- Use model-frame mapping when bulk model operations are required:
  `{ModelClass: pl.DataFrame | pl.LazyFrame}`

## S7. Testing Rules

- Add/update focused tests when behavior changes.
- Prefer Mindoff test helpers from `tdd_kit`.
- Keep fixtures small and deterministic.
- Run targeted tests first.
- Follow testing rules from:
  - `docs/architecture/tdd-kit.md`
  - `docs/developer_guide/test-driven-development.md`
- These testing rules are mandatory for AI-generated test changes.

## S7.1 API Security Baseline

- Production APIs must explicitly define `authentication_classes`.
- Production APIs must explicitly define `permission_classes`.
- Do not rely on implicit/default auth or permissions for protected endpoints.

## S7.2 Queue Mode Preconditions

If API uses `process_mode = "queue"`:

- Ensure `REDIS_URL` is configured.
- Ensure queue worker process is running before validating queue flows.
- Add or update tests for queue-mode behavior (enqueue/status/retry/cancel as relevant).

## S8. Git Commit Standard

Source: `docs/community/contribution-guide.md`.

Use:

`:<gitmoji_code>: <Verb> <short action-oriented description>`

Example:

`:sparkles: Add bulk update validation`

## S9. Documentation Duty

When behavior, architecture, conventions, or scaffolding changes:

1. Update the related docs in the same task.
2. Remove stale/duplicate guidance.
3. Keep references to canonical files.
4. Keep this `AGENTS.md` updated when project-wide agent rules or workflow expectations change.

## S10. Practical Outcome

Prioritize clarity, correctness, and maintainability while minimizing token and implementation overhead.

## S11. Definition of Done

Before closing a task, ensure:

1. Targeted tests for changed behavior pass.
2. Relevant documentation is updated (`AGENTS.md`, related project docs, and docs pages if behavior changed).
3. Commit message follows the Git commit standard in this file.

# AGENTS.md

Source of truth for AI-agent behavior in this project.

## S1. Project Purpose

Demonstrate `django-mindoff` features and prove its superiority through benchmark comparisons:
- **DRF serializer `many=True` workflows** vs **django-mindoff** native methods (`mo_crud_kit`, `mo_polars_kit`, etc.)
- Each benchmark must measure and log execution time, memory, and query count for both approaches.

## S2. Read Order (Token Efficient)

1. Read this `AGENTS.md` first.
2. Open only the required doc page from S4.1.
3. Validate behavior from code before implementing.

## S3. Source of Truth

- Runtime behavior: repository code.
- Agent rules: this `AGENTS.md`.
- Framework usage guidance: installed package `docs/`.

If code and docs conflict, ask the user which to follow, then update the other side in the same task.

## S4. Docs Source (Mandatory)

`django-mindoff` docs live only inside the installed package:
`.../site-packages/django_mindoff/docs/`

Resolve `django_mindoff.__file__` to locate the sibling `docs/` folder. If installed docs are unavailable, rely on this file and local code — ask before assuming undocumented behavior.

## S4.1 Docs Topic Map (Use Only What You Need)

| Task | Doc page |
|---|---|
| API | `docs/architecture/api-kit.md`, `docs/developer_guide/api-development.md` |
| CRUD / data | `docs/architecture/crud-kit.md`, `docs/developer_guide/data-operations-crud.md` |
| Polars | `docs/architecture/polars-kit.md`, `docs/developer_guide/polars-utilities.md` |
| Validation | `docs/architecture/validation-kit.md`, `docs/developer_guide/validations.md` |
| Responses | `docs/architecture/response-kit.md`, `docs/developer_guide/responses.md` |
| Queue | `docs/developer_guide/queued-api-processing.md` |
| Testing | `docs/architecture/tdd-kit.md`, `docs/developer_guide/test-driven-development.md` |
| Scaffolding | `docs/architecture/management-kit.md` |
| Commits | `docs/community/contribution-guide.md` |

## S4.2 Expected Project Structure (Keep Aligned)

```
apps/<app_name>/apis/
apps/<app_name>/components/
apps/<app_name>/tests/
apps/<app_name>/models.py
apps/<app_name>/urls.py
config/settings.py
config/urls.py
config/responses.csv
pytest.ini
mindoff.py
```

Do not invent alternative structure unless the user explicitly requests it.

## S5. Framework-First Implementation Rules

- Prefer Mindoff kits over custom plumbing.
- Keep handlers thin; place reusable logic in components/services.
- Use `MindoffAPIMixin`, `mo_validation_kit`, `mo_response_kit`.
- Use `mo_crud_kit` + `mo_polars_kit` for bulk/tabular data — vectorized, no Python row loops.

## S5.1 Manager Commands for Scaffolding (Mandatory)

Use `python mindoff.py` manager commands — never create scaffold files manually.

```
python mindoff.py createapp <app_name>
python mindoff.py createapi <app_name>/<api_name> [--url <path>]
python mindoff.py createmodel <app_name>/<ModelName>
python mindoff.py create_model_field <app_name>/<ModelName> <field_name> --to <parent_app>/<ParentModel>
python mindoff.py deleteapp <app_name>
```

After `createmodel` / `create_model_field`:
```
python manage.py makemigrations && python manage.py migrate
```

## S6. Benchmark Rules

Every benchmark must:
1. Implement **both** approaches (standard Django and django-mindoff) in the same file.
2. Measure clean wall time separately from memory and query-count passes.
3. Use RSS / peak-RSS memory measurement so native Polars/Arrow allocations are counted.
4. Run at least 5 measured iterations after a warmup and report median time.
5. Keep headline charts focused on common API workflows: DRF serializer `many=True` create/read/update vs django-mindoff create/read/update.
6. Return or log a comparison dict including `{approach, time_ms, memory_mb, query_count}` plus benchmark context.
7. Treat `query_count` as diagnostic only; Mindoff write paths may bypass Django cursor capture.
8. Include a focused test asserting the mindoff approach is faster or equal for an appropriate baseline/scale.

## S7. Testing Rules

- Use `tdd_kit` helpers; keep fixtures small and deterministic.
- Run targeted tests first.
- Follow rules in `docs/architecture/tdd-kit.md` and `docs/developer_guide/test-driven-development.md`.

## S7.1 API Security Baseline

- Production APIs must explicitly define `authentication_classes` and `permission_classes`.
- Do not rely on implicit/default auth for protected endpoints.

## S7.2 Queue Mode Preconditions

If API uses `process_mode = "queue"`: ensure `REDIS_URL` is configured and a queue worker is running before validating queue flows.

## S8. Git Commit Standard

Source: `docs/community/contribution-guide.md`.

`:<gitmoji_code>: <Verb> <short description>`

Example: `:sparkles: Add bulk update benchmark`

## S9. Documentation Duty

When behavior, architecture, or scaffolding changes:
1. Update related docs in the same task.
2. Remove stale/duplicate guidance.
3. Keep this `AGENTS.md` updated when project-wide rules change.

## S10. Definition of Done

1. Targeted tests pass.
2. Benchmark comparison result is logged/returned.
3. Relevant docs updated (`AGENTS.md` if rules change).
4. Commit follows S8 standard.

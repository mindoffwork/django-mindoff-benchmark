<!--
Title format (checked by CI): {emoji} {Capitalised verb phrase}
  Good:  ✨ Add bulk update benchmark lane
  Bad:   :sparkles: Added bulk update benchmark lane.
Use the raw emoji in the title; use :gitmoji: codes in commit messages.

Add exactly ONE label: feature | bug | enhancement | documentation | internal
-->

## Summary

<!-- What changed, in a sentence or two. -->

## Motivation / context

<!-- Why this change? Link any related issue/discussion. -->

## Testing

<!-- How you verified it. Include commands. -->

```bash
pytest
```

## Risks / migrations

<!-- Breaking changes, data migrations, or "none". -->

## Checklist

- [ ] One label applied (`feature` / `bug` / `enhancement` / `documentation` / `internal`)
- [ ] Tests pass locally (`pytest`)
- [ ] Docs updated, or noted here why not
- [ ] If the benchmark or `django-mindoff` pin changed, I refreshed `benchmarks/` and the version note in the README

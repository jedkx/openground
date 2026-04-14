# Contributing

## Branching model (XP-friendly)

- Base integration branch: `development`
- Feature branches: `feature/<short-topic>`
- Bugfix branches: `fix/<short-topic>`
- Hotfix branches (urgent prod patches): `hotfix/<short-topic>`
- Open Pull Requests to `development`

Typical flow:

```bash
git switch development
git pull
git switch -c feature/my-change
```

## Pull request expectations

- Keep PRs small and focused on one behavior change.
- Include tests for behavior changes.
- Update docs when workflow, API shape, or configuration changes.
- Prefer squash merges to keep history easy to scan.

## Merge checklist

Before requesting review:

- [ ] `make verify` passes locally.
- [ ] If telemetry JSON shape or CCSDS packing changed, tests are updated.
- [ ] README/CONTRIBUTING updates are included when process changed.
- [ ] PR description explains why the change exists, not just what changed.

Before merging:

- [ ] CI check `PR Check` is green.
- [ ] At least one reviewer approved.

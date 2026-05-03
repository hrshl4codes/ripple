# Contributing to Ripple

This document covers everything you need to work on Ripple cleanly and consistently.

---

## Branch naming

Every piece of work lives on its own branch. Never commit directly to `main`.

```
feature/   new capability        e.g. feature/thread-generation
fix/       bug correction        e.g. fix/twitter-char-overflow
refactor/  structural change     e.g. refactor/memory-client
docs/      documentation only    e.g. docs/api-endpoints
chore/     tooling or config     e.g. chore/update-dependencies
```

Branch names are lowercase, hyphenated, under 50 characters. Branch from `main`, merge back to `main`.

---

## Commit messages

Ripple follows the [Conventional Commits](https://www.conventionalcommits.org) specification.

**Format:**
```
<type>(<scope>): <short description>

[optional body — explain WHY, not what]

[optional footer — e.g. Closes #12]
```

**Types:**

| Type | When to use |
|---|---|
| feat | new feature or capability |
| fix | bug fix |
| refactor | code restructure, no behaviour change |
| docs | documentation only |
| chore | dependency updates, config, tooling |
| perf | performance improvement |
| test | adding or fixing tests |
| ci | CI/CD changes |

**Rules:**
- Subject line under 50 characters
- Use imperative mood ("add" not "added", "fix" not "fixed")
- No period at the end of the subject
- Body explains the reason for the change, not the mechanics
- Reference issues in the footer: `Closes #12`

**Good examples:**
```
feat(agents): add parallel execution for independent tasks

fix(parser): handle missing platform label in crew output

refactor(memory): extract embedding logic into standalone function

chore: bump crewai to 0.131.0
```

**Breaking changes:**
```
feat(api)!: rename /runs/create to POST /runs

BREAKING CHANGE: clients must update endpoint path
```

---

## Pull requests

Keep PRs under 400 lines changed. Reviewers lose context above that. If a feature is large, split it into sequential PRs.

Every PR description should answer three questions: what changed, why it was needed, and how to verify it works.

Open a draft PR early for complex changes so reviewers can weigh in before you finish.

---

## Code style

Ripple uses Python 3.12. No type: ignore comments without a reason. No bare except clauses. Pydantic models for all data boundaries.

---

## Releases and tagging

Ripple uses semantic versioning: `vMAJOR.MINOR.PATCH`.

```
PATCH   bug fix, no new features
MINOR   new feature, backwards compatible
MAJOR   breaking change
```

Tags are annotated, not lightweight:
```bash
git tag -a v1.0.0 -m "v1.0.0: initial release"
git push origin v1.0.0
```

A GitHub Release is created for every version tag with a changelog describing what changed.

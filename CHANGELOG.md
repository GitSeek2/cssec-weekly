# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-08-09

First formally structured release: aligns the skill with the Anthropic
Agent Skills convention so it loads and runs portably.

### Changed
- Script invocations in `SKILL.md` now use `${CLAUDE_SKILL_DIR}/scripts/...`
  instead of cwd-relative `scripts/...`, so the skill runs from any working
  directory.
- `SKILL.md` frontmatter extended with `license`, `metadata` (version, author),
  and `compatibility` fields, staying within the six portable spec fields.

### Added
- `references/` directory holding the three large reference docs
  (`写作风格.md`, `信息源.md`, `设计规格.md`).
- `CHANGELOG.md` (this file).

### Removed
- The four reference docs (`写作风格.md`, `信息源.md`, `设计规格.md`,
  `CHECKLIST.md`) no longer live at repo root — all moved into `references/`.

### Migration notes
- All cross-references between docs were updated for the new layout.
  External links to the old root paths should be updated to the new
  `references/` locations.
- No script behavior changed; `issues/` is still resolved relative to the
  script location (now `${CLAUDE_SKILL_DIR}/issues/` when invoked via the
  skill loader).

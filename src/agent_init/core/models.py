"""Single set of pydantic models. SQLModel tables are thin persistence shells over them.

Per the plan: one model layer to avoid drift between DB and JSON shapes.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel

# ---------- DB tables ----------

class RegisteredRepo(SQLModel, table=True):
    """A skill source repo registered globally on this machine."""

    alias: str = SQLField(primary_key=True)
    url: str
    default_ref: str = "HEAD"  # branch/tag to track on refresh
    last_fetched_at: datetime | None = None
    last_sha: str | None = None


class SkillIndex(SQLModel, table=True):
    """Discovered skill within a registered repo, used for `skill list/search`."""

    qualified_name: str = SQLField(primary_key=True)  # "<alias>/<skill_name>"
    repo_alias: str = SQLField(index=True)
    skill_name: str = SQLField(index=True)
    source_path: str  # path relative to repo root, e.g. "skills/code-review"
    title: str | None = None
    description: str | None = None
    indexed_at_sha: str
    # Comma-separated lists; SQLite has no array type. Use empty string for none.
    prereqs: str = ""  # qualified_names this skill requires (informational)
    provides: str = ""  # capability tags this skill claims to fulfill


class Template(SQLModel, table=True):
    """A registered AGENTS.md template (built-in default plus user-registered)."""

    name: str = SQLField(primary_key=True)
    source: str  # "builtin", or a path / url for user-registered
    description: str | None = None


class RuleEntry(SQLModel, table=True):
    """User-saved rule snippet. Body lives at user_config_dir/rules/<name>.md."""

    name: str = SQLField(primary_key=True)
    is_default: bool = False
    description: str | None = None


class RegisteredRuleRepo(SQLModel, table=True):
    """A shared rule library overlay — markdown rules cloned from a git repo
    and resolved as a lower-priority source after the local library."""

    alias: str = SQLField(primary_key=True)
    url: str
    default_ref: str = "HEAD"
    last_fetched_at: datetime | None = None
    last_sha: str | None = None


# ---------- Manifest (per-project JSON, committed) ----------

CURRENT_MANIFEST_VERSION = 2  # v2: per-skill `pin` + `track` fields (additive)
HISTORY_CAP = 10


class SkillVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag: str | None = None
    sha: str
    installed_at: datetime

    def identifier(self) -> str:
        """User-facing composite identifier per plan: `<tag>+<short_sha>` or SHA-only."""
        short = self.sha[:7]
        return f"{self.tag}+{short}" if self.tag else short


class InstalledSkill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    qualified_name: str  # "<repo_alias>/<skill_name>" at install time
    repo_alias: str  # the local alias at install time — survives upstream URL/name changes
    repo_url: str
    source_path: str  # path inside the source repo at install time
    target_dir: str  # path inside the project, e.g. ".claude/skills/code-review"
    current: SkillVersion
    history: list[SkillVersion] = Field(default_factory=list)
    content_hash: str | None = None  # sha256 of installed file tree (for drift detection)
    # v2 fields:
    pin: str | None = None  # exact tag — update refuses to advance past this
    track: str | None = None  # "latest-tag" | "<branch>" | "<ref>" — overrides repo.default_ref

    def push_history(self, new_current: SkillVersion) -> None:
        self.history.insert(0, self.current)
        self.current = new_current
        if len(self.history) > HISTORY_CAP:
            del self.history[HISTORY_CAP:]


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_version: int = CURRENT_MANIFEST_VERSION
    template: str = "default"
    skills: list[InstalledSkill] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    managed_files: list[str] = Field(default_factory=lambda: ["AGENTS.md"])
    # Hash of the last-written body of each managed region inside AGENTS.md (and
    # mirrors). Drift means the user edited inside markers — warn before rewrite.
    managed_region_hashes: dict[str, str] = Field(default_factory=dict)
    # Per-project preference for the primary agent dialect ("claude", "gemini",
    # "opencode", or None). Not used for rendering yet — laid down for future
    # per-agent dialect support without another manifest version bump.
    agent_dialect: str | None = None

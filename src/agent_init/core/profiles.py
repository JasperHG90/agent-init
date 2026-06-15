"""Project profiles — named bundles of init settings.

A profile snapshots a project's `(template, mirrors, rules, skills, agent_dialect)`
so you can stamp out new projects from it. Stored as JSON under
`user_config_dir/profiles/<name>.json`. Skills reference upstream by
qualified_name + pin/track, not by frozen bytes — so `init --profile X`
always picks up the latest skill version unless pinned.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from agent_init.core import paths

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class ProfileNameError(ValueError):
    pass


class ProfileNotFoundError(KeyError):
    pass


class ProfileSkill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    qualified_name: str
    pin: str | None = None
    track: str | None = None


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    template: str = "default"
    mirrors: list[str] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    skills: list[ProfileSkill] = Field(default_factory=list)
    agent_dialect: str | None = None


def _profile_path(name: str) -> Path:
    return paths.user_config_dir() / "profiles" / f"{name}.json"


def _validate_name(name: str) -> None:
    if not _NAME_RE.fullmatch(name):
        raise ProfileNameError(
            f"profile name {name!r} invalid: must be lowercase alphanumeric, _, or -"
        )


def save(profile: Profile) -> Path:
    _validate_name(profile.name)
    paths.ensure_global_dirs()
    path = _profile_path(profile.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(profile.model_dump_json(indent=2) + "\n")
    return path


def load(name: str) -> Profile:
    path = _profile_path(name)
    if not path.exists():
        raise ProfileNotFoundError(name)
    return Profile.model_validate(json.loads(path.read_text()))


def list_profiles() -> list[Profile]:
    dir_ = paths.user_config_dir() / "profiles"
    if not dir_.exists():
        return []
    out: list[Profile] = []
    for path in sorted(dir_.glob("*.json")):
        try:
            out.append(Profile.model_validate(json.loads(path.read_text())))
        except Exception:  # pragma: no cover — corrupt file
            continue
    return out


def delete(name: str) -> bool:
    path = _profile_path(name)
    if not path.exists():
        return False
    path.unlink()
    return True


def from_project(name: str, project_root: Path) -> Profile:
    """Build a profile by inspecting a project's manifest."""
    from agent_init.core import manifest

    m = manifest.load(project_root)
    return Profile(
        name=name,
        template=m.template,
        mirrors=[f for f in m.managed_files if f.lower() != "agents.md"],
        rules=list(m.rules),
        skills=[
            ProfileSkill(
                qualified_name=s.qualified_name, pin=s.pin, track=s.track
            )
            for s in m.skills
        ],
        agent_dialect=m.agent_dialect,
    )


@dataclass
class ProfileApplyResult:
    project_root: Path
    init_result: object
    installed_skills: list[str] = field(default_factory=list)
    skipped_skills: list[str] = field(default_factory=list)


def apply(name: str, project_root: Path) -> ProfileApplyResult:
    """Apply a profile to a project: run init, then install each skill."""
    from agent_init.core import init as init_mod
    from agent_init.core import install as install_mod

    profile = load(name)
    init_result = init_mod.run(
        init_mod.InitOptions(
            project_root=project_root,
            template=profile.template,
            mirrors=tuple(profile.mirrors),
            extra_rules=list(profile.rules),
            agent_dialect=profile.agent_dialect,
        )
    )
    installed: list[str] = []
    skipped: list[str] = []
    for ps in profile.skills:
        try:
            install_mod.install(
                project_root, ps.qualified_name, track=ps.track, pin=ps.pin
            )
            installed.append(ps.qualified_name)
        except install_mod.SkillNotIndexedError:
            skipped.append(ps.qualified_name)
    return ProfileApplyResult(
        project_root=project_root,
        init_result=init_result,
        installed_skills=installed,
        skipped_skills=skipped,
    )

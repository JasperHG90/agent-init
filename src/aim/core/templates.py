"""Template registry. Bundled default plus user-registered templates.

Per the plan: pluggable from day one. The `default` template is bundled and
re-seeded into the global SQLite registry on demand. The bundled default is also
copied to the user's global templates directory so it can be edited from the
TUI; `resolve()` prefers that override when it exists.

Users can add their own via `aim template add` (CLI lands in a later
phase if there is a second template; the API is wired up now so it's an
additive change).
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, StrictUndefined
from sqlmodel import select

from aim.core import content_guard, db, paths
from aim.core.models import Template

BUILTIN_DEFAULT = "default"
_BUILTIN_PACKAGE = "aim.templates"


class TemplateNotFoundError(KeyError):
    """Raised when a requested template cannot be located."""


@dataclass(frozen=True)
class ResolvedTemplate:
    """A resolved template name paired with its raw Jinja source body."""

    name: str
    body: str  # raw jinja source


def _builtin_body(template_name: str) -> str:
    """Read the bundled source for a builtin template.

    Args:
        template_name: Name of the builtin template (without extension).

    Returns:
        The raw Jinja source text of the builtin template.

    Raises:
        TemplateNotFoundError: If no bundled resource matches the name.
    """
    resource = files(_BUILTIN_PACKAGE).joinpath(f"{template_name}.md.j2")
    if not resource.is_file():
        raise TemplateNotFoundError(template_name)
    return resource.read_text()


def _builtin_override_path(template_name: str) -> Path:
    """Return the filesystem path of the user-editable copy of a builtin template.

    Args:
        template_name: Name of the builtin template (without extension).

    Returns:
        Path within the global templates library where the override lives.
    """
    paths.ensure_global_dirs()
    return paths.templates_library_dir() / f"{template_name}.md.j2"


def _ensure_builtin_override(template_name: str) -> Path:
    """Copy the bundled template into the global dir if no override exists yet.

    Args:
        template_name: Name of the builtin template (without extension).

    Returns:
        Path to the (possibly newly created) user-editable override.
    """
    override = _builtin_override_path(template_name)
    if not override.exists():
        override.write_text(_builtin_body(template_name), encoding="utf-8")
    return override


def ensure_builtin_registered() -> None:
    """Idempotently register the bundled default template in the global DB."""
    with db.session() as session:
        existing = session.get(Template, BUILTIN_DEFAULT)
        if existing is None:
            session.add(
                Template(
                    name=BUILTIN_DEFAULT,
                    source="builtin",
                    description="Default aim template (managed regions for header + rules).",
                )
            )
            session.commit()
    _ensure_builtin_override(BUILTIN_DEFAULT)


def list_templates() -> list[Template]:
    """Return all registered templates, ensuring the builtin default is present.

    Returns:
        Every template row in the global registry.
    """
    ensure_builtin_registered()
    with db.session() as session:
        return list(session.exec(select(Template)).all())


def resolve(name: str) -> ResolvedTemplate:
    """Resolve a template name to its raw Jinja source body.

    Args:
        name: Registered template name to resolve.

    Returns:
        The resolved template with its source body.

    Raises:
        TemplateNotFoundError: If the name is unregistered or its source file
            is missing.
    """
    ensure_builtin_registered()
    with db.session() as session:
        row = session.get(Template, name)
    if row is None:
        raise TemplateNotFoundError(name)
    if row.source == "builtin":
        # Prefer the user-editable override if it exists.
        override = _builtin_override_path(name)
        if override.is_file():
            body = override.read_text(encoding="utf-8")
            content_guard.assert_no_hidden_unicode(body, source=str(override))
            return ResolvedTemplate(name=name, body=body)
        body = _builtin_body(name)
        content_guard.assert_no_hidden_unicode(body, source=f"builtin template {name}")
        return ResolvedTemplate(name=name, body=body)
    # User-registered template: source is a filesystem path to a .md.j2 file.
    path = Path(row.source)
    if not path.is_file():
        raise TemplateNotFoundError(f"template {name!r} source missing: {path}")
    body = path.read_text()
    content_guard.assert_no_hidden_unicode(body, source=str(path))
    return ResolvedTemplate(name=name, body=body)


def register_user_template(name: str, source_path: Path, description: str | None = None) -> None:
    """Register or update a user template pointing at a filesystem source.

    Args:
        name: Template name to register or update.
        source_path: Path to the `.md.j2` source file backing the template.
        description: Optional human-readable description.

    Raises:
        FileNotFoundError: If `source_path` does not point at a file.
    """
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    with db.session() as session:
        existing = session.get(Template, name)
        if existing is not None:
            existing.source = str(source_path)
            existing.description = description
            session.add(existing)
        else:
            session.add(Template(name=name, source=str(source_path), description=description))
        session.commit()


def render(template_name: str, context: dict) -> str:
    """Render a named template against the given context.

    Args:
        template_name: Registered template name to render.
        context: Mapping of variables exposed to the Jinja template.

    Returns:
        The rendered template output.
    """
    template = resolve(template_name)
    env = Environment(
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
    )
    return env.from_string(template.body).render(**context)

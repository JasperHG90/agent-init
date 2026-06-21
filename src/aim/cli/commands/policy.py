"""`aim policy`: inspect and enforce the governance policy."""

from __future__ import annotations

from pathlib import Path

import typer

from aim.cli._shared import _friendly, _here
from aim.core import declarations as declarations_mod
from aim.core import layout_profiles as layout_profiles_mod
from aim.core import manifest as manifest_mod
from aim.core import policy as policy_mod

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Inspect and enforce the governance policy (blocked repos/artifacts, risk rules).",
)


@app.command("show")
@_friendly
def policy_show(project: Path | None = typer.Argument(None, help="Project root.")) -> None:
    """Print the resolved effective policy."""
    resolved = policy_mod.resolve_effective(_here(project))
    typer.echo(f"# source: {resolved.source}")
    if resolved.repo:
        typer.echo(f"# repo: {resolved.repo}")
    if resolved.hash:
        typer.echo(f"# hash: {resolved.hash}")
    typer.echo(policy_mod.to_toml(resolved.policy))


@app.command("bind")
@_friendly
def policy_bind(
    git_url: str = typer.Argument(..., help="Org policy repo URL (contains policy.toml)."),
    project: Path | None = typer.Argument(None, help="Project root."),
    ref: str = typer.Option("HEAD", "--ref", help="Branch/tag/commit to pin."),
) -> None:
    """Point this project at an org policy repo: set the policy scope to 'org' in its
    aim.toml and warm the local cache (the org policy then governs the project)."""
    root = _here(project)
    resolved = policy_mod.bind(git_url, ref)  # fetch + cache snapshot
    policy_mod.set_project_policy(root, {"scope": "org", "repo": git_url, "ref": ref})
    typer.echo(
        f"bound {root / 'aim.toml'} to org policy {resolved.policy.name!r} ({git_url} @ {ref})"
    )
    typer.echo(f"hash: {resolved.hash}")


@app.command("unbind")
@_friendly
def policy_unbind(project: Path | None = typer.Argument(None, help="Project root.")) -> None:
    """Remove the policy table from the project's aim.toml (back to permissive)."""
    policy_mod.set_project_policy(_here(project), {})
    typer.echo("removed [policy] from aim.toml")


@app.command("refresh")
@_friendly
def policy_refresh(project: Path | None = typer.Argument(None, help="Project root.")) -> None:
    """Re-fetch the project's org policy (scope='org') and update the cached snapshot."""
    resolved = policy_mod.refresh_org_policy(_here(project))
    if resolved is None:
        typer.echo("project has no org policy (scope != 'org'); nothing to refresh")
        return
    typer.echo(f"refreshed org policy {resolved.policy.name!r}; hash: {resolved.hash}")


@app.command("init-local")
@_friendly
def policy_init_local(
    project: Path | None = typer.Argument(None, help="Project root."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing policy."),
) -> None:
    """Scaffold a default local policy (scope='local') in the project's aim.toml."""
    root = _here(project)
    if policy_mod.project_policy_section(root) and not force:
        typer.echo("error: aim.toml already has a [policy]; pass --force to overwrite", err=True)
        raise typer.Exit(code=1)
    policy_mod.set_project_policy(root, {"scope": "local"})
    typer.echo(f"wrote a default [policy] scope='local' to {root / 'aim.toml'}")


@app.command("import")
@_friendly
def policy_import(
    rules_file: Path = typer.Argument(..., help="A toml file of custom [[rule]] entries."),
    project: Path | None = typer.Argument(None, help="Project root."),
) -> None:
    """Merge custom risk rules from a toml file into the project's inline policy."""
    rules = policy_mod.parse_rules_toml(rules_file.read_text(encoding="utf-8"))
    root = _here(project)
    section = dict(policy_mod.project_policy_section(root))
    section.setdefault("scope", "local")
    section["rule"] = [r.model_dump() for r in rules]
    policy_mod.set_project_policy(root, section)
    typer.echo(f"imported {len(rules)} custom rule(s) into aim.toml [policy]")


@app.command("export")
@_friendly
def policy_export(
    rules_file: Path = typer.Argument(Path("rules.toml"), help="Destination file."),
    project: Path | None = typer.Argument(None, help="Project root."),
) -> None:
    """Write the project policy's custom rules out to a shareable toml file."""
    pol = policy_mod.resolve_effective(_here(project)).policy
    rules_file.write_text(policy_mod.render_rules_toml(pol.custom_rules), encoding="utf-8")
    typer.echo(f"exported {len(pol.custom_rules)} custom rule(s) to {rules_file}")


@app.command("validate")
@_friendly
def policy_validate(
    project: Path | None = typer.Argument(None, help="Project root."),
    policy_url: str | None = typer.Option(
        None,
        "--policy",
        help="Validate against this remote policy repo (fetched fresh) instead "
        "of the local/bound policy. This is the out-of-band CI gate.",
    ),
    ref: str = typer.Option("HEAD", "--ref", help="Ref to use with --policy."),
) -> None:
    """Validate a project's declarations + lockfile against a policy.

    Without `--policy`, validates against the effective policy (org snapshot if
    bound, else local). With `--policy <git-url>`, fetches that repo fresh and
    validates against it — the out-of-band CI gate: the expected policy comes from
    a source the developer's local state cannot forge.
    """
    root = _here(project)
    if policy_url is not None:
        pol, _sha = policy_mod.fetch_org_policy(policy_url, ref)
        resolved = policy_mod.ResolvedPolicy(pol, "org", policy_url, policy_mod.compute_hash(pol))
    else:
        resolved = policy_mod.resolve_effective(root)
    pol = resolved.policy

    try:
        decl = declarations_mod.load(root)
    except declarations_mod.DeclarationsNotFoundError:
        typer.echo("no aim.toml found; nothing to validate")
        return

    problems: list[str] = []
    for alias, url in decl.repos.items():
        try:
            policy_mod.assert_repo_allowed(pol, alias, url)
        except policy_mod.PolicyViolationError as exc:
            problems.append(str(exc))
    for kind, items in (("skill", decl.skills), ("agent", decl.agents), ("rule", decl.rules)):
        for item in items:
            try:
                policy_mod.assert_artifact_allowed(pol, kind, item.qualified_name)
            except policy_mod.PolicyViolationError as exc:
                problems.append(str(exc))
    for mcp in decl.mcp_servers:
        try:
            policy_mod.assert_mcp_allowed(pol, mcp.alias, mcp.registry_name)
        except policy_mod.PolicyViolationError as exc:
            problems.append(str(exc))
    effective_profile = decl.layout_profile or layout_profiles_mod.resolve_active(root).name
    try:
        policy_mod.assert_profile_allowed(pol, effective_profile)
    except policy_mod.PolicyViolationError as exc:
        problems.append(str(exc))

    try:
        m = manifest_mod.load(root)
        if (
            m.policy_hash is not None
            and resolved.hash is not None
            and m.policy_hash != resolved.hash
        ):
            problems.append(
                f"lockfile policy hash {m.policy_hash[:12]} does not match the effective "
                f"policy hash {resolved.hash[:12]} (locked under a different policy)"
            )
    except manifest_mod.ManifestNotFoundError:
        pass

    if problems:
        for p in problems:
            typer.echo(f"violation: {p}", err=True)
        raise typer.Exit(code=1)
    n = len(decl.skills) + len(decl.agents) + len(decl.rules) + len(decl.mcp_servers)
    typer.echo(f"policy OK (source: {resolved.source}; {n} artifact(s) checked)")

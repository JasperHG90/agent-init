"""Main menu — landing screen with navigation to other screens.

The TUI is the primary surface: every action you can do via the CLI is
reachable from here without dropping to a shell.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from agent_init import __version__
from agent_init.core import init as init_mod
from agent_init.tui.modals.init_modal import InitConfig, InitModal

_BANNER = (
    "    ▄▀█ █▀▀ █▀▀ █▄░█ ▀█▀ ─ █ █▄░█ █ ▀█▀\n"
    "    █▀█ █▄█ ██▄ █░▀█ ░█░ ─ █ █░▀█ █ ░█░"
)


class MainScreen(Screen[None]):
    BINDINGS = [
        ("i", "open_init", "Init project"),
        ("r", "open_repos", "Repos"),
        ("s", "open_skills", "Skills"),
        ("u", "open_rules", "Rules"),
        ("p", "open_project", "Project"),
        ("c", "open_config", "Config"),
        ("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(_BANNER, id="banner", markup=False),
            Static(
                f"    v{__version__}  ·  scaffold • skills • rules",
                id="banner-sub",
                markup=False,
            ),
            id="banner-box",
        )
        yield Vertical(
            Static(
                "\n"
                "    I   INIT      scaffold AGENTS.md into a project\n"
                "    R   REPOS     registered skill source repositories\n"
                "    S   SKILLS    browse, search, install\n"
                "    U   RULES     global rules library\n"
                "    P   PROJECT   installed skills in the current project\n"
                "    C   CONFIG    roots, rule-repo overlays, profiles\n"
                "    Q   QUIT\n"
                "\n",
                classes="menu-item",
                markup=False,
            ),
            classes="menu",
        )
        yield Static(
            "  I/R/S/U/P/C  navigate    CTRL+P  palette    Q  quit",
            id="hint",
            markup=False,
        )

    def action_open_repos(self) -> None:
        from agent_init.tui.screens.repos_screen import ReposScreen

        self.app.push_screen(ReposScreen())

    def action_open_skills(self) -> None:
        from agent_init.tui.screens.skills_screen import SkillsScreen

        self.app.push_screen(SkillsScreen())

    def action_open_rules(self) -> None:
        from agent_init.tui.screens.rules_screen import RulesScreen

        self.app.push_screen(RulesScreen())

    def action_open_project(self) -> None:
        from agent_init.tui.screens.project_screen import ProjectScreen

        self.app.push_screen(ProjectScreen())

    def action_open_config(self) -> None:
        from agent_init.tui.screens.config_screen import ConfigScreen

        self.app.push_screen(ConfigScreen())

    def action_open_init(self) -> None:
        self.app.push_screen(InitModal(), self._run_init)

    def _run_init(self, config: InitConfig | None) -> None:
        if config is None:
            return
        try:
            result = init_mod.run(
                init_mod.InitOptions(
                    project_root=config.project_root,
                    template=config.template,
                    mirrors=config.mirrors,
                    seed_default_rules=config.seed_default_rules,
                    force=config.force,
                    agent_dialect=config.agent_dialect,
                )
            )
        except Exception as exc:
            self.app.notify(f"init failed: {exc}", severity="error")
            return
        verb = "Refreshed" if result.re_init else "Initialized"
        self.app.notify(f"{verb} {result.agents_md_path}", title="Init complete")
        for warn in result.region_drift_warnings:
            self.app.notify(warn, severity="warning")

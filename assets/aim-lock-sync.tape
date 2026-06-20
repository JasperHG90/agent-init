# aim lock -> aim sync workflow demo for the README.
# Render with: vhs assets/aim-lock-sync.tape
#
# Records against a throwaway copy of this project's aim.toml in /tmp so the real
# repo is never mutated. Before recording, warm the global cache once:
#   rm -rf /tmp/aim-demo && mkdir -p /tmp/aim-demo \
#     && cp aim.toml /tmp/aim-demo/ && (cd /tmp/aim-demo && aim lock && aim sync)
# The Hide block then clears only the temp lockfile + targets, so the shown
# `aim lock`/`aim sync` print their full per-skill output yet apply near-instantly
# from the warm cache (the original gif captured a cold sync that stalled).
#
# `aim lock` still resolves every repo over the network (~15s of spinner). After
# rendering, that dead spinner segment is trimmed out with:
#   ffmpeg -y -i assets/aim-lock-sync.gif -filter_complex \
#     "[0:v]select='lt(t,3.2)+gte(t,17.8)',setpts=N/25/TB,fps=25,split[a][b];\
#      [a]palettegen=stats_mode=full[p];[b][p]paletteuse=dither=sierra2_4a" out.gif
Output assets/aim-lock-sync.gif

Require aim

Set Shell "bash"
Set FontSize 22
Set Width 1150
Set Height 640
Set Padding 20
Set WindowBar Colorful
Set Theme "Catppuccin Mocha"
Set WaitTimeout 60s
Set WaitPattern ">$"

# --- silent setup (Hide): clean minimal prompt + reset temp project state ---
Hide
Type "unset PROMPT_COMMAND" Enter
Type "PS1='\[\e[38;2;137;180;250m\]> \[\e[0m\]'" Enter
Type "cd /tmp/aim-demo && rm -f aim.lock.toml && rm -rf .claude" Enter
Wait
Type "clear" Enter
Wait
Show

# --- the demo ---
Sleep 600ms
Type@70ms "aim lock" Sleep 400ms Enter
Wait
Sleep 1500ms
Type@70ms "aim sync" Sleep 400ms Enter
Wait
Sleep 1200ms
Type@70ms "ls .claude/skills" Sleep 400ms Enter
Wait
Sleep 2500ms

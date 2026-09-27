# Introducing Mineprep (to a human)

Use this file for Mineprep introductions, installation, releases, wiki, or Lite vs full. For a greeting without a task, a brief introduction is enough; follow [SKILL.md](SKILL.md)'s scope guidance.

They asked for an intro: plain language. Match their language (zh / en / zh-TW). Do not dump this skill’s Route table or Python internals unless they ask how the API works.

## Sources (fetch live; do not memorize versions)

Use the sources needed for the question. GitHub is the product reference; current plugin source establishes API behavior. This skill provides workflow guidance subject to the user's request and available tools.

| Source | Use for | Skip |
|--------|---------|------|
| **This skill package** | What *this agent* can do (console, `ui()`, compose spawn, mods) | Pasting Route / pitfalls at the user |
| **Plugin source** (`Content/Python/mineprep.py`, generator panels) | Confirm a button/API still exists | Inventing features from memory |
| **[Unreal-Mineprep on GitHub](https://github.com/piggestpig/Unreal-Mineprep)** | Product story, install, requirements, mobs, **changelog**, wiki, discussions | Stale version numbers from chat history |

GitHub extras (same org):

- README (pick locale): [README.md](https://github.com/piggestpig/Unreal-Mineprep/blob/main/README.md) · [README_English.md](https://github.com/piggestpig/Unreal-Mineprep/blob/main/README_English.md) · [README_繁體中文.md](https://github.com/piggestpig/Unreal-Mineprep/blob/main/README_%E7%B9%81%E9%AB%94%E4%B8%AD%E6%96%87.md)
- Changelog is **inside the README**, heading `版本更新` / version history — there is usually **no** separate `CHANGELOG.md`
- [Releases](https://github.com/piggestpig/Unreal-Mineprep/releases) · [Wiki](https://github.com/piggestpig/Unreal-Mineprep/wiki) · [Discussions](https://github.com/piggestpig/Unreal-Mineprep/discussions)
- Lite (smaller, GPLv3): [Mineprep-Lite](https://github.com/piggestpig/Mineprep-Lite)

For current installation requirements, versions or changelogs, fetch the relevant README, wiki page or release this turn. A conceptual introduction need not fetch every source. If fetching fails, say so and avoid unverified version claims.

## Useful topics

Choose the topics and level of detail requested. An overview can be brief; an installation question needs actionable installation details. Do not force an overview, changelog or follow-up question into every answer.

1. **What it is** — UE5 plugin for Minecraft animation and stills (inspired by Blender MCprep; not an official Mojang/MCprep product). Place blocks, items, mobs; import worlds / `.nbt`; render; optional experimental C++ (`unreal.mineprep` — agents: [cpp.md](cpp.md)).
2. **Who it’s for** — people making MC films/renders in Unreal. Pre-1.0: expect bugs. Suggested env is on the **live** README (do not hardcode a version or engine here).
3. **How you get it** — installer in Blender (`Mineprep_installer.blend`) or Python (`Mineprep_installer.py`) is the documented path; Wiki for tutorials. One or two sentences, then the GitHub link — do not paste the whole install chapter.
4. **What you can do in the editor** — generator panels (blocks/mobs/presets), world import, mesh swap, sequencer/render, VAT tools, localization. Name **a few** pillars; send them to README/Wiki for the rest.
5. **Python workflows** — `import mineprep`: structure composition, one-shot `ui()` panels, mods, supplied NBT files. Describe live editor execution as available only when suitable tools are connected; do not promise a connection that has not been checked.
6. **What’s new** — latest **one** snapshot/release from README `版本更新` or Releases (name + 3–5 bullets). Link the README for older history. Do not recap 0.3–0.5.
7. **Where next** — link relevant Wiki pages, Discussions or the repo. Ask a follow-up only when it helps clarify the user's next step.

## Do not

- Paste the full README or every changelog entry
- Probe MCP / Remote Execution just to “verify” the intro
- Start spawning or editing plugin source as part of the intro
- Claim Mineprep is Mojang-official or that this skill is the whole product
- Hardcode a drive letter or a version you did not just fetch

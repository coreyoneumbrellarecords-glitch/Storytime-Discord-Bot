---
name: Python Discord setup
description: Runtime and library constraints for running the Storytime bot in this workspace.
---

The bot needs the full Python tools module rather than the base Python module so pip can install project dependencies into `.pythonlibs`.

**Why:** The base Python module is externally managed and does not provide a usable pip installation path for workspace packages.

**How to apply:** Keep `discord.py` and `aiohttp` in `requirements.txt`; if dependency installation fails with an immutable-system or missing-pip error, switch the workspace to the full supported Python tools module before retrying.

This project uses the current `discord.py` command context API: `app_commands.allowed_contexts(...)` instead of the removed `dm_permission` argument.

**Why:** Newer `discord.py` releases reject `dm_permission` in `CommandTree.command`.

**How to apply:** Preserve the allowed-context decorator on slash commands when upgrading or adding commands.
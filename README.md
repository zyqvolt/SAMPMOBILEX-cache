# SAMPMOBILEX-cache

Game data files for SAMP Mobile X. The launcher reads `manifest.json` and `client-config.json` from this repo and downloads each game file from the `cache-v1` release.

## Changing game files

**Small files (under 25 MB)** — open the `incoming` folder, Add file → Upload files, and put them under `incoming/` with their game path, e.g. `incoming/SAMP/gta.dat`. Commit. The *Update game cache* action uploads them to the release, updates `manifest.json` and clears `incoming/`.

**Big files** — Releases → cache-v1 → Edit, upload the file named with `__` instead of `/` (e.g. `texdb/gta3.img` → `texdb__gta3.img`), save, then Actions → *Update game cache* → Run workflow with **rescan** ticked.

**Delete a file** — Actions → *Update game cache* → Run workflow, type the game path(s) in **delete** (e.g. `SAMP/gta.dat`).

Players get the change the next time the launcher checks its files.

`client-config.json` (maintenance / update policy) can be edited directly.

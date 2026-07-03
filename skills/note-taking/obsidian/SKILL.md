---
name: obsidian
description: Read, search, create, and edit notes in the Obsidian vault.
platforms: [linux, macos, windows]
---

# Obsidian Vault

Use this skill for filesystem-first Obsidian vault work: reading notes, listing notes, searching note files, creating notes, appending content, and adding wikilinks.

## Vault path

Use a known or resolved vault path before calling file tools.

The documented vault-path convention is the `OBSIDIAN_VAULT_PATH` environment variable, for example from `~/.hermes/.env`. If it is unset, use `~/Documents/Obsidian Vault`.

### Known vaults for this user

- **Work vault** (Hermes VM, ownCloud/rclone sync to laptop): `~/WorkVault` (e.g. `/home/tkachenkoav/WorkVault`)

Always ask which vault to use if the task doesn't make it obvious.

### Naming convention (hard rule)

**All new file and folder names in this vault must be ASCII/English only — no Cyrillic.** Cyrillic in paths breaks Obsidian wiki-links, sorting, and search. This applies to tool/project names, TZ (spec) filenames, and any new folder created inside the vault. Existing Cyrillic-named archival files (already superseded, moved to backup) don't need renaming — the rule is forward-looking for new files. Table/column headers and body prose can stay in Russian; only the filesystem-level names (files, folders) must be Latin.

## Creating a New Vault

To create a new Obsidian vault from scratch:

```bash
mkdir -p /path/to/VaultName/.obsidian
```

Then create a minimal `.obsidian/app.json`:
```json
{}
```

After creation, user must open Obsidian → **Open folder as vault** → select the folder.
The `.obsidian/` directory is what Obsidian recognizes as a vault marker.

File tools do not expand shell variables. Do not pass paths containing `$OBSIDIAN_VAULT_PATH` to `read_file`, `write_file`, `patch`, or `search_files`; resolve the vault path first and pass a concrete absolute path. Vault paths may contain spaces, which is another reason to prefer file tools over shell commands.

If the vault path is unknown, `terminal` is acceptable for resolving `OBSIDIAN_VAULT_PATH` or checking whether the fallback path exists. Once the path is known, switch back to file tools.

## Read a note

Use `read_file` with the resolved absolute path to the note. Prefer this over `cat` because it provides line numbers and pagination.

## List notes

Use `search_files` with `target: "files"` and the resolved vault path. Prefer this over `find` or `ls`.

- To list all markdown notes, use `pattern: "*.md"` under the vault path.
- To list a subfolder, search under that subfolder's absolute path.

## Search

Use `search_files` for both filename and content searches. Prefer this over `grep`, `find`, or `ls`.

- For filenames, use `search_files` with `target: "files"` and a filename `pattern`.
- For note contents, use `search_files` with `target: "content"`, the content regex as `pattern`, and `file_glob: "*.md"` when you want to restrict matches to markdown notes.

## Create a note

Use `write_file` with the resolved absolute path and the full markdown content. Prefer this over shell heredocs or `echo` because it avoids shell quoting issues and returns structured results.

## Append to a note

Prefer a native file-tool workflow when it is not awkward:

- Read the target note with `read_file`.
- Use `patch` for an anchored append when there is stable context, such as adding a section after an existing heading or appending before a known trailing block.
- Use `write_file` when rewriting the whole note is clearer than constructing a fragile patch.

For an anchored append with `patch`, replace the anchor with the anchor plus the new content.

For a simple append with no stable context, `terminal` is acceptable if it is the clearest safe option.

## Targeted edits

Use `patch` for focused note changes when the current content gives you stable context. Prefer this over shell text rewriting.

## Wikilinks

Obsidian links notes with `[[Note Name]]` syntax. When creating notes, use these to link related content.

---

## Contact Tables (WorkVault pattern)

Two flat Markdown table files in `WorkVault/Contacts/`:

- `tutu-contacts.md` — сотрудники домена tutu.ru (1 строка = 1 человек)
- `external-contacts.md` — внешние контакты

### tutu-contacts columns
`login | ФИО | aliases | telegram | email | подразделение | команда | должность`

### external-contacts columns
`ФИО | aliases | telegram | email | компания | заметки`

### Name resolution (aliases)
The `aliases` field is a comma-separated list of every variant the person may be referred to: short name, full name, login, nickname, document pseudonym (e.g. "Саша Т., Ткаченко, Александр, tkachenkoav").

When the user mentions a person by any variant, search the `aliases` column with `search_files` to find the matching row before acting on the contact.

### Adding a contact
Use `patch` to append a new `|`-delimited row to the table. Do not rewrite the whole file unless the table structure changes.

### User (tkachenkoav) aliases
`Саша Ткаченко, Саша Т., Ткаченко, Александр, tkachenkoav`

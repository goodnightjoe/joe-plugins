# joe-plugins

My curated Claude plugin marketplace. Each plugin is mirrored from its author's GitHub repo once a day by a GitHub Action, so Claude Desktop always sees the latest version.

| Plugin | From | Licence |
| --- | --- | --- |
| impeccable | [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | Apache-2.0 |
| emil-design-eng | [emilkowalski/skills](https://github.com/emilkowalski/skills) | MIT |
| shadcn | [shadcn-ui/ui](https://github.com/shadcn-ui/ui) | MIT |

All credit goes to the original authors. Each plugin folder keeps its author's licence, and `upstream.lock.json` records the exact commit each copy came from.

## Use it in Claude Desktop

1. Open **Customize** in the sidebar, then **Plugins**.
2. Click **Browse plugins**, then the **Personal** tab.
3. Click **+**, then **Add marketplace from GitHub**.
4. Enter `goodnightjoe/joe-plugins` and click **Sync**.
5. Pick the marketplace from the dropdown and install what you want.

## Add or remove a plugin

Edit `sources.json` on GitHub and commit. The Action runs straight away and rebuilds `plugins/` and `.claude-plugin/marketplace.json`. Then click **Update** on the marketplace in Claude Desktop.

- `"mode": "plugin"`: the author already ships a Claude plugin folder; `path` points to it.
- `"mode": "skills"`: the author ships plain skill folders; list them under `skills` and this repo wraps them in a plugin.

## How the sync works

`scripts/sync.py` does a small sparse clone of only the folders it needs from each repo, compares them with what's already here, and only rewrites a plugin when the author has actually changed something. If one source fails, the last good copy stays in place. You can run it by hand from **Actions → Sync community plugins → Run workflow**.

# Unity WebGL Local Translator

English | [简体中文](README.zh-CN.md)

Tools for collecting Unity WebGL resources, translating text, validating repacked asset bundles, and deploying patches through Chrome DevTools Overrides.

Version: 1.0.0. Existing patches can be processed locally. No game resources or font patches are included.

## Requirements

- Python 3.10 or later, available as `python3`
- Chrome or a compatible Chromium browser
- Tampermonkey
- A Responses API-compatible endpoint and an API key for automatic translation

## Installation

1. Extract the project and run `install.bat`. The release includes `local.example.py`; it does not include `local.py`.
2. The installer copies the template to `local.py` only when that file does not exist. Existing configuration is preserved. Dependencies are installed into the project's `python_libs` directory, which Python entry points load automatically.
3. Edit `local.py`. Set `OPENAI_API_KEY` for automatic translation; the default model is `gpt-4.1`. Collection, registration, repacking, and deployment do not require an API key.
4. Generate a local service token:

```bat
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Set the same value in `LOCAL_SERVICE_TOKEN` in `local.py` and `serviceToken` in the userscript.

## Overrides directory

The default directory is `Overrides` beside `local.py`. If the project path is long, use a short absolute path:

```python
OVERRIDES_ROOT = r"G:\Overrides"
```

Select the same directory in DevTools → Sources → Overrides, grant access, and enable **Enable Local Overrides**. Keep DevTools open when loading patches.

Preserve the directory structure corresponding to each request:

```text
Overrides/resource-host/resource-path/full-filename.bundle
```

DevTools may map long paths to `host/longurls/short-filename`. Automatic deployment and registration do not support this mapping. If `longurls` appears, shorten the Overrides root path and use the browser's **Override content** action to check the actual mapping. Do not register a shortened filename as the original bundle name.

## Userscript configuration

Install `Unity_Translation_Toolkit.user.js` and edit its `@match` rule and `GAME_CONFIG`. The default placeholder does not run on real websites.

| Setting | Description |
| --- | --- |
| `@match` | Match rule for the actual game page or iframe |
| `serviceToken` | Same value as `LOCAL_SERVICE_TOKEN` |
| `resourceHosts` | Exact hostnames allowed for collection and cache cleanup, without schemes or paths |
| `catalogURL` | Actual Addressables catalog URL; leave empty to disable catalog modification |
| `catalogIgnoreSearch` | Defaults to `true`: match catalog origin and pathname, allowing dynamic query tokens. Set to `false` for exact query matching |
| `mainPatch.enabled` | Optional main resource font replacement; disabled by default |
| `mainPatch.url` | Full main resource URL to replace, including version query parameters |
| `mainPatch.bytes` | Exact size in bytes of the decompressed local main resource patch |

All addresses below are placeholders:

```javascript
// @match        https://game.example.invalid/*
const GAME_CONFIG = Object.freeze({
  serviceToken: "YOUR_RANDOM_TOKEN",
  resourceHosts: ["cdn.example.invalid"],
  catalogURL: "https://game.example.invalid/app_data/StreamingAssets/aa/catalog.json",
  catalogIgnoreSearch: true,
  mainPatch: { enabled: false, url: "", bytes: 0 }
});
```

Ignoring query parameters applies only to the catalog. Main resource URLs still use exact matching, and bundle cache keys retain query parameters to distinguish resource versions.

When main resource replacement is enabled, select a local patch after each reload. Matching requests wait for file selection. Only decompressed `UnityWebData1.0` files are supported. Patches that depend on external font bundles require those matching bundles as well.

## Initial setup and migration

When switching versions for the first time, verify that original resources load:

1. Keep existing patches in a backup directory outside Overrides.
2. Disable game-related userscripts and DevTools local overrides.
3. If old caches exist, clear Cache Storage and UnityCache for the actual game page. Cookies do not need to be deleted.
4. Start the game once with original resources and confirm that it loads normally.
5. Enable the configured new userscript, run `start_collector.bat`, and enable local overrides.
6. Place matching patches under the selected Overrides root and register them as described below.

This is an initial migration procedure, not a requirement for every launch. Clearing browser IndexedDB deletes the userscript's pending upload queue; translations and patches on disk remain intact.

## Registering existing patches

Already translated or modified bundles do not require translation or repacking. After confirming that Overrides contains the intended patches, run from the project directory:

```bat
python3 register_overrides.py
```

To register a specific file or directory:

```bat
python3 register_overrides.py "G:\Overrides\cdn.example.invalid\resource-path"
```

Registration reads file sizes, SHA-256 hashes, and relative Overrides paths, updates `deployed.json`, and backs up the previous record. It does not modify or copy bundles. Empty files, duplicate resource hashes, unsupported formats, or shortened `longurls` filenames cause the entire registration operation to fail.

After registration:

1. Keep `start_collector.bat` running.
2. Use the panel's local service check to confirm the deployed resource count.
3. Clear patched resource caches and reload using the panel. Select the `.data` patch again if main resource font replacement is enabled.
4. Confirm that catalog logs show `Catalog patched: target CRC=0` and check the local override marker on the corresponding bundle GET requests.

Successful registration does not mean an override has been applied or that its content is translated. Register again after manually changing bundle contents. Moving only the Overrides root does not require new records if file contents and internal relative paths remain unchanged.

## Collection and translation

Running `start_collector.bat` does not call the translation API. Resources containing detected text are saved under `inbox`. Process a selected original bundle with:

```bat
python3 pipeline.py all "inbox\selected-directory\file.bundle"
```

`all` runs extraction, translation, repacking validation, and deployment in order. Directory inputs are processed recursively. Multiple versions with the same filename are skipped; select a unique original file instead. Keep previously translated bundles separate from original resources.

The browser's persistent queue holds up to 64 items and 256 MiB in total. Each item has up to five send attempts with retry backoff, then remains paused. The panel displays queue status and can retry paused items. If the queue is full or a write fails, resolve the issue and reload the resource. Clearing site storage or browser storage eviction may delete queued items.

The panel can be minimized or hidden, and logging can be disabled. Reopen the panel from the Tampermonkey menu.

## Editing translations manually

Edit `translated.json` in the corresponding `work` directory. Change only `translation`. Preserve `id`, `source`, `asset`, `path_id`, `mode`, `path`, tags, variables, and line breaks.

Run these commands for the corresponding original bundle:

```bat
python3 pipeline.py pack "inbox\selected-directory\file.bundle"
python3 pipeline.py deploy "inbox\selected-directory\file.bundle"
```

Neither command calls the API. Incomplete, blocked, or invalid tasks are not deployed. Repack after editing translations. Existing override files are backed up before deployment.

If validation reports a changed source or translation location, restore that ID's source and location fields from `extracted.json`, retaining the edited `translation`.

Keep the model and prompt fixed within a task. Switching either during an existing task is not supported. To switch, process the original resources in a separate project directory.

## Resuming tasks

Successful translation batches are saved immediately. After temporary errors exhaust retries, rerun to resume. Refusals or exhausted validation retries pause the task rather than making unlimited API calls.

Even if every initial request failed and no translation cache exists, fill in the `translation` fields in `pending.json` and import them:

```bat
python3 manual_import.py "work\task-directory" "work\task-directory\pending.json"
```

Once all entries are complete, run `pack` and `deploy`. Do not delete state files to bypass validation. Only one process may modify a task at a time; deployment record updates are serialized.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| HTTP 401 | Python and userscript authentication tokens must match |
| Zero deployed resources | Service and registration commands must use the same project and the correct Overrides root |
| Registered resources but no override marker | Check that DevTools overrides are enabled, directories match, the request is GET, and the mapping does not use longurls |
| Only HEAD requests | Check cache read logs. HEAD does not return bundle content; its marker alone cannot establish whether replacement worked |
| CRC Mismatch | Check patch registration, actual catalog matching and modification logs, parsing errors, and unmatched targets |
| Dynamic catalog query token | Catalog query parameters are ignored by default. Verify that the configured origin and pathname match the request |
| Missing font glyphs | Check the `.data` GET replacement log and corresponding font bundle overrides, not just the registered count |

Only resources whose registered or deployed hashes and relative paths match actual files enter the catalog patch list. Requests other than matching catalog requests do not wait for the local manifest. Original requests proceed if the service is unavailable.

## Compatibility

- Text extraction supports the implemented TextAsset and story field structures, including `textMap/idToText/values`.
- Catalog modification depends on the supported Addressables JSON binary extra-data format. Compatibility with every Unity version is not guaranteed.
- Automatic deployment and registration require UnityFS bundles with a 32-character hexadecimal resource hash at the end of the filename stem. The repacking module produces the format used for automatic deployment.
- Automatic font patch generation and deployment through DevTools `longurls` mappings are not supported.
- Live usage within the configured scope and automated regression checks have been completed. This does not establish compatibility with every game, Unity version, or browser.

## Disclaimer

This project is intended for learning and research and is not affiliated with Unity, game developers, or platforms. Users must ensure they have permission to process resources and comply with applicable laws and service terms. Educational use does not grant authorization or exemption. Third-party game resources and fonts remain the property of their respective rights holders. Users are responsible for API charges.

The software is provided "as is", without warranties of any kind. Users are responsible for verifying their authorization to process resources, complying with applicable laws and platform terms, and assessing the risks of using, modifying, or distributing the tool. These risks include data loss or corruption, translation errors, service or account restrictions, and API charges. To the maximum extent permitted by applicable law, the authors and contributors shall not be liable for claims, damages, or other liability arising from the software or its use. This notice does not exclude or limit liability that cannot lawfully be excluded or limited. See `LICENSE` for the full MIT License terms.

## License

Project source code is licensed under the MIT License; see `LICENSE`. This license does not cover third-party game resources or dependencies. Preserve the copyright and license notices required by dependencies when distributing them. See `THIRD_PARTY_NOTICES.md` and `licenses/` for direct dependency notices and license text.

The release contains only tool source code, blank configuration templates, and project documentation. It does not include installed dependencies, game resources, font patches, story translations, or runtime data. `glossary.json` is empty by default and may be populated with user terminology. Automatic translation sends selected text and context to the configured API service. Local collection, registration, repacking, and deployment do not call the translation API.

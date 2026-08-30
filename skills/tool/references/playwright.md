# Playwright Tool Profile

Use `playwright.browser` as the stable logical profile ID, with
`playwright.browser.inspect` and `playwright.browser.execute` as its capability
IDs. This profile is a projection and control route, not a Tool-owned registry
or runtime. Never infer that it is installed, enabled, compatible, or healthy.

## Authorities and observations

Preserve each authoritative layer rather than collapsing Playwright into one
installed-state flag:

- the selected project's language/package manifest and lockfile, whether Node,
  Python, or another supported binding, own the declared dependency and its
  resolution intent;
- the resolved Playwright package and CLI report their own installed version;
- the selected provider owns installed browser binaries or cache locations and
  reports browser identities and revisions;
- the operating system and its package authority own required system
  dependencies;
- a host-native browser capability, plugin, or MCP server may instead be the
  selected authority and need not correspond to a project Playwright package.

Do not add or duplicate a project Playwright dependency merely because a
host-native, plugin, or MCP browser capability is available. Conversely, do
not claim that such a capability satisfies a project's declared Playwright
dependency without provider evidence and an explicit binding decision.

Observe package/CLI resolution separately from browser executable presence and
provider-reported compatibility. Package availability does not prove that any
browser executable is present or compatible, and browser presence does not
prove that required system dependencies, sandbox support, or runtime
permissions are ready. Record observation time and distinguish `unknown`,
`unavailable`, and `stale`; installation alone is not a health result.

## Lifecycle mutation boundary

Treat `playwright install`, browser download, update, or removal, and
`playwright install-deps` or any equivalent system-package change as
state-changing operations. Before routing one, resolve and present:

- the exact project, language runtime, package/CLI, browser names and revisions,
  cache or installation target, and system target;
- the authoritative package manager, Playwright provider, and OS package
  authority involved;
- expected downloads, disk use, shared-cache impact, privilege or system-package
  effects, compatibility impact, and available recovery path;
- the Human authorization that covers those exact targets and effects.

Do not use a broad cache deletion as an update, removal, repair, or recovery
shortcut. Never mutate unrelated browser revisions, projects, runtimes, shared
caches, or system packages. Provider output remains authoritative, and Tool
must report an unresolved or unavailable operation when the selected authority
does not expose it.

## Agent execution and external authority

Actual page navigation, clicking, form entry or submission, uploads, downloads,
screenshots, traces, videos, and Playwright test runs are bounded Agent
execution through `playwright.browser.execute`; they are not Tool discovery,
health, or lifecycle operations. Tool readiness does not authorize execution.
Agent must bind the exact task, browser/runtime target, website or application
authority, allowed effects, and receipt.

Preserve browser sandbox and permission boundaries. A browser's technical
ability to access a page, file, device, clipboard, notification, download, or
external service does not grant authority to do so. External website actions
retain their own Human, account, and service authority, including confirmation
requirements for submissions, purchases, publication, deletion, or other
externally visible effects.

Cookies, `storageState`, sessions, tokens, passwords, client certificates, and
proxy credentials are secret material. Screenshots, traces, videos, downloads,
and test artifacts may also contain secrets or sensitive data. Do not store or
expose that material as Tool metadata or in a repository, receipt, or catalog.
Before producing or retaining an artifact, resolve its exact target, contents
risk, retention and redaction policy, access boundary, and disposal behavior.

This profile defines no concrete registry, health service, lifecycle backend,
browser cache, or credential store. Project manifests, package managers,
Playwright providers, operating systems, hosts, plugins, and MCP servers remain
authoritative for the facts and operations they expose.

## Implemented inspection route

Use `python3 skills/tool/scripts/tool.py {discover,inspect,health} --profile
playwright.browser --target <existing-project-directory>`. For a project-CLI
authority, the adapter reports recognized local manifest/lockfile paths and a
resolved local or PATH Playwright CLI version when available. Browser binaries,
system dependencies, compatibility, permissions, and health remain `unknown`
unless their provider reports them; no browser is launched as a health check.

An explicit plugin, MCP, or host-capability authority/reference is preserved
without probing or substituting a project package. Lifecycle mutation verbs
return only `provider-route-required`, `performed: false`, and required Human
approval metadata; they do not download browsers, alter packages or system
dependencies, clear caches, or perform page actions.

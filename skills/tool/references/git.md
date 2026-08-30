# Git Tool Profiles

Use these as three independent logical Tool profiles. They are projections and
control routes, not a Tool-owned registry. Never infer that a profile is
installed, connected, enabled, or healthy. Report facts only after inspecting
the named authority; otherwise use `unknown` or `unavailable` as appropriate.

| Profile ID | Authority | Capability IDs |
| --- | --- | --- |
| `git.cli` | Native `git` executable, its OS package authority, and the selected repository or worktree | `git.cli.inspect`, `git.cli.execute` |
| `github.cli` | Native `gh` executable, its OS package authority, and GitHub CLI authentication/configuration for the selected hostname | `github.cli.inspect`, `github.cli.execute` |
| `git-lfs.cli` | Native `git-lfs` executable, its OS package authority, and the selected repository's Git config, hooks, attributes, and LFS data | `git-lfs.cli.inspect`, `git-lfs.cli.execute` |

Capability availability is profile-specific. An available inspection
capability does not imply that the execution capability is authorized, and one
profile's readiness does not establish another's readiness. Tool may project
these stable identifiers without creating a backend or persisting state.

## Shared discovery and lifecycle boundary

Resolve the exact executable before observing its version. Resolve the actual
OS package manager or other installer before routing install, update, or
remove; do not assume which package owns an executable. Keep executable
availability, package availability, version, repository configuration,
authentication, and health as separate observations with an observation time.

Install, update, remove, login, logout, repository writes, remote operations,
and data cleanup are state-changing. Before routing any such action, identify
the exact executable or package, repository/worktree or hostname/account when
relevant, expected effects, recovery constraints, and explicit Human
authorization. Provider output remains authoritative. Tool readiness never
authorizes Agent execution.

## `git.cli`

Project only inspected executable identity and version, the package authority
when resolvable, and the exact selected repository/worktree identity. A Git
executable can be available while no repository target is resolved. A
repository can also have multiple worktrees; do not collapse repository,
common Git directory, worktree root, branch, or detached-HEAD state into one
identity.

Read-only discovery may inspect executable resolution and `git --version`, then
use non-mutating Git queries against an explicit target to resolve the
repository and worktree. Absence of a repository, an unsupported query, or an
unresolved package authority is not proof that Git itself is unhealthy.

Creating or cloning a repository, changing refs, index or working-tree files,
editing configuration, adding or removing worktrees or remotes, fetching,
pulling, pushing, committing, merging, rebasing, resetting, restoring, or any
other repository operation is bounded Work/domain execution. It is not Tool
lifecycle management. Agent must bind `git.cli.execute` to the exact task,
target, authority, and receipt.

## `github.cli`

Project only inspected executable identity/version plus provider-reported
authentication status for an explicit GitHub hostname: account identity,
active-account state, authentication method when safely reported, and granted
scopes. Never capture or persist a token, credential, or secret-bearing command
output. In particular, do not use a token-printing operation as a health check.

Treat executable availability and authentication independently. An installed
`gh` can be unauthenticated; an authenticated account for one hostname says
nothing about another hostname. Unknown, expired, insufficient, or
over-broad scopes must remain explicit. Requested scopes and actually granted
scopes remain separate.

Login, logout, account switching, hostname changes, and scope refresh require
explicit Human authorization and must be routed through GitHub CLI's own
authentication/configuration authority. Tool stores neither token material nor
a substitute auth record. Pull-request, issue, release, repository, workflow,
and API operations are bounded Work/domain execution through
`github.cli.execute`, not Tool lifecycle operations.

## `git-lfs.cli`

Project executable resolution, `git-lfs` version, package installation
availability when the package authority reports it, and separately inspected
repository activation/configuration. Executable availability does not prove
that Git LFS is activated for a repository. Repository activation may involve
Git configuration and hooks, while tracking policy is represented by
repository attributes; neither may be inferred from the other.

Treat `git lfs install`, `git lfs uninstall`, `git lfs track`,
`git lfs untrack`, `git lfs migrate`, and `git lfs prune` as repository,
global-configuration, history, attribute, hook, or local-data mutations rather
than lifecycle metadata checks. Do not execute them without the exact target,
impact assessment, recovery implications, and required Human authorization.
Remote transfer and other LFS content operations likewise belong to bounded
Agent execution through `git-lfs.cli.execute`.

Do not equate repository configuration with remote LFS access. Remote
authentication may be mediated by Git, a credential helper, hosting provider,
or another resolved authority; preserve that authority and never copy its
credentials into Tool metadata.

## Implemented inspection route

Use `python3 skills/tool/scripts/tool.py {discover,inspect,health} --profile
<git.cli|github.cli|git-lfs.cli> --target <existing-directory>`. The adapter
resolves executables and bounded versions. Git inspection keeps worktree root,
Git directory, common Git directory, branch, and detached state separate.
GitHub inspection asks `gh auth status --hostname HOST --json hosts` for one
explicit hostname and retains only its bounded non-secret hosts/account/scopes
projection; it never requests a token. Git LFS inspection leaves activation and remote access `unknown` rather
than inferring either from executable or repository availability.

Executable availability, structured-inspection support, and authentication
state are three separate observations. A `gh` executable whose version does
not support the selected `--json` fields reports `inspectionSupport:
unsupported` and authentication `unknown`; malformed or unrecognized
structured output likewise remains `unknown`. Only a successfully parsed,
supported provider response may report authenticated `available` or actual
unauthenticated `unavailable` state.

The same CLI accepts lifecycle mutation verbs only to return the selected
provider route with `performed: false` and the need for Human approval. It does
not execute a Git, GitHub, Git LFS, package-manager, authentication, repository,
remote, or cleanup mutation.

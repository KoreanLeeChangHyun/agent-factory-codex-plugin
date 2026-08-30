# Recommended Libraries

## Selection policy

Treat this as a dependency-selection convention, not a universal package list.
Use the owning project's established dependency and framework choices first.
Add a dependency only when it materially improves the required outcome and its
maintenance, licensing, runtime, and distribution cost are justified.

Prefer, in order:

1. an existing project dependency that already provides the capability;
2. the language or platform standard library when it is sufficient;
3. a focused, maintained dependency with a compatible license;
4. a custom implementation when the behavior is small and project-specific,
   after comparing its defect and maintenance risk with the supply-chain cost
   of another dependency.

Do not introduce overlapping libraries for the same role without an accepted
migration decision. Keep versions and dependency declarations in the owning
project's native manifest rather than copying a version recommendation into
Convention.

## Agent Factory defaults

- Prefer the Python standard library for local initialization, serving, and
  repository utilities when it provides the required behavior.
- Prefer semantic HTML, CSS, and vanilla JavaScript for portable Human-facing
  documents and the baseline Workspace shell. Keep their dependencies local
  and relative; use JavaScript as progressive enhancement.
- Use Mermaid.js as the default JavaScript renderer for inspectable,
  versionable ERD, game-behavior, and sequence diagrams. Keep Mermaid source as
  the maintained artifact and treat rendered SVG as a projection.
- Reuse existing project SVG assets first. A maintained icon library is
  acceptable only when it renders actual SVG and its source and license are
  compatible with the project.

These defaults do not override an explicit Human choice or a stronger
project-local convention. Record a project-specific library decision in the
owning Specification or Project Skill when other Agents must apply it
consistently.

## Mermaid.js boundary

Mermaid.js is a documentation renderer, not a game AI runtime, Behavior Tree
engine, decision engine, simulator, or debugger. Its inclusion must not imply
that a documented behavior graph is executable or synchronized with game
runtime behavior.

For browser integration:

- provide Mermaid.js as a local relative dependency rather than a CDN asset;
- keep the default `securityLevel: "strict"` unless an explicit security review
  approves a different setting;
- use `mermaid.run` rather than the deprecated `mermaid.init` API;
- include `accTitle` and `accDescr` in authored diagrams;
- preserve a readable source or semantic description when JavaScript is
  unavailable; and
- declare the selected version, source, license, and update mechanism in the
  owning project's dependency manifest or vendored-asset record.

This convention selects the renderer but does not itself install, vendor, or
upgrade Mermaid.js.

## Evidence basis

This policy follows the OpenSSF guidance to check existing dependencies and
the standard library first, while recognizing that reimplementing mature
functionality can introduce its own defects. Evaluate a direct dependency
before adoption, retrieve it from the correct source, manage it through the
project's package manager, and keep it updateable:

- [OpenSSF: Simplifying Software Component Updates](https://best.openssf.org/Simplifying-Software-Component-Updates)
- [OpenSSF: Concise Guide for Developing More Secure Software](https://best.openssf.org/Concise-Guide-for-Developing-More-Secure-Software.html)
- [Mermaid: Usage and security levels](https://mermaid.js.org/config/usage)
- [Mermaid: Accessibility options](https://mermaid.js.org/config/accessibility)

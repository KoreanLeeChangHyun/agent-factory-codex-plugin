# Libraries

## Selection

- Follow established project/framework choices and explicit Human direction.
- Prefer existing dependencies, then sufficient standard-library functionality,
  then a focused maintained library with compatible licensing. Compare small
  custom implementations against dependency maintenance, defect and supply-chain cost.
- Avoid overlapping libraries without an accepted migration decision. Keep
  versions/declarations in the native manifest; record durable project choices
  in the owning Specification or Project Skill.

## Rendering dependencies

- Follow [theme.md](theme.md) for portable document behavior and SVG icon rules.
- Follow [diagrams.md](diagrams.md) for Mermaid source, diagram semantics and accessibility.

## Mermaid integration

- Use Mermaid.js to render SVG.
- Use a local relative dependency, `mermaid.run` and `securityLevel: "strict"`;
  another security level requires explicit security review.
- Record version, source, license and update mechanism in the owning manifest or
  vendored-asset record. This convention authorizes no installation or upgrade.

## Sources

- [OpenSSF: Component updates](https://best.openssf.org/Simplifying-Software-Component-Updates)
- [OpenSSF: Secure software guide](https://best.openssf.org/Concise-Guide-for-Developing-More-Secure-Software.html)
- [Mermaid: Usage](https://mermaid.js.org/config/usage)
- [Mermaid: Accessibility](https://mermaid.js.org/config/accessibility)

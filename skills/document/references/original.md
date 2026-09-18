# Original writing

<a id="fidelity-and-representation"></a>

## 1. Fidelity and representation

- Apply the mandatory [Document core requirements](../SKILL.md), using its Original-specific scope rather than the
  Processed/Specification body format.
- Original is a source-faithful reference to evidence. Do not copy, rewrite, translate
  or convert the referenced source into the package.
- Store packages at `docs/original/<category>[-<domain>]-<name>/`.

<a id="source-metadata-and-content"></a>

## 2. Source metadata and links

- Store exactly one `metadata.yaml` file in each Original package. Store no copied source
  body, attachment or `assets/` directory.
- `metadata.yaml` records `document-type: original`, `category`, nullable `domain`,
  `name`, provenance and fidelity metadata, plus a nonempty `links` list of source
  locators. Each link is a nonempty string.
- A link identifies external or repository evidence; it does not imply that the linked
  content is embedded, available or verified.
- Preservation and migration requirements grant no destructive local cleanup rule.

- Catalog and search read this metadata without fetching links. Follow the shared
  [catalog and search contract](../SKILL.md#local-document-catalog-and-search).

- Preserve source identifiers, provenance and link strings exactly. A response-language
  choice alone does not authorize translating or rewriting them.

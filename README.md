# Agent Factory for Codex

English | [한국어](README.ko.md)

Human-facing responses support the language the Human uses or explicitly selects.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Agent Factory is a Codex plugin for Human-directed software delivery. It provides
a bounded agent workflow, evidence exploration, and shared project conventions.

## Core features

### 1. Document system

- Keep project knowledge in a structured, searchable collection that agents can
  consult across tasks. Maintain one editable source for each document.
- Separate source references (**Original**), investigations and working knowledge
  (**Refined**), accepted facts and rules (**Specification**), execution records
  (**Progress**), and experience from previous work (**Lessons Learned**).
- Preserve the distinction between evidence, assumptions, and accepted decisions.
  Writing or summarizing a document does not automatically make it a project rule.
- When you request migration, organize existing documents into the project structure
  while preserving their content and references. Accepted Specification documents
  can be synchronized into project Skills for agents to use in later work.

### 2. Contracts → Work–Verification loop

- Turn a conversation into a work contract with six sections: contract information,
  hired workers and their IDs, task goals with assigned worker IDs and completion criteria,
  important constraints including task dependencies, a file tree showing each change
  operation and file-specific goal beside its task ID, and a task-level order diagram.
  The constraints table is the source for the diagram’s dependency arrows.
- Each contract version at `docs/progress/<contract-id>/contract-v<N>.md` also holds
  its execution record: runs, agents, Work and Verification status, and evidence per
  task. Revisions create a new version and preserve earlier ones.
- In a Work–Verification loop, the agents have distinct responsibilities:

  | Agent | Responsibility |
  | --- | --- |
  | Main | Consolidate the request, coordinate execution, and report results. |
  | Work | Carry out the contracted tasks and perform its own checks. |
  | Verification | Independently check the completed work against its requirements. |

  ```mermaid
  flowchart LR
    accTitle: Work–Verification loop
    accDescr: Work carries out the contracted tasks and runs its own checks. Verification independently checks the result; findings return to Work for correction until Verification passes.
    C["Work contract"] --> W["Work agent"]
    W --> V["Verification agent"]
    V -->|"findings"| W
    V -->|"pass"| R["Main reports"]
  ```

- Verification findings return to Work for correction, and revised work returns
  to Verification for another check. A passing result completes the verification
  stage; unresolved findings remain visible.
- Choose the execution mode for the task. Direct Main work and Work-only execution
  are also available; a separate Verification agent runs only when the selected
  route calls for it.

### 3. Interviews

- Resolve missing requirements and decisions through guided questions in the
  conversation. The agent uses existing context first and asks about gaps that
  could materially change the outcome.
- Address one decision at a time, with meaningful options, their advantages and
  disadvantages, and a recommendation. Your answers guide the next question.
- Skip, defer, correct, or narrow a question as needed. Recommendations and
  assumptions remain distinct from your decisions.
- Finish with a summary of the decisions and any remaining gaps. Save the interview
  as a document when requested or required by the workflow, and use it to inform
  a work contract or further planning.

### 4. Lessons learned

- Preserve errors, including recovered failures, alongside differences between
  your judgment and the agent's. Record the context, known causes, attempted
  solutions, and actual outcomes.
- Retrieve relevant lessons before related work so earlier findings can inform
  the approach. Keep unknown causes and unresolved issues explicit.
- Record how a lesson was applied and whether it helped, needed correction, or
  failed again. Recurrences add evidence without erasing the earlier record.
- When you request consolidation, turn supported lessons into reusable project
  rules. Lesson records remain evidence; they do not automatically become accepted
  Specifications or trigger background changes.

## VS Code extension

- This plugin is fully installable and usable on its own; the VS Code extension is optional.
- The Agent Factory VS Code extension requires this plugin to be installed and
  enabled at the identical semantic base version. For example, extension `1.0.28`
  accepts plugin `1.0.28+codex.<token>`.

- On activation, the extension checks whether the plugin is installed, enabled, and compatible,
  and attempts automatic installation when needed. An already active, compatible plugin is used without reinstalling.
  If compatibility cannot be confirmed afterward, activation stops with an error.
- To install or update it yourself, see [Manual installation](#manual-installation) below.

## Independent components

- **Extension + plugin:** Main, Work, Verification and exec/loop provide the complete local workflow without Agent Factory MCP. No MCP package, server, account, tenant, connection or authenticated resource is required. The plugin also works without the extension.
- **MCP:** The service is independently installed and operated; it is not a dependency of the local plugin workflow.

## Skills

The plugin exposes four public Skills:

- [Agent](skills/agent/SKILL.md): Dispatches Work and Verification agents and manages
  their sessions, execution progress, and results.
- [Convention](skills/convention/SKILL.md): Provides shared rules for communication,
  user decisions, development, testing, research, and interviews.
- [Document](skills/document/SKILL.md): Guides project document writing, organization,
  storage, and search, and synchronizes project specifications to Codex Skills.
- [Tool](skills/tool/SKILL.md): Lists the plugin scripts and points to the Skill that owns each one.

### Agent execution

- By default (orchestrator mode) Main converses, plans and routes, and delegates changes
  and research to Work; Verification runs only when you ask for it. In worker mode Main
  handles tasks directly.
- For each message, you can select Work (delegate a task), Plan (create a plan only),
  or Verification (check existing work). Combine planning, work, and verification with
  Plan·Work, Work·Verification, or Plan·Work·Verification.
- Your selection applies only to that message. See the
  [execution guide](skills/agent/references/execution-modes.md) for details.
- Research and interviews help gather evidence and clarify requirements.

### Models and sessions

- Agents can also run on Claude Code: choose a `claude-*` model such as `claude-opus-5-5`,
  `claude-sonnet-5`, `claude-fable-5-1` or `claude-haiku-4-5-20251001`, or the aliases
  `claude-opus`, `claude-sonnet` and `claude-haiku`.
- Every route works with Claude. Plan runs in Claude's plan mode, then the same session executes.
  Execution permissions map to the nearest Claude permission mode; they are not an OS sandbox.
  See the [execution guide](skills/agent/references/execution-modes.md#7-execution-providers).
- The Antigravity CLI (`agy`) can also run agents with Google AI subscription models: `gemini-*`
  models select it, and its other models are named `antigravity/<id>`. Antigravity runs are
  text-only. See [Antigravity](skills/agent/references/execution-modes.md#71-antigravity).
- This package is installed through Codex, and the runtime launches Claude and Antigravity runs.
  For Claude Code, install the separate [Claude Code distribution](https://github.com/KoreanLeeChangHyun/agent-factory-claude-plugin).

## Manual installation

- Official runtime installation guides: [Codex CLI](https://developers.openai.com/codex/cli/) · [Claude Code](https://code.claude.com/docs/en/setup).

- The Agent Factory VS Code extension installs the plugin automatically by default.
- To use the plugin on its own or install it manually, run:

  ```bash
  codex plugin marketplace add KoreanLeeChangHyun/agent-factory-codex-plugin --ref main
  codex plugin add agent-factory@agent-factory
  ```

- To install a published update:

  ```bash
  codex plugin marketplace upgrade agent-factory
  codex plugin add agent-factory@agent-factory
  ```

- Start a new Codex thread after installation or update so the Skills and tools are loaded.

## Document synchronization

- Project specification documents written according to Agent Factory rules in `docs/skills/`
  are synchronized to `.codex/skills/`, `.claude/skills/` and `.agents/skills/`, making them
  available to Codex, Claude Code and Antigravity as project Skills.
- After writing project specification documents in `docs/skills/`, agents run the
  [Document Skill synchronization script](skills/document/references/host-sync.md#continuous-codex-synchronization)
  and check the result. They also run it after modifying or deleting these documents.
- If synchronized documents are edited independently, synchronization reports a conflict
  and stops to preserve those changes.
- Existing Skills outside managed synchronization are preserved without modification.
  Document migration may proceed according to Agent Factory rules only when the user
  explicitly requests it, and only within the requested scope.

## Compatibility

- **Operating system:** Execution supports Linux, macOS and native Windows; WSL must meet the Linux requirements.
  On Windows, use a native Python (python.org or Microsoft Store), for example from Git Bash;
  MSYS2/Cygwin Python builds are unsupported. macOS and Windows require validation in your actual environment.
- **Python:** Python 3.10+.
- **Codex:** Codex CLI must be installed. Required capabilities and environment readiness are checked before execution.
- See [host readiness](skills/agent/references/installation.md#host-readiness-and-diagnostics)
  for environment-specific requirements and limitations.

## Bug reports

Please report bugs by email to [m.leechanghyun@gmail.com](mailto:m.leechanghyun@gmail.com).

## License

MIT License. See [LICENSE](LICENSE).

## Source

This repository is generated. Do not edit it directly; changes are made in
[https://github.com/KoreanLeeChangHyun/agent-factory-plugin-source](https://github.com/KoreanLeeChangHyun/agent-factory-plugin-source) and published with `distribution/port.py`.

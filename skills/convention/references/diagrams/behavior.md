# Behavior Diagrams

Use behavior diagrams to document game monster, NPC, and boss decision patterns.
They visualize intended or observed behavior; they are not executable game AI.

## Select the form

- Use Mermaid `stateDiagram-v2` for a finite-state machine: states, events,
  guards, transitions, initial state, terminal state, and boss phases.
- Use Mermaid `flowchart` for a Behavior Tree: Root, Selector, Sequence,
  Condition, Action, and the Success, Failure, or Running outcomes that matter
  to understanding the tree.
- Use `sequenceDiagram` instead when the primary question is the time order of
  interaction among the player, NPC, boss, environment, or game systems.

Do not call an ordinary flowchart a Behavior Tree unless its control nodes and
evaluation semantics are identified. Do not combine FSM and Behavior Tree
notation without naming the boundary between them.

## Content rules

- Name states and actions with domain terms used by the game design or code.
- Label transitions with the event or guard that causes them; do not invent
  thresholds, probabilities, cooldowns, priorities, or phase conditions.
- Distinguish a condition from an action and an interrupt from an ordinary
  transition.
- Show loops and terminal behavior explicitly when they affect comprehension.
- Keep implementation observations separate from desired design and unresolved
  behavior.
- Add `accTitle` and `accDescr` summarizing the behavior and critical branches.

## Runtime boundary

Mermaid.js renders documentation only. It is not a Behavior Tree engine, FSM
runtime, planner, decision engine, simulator, debugger, telemetry viewer, or
source of executable truth. Never claim that a rendered graph runs in the game,
matches the current build, or is synchronized with runtime logic without
separate inspected evidence.

If a project later needs visual node editing, live simulation, runtime tracing,
or code generation, resolve that as a separate tool and architecture decision;
do not expand this documentation convention into an engine contract.

## Official syntax references

- [Mermaid state diagrams](https://mermaid.js.org/syntax/stateDiagram)
- [Mermaid flowcharts](https://mermaid.js.org/syntax/flowchart)
- [Mermaid sequence diagrams](https://mermaid.js.org/syntax/sequenceDiagram)

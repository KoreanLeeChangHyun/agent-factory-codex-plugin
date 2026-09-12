# Cloud Reporting Adapter

## Contract and authority

- Cloud reporting is an optional integration. Use only an available connection
  that the Human selected and authorized, then read its advertised authenticated
  guide and tool schemas for binding, replay, heartbeat/freshness and search contracts.
- No reporting configuration is the normal standalone mode. Discovering a
  connector never authorizes reporting or transmission.
- Exec owns local process/session/run facts; loop alone owns transitions/END.
  Reports never control execution or prove Verification pass. Planning tasks remain separate.

## Configuration

- Opt in per run: `exec.py --reporting-config`; otherwise execution stays local.
- Loops use separate `--work-reporting-config` and `--verification-reporting-config`;
  never forward configuration between roles.
- Resolve authenticated endpoint, project/organization/Workspace/reporting-user/cloud-Agent
  identities and credential reference from existing authority. Never invent accounts,
  create cloud Agents or widen scopes. Keep secrets outside config/runtime/Git.

## Delivery and recovery

1. Wait for durable real session ID; bind project/Agent/session/run/optional loop.
   New runs get new tasks; retries preserve task/binding/recipient/user.
2. Persist command/key, revision and credential-free target before dispatch;
   persist acknowledgement before marking done. Unknown delivery retries identical
   commands under current authority; never rewrite pending commands or evade conflicts.
3. Deliver with `exec.py reporting-deliver --project-root PROJECT --agent AGENT --run-id RUN`.
   No AI turn, submit or `agent_run_submit`; never block supervision or alter the graph.
4. Keep failures/recipient changes pending with credential-free diagnostics.
   Reconcile cloud state before creating genuinely new events.

## Evidence

- Observe heartbeat facts with increasing sequence/nonregressing time; never fabricate
  timestamps or infer results from exit/staleness. Search supplies discovery only.
- Require explicit terminal evidence and validated receipts for semantic reports.
  Preserve intent/result/receipt hashes; changed evidence remains pending. Retry
  capture/delivery without rerunning execution; Human decisions stay input-required.
- Exclude requests, paths, environments, secrets and arbitrary result/receipt bodies
  from metadata. Document uploads need separate authority.
- Configuration proves no delivery/deployment/registration/migration or transport/RLS
  verification. Preserve recovery data until backup, verified import and authorized deletion.

"""Provider selection. Historical sessions without a provider remain Codex-owned."""
from runtime_errors import ContractError
from adapters.contracts import ProviderAdapter


def provider_for(model=None, provider=None, session=None):
    selected = provider or ("claude" if isinstance(model, str) and model.startswith("claude-") else
                            "codex" if model else (session or {}).get("provider", "codex"))
    if selected not in ("codex", "claude"):
        raise ContractError("provider_invalid", "Unknown execution provider")
    if provider and model and (model.startswith("claude-") != (provider == "claude")):
        raise ContractError("provider_model_mismatch", "Use a claude-* model identifier for Claude")
    if session and session.get("sessionId") and selected != session.get("provider", "codex"):
        raise ContractError("provider_session_mismatch", "Start a new chat or clear the conversation before changing provider; history is retained")
    return selected


def adapter(provider) -> ProviderAdapter:
    if provider == "claude":
        from adapters import claude
        return claude
    if provider == "codex":
        from adapters import codex
        return codex
    raise ContractError("provider_invalid", "Unknown execution provider")


def for_session(session) -> ProviderAdapter:
    return adapter(session.get("provider", "codex"))


def inherited_host_policy():
    """Identify the invoking host independently of the selected child provider."""
    import os
    thread = os.environ.get("CODEX_THREAD_ID")
    if thread:
        from adapters.codex.parent_policy import _rollout_policy
        return _rollout_policy(thread)
    return None

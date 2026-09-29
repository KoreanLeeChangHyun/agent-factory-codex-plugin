"""Provider selection. Historical sessions without a provider remain Codex-owned."""
from storage.errors import ContractError
from adapters.contracts import ProviderAdapter


# Model identifier prefix that selects each non-default provider. Antigravity also serves other
# families; `antigravity/<id>` names such a model explicitly (e.g. antigravity/claude-sonnet-4-6).
PREFIXES = {"antigravity": ("antigravity/", "gemini-"), "claude": ("claude-",)}
PROVIDERS = ("codex", *PREFIXES)
ANY_MODEL = ("antigravity",)


def _model_provider(model):
    return next((name for name, prefixes in PREFIXES.items() if model.startswith(prefixes)), "codex")


def provider_for(model=None, provider=None, session=None):
    current = (session or {}).get("provider", "codex")
    selected = provider or (_model_provider(model) if isinstance(model, str) and model else current)
    if selected not in PROVIDERS:
        raise ContractError("provider_invalid", "Unknown execution provider")
    # An explicit Antigravity provider may run any of its models by plain identifier.
    if provider and model and provider not in ANY_MODEL and _model_provider(model) != provider:
        raise ContractError("provider_model_mismatch", "Use a claude-* model for Claude and gemini-* or antigravity/<id> for Antigravity")
    if session and session.get("sessionId") and selected != current:
        raise ContractError("provider_session_mismatch", "Start a new chat or clear the conversation before changing provider; history is retained")
    return selected


def adapter(provider) -> ProviderAdapter:
    if provider == "claude":
        from adapters import claude
        return claude
    if provider == "antigravity":
        from adapters import antigravity
        return antigravity
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
        from adapters.codex.policy import _rollout_policy
        return _rollout_policy(thread)
    return None

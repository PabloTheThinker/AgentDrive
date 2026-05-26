"""
Built-in provider profiles for Agent Drive.
Each profile defines connection settings, env var names, and model lists.
"""

from agentdrive.providers.base import ProviderProfile, register

# ── OpenAI ────────────────────────────────────────────────────────────────

register(
    ProviderProfile(
        name="openai",
        display_name="OpenAI",
        description="OpenAI (GPT-4, GPT-4o, o-series models)",
        api_mode="chat_completions",
        env_var="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
        models_url="https://api.openai.com/v1/models",
        fallback_models=[
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4.1",
            "gpt-4.1-mini",
            "o3",
            "o4-mini",
        ],
        default_model="gpt-4o",
        signup_url="https://platform.openai.com/api-keys",
    )
)

# ── Anthropic ─────────────────────────────────────────────────────────────

register(
    ProviderProfile(
        name="anthropic",
        display_name="Anthropic",
        description="Anthropic (Claude models)",
        api_mode="anthropic",
        env_var="ANTHROPIC_API_KEY",
        alt_env_vars=("ANTHROPIC_TOKEN",),
        base_url="https://api.anthropic.com/v1",
        fallback_models=[
            "claude-sonnet-4",
            "claude-opus-4",
            "claude-haiku-3.5",
            "claude-sonnet-4.6",
            "claude-opus-4.6",
        ],
        default_model="claude-sonnet-4.6",
        signup_url="https://console.anthropic.com/",
    )
)

# ── OpenRouter ────────────────────────────────────────────────────────────

register(
    ProviderProfile(
        name="openrouter",
        display_name="OpenRouter",
        description="OpenRouter (200+ models, unified billing)",
        api_mode="chat_completions",
        env_var="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        models_url="https://openrouter.ai/api/v1/models",
        fallback_models=[
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "anthropic/claude-sonnet-4",
            "anthropic/claude-opus-4",
            "google/gemini-2.5-flash",
            "google/gemini-2.5-pro",
            "meta-llama/llama-4",
            "deepseek/deepseek-chat",
        ],
        default_model="openai/gpt-4o",
        signup_url="https://openrouter.ai/keys",
    )
)

# ── Google Gemini ─────────────────────────────────────────────────────────

register(
    ProviderProfile(
        name="gemini",
        display_name="Google Gemini",
        description="Google Gemini (Gemini 2.5 Flash, Pro)",
        api_mode="chat_completions",
        env_var="GOOGLE_API_KEY",
        alt_env_vars=("GEMINI_API_KEY",),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        fallback_models=["gemini-2.5-flash", "gemini-2.5-pro"],
        default_model="gemini-2.5-flash",
        signup_url="https://aistudio.google.com/apikey",
    )
)

# ── xAI / Grok ────────────────────────────────────────────────────────────

register(
    ProviderProfile(
        name="xai",
        display_name="xAI (Grok)",
        description="xAI Grok models",
        api_mode="chat_completions",
        env_var="XAI_API_KEY",
        base_url="https://api.x.ai/v1",
        fallback_models=["grok-3", "grok-3-mini"],
        default_model="grok-3",
        signup_url="https://console.x.ai/",
    )
)

# ── DeepSeek ──────────────────────────────────────────────────────────────

register(
    ProviderProfile(
        name="deepseek",
        display_name="DeepSeek",
        description="DeepSeek models",
        api_mode="chat_completions",
        env_var="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com/v1",
        fallback_models=["deepseek-chat", "deepseek-reasoner"],
        default_model="deepseek-chat",
        signup_url="https://platform.deepseek.com/",
    )
)

# ── Ollama (local) ────────────────────────────────────────────────────────

register(
    ProviderProfile(
        name="ollama",
        display_name="Ollama (Local)",
        description="Local models via Ollama (runs on your machine)",
        api_mode="chat_completions",
        env_var="",
        requires_key=False,
        base_url="http://localhost:11434/v1",
        models_url="http://localhost:11434/api/tags",
        fallback_models=["llama3.2", "mistral", "qwen2.5", "phi4"],
        default_model="llama3.2",
    )
)

# ── Custom Endpoint ───────────────────────────────────────────────────────

register(
    ProviderProfile(
        name="custom",
        display_name="Custom Endpoint",
        description="Any OpenAI-compatible endpoint",
        api_mode="chat_completions",
        env_var="CUSTOM_API_KEY",
        requires_key=False,
        base_url="",
        fallback_models=["custom-model"],
        default_model="custom-model",
    )
)

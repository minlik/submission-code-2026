from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass
from typing import Optional

from .code_home_env import CodeHomeEnvironmentFormatter
from .home_env import HomeEnvironmentFormatter


@dataclass(frozen=True)
class ResolvedInferenceConfig:
    tool_profile_name: Optional[str]
    context_mode: str
    template_name: str


_MODE_DEFAULTS = {
    "context": ResolvedInferenceConfig(
        tool_profile_name=None,
        context_mode="full",
        template_name="assistant_context.md",
    ),
    "tool": ResolvedInferenceConfig(
        tool_profile_name="tool",
        context_mode="brief",
        template_name="assistant_tool_v3.md",
    ),
    "advanced_tool": ResolvedInferenceConfig(
        tool_profile_name="advanced_tool",
        context_mode="brief",
        template_name="assistant_tool_advanced.md",
    ),
    "code": ResolvedInferenceConfig(
        tool_profile_name="code",
        context_mode="brief",
        template_name="assistant_code_v3.md",
    ),
    "full_context_tool": ResolvedInferenceConfig(
        tool_profile_name="full_context_tool",
        context_mode="full",
        template_name="assistant_tool_full_context.md",
    ),
}

_PROFILE_DEFAULTS = {
    "tool": ResolvedInferenceConfig(
        tool_profile_name="tool",
        context_mode="brief",
        template_name="assistant_tool_v3.md",
    ),
    "advanced_tool": ResolvedInferenceConfig(
        tool_profile_name="advanced_tool",
        context_mode="brief",
        template_name="assistant_tool_advanced.md",
    ),
    "code": ResolvedInferenceConfig(
        tool_profile_name="code",
        context_mode="brief",
        template_name="assistant_code_v3.md",
    ),
    "full_context_tool": ResolvedInferenceConfig(
        tool_profile_name="full_context_tool",
        context_mode="full",
        template_name="assistant_tool_full_context.md",
    ),
}


def resolve_inference_config(args: Namespace) -> ResolvedInferenceConfig:
    try:
        resolved = _config_from_mode(args.inference_mode, args)
    except KeyError as exc:
        raise ValueError(f"unsupported inference_mode: {args.inference_mode}") from exc

    explicit_tool_profile = getattr(args, "tool_profile", None)
    if explicit_tool_profile:
        if resolved.tool_profile_name is None:
            raise ValueError("tool_profile cannot be used with inference_mode=context")
        try:
            resolved = _config_from_profile(explicit_tool_profile, args)
        except KeyError as exc:
            raise ValueError(f"unsupported tool_profile: {explicit_tool_profile}") from exc

    explicit_context_mode = getattr(args, "context_mode", None)
    if explicit_context_mode:
        if resolved.tool_profile_name is None and explicit_context_mode != "full":
            raise ValueError("context_mode for inference_mode=context must be full")
        resolved = ResolvedInferenceConfig(
            tool_profile_name=resolved.tool_profile_name,
            context_mode=explicit_context_mode,
            template_name=resolved.template_name,
        )

    explicit_template = getattr(args, "assistant_template", None)
    if explicit_template:
        resolved = ResolvedInferenceConfig(
            tool_profile_name=resolved.tool_profile_name,
            context_mode=resolved.context_mode,
            template_name=explicit_template,
        )
    return resolved


def build_context_formatter(context_mode: str):
    if context_mode == "full":
        return HomeEnvironmentFormatter()
    if context_mode == "brief":
        return CodeHomeEnvironmentFormatter()
    raise ValueError(f"unsupported context_mode: {context_mode}")


def _config_from_mode(inference_mode: str, args: Namespace) -> ResolvedInferenceConfig:
    default = _MODE_DEFAULTS[inference_mode]
    return ResolvedInferenceConfig(
        tool_profile_name=default.tool_profile_name,
        context_mode=default.context_mode,
        template_name=_template_name_for(default, args),
    )


def _config_from_profile(profile_name: str, args: Namespace) -> ResolvedInferenceConfig:
    default = _PROFILE_DEFAULTS[profile_name]
    return ResolvedInferenceConfig(
        tool_profile_name=default.tool_profile_name,
        context_mode=default.context_mode,
        template_name=_template_name_for(default, args),
    )


def _template_name_for(default: ResolvedInferenceConfig, args: Namespace) -> str:
    if default.tool_profile_name is None:
        return getattr(args, "template_assistant_context")
    if default.tool_profile_name == "tool":
        return getattr(args, "template_assistant_tool")
    if default.tool_profile_name == "advanced_tool":
        return getattr(args, "template_assistant_advanced_tool")
    if default.tool_profile_name == "code":
        return getattr(args, "template_assistant_code")
    if default.tool_profile_name == "full_context_tool":
        return getattr(args, "template_assistant_full_context_tool")
    raise ValueError(f"unsupported tool profile for template lookup: {default.tool_profile_name}")

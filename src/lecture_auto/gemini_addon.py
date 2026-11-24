from __future__ import annotations

from dataclasses import asdict
from typing import Any

from lecture_auto.llm_config import LLMConfig
from lecture_auto.local_runtime import LocalRuntimeError, LocalRuntimeManager


class HostedLLMAddonAdapter:
    """Runs hosted LLM work in the separately installed managed Python runtime."""

    def __init__(self, config: LLMConfig, runtime_manager: LocalRuntimeManager) -> None:
        self.config = config
        self.runtime_manager = runtime_manager

    def _run(self, action: str, **payload: Any) -> str:
        try:
            return self._run_worker(action, payload)
        except LocalRuntimeError as exc:
            if self.config.provider != "openrouter":
                raise
            from lecture_auto.llm_adapter import (
                LLMConfigError, LLMNoteQualityError, LLMProviderAuthError, LLMTransientNetworkError,
            )

            error_types = (LLMConfigError, LLMNoteQualityError, LLMProviderAuthError, LLMTransientNetworkError)
            error_type = {error.__name__: error for error in error_types}.get(exc.code, LLMConfigError)
            raise error_type(str(exc)) from exc

    def _run_worker(self, action: str, payload: dict[str, Any]) -> str:
        result = self.runtime_manager.run_feature(
            self.config.provider,
            {
                "action": action,
                "config": asdict(self.config),
                **payload,
            },
            timeout=None,
        )
        return str(result.get("text") or "")

    def refine_transcript(
        self,
        raw_text: str,
        context_topic: str | None = None,
        evidence: dict[str, object] | None = None,
        checkpoint_path: str | None = None,
    ) -> str:
        return self._run(
            f"{self.config.provider}_refine_transcript",
            raw_text=raw_text,
            context_topic=context_topic,
            evidence=evidence,
            checkpoint_path=checkpoint_path,
        )

    def generate_notes(
        self,
        transcript: str,
        template: str,
        context_topic: str | None = None,
        material_path: str | None = None,
    ) -> str:
        return self._run(
            f"{self.config.provider}_generate_notes",
            transcript=transcript,
            template=template,
            context_topic=context_topic,
            material_path=material_path,
        )


GeminiAddonAdapter = HostedLLMAddonAdapter

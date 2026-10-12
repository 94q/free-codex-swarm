from __future__ import annotations


class ModelRouter:
    def __init__(self, models: list[dict]):
        self.models = {m["model"]: m for m in models}
        if not self.models:
            raise ValueError("Model catalog is empty; refresh models after login")

    def select(
        self,
        model: str = "auto",
        effort: str = "auto",
        role: str = "worker",
        mode: str = "auto",
    ) -> tuple[str, str]:
        if model == "auto":
            preferences = (
                ["gpt-6-astra", "gpt-6.1-sol"]
                if role == "coordinator" and mode != "eco"
                else ["gpt-6-luna", "gpt-6.1-sol"]
                if mode == "eco"
                else ["gpt-6.1-sol", "gpt-6-sol"]
            )
            default = next(
                (m["model"] for m in self.models.values() if m.get("isDefault")),
                next(iter(self.models)),
            )
            model = next((m for m in preferences if m in self.models), default)
        if model not in self.models:
            raise ValueError(f"Model not in this session's discovered catalog: {model}")
        item = self.models[model]
        supported = [r["reasoningEffort"] for r in item["supportedReasoningEfforts"]]
        if effort == "auto":
            desired = (
                "low"
                if mode == "eco"
                else "high"
                if role == "coordinator" or mode == "performance"
                else "medium"
            )
            effort = desired if desired in supported else item["defaultReasoningEffort"]
        if effort not in supported:
            raise ValueError(f"{model} supports {supported}, not {effort}")
        return model, effort

    def compact(self) -> list[dict]:
        return [
            {
                "model": m["model"],
                "efforts": [
                    r["reasoningEffort"] for r in m["supportedReasoningEfforts"]
                ],
            }
            for m in self.models.values()
        ]

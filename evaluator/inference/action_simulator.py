from typing import Any, Dict, List, Tuple

from ..data.mha_adapter import MhaAdapter


class ActionSimulator:
    def __init__(self, adapter: MhaAdapter | None = None) -> None:
        self.adapter = adapter or MhaAdapter()

    def labels_from_actions(
        self, engine_data: Dict[str, Any], actions: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        errors: List[str] = []
        if not actions:
            return [], errors
        env = self.adapter.build_env(engine_data)
        before = self._snapshot(env)
        for action in actions:
            try:
                self._apply_action(env, self.normalize_action(engine_data, action))
            except Exception as exc:
                did = action.get("did")
                locator = action.get("locator")
                errors.append(f"action failed did={did} locator={locator}: {exc}")
        after = self._snapshot(env)
        labels: List[Dict[str, Any]] = []
        for key, prev_value in before.items():
            if key not in after:
                continue
            cur_value = after[key]
            if cur_value != prev_value:
                did, attribute = key
                labels.append({"did": did, "attribute": attribute, "value": cur_value})
        return labels, errors

    def normalize_action(self, engine_data: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
        return dict(action)

    def _apply_action(self, env: Any, action: Dict[str, Any]) -> None:
        did = action.get("did")
        locator = action.get("locator")
        if not did or not locator:
            raise ValueError("action missing did or locator")
        payload: Dict[str, Any] = {
            "name": "control_device",
            "did": did,
            "locator": locator,
        }
        if "arguments" in action:
            payload["arguments"] = action.get("arguments")
        if "value" in action:
            payload["value"] = action.get("value")
        if "operator" in action:
            payload["operator"] = action.get("operator")
        if "cron" in action:
            payload["cron"] = action.get("cron")
        obs, *_ = env.step(payload)
        if getattr(obs, "error", None) is not None:
            raise RuntimeError(obs.error)

    def _snapshot(self, env: Any) -> Dict[Tuple[str, str], Any]:
        from mha.syntax import Attribute, Argument

        snapshot: Dict[Tuple[str, str], Any] = {}
        engine = getattr(env, "engine", None)
        if engine is None:
            return snapshot
        home = getattr(engine, "home", None)
        if home is None:
            return snapshot

        def collect(device):
            def visitor(node):
                if isinstance(node, Attribute) and not isinstance(node, Argument):
                    snapshot[(device.did, node.location)] = node.value
            device.traverse(visitor)

        for device in home.devices:
            collect(device)
        return snapshot

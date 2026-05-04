import copy
import re
from typing import Any, Callable, Dict, Optional, Set

from ..data.mha_adapter import MhaAdapter


class CriticEvaluator:
    def __init__(
        self,
        env_factory: Optional[Callable[[Dict[str, Any]], Any]] = None,
        expression_runner: Optional[Callable[[Any, str], bool]] = None,
        adapter: Optional[MhaAdapter] = None,
    ) -> None:
        self.adapter = adapter or MhaAdapter()
        self.env_factory = env_factory or self._default_env_factory
        self.expression_runner = expression_runner or self._default_expression_runner

    def evaluate(self, engine: Dict[str, Any], labels: Any, critic: Optional[str]) -> bool:
        """Evaluate critic using initial engine state plus predicted labels.

        In addition to the original expression check, this now enforces that
        no device outside the critic expression changes state compared with
        the initial engine snapshot.
        """

        try:
            expression = self._prepare_expression(critic)
            allowed_dids = self._critic_dids(expression)

            baseline_engine = copy.deepcopy(engine)
            candidate_engine = self._apply_labels_to_engine(copy.deepcopy(engine), labels)

            env = self.env_factory(candidate_engine)
            if not self.expression_runner(env, expression):
                return False

            return self._disallowed_devices_unchanged(baseline_engine, candidate_engine, allowed_dids)
        except Exception as exc:
            raise RuntimeError(f"critic evaluation failed: {exc}") from exc

    def evaluate_engine(
        self,
        engine: Dict[str, Any],
        critic: Optional[str],
        baseline_engine: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Evaluate critic against a fully predicted engine snapshot.

        The baseline (ground-truth) engine must also be provided so we can
        ensure devices not referenced in the critic remain unchanged.
        """

        try:
            expression = self._prepare_expression(critic)
            if baseline_engine is None:
                raise ValueError("missing baseline engine for critic evaluation")

            allowed_dids = self._critic_dids(expression)

            env = self.env_factory(engine)
            if not self.expression_runner(env, expression):
                return False

            return self._disallowed_devices_unchanged(baseline_engine, engine, allowed_dids)
        except Exception as exc:
            raise RuntimeError(f"critic evaluation failed: {exc}") from exc

    def labels_noop(self, engine: Dict[str, Any], labels: Any) -> bool:
        env = self.env_factory(engine)
        if labels is None:
            raise ValueError("missing labels")
        for label in labels:
            did = label.get("did")
            attribute = label.get("attribute")
            value = label.get("value")
            if did is None or attribute is None:
                raise ValueError("invalid label format")
            current = self._get_attribute(env, did, attribute)
            if current != value:
                return False
        return True

    def _apply_labels_to_engine(self, engine: Dict[str, Any], labels: Any) -> Dict[str, Any]:
        """Apply predicted labels directly onto an engine dict (in place)."""

        if labels is None:
            raise ValueError("missing labels")
        for label in labels:
            did = label.get("did")
            attribute = label.get("attribute")
            value = label.get("value")
            if did is None or attribute is None:
                raise ValueError("invalid label format")
            device = self.adapter.find_device(engine, did)
            if device is None:
                raise ValueError(f"device {did} not found in engine")
            self._set_attribute_on_device(device, attribute, value)
        return engine

    def _critic_dids(self, critic: str) -> Set[str]:
        pattern = r"device\([\"']([^\"']+)[\"']\)"
        return set(re.findall(pattern, critic))

    def _prepare_expression(self, critic: Optional[str]) -> str:
        if not critic:
            raise ValueError("missing critic expression")
        return critic.strip()

    def _set_attribute_on_device(self, device: Dict[str, Any], attribute: str, value: Any) -> None:
        if "." in attribute:
            component_name, attr_name = attribute.split(".", 1)
            components = device.get("components") or []
            component = next((item for item in components if item.get("name") == component_name), None)
            if component is None:
                raise ValueError(f"component {component_name} not found on device")
            self._set_attribute_in_list(component.get("attributes"), attr_name, value)
        else:
            self._set_attribute_in_list(device.get("attributes"), attribute, value)

    def _set_attribute_in_list(self, attributes: Any, attr_name: str, value: Any) -> None:
        if attributes is None:
            raise ValueError("device has no attributes")
        for attr in attributes:
            if attr.get("name") == attr_name:
                attr["value"] = value
                return
        raise ValueError(f"attribute {attr_name} not found on device")

    def _set_attribute(self, env: Any, did: str, attribute: str, value: Any) -> None:
        device = self._get_device(env, did)
        if "." in attribute:
            component_name, attr_name = attribute.split(".", 1)
            component = getattr(device, component_name)
            setattr(component, attr_name, value)
        else:
            setattr(device, attribute, value)

    def _get_attribute(self, env: Any, did: str, attribute: str) -> Any:
        device = self._get_device(env, did)
        if "." in attribute:
            component_name, attr_name = attribute.split(".", 1)
            component = getattr(device, component_name)
            return getattr(component, attr_name)
        return getattr(device, attribute)

    def _get_device(self, env: Any, did: str) -> Any:
        engine = getattr(env, "engine", None)
        if engine is None:
            raise ValueError("critic env has no engine")
        home = getattr(engine, "home", None)
        if home is None:
            raise ValueError("critic engine has no home")
        return home.get_device(did)

    def _disallowed_devices_unchanged(
        self, baseline_engine: Dict[str, Any], candidate_engine: Dict[str, Any], allowed_dids: Set[str]
    ) -> bool:
        baseline_devices = self._devices_by_did(baseline_engine)
        candidate_devices = self._devices_by_did(candidate_engine)
        all_dids = set(baseline_devices.keys()) | set(candidate_devices.keys())

        for did in all_dids:
            if did in allowed_dids:
                continue
            left = baseline_devices.get(did)
            right = candidate_devices.get(did)
            if left is None or right is None:
                return False
            if self._device_attributes(left) != self._device_attributes(right):
                return False
        return True

    def _devices_by_did(self, engine: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        for device in self.adapter.devices(engine):
            userdata = device.get("userdata") or {}
            did = userdata.get("did")
            if did and did not in result:
                result[did] = device
        return result

    def _device_attributes(self, device: Dict[str, Any]) -> Dict[str, Any]:
        attrs: Dict[str, Any] = {}
        for attr in device.get("attributes") or []:
            name = attr.get("name")
            if name is not None:
                attrs[name] = attr.get("value")

        for component in device.get("components") or []:
            comp_name = component.get("name")
            if comp_name is None:
                continue
            for attr in component.get("attributes") or []:
                attr_name = attr.get("name")
                if attr_name is not None:
                    attrs[f"{comp_name}.{attr_name}"] = attr.get("value")
        return attrs

    def _default_env_factory(self, engine: Dict[str, Any]) -> Any:
        try:
            from mha.env import HomeEnv
        except ImportError as exc:
            raise RuntimeError("mha.env.HomeEnv is required for critic evaluation") from exc
        engine_dict = dict(engine)
        home = dict(engine_dict.get("home") or {})
        if not home:
            raise ValueError("engine.home is required for critic evaluation")
        home.setdefault("name", "home")
        engine_dict["home"] = home
        return HomeEnv.from_dict({"engine": engine_dict})

    @staticmethod
    def _default_expression_runner(env: Any, expression: str) -> bool:
        engine = getattr(env, "engine", None)
        if engine is None:
            raise ValueError("critic env has no engine")
        try:
            result = engine.eval(expression)
        except Exception as exc:  # SyntaxError or other compile/runtime errors
            raise RuntimeError(exc) from exc
        if result.error is not None:
            raise RuntimeError(result.error)
        return bool(result.retvalue)

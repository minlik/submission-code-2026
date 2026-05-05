from typing import Optional, List, Sequence, Any
from mha.engine.core import Plugin
from mha.engine.home import Home, Device
from mha.syntax import Attribute, Service
from .data import Rule, Log


__all__ = ["Firewall"]



class Firewall(Plugin):
    Name: str = "firewall"
    Depends: Sequence[str] = ["home"]

    def __init__(self, rules: Optional[Sequence[Rule]] = None, logs: Optional[Sequence[Log]] = None):
        self._rules = [] if rules is None else list(rules)
        self._logs = [] if logs is None else list(logs)
        
    @property
    def logs(self) -> List[Log]:
        return self._logs
    
    @property
    def rules(self) -> List[Rule]:
        return self._rules

    @property
    def _home(self) -> Home:
        return self.manager.get_plugin("home")
    
    def setup(self, manager):
        super().setup(manager)
        self._home.add_event_listener(self._on_device_changed, ['call_service', 'set_attribute'])

    def get_rule(self, id: str) -> Rule:
        for rule in self._rules:
            if rule.id == id:
                return rule
        assert False, ValueError(f"rule '{id}' not found")

    def add_rule(self, action: str, key: str, values: Sequence[Any]) -> str:
        # merge
        for rule in self._rules:
            if rule.action != action or rule.key != key:
                continue
            rule.values.update(values)
            return rule.id

        # make new one
        rule = Rule(action, key, values)
        self._rules.append(rule)
        return rule.id
    
    def del_rule(self, id: str) -> None:
        for i, rule in enumerate(self._rules):
            if rule.id == id:
                del self._rules[i]
                break

    def clear_rules(self) -> None:
        self._rules.clear()

    def clear_logs(self) -> None:
        self._logs.clear()

    def _on_device_changed(self, event: str, **kwargs) -> None:
        log: Optional[Log] = None
        device: Optional[Device] = None
        if event == 'call_service':
            service: Service = kwargs['service']
            device = service.root
            log = Log(
                did=device.did,
                location=service.location,
                object="service",
                args=kwargs["args"],
                kwargs=kwargs['kwargs'],
                ret_value=kwargs['ret_value'],
                error=kwargs['error']
            )

        elif event == 'set_attribute':
            attribute: Attribute = kwargs['attribute']
            device = attribute.root
            log = Log(
                did=device.did,
                location=attribute.location,
                object="attribute",
                prev_value=kwargs['prev_value'],
                post_value=kwargs['post_value'],
                error=kwargs['error']
            )

        if log is None:
            return
        
        # check rule
        for rule in self._rules:
            if rule.check(device):
                continue
            log.add_block_rule(rule.id)
        
        # save log
        self._logs.append(log)

        # send block event
        if log.block_rules is not None:
            self.send_event("rule_block", log=log)

    def to_dict(self):
        return {
            **super().to_dict(),
            "rules": [rule.to_dict() for rule in self._rules],
            # "logs": [log.to_dict() for log in self._logs]
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            rules= [Rule.from_dict(rule) for rule in data["rules"]] if "rules" in data else None,
            # logs= [Log.from_dict(log) for log in data["logs"]] if "logs" in data else None,
        )
    


Plugin.register(Firewall)
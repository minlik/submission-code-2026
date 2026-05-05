from typing import Optional, Sequence, Dict, Any
import secrets
from mha.engine.core import Plugin
from mha.syntax import Attribute
from mha.engine.pyvm import PyVM
from mha.engine.home import Device, Home
from .task import Task


__all__ = ["TaskManager"]



class TaskManager(Plugin):
    Name: str = "task"
    Depends = ["home", "pyvm"]

    def __init__(self, tasks: Optional[Sequence[Task]] = None):
        self._tasks = [] if tasks is None else tasks
        self._task_map = {t.id: t for t in self.tasks}

    @property
    def tasks(self) -> Sequence[Task]:
        return self._tasks
    
    @property
    def all_finished(self) -> bool:
        return sum([1 for t in self.tasks if t.finished]) == len(self.tasks)
    
    @property
    def num_finished(self) -> int:
        return sum([1 for t in self.tasks if t.finished])
    
    @property
    def num_unfinished(self) -> int:
        return sum([1 for t in self.tasks if not t.finished])
    
    @property
    def progress(self) -> float:
        return 0 if len(self._tasks) == 0 else self.num_finished / len(self._tasks)
    
    @property
    def _home(self) -> Home:
        return self.manager.get_plugin("home")
    
    @property
    def _pyvm(self) -> PyVM:
        return self.manager.get_plugin("pyvm")

    def __len__(self) -> int:
        return len(self.tasks)
    
    def setup(self, manager):
        super().setup(manager)
        self.verify_all()

    def get_task(self, id: str) -> Task:
        task = self._task_map.get(id)
        if task is None:
            raise ValueError(f"no such task, {id}")
        return task
    
    def find_task(self, id: str) -> Optional[Task]:
        return self._task_map.get(id, None)

    def add_task(self, condition: str, description: Optional[str] = None) -> str:
        finished = self._verify_condition(condition) if self.installed else False
        id = secrets.token_urlsafe(6)[:8]
        task = Task(id, condition, description, finished)
        self._tasks.append(task)
        self._task_map[id] = task
        return id
    
    def del_task(self, id: str) -> None:
        task = self._task_map.get(id, None)
        if task is None:
            return
        self._tasks.remove(task)

    def clear_tasks(self) -> None:
        self._tasks.clear()
        self._task_map.clear()

    def verify(self, id: str) -> bool:
        task = self.get_task(id)
        prefinish = task.finished
        task._finished = self._verify_condition(task.condition)
        if prefinish != task.finished:
            self.send_event("task_status_changed", task=task)
        return task.finished
    
    def verify_all(self) -> None:
        for task in self._tasks:
            self.verify(task.id)

    def _verify_condition(self, condition: str) -> bool:
        # check vm
        if self._pyvm is None:
            raise RuntimeError("pyvm is not connected, please call connect() first")
        
        # evaluate condition
        def _raise_attribute_set(event: str, attribute: Attribute, **kwargs):
            device: Device = attribute.root
            raise ValueError(f"Attribute '{attribute.location}' is set in evaluating an condition, did: '{device.did}' name: {device.name}")

        with self._home.make_sniffer(_raise_attribute_set, "set_attribute"):
            res = self._pyvm.eval(condition)

        # check error
        if res.error is not None:
            raise ValueError(f"evaluate condition failed, {res.error}, condition: '{condition}'")
        
        # check return value
        if not isinstance(res.retvalue, bool):
            raise ValueError(f"condition must return a boolean value, but got {res.retvalue}, condition: '{condition}'")

        return res.retvalue
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update(tasks = [t.to_dict() for t in self._tasks])
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskManager":
        tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
        return cls(tasks)
    

Plugin.register(TaskManager)
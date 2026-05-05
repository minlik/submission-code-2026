from typing import Optional, Dict, Any, Tuple, Union
import gymnasium as gym
from gymnasium.envs.registration import register
from mha.engine import HomeEngine
from .action import Action, ActionSpace
from .obs import ObservationSpace, Observation


__all__ = ['HomeEnv']



class HomeEnv(gym.Env):

    observation_space = ObservationSpace()
    action_space = ActionSpace()

    def __init__(
        self, 
        engine: Optional[HomeEngine] = None,
        allow_step_after_done: bool = False,
        terminated: bool = False, 
        error: Optional[str] = None, 
        **kwargs
    ):
        super().__init__()
        if engine is not None:
            assert len(kwargs) == 0, f"can not specify both engine and arguments of engine"
        self._engine = HomeEngine(**kwargs) if engine is None else engine
        self._allow_step_after_done = allow_step_after_done
        self._terminated = terminated
        self._error: Optional[str] = error

    @property
    def engine(self) -> HomeEngine:
        return self._engine
    
    @property
    def allow_step_after_done(self) -> bool:
        return self._allow_step_after_done
    
    @property
    def terminated(self) -> bool:
        return self._terminated
    
    @property
    def error(self) -> Optional[str]:
        return self._error
    
    def reset(self, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None) -> Tuple[Observation, Dict]:
        self._terminated = False
        return Observation(), {}

    def step(self, action: Union[Action, Dict]):
        if not self._allow_step_after_done and self._terminated:
            raise RuntimeError("can not step a terminated environment")

        task_activated = self._engine.has_plugin("task")
        firewall_activated = self._engine.has_plugin("firewall")

        # wrap action
        if isinstance(action, dict):
            action = Action.from_dict(action)

        # run action
        rule_block_logs = []
        if firewall_activated:
            _add_block_log = lambda _, log: rule_block_logs.append(log.to_dict())
            with self._engine.firewall.make_sniffer(_add_block_log, "rule_block"):
                result = action(self.engine)
        else:
            result = action(self.engine)

        # check task
        effected_tasks = []
        if task_activated:
            _add_effect_task = lambda _, task: effected_tasks.append(task.id)
            with self._engine.task.make_sniffer(_add_effect_task, "task_status_changed"):
                self._engine.task.verify_all()

        # check terminated
        task_all_finished = (task_activated and len(self._engine.task) > 0 and self._engine.task.all_finished)
        self._terminated = task_all_finished or (len(rule_block_logs) > 0)
        if len(rule_block_logs) > 0:
            self._error = "blocked by firewall"

        # return
        observation = Observation(
            action=action.to_dict(), 
            stdout=result.stdout,
            stderr=result.stderr,
            error=result.error,
            effected_tasks = None if len(effected_tasks) == 0 else effected_tasks,
            block_logs=None if len(rule_block_logs) == 0 else rule_block_logs
        )
        return observation, 0.0, self._terminated, False, {}
    
    def copy(self) -> "HomeEnv":
        return type(self).from_dict(self.to_dict())

    def to_dict(self) -> Dict:
        d = {
            'engine': self.engine.to_dict(),
            'allow_step_after_done': self.allow_step_after_done,
            'terminated': self.terminated,
        }
        if self.error is not None:
            d['error'] = self.error
        return d

    @classmethod
    def from_dict(cls, data: Dict) -> "HomeEnv":
        args = {**data}
        args["engine"] = HomeEngine.from_dict(args['engine'])
        return cls(**args)
    
    @staticmethod
    def make(name="HomeEnv-v0", **kwargs) -> "HomeEnv":
        return gym.make(name, **kwargs).unwrapped
    


register(
    id='HomeEnv-v0',
    entry_point='mha.env.env:HomeEnv',
    order_enforce=False,
    disable_env_checker=True,
)
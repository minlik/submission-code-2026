from typing import Optional
from .core import PluginManager
from .home import Home
from .index import Query
from .pysolver import PySolver
from .pyvm import PyVM, PyCallResult
from .task import TaskManager
from .firewall import Firewall
from .memory import Memory
from .utility import Clock



__all__ = ['HomeEngine']


class HomeEngine(PluginManager):
    def __init__(self, home: Home, **plugins):
        self.add_plugin(home)
        self.add_plugins(plugins.values())
        
    @property
    def home(self) -> Home:
        return self.get_plugin('home')
    
    @property
    def clock(self) -> Clock:
        return self.get_or_create_plugin('clock')
    
    @property
    def query(self) -> Query:
        return self.get_or_create_plugin('query')
    
    @property
    def task(self) -> TaskManager:
        return self.get_or_create_plugin('task')
    
    @property
    def pysolver(self) -> PySolver:
        return self.get_or_create_plugin('pysolver')

    @property
    def pyvm(self) -> PyVM:
        return self.get_or_create_plugin('pyvm')
    
    @property
    def firewall(self) -> Firewall:
        return self.get_or_create_plugin('firewall')

    @property
    def memory(self) -> Memory:
        return self.get_or_create_plugin('memory')
    
    def eval(self, code: str) -> PyCallResult:
        return self.pyvm.eval(code)
    
    def exec(self, code: str) -> PyCallResult:
        return self.pyvm.exec(code)

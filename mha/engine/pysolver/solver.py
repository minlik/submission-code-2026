from typing import Optional, Dict, List, Sequence
from itertools import combinations
import ast
from z3 import *
import builtins
from dataclasses import dataclass
from mha.engine.core import Plugin
from mha.engine.home import Home
from .visitor import Visitor, Variable


__all__ = ["PySolver"]


@dataclass
class PyParsedExpr(object):
    expr: z3.ExprRef
    variables: List[Variable]
    tree: Optional[ast.Expression] = None


@dataclass
class PySolution(object):
    solved: bool
    expr: z3.ExprRef
    variables: List[Variable]
    values: Optional[List[Any]] = None


@dataclass
class PyEquivalence(object):
    exprs: List[PyParsedExpr]
    conflict: PySolution

    @property
    def equivalent(self) -> bool:
        return not self.conflict.solved


class PySolver(Plugin):
    Name: str = "pysolver"
    Depends = ["home"]

    def __init__(self, globals: Optional[Dict] = None):
        super().__init__()
        self._globals = globals

    @property
    def _home(self) -> Home:
        return self.manager.get_plugin("home")

    def parse(self, expr: str) -> PyParsedExpr:
        tree = ast.parse(expr, mode="eval")
        visitor = Visitor(globals=self.make_visitor_globals())
        parsed_expr = visitor.visit(tree.body)
        return PyParsedExpr(tree=tree, expr=parsed_expr, variables=visitor.variables)

    def solve(self, expr: PyParsedExpr) -> PySolution:
        solver = z3.Solver()
        for c in [c for var in expr.variables for c in var.constraints]:
            solver.add(c)
        solver.add(expr.expr)
        if solver.check() == z3.sat:
            model = solver.model()
            values = [
                self.get_python_value(model.eval(var.expr, model_completion=True))
                for var in expr.variables
            ]
            return PySolution(solved=True, expr=expr.expr, variables=expr.variables, values=values)

        return PySolution(solved=False, expr=expr.expr, variables=expr.variables)

    def equivalent(self, *exprs: PyParsedExpr) -> PyEquivalence:
        all_variables = [var for expr in exprs for var in expr.variables]
        combined_exprs = [lhs.expr != rhs.expr for lhs, rhs in combinations(exprs, 2)]
        sum_expr = z3.Or(*combined_exprs) if len(combined_exprs) > 1 else combined_exprs[0]
        solution = self.solve(PyParsedExpr(expr=sum_expr, variables=all_variables))
        return PyEquivalence(exprs=exprs, conflict=solution)
                
    def make_visitor_globals(self):
        return dict(
            **vars(builtins),

            # home
            home=self._home,
            device=self._home.get_device,
            get_device=self._home.get_device,
            get_devices=lambda : self._home.devices,
            get_room=self._home.get_room,
            get_rooms=lambda: self._home.rooms,

            **(self._globals or {}),
        )

    @staticmethod
    def get_python_value(expr: ExprRef) -> Any:
        if z3.is_int(expr):
            return expr.as_long()
        elif z3.is_real(expr):
            return expr.as_fraction()
        elif z3.is_seq(expr):
            return expr.as_string()
        elif z3.is_bool(expr):
            return is_true(expr)
        else:
            raise ValueError(f"Unsupported expression: {expr}")


Plugin.register(PySolver)
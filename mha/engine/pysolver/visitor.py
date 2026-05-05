from typing import Any, Dict, Optional, Union, List
from dataclasses import dataclass
import ast
from z3 import *
from mha import syntax


__all__ = ['Visitor', 'Variable']


_Z3_VAR_TYPES: Dict[str, Callable[[Any], z3.ExprRef]] = {
    'bool': z3.Bool,
    'int': z3.Int,
    'float': z3.Real,
    'str': z3.String,
}

_UNARY_OPS = {
    ast.UAdd:   lambda x: x,
    ast.USub:   lambda x: -x,
    ast.Not:    z3.Not,
}

_BIN_OPS = {
    ast.Add:      lambda a, b: a + b,
    ast.Sub:      lambda a, b: a - b,
    ast.Mult:     lambda a, b: a * b,
    ast.MatMult:  None,              
    ast.Div:      lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod:      lambda a, b: a % b,
    ast.Pow:      lambda a, b: a ** b,
}

_COMPARES = {
    ast.Eq:     lambda a, b: a == b,
    ast.NotEq:  lambda a, b: a != b,
    ast.Lt:     lambda a, b: a < b, 
    ast.LtE:    lambda a, b: a <= b,
    ast.Gt:     lambda a, b: a > b, 
    ast.GtE:    lambda a, b: a >= b,
    
    ast.In:     lambda a, b: z3.Or(*[a == item for item in b]),
    ast.NotIn:  lambda a, b: z3.And(*[a != item for item in b]),
    
    ast.Is:     lambda a, b: a == b,
    ast.IsNot:  lambda a, b: not (a == b),
    
    ast.And:    z3.And,
    ast.Or:     z3.Or,
}


@dataclass
class Variable(object):
    name: str
    value: syntax.Attribute
    expr: z3.ExprRef
    constraints: List[z3.ExprRef]


class Visitor(ast.NodeVisitor):

    def __init__(self, globals: Optional[Dict] = None):
        super().__init__()
        self._globals = {} if globals is None else globals
        self._variables: Dict[str, Variable] = {}

    @property
    def variables(self) -> List[Variable]:
        return list(self._variables.values())
    

    # ==================== objects ==================== #

    def visit_Name(self, node: ast.Name):
        if node.id not in self._globals:
            raise KeyError(f"global variable '{node.id}' is not defined")
        return self._globals[node.id]

    def visit_Constant(self, node: ast.Constant):
        return node.value
    
    def visit_List(self, node: ast.List):
        return [self.visit(item) for item in node.elts]
    
    def visit_Tuple(self, node: ast.Tuple):
        return tuple(self.visit(item) for item in node.elts)
    
    def visit_Set(self, node: ast.Set):
        return set([self.visit(item) for item in node.elts])

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        return self.visit(node.value)[self.visit(node.slice)]
    
    def visit_Attribute(self, node: ast.Attribute):
        root = self.visit(node.value)
        return self._try_make_variable(node, self._z3_getattr(root, node.attr))
            
    def visit_Call(self, node: ast.Call):
        args = [self.visit(arg) for arg in node.args]
        kwds = {kwd.arg: self.visit(kwd.value) for kwd in node.keywords}
        fn = self.visit(node.func)
        if not callable(fn):
            raise NotImplementedError(f"function '{fn}' is not callable")
        return self._try_make_variable(node, fn(*args, **kwds))


    # ==================== operators ==================== #

    def visit_UnaryOp(self, node: ast.UnaryOp):
        op = _UNARY_OPS.get(node.op.__class__, None)
        if op is None:
            raise NotImplementedError(f"unaryop '{node.op}' is not supported")
        return op(self.visit(node.operand))

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        lhs = self.visit(node.left)
        rhs = self.visit(node.right)
        op = _BIN_OPS.get(node.op.__class__, None)
        if op is None:
            raise NotImplementedError(f"binaryop '{node.op}' is not supported")
        return op(lhs, rhs)

    def visit_BoolOp(self, node: ast.BoolOp):
        op = _COMPARES.get(node.op.__class__, None)
        if op is None:
            raise NotImplementedError(f"boolop '{node.op}' is not supported")
        
        lhs = self.visit(node.values[0])
        for v in node.values[1:]:
            rhs = self.visit(v)
            lhs = op(lhs, rhs)
        return lhs

    def visit_Compare(self, node: ast.Compare):
        lhs = self.visit(node.left)
        vars = [lhs] + [self.visit(comp) for comp in node.comparators]
        assert len(vars) == len(node.ops) + 1, "number of variables and operators must match"
        exprs = []
        for i, ast_op in enumerate(node.ops):
            op = _COMPARES.get(ast_op.__class__, None)
            if op is None:
                raise NotImplementedError(f"compare operator '{ast_op.__class__.__name__}' is not supported")
            exprs.append(op(vars[i], vars[i+1]))
        return z3.And(*exprs) if len(exprs) > 1 else exprs[0]
    
    def generic_visit(self, node: ast.AST):
        raise NotImplementedError(f"'{node.__class__.__name__}' is not implemented for {self.__class__.__name__}")


    def _try_make_variable(self, node: ast.expr, value: Any) -> Any:
        if not isinstance(value, syntax.Attribute):
            return value
        
        # find variable
        varname = f"""device('{value.root.did}').{value.location}"""
        var = self._variables.get(varname, None)
        if var is not None:
            return var.expr

        # make new variable
        f_var = _Z3_VAR_TYPES.get(value.type.name, None)
        if f_var is None:
            raise NotImplementedError(f"type '{value.type.name}' is not supported to make variable")
        varexpr = f_var(varname)

        # constraints
        constraints = []
        if value.type.has_range:
            constraints.append(z3.And(value.type.range[0] <= varexpr, varexpr <= value.type.range[1]))
        if value.type.has_options:
            constraints.append(z3.Or(*[varexpr == opt for opt in value.type.options]))
        
        var = self._variables[varname] = Variable(varname, value, varexpr, constraints)
        return var.expr


    def _z3_getattr(self, a: Any, name: str) -> Any:
        obj = self._variables[str(a)].value if isinstance(a, z3.ExprRef) else a
        return getattr(obj, name)
        
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import z3


@dataclass
class StateExprComparisonResult:
    passed: bool
    reason: str
    error: Optional[str] = None


_ATOM_TYPE_TO_CONST = {
    "bool": z3.Bool,
    "int": z3.Int,
    "float": z3.Real,
    "str": z3.String,
}


class StateExprEquivalence:
    def __init__(self, engine: Dict[str, Any]) -> None:
        self.engine = engine or {}
        self._schemas = self._build_schema_index()

    def compare(self, ground_truth: Optional[str], prediction: Optional[str]) -> StateExprComparisonResult:
        if ground_truth is None and prediction is None:
            return StateExprComparisonResult(True, "both state_expr are null")
        if ground_truth is None or prediction is None:
            return StateExprComparisonResult(False, "state_expr null mismatch")

        try:
            gt_tree = ast.parse(self._normalize_expression(ground_truth), mode="eval")
            pred_tree = ast.parse(self._normalize_expression(prediction), mode="eval")
            variable_constraints = self._extract_constraints([gt_tree, pred_tree])
            variables, constraints = self._build_z3_variables(variable_constraints)
            gt_expr = self._ast_to_z3(gt_tree.body, variables)
            pred_expr = self._ast_to_z3(pred_tree.body, variables)
            solver = z3.Solver()
            solver.add(*constraints)
            solver.add(gt_expr != pred_expr)
            if solver.check() == z3.unsat:
                return StateExprComparisonResult(True, "state_expr are equivalent")
            gt_norm = self._normalize_expression(ground_truth)
            pred_norm = self._normalize_expression(prediction)
            gt_relaxed = self._relax_strict_inequalities(gt_norm)
            pred_relaxed = self._relax_strict_inequalities(pred_norm)
            if gt_relaxed != gt_norm or pred_relaxed != pred_norm:
                try:
                    gt_tree2 = ast.parse(gt_relaxed, mode="eval")
                    pred_tree2 = ast.parse(pred_relaxed, mode="eval")
                    vc2 = self._extract_constraints([gt_tree2, pred_tree2])
                    vars2, cons2 = self._build_z3_variables(vc2)
                    gt_expr2 = self._ast_to_z3(gt_tree2.body, vars2)
                    pred_expr2 = self._ast_to_z3(pred_tree2.body, vars2)
                    solver2 = z3.Solver()
                    solver2.add(*cons2)
                    solver2.add(gt_expr2 != pred_expr2)
                    if solver2.check() == z3.unsat:
                        return StateExprComparisonResult(True, "state_expr are equivalent (relaxed boundary)")
                except Exception:
                    pass
            return StateExprComparisonResult(False, "state_expr are not equivalent")
        except Exception as exc:
            return StateExprComparisonResult(False, f"state_expr comparison failed: {exc}", error=str(exc))

    @staticmethod
    def _normalize_expression(expression: str) -> str:
        return expression.replace("home.get_device", "device").strip()

    @staticmethod
    def _relax_strict_inequalities(expression: str) -> str:
        import re
        expression = re.sub(r'(?<![=<>!])>\s*(\d+\.?\d*)', r'>= \1', expression)
        expression = re.sub(r'(?<![=<>!])<\s*(\d+\.?\d*)', r'<= \1', expression)
        return expression

    def _build_schema_index(self) -> Dict[str, Dict[str, Any]]:
        index: Dict[str, Dict[str, Any]] = {}
        home = self.engine.get("home") or {}
        for device in home.get("devices") or []:
            userdata = device.get("userdata") or {}
            did = str(userdata.get("did") or "")
            if not did:
                continue
            for attr in device.get("attributes") or []:
                name = attr.get("name")
                if name:
                    index[f"device('{did}').{name}"] = {k: v for k, v in attr.items() if k != "value"}
            for component in device.get("components") or []:
                component_name = component.get("name")
                if not component_name:
                    continue
                for attr in component.get("attributes") or []:
                    name = attr.get("name")
                    if name:
                        index[f"device('{did}').{component_name}.{name}"] = {
                            k: v for k, v in attr.items() if k != "value"
                        }
        return index

    def _extract_constraints(self, trees: Iterable[ast.Expression]) -> Dict[str, Dict[str, Any]]:
        constraints: Dict[str, Dict[str, Any]] = {}
        for tree in trees:
            for node in ast.walk(tree):
                key = self._attribute_key(node)
                if key is None:
                    continue
                schema = self._schemas.get(key)
                if schema is None:
                    if any(name.startswith(f"{key}.") for name in self._schemas):
                        continue
                    raise ValueError(f"unsupported attribute reference: {key}")
                constraints[key] = schema
        return constraints

    def _build_z3_variables(
        self, variable_constraints: Dict[str, Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], List[z3.ExprRef]]:
        variables: Dict[str, Any] = {}
        constraints: List[z3.ExprRef] = []
        for name, schema in variable_constraints.items():
            var_type = schema.get("type")
            constructor = _ATOM_TYPE_TO_CONST.get(var_type)
            if constructor is None:
                raise NotImplementedError(f"unsupported attribute type: {var_type} for {name}")
            variables[name] = constructor(name)
            constraint = self._build_constraint(name, schema, variables[name])
            if constraint is not None:
                constraints.append(constraint)
        return variables, constraints

    def _build_constraint(self, name: str, schema: Dict[str, Any], variable: Any) -> Optional[z3.ExprRef]:
        attr_range = schema.get("range")
        options = schema.get("options")
        if attr_range:
            lower = attr_range[0]
            upper = attr_range[1]
            if schema.get("type") == "float":
                return z3.And(variable >= float(lower), variable <= float(upper))
            return z3.And(variable >= int(lower), variable <= int(upper))
        if options:
            return z3.Or(*[variable == option for option in options])
        return None

    def _ast_to_z3(self, node: ast.AST, variables: Dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Attribute):
            key = self._attribute_key(node)
            if key is None or key not in variables:
                raise ValueError(f"unsupported attribute expression: {ast.unparse(node)}")
            return variables[key]
        if isinstance(node, ast.Name):
            if node.id in {"True", "False", "None"}:
                return ast.literal_eval(node.id)
            raise ValueError(f"unsupported name: {node.id}")
        if isinstance(node, ast.BoolOp):
            values = [self._to_bool(self._ast_to_z3(value, variables)) for value in node.values]
            if isinstance(node.op, ast.And):
                return z3.And(*values)
            if isinstance(node.op, ast.Or):
                return z3.Or(*values)
            raise NotImplementedError(f"unsupported bool op: {ast.dump(node.op)}")
        if isinstance(node, ast.UnaryOp):
            operand = self._ast_to_z3(node.operand, variables)
            if isinstance(node.op, ast.Not):
                return z3.Not(self._to_bool(operand))
            if isinstance(node.op, ast.USub):
                return -operand
            raise NotImplementedError(f"unsupported unary op: {ast.dump(node.op)}")
        if isinstance(node, ast.Compare):
            left = self._ast_to_z3(node.left, variables)
            result = None
            for op, comparator in zip(node.ops, node.comparators):
                right = self._ast_to_z3(comparator, variables)
                current = self._compare(left, op, right)
                result = current if result is None else z3.And(result, current)
                left = right
            return result
        if isinstance(node, ast.BinOp):
            left = self._ast_to_z3(node.left, variables)
            right = self._ast_to_z3(node.right, variables)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Mod):
                return left % right
            raise NotImplementedError(f"unsupported binary op: {ast.dump(node.op)}")
        raise NotImplementedError(f"unsupported expression node: {ast.dump(node)}")

    def _compare(self, left: Any, op: ast.cmpop, right: Any) -> z3.ExprRef:
        if self._is_real_expr(left) and self._is_int_expr(right):
            right = z3.ToReal(right)
        elif self._is_real_expr(right) and self._is_int_expr(left):
            left = z3.ToReal(left)
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        if isinstance(op, ast.Lt):
            return left < right
        if isinstance(op, ast.LtE):
            return left <= right
        if isinstance(op, ast.Gt):
            return left > right
        if isinstance(op, ast.GtE):
            return left >= right
        if isinstance(op, ast.Is):
            return left == right
        if isinstance(op, ast.IsNot):
            return left != right
        raise NotImplementedError(f"unsupported comparison op: {ast.dump(op)}")

    @staticmethod
    def _to_bool(value: Any) -> Any:
        if isinstance(value, bool) or z3.is_bool(value):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return value != ""

    @staticmethod
    def _is_real_expr(value: Any) -> bool:
        return isinstance(value, z3.ExprRef) and z3.is_real(value)

    @staticmethod
    def _is_int_expr(value: Any) -> bool:
        return isinstance(value, z3.ExprRef) and z3.is_int(value)

    def _attribute_key(self, node: ast.AST) -> Optional[str]:
        if not isinstance(node, ast.Attribute):
            return None
        parts: List[str] = []
        current: ast.AST = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if not isinstance(current, ast.Call):
            return None
        if not isinstance(current.func, ast.Name) or current.func.id != "device":
            return None
        if len(current.args) != 1 or not isinstance(current.args[0], ast.Constant):
            return None
        did = current.args[0].value
        if not isinstance(did, str):
            return None
        return "device('{}').{}".format(did, ".".join(reversed(parts)))

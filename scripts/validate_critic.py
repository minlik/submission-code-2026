#!/usr/bin/env python3
"""Standalone script to validate and auto-fix critic expressions."""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluator.data.io import read_jsonl, write_jsonl
from evaluator.data.mha_adapter import MhaAdapter
from evaluator.judging.critic import CriticEvaluator


DEVICE_ACCESS_PATTERN = re.compile(r"device\(['\"]([^'\"]+)['\"]\)\.([A-Za-z_][\w\.]*?)\b")


class CriticValidator:
    def __init__(self, adapter: Optional[MhaAdapter] = None) -> None:
        self.adapter = adapter or MhaAdapter()
        self.critic_evaluator = CriticEvaluator(adapter=self.adapter)

    def validate(self, record: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], str, Optional[str]]:
        """Validate one record. Returns (new_record|None, status, error_msg)."""

        critic = record.get("critic")
        if not critic:
            return record, "empty", None

        engine = record.get("engine") or {}
        ok, first_error = self._runs(engine, critic)
        if ok:
            return record, "valid", None

        repaired, changed, repair_error = self._repair_paths(engine, critic)
        if repair_error:
            return None, "dropped", repair_error
        if repaired is None:
            return None, "dropped", first_error

        ok, second_error = self._runs(engine, repaired)
        if ok and changed:
            new_record = dict(record)
            new_record["critic"] = repaired
            return new_record, "fixed", None
        if ok:
            return record, "valid", None

        return None, "dropped", second_error or first_error

    def validate_ground_truth(self, record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate that ground_truth.labels satisfy critic (mirrors --ground-truth-only)."""

        engine = record.get("engine") or {}
        critic = record.get("critic")
        ground_truth = record.get("ground_truth") or {}
        labels = ground_truth.get("labels") or []

        if not critic:
            if not labels:
                return True, None
            try:
                if self.critic_evaluator.labels_noop(engine, labels):
                    return True, None
            except Exception as exc:  # noqa: BLE001
                return False, f"ground_truth labels noop check failed: {exc}"
            return False, "ground_truth labels modify state but critic is empty"

        if not labels:
            return False, "missing ground_truth.labels for critic evaluation"

        try:
            ok = self.critic_evaluator.evaluate(engine=engine, labels=labels, critic=critic)
        except Exception as exc:  # noqa: BLE001
            return False, f"ground_truth critic evaluation failed: {exc}"

        if not ok:
            return False, "ground_truth labels do not satisfy critic"
        return True, None

    def _runs(self, engine: Dict[str, Any], expression: str) -> Tuple[bool, Optional[str]]:
        try:
            env = self.adapter.build_env(engine)
        except Exception:
            # Environment errors are infrastructure issues; surface them to the caller.
            raise

        try:
            engine_obj = getattr(env, "engine", None)
            if engine_obj is None:
                raise RuntimeError("critic env has no engine")
            result = engine_obj.eval(expression)
            if result.error:
                raise RuntimeError(result.error)
            return True, None
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)

    def _repair_paths(self, engine: Dict[str, Any], critic: str) -> Tuple[Optional[str], bool, Optional[str]]:
        """Ensure every device path is executable; apply fallback rules."""

        matches = list(DEVICE_ACCESS_PATTERN.finditer(critic))
        if not matches:
            return critic, False, None

        parts: List[str] = []
        last = 0
        changed = False

        for match in matches:
            did, path = match.group(1), match.group(2)
            replacement, err = self._choose_path(engine, did, path)
            if err:
                return None, changed, err
            if replacement != path:
                changed = True
            start, end = match.start(2), match.end(2)
            parts.append(critic[last:start])
            parts.append(replacement)
            last = end

        parts.append(critic[last:])
        return "".join(parts), changed, None

    def _choose_path(self, engine: Dict[str, Any], did: str, path: str) -> Tuple[str, Optional[str]]:
        device = self.adapter.find_device(engine, did)
        if device is None:
            return path, f"device {did} not found"

        if "." in path:
            comp_name, attr_name = path.split(".", 1)
            if self._has_component_attr(device, comp_name, attr_name):
                return path, None
            if self._has_direct_attr(device, attr_name):
                return attr_name, None
            return path, f"attr {path} not found"

        attr_name = path
        if self._has_direct_attr(device, attr_name):
            return path, None
        comp_names = self._components_with_attr(device, attr_name)
        if comp_names:
            return f"{comp_names[0]}.{attr_name}", None
        return path, f"attr {attr_name} not found"

    @staticmethod
    def _has_direct_attr(device: Dict[str, Any], attr_name: str) -> bool:
        for attr in device.get("attributes") or []:
            if attr.get("name") == attr_name:
                return True
        return False

    @staticmethod
    def _has_component_attr(device: Dict[str, Any], comp_name: str, attr_name: str) -> bool:
        for component in device.get("components") or []:
            if component.get("name") != comp_name:
                continue
            for attr in component.get("attributes") or []:
                if attr.get("name") == attr_name:
                    return True
        return False

    @staticmethod
    def _components_with_attr(device: Dict[str, Any], attr_name: str) -> List[str]:
        names: List[str] = []
        for component in device.get("components") or []:
            comp_name = component.get("name")
            if not comp_name:
                continue
            for attr in component.get("attributes") or []:
                if attr.get("name") == attr_name:
                    names.append(comp_name)
                    break
        return names


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate critic expressions in dataset files.")
    parser.add_argument("--data-dir", help="Directory containing JSONL files (recursively processed).")
    parser.add_argument("--data-files", nargs="+", help="Explicit JSONL files to process.")
    parser.add_argument(
        "--output-suffix",
        default="critic_validated",
        help="Suffix added to output filename before extension (default: critic_validated).",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite input files instead of writing <name>.<suffix>.jsonl outputs.",
    )
    return parser.parse_args()


def collect_paths(args: argparse.Namespace) -> List[str]:
    paths: List[str] = []
    if args.data_dir:
        for root, _, files in os.walk(args.data_dir):
            for name in files:
                if name.endswith(".jsonl"):
                    paths.append(os.path.join(root, name))
    if args.data_files:
        paths.extend(args.data_files)
    if not paths:
        raise RuntimeError("Provide --data-dir or --data-files")
    return sorted(set(paths))


def output_path(input_path: str, suffix: str) -> str:
    directory = os.path.dirname(input_path)
    stem, ext = os.path.splitext(os.path.basename(input_path))
    new_name = f"{stem}.{suffix}{ext}"
    return os.path.join(directory, new_name)


def process_file(path: str, validator: CriticValidator, suffix: str, in_place: bool) -> Dict[str, Any]:
    records = list(read_jsonl(path))
    kept: List[Dict[str, Any]] = []
    stats = {
        "total": len(records),
        "empty": 0,
        "valid": 0,
        "fixed": 0,
        "kept": 0,
        "dropped": 0,
        "dropped_critic": 0,
        "dropped_ground_truth": 0,
    }
    dropped_examples: List[str] = []

    for record in records:
        new_record, status, error = validator.validate(record)
        if status == "empty":
            candidate = record
        elif status == "valid":
            candidate = record
        elif status == "fixed":
            candidate = new_record  # type: ignore[assignment]
        else:
            stats["dropped"] += 1
            stats["dropped_critic"] += 1
            label = record.get("uuid") or str(record.get("query_idx"))
            if error:
                label = f"{label}:{error}"
            dropped_examples.append(label)
            continue

        gt_ok, gt_error = validator.validate_ground_truth(candidate)  # type: ignore[arg-type]
        if not gt_ok:
            stats["dropped"] += 1
            stats["dropped_ground_truth"] += 1
            label = record.get("uuid") or str(record.get("query_idx"))
            if gt_error:
                label = f"{label}:{gt_error}"
            dropped_examples.append(label)
            continue

        # Passed both critic MHA validation and ground-truth consistency.
        if status == "valid":
            stats["valid"] += 1
        elif status == "fixed":
            stats["fixed"] += 1
        else:
            stats["empty"] += 1
        stats["kept"] += 1
        kept.append(candidate)  # type: ignore[arg-type]

    out_path = path if in_place else output_path(path, suffix)
    if in_place:
        tmp_path = f"{path}.tmp"
        write_jsonl(tmp_path, kept)
        os.replace(tmp_path, path)
    else:
        write_jsonl(out_path, kept)
    stats["output_path"] = out_path
    if dropped_examples:
        stats["dropped_examples"] = dropped_examples[:5]
    return stats


def main() -> None:
    args = parse_args()
    validator = CriticValidator()
    paths = collect_paths(args)
    suffix = args.output_suffix.strip() or "critic_validated"
    in_place = bool(args.in_place)

    for path in paths:
        stats = process_file(path, validator, suffix, in_place)
        print(
            f"[{path}] -> {stats['output_path']} | "
            f"total={stats['total']} kept={stats['kept']} "
            f"empty={stats['empty']} valid={stats['valid']} fixed={stats['fixed']} "
            f"dropped={stats['dropped']} (critic={stats['dropped_critic']} "
            f"ground_truth={stats['dropped_ground_truth']})"
        )
        if "dropped_examples" in stats:
            print(f"  dropped examples: {', '.join(stats['dropped_examples'])}")


if __name__ == "__main__":
    main()

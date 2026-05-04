import os
import uuid as uuid_lib
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .io import read_jsonl, write_jsonl
from ..core.types import Sample


@dataclass
class DatasetFile:
    path: str
    records: List[Dict]
    samples: List[Sample]


class DatasetLoader:
    def load(self, paths: List[str]) -> Tuple[List[DatasetFile], List[Sample]]:
        dataset_files: List[DatasetFile] = []
        all_samples: List[Sample] = []
        for path in paths:
            records = list(read_jsonl(path))
            samples = [Sample.from_dict(record) for record in records]
            category = self._category_from_path(path)
            for sample in samples:
                sample.source_path = path
                sample.category = category
            dataset_files.append(DatasetFile(path=path, records=records, samples=samples))
            all_samples.extend(samples)
        return dataset_files, all_samples

    def ensure_uuids(self, dataset_files: List[DatasetFile]) -> None:
        for dataset in dataset_files:
            changed = False
            for record, sample in zip(dataset.records, dataset.samples):
                if not record.get("uuid"):
                    new_uuid = str(uuid_lib.uuid4())
                    record["uuid"] = new_uuid
                    sample.uuid = new_uuid
                    changed = True
                else:
                    sample.uuid = record.get("uuid")
            if changed:
                write_jsonl(dataset.path, dataset.records)

    def _category_from_path(self, path: str) -> str:
        norm = os.path.normpath(path)
        parts = norm.split(os.sep)
        if "data" in parts:
            idx = parts.index("data")
            rel_parts = parts[idx + 1 : -1]
        else:
            rel_parts = parts[:-1]
        return "/".join(rel_parts)

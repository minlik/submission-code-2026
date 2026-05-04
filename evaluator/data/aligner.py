from typing import Dict, List, Optional

from ..core.types import PredictionRecord, Sample


class PredictionAligner:
    def align(self, samples: List[Sample], predictions: List[PredictionRecord]) -> None:
        by_uuid: Dict[str, PredictionRecord] = {}
        by_query_idx: Dict[int, PredictionRecord] = {}
        for record in predictions:
            if record.uuid:
                by_uuid[record.uuid] = record
            if record.query_idx is not None:
                by_query_idx[record.query_idx] = record
        for sample in samples:
            record = None
            if sample.uuid:
                record = by_uuid.get(sample.uuid)
            if record is None and sample.query_idx is not None:
                record = by_query_idx.get(sample.query_idx)
            if record is not None:
                sample.predictions = record.predictions

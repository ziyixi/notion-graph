from __future__ import annotations

from collections import defaultdict
from threading import Lock

DEFAULT_HISTOGRAM_BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10)


def _sanitize_label_value(raw: str) -> str:
    return raw.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._histograms: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, object]] = {}

    def inc_counter(
        self,
        name: str,
        labels: dict[str, str] | None = None,
        amount: float = 1.0,
    ) -> None:
        key = self._labels_key(name, labels)
        with self._lock:
            self._counters[key] += amount

    def observe_histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        buckets: tuple[float, ...] = DEFAULT_HISTOGRAM_BUCKETS,
    ) -> None:
        key = self._labels_key(name, labels)
        with self._lock:
            item = self._histograms.get(key)
            if item is None:
                item = {
                    "buckets": buckets,
                    "bucket_counts": {bucket: 0 for bucket in buckets},
                    "inf_count": 0,
                    "sum": 0.0,
                    "count": 0,
                }
                self._histograms[key] = item

            for bucket in item["buckets"]:
                if value <= bucket:
                    item["bucket_counts"][bucket] += 1
            item["inf_count"] += 1
            item["sum"] += value
            item["count"] += 1

    def render_prometheus(self) -> str:
        lines: list[str] = []

        with self._lock:
            counter_keys = sorted(self._counters.keys())
            histogram_keys = sorted(self._histograms.keys())

            if counter_keys:
                rendered_names: set[str] = set()
                for name, _labels in counter_keys:
                    if name in rendered_names:
                        continue
                    lines.append(f"# TYPE {name} counter")
                    rendered_names.add(name)

                for name, labels in counter_keys:
                    value = self._counters[(name, labels)]
                    lines.append(f"{name}{self._labels_to_text(labels)} {value}")

            if histogram_keys:
                rendered_hist_names: set[str] = set()
                for name, _labels in histogram_keys:
                    if name in rendered_hist_names:
                        continue
                    lines.append(f"# TYPE {name} histogram")
                    rendered_hist_names.add(name)

                for name, labels in histogram_keys:
                    item = self._histograms[(name, labels)]
                    bucket_counts = item["bucket_counts"]
                    running = 0
                    for bucket in item["buckets"]:
                        running += bucket_counts[bucket]
                        bucket_labels = labels + (("le", str(bucket)),)
                        lines.append(
                            f"{name}_bucket{self._labels_to_text(bucket_labels)} {running}"
                        )
                    inf_labels = labels + (("le", "+Inf"),)
                    lines.append(
                        f"{name}_bucket{self._labels_to_text(inf_labels)} {item['inf_count']}"
                    )
                    lines.append(f"{name}_sum{self._labels_to_text(labels)} {item['sum']}")
                    lines.append(f"{name}_count{self._labels_to_text(labels)} {item['count']}")

        return "\n".join(lines) + ("\n" if lines else "")

    def _labels_key(
        self,
        name: str,
        labels: dict[str, str] | None,
    ) -> tuple[str, tuple[tuple[str, str], ...]]:
        normalized_labels = tuple(sorted((labels or {}).items()))
        return (name, normalized_labels)

    def _labels_to_text(self, labels: tuple[tuple[str, str], ...]) -> str:
        if not labels:
            return ""
        body = ",".join(f'{key}="{_sanitize_label_value(value)}"' for key, value in labels)
        return "{" + body + "}"


metrics_registry = MetricsRegistry()

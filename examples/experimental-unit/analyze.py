"""Recompute the descriptive results of the synthetic nested-fields example."""
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean


def summarize(path: Path) -> dict:
    """Give each animal equal weight. Also show the different field-weighted result."""
    measurements = defaultdict(list)
    group_by_animal = {}
    seen_fields = set()
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or []) != {"animal_id", "field_id", "group", "stained_area_pct"}:
            raise ValueError("Expected animal_id, field_id, group and stained_area_pct")
        for row in reader:
            animal, field, group = row["animal_id"], row["field_id"], row["group"]
            if not animal or not field or group not in {"control", "treated"}:
                raise ValueError(f"Invalid identity or group on line {reader.line_num}")
            if (animal, field) in seen_fields:
                raise ValueError(f"Duplicate field {field} for animal {animal}")
            if group_by_animal.setdefault(animal, group) != group:
                raise ValueError(f"Animal {animal} appears in two groups")
            value = float(row["stained_area_pct"])
            if not math.isfinite(value) or not 0 <= value <= 100:
                raise ValueError(f"Invalid percentage on line {reader.line_num}")
            seen_fields.add((animal, field))
            measurements[animal].append(value)

    groups = {}
    for group in ("control", "treated"):
        animals = sorted(animal for animal in measurements if group_by_animal[animal] == group)
        if not animals:
            raise ValueError(f"No animals in group {group}")
        individual = {animal: mean(measurements[animal]) for animal in animals}
        fields = [value for animal in animals for value in measurements[animal]]
        groups[group] = {
            "animals": len(animals),
            "fields": len(fields),
            "animal_means_pct": individual,
            "animal_weighted_mean_pct": mean(individual.values()),
            "field_weighted_mean_pct": mean(fields),
        }

    return {
        "groups": groups,
        "treated_minus_control_pp": (
            groups["treated"]["animal_weighted_mean_pct"]
            - groups["control"]["animal_weighted_mean_pct"]
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, nargs="?", default=Path(__file__).with_name("fields.csv"))
    print(json.dumps(summarize(parser.parse_args().csv), ensure_ascii=False, indent=2))

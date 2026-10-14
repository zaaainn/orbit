"""Rebuild the demo logistic-regression model from the bundled synthetic XLSX.

Uses only Python's standard library so the training artifact is reproducible
without installing a package. The model remains a synthetic-data classroom demo.
Run from this folder: python train_audience_model.py
"""
from __future__ import annotations

import json
import math
import random
import statistics
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

BASE = Path(__file__).resolve().parent
WORKBOOK = BASE / "social_campaign_audience_dataset.xlsx"
OUTPUT = BASE / "trained-model.js"
SEED = 205
L2 = 0.05

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
NUMERIC = ["age", "active_hour", "log_followers", "engagement_rate_pct", "posts_per_week"]
BINARY = ["interest_wellness", "interest_sustainability", "interest_design", "interest_travel", "interest_food"]
TOPIC_TARGETS = {
    "coffee": "interested_specialty_coffee",
    "wellness": "interest_wellness",
    "sustainability": "interest_sustainability",
    "design": "interest_design",
    "travel": "interest_travel",
    "food": "interest_food",
}
CATEGORIES = [
    ("gender", "gender"),
    ("location", "location"),
    ("primary_platform", "platform"),
    ("preferred_format", "format"),
]


def excel_col_index(reference: str) -> int:
    value = 0
    for char in reference:
        if not char.isalpha():
            break
        value = value * 26 + ord(char.upper()) - 64
    return value - 1


def read_rows(path: Path) -> list[dict[str, object]]:
    with zipfile.ZipFile(path) as book:
        sheet = ET.fromstring(book.read("xl/worksheets/sheet1.xml"))
        strings: list[str] = []
        if "xl/sharedStrings.xml" in book.namelist():
            shared = ET.fromstring(book.read("xl/sharedStrings.xml"))
            strings = ["".join(part.text or "" for part in item.findall(".//m:t", NS)) for item in shared.findall("m:si", NS)]
        parsed: list[list[object]] = []
        for row in sheet.findall(".//m:sheetData/m:row", NS):
            cells: list[object] = []
            for cell in row.findall("m:c", NS):
                index = excel_col_index(cell.attrib.get("r", "A1"))
                while len(cells) <= index:
                    cells.append(None)
                value = cell.find("m:v", NS)
                if cell.attrib.get("t") == "s" and value is not None:
                    cells[index] = strings[int(value.text or "0")]
                elif cell.attrib.get("t") == "inlineStr":
                    cells[index] = "".join(part.text or "" for part in cell.findall(".//m:t", NS))
                elif value is not None:
                    text = value.text or ""
                    try:
                        number = float(text)
                        cells[index] = int(number) if number.is_integer() else number
                    except ValueError:
                        cells[index] = text
            parsed.append(cells)
    if not parsed:
        raise ValueError("The workbook's first sheet is empty.")
    header = [str(value or "") for value in parsed[0]]
    rows = [dict(zip(header, row)) for row in parsed[1:] if row and row[0] is not None]
    required = {"age", "active_hour", "followers", "engagement_rate_pct", "posts_per_week", "interested_specialty_coffee", *BINARY, *(field for field, _ in CATEGORIES)}
    missing = required.difference(header)
    if missing:
        raise ValueError("Dataset is missing required fields: " + ", ".join(sorted(missing)))
    return rows


def feature_names(rows: list[dict[str, object]]) -> tuple[list[str], dict[str, list[str]]]:
    levels = {field: sorted({str(row[field]) for row in rows}) for field, _ in CATEGORIES}
    names = ["age", *BINARY, "active_hour", "log_followers", "engagement_rate_pct", "posts_per_week"]
    for field, suffix in CATEGORIES:
        names.extend(f"{suffix}_{value}" for value in levels[field])
    return names, levels


def raw_features(row: dict[str, object], names: list[str], levels: dict[str, list[str]]) -> list[float]:
    values = [float(row["age"]), *(float(row[name]) for name in BINARY), float(row["active_hour"]), math.log1p(float(row["followers"])), float(row["engagement_rate_pct"]), float(row["posts_per_week"])]
    for field, suffix in CATEGORIES:
        values.extend(1.0 if str(row[field]) == level else 0.0 for level in levels[field])
    if len(values) != len(names):
        raise ValueError("Feature names and values do not match.")
    return values


def standardize(train: list[list[float]], other: list[list[float]], numeric_positions: set[int]) -> tuple[list[list[float]], list[list[float]], list[float], list[float]]:
    means: list[float] = []
    stds: list[float] = []
    for index in range(len(train[0])):
        column = [row[index] for row in train]
        mean = statistics.fmean(column) if index in numeric_positions else 0.0
        std = statistics.pstdev(column) if index in numeric_positions else 1.0
        if std < 1e-12:
            std = 1.0
        means.append(mean)
        stds.append(std)
    def transform(matrix: list[list[float]]) -> list[list[float]]:
        return [[(value - means[index]) / stds[index] for index, value in enumerate(row)] for row in matrix]
    return transform(train), transform(other), means, stds


def sigmoid(value: float) -> float:
    value = max(-35.0, min(35.0, value))
    return 1.0 / (1.0 + math.exp(-value))


def fit_logistic(x: list[list[float]], y: list[int]) -> tuple[list[float], float]:
    width = len(x[0])
    weights = [0.0] * width
    bias = 0.0
    rate = 0.12
    for _ in range(1200):
        grad = [0.0] * width
        grad_bias = 0.0
        for row, label in zip(x, y):
            error = sigmoid(sum(a * b for a, b in zip(row, weights)) + bias) - label
            grad_bias += error
            for index, value in enumerate(row):
                grad[index] += error * value
        scale = 1.0 / len(y)
        for index in range(width):
            grad[index] = grad[index] * scale + L2 * weights[index]
        grad_bias *= scale
        change = max([abs(rate * grad_bias), *(abs(rate * value) for value in grad)])
        weights = [weight - rate * delta for weight, delta in zip(weights, grad)]
        bias -= rate * grad_bias
        if change < 1e-8:
            break
    return weights, bias


def stratified_split(labels: list[int]) -> tuple[list[int], list[int]]:
    rng = random.Random(SEED)
    train: list[int] = []
    holdout: list[int] = []
    for label in (0, 1):
        indices = [index for index, value in enumerate(labels) if value == label]
        rng.shuffle(indices)
        cut = int(len(indices) * 0.8)
        train.extend(indices[:cut])
        holdout.extend(indices[cut:])
    rng.shuffle(train)
    rng.shuffle(holdout)
    return train, holdout


def fit_target(rows: list[dict[str, object]], names: list[str], raw: list[list[float]], target: str) -> tuple[dict[str, object], list[float]]:
    # Never include a label as one of its own input features.
    keep = [index for index, name in enumerate(names) if name != target]
    feature_names = [names[index] for index in keep]
    x = [[row[index] for index in keep] for row in raw]
    numeric_positions = {index for index, name in enumerate(feature_names) if name in NUMERIC}
    labels = [int(row[target]) for row in rows]
    train_indices, holdout_indices = stratified_split(labels)
    train_x, holdout_x, means, stds = standardize(
        [x[index] for index in train_indices],
        [x[index] for index in holdout_indices],
        numeric_positions,
    )
    weights, bias = fit_logistic(train_x, [labels[index] for index in train_indices])
    probabilities = [sigmoid(sum(a * b for a, b in zip(row, weights)) + bias) for row in holdout_x]
    model = {
        "algorithm": "Logistic regression (L2, batch gradient descent)",
        "target": target,
        "features": feature_names,
        "scaler": {"columns": [name for name in feature_names if name in NUMERIC], "means": means, "stds": stds},
        "weights": weights,
        "bias": bias,
        "training": {"trainN": len(train_indices), "seed": SEED, "l2": L2, "source": WORKBOOK.name},
        "holdout": evaluate([labels[index] for index in holdout_indices], probabilities),
    }
    return model, probabilities


def predict_cluster(cluster: dict[str, object], names: list[str], levels: dict[str, list[str]], model: dict[str, object]) -> float:
    cluster_row: dict[str, object] = {
        "age": cluster["avgAge"],
        "active_hour": cluster["avgActiveHour"],
        "followers": cluster["avgFollowers"],
        "engagement_rate_pct": cluster["avgEngagement"],
        "posts_per_week": cluster["postsPerWeek"],
        "gender": cluster["gender"],
        "location": cluster["topLocation"],
        "primary_platform": cluster["topPlatform"],
        "preferred_format": cluster["topFormat"],
    }
    cluster_row.update({name: value for name, value in zip(BINARY, cluster["interestShares"])})
    cluster_row["interested_specialty_coffee"] = 0
    raw = raw_features(cluster_row, names, levels)
    model_features = model["features"]
    features = [raw[names.index(name)] for name in model_features]
    scaler = model["scaler"]
    means, stds = scaler["means"], scaler["stds"]
    scaled = [(value - means[index]) / stds[index] for index, value in enumerate(features)]
    return sigmoid(sum(a * b for a, b in zip(scaled, model["weights"])) + model["bias"])


def evaluate(labels: list[int], probabilities: list[float]) -> dict[str, float | int]:
    predictions = [int(value >= 0.5) for value in probabilities]
    tp = sum(y == 1 and p == 1 for y, p in zip(labels, predictions))
    tn = sum(y == 0 and p == 0 for y, p in zip(labels, predictions))
    fp = sum(y == 0 and p == 1 for y, p in zip(labels, predictions))
    fn = sum(y == 1 and p == 0 for y, p in zip(labels, predictions))
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    specificity = tn / max(1, tn + fp)
    return {
        "n": len(labels),
        "accuracy": round(100 * (tp + tn) / len(labels), 1),
        "precision": round(100 * precision, 1),
        "recall": round(100 * recall, 1),
        "f1": round(100 * 2 * precision * recall / max(1e-12, precision + recall), 1),
        "balancedAccuracy": round(100 * (recall + specificity) / 2, 1),
        "baselineAccuracy": round(100 * max(labels.count(0), labels.count(1)) / len(labels), 1),
        "brier": round(sum((p - y) ** 2 for y, p in zip(labels, probabilities)) / len(labels), 4),
    }


def main() -> None:
    rows = read_rows(WORKBOOK)
    names, levels = feature_names(rows)
    raw = [raw_features(row, names, levels) for row in rows]
    models: dict[str, dict[str, object]] = {}
    for topic, target in TOPIC_TARGETS.items():
        models[topic], _ = fit_target(rows, names, raw, target)
    existing = OUTPUT.read_text(encoding="utf-8")
    marker = "window.ORBIT_MODEL="
    if not existing.startswith(marker):
        raise ValueError("Unexpected trained-model.js format; refusing to overwrite it.")
    payload = json.loads(existing[len(marker):].rstrip().rstrip(";"))
    payload["profiles"] = len(rows)
    payload["topicModels"] = models
    payload["logistic"] = models["coffee"]
    for cluster in payload.get("clusters", []):
        predictions = [predict_cluster(cluster, names, levels, models[topic]) for topic in TOPIC_TARGETS]
        cluster["predictedInterestShares"] = [round(value, 4) for value in predictions]
        cluster["predictedCoffeeRate"] = round(predictions[0] * 100, 1)
        cluster["predictionMethod"] = "Logistic regression; representative cluster profile"
    OUTPUT.write_text(marker + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(json.dumps({"profiles": len(rows), "topics": {topic: model["holdout"] for topic, model in models.items()}, "clusterPredictions": {cluster["name"]: [round(value * 100, 1) for value in cluster["predictedInterestShares"]] for cluster in payload["clusters"]}}, indent=2))


if __name__ == "__main__":
    main()

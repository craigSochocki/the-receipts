"""Writing the pipeline's CSV and JSON files the way every step always has."""
import csv
import json


def write_json(path, content):
    with open(path, 'w') as f:
        json.dump(content, f, indent=1)


def write_csv(path, rows, fieldnames=None):
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def text_or_none(amount):
    return None if amount is None else str(amount)


def text_or_blank(amount):
    return '' if amount is None else str(amount)

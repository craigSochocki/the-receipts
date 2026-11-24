"""Reading and writing the pipeline's CSV and JSON files the way every step always has."""

import json

import yaml


def read_json(path):
    with open(path) as f:
        return json.load(f)


def read_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def write_json(path, content):
    with open(path, 'w') as f:
        json.dump(content, f, indent=1)


def text_or_none(amount):
    return None if amount is None else str(amount)


def text_or_blank(amount):
    return '' if amount is None else str(amount)

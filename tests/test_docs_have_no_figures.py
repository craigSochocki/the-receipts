"""The reference docs describe code and method, never results.

Results change with every FEC snapshot, so they live in data/source/baseline.json
and the dataset; the evidence behind each rule is in research/. STATUS.md, research/
and the onboarding tour are dated records and may carry figures.
"""

import ast
import io
import re
import tokenize

from receipts.common.settings import repo_root

ROOT = repo_root()
REFERENCE_DOCS = ('AGENTS.md', 'README.md', 'architecture.md', 'methodology.md')

FIGURE = re.compile(
    r'\$\s?(?!0\b)\d'  # dollar amounts; "$0" states a rule, not a result
    r'|\b\d{1,3}(?:,\d{3})+\b'  # 1,234-style counts
    r'|\b\d+(?:\.\d+)?\s?%(?![a-z])'  # percentages, not printf/ssh placeholders
    r'|\b[0-9a-f]{32}\b'  # md5s
    r'|\b(?!(?:19|20)\d\d\b)\d+\s+'
    r'(?:rows|people|members|persons|races|committees|candidates|filings|groups)\b'
)

# Formats and rules written as numbers: neither is a result.
ALLOWED = {
    ('receipts/domain/money.py', "'2500', '1234.56', '$1,000'"),
    ('receipts/domain/money.py', "',' gives 1,234.50"),
}


def doc_lines(path):
    yield from enumerate(path.read_text().split('\n'), 1)


def yaml_comments(path):
    for n, line in doc_lines(path):
        if '#' in line:
            yield n, line[line.index('#') :]


def comments_and_docstrings(path):
    source = path.read_text()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            yield token.start[0], token.string
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            docstring = ast.get_docstring(node, clean=False)
            if docstring:
                first = node.body[0].lineno
                for offset, line in enumerate(docstring.split('\n')):
                    yield first + offset, line


def sources():
    yield from ((ROOT / name, doc_lines) for name in REFERENCE_DOCS)
    yield ROOT / 'config.yaml', yaml_comments
    yield from (
        (path, comments_and_docstrings) for path in sorted((ROOT / 'receipts').rglob('*.py'))
    )


def figures():
    for path, lines in sources():
        name = path.relative_to(ROOT).as_posix()
        for n, text in lines(path):
            if FIGURE.search(text) and not any(
                name == allowed_file and snippet in text for allowed_file, snippet in ALLOWED
            ):
                yield f'{name}:{n}: {text.strip()}'


def test_reference_docs_and_code_comments_carry_no_result_figures():
    found = list(figures())
    assert not found, 'move these to baseline.json or research/:\n' + '\n'.join(found)


def test_every_allowed_exception_still_exists():
    stale = [
        (name, snippet) for name, snippet in ALLOWED if snippet not in (ROOT / name).read_text()
    ]
    assert not stale, f'remove these exceptions, the text is gone: {stale}'

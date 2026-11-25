"""Pure, metadata-driven file processing; no database or UI dependencies."""
import csv
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd


def read_file(content, filename, rules):
    fmt = rules['format']
    if fmt not in ('csv', 'xlsx') or Path(filename).suffix.lower() != '.' + fmt:
        raise ValueError('Unexpected file format')
    start, footer = rules.get('start_row', 1), rules.get('trailing_rows', 0)
    if start < 1 or footer < 0:
        raise ValueError('Invalid row configuration')
    if fmt == 'csv':
        options = dict(delimiter=rules.get('delimiter') or ',', quotechar=rules.get('text_identifier') or '"')
        rows = list(csv.reader(StringIO(content.decode('utf-8-sig')), **options))
    else:
        rows = pd.read_excel(BytesIO(content), header=None, dtype=str, keep_default_na=False).values.tolist()
    location = rules.get('validate_location')
    if location is not None:
        if not 1 <= location <= len(rows) or not any(str(rules['validate_value']) in str(cell) for cell in rows[location - 1]):
            raise ValueError('File identity validation failed')
    rows = rows[start - 1:len(rows) - footer if footer else None]
    if not rows:
        raise ValueError('Missing header row')
    headers = [str(c).strip() for c in rows[0]]
    if len(headers) != len(set(headers)):
        raise ValueError('Duplicate column names')
    if any(len(row) != len(headers) for row in rows[1:]):
        raise ValueError('Inconsistent column count')
    return pd.DataFrame(rows[1:], columns=headers).fillna('')


def resolve_mapping(df, mapping):
    """Named/positional columns, literals, templates and amount fallback."""
    if isinstance(mapping, list):
        if not mapping:
            raise ValueError('Empty mapping list')
        result = resolve_mapping(df, mapping[0]).replace(r'^\s*$', pd.NA, regex=True)
        for item in mapping[1:]:
            result = result.fillna(resolve_mapping(df, item).replace(r'^\s*$', pd.NA, regex=True))
        return result.fillna('')
    if re.fullmatch(r'\([1-9]\d*\)', mapping):
        return df.iloc[:, int(mapping[1:-1]) - 1]
    if mapping == '{now}':
        return pd.Series(date.today().isoformat(), index=df.index)
    if mapping.startswith('{') and mapping.endswith('}'):
        template = mapping[1:-1]
        return df.apply(lambda row: re.sub(r'\[([^]]+)\]', lambda m: str(row[m[1]]), template), axis=1)
    return df[mapping]


def money(value):
    text = str(value).strip().replace(',', '').replace(' ', '').replace('R', '').replace('$', '')
    if text.startswith('(') and text.endswith(')'):
        text = '-' + text[1:-1]
    try:
        amount = Decimal(text)
        if not amount.is_finite() or abs(amount) >= Decimal('1000000000000000') or amount != amount.quantize(Decimal('0.0001')):
            raise ValueError('Amount outside DECIMAL(19,4) precision')
        return amount.quantize(Decimal('0.0001'))
    except InvalidOperation as exc:
        raise ValueError(f'Invalid amount: {value}') from exc


def extract_account(reference, description):
    for text in (reference, description):
        match = re.search(r'\b\d{10}\b', text)
        if match:
            return match[0]
    return None


def ingest_file(content, filename, metadata):
    exceptions = metadata['exceptions']
    if exceptions.get('password_protected'):
        raise ValueError('Encrypted files are not supported in this demo')
    df = read_file(content, filename, metadata['structure'])
    for rule in exceptions.get('row_exclusions') or []:
        df = df.loc[df[rule['col']].astype(str).str.strip() != str(rule['value'])]
    mappings = metadata['mappings']
    result = pd.DataFrame(index=df.index)
    result['effective_date'] = pd.to_datetime(resolve_mapping(df, mappings['eff_date']), format=mappings.get('date_format') or 'ISO8601', errors='raise').dt.date
    result['description'] = resolve_mapping(df, mappings['desc']).astype(str).str.strip()
    result['reference'] = resolve_mapping(df, mappings['account']).astype(str).str.strip()
    result['amount'] = resolve_mapping(df, mappings['amount']).map(money)
    result['account_no'] = [extract_account(r, d) for r, d in zip(result.reference, result.description)]
    if result.empty or result.effective_date.isna().any():
        raise ValueError('No transactions or missing effective date')
    if result.description.str.len().gt(200).any() or result.reference.str.len().gt(100).any():
        raise ValueError('Description or reference exceeds database length')
    batch_totals(result, exceptions)
    return result.reset_index(drop=True)


def batch_totals(df, rules):
    debit, credit = rules['dr_trans'], rules['cr_trans']
    if {debit, credit} != {'>0', '<0'}:
        raise ValueError('Debit and credit rules must be opposite signs')
    positive = sum((x for x in df.amount if x > 0), Decimal(0))
    negative = sum((x for x in df.amount if x < 0), Decimal(0))
    return (positive, negative) if debit == '>0' else (negative, positive)

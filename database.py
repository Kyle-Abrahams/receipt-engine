"""SQL Server access. Each import commits once or rolls back completely."""
import json
import os
from contextlib import contextmanager

import pyodbc

from ingestion import batch_totals


@contextmanager
def connection():
    conn = pyodbc.connect(os.environ['DB_CONNECTION_STRING'], autocommit=False)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_batch_types():
    with connection() as conn:
        return {row[0]: row[1] for row in conn.cursor().execute('SELECT type_id, description FROM dbo.batch_type ORDER BY type_id')}


def get_metadata(type_id):
    with connection() as conn:
        row = conn.cursor().execute('SELECT [json] FROM dbo.batch_type WHERE type_id = ?', type_id).fetchone()
        if row is None:
            raise ValueError('Unknown batch type')
        return json.loads(row[0])


def import_batch(type_id, filename, df, metadata):
    debit, credit = batch_totals(df, metadata['exceptions'])
    with connection() as conn:
        cursor = conn.cursor()
        batch_id = cursor.execute('''INSERT dbo.batch (file_type, file_name, num_trans, cr_value, dr_value)
            OUTPUT INSERTED.id VALUES (?, ?, ?, ?, ?)''', type_id, filename, len(df), credit, debit).fetchone()[0]
        rows = [(batch_id, r.effective_date, r.description, r.reference, r.account_no, r.amount) for r in df.itertuples(index=False)]
        cursor.executemany('''INSERT dbo.import_temp (batch_id, eff_date, description, reference, account_no, amount)
            VALUES (?, ?, ?, ?, ?, ?)''', rows)
        cursor.execute('EXEC dbo.spImportTransactions ?', batch_id)
        return batch_id


def get_transactions(batch_id):
    with connection() as conn:
        cursor = conn.cursor().execute('''SELECT t.effective_date, t.description, t.reference, t.amount,
            a.account_no, a.source_system, t.allocation_status, t.match_method
            FROM dbo.transactions t LEFT JOIN dbo.accounts a ON a.id = t.account_id
            WHERE t.batch_id = ? ORDER BY t.id''', batch_id)
        columns = [c[0] for c in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

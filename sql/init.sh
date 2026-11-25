#!/bin/bash
set -euo pipefail
run() { /opt/mssql-tools18/bin/sqlcmd -S db -U sa -C -b "$@"; }
run -Q "IF DB_ID('ReceiptDemo') IS NULL CREATE DATABASE ReceiptDemo;"
if ! run -d ReceiptDemo -Q "IF OBJECT_ID('dbo.batch_type') IS NULL THROW 50000, 'Not initialized', 1;" >/dev/null 2>&1; then
    # Run initialization atomically, including GO-separated scripts.
    { echo 'SET XACT_ABORT ON; BEGIN TRANSACTION;'; echo GO; cat /scripts/schema.sql /scripts/procedures.sql /scripts/seed.sql; echo GO; echo 'COMMIT;'; echo GO; } | run -d ReceiptDemo
fi

CREATE OR ALTER PROCEDURE dbo.spImportTransactions @BatchID INT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    -- Caller owns the transaction. Serialize processing of the same batch.
    DECLARE @Expected INT;
    SELECT @Expected = num_trans FROM dbo.batch WITH (UPDLOCK, HOLDLOCK) WHERE id = @BatchID;
    IF @Expected IS NULL OR @Expected <> (SELECT COUNT(*) FROM dbo.import_temp WHERE batch_id = @BatchID)
        THROW 50001, 'Missing batch or incorrect staging row count', 1;
    IF EXISTS (SELECT 1 FROM dbo.transactions WHERE batch_id = @BatchID)
        THROW 50002, 'Batch already imported', 1;

    -- Rank candidates by configured priority. Never guess between tied accounts.
    ;WITH candidates AS (
        SELECT t.id AS staging_id, r.account_id, r.reference_type,
            DENSE_RANK() OVER (PARTITION BY t.id ORDER BY r.priority) AS match_rank
        FROM dbo.import_temp t
        JOIN dbo.account_reference r ON r.reference IN (t.reference, t.account_no)
        WHERE t.batch_id = @BatchID AND r.reference <> ''
    ), best AS (
        SELECT staging_id, COUNT(DISTINCT account_id) AS account_count,
            MIN(account_id) AS account_id, MIN(reference_type) AS match_method
        FROM candidates WHERE match_rank = 1 GROUP BY staging_id
    )
    INSERT dbo.transactions (batch_id, effective_date, description, reference,
        extracted_account, amount, account_id, allocation_status, match_method)
    SELECT t.batch_id, t.eff_date, t.description, t.reference, t.account_no, t.amount,
        CASE WHEN b.account_count = 1 THEN b.account_id END,
        CASE WHEN b.account_count = 1 THEN 'ALLOCATED'
             WHEN b.account_count > 1 THEN 'AMBIGUOUS' ELSE 'UNMATCHED' END,
        CASE WHEN b.account_count = 1 THEN b.match_method END
    FROM dbo.import_temp t LEFT JOIN best b ON b.staging_id = t.id
    WHERE t.batch_id = @BatchID;

    DELETE dbo.import_temp WHERE batch_id = @BatchID;
END;
GO

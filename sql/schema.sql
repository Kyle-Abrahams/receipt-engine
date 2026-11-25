CREATE TABLE dbo.batch_type (
    type_id INT IDENTITY PRIMARY KEY,
    description NVARCHAR(100) NOT NULL UNIQUE,
    [json] NVARCHAR(MAX) NOT NULL CHECK (ISJSON([json]) = 1)
);
CREATE TABLE dbo.batch (
    id INT IDENTITY PRIMARY KEY,
    file_type INT NOT NULL REFERENCES dbo.batch_type(type_id),
    file_name NVARCHAR(255) NOT NULL,
    create_date DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    num_trans INT NOT NULL CHECK (num_trans > 0),
    cr_value DECIMAL(19,4) NOT NULL,
    dr_value DECIMAL(19,4) NOT NULL
);
CREATE TABLE dbo.accounts (
    id INT IDENTITY PRIMARY KEY,
    account_no VARCHAR(50) NOT NULL UNIQUE,
    account_name NVARCHAR(100) NOT NULL,
    source_system VARCHAR(30) NOT NULL
);
CREATE TABLE dbo.account_reference (
    account_id INT NOT NULL REFERENCES dbo.accounts(id),
    reference NVARCHAR(100) NOT NULL,
    reference_type VARCHAR(20) NOT NULL,
    priority INT NOT NULL CHECK (priority > 0),
    PRIMARY KEY (reference, account_id, reference_type)
);
CREATE TABLE dbo.import_temp (
    id INT IDENTITY PRIMARY KEY,
    batch_id INT NOT NULL REFERENCES dbo.batch(id),
    eff_date DATE NOT NULL,
    description NVARCHAR(200) NOT NULL,
    reference NVARCHAR(100) NOT NULL,
    account_no VARCHAR(50) NULL,
    amount DECIMAL(19,4) NOT NULL
);
CREATE INDEX IX_import_temp_batch ON dbo.import_temp(batch_id);
CREATE TABLE dbo.transactions (
    id INT IDENTITY PRIMARY KEY,
    batch_id INT NOT NULL REFERENCES dbo.batch(id),
    effective_date DATE NOT NULL,
    description NVARCHAR(200) NOT NULL,
    reference NVARCHAR(100) NOT NULL,
    extracted_account VARCHAR(50) NULL,
    amount DECIMAL(19,4) NOT NULL,
    account_id INT NULL REFERENCES dbo.accounts(id),
    allocation_status VARCHAR(20) NOT NULL,
    match_method VARCHAR(20) NULL,
    CHECK ((allocation_status = 'ALLOCATED' AND account_id IS NOT NULL AND match_method IS NOT NULL)
        OR (allocation_status IN ('UNMATCHED','AMBIGUOUS') AND account_id IS NULL AND match_method IS NULL))
);
CREATE INDEX IX_transactions_batch ON dbo.transactions(batch_id);
GO

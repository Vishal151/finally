-- FinAlly seed data

INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at)
VALUES ('default', 10000.0, '2025-01-01T00:00:00Z');

INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES
    ('seed-wl-aapl',  'default', 'AAPL',  '2025-01-01T00:00:00Z'),
    ('seed-wl-googl', 'default', 'GOOGL', '2025-01-01T00:00:00Z'),
    ('seed-wl-msft',  'default', 'MSFT',  '2025-01-01T00:00:00Z'),
    ('seed-wl-amzn',  'default', 'AMZN',  '2025-01-01T00:00:00Z'),
    ('seed-wl-tsla',  'default', 'TSLA',  '2025-01-01T00:00:00Z'),
    ('seed-wl-nvda',  'default', 'NVDA',  '2025-01-01T00:00:00Z'),
    ('seed-wl-meta',  'default', 'META',  '2025-01-01T00:00:00Z'),
    ('seed-wl-jpm',   'default', 'JPM',   '2025-01-01T00:00:00Z'),
    ('seed-wl-v',     'default', 'V',     '2025-01-01T00:00:00Z'),
    ('seed-wl-nflx',  'default', 'NFLX',  '2025-01-01T00:00:00Z');

-- Todos tabell för att-göra-listor
-- Kör denna SQL i Supabase SQL Editor

CREATE TABLE IF NOT EXISTS todos (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    uppgift TEXT NOT NULL,
    kategori TEXT DEFAULT 'backlog', -- 'idag', 'ai', 'träning', 'praktiskt', 'innehåll', 'backlog'
    prioritet TEXT DEFAULT 'normal', -- 'hög', 'normal', 'låg'
    status TEXT DEFAULT 'öppen', -- 'öppen', 'påbörjad', 'klar', 'avbruten'
    skapad_av TEXT,
    tilldelad_till TEXT,
    deadline DATE,
    anteckning TEXT,
    skapad_datum TIMESTAMPTZ DEFAULT NOW(),
    uppdaterad_datum TIMESTAMPTZ DEFAULT NOW(),
    klar_datum TIMESTAMPTZ
);

-- Index för snabbare queries
CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
CREATE INDEX IF NOT EXISTS idx_todos_kategori ON todos(kategori);
CREATE INDEX IF NOT EXISTS idx_todos_prioritet ON todos(prioritet);
CREATE INDEX IF NOT EXISTS idx_todos_skapad_datum ON todos(skapad_datum DESC);

-- Row Level Security (RLS)
ALTER TABLE todos ENABLE ROW LEVEL SECURITY;

-- Policy: Alla kan läsa och skriva (för nu - anpassa efter behov)
CREATE POLICY "Enable all access for todos" ON todos
    FOR ALL USING (true);

-- Trigger för att uppdatera uppdaterad_datum automatiskt
CREATE OR REPLACE FUNCTION update_todos_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.uppdaterad_datum = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER todos_updated_at
    BEFORE UPDATE ON todos
    FOR EACH ROW
    EXECUTE FUNCTION update_todos_timestamp();

-- View för öppna todos (status = 'öppen' eller 'påbörjad')
CREATE OR REPLACE VIEW öppna_todos AS
SELECT *
FROM todos
WHERE status IN ('öppen', 'påbörjad')
ORDER BY
    CASE prioritet
        WHEN 'hög' THEN 1
        WHEN 'normal' THEN 2
        WHEN 'låg' THEN 3
    END,
    skapad_datum DESC;

-- View för dagens todos
CREATE OR REPLACE VIEW dagens_todos AS
SELECT *
FROM todos
WHERE kategori = 'idag' AND status IN ('öppen', 'påbörjad')
ORDER BY
    CASE prioritet
        WHEN 'hög' THEN 1
        WHEN 'normal' THEN 2
        WHEN 'låg' THEN 3
    END;

COMMENT ON TABLE todos IS 'Att-göra-lista för Gideon AI-assistenten';
COMMENT ON COLUMN todos.kategori IS 'idag, ai, träning, praktiskt, innehåll, backlog';
COMMENT ON COLUMN todos.prioritet IS 'hög, normal, låg';
COMMENT ON COLUMN todos.status IS 'öppen, påbörjad, klar, avbruten';

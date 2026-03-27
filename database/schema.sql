-- Gideon Database Schema för Supabase
-- Kör detta i Supabase SQL Editor

-- Aktivera pgvector extension för AI-minne
CREATE EXTENSION IF NOT EXISTS vector;

-- Leads-tabell (företag ni pratar med)
CREATE TABLE IF NOT EXISTS leads (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    företag TEXT NOT NULL,
    kontaktperson TEXT,
    email TEXT,
    telefon TEXT,
    status TEXT DEFAULT 'ny', -- ny, kontaktad, intresserad, förhandling, kund, ej_intresserad
    tjänst TEXT, -- chatbot, voice_agent, crm, bokningssystem
    anteckningar TEXT,
    skapad_av TEXT, -- discord user id
    skapad_datum TIMESTAMP DEFAULT NOW(),
    uppdaterad_datum TIMESTAMP DEFAULT NOW()
);

-- Reflektioner (dagliga/veckovisa reflektioner)
CREATE TABLE IF NOT EXISTS reflektioner (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    användare TEXT NOT NULL, -- discord user id eller namn
    datum DATE DEFAULT CURRENT_DATE,
    typ TEXT DEFAULT 'daglig', -- daglig, veckovis, månatlig
    text TEXT NOT NULL,
    lärdomar TEXT[], -- array med key learnings
    nästa_steg TEXT[], -- action items
    sentiment TEXT, -- positiv, neutral, negativ (AI kan analysera)
    skapad_datum TIMESTAMP DEFAULT NOW()
);

-- KPIs (nyckeltal ni vill följa)
CREATE TABLE IF NOT EXISTS kpis (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    namn TEXT NOT NULL, -- "hemsidor_sålda", "intäkt", "möten_bokade"
    värde NUMERIC NOT NULL,
    enhet TEXT, -- "kr", "st", "%"
    kategori TEXT, -- "försäljning", "ekonomi", "produktivitet"
    datum DATE DEFAULT CURRENT_DATE,
    anteckning TEXT,
    skapad_av TEXT,
    skapad_datum TIMESTAMP DEFAULT NOW()
);

-- Långtidsminne med pgvector (AI kommer ihåg allt)
CREATE TABLE IF NOT EXISTS minnen (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    användare TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding vector(1536), -- OpenAI text-embedding-3-small dimension
    metadata JSONB, -- flexibel metadata (datum, typ, relevans, etc)
    skapad_datum TIMESTAMP DEFAULT NOW()
);

-- Index för snabbare sökning
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_skapad_datum ON leads(skapad_datum DESC);
CREATE INDEX IF NOT EXISTS idx_reflektioner_datum ON reflektioner(datum DESC);
CREATE INDEX IF NOT EXISTS idx_reflektioner_användare ON reflektioner(användare);
CREATE INDEX IF NOT EXISTS idx_kpis_datum ON kpis(datum DESC);
CREATE INDEX IF NOT EXISTS idx_kpis_namn ON kpis(namn);
CREATE INDEX IF NOT EXISTS idx_minnen_användare ON minnen(användare);

-- Vector similarity index för snabb AI-sökning
CREATE INDEX IF NOT EXISTS idx_minnen_embedding ON minnen
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Funktion för att automatiskt uppdatera uppdaterad_datum
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.uppdaterad_datum = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger för leads
CREATE TRIGGER update_leads_updated_at BEFORE UPDATE ON leads
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security (RLS) - kan aktiveras senare för säkerhet
-- ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE reflektioner ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE kpis ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE minnen ENABLE ROW LEVEL SECURITY;

-- Views för snabb översikt
CREATE OR REPLACE VIEW aktiva_leads AS
SELECT * FROM leads
WHERE status NOT IN ('kund', 'ej_intresserad')
ORDER BY uppdaterad_datum DESC;

CREATE OR REPLACE VIEW denna_vecka_kpis AS
SELECT * FROM kpis
WHERE datum >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY datum DESC;

-- Exempeldata för testning (kan tas bort senare)
INSERT INTO leads (företag, kontaktperson, status, tjänst, anteckningar, skapad_av) VALUES
('Hotel Östersund', 'Magnus Jonsson', 'kund', 'chatbot', 'Referenskund - chatbot live!', 'isak'),
('Jamtproj', 'Magnus Jonsson', 'intresserad', 'chatbot', 'Potentiell första betalande kund', 'isak')
ON CONFLICT DO NOTHING;

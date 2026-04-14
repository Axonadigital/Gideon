-- Schema för conversation memory system
-- Korttidsminne: Detaljerade meddelanden
-- Långtidsminne: AI-genererade sammanfattningar

-- Conversation messages (korttidsminne)
CREATE TABLE IF NOT EXISTS conversation_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    session_id UUID NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Index för snabba queries
    INDEX idx_user_session (user_id, session_id),
    INDEX idx_created_at (created_at DESC)
);

-- Session summaries (långtidsminne)
CREATE TABLE IF NOT EXISTS conversation_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    session_id UUID NOT NULL UNIQUE,
    session_start TIMESTAMPTZ NOT NULL,
    session_end TIMESTAMPTZ NOT NULL,

    -- Strukturerad sammanfattning
    summary TEXT NOT NULL,
    key_topics TEXT[] DEFAULT '{}',
    decisions TEXT[] DEFAULT '{}',
    leads_mentioned TEXT[] DEFAULT '{}',
    meetings_mentioned TEXT[] DEFAULT '{}',
    next_steps TEXT[] DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Index
    INDEX idx_user_summaries (user_id, session_start DESC),
    INDEX idx_session (session_id)
);

-- Cleanup policy: Radera messages äldre än 7 dagar (sammanfattningar finns kvar)
-- Kör manuellt eller med cron:
-- DELETE FROM conversation_messages WHERE created_at < NOW() - INTERVAL '7 days';

-- Cleanup policy: Radera summaries äldre än 90 dagar
-- DELETE FROM conversation_summaries WHERE created_at < NOW() - INTERVAL '90 days';

-- Production-ready schema for PostgreSQL/MySQL
-- Supports user management, article storage, predictions, and analytics

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE TABLE sources (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) UNIQUE NOT NULL,
    credibility_score DECIMAL(5,2) CHECK (credibility_score >= 0 AND credibility_score <= 100),
    category VARCHAR(50), -- news, blog, satire, unknown
    verified BOOLEAN DEFAULT FALSE,
    reliability_rating VARCHAR(20), -- high, medium, low
    flagged_count INTEGER DEFAULT 0
);

CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    url TEXT,
    headline TEXT NOT NULL,
    content TEXT,
    source_id INTEGER REFERENCES sources(id),
    author VARCHAR(100),
    published_date TIMESTAMP,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_html TEXT
);

CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id),
    user_id INTEGER REFERENCES users(id),
    prediction VARCHAR(20) CHECK (prediction IN ('Real', 'Fake', 'Partially Correct')),
    confidence_score DECIMAL(5,2),
    trust_score INTEGER CHECK (trust_score >= 0 AND trust_score <= 100),
    model_version VARCHAR(20),
    processing_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    explanation JSONB, -- Stores detailed breakdown
    source_type VARCHAR(20) DEFAULT 'ml' -- 'fact_db' or 'ml'
);

CREATE TABLE keywords (
    id SERIAL PRIMARY KEY,
    word VARCHAR(100) UNIQUE NOT NULL,
    category VARCHAR(50), -- clickbait, sensational, political, etc.
    weight DECIMAL(3,2) DEFAULT 1.0,
    frequency_count INTEGER DEFAULT 1
);

CREATE TABLE search_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    query TEXT NOT NULL,
    result_id INTEGER REFERENCES predictions(id),
    ip_address INET,
    searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE feedback (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER REFERENCES predictions(id),
    user_id INTEGER REFERENCES users(id),
    is_accurate BOOLEAN,
    user_correction VARCHAR(20),
    comments TEXT,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE fact_checks (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id),
    fact_check_source VARCHAR(100),
    fact_check_url TEXT,
    verdict VARCHAR(50),
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_articles_url ON articles(url);
CREATE INDEX idx_predictions_created ON predictions(created_at);
CREATE INDEX idx_predictions_result ON predictions(prediction);
CREATE INDEX idx_search_history_user ON search_history(user_id);
CREATE INDEX idx_feedback_prediction ON feedback(prediction_id);

-- Insert default clickbait/sensational keywords
INSERT INTO keywords (word, category, weight) VALUES 
('shocking', 'clickbait', 0.8),
('unbelievable', 'clickbait', 0.9),
('you won''t believe', 'clickbait', 1.0),
('doctors hate this', 'clickbait', 0.9),
('secret trick', 'clickbait', 0.7),
('what happens next', 'clickbait', 0.8),
('conspiracy', 'sensational', 0.6),
('cover-up', 'sensational', 0.7),
('exposed', 'sensational', 0.5),
('breaking', 'sensational', 0.4);
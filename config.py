import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://user:pass@localhost/fakenewsdb'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ML Model Settings
    MODEL_PATH = 'model/ensemble_model.pkl'
    VECTORIZER_PATH = 'model/vectorizer.pkl'
    MODEL_VERSION = 'v1.0.0'
    
    # API Keys (load from environment)
    GOOGLE_FACT_CHECK_API_KEY = os.environ.get('GOOGLE_FACT_CHECK_API_KEY')
    NEWSAPI_KEY = os.environ.get('NEWSAPI_KEY')  # For multi-source news verification (free at newsapi.org)
    
    # App Settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    REQUEST_TIMEOUT = 30
    
    # Trust Score Weights
    TRUST_WEIGHTS = {
        'ml_confidence': 0.4,
        'source_credibility': 0.25,
        'clickbait_score': 0.15,
        'similarity_check': 0.10,
        'fact_check': 0.10
    }

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True
    }

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///dev.db'
# AI Fake News Detection Platform

Production-ready full-stack application for automated fake news detection using ensemble machine learning.

## Features

- **Multi-factor Analysis**: Combines ML predictions, source credibility, and semantic analysis
- **Ensemble ML**: Logistic Regression + Random Forest + Naive Bayes voting classifier
- **Trust Scoring**: 0-100 weighted score incorporating 5 verification dimensions
- **Real-time Dashboard**: Chart.js visualizations with trend analysis
- **Duplicate Detection**: Cosine similarity matching against historical articles
- **REST API**: Token-authenticated endpoints for bulk processing

## Features (Updated)

- **Multi-Source News Verification**: Verifies news against 4+ trusted sources (Reuters, BBC, AP, NYT, etc.) via NewsAPI
- **Trusted Sources Display**: Shows which reputable sites verified or contradicted the claim
- **Fact Database**: Universal truths and known contradictions (e.g. sun rises east, earth round)
- **Ensemble ML**: Logistic Regression + Random Forest + Naive Bayes
- **Trust Scoring**: 0-100 with Real / Partially Correct / Fake verdict

### News Verification (Optional)

To enable verification from trusted news sites:
1. Get a free API key at [newsapi.org](https://newsapi.org/register)
2. Create a `.env` file: `NEWSAPI_KEY=your_key_here`
3. Or set the environment variable: `set NEWSAPI_KEY=your_key` (Windows)

Without NEWSAPI_KEY, the app uses ML + fact database only.

## Quick Start

### 1. Setup Environment

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m nltk.downloader stopwords
cp .env.example .env   # Add your NEWSAPI_KEY for news verification
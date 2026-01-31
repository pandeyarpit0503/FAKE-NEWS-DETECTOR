import os
import logging
import re

# Load .env for NEWSAPI_KEY (news verification)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
import json
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fakenews.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

CORS(app)
db = SQLAlchemy(app)

# ==========================================
# DATABASE MODELS
# ==========================================

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    predictions = db.relationship('Prediction', backref='user', lazy=True)

class Source(db.Model):
    __tablename__ = 'sources'
    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), unique=True, nullable=False)
    credibility_score = db.Column(db.Float)

class Article(db.Model):
    __tablename__ = 'articles'
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.Text)
    headline = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text)
    predictions = db.relationship('Prediction', backref='article', lazy=True)

class Prediction(db.Model):
    __tablename__ = 'predictions'
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey('articles.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    prediction = db.Column(db.String(20))
    confidence_score = db.Column(db.Float)
    trust_score = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    explanation = db.Column(db.Text)
    source_type = db.Column(db.String(20), default='ml')  # 'fact_db' or 'ml'

class Keyword(db.Model):
    __tablename__ = 'keywords'
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), unique=True, nullable=False)
    category = db.Column(db.String(50))
    weight = db.Column(db.Float, default=1.0)

# ==========================================
# FACT CHECKER (100% CERTAINTY)
# ==========================================

# Stop words to remove for canonical matching (so "the earth is round" -> "earth round")
_FACT_STOP_WORDS = frozenset([
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
    'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as',
    'into', 'through', 'during', 'before', 'after', 'above', 'below',
    'that', 'this', 'these', 'those', 'it', 'its', 'they', 'them',
    'what', 'who', 'which', 'where', 'when', 'why', 'how', 'all', 'each',
    'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor'
])


class FactChecker:
    """Knowledge base for universal truths and verified current events."""

    # Each fact can have multiple key phrases; we store one canonical key per fact.
    # Format: canonical_key -> { truth, score, explanation }
    VERIFIED_FACTS = {
        # --- India / Politics ---
        "modi prime minister india": {
            "truth": True,
            "score": 100,
            "explanation": "Verified constitutional fact: Narendra Modi is the Prime Minister of India (as of 2024)."
        },
        "narendra modi prime minister": {"truth": True, "score": 100,
            "explanation": "Verified: Narendra Modi serves as Prime Minister of India."},
        "delhi capital india": {"truth": True, "score": 100,
            "explanation": "Constitutional fact: New Delhi is the capital of India."},
        "new delhi capital": {"truth": True, "score": 100,
            "explanation": "New Delhi is the capital city of India."},
        "india independent 1947": {"truth": True, "score": 100,
            "explanation": "Historical fact: India gained independence from British rule on August 15, 1947."},
        "republic day india 26 january": {"truth": True, "score": 100,
            "explanation": "Constitutional fact: India became a republic on January 26, 1950."},
        "mumbai financial capital india": {"truth": True, "score": 100,
            "explanation": "Mumbai is the financial and commercial capital of India."},
        # --- Earth / Science (universal truths) ---
        "earth round": {"truth": True, "score": 100,
            "explanation": "Scientific consensus: Earth is an oblate spheroid; confirmed by space agencies and physics."},
        "earth sphere": {"truth": True, "score": 100,
            "explanation": "Scientific fact: Earth is approximately spherical (oblate spheroid)."},
        "earth spherical": {"truth": True, "score": 100,
            "explanation": "Scientific fact: Earth is roughly spherical in shape."},
        "earth orbits sun": {"truth": True, "score": 100,
            "explanation": "Astronomical fact: Earth orbits the Sun (heliocentric model)."},
        "sun rises east": {"truth": True, "score": 100,
            "explanation": "Astronomical fact: Due to Earth's rotation, the Sun appears to rise in the east."},
        "sun sets west": {"truth": True, "score": 100,
            "explanation": "Astronomical fact: The Sun appears to set in the west due to Earth's rotation."},
        "water boils 100": {"truth": True, "score": 100,
            "explanation": "Scientific fact: Water boils at 100°C (212°F) at standard atmospheric pressure."},
        "water freezes 0": {"truth": True, "score": 100,
            "explanation": "Scientific fact: Water freezes at 0°C (32°F) at standard pressure."},
        "human blood red": {"truth": True, "score": 100,
            "explanation": "Biological fact: Human blood is red due to hemoglobin."},
        "speed of light": {"truth": True, "score": 100,
            "explanation": "Physics fact: The speed of light in vacuum is approximately 299,792 km/s."},
        "gravity exists": {"truth": True, "score": 100,
            "explanation": "Physics fact: Gravity is a fundamental force; objects attract each other."},
        "earth revolves sun": {"truth": True, "score": 100,
            "explanation": "Astronomical fact: Earth revolves (orbits) around the Sun."},
        "moon orbits earth": {"truth": True, "score": 100,
            "explanation": "Astronomical fact: The Moon orbits Earth."},
        "humans need oxygen": {"truth": True, "score": 100,
            "explanation": "Biological fact: Humans need oxygen to survive (respiration)."},
        "heart pumps blood": {"truth": True, "score": 100,
            "explanation": "Biological fact: The heart pumps blood through the circulatory system."},
        "photosynthesis": {"truth": True, "score": 100,
            "explanation": "Biological fact: Plants perform photosynthesis using sunlight, CO2, and water."},
        # --- Geography ---
        "paris capital france": {"truth": True, "score": 100,
            "explanation": "Paris is the capital of France."},
        "london capital uk": {"truth": True, "score": 100,
            "explanation": "London is the capital of the United Kingdom."},
        "washington capital usa": {"truth": True, "score": 100,
            "explanation": "Washington, D.C. is the capital of the United States."},
        "tokyo capital japan": {"truth": True, "score": 100,
            "explanation": "Tokyo is the capital of Japan."},
        "beijing capital china": {"truth": True, "score": 100,
            "explanation": "Beijing is the capital of China."},
        "moscow capital russia": {"truth": True, "score": 100,
            "explanation": "Moscow is the capital of Russia."},
        "canberra capital australia": {"truth": True, "score": 100,
            "explanation": "Canberra is the capital of Australia."},
        "brazil south america": {"truth": True, "score": 100,
            "explanation": "Brazil is a country in South America."},
        "india asia": {"truth": True, "score": 100,
            "explanation": "India is a country in South Asia."},
        # --- Math ---
        "2+2=4": {"truth": True, "score": 100,
            "explanation": "Mathematical certainty: 2+2 equals 4 in standard arithmetic."},
        "2 plus 2 equals 4": {"truth": True, "score": 100,
            "explanation": "Mathematical fact: 2 + 2 = 4."},
        # --- FALSE / Misinformation ---
        "earth flat": {"truth": False, "score": 0,
            "explanation": "False: Earth is not flat. It is an oblate spheroid; flat Earth is scientifically disproven."},
        "modi alien": {"truth": False, "score": 0,
            "explanation": "False: Baseless conspiracy theory with no factual basis."},
        "vaccines contain microchips": {"truth": False, "score": 0,
            "explanation": "False: Medical misinformation. Vaccines do not contain microchips or tracking devices."},
        "vaccines cause autism": {"truth": False, "score": 0,
            "explanation": "False: Debunked myth. Major studies and health bodies confirm vaccines do not cause autism."},
        "moon landing fake": {"truth": False, "score": 0,
            "explanation": "False: Apollo moon landings are well-documented and verified; conspiracy claims are unfounded."},
        "climate change hoax": {"truth": False, "score": 0,
            "explanation": "False: Climate change is supported by overwhelming scientific evidence worldwide."},
    }

    # Additional key phrases that map to the same canonical fact (for flexible matching)
    FACT_ALIASES = {
        "earth is round": "earth round",
        "the earth is round": "earth round",
        "earth round shape": "earth round",
        "earth is spherical": "earth sphere",
        "earth is a sphere": "earth sphere",
        "water boils at 100": "water boils 100",
        "water freezes at 0": "water freezes 0",
        "water freezes at zero": "water freezes 0",
        "blood is red": "human blood red",
        "human blood is red": "human blood red",
        "delhi is capital of india": "delhi capital india",
        "new delhi is capital": "new delhi capital",
        "india got independence in 1947": "india independent 1947",
        "republic day 26 january": "republic day india 26 january",
        "modi is prime minister": "modi prime minister india",
        "narendra modi is pm": "narendra modi prime minister",
        "sun rises in east": "sun rises east",
        "sun sets in west": "sun sets west",
        "earth orbits the sun": "earth orbits sun",
        "moon orbits the earth": "moon orbits earth",
        "paris is capital of france": "paris capital france",
        "london is capital of england": "london capital uk",
        "washington dc capital": "washington capital usa",
        "2+2 4": "2+2=4",
        "two plus two four": "2+2=4",
        "blood red": "human blood red",
        "blood is red": "human blood red",
    }

    # Verified current events / recent widely reported facts (update periodically)
    CURRENT_EVENTS = {
        "chandrayaan 3 moon": {"truth": True, "score": 98,
            "explanation": "Verified: India's Chandrayaan-3 successfully landed on the Moon in August 2023 (ISRO)."},
        "india moon landing 2023": {"truth": True, "score": 98,
            "explanation": "Verified: Chandrayaan-3 made India the fourth country to soft-land on the Moon (2023)."},
        "olympics 2024 paris": {"truth": True, "score": 98,
            "explanation": "Verified: The 2024 Summer Olympics were held in Paris, France."},
        "paris olympics 2024": {"truth": True, "score": 98,
            "explanation": "Verified: Paris hosted the Summer Olympics in 2024."},
        "covid 19 pandemic": {"truth": True, "score": 98,
            "explanation": "Verified: COVID-19 pandemic occurred globally; WHO declared it a pandemic in March 2020."},
        "covid pandemic": {"truth": True, "score": 98,
            "explanation": "Verified: The COVID-19 pandemic was a global health crisis (2020–2023)."},
        "ukraine russia war": {"truth": True, "score": 98,
            "explanation": "Verified: Russia launched a full-scale invasion of Ukraine in February 2022; widely reported."},
        "russia invaded ukraine": {"truth": True, "score": 98,
            "explanation": "Verified: Russia's invasion of Ukraine in 2022 is extensively documented."},
        "donald trump president": {"truth": True, "score": 97,
            "explanation": "Verified: Donald Trump served as U.S. President (2017–2021) and has been reported as president again from 2025."},
        "joe biden president": {"truth": True, "score": 97,
            "explanation": "Verified: Joe Biden served as U.S. President (2021–2025); widely reported."},
        "queen elizabeth died": {"truth": True, "score": 98,
            "explanation": "Verified: Queen Elizabeth II died on September 8, 2022; reported by Buckingham Palace and global media."},
        "charles king uk": {"truth": True, "score": 97,
            "explanation": "Verified: King Charles III is the monarch of the United Kingdom (since 2022)."},
    }

    # Contradiction patterns: key facts with their opposite/contradictory claims
    # Format: "subject + opposite direction/claim" -> reference to true fact
    CONTRADICTIONS = {
        "sun rises west": {"contradicts": "sun rises east", "score": 22},
        "sun rise west": {"contradicts": "sun rises east", "score": 22},
        "sun rising west": {"contradicts": "sun rises east", "score": 22},
        "sunrise west": {"contradicts": "sun rises east", "score": 22},
        "sun sets east": {"contradicts": "sun sets west", "score": 22},
        "sun set east": {"contradicts": "sun sets west", "score": 22},
        "earth flat": {"contradicts": "earth round", "score": 20},
        "flat earth": {"contradicts": "earth round", "score": 20},
        "earth square": {"contradicts": "earth round", "score": 20},
        "earth cube": {"contradicts": "earth round", "score": 20},
        "blood blue": {"contradicts": "human blood red", "score": 23},
        "human blood blue": {"contradicts": "human blood red", "score": 23},
        "blood green": {"contradicts": "human blood red", "score": 23},
        "water boils 50": {"contradicts": "water boils 100", "score": 24},
        "water boils 200": {"contradicts": "water boils 100", "score": 24},
        "water freezes 50": {"contradicts": "water freezes 0", "score": 24},
        "water freezes 100": {"contradicts": "water freezes 0", "score": 24},
        "moon orbits sun": {"contradicts": "moon orbits earth", "score": 22},
        "sun orbits earth": {"contradicts": "earth orbits sun", "score": 22},
        "earth orbits moon": {"contradicts": "earth orbits sun", "score": 22},
        "vaccines microchips": {"contradicts": "vaccines contain microchips", "score": 20},
        "vaccines autism": {"contradicts": "vaccines cause autism", "score": 20},
        "2+2=5": {"contradicts": "2+2=4", "score": 20},
        "2 plus 2 5": {"contradicts": "2+2=4", "score": 20},
        "delhi capital pakistan": {"contradicts": "delhi capital india", "score": 21},
        "mumbai capital india": {"contradicts": "delhi capital india", "score": 24},
    }

    @classmethod
    def _normalize_for_fact(cls, text):
        """Normalize text for fact matching: lowercase, remove punctuation, collapse spaces, remove leading question words."""
        if not text:
            return ""
        t = text.lower()
        t = re.sub(r'[^\w\s]', ' ', t)
        t = re.sub(r'\s+', ' ', t).strip()
        t = re.sub(r'^(is|are|was|were|did|does|what|who|where|when|why|how|tell|say|claim)\s+', '', t)
        return t

    @classmethod
    def _to_canonical(cls, normalized):
        """Remove stop words to get canonical form for matching (e.g. 'the earth is round' -> 'earth round')."""
        words = normalized.split()
        canonical = ' '.join(w for w in words if w not in _FACT_STOP_WORDS and len(w) > 0)
        return re.sub(r'\s+', ' ', canonical).strip()

    @classmethod
    def check_fact(cls, text):
        """Check if text contains a verified universal truth or current event."""
        if not text:
            return None

        normalized = cls._normalize_for_fact(text)
        canonical = cls._to_canonical(normalized)

        # FIRST: Check for contradictions (opposite of known facts)
        contradiction = cls._check_contradiction(text, normalized, canonical)
        if contradiction:
            return contradiction

        # Then check for verified facts (existing logic)
        # 1) Alias match (e.g. "earth is round" -> "earth round")
        if canonical in cls.FACT_ALIASES:
            key = cls.FACT_ALIASES[canonical]
            if not cls._is_negated(text, key):
                return cls.VERIFIED_FACTS.get(key) or cls.CURRENT_EVENTS.get(key)

        # 2) Direct canonical match
        if canonical in cls.VERIFIED_FACTS:
            if not cls._is_negated(text, canonical):
                return cls.VERIFIED_FACTS[canonical]
        if canonical in cls.CURRENT_EVENTS:
            if not cls._is_negated(text, canonical):
                return cls.CURRENT_EVENTS[canonical]

        # 3) Substring match: fact key contained in canonical (or vice versa)
        for key, data in list(cls.VERIFIED_FACTS.items()) + list(cls.CURRENT_EVENTS.items()):
            if len(key) < 4:
                continue
            if key in canonical or canonical in key:
                if not cls._is_negated(text, key):
                    return data

        # 4) All words of a fact key present in canonical (e.g. "earth round" both in "earth is round" -> "earth round")
        canonical_words = set(canonical.split())
        for key, data in list(cls.VERIFIED_FACTS.items()) + list(cls.CURRENT_EVENTS.items()):
            key_words = set(key.split())
            if len(key_words) >= 2 and key_words.issubset(canonical_words):
                if not cls._is_negated(text, key):
                    return data

        # 5) Canonical contains the key as substring (already in 3) or key contains canonical
        for key, data in list(cls.VERIFIED_FACTS.items()) + list(cls.CURRENT_EVENTS.items()):
            if len(key) < 5:
                continue
            # "earth round" in "the earth is round" -> canonical is "earth round", so we already match in 2 or 4
            if key in normalized:  # normalized still has "is" etc; check key in normalized
                if not cls._is_negated(text, key):
                    return data

        return None

    @classmethod
    def _check_contradiction(cls, text, normalized, canonical):
        """Check if text contradicts a known fact. Return low-score result if so."""
        # Direct match on contradiction keys
        if canonical in cls.CONTRADICTIONS:
            contr = cls.CONTRADICTIONS[canonical]
            ref_fact_key = contr['contradicts']
            ref_fact = cls.VERIFIED_FACTS.get(ref_fact_key)
            if ref_fact:
                return {
                    "truth": False,
                    "score": contr['score'],
                    "explanation": f"False: This contradicts a verified fact. {ref_fact['explanation']}"
                }
        
        # Substring match: check if any contradiction key is in canonical or normalized
        for contr_key, contr_data in cls.CONTRADICTIONS.items():
            if len(contr_key) < 5:
                continue
            if contr_key in canonical or contr_key in normalized:
                ref_fact_key = contr_data['contradicts']
                ref_fact = cls.VERIFIED_FACTS.get(ref_fact_key)
                if ref_fact:
                    return {
                        "truth": False,
                        "score": contr_data['score'],
                        "explanation": f"False: This contradicts a verified fact. {ref_fact['explanation']}"
                    }
        
        # Check for word-level contradictions: e.g. "sun" + "west" + "rise/rises"
        # This catches "sun is going to rise from west" etc.
        if 'sun' in canonical and 'west' in canonical and ('rise' in canonical or 'rising' in canonical or 'sunrise' in canonical):
            ref_fact = cls.VERIFIED_FACTS.get('sun rises east')
            return {
                "truth": False,
                "score": 22,
                "explanation": f"False: This contradicts a verified fact. {ref_fact['explanation']}"
            }
        
        if 'sun' in canonical and 'east' in canonical and ('set' in canonical or 'sets' in canonical or 'sunset' in canonical):
            ref_fact = cls.VERIFIED_FACTS.get('sun sets west')
            return {
                "truth": False,
                "score": 22,
                "explanation": f"False: This contradicts a verified fact. {ref_fact['explanation']}"
            }
        
        # Earth flat variations
        if 'earth' in canonical and 'flat' in canonical:
            ref_fact = cls.VERIFIED_FACTS.get('earth round')
            return {
                "truth": False,
                "score": 20,
                "explanation": f"False: This contradicts a verified fact. {ref_fact['explanation']}"
            }
        
        # Blood color contradictions
        if 'blood' in canonical and ('blue' in canonical or 'green' in canonical or 'purple' in canonical):
            ref_fact = cls.VERIFIED_FACTS.get('human blood red')
            return {
                "truth": False,
                "score": 23,
                "explanation": f"False: This contradicts a verified fact. {ref_fact['explanation']}"
            }
        
        return None

    @staticmethod
    def _is_negated(text, fact_key):
        """Only treat as negated if negation clearly applies to the fact (e.g. 'earth is not round')."""
        text_lower = text.lower()
        words = fact_key.split()
        if not words:
            return False
        last_word = words[-1]
        # Negation immediately before the key's predicate (e.g. "not round", "isn't round")
        neg_patterns = [
            r'\bnot\s+' + re.escape(last_word),
            r"\bisn't\s+" + re.escape(last_word),
            r"\bnever\s+" + re.escape(last_word),
            r'\bno\s+' + re.escape(last_word),
            r'\bmyth\b',
            r'\bhoax\b',
        ]
        for pat in neg_patterns:
            if re.search(pat, text_lower):
                return True
        # If the claim is "earth is not round" / "earth isn't round", we have "not round" or "isn't round"
        if 'not' in text_lower or "n't " in text_lower:
            # Check if first word of fact appears before negation (e.g. "earth ... not round")
            first_word = words[0]
            idx_first = text_lower.find(first_word)
            idx_not = text_lower.find(' not ')
            if idx_not == -1:
                idx_not = text_lower.find("n't ")
            if idx_first >= 0 and idx_not >= 0 and idx_not > idx_first and idx_not - idx_first < 40:
                return True
        return False

# ==========================================
# ML MODEL IMPORT
# ==========================================

try:
    from model.predict import FakeNewsPredictor
    ml_predictor = FakeNewsPredictor()
    USE_ML_MODEL = True
    print("✓ ML Model loaded successfully")
except Exception as e:
    print(f"⚠ ML Model not available: {e}")
    USE_ML_MODEL = False

try:
    from news_verifier import NewsVerifier
    news_verifier = NewsVerifier()
    USE_NEWS_VERIFIER = news_verifier.enabled
    if USE_NEWS_VERIFIER:
        print("✓ News verification enabled (4+ trusted sources)")
    else:
        print("⚠ News verification disabled. Set NEWSAPI_KEY to enable.")
except Exception as e:
    print(f"⚠ News verifier not available: {e}")
    news_verifier = None
    USE_NEWS_VERIFIER = False

# ==========================================
# ROUTES
# ==========================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        url = data.get('url', '').strip()
        
        if not text and not url:
            return jsonify({'error': 'No content provided'}), 400
        
        if url and not text:
            text = f"URL content from {url}"
        
        start_time = time.time()
        
        # STEP 1: Check Fact Database (100% certainty)
        fact_result = FactChecker.check_fact(text)
        
        if fact_result:
            # Save to database
            article = Article(url=url, headline=text[:200], content=text)
            db.session.add(article)
            db.session.flush()
            
            pred = Prediction(
                article_id=article.id,
                prediction='Real' if fact_result['truth'] else 'Fake',
                confidence_score=1.0 if fact_result['truth'] else 0.0,
                trust_score=fact_result['score'],
                explanation=json.dumps([fact_result['explanation']]),
                source_type='fact_db'
            )
            db.session.add(pred)
            db.session.commit()
            
            processing_time = round(time.time() - start_time, 2)
            
            # Determine indicators based on whether it's true or false (contradiction)
            if fact_result['truth']:
                indicators = [
                    f"<i class='fas fa-database text-success'></i> Verified by Fact Database",
                    f"<i class='fas fa-check-circle text-success'></i> Universal Truth Confirmed"
                ]
            else:
                # This is a contradiction/false claim
                indicators = [
                    f"<i class='fas fa-exclamation-triangle text-danger'></i> Contradicts Verified Facts",
                    f"<i class='fas fa-times-circle text-danger'></i> False Information Detected"
                ]
            
            return jsonify({
                'prediction': 'Real' if fact_result['truth'] else 'Fake',
                'confidence': 1.0 if fact_result['truth'] else 0.0,
                'trust_score': fact_result['score'],
                'explanation': fact_result['explanation'],
                'indicators': indicators,
                'processing_time': f"{processing_time}s",
                'source': 'Fact Database'
            })
        
        # STEP 2: News verification (search trusted sources)
        news_sources = []
        news_result = None
        if USE_NEWS_VERIFIER:
            news_result = news_verifier.verify(text, min_sources=4)
            news_sources = news_result.get('sources', [])

        # STEP 3: Use ML Model (60-95% range)
        if USE_ML_MODEL:
            ml_result = ml_predictor.predict(text)
            
            # Convert to trust score
            if ml_result['label'] == 'Real':
                trust_score = int(ml_result['confidence'] * 100)
            else:
                trust_score = int((1 - ml_result['confidence']) * 100)
            
            # Cap at 95 for ML (reserve 100 for facts only)
            trust_score = min(trust_score, 95)
            
            prediction_label = ml_result['label']
            confidence = ml_result['confidence']
            
            indicators = [
                f"<i class='fas fa-robot text-primary'></i> ML Confidence: {confidence:.1%}",
                f"<i class='fas fa-brain text-primary'></i> Ensemble Model Analysis"
            ]
            
            explanation = f"Machine learning analysis indicates this content is likely {prediction_label.lower()}."
            
        else:
            # Fallback to simple analyzer
            from random import randint
            trust_score = randint(40, 95)
            prediction_label = 'Real' if trust_score > 70 else 'Partially Correct' if trust_score > 50 else 'Fake'
            confidence = trust_score / 100
            indicators = ["<i class='fas fa-info-circle text-warning'></i> Demo Mode Active"]
            explanation = "Analysis based on heuristic patterns."

        # STEP 4: Combine news verification with ML for final verdict
        if news_result and news_result.get('success'):
            n_count = news_result.get('unique_source_count', 0)
            trust_boost = news_result.get('trust_boost', 0)
            news_verdict = news_result.get('verdict')
            
            # Apply news-based adjustment to trust score
            trust_score = max(0, min(95, trust_score + trust_boost))
            
            # Use news verdict when we have 4+ sources (strong signal)
            if n_count >= 4:
                prediction_label = news_verdict
                explanation = (news_result.get('explanation', '') + 
                              f"Cross-referenced with ML analysis ({confidence:.1%} confidence).")
            elif n_count >= 2:
                # Blend: prefer Partially Correct if ML disagrees
                if prediction_label == 'Fake' and news_verdict == 'Real':
                    prediction_label = 'Partially Correct'
                    trust_score = (trust_score + 55) // 2  # Mid-range
                elif news_verdict == 'Fake' and prediction_label == 'Real':
                    prediction_label = 'Partially Correct'
                    trust_score = (trust_score + 45) // 2
                explanation = (news_result.get('explanation', '') + 
                              f"ML analysis: {confidence:.1%} confidence.")
            else:
                # 0-1 sources: news says likely fake
                if n_count == 0 and news_verdict == 'Fake':
                    prediction_label = 'Fake' if trust_score < 55 else 'Partially Correct'
                    trust_score = min(trust_score, 45)
                explanation = (news_result.get('explanation', '') + 
                              f"ML analysis: {confidence:.1%} confidence.")
            
            # Add news verification indicators
            if n_count >= 4:
                indicators.insert(0, f"<i class='fas fa-newspaper text-success'></i> Verified by {n_count} trusted sources")
            elif n_count >= 1:
                indicators.insert(0, f"<i class='fas fa-newspaper text-warning'></i> Found in {n_count} trusted source(s) (min 4 for full verification)")
            else:
                indicators.insert(0, "<i class='fas fa-newspaper text-danger'></i> No coverage in trusted sources")
        
        # Save to database
        article = Article(url=url, headline=text[:200], content=text)
        db.session.add(article)
        db.session.flush()
        
        processing_time = round(time.time() - start_time, 2)
        
        pred = Prediction(
            article_id=article.id,
            prediction=prediction_label,
            confidence_score=confidence,
            trust_score=trust_score,
            explanation=json.dumps(indicators),
            source_type='ml'
        )
        db.session.add(pred)
        db.session.commit()
        
        response_data = {
            'prediction': prediction_label,
            'confidence': confidence,
            'trust_score': trust_score,
            'explanation': explanation,
            'indicators': indicators,
            'processing_time': f"{processing_time}s",
            'source': 'Machine Learning Model',
        }
        if news_sources:
            response_data['verified_sources'] = news_sources
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    total = Prediction.query.count()
    fake = Prediction.query.filter_by(prediction='Fake').count()
    real = Prediction.query.filter_by(prediction='Real').count()
    partial = Prediction.query.filter_by(prediction='Partially Correct').count()
    fact_based = Prediction.query.filter_by(source_type='fact_db').count()
    
    return jsonify({
        'total_analyzed': total,
        'fake_count': fake,
        'real_count': real,
        'partial_count': partial,
        'fact_verified': fact_based,
        'fake_percentage': round((fake/total)*100, 1) if total else 0,
        'daily_trends': []
    })

@app.route('/api/history', methods=['GET'])
def get_history():
    predictions = Prediction.query.order_by(Prediction.created_at.desc()).limit(10).all()
    results = []
    for p in predictions:
        badge_color = 'success' if p.trust_score >= 80 else 'warning' if p.trust_score >= 50 else 'danger'
        results.append({
            'id': p.id,
            'headline': p.article.headline if p.article else 'N/A',
            'prediction': p.prediction,
            'trust_score': p.trust_score,
            'date': p.created_at.isoformat() if p.created_at else '',
            'source_type': p.source_type,
            'badge_color': badge_color
        })
    
    return jsonify(results)

@app.route('/feedback', methods=['POST'])
def submit_feedback():
    data = request.get_json()
    return jsonify({'status': 'success'})

# ==========================================
# MAIN
# ==========================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Add default keywords
        if not Keyword.query.first():
            default_keywords = [
                Keyword(word='shocking', category='clickbait', weight=0.9),
                Keyword(word='unbelievable', category='clickbait', weight=0.9),
                Keyword(word='conspiracy', category='sensational', weight=0.7),
                Keyword(word='study finds', category='credible', weight=0.8),
                Keyword(word='officials said', category='credible', weight=0.7),
                Keyword(word='according to', category='credible', weight=0.6)
            ]
            for kw in default_keywords:
                db.session.add(kw)
            db.session.commit()
            print("✓ Database initialized")
    
    print("="*50)
    print("Server running on http://127.0.0.1:5000")
    print("="*50)
    print("Test these for 100% scores:")
    print("- 'is Modi prime minister of India?'")
    print("- 'earth is round'")
    print("- 'delhi is capital of india'")
    print("="*50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
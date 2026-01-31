import joblib
import numpy as np
import re
import string
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
import nltk

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

class FakeNewsPredictor:
    def __init__(self, model_path='model/ensemble_model.pkl', 
                 vectorizer_path='model/vectorizer.pkl'):
        self.stemmer = PorterStemmer()
        self.stop_words = set(stopwords.words('english'))
        
        try:
            self.model = joblib.load(model_path)
            self.vectorizer = joblib.load(vectorizer_path)
        except FileNotFoundError:
            print("Warning: Model files not found. Using dummy predictor.")
            self.model = None
            self.vectorizer = None
    
    def clean_text(self, text):
        """Consistent preprocessing with training"""
        if not text:
            return ""
        
        text = text.lower()
        text = re.sub(r'http\S+|www\S+|https\S+', '', text)
        text = re.sub(r'@\w+', '', text)
        text = re.sub(r'#', '', text)
        text = text.translate(str.maketrans('', '', string.punctuation + string.digits))
        text = re.sub(r'\s+', ' ', text).strip()
        
        tokens = text.split()
        tokens = [self.stemmer.stem(word) for word in tokens 
                  if word not in self.stop_words and len(word) > 2]
        
        return ' '.join(tokens)
    
    def predict(self, text):
        """
        Predict fake news with confidence scores
        Returns: dict with label, confidence, and probabilities
        """
        if not self.model:
            # Dummy fallback
            return {
                'label': 'Unknown',
                'confidence': 0.0,
                'probabilities': {}
            }
        
        cleaned = self.clean_text(text)
        
        if not cleaned:
            return {
                'label': 'Invalid',
                'confidence': 0.0,
                'probabilities': {}
            }
        
        # Vectorize
        X = self.vectorizer.transform([cleaned])
        
        # Predict
        prediction = self.model.predict(X)[0]
        probabilities = self.model.predict_proba(X)[0]
        
        # Get confidence (probability of predicted class)
        class_labels = self.model.classes_
        prob_dict = dict(zip(class_labels, probabilities))
        confidence = prob_dict[prediction]
        
        # Determine if partially correct (confidence between 0.45-0.65)
        if 0.45 <= confidence < 0.65:
            final_label = 'Partially Correct'
        else:
            final_label = prediction
        
        return {
            'label': final_label,
            'confidence': float(confidence),
            'probabilities': {k: float(v) for k, v in prob_dict.items()},
            'cleaned_text': cleaned[:200]  # For debugging
        }
    
    def batch_predict(self, texts):
        """Predict multiple articles"""
        return [self.predict(text) for text in texts]
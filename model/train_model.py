import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.pipeline import Pipeline
import joblib
import re
import string
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
import nltk
import os
import warnings
warnings.filterwarnings('ignore')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

class FakeNewsTrainer:
    def __init__(self):
        self.stemmer = PorterStemmer()
        self.stop_words = set(stopwords.words('english'))
        self.vectorizer = None
        self.model = None
        self.accuracy = 0
        
    def clean_text(self, text):
        if pd.isna(text):
            return ""
        
        text = str(text).lower()
        text = re.sub(r'http\S+|www\S+|https\S+', '', text)
        text = re.sub(r'@\w+', '', text)
        text = re.sub(r'#', '', text)
        text = text.translate(str.maketrans('', '', string.punctuation))
        text = re.sub(r'\d+', '', text)  # Remove numbers
        text = re.sub(r'\s+', ' ', text).strip()
        
        tokens = text.split()
        tokens = [self.stemmer.stem(word) for word in tokens 
                  if word not in self.stop_words and len(word) > 2]
        
        return ' '.join(tokens)
    
    def load_data(self):
        """Auto-detect and load best available dataset"""
        datasets = [
            'data/train.csv',           # Kaggle
            'data/liar_dataset.csv',    # LIAR  
            'data/large_dataset.csv',   # Large synthetic
            'data/fake_news_dataset.csv' # Small synthetic
        ]
        
        for dataset in datasets:
            if os.path.exists(dataset):
                print(f"Found dataset: {dataset}")
                
                if 'train.csv' in dataset:
                    return self.load_kaggle_data(dataset)
                elif 'liar' in dataset:
                    return self.load_liar_data(dataset)
                else:
                    return self.load_generic(dataset)
        
        raise FileNotFoundError("No dataset found! Run download_data.py first")
    
    def load_kaggle_data(self, path):
        df = pd.read_csv(path)
        df['text'] = df['title'].fillna('') + ' ' + df['text'].fillna('')
        df['label'] = df['label'].map({0: 'Real', 1: 'Fake'})
        return self._process_df(df)
    
    def load_liar_data(self, path):
        df = pd.read_csv(path)
        df.rename(columns={'statement': 'text'}, inplace=True)
        return self._process_df(df)
    
    def load_generic(self, path):
        df = pd.read_csv(path)
        return self._process_df(df)
    
    def _process_df(self, df):
        print(f"Raw dataset: {len(df)} articles")
        
        # Remove missing values
        df = df.dropna(subset=['text', 'label'])
        
        # Clean
        print("Preprocessing text (this may take a minute)...")
        df['cleaned_text'] = df['text'].apply(self.clean_text)
        df = df[df['cleaned_text'].str.len() > 5]
        
        # Only keep Real/Fake (remove Partially Correct if present)
        df = df[df['label'].isin(['Real', 'Fake'])]
        
        print(f"Final dataset: {len(df)} articles")
        print(f"Class distribution:\n{df['label'].value_counts()}")
        
        return df
    
    def train(self, df):
        X = df['cleaned_text']
        y = df['label']
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        print(f"\nTraining: {len(X_train)} | Testing: {len(X_test)}")
        
        # TF-IDF with better parameters for large datasets
        self.vectorizer = TfidfVectorizer(
            max_features=10000,      # More features for large data
            ngram_range=(1, 3),      # Include trigrams
            min_df=2,                # Ignore very rare words
            max_df=0.9,              # Ignore very common words
            sublinear_tf=True,       # Apply sublinear tf scaling
            use_idf=True
        )
        
        X_train_tfidf = self.vectorizer.fit_transform(X_train)
        X_test_tfidf = self.vectorizer.transform(X_test)
        
        print(f"Vectorized shape: {X_train_tfidf.shape}")
        
        # Advanced ensemble
        lr = LogisticRegression(max_iter=1000, C=1.0, class_weight='balanced')
        rf = RandomForestClassifier(
            n_estimators=200,        # More trees
            max_depth=50,
            min_samples_split=5,
            min_samples_leaf=2,
            class_weight='balanced',
            n_jobs=-1,               # Use all CPU cores
            random_state=42
        )
        nb = MultinomialNB(alpha=0.1)
        
        self.model = VotingClassifier(
            estimators=[('lr', lr), ('rf', rf), ('nb', nb)],
            voting='soft'
        )
        
        print("\nTraining ensemble model (this may take a few minutes)...")
        self.model.fit(X_train_tfidf, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test_tfidf)
        self.accuracy = accuracy_score(y_test, y_pred)
        
        print("\n" + "="*60)
        print(f"MODEL PERFORMANCE")
        print("="*60)
        print(f"Accuracy: {self.accuracy:.2%}")
        print("\nDetailed Report:")
        print(classification_report(y_test, y_pred))
        
        # Cross-validation for robustness
        print("Running 5-fold cross-validation...")
        cv_scores = cross_val_score(self.model, X_train_tfidf, y_train, cv=5)
        print(f"CV Accuracy: {cv_scores.mean():.2%} (+/- {cv_scores.std():.2%})")
        
        # Feature importance from Random Forest
        rf_model = self.model.named_estimators_['rf']
        feature_names = self.vectorizer.get_feature_names_out()
        importances = rf_model.feature_importances_
        top_idx = importances.argsort()[-10:][::-1]
        
        print("\nTop 10 Important Words:")
        for idx in top_idx:
            print(f"  {feature_names[idx]}: {importances[idx]:.4f}")
        
        return self.accuracy
    
    def save_model(self, model_dir='model'):
        if not os.path.exists(model_dir):
            os.makedirs(model_dir)
            
        joblib.dump(self.model, os.path.join(model_dir, 'ensemble_model.pkl'))
        joblib.dump(self.vectorizer, os.path.join(model_dir, 'vectorizer.pkl'))
        
        print(f"\n✓ Model and vectorizer saved to {model_dir}/")
        
        # Save model info
        info = {
            'accuracy': float(self.accuracy),
            'vectorizer_features': len(self.vectorizer.get_feature_names_out()),
            'models': ['LogisticRegression', 'RandomForest', 'NaiveBayes']
        }
        import json
        with open(os.path.join(model_dir, 'model_info.json'), 'w') as f:
            json.dump(info, f, indent=2)

if __name__ == "__main__":
    trainer = FakeNewsTrainer()
    
    try:
        df = trainer.load_data()
        trainer.train(df)
        trainer.save_model()
        
        print("\n✓ Training complete! Ready to use.")
        print("Run: python app.py")
        
    except Exception as e:
        print(f"\nError: {e}")
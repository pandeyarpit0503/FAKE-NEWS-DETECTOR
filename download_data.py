import pandas as pd
import requests
import zipfile
import io
import os

def download_liar_dataset():
    """
    Downloads LIAR dataset (12,836 labeled statements from Politifact)
    This is a real benchmark dataset used in research
    """
    print("Downloading LIAR dataset (real-world fake news)...")
    
    # Create data directory
    if not os.path.exists('data'):
        os.makedirs('data')
    
    # LIAR dataset URL (GitHub mirror)
    urls = {
        'train': 'https://raw.githubusercontent.com/Tariq60/LIAR-Plus/master/dataset/tsv/train.tsv',
        'test': 'https://raw.githubusercontent.com/Tariq60/LIAR-Plus/master/dataset/tsv/test.tsv',
        'valid': 'https://raw.githubusercontent.com/Tariq60/LIAR-Plus/master/dataset/tsv/valid.tsv'
    }
    
    all_data = []
    
    for split, url in urls.items():
        try:
            print(f"Downloading {split} set...")
            response = requests.get(url, timeout=30)
            
            # Parse TSV
            from io import StringIO
            df = pd.read_csv(StringIO(response.text), sep='\t', 
                           names=['id', 'label', 'statement', 'subject', 'speaker', 
                                  'job', 'state', 'party', 'barely_true', 'false', 
                                  'half_true', 'mostly_true', 'pants_on_fire', 'context'])
            
            # Simplify labels to Real/Fake
            label_map = {
                'true': 'Real',
                'mostly-true': 'Real',
                'half-true': 'Partially Correct',
                'barely-true': 'Fake',
                'false': 'Fake',
                'pants-fire': 'Fake'
            }
            
            df['label'] = df['label'].map(label_map)
            df = df[df['label'].isin(['Real', 'Fake'])]  # Only keep clear real/fake
            
            all_data.append(df[['statement', 'label']])
            print(f"  {split}: {len(df)} articles")
            
        except Exception as e:
            print(f"  Warning: Could not download {split}: {e}")
    
    # Combine all splits
    combined = pd.concat(all_data, ignore_index=True)
    combined.rename(columns={'statement': 'text'}, inplace=True)
    
    # Save
    combined.to_csv('data/liar_dataset.csv', index=False)
    print(f"\n✓ Dataset saved: {len(combined)} articles")
    print(f"  Real: {(combined['label']=='Real').sum()}")
    print(f"  Fake: {(combined['label']=='Fake').sum()}")
    
    return combined

def download_large_synthetic_dataset():
    """
    If LIAR download fails, create a larger synthetic dataset (1000 articles)
    """
    print("Creating large synthetic dataset...")
    
    real_templates = [
        "Government announces new {policy} with bipartisan support",
        "Study finds correlation between {factor} and {outcome}",
        "{Organization} reports quarterly earnings of ${amount}",
        "Scientists discover {discovery} in {location}",
        "Federal Reserve {action} interest rates by {percent}",
        "New research shows {topic} benefits mental health",
        "Parliament passes bill regarding {subject}",
        "Supreme Court rules on case involving {topic}",
        "International summit discusses {issue}",
        "Ministry of {department} releases new guidelines"
    ]
    
    fake_templates = [
        "Shocking: {person} exposed for {scandal}",
        "You won't believe what {celebrity} did with {object}",
        "Secret documents reveal {organization} covering up {event}",
        "Miracle cure for {disease} suppressed by doctors",
        "{Person} faked {event} to escape {consequence}",
        "Conspiracy theorists prove {belief} using {method}",
        "Doctors hate this one weird trick for {benefit}",
        "Anonymous source reveals {entity} is actually {truth}",
        "Breaking: {Person} caught worshipping {deity}",
        "Cover-up exposed: {event} was staged by {group}"
    ]
    
    import random
    
    real_news = []
    fake_news = []
    
    # Generate 500 real
    for i in range(500):
        template = random.choice(real_templates)
        real_news.append(template.format(
            policy=random.choice(['tax reform', 'healthcare bill', 'education act', 'trade agreement']),
            factor=random.choice(['exercise', 'sleep', 'diet', 'meditation']),
            outcome=random.choice(['wellness', 'longevity', 'productivity', 'happiness']),
            Organization=random.choice(['TechCorp', 'GlobalBank', 'MegaRetail', 'AutoInc']),
            amount=random.randint(1, 50),
            discovery=random.choice(['species', 'civilization', 'element', 'fossil']),
            location=random.choice(['Amazon', 'Antarctica', 'Africa', 'Pacific Ocean']),
            action=random.choice(['raises', 'lowers', 'maintains']),
            percent=random.choice(['0.25%', '0.5%', '1%']),
            topic=random.choice(['yoga', 'reading', 'walking', 'music']),
            subject=random.choice(['labor laws', 'immigration', 'environment', 'infrastructure']),
            department=random.choice(['Health', 'Defense', 'Education', 'Finance']),
            issue=random.choice(['climate change', 'trade wars', 'refugee crisis', 'pandemic'])
        ))
    
    # Generate 500 fake
    for i in range(500):
        template = random.choice(fake_templates)
        fake_news.append(template.format(
            person=random.choice(['politician', 'celebrity', 'scientist', 'expert']),
            scandal=random.choice(['corruption', 'fraud', 'affair', 'crimes']),
            celebrity=random.choice(['Actor A', 'Singer B', 'Athlete C', 'Star D']),
            object=random.choice(['aliens', 'time machine', 'secret formula', 'magic stone']),
            organization=random.choice(['government', 'NASA', 'FBI', 'WHO']),
            event=random.choice(['moon landing', 'election', 'pandemic', 'terror attack']),
            Person=random.choice(['Obama', 'Trump', 'Musk', 'Gates']),
            disease=random.choice(['cancer', 'diabetes', 'blindness', 'aging']),
            consequence=random.choice(['taxes', 'fame', 'lawsuits', 'death']),
            belief=random.choice(['flat earth', 'fake moon', 'illuminati', 'lizard people']),
            method=random.choice(['smartphone', 'Facebook post', 'YouTube video', 'dream']),
            benefit=random.choice(['weight loss', 'eternal youth', 'wealth', 'superpowers']),
            entity=random.choice(['earth', 'humans', 'animals', 'plants']),
            truth=random.choice(['robots', 'aliens', 'simulation', 'hologram']),
            deity=random.choice(['Satan', 'ancient gods', 'lizards', 'AI overlord']),
            group=random.choice(['Hollywood', 'government', 'corporations', 'scientists'])
        ))
    
    # Create DataFrame
    df = pd.DataFrame({
        'text': real_news + fake_news,
        'label': ['Real'] * 500 + ['Fake'] * 500
    })
    
    # Shuffle
    df = df.sample(frac=1).reset_index(drop=True)
    
    df.to_csv('data/large_dataset.csv', index=False)
    print(f"\n✓ Created large synthetic dataset: {len(df)} articles")
    print("  Real: 500, Fake: 500")
    
    return df

if __name__ == "__main__":
    try:
        # Try to get real LIAR dataset first
        download_liar_dataset()
    except Exception as e:
        print(f"\nCould not download LIAR dataset: {e}")
        print("Creating large synthetic dataset instead...")
        download_large_synthetic_dataset()
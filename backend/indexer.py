import os
import json
import glob
import pickle
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METADATA_DIR = os.path.join(BASE_DIR, "data", "metadata")
CACHE_FILE = os.path.join(BASE_DIR, "backend", "index_cache.pkl")

STATE_SYNONYMS = {
    "NSW": ["NSW", "NSW/ACT", "NSW/ACT/NT", "NEW SOUTH WALES"],
    "VIC": ["VIC", "VIC/TAS", "VICTORIA"],
    "QLD": ["QLD", "QUEENSLAND"],
    "WA":  ["WA", "WESTERN AUSTRALIA"],
    "SA":  ["SA", "SOUTH AUSTRALIA"],
    "TAS": ["TAS", "TASMANIA", "VIC/TAS"],
    "ACT": ["ACT", "NSW/ACT", "AUSTRALIAN CAPITAL TERRITORY"],
    "NT":  ["NT", "NORTHERN TERRITORY", "NSW/ACT/NT"],
}

def is_state_match(target_state, item_state):
    if not target_state or target_state.upper() in ["NATIONAL", "ALL", "AUSTRALIA"]:
        return True
    if not item_state or item_state.upper() in ["NATIONAL", "ALL", "AUSTRALIA", "NATIONAL/UNSPECIFIED", "INTERNATIONAL"]:
        return True
    
    target_clean = target_state.upper()
    item_clean = item_state.upper()
    
    synonyms = STATE_SYNONYMS.get(target_clean, [target_clean])
    return any(syn in item_clean for syn in synonyms)

class MNDIndexer:
    def __init__(self):
        self.documents = []
        self.entities = []
        self.vectorizer = None
        self.tfidf_matrix = None
        
    def build_index(self):
        print("Starting indexing of MND dataset...", flush=True)
        doc_files = sorted(glob.glob(os.path.join(METADATA_DIR, "*_documents.jsonl")))
        rec_files = sorted([
            f for f in glob.glob(os.path.join(METADATA_DIR, "*.jsonl"))
            if not f.endswith("_sources.jsonl") and not f.endswith("_documents.jsonl")
        ])
        
        # 1. Load document chunks
        self.documents = []
        for df in doc_files:
            cat_name = os.path.basename(df).replace("_documents.jsonl", "")
            with open(df, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        data = json.loads(line)
                        data["category_id"] = cat_name
                        self.documents.append(data)
                    except Exception:
                        pass
        print(f"Loaded {len(self.documents)} document chunks.", flush=True)

        # 2. Load structured entity records
        self.entities = []
        for rf in rec_files:
            cat_name = os.path.basename(rf)
            with open(rf, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        data = json.loads(line)
                        data["file_source"] = cat_name
                        self.entities.append(data)
                    except Exception:
                        pass
        print(f"Loaded {len(self.entities)} structured entity records.", flush=True)

        # 3. Build TF-IDF Vectorizer over document text + titles
        print("Computing TF-IDF matrix...", flush=True)
        corpus = [
            f"{doc.get('source_title', '')} {doc.get('topic', '')} {doc.get('text', '')}"
            for doc in self.documents
        ]
        
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=40000,
            ngram_range=(1, 2),
            sublinear_tf=True
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        print("TF-IDF matrix built successfully.", flush=True)
        
        # 4. Save cache
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "wb") as f:
            pickle.dump({
                "documents": self.documents,
                "entities": self.entities,
                "vectorizer": self.vectorizer,
                "tfidf_matrix": self.tfidf_matrix
            }, f)
        print(f"Saved index cache to {CACHE_FILE}", flush=True)

    def load_index(self):
        if os.path.exists(CACHE_FILE):
            print(f"Loading index from cache: {CACHE_FILE}", flush=True)
            with open(CACHE_FILE, "rb") as f:
                data = pickle.load(f)
                self.documents = data["documents"]
                self.entities = data["entities"]
                self.vectorizer = data["vectorizer"]
                self.tfidf_matrix = data["tfidf_matrix"]
            print(f"Loaded {len(self.documents)} docs, {len(self.entities)} entities.", flush=True)
        else:
            self.build_index()

    def search_entities(self, query, state=None, top_k=4):
        """Search structured entity records (equipment, services, NDIS funding, etc.)"""
        query_words = set(re.findall(r'\w+', query.lower()))
        matched = []
        
        for ent in self.entities:
            score = 0.0
            name = str(ent.get("name", "")).lower()
            desc = str(ent.get("description", "")).lower()
            cat = str(ent.get("category", "")).lower()
            ent_state = str(ent.get("state", "")).upper()
            
            # Keyword matching
            for w in query_words:
                if len(w) <= 2: continue
                if w in name: score += 3.0
                if w in cat: score += 2.0
                if w in desc: score += 1.0

            if score > 0:
                # State filtering & heavy boosting
                if state and state.upper() not in ["ALL", "NATIONAL"]:
                    if is_state_match(state, ent_state):
                        if ent_state not in ["AUSTRALIA", "NATIONAL", "ALL", "INTERNATIONAL"]:
                            score += 10.0 # Heavy boost for target state specific entities
                    else:
                        score -= 15.0 # Severe penalty for conflicting state entities

                matched.append((score, ent))

        matched.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in matched if item[0] > 0][:top_k]

    def search_documents(self, query, state=None, category=None, top_k=5):
        """Search text chunks using TF-IDF cosine similarity + state filtering boost"""
        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        # Apply state boost or penalty
        if state and state.upper() not in ["ALL", "NATIONAL"]:
            for idx, doc in enumerate(self.documents):
                doc_st = str(doc.get("state", "")).upper()
                if is_state_match(state, doc_st):
                    if doc_st not in ["NATIONAL/UNSPECIFIED", "ALL", "AUSTRALIA"]:
                        similarities[idx] *= 2.5 # 2.5x boost for matching state chunks
                else:
                    similarities[idx] *= 0.1 # Heavily suppress non-matching state chunks

        top_indices = np.argsort(similarities)[::-1][:top_k*3]
        results = []
        seen_urls = set()

        for idx in top_indices:
            score = float(similarities[idx])
            if score <= 0: continue
            doc = self.documents[idx]
            url = doc.get("url", "")
            if url in seen_urls and len(results) >= 2:
                continue
            seen_urls.add(url)
            doc_copy = dict(doc)
            doc_copy["relevance_score"] = round(score, 4)
            results.append(doc_copy)
            if len(results) >= top_k:
                break

        return results

if __name__ == "__main__":
    indexer = MNDIndexer()
    indexer.build_index()
    
    print("\n--- TEST SEARCH ---")
    results = indexer.search_documents("flexequip wheelchair access NSW", state="NSW", top_k=3)
    for r in results:
        print(f"[{r['relevance_score']}] {r['source_title']} ({r['state']}) -> {r['url']}")
    
    print("\n--- TEST ENTITY SEARCH ---")
    entities = indexer.search_entities("carer gateway respite", top_k=2)
    for e in entities:
        print(f"Entity: {e.get('name')} | {e.get('category')} | {e.get('source_id')}")

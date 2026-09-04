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
CACHE_VERSION = 3

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

ENTITY_QUERY_STOPWORDS = {
    "a", "about", "all", "also", "am", "an", "and", "any", "are", "as", "at",
    "be", "been", "being", "but", "by", "can", "could", "did", "do", "does",
    "doing", "for", "from", "gday", "get", "give", "had", "has", "have", "he",
    "hello", "help", "her", "here", "hers", "hey", "hi", "him", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "just", "know", "like", "mate",
    "me", "more", "my", "myself", "no", "not", "of", "off", "on", "once", "one",
    "or", "other", "our", "ours", "out", "please", "see", "she", "should", "show",
    "so", "some", "such", "sup", "tell", "than", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "through", "to", "too",
    "up", "was", "we", "were", "what", "whats", "when", "where", "which", "while",
    "who", "whom", "whose", "why", "will", "with", "would", "you", "your", "yours",
    "manage", "problem", "problems",
}

def entity_url(ent):
    return str(
        ent.get("url")
        or ent.get("website")
        or ent.get("source_url")
        or ent.get("served_url")
        or ent.get("product_url")
        or ""
    ).strip()


def normalize_entity_url(url):
    return str(url or "").strip().lower().rstrip("/")


NATIONAL_STATES = {
    "", "NATIONAL", "ALL", "AUSTRALIA", "NATIONAL/UNSPECIFIED", "INTERNATIONAL",
}

PUBLISHER_HOMEPAGES = {
    "mnd australia": "https://www.mndaustralia.org.au",
    "mnd nsw": "https://www.mndnsw.org.au",
    "mnd victoria": "https://www.mnd.asn.au",
    "mnd queensland": "https://www.mndqld.org.au",
    "mnd western australia": "https://www.mndawa.asn.au",
    "mnd south australia": "https://www.mndsa.org.au",
    "healthdirect australia": "https://www.healthdirect.gov.au",
    "healthdirect": "https://www.healthdirect.gov.au",
    "ndis": "https://www.ndis.gov.au",
    "services australia": "https://www.servicesaustralia.gov.au",
    "carer gateway": "https://www.carergateway.gov.au",
    "my aged care": "https://www.myagedcare.gov.au",
    "palliative care australia": "https://palliativecare.org.au",
    "caresearch": "https://www.caresearch.com.au",
    "lifeline australia": "https://www.lifeline.org.au",
    "beyond blue": "https://www.beyondblue.org.au",
}

DEFINITION_TITLE_RE = re.compile(
    r"(what is (motor neurone|mnd)|motor neurone disease \(mnd\)|overview of mnd|"
    r"about (motor neurone|mnd)|causes, symptoms and treatments|learn about motor neurone)",
    re.I,
)
OFFTOPIC_DEFINITION_RE = re.compile(
    r"\b(niv|non-invasive|wheelchair|flexequip|notification|research grants|"
    r"statistics|swallowing|eye gaze|commode|shower|hoist|respiratory equipment)\b",
    re.I,
)
NEWSY_TITLE_RE = re.compile(
    r"notification|media release|\bnews\b|from \d|1 september|campaign",
    re.I,
)
PRODUCT_ENTITY_HINTS = (
    "communication", "assistive_technology", "wheelchair", "equipment",
    "notification", "flexequip", "eye gaze", "commode", "shower", "bed",
    "product",
)


def record_http_url(record):
    for key in ("url", "website", "source_url", "served_url", "product_url"):
        val = str(record.get(key) or "").strip()
        if val.lower().startswith("http"):
            return val
    return ""


def publisher_homepage(publisher):
    return PUBLISHER_HOMEPAGES.get(str(publisher or "").strip().lower(), "")


TOPIC_LABELS = {
    "mnd_basics": "MND basics",
    "palliative_care_advance_planning": "Palliative care and advance planning",
    "equipment_assistive_technology": "Equipment and assistive technology",
    "support_services": "Australian support services",
    "ndis_funding_benefits": "NDIS, funding and benefits",
    "carer_support": "Carer support",
    "mental_health_cognition": "Mental health and cognition",
    "clinical_trials_research": "Clinical trials and research",
    "forms_templates_directories": "Forms, templates and directories",
    "mobility_daily_living": "Mobility and daily living",
    "breathing_respiratory_care": "Breathing and respiratory care",
    "pain_cramps_spasticity": "Pain, cramps and spasticity",
    "home_nursing_personal_care_in_home_supports": "Home nursing and in-home supports",
    "sleep": "Sleep",
    "emergency_planning": "Emergency planning",
    "food_nutrition": "Food and nutrition",
    "treatments_medicines": "Treatments and medicines",
    "culturally_accessible_regional_support": "Culturally accessible and regional support",
    "communication": "Communication",
    "risk_factors_epidemiology_registries": "Risk factors, epidemiology and registries",
    "driving_transport_travel_vehicle_modification": "Driving, transport and vehicle modification",
    "genetics_family_risk_testing": "Genetics, family risk and testing",
    "state_mnd_association": "State MND associations",
    "national_peak_body": "National peak bodies",
    "equipment_service": "Equipment services",
    "national_carer_peak_body": "National carer peak bodies",
    "health_information_service": "Health information services",
    "bathroom": "Bathroom equipment",
    "beds_and_bed_equipment": "Beds and bed equipment",
    "mobility": "Mobility equipment",
    "pressure_care": "Pressure care",
    "transfer_aids": "Transfer aids",
    "state equipment scheme": "State equipment schemes",
    "assistive_technology": "Assistive technology",
    "armchairs": "Armchairs",
    "Centrelink payment": "Centrelink payments",
    "mnd_equipment_guidance": "MND equipment guidance",
    "respiratory_equipment": "Respiratory equipment",
    "funding_pathways": "Funding pathways",
}

SOURCE_TYPE_LABELS = {
    "webpage": "Webpage",
    "pdf": "PDF",
    "docx": "Word document",
    "jpg": "Image",
    "bin": "File",
    "equipment_record": "Equipment directory",
    "service_directory": "Service directory",
    "funding_record": "Funding directory",
    "directory": "Directory record",
}


def topic_label(raw):
    key = str(raw or "").strip()
    if not key:
        return "General"
    if key in TOPIC_LABELS:
        return TOPIC_LABELS[key]
    stripped = re.sub(r"^\d+_", "", key)
    if stripped in TOPIC_LABELS:
        return TOPIC_LABELS[stripped]
    stripped = re.sub(r"_record$", "", stripped)
    if stripped in TOPIC_LABELS:
        return TOPIC_LABELS[stripped]
    return stripped.replace("_", " ").strip().title() or "General"


def source_type_label(raw):
    key = str(raw or "webpage").strip()
    mapped = SOURCE_TYPE_LABELS.get(key.lower())
    if mapped:
        return mapped
    if key.lower().endswith("_record"):
        return f"{topic_label(key)} directory"
    return key.replace("_", " ").strip().title() or "Webpage"


def display_state(raw):
    value = str(raw or "").strip()
    if not value or value.upper() in NATIONAL_STATES:
        return "National"
    return value


def page_host(url):
    match = re.match(r"https?://([^/]+)", str(url or ""), re.I)
    if not match:
        return ""
    return match.group(1).lower().removeprefix("www.")


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
        self._source_catalog = None

    def _metadata_files(self):
        return sorted(glob.glob(os.path.join(METADATA_DIR, "*.jsonl")))

    def _metadata_signature(self):
        signature = []
        for path in self._metadata_files():
            try:
                stat = os.stat(path)
            except OSError:
                continue
            signature.append((os.path.basename(path), stat.st_size, int(stat.st_mtime)))
        return signature
        
    def build_index(self):
        print("Starting indexing of MND dataset...", flush=True)
        self.documents = []
        self.entities = []

        # 1. Load document chunks and structured entities from data/metadata
        for fpath in self._metadata_files():
            fname = os.path.basename(fpath)
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if not line_str: continue
                    try:
                        record = json.loads(line_str)
                        record["file_source"] = fname
                        
                        # Structured entity vs document chunk
                        if "name" in record and "category" in record:
                            self.entities.append(record)
                        elif "text" in record or "chunk" in record:
                            text_val = record.get("text") or record.get("chunk") or ""
                            record["text"] = text_val
                            self.documents.append(record)
                    except json.JSONDecodeError:
                        continue

        print(f"Loaded {len(self.documents)} document chunks.", flush=True)
        print(f"Loaded {len(self.entities)} structured entity records.", flush=True)
        self._backfill_missing_urls()
        self._source_catalog = None

        # 2. Build TF-IDF vectorizer over document chunks
        print("Computing TF-IDF matrix...", flush=True)
        corpus = [f"{d.get('source_title', '')} {d.get('publisher', '')} {d.get('text', '')}" for d in self.documents]
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=40000,
            ngram_range=(1, 2),
            sublinear_tf=True
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        print("TF-IDF matrix built successfully.", flush=True)

        # 3. Save cache to disk
        cache_data = {
            "cache_version": CACHE_VERSION,
            "metadata_signature": self._metadata_signature(),
            "documents": self.documents,
            "entities": self.entities,
            "vectorizer": self.vectorizer,
            "tfidf_matrix": self.tfidf_matrix
        }
        with open(CACHE_FILE, "wb") as f:
            pickle.dump(cache_data, f)
        print(f"Saved index cache to {CACHE_FILE}", flush=True)

    def load_index(self):
        if os.path.exists(CACHE_FILE):
            print(f"Loading index from cache: {CACHE_FILE}", flush=True)
            with open(CACHE_FILE, "rb") as f:
                data = pickle.load(f)
            if (
                data.get("cache_version") != CACHE_VERSION
                or data.get("metadata_signature") != self._metadata_signature()
            ):
                print("Index cache is stale; rebuilding from metadata.", flush=True)
                self.build_index()
                return
            else:
                self.documents = data["documents"]
                self.entities = data["entities"]
                self.vectorizer = data["vectorizer"]
                self.tfidf_matrix = data["tfidf_matrix"]
                self._backfill_missing_urls()
                self._source_catalog = None
            print(f"Loaded {len(self.documents)} docs, {len(self.entities)} entities.", flush=True)
        else:
            self.build_index()

    def _backfill_missing_urls(self):
        """Copy alternate URL fields, then same-title matches, then known publisher homepages."""
        title_urls = {}
        for doc in self.documents:
            url = record_http_url(doc)
            if not url:
                continue
            title = str(doc.get("source_title") or "").strip().lower()
            pub = str(doc.get("publisher") or "").strip().lower()
            if title:
                title_urls.setdefault((title, pub), url)
                title_urls.setdefault((title, ""), url)

        filled = 0
        for doc in self.documents:
            url = record_http_url(doc)
            if url:
                if not str(doc.get("url") or "").lower().startswith("http"):
                    doc["url"] = url
                continue
            title = str(doc.get("source_title") or "").strip().lower()
            pub = str(doc.get("publisher") or "").strip().lower()
            url = title_urls.get((title, pub)) or title_urls.get((title, "")) or publisher_homepage(pub)
            if url:
                doc["url"] = url
                filled += 1

        for ent in self.entities:
            url = record_http_url(ent)
            if url:
                if not str(ent.get("url") or "").lower().startswith("http"):
                    ent["url"] = url
                continue
            pub = str(ent.get("publisher") or ent.get("supplier") or "").strip().lower()
            url = publisher_homepage(pub)
            if url:
                ent["url"] = url
                filled += 1
        if filled:
            print(f"Backfilled {filled} missing source URLs.", flush=True)

    def missing_url_count(self) -> int:
        docs = sum(1 for d in self.documents if not str(d.get("url") or "").lower().startswith("http"))
        ents = sum(1 for e in self.entities if not record_http_url(e).lower().startswith("http"))
        return docs + ents

    def catalog_sources(self):
        """Unique publication and directory pages grouped by publisher."""
        if self._source_catalog is not None:
            return self._source_catalog

        from answer_policy import readable_title

        pages = {}

        def upsert(url, title, publisher, topic, source_type, state, kind, extras=None):
            url = str(url or "").strip()
            publisher = str(publisher or "").strip() or "Unknown publisher"
            title = readable_title(title, publisher, url)
            if url.lower().startswith("http"):
                key = url.lower().rstrip("/")
            else:
                key = f"local:{kind}:{publisher}:{title}".lower()
            label = topic_label(topic)
            extra = extras or {}
            existing = pages.get(key)
            if existing:
                if label not in existing["topics"]:
                    existing["topics"].append(label)
                if kind == "publication":
                    existing["kind"] = "publication"
                if title and len(title) > len(existing["title"]):
                    existing["title"] = title
                for field in ("description", "phone", "eligibility", "region"):
                    if extra.get(field) and not existing.get(field):
                        existing[field] = extra[field]
                return
            page = {
                "title": title,
                "publisher": publisher,
                "url": url if url.lower().startswith("http") else "",
                "host": page_host(url),
                "topics": [label],
                "source_type": source_type_label(source_type),
                "state": display_state(state),
                "kind": kind,
            }
            for field, value in extra.items():
                if value:
                    page[field] = value
            pages[key] = page

        for doc in self.documents:
            upsert(
                record_http_url(doc),
                doc.get("source_title") or doc.get("title") or "",
                doc.get("publisher") or "",
                doc.get("topic") or doc.get("v1_data_topic") or "",
                doc.get("source_type") or "webpage",
                doc.get("state") or "",
                "publication",
            )

        for ent in self.entities:
            extras = {}
            description = str(ent.get("description") or ent.get("notes") or "").strip()
            if description:
                extras["description"] = description[:400]
            phone = str(ent.get("phone") or "").strip()
            if phone:
                extras["phone"] = phone
            eligibility = str(ent.get("eligibility") or "").strip()
            if eligibility:
                extras["eligibility"] = eligibility[:240]
            region = str(ent.get("region") or "").strip()
            if region:
                extras["region"] = region
            publisher = str(ent.get("publisher") or ent.get("supplier") or "").strip()
            if not publisher:
                category = str(ent.get("category") or "")
                if category in {
                    "state_mnd_association", "national_peak_body", "national_carer_peak_body",
                    "health_information_service", "equipment_service", "carer_support",
                }:
                    publisher = str(ent.get("name") or "").strip()
                else:
                    publisher = "Service and equipment directory"
            upsert(
                entity_url(ent) or record_http_url(ent),
                ent.get("name") or "",
                publisher,
                ent.get("category") or ent.get("topic") or "directory",
                ent.get("source_type") or "directory",
                ent.get("state") or "",
                "directory",
                extras,
            )

        groups = {}
        for page in pages.values():
            groups.setdefault(page["publisher"], []).append(page)

        topic_counts = {}
        publishers = []
        for name, items in groups.items():
            items.sort(key=lambda page: page["title"].lower())
            pub_topics = []
            for page in items:
                for label in page["topics"]:
                    if label not in pub_topics:
                        pub_topics.append(label)
                    topic_counts[label] = topic_counts.get(label, 0) + 1
            publishers.append({
                "name": name,
                "count": len(items),
                "homepage": publisher_homepage(name) or next((p["url"] for p in items if p.get("url")), ""),
                "topics": sorted(pub_topics),
                "pages": items,
            })
        publishers.sort(key=lambda group: (-group["count"], group["name"].lower()))

        self._source_catalog = {
            "page_count": len(pages),
            "publisher_count": len(publishers),
            "topic_count": len(topic_counts),
            "topics": sorted(
                [{"name": name, "count": count} for name, count in topic_counts.items()],
                key=lambda item: (-item["count"], item["name"].lower()),
            ),
            "publishers": publishers,
        }
        return self._source_catalog

    def search_entities(self, query, state=None, top_k=4, topic=None):
        """Search structured entity records (equipment, services, NDIS funding, etc.)"""
        query_words = {
            w for w in re.findall(r'\w+', query.lower())
            if len(w) > 2 and w not in ENTITY_QUERY_STOPWORDS
        }
        if not query_words:
            return []
        matched = []
        
        for ent in self.entities:
            score = 0.0
            name = str(ent.get("name", "")).lower()
            desc = str(ent.get("description", "")).lower()
            cat = str(ent.get("category", "")).lower()
            ent_state = str(ent.get("state", "")).upper()
            blob = f"{name} {cat}"

            if topic in {"definition", "mental_health", "crisis", "medical"}:
                if any(re.search(r"\b" + re.escape(hint) + r"\b", blob) for hint in PRODUCT_ENTITY_HINTS):
                    continue
                if topic == "definition" and any(x in cat for x in ("research_grants", "resource_library")):
                    continue

            # Word boundary matching
            for w in query_words:
                pattern = r'\b' + re.escape(w) + r'\b'
                if re.search(pattern, name): score += 5.0
                if re.search(pattern, cat): score += 3.0
                if re.search(pattern, desc): score += 1.0

            if score > 0:
                if topic in {"definition", "mental_health", "crisis"}:
                    if "association" in cat or "mnd nsw" in name or "mnd australia" in name:
                        score += 8.0
                # State filtering & heavy boosting
                if state and state.upper() not in ["ALL", "NATIONAL"]:
                    if is_state_match(state, ent_state):
                        if ent_state not in NATIONAL_STATES:
                            score += 10.0 # Heavy boost for target state specific entities
                    else:
                        score -= 15.0 # Severe penalty for conflicting state entities

                matched.append((score, ent))

        matched.sort(key=lambda x: x[0], reverse=True)
        results = []
        seen_name_urls = set()
        seen_urls = set()
        for score, ent in matched:
            if score <= 0:
                continue
            ent_url = normalize_entity_url(entity_url(ent))
            name_key = str(ent.get("name", "")).strip().lower()
            if (name_key, ent_url) in seen_name_urls:
                continue
            # Distinct cards must open distinct pages — keep the highest-scoring record per URL.
            if ent_url and ent_url in seen_urls:
                continue
            seen_name_urls.add((name_key, ent_url))
            if ent_url:
                seen_urls.add(ent_url)
            results.append(ent)
            if len(results) >= top_k:
                break
        return results

    def search_documents(self, query, state=None, category=None, top_k=5, topic=None):
        """Search text chunks using TF-IDF cosine similarity + title/topic rerank."""
        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        query_terms = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2]
        apply_state_boost = topic not in {"definition", "medical", "mental_health", "crisis"}

        for idx, doc in enumerate(self.documents):
            title = str(doc.get("source_title", "")).lower()
            if query_terms:
                title_hits = sum(1 for term in query_terms if term in title)
                if title_hits:
                    similarities[idx] *= 1.0 + 0.45 * title_hits
            if NEWSY_TITLE_RE.search(title):
                similarities[idx] *= 0.12
            if topic == "definition":
                if DEFINITION_TITLE_RE.search(title):
                    similarities[idx] *= 8.0
                topic_id = str(doc.get("topic") or doc.get("v1_data_topic") or "").lower()
                if topic_id in {"mnd_basics", "01_mnd_basics"} or topic_id.startswith("01_"):
                    similarities[idx] *= 2.0
                if OFFTOPIC_DEFINITION_RE.search(title):
                    similarities[idx] *= 0.08
            if apply_state_boost and state and state.upper() not in ["ALL", "NATIONAL"]:
                doc_st = str(doc.get("state") or "").upper()
                if is_state_match(state, doc_st):
                    if doc_st not in NATIONAL_STATES:
                        similarities[idx] *= 2.5
                else:
                    similarities[idx] *= 0.1

        pool = top_k * 5 if topic == "definition" else top_k * 3
        top_indices = np.argsort(similarities)[::-1][:pool]
        results = []
        seen_urls = set()
        seen_texts = set()
        seen_title_urls = set()

        for idx in top_indices:
            score = float(similarities[idx])
            if score <= 0: continue
            doc = self.documents[idx]
            url = doc.get("url", "")
            title = str(doc.get("source_title", "")).strip().lower()
            text_key = re.sub(r"\s+", " ", str(doc.get("text", "")).strip().lower())
            title_url_key = (title, str(url).strip().lower())
            if text_key and text_key in seen_texts:
                continue
            if title_url_key in seen_title_urls:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            seen_texts.add(text_key)
            seen_title_urls.add(title_url_key)
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

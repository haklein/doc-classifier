"""Classification: rank folders by TF-IDF cosine similarity."""

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .indexer import Index


def classify(
    text: str, index: Index, top_n: int = 30, min_similarity: float = 0.10
) -> list[tuple[str, float]]:
    """Classify text against folder centroids.

    Returns list of (folder_name, score_percent) sorted by descending score.
    Score is 0-100%.
    """
    if not index.folder_names or not text.strip():
        return [("[NEW FOLDER]", 0.0)]

    doc_vector = index.vectorizer.transform([text])
    similarities = cosine_similarity(doc_vector, index.centroids).flatten()

    # Pair with folder names and sort descending
    scored = [
        (index.folder_names[i], float(similarities[i] * 100))
        for i in range(len(index.folder_names))
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    results = scored[:top_n]

    # If best score below threshold, prepend [NEW FOLDER]
    if not results or results[0][1] < min_similarity * 100:
        results.insert(0, ("[NEW FOLDER]", 0.0))

    return results

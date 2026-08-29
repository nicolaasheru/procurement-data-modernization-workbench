# Example retrieval trace

**Query:** `Furniture healthcare Facilities Flood Affected`  
**Filter:** country = Pakistan  
**Expected relevant records:** contract awards 1894368 and 1894364  
**Process:** encode query with the pinned Sentence Transformer → apply SQL metadata filters → pgvector cosine rank → threshold or abstain → attach official URL  
**Interpretation:** score ranks text similarity only. Retrieved record content remains a source fact; the ranking is a system output.

An unsupported query (`xylophone nebula quasar`) returns no result and the system states that evidence is insufficient within the indexed prototype scope.

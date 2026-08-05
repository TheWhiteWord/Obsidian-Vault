# OBSIDIAN-VAULT PLUGIN DESIGN
**Context:** Design specification for an Obsidian vault plugin tailored for the **Hermes Agent** agentic harness.

## 1. User Roles & Permissions
The plugin defines two primary agent roles that dictate available tools and scope:

*   **Manager**
    *   **Scope:** Default access to all tools and domains.
    *   **Restrictions:** Can manually reduce scope to specific existing domains if necessary.
*   **Contributor**
    *   **Scope:** Restricted set of tools based on role flags.
    *   **Domain:** Restricted to a specific folder (and its subfolders) acting as their "personal domain."

## 2. Note Creation
*   **Base Format:** A standard, universal format applied to all notes by default.
*   **Custom Formats:** Support for domain-specific formats customizable per folder/role.
*   **Smart Tagging & Wikilinks:**
    *   Automatic maintenance of tags and wikilinks.
    *   Deduplication logic (prevents duplicate tags/links).
    *   Similarity matching to suggest connections.
    *   Context awareness: Ensures proper connection with existing knowledge in the vault.
    *   **Graph Integration:** Triggers incremental graph node creation and edge indexing. Domain-specific formats may restrict initial link scope.
*   **Auto-Indexing:** Automatically generates short descriptions and indexes new notes for faster retrieval.

## 3. Note Removal
*   **Dependency Management:** Automatic system to clean up dependencies when a note is deleted.
*   **Sanitization:**
    *   Removes tags that are no longer used elsewhere.
    *   Sanitizes broken wikilinks that referred to the removed note.
    *   General cleanup of orphaned metadata.
*   **Graph Maintenance:**
    *   Triggers edge pruning and orphan node detection. Broken wikilinks are queued for sanitization before final deletion.

## 4. Search Capabilities
*Note: Optimized for low-VRAM environments. Avoids local embedding models and relies on deterministic, lightweight retrieval methods.*

*   **Lightweight Full-Text Search:**
    *   Leverages Obsidian’s native search index and BM25/TF-IDF ranking for fast, CPU-efficient keyword matching.
    *   Supports boolean operators, fuzzy matching, and regex patterns for precise agent queries.
    *   Maintains a pre-computed inverted index in `.obsidian-vault/search-index/` to eliminate repeated vault scans.

*   **Graph-Aware Context Expansion:**
    *   **Execution:** Runs via the Graph Architecture (Section 6). Configurable hops (1–3) traverse domain-permitted edges.
    *   **Topic Proximity:** Tag/metadata clustering supplements edge traversal for topic proximity.
    *   **Targeted Snippets:** Returns only the relevant excerpt around matched terms or link references to minimize LLM token overhead.

*   **Structured Agent Output:**
    *   All results are serialized to a strict JSON schema (exammple):
        ```json
        {
          "note_title": "string",
          "file_path": "string",
          "relevance_score": "float",
          "match_type": "keyword | wikilink | tag",
          "snippet": "string",
          "metadata": { "tags": [], "created": "ISO8601", "domain": "string" }
        }
        ```
    *   Supports pagination (`limit`, `offset`), sorting (`relevance`, `date`, `alphabetical`), and explicit citation line ranges.

*   **Domain & Permission Enforcement:**
    *   **Scope Isolation:** Contributors automatically receive results filtered to their designated folder/domain.
    *   **Cross-Domain Queries:** Managers can opt-in to vault-wide searches, with results tagged by origin domain.
    *   **Exclusion Rules:** Supports `exclude_tags`, `exclude_folders`, and `status: "archived"` filters to reduce noise.

*   **Optional External Embeddings (Fallback):**
    *   If semantic search is strictly required, the plugin supports a lightweight HTTP client to call external embedding APIs.
    *   *Disabled by default* due to privacy/latency concerns. Results are cached locally with TTL to minimize API calls.

*   **Performance Optimizations:**
    *   **In-Memory Cache:** Frequently queried terms and graph traversals are cached to avoid redundant processing.
    *   **Lazy Loading:** Only metadata and snippets are fetched initially; full note content is loaded on-demand when the agent explicitly requests it.
    *   **Async Indexing:** Index updates run in the background to prevent UI blocking or context saturation.

## 5. Background Events & Verification
*   **Change Tracking Mechanism:**
  *   **Frontmatter State Schema:** Each note includes a standardized metadata block:
    ```yaml
    ---
    maintenance_status: pending | approved | rejected
    verified_at: ISO 8601 timestamp
    verified_by: manager_id
    last_modified_by: contributor_id | agent_id
    ---
    ```
  *   **Vault Event Listener:** The plugin hooks into Obsidian’s `file:create`, `file:change`, and `file:delete` events to log structural changes in a local index (e.g., `.obsidian-vault/change-log.json`).
*   **Maintenance Run Logic:**
  *   The Manager agent stores a `last_maintenance_run` timestamp in `.obsidian-vault/config.json`.
  *   On execution, it queries only notes matching:
    *   `hermes_status == "pending"`, OR
    *   `hermes_status == "approved"` AND `last_modified_by` changed after `verified_at`.
  *   Deletions are tracked via a tombstone registry or event log, enabling targeted cleanup of broken links/tags without scanning the full vault.
*   **Verification Workflow:**
  *   **Tiered Review:** Low-risk domains or auto-formatted notes can auto-approve; high-risk or cross-domain notes require Manager review.
  *   **State Updates:** Manager reviews content, updates `mantainance_status`, and sets `verified_at`. Rejected notes return to `pending` with optional revision notes.
  *   **Audit Trail:** All state transitions are logged in `.obsidian-vault/audit-log.json` with timestamps, agent IDs, and optional diff snapshots for compliance.
*   **Implementation Considerations:**
  *   Use Obsidian’s `MetadataCache` and `TFile` API for non-blocking, efficient reads.
  *   Keep `.obsidian-vault/` hidden by default (`.obsidian/vault.json` → `"showHiddenFiles": false`) to avoid UI clutter.
  *   Expose a `!mantainance-verify` command to trigger manual maintenance runs or force-scan specific domains.
  *   Graph edge updates share the same event listener hooks to avoid duplicate processing. Maintenance runs validate graph integrity alongside note state.

## 6. Graph Architecture & Maintenance
*   **Construction Strategy:**
    *   **Event-Driven & Incremental:** The graph updates in real-time using the same Obsidian file events (`file:create`, `file:change`, `file:delete`) defined in Section 5. No full vault rebuilds are triggered.
    *   **Storage Format:** Maintained as a lightweight adjacency list in `.obsidian-vault/graph/edges.json` and `.obsidian-vault/graph/nodes.json`. Keys use relative file paths prefixed with domain identifiers for O(1) lookups.
*   **Scope & Permission Boundaries:**
    *   **Domain Isolation:** Contributors can only traverse edges within their designated folder/domain. Cross-domain wikilinks are treated as "gateways" that require Manager permission to follow.
    *   **Manager View:** Full vault graph with domain tags attached to each node for routing and cross-domain query resolution.
*   **Integration with Search & Verification:**
    *   **On-Demand Expansion:** The graph is queried dynamically during search (Section 4) or verification (Section 5), not pre-computed for all possible paths.
    *   **Context Caching:** Frequently traversed paths and tag clusters are cached in-memory with a configurable TTL to avoid redundant graph walks.
*   **Maintenance Operations:**
    *   All graph maintenance tasks, including stale edge pruning and orphan node detection, are handled by the Manager Maintenance Operations in Section 7 to ensure consistency and permission enforcement.

## 7. Manager Maintenance Operations
*These tools are restricted to the **Manager** role and are exposed via the Command Palette or internal API. They are designed to be lightweight and non-blocking.*

### 7.0 Maintenance Execution
*   **Trigger Logic:**
    *   The Manager agent stores a `last_maintenance_run` timestamp in `.obsidian-vault/config.json`.
    *   On execution, it queries only notes matching:
        *   `maintenance_status == "pending"`, OR
        *   `maintenance_status == "approved"` AND `last_modified_by` changed after `verified_at`.
    *   Deletions are tracked via a tombstone registry or event log, enabling targeted cleanup of broken links/tags without scanning the full vault.
*   **Concurrency:** All maintenance tasks must be queued to prevent race conditions with the background event listeners (Section 5).

### 7.1 Graph Maintenance
*   **Full Graph Rebuild:**
    *   **Trigger:** `!rebuild-graph` command.
    *   **Function:** Scans the entire vault to reconstruct `nodes.json` and `edges.json` from scratch.
    *   **Safety:** Runs in chunks to prevent memory spikes (Low VRAM optimization).
    *   **Validation:** Compares the new graph against the existing one; only updates if structural changes are detected.
*   **Orphan Node Cleanup:**
    *   **Function:** Identifies nodes in the graph with zero inbound or outbound edges (excluding the root node).
    *   **Action:** Flags these notes in `maintenance_status: pending` for review or automatically archives them based on domain policy.
*   **Stale Edge Pruning:**
    *   **Function:** During maintenance runs, edges referencing deleted, archived, or permission-restricted notes are automatically removed.

### 7.2 Link & Tag Sanitization
*   **Broken Link Repair:**
    *   **Function:** Scans all markdown files for broken wikilinks (referencing deleted or moved files).
    *   **Smart Fix:** Uses the "Similarity Matching" logic from Section 2 to suggest replacements.
    *   **Manager Override:** Manager can manually approve or reject suggested fixes in bulk.
*   **Tag Consolidation:**
    *   **Function:** Detects duplicate tags (e.g., `#project` vs `#Project`) and semantically similar tags.
    *   **Action:** Merges tags into a canonical form and updates all affected notes atomically.
    *   **Audit:** Logs all tag merges in `.obsidian-vault/audit-log.json`.

### 7.3 Note Lifecycle Management
*   **Empty Note Purge:**
    *   **Function:** Identifies notes that contain only frontmatter or whitespace.
    *   **Action:** Moves them to a `.trash/` folder or deletes them if `auto_purge_empty` is enabled in config.
*   **Duplicate Note Merge:**
    *   **Function:** Uses content hashing and similarity scoring to identify near-duplicate notes.
    *   **Action:** Merges content into the most recent version, updates all incoming links, and archives the redundant note.
*   **Stale Content Archiving:**
    *   **Function:** Identifies notes not modified within a configurable timeframe (e.g., 1 year).
    *   **Action:** Moves notes to an `Archive` domain and updates their metadata to `status: "archived"`.

### 7.4 Index Optimization
*   **Force Re-index:**
    *   **Function:** Rebuilds the BM25/TF-IDF inverted index in `.obsidian-vault/search-index/`.
    *   **Use Case:** Useful after bulk note modifications or if search results become inconsistent.
*   **Cache Clearing:**
    *   **Function:** Clears the in-memory cache for search snippets and graph traversals.
    *   **Safety:** Does not delete the persistent search index on disk.

### 7.5 Audit & Compliance
*   **Audit Log Export:**
    *   **Function:** Exports `.obsidian-vault/audit-log.json` to a timestamped `.md` or `.json` file in the vault root.
    *   **Filtering:** Supports filtering by date range, agent ID, or action type (create, delete, merge).
*   **Maintenance Report:**
    *   **Function:** Generates a summary of the last maintenance run, including:
        *   Number of broken links fixed.
        *   Number of orphaned nodes detected.
        *   Graph integrity score (percentage of valid edges).
    *   **Output:** Saves the report to `Maintenance-Report-[Date].md`.

### 7.6 Implementation Notes
*   **Undo Support:** Where possible, maintenance actions should be reversible via the Obsidian "Undo" stack or by restoring from the `.trash/` folder.
*   **Performance:** Heavy operations (e.g., Full Graph Rebuild) should display a progress modal and allow cancellation to prevent UI freezing.


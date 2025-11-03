// Neo4j indexes and constraints for Resync
//
// This Cypher script defines indexes and constraints required by the
// Resync knowledge graph.  It is idempotent: each statement uses
// ``IF NOT EXISTS`` to avoid errors when reapplying the script.  Keep
// this file in sync with ``resync/core/neo4j_bootstrap.py``.

// Unique constraint on Job.id ensures that job identifiers are not duplicated
CREATE CONSTRAINT job_id_unique IF NOT EXISTS
FOR (j:Job) REQUIRE j.id IS UNIQUE;

// Index on Job.timestamp accelerates queries that filter by time
CREATE INDEX job_timestamp_index IF NOT EXISTS
FOR (j:Job) ON (j.timestamp);

// Optional compound index on Job.id and Job.timestamp; uncomment to enable
// CREATE INDEX job_id_ts_index IF NOT EXISTS
// FOR (j:Job) ON (j.id, j.timestamp);
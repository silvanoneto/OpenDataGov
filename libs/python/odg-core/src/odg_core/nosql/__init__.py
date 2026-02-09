"""NoSQL database integrations for OpenDataGov.

Provides clients for document storage (CouchDB) and graph databases (JanusGraph).
"""

from odg_core.nosql.couchdb_client import CouchDBClient

__all__ = [
    "CouchDBClient",
]

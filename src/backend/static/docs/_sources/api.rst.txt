REST API
========

Base URL: ``https://interopdb-staging-f-ca.salmonpebble-cac1724c.northeurope.azurecontainerapps.io``

Interactive documentation is available at `/apidocs/ <https://interopdb-staging-f-ca.salmonpebble-cac1724c.northeurope.azurecontainerapps.io/apidocs/>`_.

Get Entity
----------

Retrieve a gene or strain by local ID or UID.

**Request**::

    GET /<resource>/<identifier>

- ``resource``: ``gene`` or ``strain``
- ``identifier``: Local ID (e.g. ``rpoB``) or UID (e.g. ``G-80D178D48AB8``)

**Response** (200):

.. code-block:: json

    {
      "local_id": "rpoB",
      "uid": "G-80D178D48AB8",
      "entity_type": "gene",
      "attributes": [
        {
          "source_db": "ALEdb",
          "local_id": "rpoB",
          "data": {}
        },
        {
          "source_db": "BiGGr",
          "local_id": "b3987",
          "data": {}
        }
      ]
    }

**Errors**:

- ``400``: Invalid resource type
- ``404``: Entity not found

**Examples**::

    curl /gene/rpoB
    curl /strain/511145
    curl /gene/G-80D178D48AB8

Get Pair
--------

Query a gene-strain pair across all source databases.

**Request**::

    GET /pair/<gene_id>,<strain_id>

- ``gene_id``: Gene local ID or UID
- ``strain_id``: Strain local ID or UID

**Response** (200):

.. code-block:: json

    {
      "gene": "rpoB",
      "strain": "511145",
      "sources": [
        {
          "source": "aledb",
          "data": {"mutations": [], "count": 0}
        },
        {
          "source": "biggr",
          "data": {}
        },
        {
          "source": "pankb",
          "data": {}
        },
        {
          "source": "pmkbase",
          "data": {}
        }
      ]
    }

**Errors**:

- ``400``: Missing gene or strain identifier

**Examples**::

    curl /pair/rpoB,511145
    curl /pair/G-80D178D48AB8,S-6AC722234E99

Search Entities (AJAX)
----------------------

**Request**::

    GET /api/entities?q=<search_term>

Returns up to 200 entities matching the search term against local IDs,
UIDs, and synonyms. Without ``q``, returns the first 200 entities.

**Response** (200):

.. code-block:: json

    {
      "total": 400978,
      "gene_count": 355082,
      "strain_count": 45896,
      "result_gene_count": 5,
      "result_strain_count": 2,
      "entities": [],
      "search_query": "rpoB"
    }

Search Relationships (AJAX)
---------------------------

**Request**::

    GET /api/relationships?q=<search_term>

Returns up to 200 gene-strain relationships matching the search term.

**Response** (200):

.. code-block:: json

    {
      "total": 164067571,
      "result_count": 15,
      "relationships": [],
      "search_query": "rpoB"
    }

Python Client
=============

The ``interopdb`` package provides a Python client and CLI for querying the
Interop DB Registry programmatically.

Installation
------------

.. code-block:: bash

    pip install -e clients/python/

Python API
----------

.. code-block:: python

    from interopdb import InteropClient

    client = InteropClient()

    # Query a gene
    result = client.get_gene("rpoB")
    print(result["uid"])          # G-80D178D48AB8
    print(result["attributes"])   # Data from all source databases

    # Query a strain
    result = client.get_strain("511145")

    # Query a gene-strain pair
    result = client.get_pair("rpoB", "511145")
    for source in result["sources"]:
        print(source["source"], source["data"])

    # Save result to JSON
    client.save_json(result, "output.json")

Custom server URL:

.. code-block:: python

    client = InteropClient(base_url="http://localhost:50505")

Context manager for automatic cleanup:

.. code-block:: python

    with InteropClient() as client:
        result = client.get_gene("rpoB")

CLI
---

Query entities:

.. code-block:: bash

    interopdb gene rpoB
    interopdb strain 511145

Query a gene-strain pair:

.. code-block:: bash

    interopdb pair rpoB 511145

Save results to a file:

.. code-block:: bash

    interopdb gene rpoB -o result.json

Use a custom server:

.. code-block:: bash

    interopdb --url http://localhost:50505 gene rpoB

    # Or via environment variable
    export INTEROPDB_URL=http://localhost:50505
    interopdb gene rpoB

API Reference
-------------

InteropClient
~~~~~~~~~~~~~

``InteropClient(base_url=DEFAULT_URL, timeout=120.0)``
    Create a client instance.

``get_gene(identifier) -> dict``
    Query a gene by local ID or UID. Returns the registry item with attributes
    from all source databases.

``get_strain(identifier) -> dict``
    Query a strain by local ID or UID.

``get_pair(gene_id, strain_id) -> dict``
    Query a gene-strain pair. Returns data from all source databases.

``save_json(data, path) -> None``
    Save a result dictionary to a JSON file.

``close() -> None``
    Close the underlying HTTP connection.

InteropError
~~~~~~~~~~~~

``InteropError(status_code, detail)``
    Raised when an API request returns a non-200 status code.
    Has ``status_code`` and ``detail`` attributes.

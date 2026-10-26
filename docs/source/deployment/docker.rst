
Docker
======

Conductor can be easily run in a Docker container to ensure environment consistency and simplify deployment.

Official Image
--------------

The official Conductor image is based on ``python:3.11-slim``.

Quick Start
-----------

To test if the Docker image works, you can run the following command:

.. code-block:: bash

    docker build -t conductor .
    docker run -it --rm conductor

Persisting Data
---------------

To persist your configuration and plugins, you should mount your local project directory to the ``/app`` directory in the container:

.. code-block:: bash

    docker run -it \
      --name conductor-instance \
      -v $(pwd):/app \
      -p 5678:5678 \
      conductor

Environment Variables
---------------------

You can configure the kernel using environment variables:

- ``FLASK_ENV``: Set to ``development`` for debugging or ``production`` for deployment.
- ``FLASK_DEBUG``: Set to ``1`` to enable Flask debug mode and Conductor plugin hot reload.
- ``CONDUCTOR_DEBUG``: Set to ``1`` to enable Conductor debug mode without relying on Flask-specific environment naming.
- ``CONDUCTOR_CONFIG_PATH``: Path to the configuration file (default: ``./config.json``).

Docker Compose
--------------

For a more robust setup, use the provided ``docker-compose.yml``:

.. code-block:: yaml

    version: '3.8'

    services:
      conductor-backend:
        build: .
        volumes:
          - .:/app
        ports:
          - "5678:5678"
        environment:
          - FLASK_ENV=development
          - FLASK_DEBUG=1
        command: flask run --host=0.0.0.0

Run with:

.. code-block:: bash

    docker-compose up -d

Customizing the Environment
---------------------------

If you need to install additional system packages for your plugins, you can extend the base ``Dockerfile``:

.. code-block:: dockerfile

    FROM conductor:latest

    RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        && rm -rf /var/lib/apt/lists/*

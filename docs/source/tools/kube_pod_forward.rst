Kubernetes Pod Forward Tool
========================

The Kubernetes Pod Forward Tool simplifies port forwarding to pods in a Kubernetes cluster.

Description
----------

This tool allows you to easily forward local ports to Kubernetes pods matching a name pattern.
It handles automatic reconnection if the connection drops, making it useful for development
and debugging scenarios where you need to connect to services in a Kubernetes cluster.

Usage
-----

.. code-block:: bash

    ml_research_tools kube-pod-forward [options] pod_name_pattern

.. program-output:: ml_research_tools kube-pod-forward --help

Examples
--------

Forward local port 8080 to pod with a name containing "web-app":

.. code-block:: bash

    ml_research_tools kube-pod-forward web-app

Specify namespace and different ports:

.. code-block:: bash

    ml_research_tools kube-pod-forward -n production -l 3000 -r 8080 api-service

Features
--------

* **Pattern Matching**: Forwards to the first pod matching the provided name pattern
* **Auto-reconnection**: Automatically reconnects if the connection is lost
* **Visual Interface**: Shows a table of available pods with highlighting for the matched pod
* **Cross-platform**: Works on any system with kubectl configured

Requirements
-----------

This tool requires:

* ``kubectl`` - The Kubernetes command-line tool, properly configured for your cluster

Troubleshooting
--------------

If you encounter issues:

1. Ensure kubectl is installed and in your PATH
2. Verify your kubeconfig is correctly set up
3. Check that you have permissions to access the specified namespace
4. Confirm the pod is running and the specified port is exposed

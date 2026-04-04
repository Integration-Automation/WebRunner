Create Project
==============

Overview
--------

WebRunner can generate a quick-start project structure with sample files,
including example JSON keyword files and Python executor scripts.

Usage
-----

.. code-block:: python

    from je_web_runner import create_project_dir

    # Create on current working directory
    create_project_dir()

    # Create at a specific path
    create_project_dir(project_path="./my_project")

    # Create with a custom parent name
    create_project_dir(project_path="./my_project", parent_name="MyTest")

CLI Method
----------

.. code-block:: bash

    python -m je_web_runner --create_project ./my_project

Generated Structure
-------------------

.. code-block:: text

    my_project/WebRunner/
    ├── keyword/
    │   ├── keyword1.json          # Sample action file (success case)
    │   ├── keyword2.json          # Sample action file (success case)
    │   └── bad_keyword_1.json     # Sample action file (failure case)
    └── executor/
        ├── executor_one_file.py   # Execute a single JSON file
        ├── executor_folder.py     # Execute all JSON files in a folder
        └── executor_bad_file.py   # Execute failure case file

Template Details
----------------

**keyword1.json / keyword2.json**: Sample action lists that demonstrate correct usage
of WebRunner commands (launching a browser, navigating, quitting).

**bad_keyword_1.json**: An intentionally broken action list to demonstrate error handling.

**executor_one_file.py**: Reads and executes a single keyword JSON file using
``execute_action(read_action_json(path))``.

**executor_folder.py**: Uses ``execute_files(get_dir_files_as_list(path))`` to
execute all ``.json`` files in the ``keyword/`` directory.

**executor_bad_file.py**: Executes the bad keyword file to demonstrate
how errors are captured and reported.

Parameters
----------

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Parameter
     - Default
     - Description
   * - ``project_path``
     - Current working directory
     - Path where the project will be created
   * - ``parent_name``
     - ``"WebRunner"``
     - Name of the top-level project directory

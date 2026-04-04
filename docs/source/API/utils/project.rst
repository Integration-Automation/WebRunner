Project API
===========

``je_web_runner.utils.project.create_project_structure``

.. code-block:: python

    def create_dir(dir_name: str) -> None:
        """
        Create a directory (with parents, no error if exists).

        :param dir_name: directory path to create
        """

    def create_template(parent_name: str, project_path: str = None) -> None:
        """
        Create template files (keyword JSONs and executor Python scripts)
        in the project directory.

        :param parent_name: project name (subdirectory name)
        :param project_path: project base path (default: current working directory)
        """

    def create_project_dir(project_path: str = None, parent_name: str = "WebRunner") -> None:
        """
        Create project directory structure and generate template files.
        Creates keyword/ and executor/ subdirectories with sample files.

        :param project_path: path where the project will be created (default: cwd)
        :param parent_name: top-level project directory name (default: "WebRunner")
        """

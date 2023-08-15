Project API
----

.. code-block:: python

    def create_dir(dir_name: str) -> None:
        """
        :param dir_name: create dir use dir name
        :return: None
        """
        Path(dir_name).mkdir(
            parents=True,
            exist_ok=True
        )

.. code-block:: python

    def create_template(parent_name: str, project_path: str = None) -> None:
        """
        create template ob project dir
        :param parent_name: project name
        :param project_path: project create path
        :return: None
        """

.. code-block:: python

    def create_project_dir(project_path: str = None, parent_name: str = "WebRunner") -> None:
        """
        :param parent_name: project name
        :param project_path: project create path
        :return: None
        """
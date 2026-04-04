File Process API
================

``je_web_runner.utils.file_process.get_dir_file_list``

.. code-block:: python

    def get_dir_files_as_list(
        dir_path: str = getcwd(),
        default_search_file_extension: str = ".json"
    ) -> List[str]:
        """
        Recursively walk a directory and return files matching the given extension.

        :param dir_path: directory to search (default: current working directory)
        :param default_search_file_extension: file extension to filter (default: ".json")
        :return: list of absolute file paths, or empty list if none found
        """

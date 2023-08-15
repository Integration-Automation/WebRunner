Generate report API
----

.. code-block:: python

    def generate_html() -> str:
        """
        :return: html_string
        """

.. code-block:: python

    def generate_html_report(html_name: str = "default_name"):
        """
        this function will create and save html report on current folder
        :param html_name: save html file name
        """

.. code-block:: python

    def generate_json():
        """
        :return: success test dict and failure test dict
        """

.. code-block:: python

    def generate_json_report(json_file_name: str = "default_name"):
        """
        :param json_file_name: save json file's name
        """

.. code-block:: python

    def generate_xml():
        """
        :return: success test dict and failure test dict
        """

.. code-block:: python

    def generate_xml_report(xml_file_name: str = "default_name"):
        """
        :param xml_file_name: save xml use xml_file_name
        """
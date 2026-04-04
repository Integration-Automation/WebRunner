Generate Report API
===================

``je_web_runner.utils.generate_report``

HTML Report
-----------

``je_web_runner.utils.generate_report.generate_html_report``

.. code-block:: python

    def generate_html() -> str:
        """
        Generate a complete HTML report string from test_record_instance.

        The report contains color-coded tables:
        - aqua (event_table_head) for successful actions
        - red (failure_table_head) for failed actions

        :return: complete HTML document string
        :raises WebRunnerHTMLException: if no test records exist
        """

    def generate_html_report(html_name: str = "default_name") -> None:
        """
        Generate and save an HTML report file.
        Thread-safe (uses threading.Lock).

        :param html_name: output file name without extension (creates {html_name}.html)
        """

JSON Report
-----------

``je_web_runner.utils.generate_report.generate_json_report``

.. code-block:: python

    def generate_json() -> tuple:
        """
        Generate JSON report data from test_record_instance.

        :return: tuple of (success_dict, failure_dict)
        """

    def generate_json_report(json_file_name: str = "default_name") -> None:
        """
        Generate and save JSON report files.
        Creates two files: {json_file_name}_success.json and {json_file_name}_failure.json.
        Thread-safe (uses threading.Lock).

        :param json_file_name: base file name without extension
        """

XML Report
----------

``je_web_runner.utils.generate_report.generate_xml_report``

.. code-block:: python

    def generate_xml() -> tuple:
        """
        Generate XML report data from test_record_instance.

        :return: tuple of (success_records, failure_records)
        """

    def generate_xml_report(xml_file_name: str = "default_name") -> None:
        """
        Generate and save XML report files.
        Creates two files: {xml_file_name}_success.xml and {xml_file_name}_failure.xml.

        :param xml_file_name: base file name without extension
        """

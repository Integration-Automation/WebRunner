==================
WebRunner Html Report Doc
==================

.. code-block:: python

    """
    need test_record_instance.set_record_enable(True) first
    """
    def generate_html(html_name: str = "default_name") -> str:
        """
        this function will create and save html report on current folder
        :param html_name: save html file name
        :return: html_string
        """
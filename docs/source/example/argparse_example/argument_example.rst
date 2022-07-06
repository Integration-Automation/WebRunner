==================
WebRunner command Example
==================

.. code-block:: python

    """
    cd to workdir
    python je_web_runner + action file path
    or programming use
    """

    import os

    print(os.getcwd())

    os.system("cd " + os.getcwd())
    "execute one file"
    os.system("python -m je_web_runner --execute_file " + os.getcwd() + r"/test/unit_test/argparse/test1.json")
    "execute all file on folder"
    os.system("python -m je_web_runner --execute_dir " + os.getcwd() + r"/test/unit_test/argparse")

# This example is primarily intended to remind users of the importance of verifying input.
from je_web_runner import execute_action, read_action_json
    
execute_action(
    read_action_json(
        r"C:\Users\JeffreyChen\Desktop\Code_Space\WebRunner\test\unit_test\create_project_test/WebRunner/keyword/bad_keyword_1.json"
    )
)

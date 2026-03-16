import ast
from utils.logger import get_logger

logger = get_logger("validator")


def validator_node(state):

    logger.info("Validator Agent running")

    edited_files = state.get("edited_files", [])

    validation_results = {}
    has_error          = False

    for file_path in edited_files:

        try:

            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()

            ast.parse(code)

            logger.info("Syntax OK: %s", file_path)

            validation_results[file_path] = "valid"

        except SyntaxError as e:

            logger.error("Syntax Error in %s: %s", file_path, e)

            validation_results[file_path] = str(e)
            has_error = True

    state["validation_results"] = validation_results
    state["has_error"]          = has_error

    return state

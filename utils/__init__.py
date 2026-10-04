import logging


def logged_input(logger: logging.Logger, prompt: str) -> str:
    logger.info("%s", prompt)
    value = input()
    logger.info("用户输入：%s", value)
    return value


language_map = {
    0: "jp",
    1: "en",
    2: "cn",
    3: "tw"
}

def generate_next_signature(eval: str, storage: str, target: str, type: str) -> str:
    return f"eval={eval}|storage={storage}|target={target}|type={type}"

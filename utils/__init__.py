language_map = {
    0: "jp",
    1: "en",
    2: "sc",
    3: "tc"
}

def generate_next_signature(eval: str, storage: str, target: str, type: str) -> str:
    return f"eval={eval}|storage={storage}|target={target}|type={type}"

def build_message(data: str) -> str:
    """Construye un mensaje simple con el formato STX-DATA-ETX"""
    return f"<STX>{data}<ETX>"
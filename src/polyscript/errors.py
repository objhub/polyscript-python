"""PolyScript error hierarchy."""


class PolyScriptError(Exception):
    def __init__(self, message: str, line: int | None = None, column: int | None = None):
        self.line = line
        self.column = column
        loc = f" (line {line}" + (f", col {column}" if column else "") + ")" if line else ""
        super().__init__(f"{message}{loc}")


class ParseError(PolyScriptError):
    pass


class ValidationError(PolyScriptError):
    pass


class CodegenError(PolyScriptError):
    pass


class ExecutionError(PolyScriptError):
    pass

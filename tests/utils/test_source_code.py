from pypss.utils.source_code import extract_function_code


class TestSourceCode:
    def test_extract_function_code(self, tmp_path):
        file_path = tmp_path / "code.py"
        code = """
def my_func():
    x = 1
    y = 2
    return x + y

def other_func():
    pass
"""
        file_path.write_text(code.strip())

        # Extract my_func (starts at line 1)
        extracted = extract_function_code(str(file_path), 1)
        assert "def my_func():" in extracted
        assert "return x + y" in extracted
        assert "def other_func():" not in extracted

    def test_extract_function_code_missing(self):
        assert "not available" in extract_function_code("missing.py", 1)

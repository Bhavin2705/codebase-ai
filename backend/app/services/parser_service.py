import ast
import re
from typing import Any, List, Dict, Tuple, Optional


def find_matching_brace(code: str, start_index: int) -> int:
    """
    Finds the index of the matching closing brace '}' starting after start_index.
    Properly handles single/double quotes, template literals, and comments.
    """
    n = len(code)
    first_brace = code.find("{", start_index)
    if first_brace == -1:
        return -1

    depth = 0
    in_single_quote = False
    in_double_quote = False
    in_template_literal = False
    in_line_comment = False
    in_block_comment = False
    i = first_brace

    while i < n:
        char = code[i]
        prev_char = code[i - 1] if i > 0 else ""
        next_char = code[i + 1] if i + 1 < n else ""

        # Handle comments
        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        # Handle strings & template literals
        if in_single_quote:
            if char == "'" and prev_char != "\\":
                in_single_quote = False
            i += 1
            continue

        if in_double_quote:
            if char == '"' and prev_char != "\\":
                in_double_quote = False
            i += 1
            continue

        if in_template_literal:
            if char == "`" and prev_char != "\\":
                in_template_literal = False
            i += 1
            continue

        # Check comment triggers
        if char == "/" and next_char == "/":
            in_line_comment = True
            i += 2
            continue
        if char == "/" and next_char == "*":
            in_block_comment = True
            i += 2
            continue

        # Check string triggers
        if char == "'":
            in_single_quote = True
            i += 1
            continue
        if char == '"':
            in_double_quote = True
            i += 1
            continue
        if char == "`":
            in_template_literal = True
            i += 1
            continue

        # Track braces
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return i

        i += 1

    return -1


class PythonASTSymbolVisitor(ast.NodeVisitor):
    def __init__(self, code_lines: List[str]):
        self.code_lines = code_lines
        self.symbols: List[Dict[str, Any]] = []
        self.class_stack: List[str] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", node.lineno)
        source_code = "\n".join(self.code_lines[start_line - 1 : end_line])

        bases_list = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                bases_list.append(b.id)
            elif isinstance(b, ast.Attribute):
                bases_list.append(b.attr)
        bases_str = f"({', '.join(bases_list)})" if bases_list else ""
        signature = f"class {node.name}{bases_str}"

        self.symbols.append({
            "name": node.name,
            "symbol_type": "class",
            "signature": signature,
            "source_code": source_code,
            "start_line": start_line,
            "end_line": end_line,
        })

        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._record_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._record_function(node, is_async=True)

    def _record_function(self, node: Any, is_async: bool):
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", node.lineno)
        source_code = "\n".join(self.code_lines[start_line - 1 : end_line])

        args_list = [arg.arg for arg in getattr(node.args, "args", [])]
        args_str = ", ".join(args_list)
        prefix = "async def" if is_async else "def"
        signature = f"{prefix} {node.name}({args_str})"
        symbol_type = "method" if self.class_stack else "function"

        self.symbols.append({
            "name": node.name,
            "symbol_type": symbol_type,
            "signature": signature,
            "source_code": source_code,
            "start_line": start_line,
            "end_line": end_line,
        })

        self.generic_visit(node)


class CodeParserService:
    """
    Lightweight, high-performance syntactic code parser.
    Uses native Python `ast` for Python files and robust syntactic brace/boundary tracking
    for JavaScript, TypeScript, JSX, TSX, Java, and fallback languages without heavy native C binaries.
    """

    def _chunk_file(self, file_path: str, code_content: str) -> List[Dict[str, Any]]:
        lines = code_content.splitlines()
        total_lines = len(lines)
        if total_lines == 0:
            return []

        chunks: List[Dict[str, Any]] = []
        chunk_size = 120
        overlap = 20
        step = chunk_size - overlap

        start = 0
        while start < total_lines:
            end = min(start + chunk_size, total_lines)
            chunk_lines = lines[start:end]
            start_line = start + 1
            end_line = end
            chunk_source = "\n".join(chunk_lines)

            chunks.append({
                "name": f"FileChunk_{start_line}_{end_line}",
                "symbol_type": "chunk",
                "signature": file_path,
                "source_code": chunk_source,
                "start_line": start_line,
                "end_line": end_line,
            })

            if end >= total_lines:
                break
            start += step

        return chunks

    def parse_file(self, file_path: str, code_content: str, language: str) -> List[Dict[str, Any]]:
        # For large files or minified code over 50KB, generate deterministic line chunks
        if len(code_content) > 50000 or any(len(line) > 1000 for line in code_content.splitlines()[:10]):
            return self._chunk_file(file_path, code_content)

        target = language.lower().strip(".")

        if target in ("py", "python"):
            return self._parse_python(file_path, code_content)
        elif target in ("js", "jsx", "javascript", "mjs", "cjs", "ts", "tsx", "typescript"):
            return self._parse_javascript_typescript(file_path, code_content)
        else:
            return self._fallback_parse(file_path, code_content, target)

    def _parse_python(self, file_path: str, code_content: str) -> List[Dict[str, Any]]:
        try:
            tree = ast.parse(code_content, filename=file_path)
            lines = code_content.splitlines()
            visitor = PythonASTSymbolVisitor(lines)
            visitor.visit(tree)
            if visitor.symbols:
                return visitor.symbols
        except Exception:
            pass

        return self._fallback_parse(file_path, code_content, "python")

    def _parse_javascript_typescript(self, file_path: str, code_content: str) -> List[Dict[str, Any]]:
        extracted_symbols: List[Dict[str, Any]] = []
        seen_ranges: set[Tuple[int, int]] = set()

        # 1. Express / Router route declarations: router.get('/path', ...), app.post('/path', ...)
        route_pattern = re.compile(
            r"(?:^|\s)(router|app)\.(get|post|put|delete|patch|use)\s*\(\s*(['\"`][^'\"`]+['\"`])",
            re.MULTILINE
        )
        for match in route_pattern.finditer(code_content):
            start_pos = match.start()
            line_no = code_content[:start_pos].count("\n") + 1
            obj_name, method, path_literal = match.groups()
            clean_path = path_literal.strip("'\"`")
            route_name = f"{obj_name}.{method}('{clean_path}')"

            # Find boundary of the statement
            end_brace = find_matching_brace(code_content, match.end())
            if end_brace != -1:
                end_pos = code_content.find(";", end_brace)
                end_pos = end_pos + 1 if end_pos != -1 else end_brace + 1
            else:
                end_pos = code_content.find(");", start_pos)
                end_pos = end_pos + 2 if end_pos != -1 else match.end()

            end_line = code_content[:end_pos].count("\n") + 1
            source_snippet = code_content[start_pos:end_pos].strip()

            extracted_symbols.append({
                "name": route_name,
                "symbol_type": "route",
                "signature": f"{method.upper()} {clean_path}",
                "source_code": source_snippet or match.group(0),
                "start_line": line_no,
                "end_line": max(line_no, end_line),
            })
            seen_ranges.add((line_no, end_line))

        # 2. Mongoose models: const User = mongoose.model('User', schema)
        model_pattern = re.compile(
            r"(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:mongoose\.)?model\s*\(\s*(['\"`][^'\"`]+['\"`])",
            re.MULTILINE
        )
        for match in model_pattern.finditer(code_content):
            start_pos = match.start()
            line_no = code_content[:start_pos].count("\n") + 1
            var_name, model_str = match.groups()
            clean_model = model_str.strip("'\"`")

            end_pos = code_content.find(";", start_pos)
            end_pos = end_pos + 1 if end_pos != -1 else match.end()
            end_line = code_content[:end_pos].count("\n") + 1

            extracted_symbols.append({
                "name": clean_model or var_name,
                "symbol_type": "model",
                "signature": f"mongoose.model('{clean_model}')",
                "source_code": code_content[start_pos:end_pos].strip(),
                "start_line": line_no,
                "end_line": max(line_no, end_line),
            })
            seen_ranges.add((line_no, end_line))

        # 3. Class declarations: class UserProfile extends React.Component { ... }
        class_pattern = re.compile(
            r"(?:export\s+)?(?:default\s+)?class\s+([A-Za-z0-9_]+)(?:\s+extends\s+[A-Za-z0-9_.]+)?\s*\{",
            re.MULTILINE
        )
        for match in class_pattern.finditer(code_content):
            start_pos = match.start()
            line_no = code_content[:start_pos].count("\n") + 1
            class_name = match.group(1)

            end_brace = find_matching_brace(code_content, match.end() - 1)
            end_pos = end_brace + 1 if end_brace != -1 else match.end()
            end_line = code_content[:end_pos].count("\n") + 1

            extracted_symbols.append({
                "name": class_name,
                "symbol_type": "class",
                "signature": f"class {class_name}",
                "source_code": code_content[start_pos:end_pos].strip(),
                "start_line": line_no,
                "end_line": max(line_no, end_line),
            })
            seen_ranges.add((line_no, end_line))

        # 4. Interfaces and Types (TypeScript)
        ts_type_pattern = re.compile(
            r"(?:export\s+)?(interface|type)\s+([A-Za-z0-9_]+)",
            re.MULTILINE
        )
        for match in ts_type_pattern.finditer(code_content):
            start_pos = match.start()
            line_no = code_content[:start_pos].count("\n") + 1
            decl_kind, name = match.groups()

            end_brace = find_matching_brace(code_content, match.end())
            if end_brace != -1:
                end_pos = end_brace + 1
            else:
                end_pos = code_content.find(";", start_pos)
                end_pos = end_pos + 1 if end_pos != -1 else match.end()

            end_line = code_content[:end_pos].count("\n") + 1

            extracted_symbols.append({
                "name": name,
                "symbol_type": "interface" if decl_kind == "interface" else "type",
                "signature": f"{decl_kind} {name}",
                "source_code": code_content[start_pos:end_pos].strip(),
                "start_line": line_no,
                "end_line": max(line_no, end_line),
            })

        # 5. Standard function declarations: function UserProfile(...) { ... }
        func_pattern = re.compile(
            r"(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*([A-Za-z0-9_]*)\s*\(([^)]*)\)\s*\{",
            re.MULTILINE
        )
        for match in func_pattern.finditer(code_content):
            start_pos = match.start()
            line_no = code_content[:start_pos].count("\n") + 1
            name, params = match.groups()
            func_name = name or "anonymousFunction"

            end_brace = find_matching_brace(code_content, match.end() - 1)
            end_pos = end_brace + 1 if end_brace != -1 else match.end()
            end_line = code_content[:end_pos].count("\n") + 1

            is_component = bool(func_name and func_name[0].isupper())
            extracted_symbols.append({
                "name": func_name,
                "symbol_type": "component" if is_component else "function",
                "signature": f"function {func_name}({params.strip()})",
                "source_code": code_content[start_pos:end_pos].strip(),
                "start_line": line_no,
                "end_line": max(line_no, end_line),
            })
            seen_ranges.add((line_no, end_line))

        # 6. Arrow functions & Variable functional declarations: const UserCard = (...) => { ... }
        var_func_pattern = re.compile(
            r"(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z0-9_]+)\s*=>\s*\{?",
            re.MULTILINE
        )
        for match in var_func_pattern.finditer(code_content):
            start_pos = match.start()
            line_no = code_content[:start_pos].count("\n") + 1
            var_name = match.group(1)

            if any(s["name"] == var_name for s in extracted_symbols):
                continue

            # Check if block-bodied { ... } or concise-bodied
            if "{" in code_content[match.start():match.end() + 2]:
                end_brace = find_matching_brace(code_content, match.end() - 1)
                end_pos = end_brace + 1 if end_brace != -1 else match.end()
            else:
                end_semi = code_content.find(";", start_pos)
                end_pos = end_semi + 1 if end_semi != -1 else match.end()

            end_line = code_content[:end_pos].count("\n") + 1
            is_component = bool(var_name and var_name[0].isupper())

            extracted_symbols.append({
                "name": var_name,
                "symbol_type": "component" if is_component else "function",
                "signature": f"const {var_name}",
                "source_code": code_content[start_pos:end_pos].strip(),
                "start_line": line_no,
                "end_line": max(line_no, end_line),
            })

        if extracted_symbols:
            return extracted_symbols

        return self._fallback_parse(file_path, code_content, "javascript")


    def _fallback_parse(self, file_path: str, code_content: str, target_language: str) -> List[Dict[str, Any]]:
        extracted_symbols: List[Dict[str, Any]] = []
        lines = code_content.splitlines()

        # Generic function/class regex fallback
        generic_class = re.compile(r"^\s*(?:class|struct|type|interface)\s+([A-Za-z0-9_]+)", re.MULTILINE)
        for m in generic_class.finditer(code_content):
            line_no = code_content[:m.start()].count("\n") + 1
            extracted_symbols.append({
                "name": m.group(1),
                "symbol_type": "class",
                "signature": m.group(0).strip(),
                "source_code": m.group(0).strip(),
                "start_line": line_no,
                "end_line": line_no,
            })

        generic_func = re.compile(r"^\s*(?:def|function|fn|func|pub fn)\s+([A-Za-z0-9_]+)", re.MULTILINE)
        for m in generic_func.finditer(code_content):
            line_no = code_content[:m.start()].count("\n") + 1
            extracted_symbols.append({
                "name": m.group(1),
                "symbol_type": "function",
                "signature": m.group(0).strip(),
                "source_code": m.group(0).strip(),
                "start_line": line_no,
                "end_line": line_no,
            })

        if not extracted_symbols:
            file_name = file_path.replace("\\", "/").split("/")[-1]
            extracted_symbols.append({
                "name": file_name,
                "symbol_type": "file",
                "signature": file_path,
                "source_code": code_content[:1500],
                "start_line": 1,
                "end_line": max(1, len(lines)),
            })

        return extracted_symbols

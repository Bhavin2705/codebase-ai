from typing import Any

try:
    from tree_sitter import Language, Parser
    import tree_sitter_java as tsjava
    import tree_sitter_python as tspython
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False

try:
    import tree_sitter_javascript as tsjs
    HAS_JS_TREE_SITTER = True
except ImportError:
    HAS_JS_TREE_SITTER = False

class CodeParserService:
    def __init__(self):
        self.parsers = {}
        if HAS_TREE_SITTER:
            try:
                self.parsers['java'] = Parser(Language(tsjava.language()))
                self.parsers['python'] = Parser(Language(tspython.language()))
            except Exception:
                pass

        if HAS_JS_TREE_SITTER:
            try:
                js_parser = Parser(Language(tsjs.language()))
                self.parsers['javascript'] = js_parser
                self.parsers['js'] = js_parser
                self.parsers['jsx'] = js_parser
                self.parsers['ts'] = js_parser
                self.parsers['tsx'] = js_parser
            except Exception:
                pass

    def parse_file(self, file_path: str, code_content: str, language: str) -> list[dict[str, Any]]:
        target_language = language.lower().strip('.')
        if target_language not in self.parsers:
            # Map extensions
            if target_language in ('js', 'jsx', 'ts', 'tsx', 'javascript', 'typescript'):
                target_language = 'javascript' if 'javascript' in self.parsers else target_language

        if target_language not in self.parsers:
            return self._fallback_parse(file_path, code_content, target_language)

        parser = self.parsers[target_language]
        tree = parser.parse(bytes(code_content, "utf8"))
        root_node = tree.root_node

        extracted_symbols = []
        if target_language == 'java':
            self._extract_java_symbols(root_node, code_content, extracted_symbols)
        elif target_language == 'python':
            self._extract_python_symbols(root_node, code_content, extracted_symbols)
        elif target_language in ('javascript', 'js', 'jsx', 'ts', 'tsx'):
            self._extract_js_symbols(root_node, code_content, extracted_symbols)

        return extracted_symbols if extracted_symbols else self._fallback_parse(file_path, code_content, target_language)

    def _extract_java_symbols(self, ast_node: Any, source_code: str, extracted_symbols: list):
        if ast_node.type in ("class_declaration", "interface_declaration"):
            name_node = ast_node.child_by_field_name("name")
            name = name_node.text.decode("utf8") if name_node else "UnknownClass"
            extracted_symbols.append({
                "name": name,
                "symbol_type": "class" if ast_node.type == "class_declaration" else "interface",
                "signature": f"public class {name}",
                "source_code": source_code[ast_node.start_byte:ast_node.end_byte],
                "start_line": ast_node.start_point[0] + 1,
                "end_line": ast_node.end_point[0] + 1
            })

        elif ast_node.type == "method_declaration":
            name_node = ast_node.child_by_field_name("name")
            name = name_node.text.decode("utf8") if name_node else "unknownMethod"
            extracted_symbols.append({
                "name": name,
                "symbol_type": "method",
                "signature": f"{name}()",
                "source_code": source_code[ast_node.start_byte:ast_node.end_byte],
                "start_line": ast_node.start_point[0] + 1,
                "end_line": ast_node.end_point[0] + 1
            })

        for child_node in ast_node.children:
            self._extract_java_symbols(child_node, source_code, extracted_symbols)

    def _extract_python_symbols(self, ast_node: Any, source_code: str, extracted_symbols: list):
        if ast_node.type == "class_definition":
            name_node = ast_node.child_by_field_name("name")
            name = name_node.text.decode("utf8") if name_node else "UnknownClass"
            extracted_symbols.append({
                "name": name,
                "symbol_type": "class",
                "signature": f"class {name}",
                "source_code": source_code[ast_node.start_byte:ast_node.end_byte],
                "start_line": ast_node.start_point[0] + 1,
                "end_line": ast_node.end_point[0] + 1
            })

        elif ast_node.type in ("function_definition", "async_function_definition"):
            name_node = ast_node.child_by_field_name("name")
            name = name_node.text.decode("utf8") if name_node else "unknown_func"
            extracted_symbols.append({
                "name": name,
                "symbol_type": "function",
                "signature": f"def {name}()",
                "source_code": source_code[ast_node.start_byte:ast_node.end_byte],
                "start_line": ast_node.start_point[0] + 1,
                "end_line": ast_node.end_point[0] + 1
            })

        for child_node in ast_node.children:
            self._extract_python_symbols(child_node, source_code, extracted_symbols)

    def _extract_js_symbols(self, ast_node: Any, source_code: str, extracted_symbols: list):
        snippet_text = source_code[ast_node.start_byte:ast_node.end_byte]

        if ast_node.type in ("function_declaration", "generator_function_declaration"):
            name_node = ast_node.child_by_field_name("name")
            name = name_node.text.decode("utf8") if name_node else "anonymousFunction"
            is_component = name[0].isupper() if name else False
            extracted_symbols.append({
                "name": name,
                "symbol_type": "component" if is_component else "function",
                "signature": f"function {name}()",
                "source_code": snippet_text,
                "start_line": ast_node.start_point[0] + 1,
                "end_line": ast_node.end_point[0] + 1
            })

        elif ast_node.type == "class_declaration":
            name_node = ast_node.child_by_field_name("name")
            name = name_node.text.decode("utf8") if name_node else "UnknownClass"
            extracted_symbols.append({
                "name": name,
                "symbol_type": "class",
                "signature": f"class {name}",
                "source_code": snippet_text,
                "start_line": ast_node.start_point[0] + 1,
                "end_line": ast_node.end_point[0] + 1
            })

        elif ast_node.type in ("interface_declaration", "type_alias_declaration"):
            name_node = ast_node.child_by_field_name("name")
            name = name_node.text.decode("utf8") if name_node else "UnknownType"
            extracted_symbols.append({
                "name": name,
                "symbol_type": "interface" if ast_node.type == "interface_declaration" else "type",
                "signature": f"{ast_node.type.replace('_declaration', '')} {name}",
                "source_code": snippet_text,
                "start_line": ast_node.start_point[0] + 1,
                "end_line": ast_node.end_point[0] + 1
            })

        elif ast_node.type == "expression_statement":
            # Detect Express routes: app.get('/path', ...), router.post('/path', ...)
            if any(term in snippet_text for term in ("router.", "app.get(", "app.post(", "app.put(", "app.delete(", "router.get(", "router.post(", "router.put(", "router.delete(")):
                first_line_code = snippet_text.split('\n')[0].strip()
                extracted_symbols.append({
                    "name": first_line_code.split('(')[0],
                    "symbol_type": "route",
                    "signature": first_line_code,
                    "source_code": snippet_text,
                    "start_line": ast_node.start_point[0] + 1,
                    "end_line": ast_node.end_point[0] + 1
                })

        elif ast_node.type in ("lexical_declaration", "variable_declaration"):
            # Captures const handleClick = () => {}, const User = mongoose.model(...), const userSchema = new Schema(...)
            if "=>" in snippet_text or "function" in snippet_text or "router." in snippet_text or "model(" in snippet_text or "Schema(" in snippet_text:
                variable_declarators = [c for c in ast_node.children if c.type == "variable_declarator"]
                for variable_declarator in variable_declarators:
                    name_node = variable_declarator.child_by_field_name("name")
                    if name_node:
                        name = name_node.text.decode("utf8")
                        extracted_symbol_type = "function"
                        if "mongoose.model" in snippet_text or "new Schema" in snippet_text or "model(" in snippet_text:
                            extracted_symbol_type = "model"
                        elif name[0].isupper():
                            extracted_symbol_type = "component"

                        extracted_symbols.append({
                            "name": name,
                            "symbol_type": extracted_symbol_type,
                            "signature": f"const {name}",
                            "source_code": snippet_text,
                            "start_line": ast_node.start_point[0] + 1,
                            "end_line": ast_node.end_point[0] + 1
                        })

        for child_node in ast_node.children:
            self._extract_js_symbols(child_node, source_code, extracted_symbols)

    def _fallback_parse(self, file_path: str, code_content: str, target_language: str) -> list[dict[str, Any]]:
        import re
        extracted_symbols = []
        lines = code_content.split("\n")

        if target_language in ("js", "jsx", "ts", "tsx", "javascript", "typescript"):
            # Regex extraction for MERN constructs if tree-sitter parser is unavailable
            # 1. Express routes
            route_matches = re.finditer(r"(router|app)\.(get|post|put|delete|patch|use)\s*\(\s*['\"]([^'\"]+)['\"]", code_content)
            for regex_match in route_matches:
                line_number = code_content[:regex_match.start()].count("\n") + 1
                extracted_symbols.append({
                    "name": f"{regex_match.group(1)}.{regex_match.group(2)}('{regex_match.group(3)}')",
                    "symbol_type": "route",
                    "signature": f"{regex_match.group(2).upper()} {regex_match.group(3)}",
                    "source_code": regex_match.group(0),
                    "start_line": line_number,
                    "end_line": line_number
                })

            # 2. Mongoose models
            model_matches = re.finditer(r"const\s+([A-Za-z0-9_]+)\s*=\s*(?:mongoose\.)?model\s*\(\s*['\"]([^'\"]+)['\"]", code_content)
            for regex_match in model_matches:
                line_number = code_content[:regex_match.start()].count("\n") + 1
                extracted_symbols.append({
                    "name": regex_match.group(1),
                    "symbol_type": "model",
                    "signature": f"mongoose.model('{regex_match.group(2)}')",
                    "source_code": regex_match.group(0),
                    "start_line": line_number,
                    "end_line": line_number
                })

            # 3. React components / Functions
            func_matches = re.finditer(r"(?:export\s+)?(?:function|const)\s+([A-Za-z0-9_]+)\s*=?\s*(?:function|\([^)]*\)\s*=>)", code_content)
            for regex_match in func_matches:
                name = regex_match.group(1)
                line_number = code_content[:regex_match.start()].count("\n") + 1
                extracted_symbols.append({
                    "name": name,
                    "symbol_type": "component" if name[0].isupper() else "function",
                    "signature": f"function/const {name}",
                    "source_code": regex_match.group(0),
                    "start_line": line_number,
                    "end_line": line_number
                })

        if not extracted_symbols:
            file_name = file_path.replace("\\", "/").split("/")[-1]
            extracted_symbols.append({
                "name": file_name,
                "symbol_type": "file",
                "signature": file_path,
                "source_code": code_content[:500],
                "start_line": 1,
                "end_line": len(lines)
            })

        return extracted_symbols



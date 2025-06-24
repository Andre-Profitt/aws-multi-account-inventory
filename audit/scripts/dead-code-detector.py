#!/usr/bin/env python3
"""
Dead Code Detection Script
Identifies unused functions, classes, and variables in the codebase
"""

import ast
import json
import sys
from pathlib import Path


class DeadCodeDetector:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.defined_symbols = {}  # file -> set of defined symbols
        self.used_symbols = {}     # file -> set of used symbols
        self.imports = {}          # file -> set of imported symbols
        self.global_definitions = set()
        self.global_usage = set()

    def analyze_file(self, filepath: Path) -> tuple[set[str], set[str]]:
        """Analyze a single Python file for definitions and usage"""
        with open(filepath, encoding='utf-8') as f:
            try:
                tree = ast.parse(f.read(), str(filepath))
            except SyntaxError:
                print(f"Syntax error in {filepath}")
                return set(), set()

        definitions = set()
        usage = set()

        class DefinitionVisitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                definitions.add(node.name)
                self.generic_visit(node)

            def visit_AsyncFunctionDef(self, node):
                definitions.add(node.name)
                self.generic_visit(node)

            def visit_ClassDef(self, node):
                definitions.add(node.name)
                self.generic_visit(node)

            def visit_Assign(self, node):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        definitions.add(target.id)
                self.generic_visit(node)

        class UsageVisitor(ast.NodeVisitor):
            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Load):
                    usage.add(node.id)
                self.generic_visit(node)

            def visit_Attribute(self, node):
                if isinstance(node.value, ast.Name):
                    usage.add(node.value.id)
                self.generic_visit(node)

            def visit_Call(self, node):
                if isinstance(node.func, ast.Name):
                    usage.add(node.func.id)
                self.generic_visit(node)

        # Find definitions
        def_visitor = DefinitionVisitor()
        def_visitor.visit(tree)

        # Find usage
        use_visitor = UsageVisitor()
        use_visitor.visit(tree)

        # Handle imports specially
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    usage.add(name)

        return definitions, usage

    def scan_project(self) -> dict[str, list[str]]:
        """Scan entire project for dead code"""
        # Find all Python files
        python_files = list(self.project_root.rglob("*.py"))

        # Exclude virtual environments and build directories
        excluded_dirs = {'venv', '.venv', 'build', 'dist', '__pycache__', '.tox', 'site-packages'}
        python_files = [
            f for f in python_files
            if not any(excluded in f.parts for excluded in excluded_dirs)
        ]

        print(f"Analyzing {len(python_files)} Python files...")

        # Analyze each file
        for filepath in python_files:
            relative_path = filepath.relative_to(self.project_root)
            defs, uses = self.analyze_file(filepath)

            self.defined_symbols[str(relative_path)] = defs
            self.used_symbols[str(relative_path)] = uses
            self.global_definitions.update(defs)
            self.global_usage.update(uses)

        # Find potentially dead code
        dead_code = {
            'unused_functions': [],
            'unused_classes': [],
            'unused_variables': [],
            'unused_imports': []
        }

        # Check each file for unused definitions
        for filepath, definitions in self.defined_symbols.items():
            file_usage = self.used_symbols.get(filepath, set())

            for symbol in definitions:
                # Check if symbol is used anywhere in the project
                if symbol not in self.global_usage:
                    # Classify the type of dead code
                    if self._is_function(symbol):
                        if not symbol.startswith('_'):  # Ignore private functions
                            dead_code['unused_functions'].append({
                                'file': filepath,
                                'symbol': symbol
                            })
                    elif self._is_class(symbol):
                        dead_code['unused_classes'].append({
                            'file': filepath,
                            'symbol': symbol
                        })
                    else:
                        if not symbol.startswith('_'):  # Ignore private variables
                            dead_code['unused_variables'].append({
                                'file': filepath,
                                'symbol': symbol
                            })

        return dead_code

    def _is_function(self, symbol: str) -> bool:
        """Check if symbol is likely a function"""
        # Simple heuristic - functions usually have lowercase names
        return symbol.islower() or '_' in symbol

    def _is_class(self, symbol: str) -> bool:
        """Check if symbol is likely a class"""
        # Classes usually start with uppercase
        return symbol[0].isupper() if symbol else False

    def generate_report(self, output_file: str = 'dead_code_report.json'):
        """Generate dead code report"""
        dead_code = self.scan_project()

        # Calculate statistics
        total_dead = sum(len(items) for items in dead_code.values())

        report = {
            'summary': {
                'total_files_analyzed': len(self.defined_symbols),
                'total_dead_code_items': total_dead,
                'unused_functions': len(dead_code['unused_functions']),
                'unused_classes': len(dead_code['unused_classes']),
                'unused_variables': len(dead_code['unused_variables'])
            },
            'details': dead_code
        }

        # Save JSON report
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)

        # Print summary
        print("\nDead Code Analysis Summary:")
        print(f"Total files analyzed: {report['summary']['total_files_analyzed']}")
        print(f"Total dead code items: {report['summary']['total_dead_code_items']}")
        print(f"  - Unused functions: {report['summary']['unused_functions']}")
        print(f"  - Unused classes: {report['summary']['unused_classes']}")
        print(f"  - Unused variables: {report['summary']['unused_variables']}")

        # Print top offenders
        if dead_code['unused_functions']:
            print("\nTop unused functions:")
            for item in dead_code['unused_functions'][:10]:
                print(f"  - {item['file']}: {item['symbol']}")

        return output_file

if __name__ == '__main__':
    project_root = sys.argv[1] if len(sys.argv) > 1 else '.'
    detector = DeadCodeDetector(project_root)
    report_file = detector.generate_report()
    print(f"\nDetailed report saved to: {report_file}")

"""Code Expert: Code generation with security and quality validation.

Architecture:
1. User query → Parse intent and language
2. Generate code with Starcoder (local inference)
3. Validate syntax with TreeSitter
4. Security scan (placeholder for Semgrep/Bandit)
5. Return code + validation report for human review
"""

from __future__ import annotations

import ast
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class SecurityScanner:
    """Security scanner for generated code (placeholder for Semgrep)."""

    def scan(self, code: str, language: str = "python") -> list[dict[str, Any]]:
        """Scan code for security vulnerabilities.

        In production, integrate with:
        - Semgrep (SAST)
        - Bandit (Python security linter)
        - GitHub CodeQL

        Args:
            code: Code to scan
            language: Programming language

        Returns:
            List of vulnerabilities found
        """
        vulnerabilities = []

        if language == "python":
            # Basic security checks (replace with Semgrep in production)
            dangerous_patterns = [
                (r"eval\(", "CRITICAL", "Use of eval() is dangerous"),
                (r"exec\(", "CRITICAL", "Use of exec() is dangerous"),
                (r"__import__\(", "HIGH", "Dynamic imports should be reviewed"),
                (r"pickle\.loads\(", "HIGH", "Pickle deserialization vulnerability"),
                (r"subprocess\.call\([^,]+,\s*shell=True", "HIGH", "Command injection risk"),
                (r"os\.system\(", "HIGH", "Shell command execution risk"),
                (r"input\([^)]*\).*eval", "CRITICAL", "User input with eval()"),
            ]

            for pattern, severity, message in dangerous_patterns:
                if re.search(pattern, code):
                    vulnerabilities.append(
                        {
                            "severity": severity,
                            "message": message,
                            "pattern": pattern,
                        }
                    )

        return vulnerabilities


class SyntaxValidator:
    """Syntax validator using Python AST and TreeSitter."""

    def __init__(self):
        """Initialize validator."""
        # In production, initialize TreeSitter with language grammars
        # For now, use Python's built-in AST
        pass

    def validate_python(self, code: str) -> tuple[bool, str | None]:
        """Validate Python syntax.

        Args:
            code: Python code to validate

        Returns:
            (is_valid, error_message)
        """
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, f"Syntax error at line {e.lineno}: {e.msg}"

    def validate(self, code: str, language: str = "python") -> tuple[bool, str | None]:
        """Validate code syntax.

        Args:
            code: Code to validate
            language: Programming language

        Returns:
            (is_valid, error_message)
        """
        if language == "python":
            return self.validate_python(code)
        else:
            # For other languages, would use TreeSitter
            logger.warning(f"Validation for {language} not implemented, skipping")
            return True, None


class CodeExpert:
    """Code Expert with Starcoder and security scanning.

    Architecture:
    1. Query → Analyze intent and target language
    2. Generate code with Starcoder (or placeholder)
    3. Validate syntax with AST/TreeSitter
    4. Security scan with pattern matching (Semgrep in production)
    5. Return code + validation report
    """

    def __init__(
        self,
        model_name: str = "bigcode/starcoder",
        max_length: int = 512,
        temperature: float = 0.2,
    ):
        """Initialize Code Expert.

        Args:
            model_name: Starcoder model name
            max_length: Max generated tokens
            temperature: Sampling temperature
        """
        self.model_name = model_name
        self.max_length = max_length
        self.temperature = temperature

        # Initialize validators
        self.syntax_validator = SyntaxValidator()
        self.security_scanner = SecurityScanner()

        # Initialize model (placeholder - in production use transformers)
        logger.info(f"Code Expert initialized with model: {model_name}")
        logger.warning("Using placeholder code generation (load Starcoder in production)")

    async def process(self, request: dict[str, Any]) -> dict[str, Any]:
        """Process expert request (main entry point).

        Args:
            request: Expert request with capability and parameters

        Returns:
            Expert response with recommendation and metadata

        Example:
            >>> response = await expert.process({
            ...     "capability": "code_generation",
            ...     "query": "Write a function to validate email addresses",
            ...     "context": {"language": "python"}
            ... })
        """
        capability = request.get("capability")
        query = request.get("query", "")
        context = request.get("context", {})

        logger.info(f"Processing Code Expert request: capability={capability}")

        if capability == "code_generation":
            return await self._generate_code(query, context)
        elif capability == "code_review":
            return await self._review_code(query, context)
        elif capability == "refactoring":
            return await self._refactor_code(query, context)
        elif capability == "bug_fix":
            return await self._fix_bug(query, context)
        else:
            return {
                "recommendation": f"Unknown capability: {capability}",
                "confidence": 0.0,
                "reasoning": "Unknown capability",
                "metadata": {"error": "unknown_capability"},
                "requires_approval": True,
            }

    async def _generate_code(self, query: str, context: dict) -> dict[str, Any]:
        """Generate code from natural language query.

        Args:
            query: Natural language description
            context: Additional context (language, framework, etc.)

        Returns:
            Generated code with validation report
        """
        language = context.get("language", "python")

        # Generate code (placeholder - in production use Starcoder)
        generated_code = self._placeholder_generate(query, language)

        # Validate syntax
        is_valid, error = self.syntax_validator.validate(generated_code, language)

        if not is_valid:
            return {
                "recommendation": generated_code,
                "confidence": 0.3,
                "reasoning": f"Syntax validation failed: {error}",
                "metadata": {
                    "language": language,
                    "syntax_error": error,
                    "validation_status": "failed",
                },
                "requires_approval": True,
            }

        # Security scan
        vulnerabilities = self.security_scanner.scan(generated_code, language)

        if vulnerabilities:
            critical_vulns = [v for v in vulnerabilities if v["severity"] == "CRITICAL"]
            high_vulns = [v for v in vulnerabilities if v["severity"] == "HIGH"]

            confidence = 0.5 if critical_vulns else 0.7
            reasoning = (
                f"Security issues found: {len(critical_vulns)} CRITICAL, "
                f"{len(high_vulns)} HIGH. Manual review required."
            )

            return {
                "recommendation": generated_code,
                "confidence": confidence,
                "reasoning": reasoning,
                "metadata": {
                    "language": language,
                    "vulnerabilities": vulnerabilities,
                    "validation_status": "passed",
                    "security_status": "issues_found",
                },
                "requires_approval": True,  # Always require approval for code with vulnerabilities
            }

        # Code passed all checks
        return {
            "recommendation": generated_code,
            "confidence": 0.85,
            "reasoning": "Code passed syntax and security validation. Manual review recommended.",
            "metadata": {
                "language": language,
                "vulnerabilities": [],
                "validation_status": "passed",
                "security_status": "clean",
            },
            "requires_approval": True,  # ADR-011: AI recommends, human decides
        }

    async def _review_code(self, query: str, context: dict) -> dict[str, Any]:
        """Review code for security and quality issues.

        Args:
            query: Code to review
            context: Additional context

        Returns:
            Review report with findings
        """
        language = context.get("language", "python")

        # Validate syntax
        is_valid, error = self.syntax_validator.validate(query, language)

        # Security scan
        vulnerabilities = self.security_scanner.scan(query, language)

        findings = []
        if not is_valid:
            findings.append(f"Syntax error: {error}")

        if vulnerabilities:
            findings.extend([f"{v['severity']}: {v['message']}" for v in vulnerabilities])

        if not findings:
            review_summary = "No issues found. Code looks clean."
            confidence = 0.8
        else:
            review_summary = f"Found {len(findings)} issues:\n" + "\n".join(f"- {f}" for f in findings)
            confidence = 0.9  # High confidence in finding issues

        return {
            "recommendation": review_summary,
            "confidence": confidence,
            "reasoning": "Code reviewed with syntax and security analysis",
            "metadata": {
                "language": language,
                "findings": findings,
                "vulnerabilities": vulnerabilities,
            },
            "requires_approval": False,  # Review doesn't need approval (read-only)
        }

    async def _refactor_code(self, query: str, context: dict) -> dict[str, Any]:
        """Suggest code refactoring improvements.

        Args:
            query: Code to refactor
            context: Additional context

        Returns:
            Refactoring suggestions
        """
        language = context.get("language", "python")

        # Placeholder refactoring suggestions
        suggestions = [
            "Consider extracting complex logic into separate functions",
            "Add type hints for better code clarity",
            "Use list comprehensions for more Pythonic code",
            "Add docstrings to document function behavior",
        ]

        return {
            "recommendation": "Refactoring suggestions:\n"
            + "\n".join(f"{i + 1}. {s}" for i, s in enumerate(suggestions)),
            "confidence": 0.7,
            "reasoning": "Generated refactoring suggestions based on best practices",
            "metadata": {
                "language": language,
                "suggestions": suggestions,
            },
            "requires_approval": False,  # Suggestions don't need approval
        }

    async def _fix_bug(self, query: str, context: dict) -> dict[str, Any]:
        """Suggest bug fixes.

        Args:
            query: Bug description or code with bug
            context: Additional context

        Returns:
            Bug fix suggestions
        """
        language = context.get("language", "python")

        # Placeholder bug fix (in production, analyze code and suggest fix)
        fix_suggestion = "Analyze the code for common bugs:\n"
        fix_suggestion += "- Check for off-by-one errors in loops\n"
        fix_suggestion += "- Verify null/None checks\n"
        fix_suggestion += "- Ensure proper exception handling\n"
        fix_suggestion += "- Review variable scoping issues"

        return {
            "recommendation": fix_suggestion,
            "confidence": 0.6,
            "reasoning": "Generated bug fix checklist. Specific fix requires code analysis.",
            "metadata": {
                "language": language,
            },
            "requires_approval": True,  # Code changes require approval
        }

    def _placeholder_generate(self, query: str, language: str) -> str:
        """Placeholder code generation (replace with Starcoder in production).

        Args:
            query: Natural language description
            language: Target language

        Returns:
            Generated code
        """
        # Simple template-based generation for demo
        if "email" in query.lower() and "validate" in query.lower():
            return '''import re

def validate_email(email: str) -> bool:
    """Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        True if valid, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
'''
        elif "factorial" in query.lower():
            return '''def factorial(n: int) -> int:
    """Calculate factorial of n.

    Args:
        n: Non-negative integer

    Returns:
        Factorial of n

    Raises:
        ValueError: If n is negative
    """
    if n < 0:
        raise ValueError("Factorial not defined for negative numbers")
    if n == 0 or n == 1:
        return 1
    return n * factorial(n - 1)
'''
        else:
            return f'''# Generated code for: {query}
# TODO: Implement {query.lower()}

def placeholder_function():
    """Placeholder function - implement based on requirements."""
    pass
'''

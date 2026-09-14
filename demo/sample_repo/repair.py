"""Deterministic repair script used by the sandbox demo.

Executed by ``SandboxAgent`` with the sandbox root as the working directory.
It rewrites ``calc.py`` so ``total`` sums every price instead of skipping the
first one, then the agent re-runs the test suite to verify.
"""

from pathlib import Path

path = Path(__file__).with_name("calc.py")
text = path.read_text(encoding="utf-8")
fixed = text.replace("return sum(prices[1:])", "return sum(prices)")
assert fixed != text, "expected to find the buggy line in calc.py"
path.write_text(fixed, encoding="utf-8")
print(f"patched {path.name}: total() now sums all prices")
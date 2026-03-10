#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path


SNIPPET = """
<script>
(() => {
  const self = new URL(location.href);
  self.searchParams.set("__reload", Date.now().toString());
  let lastModified = null;
  async function check() {
    try {
      const res = await fetch(self.toString(), { cache: "no-store" });
      const lm = res.headers.get("last-modified") || null;
      if (lastModified === null) { lastModified = lm; return; }
      if (lm && lastModified && lm !== lastModified) location.reload();
    } catch (e) {}
  }
  setInterval(check, 800);
})();
</script>
</body>
""".lstrip()


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: inject_dev_reload.py <html-file>", file=sys.stderr)
        return 1

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"HTML file not found: {path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    if "__reload" in text:
        return 0
    if "</body>" not in text:
        print(f"Missing </body> in {path}", file=sys.stderr)
        return 1

    path.write_text(text.replace("</body>", SNIPPET, 1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

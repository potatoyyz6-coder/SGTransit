"""Check inline local Markdown links against the publishable file inventory."""
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from tools.release_check import ROOT, git_files


def check(root=ROOT):
    files = set(git_files(root))
    issues, checked = [], 0
    for relative in sorted(files):
        if not relative.endswith('.md'):
            continue
        fenced = False
        for line_no, line in enumerate((root/relative).read_text(encoding='utf-8').splitlines(), 1):
            if line.lstrip().startswith(('```', '~~~')):
                fenced = not fenced
            if fenced:
                continue
            for match in re.finditer(r'!?\[[^\]]*\]\((?:<([^>]+)>|([^\s)]+))[^)]*\)', line):
                target = match[1] or match[2]
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                checked += 1
                resolved = ((root/relative).parent/unquote(parsed.path)).resolve()
                try:
                    path = resolved.relative_to(root.resolve()).as_posix()
                except ValueError:
                    path = ''
                if path not in files:
                    issues.append(dict(file=relative, line=line_no, target=target,
                                       reason='not in publishable file inventory'))
    return dict(checked=checked, issues=issues,
                scope='Inline local file links outside fenced code; no external requests or anchor validation')


def main():
    result = check()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result['issues']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

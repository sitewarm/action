"""Extracts the `run:` script of a named step from action.yml, without a YAML parser (standard library only)."""
import re
import sys


def step_script(action_yml: str, step_name: str) -> str:
    with open(action_yml, encoding="utf-8") as f:
        lines = f.read().split("\n")
    start = next((i for i, l in enumerate(lines) if re.fullmatch(r"    - name: " + re.escape(step_name), l)), None)
    if start is None:
        raise KeyError(step_name)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("    - ")), len(lines))
    run = next((i for i in range(start, end) if lines[i] == "      run: |"), None)
    if run is None:
        raise KeyError("no run: | in " + step_name)
    body = []
    for l in lines[run + 1:end]:
        if l.strip() == "":
            body.append("")
        elif l.startswith("        "):
            body.append(l[8:])
        else:
            break
    return "\n".join(body) + "\n"


if __name__ == "__main__":
    sys.stdout.write(step_script(sys.argv[1], sys.argv[2]))

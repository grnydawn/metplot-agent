"""QA test for issue #29 — installation documentation.

One observable assertion per acceptance criterion. Non-visual (docs-only),
so no screenshots. Run: python -m pytest tests/docs/test_installation_doc.py -q
"""
import os
import re
import subprocess
import tomllib

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOC = os.path.join(REPO, "docs", "installation.md")
HOSTS = [
    "Claude Code", "Cursor", "GitHub Copilot", "Gemini CLI",
    "Codex", "Antigravity", "Claude Desktop",
]


def _doc():
    with open(DOC) as fh:
        return fh.read()


def _sections(text):
    sections, cur, buf = {}, None, []
    for line in text.splitlines():
        m = re.match(r"### (.+)", line)
        if m:
            if cur:
                sections[cur] = "\n".join(buf)
            cur, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    if cur:
        sections[cur] = "\n".join(buf)
    return sections


def _anchors(path):
    out = set()
    for line in open(path).read().splitlines():
        m = re.match(r"#{1,6}\s+(.*)", line)
        if m:
            a = re.sub(r"[^\w\s-]", "", re.sub(r"`", "", m.group(1).strip().lower()))
            out.add(re.sub(r"\s+", "-", a))
    return out


def test_ac1_doc_exists_linked_and_covers_7_targets():
    assert os.path.exists(DOC), "docs/installation.md must exist"
    readme = open(os.path.join(REPO, "README.md")).read()
    assert "docs/installation.md" in readme, "README must link installation.md"
    text = _doc()
    for host in HOSTS:
        assert host.lower() in text.lower(), f"target not covered: {host}"


def test_ac2_each_host_has_build_install_enable_verify():
    sections = _sections(_doc())
    for host in HOSTS:
        matched = [k for k in sections if host.lower() in k.lower()]
        assert matched, f"missing host section: {host}"
        body = sections[matched[0]]
        assert "python -m tools.build" in body, f"{host}: no build command"
        assert "Install" in body, f"{host}: no install/point step"
        assert "Enable skills" in body, f"{host}: no enable step"
        assert "Verify it works" in body, f"{host}: no verify step"


def test_ac3_mcp_extra_documented_matches_pyproject():
    text = _doc()
    assert "`mcp`" in text and "metplot:setup" in text
    with open(os.path.join(REPO, "pyproject.toml"), "rb") as fh:
        deps = tomllib.load(fh)["project"]["optional-dependencies"]["mcp"]
    pkgs = {d.split(">")[0].split("=")[0].split("[")[0] for d in deps}
    for pkg in ["mcp", "xarray", "netcdf4", "numpy", "matplotlib", "cartopy"]:
        assert pkg in pkgs, f"mcp extra missing {pkg} in pyproject"
        assert pkg in text, f"{pkg} not documented in installation.md"


def test_ac4_prerequisites_python_and_cartopy_syslibs():
    text = _doc()
    assert ("Python ≥ 3.10" in text) or ("Python ≥3.10" in text)
    assert "GEOS" in text and "PROJ" in text, "cartopy system libs not stated"


def test_ac5_per_tool_verify_inspect_then_plot():
    sections = _sections(_doc())
    for host in HOSTS:
        body = sections[[k for k in sections if host.lower() in k.lower()][0]]
        assert "inspect" in body.lower(), f"{host}: verify lacks inspect"
        assert ("plot" in body.lower()) or ("render" in body.lower()), \
            f"{host}: verify lacks plot/render"


def test_ac6_make_lint_clean():
    res = subprocess.run(["make", "lint"], cwd=REPO, capture_output=True, text=True)
    assert res.returncode == 0, f"make lint failed:\n{res.stdout}\n{res.stderr}"


def test_ac6_all_relative_links_and_anchors_resolve():
    text = _doc()
    docdir = os.path.dirname(DOC)
    fails = []
    for ln in re.findall(r"\]\(([^)]+)\)", text):
        if ln.startswith(("http://", "https://")):
            continue
        path_part, _, frag = ln.partition("#")
        target = DOC if path_part == "" else os.path.normpath(os.path.join(docdir, path_part))
        if not os.path.exists(target):
            fails.append(f"missing file: {ln}")
            continue
        if frag and frag.lower() not in _anchors(target):
            fails.append(f"missing anchor: {ln}")
    assert not fails, "unresolved links: " + "; ".join(fails)

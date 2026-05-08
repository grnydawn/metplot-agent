from pathlib import Path


from tools.install_deps import Args, build_plan


def _args(**kw) -> Args:
    return Args(no_cartopy=False, no_scipy=False, quiet=False,
                 dry_run=False, force=False,
                 mcp_servers_dir=Path("/m"), **kw)


def test_default_plan_has_4_steps():
    plan = build_plan(_args())
    assert len(plan) == 4


def test_default_plan_step_order():
    plan = build_plan(_args())
    titles = [s.title for s in plan]
    assert titles == ["netcdf-reader", "plot-renderer",
                       "cartopy", "scipy"]


def test_required_flag():
    plan = build_plan(_args())
    assert plan[0].required is True   # netcdf-reader
    assert plan[1].required is True   # plot-renderer
    assert plan[2].required is False  # cartopy
    assert plan[3].required is False  # scipy


def test_no_cartopy_skips_cartopy():
    plan = build_plan(Args(no_cartopy=True, no_scipy=False, quiet=False,
                            dry_run=False, force=False,
                            mcp_servers_dir=Path("/m")))
    titles = [s.title for s in plan]
    assert "cartopy" not in titles


def test_no_scipy_skips_scipy():
    plan = build_plan(Args(no_cartopy=False, no_scipy=True, quiet=False,
                            dry_run=False, force=False,
                            mcp_servers_dir=Path("/m")))
    titles = [s.title for s in plan]
    assert "scipy" not in titles


def test_mcp_step_uses_mcp_servers_dir():
    plan = build_plan(Args(no_cartopy=True, no_scipy=True, quiet=False,
                            dry_run=False, force=False,
                            mcp_servers_dir=Path("/m")))
    # Required steps point at the package dirs
    assert plan[0].pkg_path == Path("/m/netcdf_reader")
    assert plan[1].pkg_path == Path("/m/plot_renderer")

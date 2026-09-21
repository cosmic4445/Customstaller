import pytest

from customstaller.config import CustomstallerError, Project
from customstaller.tabs import (
    add_premade, create_tab, load_tabs, move_tab, remove_tab, slugify, class_name,
)


def test_slugify():
    assert slugify("My Cool Tab!") == "my_cool_tab"
    assert slugify("  ") == ""
    assert slugify("2fast") == "tab_2fast"
    assert slugify("class") == "class_tab"
    assert class_name("my_cool_tab") == "MyCoolTab"


def test_init_creates_four_premade_tabs(project_dir):
    p = Project.load(project_dir)
    assert p.order == ["home", "license", "console", "finish"]
    for slug in p.order:
        assert (project_dir / "tabs" / f"{slug}.py").is_file()


def test_new_tab_goes_before_console_and_loads(project_dir):
    p = Project.load(project_dir)
    slug, path = create_tab(p, "Pick Components")
    assert p.order == ["home", "license", "pick_components", "console", "finish"]
    assert path.read_text().count("class PickComponents(Tab)") == 1
    tabs = dict(load_tabs(Project.load(project_dir)))
    assert tabs["pick_components"].title == "Pick Components"


def test_titles_with_quotes_dont_break_the_generated_file(project_dir):
    p = Project.load(project_dir)
    create_tab(p, 'It\'s "quoted" \\ tab')
    tabs = dict(load_tabs(Project.load(project_dir)))
    assert tabs["it_s_quoted_tab"].title == 'It\'s "quoted" \\ tab'


def test_duplicate_and_empty_names_are_rejected(project_dir):
    p = Project.load(project_dir)
    create_tab(p, "Extras")
    with pytest.raises(CustomstallerError):
        create_tab(p, "extras")
    with pytest.raises(CustomstallerError):
        create_tab(p, "!!!")
    with pytest.raises(CustomstallerError):
        create_tab(p, "Home")


def test_remove_keeps_file_and_readd_keeps_edits(project_dir):
    p = Project.load(project_dir)
    remove_tab(p, "license")
    assert "license" not in p.order
    lic = project_dir / "tabs" / "license.py"
    lic.write_text(lic.read_text() + "\n# my edit\n")
    add_premade(p, "license")
    assert p.order == ["home", "license", "console", "finish"]
    assert "# my edit" in lic.read_text()


def test_premade_order_is_canonical(project_dir):
    p = Project.load(project_dir)
    for s in ("finish", "console", "license", "home"):
        remove_tab(p, s)
    for s in ("finish", "home", "console", "license"):
        add_premade(p, s)
    assert p.order == ["home", "license", "console", "finish"]


def test_move(project_dir):
    p = Project.load(project_dir)
    move_tab(p, "finish", -1)
    assert p.order == ["home", "license", "finish", "console"]
    move_tab(p, "home", -1)
    assert p.order[0] == "home"


def test_broken_tab_file_gives_a_clear_error(project_dir):
    (project_dir / "tabs" / "home.py").write_text("raise ValueError('boom')\n")
    with pytest.raises(CustomstallerError, match="home.py has an error"):
        load_tabs(Project.load(project_dir))
    (project_dir / "tabs" / "home.py").write_text("x = 1\n")
    with pytest.raises(CustomstallerError, match="doesn't define a Tab"):
        load_tabs(Project.load(project_dir))


def test_new_tab_placement_without_console(project_dir):
    p = Project.load(project_dir)
    remove_tab(p, "console")
    create_tab(p, "Extras")
    assert p.order == ["home", "license", "extras", "finish"]
    remove_tab(p, "finish")
    create_tab(p, "More")
    assert p.order[-1] == "more"

"""临时:SVG 星模板跑校准 GT(用完即删)。"""
import pytest
import cv2

import sr_od.application.currency_war.cw_identity_obs as obs
from sr_od.application.currency_war.cw_identity_obs import read_star
from test.conftest import SrTestContext


@pytest.fixture(autouse=True)
def _svg_template() -> None:
    """全部用例换 SVG 模板(模块级缓存直写,monkeypatch 管不到全局变量,手动换回)。"""
    old = obs._STAR_TMPL_CACHE
    obs._STAR_TMPL_CACHE = cv2.imread(
        "assets/template/cw_star/star_official_svg_mask.png", cv2.IMREAD_GRAYSCALE)
    yield
    obs._STAR_TMPL_CACHE = old


def test_svg_star_2star_positions(test_context: SrTestContext) -> None:
    """SVG 模板:deployed_2star 三难例(衣服淹没/thresh/紧贴)+对照。"""
    if not test_context.has_screen("货币战争-备战", "deployed_2star"):
        pytest.skip("fixture 未采")
    screen = test_context.load_screen("货币战争-备战", "deployed_2star")
    assert read_star(screen[329:467, 969:1097]) == 2, "前排-3 应为 2 星(衣服淹没)"
    assert read_star(screen[600:739, 823:953]) == 2, "后排-3 应为 2 星"
    assert read_star(screen[845:979, 757:869]) == 2, "备战栏-4 应为 2 星(紧贴)"
    assert read_star(screen[845:979, 382:495]) == 1, "备战栏-1 应为 1 星(对照)"


def test_svg_star_full_fixture(test_context: SrTestContext) -> None:
    """SVG 模板:deployed_2star_full 三行广覆盖(1★+2★)。"""
    if not test_context.has_screen("货币战争-备战", "deployed_2star_full"):
        pytest.skip("fixture 未采")
    screen = test_context.load_screen("货币战争-备战", "deployed_2star_full")
    assert read_star(screen[329:467, 969:1097]) == 1, "前排-3 花火 1★"
    assert read_star(screen[329:467, 1109:1241]) == 2, "前排-4 万敌 2★"
    assert read_star(screen[600:739, 534:675]) == 1, "后排-1 三月七 1★"
    assert read_star(screen[600:739, 823:953]) == 2, "后排-3 椒丘 2★"
    assert read_star(screen[845:979, 382:495]) == 1, "备战-1 艾丝妲 1★"
    assert read_star(screen[845:979, 757:869]) == 2, "备战-4 飞霄 2★"
    assert read_star(screen[845:979, 1256:1368]) == 1, "备战-8 万敌 1★(同名异星)"


def test_svg_star_edge_slots(test_context: SrTestContext) -> None:
    """SVG 模板:各排边槽 2★。"""
    if test_context.has_screen("货币战争-备战", "deployed_2star_bench1"):
        s = test_context.load_screen("货币战争-备战", "deployed_2star_bench1")
        assert read_star(s[845:979, 382:495]) == 2, "备战-1 飞霄 2★(左)"
    if test_context.has_screen("货币战争-备战", "deployed_2star_bench9"):
        s = test_context.load_screen("货币战争-备战", "deployed_2star_bench9")
        assert read_star(s[844:980, 1379:1493]) == 2, "备战-9 飞霄 2★(右,circ边界)"
        assert read_star(s[600:739, 1106:1241]) == 2, "后排-5 万敌 2★"
    if test_context.has_screen("货币战争-备战", "deployed_2star_back6"):
        s = test_context.load_screen("货币战争-备战", "deployed_2star_back6")
        assert read_star(s[600:739, 1245:1386]) == 2, "后排-6 椒丘 2★(右,最紧贴)"

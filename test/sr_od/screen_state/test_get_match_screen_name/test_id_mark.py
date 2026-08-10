"""id_mark 准确性 + 碰撞测试(重构自旧 test_get_match_screen_name)。

对 ``screens/`` 中央归档库的每张 fixture,验证每个**有 id_mark 的画面**:

1. **真阳性**:该画面 id_mark 在自家 fixture 全命中(``is_target_screen=True``);
2. **无碰撞**:别家 id_mark 画面**不会**在这张 fixture 全命中(否则两屏都 is_target_screen →
   bot 可能误识别)。

新增 / 改动画面后跑这个,能抓"id_mark 撞车" —— A 的 id_mark 文字 / 模板在 B 画面也全命中
→ A 与 B 撞车。修复:给撞车的屏加更独有的 id_mark(更长关键词 / 独有锚 / 第 2 个 id_mark)。

旧版只硬编码 ~16 屏验真阳性(``get_match_screen_name`` 返回正确名),抓不到碰撞;新版自动
发现全部 fixture + 加碰撞检查。

需完整 SR 数据栈(screen_info + 模板 + OCR),CI clean checkout 无 → 本地跑。
"""
import os
from pathlib import Path

import pytest

from one_dragon.base.screen import screen_utils
from test.conftest import SrTestContext

pytestmark = pytest.mark.skipif(
    bool(os.environ.get('CI')),
    reason='需完整 SR 数据栈(screen_info / 模板 / OCR),CI clean checkout 无;本地有数据则跑',
)


def _screens_dir() -> Path:
    """从本测试文件向上找中央归档库(含 ``<screen>/<state>.webp`` 的 ``screens/``)。

    注意:``sr-od-test/test/sr_od/screens/`` 是测试包目录(放 test_shared_screen_fixtures),
    也叫 screens 但没 webp —— 必须用 ``any(glob('*/*.webp'))`` 排除,找到真归档库
    ``sr-od-test/screens/``。
    """
    p = Path(__file__).resolve().parent
    for _ in range(6):
        cand = p / 'screens'
        if cand.is_dir() and any(cand.glob('*/*.webp')):
            return cand
        p = p.parent
    raise RuntimeError('未找到 screens/ 归档库(含 <screen>/<state>.webp)')


def _discover_fixtures() -> list[tuple[str, str]]:
    """自动发现 ``screens/<screen>/<state>.webp`` → (screen, state) 列表。

    screen = 目录名(= screen_info.screen_name);state = 文件名(不带后缀)。
    新建档 fixture 自动进测试,无需维护清单。
    """
    screens_dir = _screens_dir()
    return [
        (p.parent.name, p.stem)
        for p in sorted(screens_dir.glob('*/*.webp'))
    ]


_FIXTURES: list[tuple[str, str]] = _discover_fixtures()


@pytest.mark.parametrize(
    'screen,state',
    _FIXTURES,
    ids=[f'{s}/{st}' for s, st in _FIXTURES],
)
def test_id_mark(screen: str, state: str, test_context: SrTestContext) -> None:
    """每张 fixture:自家 id_mark 命中(真阳性)+ 别家 id_mark 不命中(无碰撞)。"""
    target = test_context.screen_loader.get_screen(screen)
    if target is None:
        pytest.skip(f'无 screen_info:{screen}(仅归档截图,未建 screen_info entry)')
    if not any(a.id_mark for a in target.area_list):
        pytest.skip(f'{screen} 无 id_mark(走模糊 top_n 匹配,不测 id_mark 碰撞)')

    img = test_context.load_screen(screen, state)

    # 1. 真阳性:自家 id_mark 在自家 fixture 全命中
    assert screen_utils.is_target_screen(test_context, img, screen_info=target), (
        f'{screen}/{state}:自家 id_mark 未全命中(真阳性失败 —— id_mark 过严 / '
        'fixture 非该屏典型态?自行核实)'
    )

    # 2. 无碰撞:别家 id_mark 画面不该在这张 fixture 全命中
    collisions = [
        info.screen_name
        for info in test_context.screen_loader.screen_info_list
        if info.screen_name != screen
        and any(a.id_mark for a in info.area_list)
        and screen_utils.is_target_screen(test_context, img, screen_info=info)
    ]
    assert not collisions, (
        f'{screen}/{state}:被别家画面 {collisions} 的 id_mark 全命中(撞车)'
        ' → 给本屏或撞车屏加更独有的 id_mark(更长关键词 / 独有锚 / 第 2 个 id_mark)'
    )

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

# 已知错档 fixture(归档目录 ≠ 画面实属屏):strict xfail 记录该缺口,修复后转 XPASS 会响,
# 提示移除本标记。2026-08-15 无名勋礼两张错档已迁移根治(webp 迁 screens/无名勋礼/ +
# 独立屏建档,详见 docs/game/screens/无名勋礼.md),现为空集;机制保留,供未来错档登记。
_KNOWN_MISFILED: set[tuple[str, str]] = set()

# 已知合法双命中(fixture 帧上父屏 id_mark 全可见):小型侧边 overlay 不遮父屏
# 任何 id_mark 元素,父屏(货币战争-备战)对这些帧 is_precise 属画面事实,不算撞车。
# (真正的撞车 = 双方都该 is_precise 但语义互斥;这三帧是「父屏 + 小浮窗」叠加态,
# 上层排除由 cw_obs_core.UPPER_SCREENS 两段式门负责,不经 screen 匹配竞争。)
_ALLOWED_DUAL_HIT: dict[tuple[str, str], set[str]] = {
    ('货币战争-备战-装备详情浮窗', 'equip_detail_roller'): {'货币战争-备战'},
    ('货币战争-备战-装备详情浮窗', 'equip_detail_synth_target'): {'货币战争-备战'},
    ('货币战争-备战-角色信息提示', 'char_detail'): {'货币战争-备战'},
}


@pytest.mark.parametrize(
    'screen,state',
    [
        pytest.param(s, st, marks=pytest.mark.xfail(
            reason='fixture 错档:实为无名勋礼面板屏(菜单锚不可见),待迁移+建模',
            strict=True,
        )) if (s, st) in _KNOWN_MISFILED else (s, st)
        for s, st in _FIXTURES
    ],
    ids=[f'{s}/{st}' for s, st in _FIXTURES],
)
def test_id_mark(screen: str, state: str, test_context: SrTestContext) -> None:
    """每张 fixture:自家 id_mark 命中(真阳性)+ 别家 id_mark 不命中(无碰撞)。"""
    try:
        target = test_context.screen_loader.get_screen(screen)
    except Exception:
        # get_screen 对未建模画面抛「未找到画面」而非返 None(孤儿 fixture);
        # 这些屏已知未建模(如差分宇宙,见 docs/game/screens/README.md)→ skip
        pytest.skip(f'无 screen_info:{screen}(仅归档截图,未建 screen_info entry)')
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

    # 2. 无碰撞:别家 id_mark 画面不该在这张 fixture 全命中。
    #    能区分靠各屏 id_mark 互不重叠:备战 id_mark 含「前台区域」(overlay 会盖住),
    #    所以 partner/megastar/wish 帧里备战凑不齐 → 备战不是 is_precise → 不撞车;
    #    overlay 自己的 id_mark(购买经验 + 标题)更独有,只在 overlay 帧全命中。
    collisions = []
    _exempt = _ALLOWED_DUAL_HIT.get((screen, state), set())
    for info in test_context.screen_loader.screen_info_list:
        if info.screen_name == screen or info.screen_name in _exempt \
                or not any(a.id_mark for a in info.area_list):
            continue
        if screen_utils.is_target_screen(test_context, img, screen_info=info):
            collisions.append(info.screen_name)
    assert not collisions, (
        f'{screen}/{state}:被别家画面 {collisions} 的 id_mark 全命中(撞车)'
        ' → 给本屏或撞车屏加更独有的 id_mark(更长关键词 / 独有锚 / 第 2 个 id_mark)'
    )

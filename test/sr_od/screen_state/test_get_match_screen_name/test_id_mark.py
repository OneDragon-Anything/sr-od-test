"""id_mark 准确性 + 碰撞测试(重构自旧 test_get_match_screen_name)。

对 ``screens/`` 中央归档库的每张 fixture,验证每个**有 id_mark 的画面**:

1. **真阳性**:该画面 id_mark 在自家 fixture 全命中(``is_target_screen=True``);
2. **无碰撞**:别家 id_mark 画面**不会**在这张 fixture 全命中(否则两屏都 is_target_screen →
   bot 可能误识别)。

新增 / 改动画面后跑这个,能抓"id_mark 撞车" —— A 的 id_mark 文字 / 模板在 B 画面也全命中
→ A 与 B 撞车。修复:给撞车的屏加更独有的 id_mark(更长关键词 / 独有识别标志 / 第 2 个 id_mark)。

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
# 独立屏建档,详见 docs/game/screens/无名勋礼.md)。机制保留,供未来错档登记。
# 2026-08-29:通用「获得物品」弹窗帧错档两例(邮箱/委托领取后截到,标题被弹窗遮罩盖住,
# 帧实属通用获得物品弹窗而非宿主画面)。邮件一张已迁 screens/获得物品/邮件领取后.webp;
# 委托一张因被 test_assignments_app 作 mock 输入引用暂留原位,待获得物品屏建档后统一迁移。
_KNOWN_MISFILED: set[tuple[str, str]] = {
    ('委托', '委托领取弹窗'),
}

# 已知过时 fixture(游戏 UI 改版后元素消失,帧非当前版本典型态):strict xfail,
# 实机补拍后转 XPASS 会响,提示重拍并移除本标记。
# 末日幻影-编队两张旧帧截于「星启模式」上线前,缺 04-星启模式标签(新帧实测有)。
_STALE_PENDING_RECAPTURE: set[tuple[str, str]] = {
    ('末日幻影-编队', '默认'),
    ('末日幻影-编队', '编队屏-有队伍'),
}

# 宿主画面 + 遮蔽态帧:弹窗/整页子态把宿主 id_mark 盖住或替换,宿主对这些帧
# is_precise 不成立属画面事实;弹窗与子态 areas 按建模决定挂宿主 yml(如
# 「标题-材料补全弹窗」被 4 个升级 op 作宿主 area 消费),帧留宿主目录。
# 真屏判定由消费 op 的专属 area 锚负责,不经 screen 匹配竞争。碰撞检查保留。
_HOST_COVERED_STATES: set[tuple[str, str]] = {
    # 材料补全弹窗(白底弹窗压暗行迹页,标题-行迹不可读)
    ('角色-行迹', '材料补全弹窗-一行材料'),
    ('角色-行迹', '材料补全弹窗-两行材料'),
    # 周本编队态 = 整页子态(左上角是「队伍7」,历战余响标题不在场;
    # 编队 areas 挂宿主 yml,消费 op 以队伍标题/开始挑战锚判定)
    ('挑战副本-历战余响', '编队态'),
    # 次数耗尽确认弹窗(通用「提示」弹窗族,宿主标题被模糊蒙层盖住)
    ('挑战副本-历战余响', '次数耗尽弹窗'),
}

# 已知合法双命中(fixture 帧上父屏 id_mark 全可见):小型侧边 overlay 不遮父屏
# 任何 id_mark 元素,父屏(货币战争-备战)对这些帧 is_precise 属画面事实,不算撞车。
# (真正的撞车 = 双方都该 is_precise 但语义互斥;这三帧是「父屏 + 小浮窗」叠加态,
# 上层排除由 cw_obs_core.UPPER_SCREENS 两段式门负责,不经 screen 匹配竞争。)
_ALLOWED_DUAL_HIT: dict[tuple[str, str], set[str]] = {
    ('货币战争-备战-装备详情浮窗', 'equip_detail_roller'): {'货币战争-备战'},
    ('货币战争-备战-装备详情浮窗', 'equip_detail_synth_target'): {'货币战争-备战'},
    ('货币战争-备战-角色信息提示', 'char_detail'): {'货币战争-备战'},
    # 同一 overlay 的第二实例(狸猫台词卡帧,原误归备战目录已迁入):浮窗
    # 遮住后台右段但父屏 id_mark(前台区域)仍全可见,叠加态画面事实。
    ('货币战争-备战-角色信息提示', '后排9槽-cap7lv4-浮窗遮挡'): {'货币战争-备战'},
    # 菜单的省略号子菜单是小型 overlay,不遮菜单 id_mark(开拓等级) → 菜单对该帧
    # is_precise 属画面事实;上层排除由导航顺序/运行时上下文负责。
    ('菜单-更多', '展开'): {'菜单'},
    # 我来当策划模态只盖上半屏,商店识别标志(购买经验/收起)在下层透出 → 开商店对该帧
    # is_precise 属画面事实;运行时消歧由 cw_loop 0a2 分支优先级负责
    # (模态分支先于备战双识别标志分支接管,W944 实证帧归档)。
    ('货币战争-银狼升星', '骇入二选一'): {'货币战争-备战-开商店'},
    # 遭遇锁定暗色态 = 备战子态(整屏暗化蒙层,备战识别标志购买经验/出战在下层可读)
    # → 备战对该帧 is_precise 属画面事实;运行时消歧由遭遇 op 专属分发与
    # cw_loop 锁定态分支负责(策略锁定近似撞车已随其识别标志 lcs 0.75 完结)。
    ('货币战争-备战-遭遇锁定', '锁定态'): {'货币战争-备战'},
    # 背包筛选面板是右侧抽屉 overlay,不遮父屏(背包-遗器)任何 id_mark
    # (背包/遗器标题在左上、分解按钮在面板外下方,均全可见)→ 父屏对
    # 面板帧 is_precise 属画面事实;运行时消歧:消费 op(SelectBagRelicOp)
    # 以面板自己的「筛选方案」区域命中作锚,不经 screen 匹配竞争。
    ('背包-遗器-筛选', '面板打开'): {'背包-遗器'},
    # 通用「提示+确认」弹窗族与战斗-退出确认弹窗同构(「提示」标题与确认/取消按钮
    # 同位同文,战斗退出弹窗按位置锚定不依赖正文文案)→ 这三张帧上双方 id_mark
    # 全命中属画面事实。运行时消歧:战斗-退出确认弹窗只被 EnterGame 登录恢复退出链
    # 消费,其识别位置在登录/模拟宇宙/大世界判断之后;跃迁/货币战争弹窗在登录恢复
    # 路径不可达。跃迁-梦华兑换/星琼不足 另有与跃迁-兑换确认的存量撞车(lcs 0.5
    # 短词子序列),不在本豁免范围(豁免会掩盖既有红)。
    ('货币战争-未达上限警告', 'default'): {'战斗-退出确认弹窗'},
    ('跃迁-兑换确认', '专票不足'): {'战斗-退出确认弹窗'},
    ('跃迁-梦华兑换', '星琼不足'): {'战斗-退出确认弹窗'},
    # 历战余响次数耗尽弹窗 = 同上通用「提示」弹窗族(提示标题+取消/确认同位同文),
    # 宿主标题被模糊蒙层盖住(登记于 _HOST_COVERED_STATES,只跑碰撞半边)。
    # 运行时消歧:该弹窗只被周本挑战 op 在历战余响流程内消费,按上下文点名确认。
    ('挑战副本-历战余响', '次数耗尽弹窗'): {'战斗-退出确认弹窗'},
    # 「筛选规则」弹窗在背包侧与遗器替换侧是同一游戏组件、像素级同构
    # (标题同文同位,filter_relic_replace.py 注释已明示),两屏 id_mark 必然
    # 双命中,属画面事实无法靠 id_mark 区分。运行时消歧:两屏各被自己的
    # 消费 op 按流程上下文点名(背包分解链 / 遗器替换链),不经 screen 匹配竞争。
    ('背包-遗器-筛选规则', '隧洞列表'): {'遗器-替换-筛选规则'},
    ('背包-遗器-筛选规则', '已勾选'): {'遗器-替换-筛选规则'},
    ('遗器-替换-筛选规则', '筛选规则弹窗'): {'背包-遗器-筛选规则'},
    ('遗器-替换-筛选规则', '筛选规则弹窗已勾选'): {'背包-遗器-筛选规则'},
    # 遗器替换页右侧筛选抽屉与背包遗器筛选抽屉同为同一抽屉组件:抽屉屏
    # (遗器-替换-筛选/背包-遗器-筛选)的 id_mark 与宿主标题在抽屉帧上全部
    # 同场,三屏同帧全命中属画面事实。运行时消歧:替换链消费 op 以宿主+
    # 抽屉 area 组合锚定,背包链以「筛选方案」区域命中作锚(见上)。
    ('遗器-替换', '筛选面板开'): {'背包-遗器-筛选', '遗器-替换-筛选'},
    ('遗器-替换', '筛选面板已清'): {'背包-遗器-筛选', '遗器-替换-筛选'},
    ('遗器-替换', '筛选面板带chip筛选后列表'): {'背包-遗器-筛选', '遗器-替换-筛选'},
}


@pytest.mark.parametrize(
    'screen,state',
    [
        pytest.param(s, st, marks=pytest.mark.xfail(
            reason='fixture 错档:实为无名勋礼面板屏(菜单识别标志不可见),待迁移+建模',
            strict=True,
        )) if (s, st) in _KNOWN_MISFILED else pytest.param(s, st, marks=pytest.mark.xfail(
            reason='fixture 过时:游戏 UI 改版后元素缺失,待实机补拍',
            strict=True,
        )) if (s, st) in _STALE_PENDING_RECAPTURE else (s, st)
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

    # 1. 真阳性:自家 id_mark 在自家 fixture 全命中。
    #    遮蔽态帧(宿主+弹窗/整页子态)跳过本半边:宿主 id_mark 不在场属画面
    #    事实(见 _HOST_COVERED_STATES),碰撞半边照跑。
    if (screen, state) not in _HOST_COVERED_STATES:
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
        ' → 给本屏或撞车屏加更独有的 id_mark(更长关键词 / 独有识别标志 / 第 2 个 id_mark)'
    )

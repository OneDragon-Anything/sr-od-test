"""UseTrailblazePower 开拓力「等待战斗结果」超时语义锁。

背景(2026-08-27 实锤断面,run 48):新版本「贪饕侵蚀」机制把拟造花萼常规战斗拖到
20分49秒,旧 600s 节点上限到点直接判失败 → op 放弃但游戏内战斗继续自打(孤 battle),
战场残留导致下一个 app 入口误导航。治本修法:
- 等待本身信号驱动不变(每轮识别结算画面),上限放大为防真死锁的兜底窗;
- 超时不放弃:沿 fail 边(status=执行超时)进「战斗超时收尾」节点,继续观察至结算
  画面再点退出关卡,不把孤 battle 留给下一个 app。

锁的内容(超时判据语义,不锁与机制无关的实现细节):
1. 主等待窗上限 ≥ 实测最坏战斗时长 + 余量(修法回归守卫:谁改回 600s 就红)。
2. 「执行超时」fail 边存在且指向「战斗超时收尾」节点(收尾接线不被静默拆掉)。
3. 收尾节点自身有有限超时(死锁兜底,防二次观察窗变成无限等待)。
4. 行为:收尾节点见挑战成功 → 补记次数 + 回调 + 尝试退出关卡;见战斗失败 → 不补记
   但尝试退出;仍在战斗 → round_wait 继续观察,不点击。
"""

import pytest
from test.conftest import SrTestContext

from one_dragon.base.operation.operation import Operation
from sr_od.challenge_mission.use_trailblaze_power import (
    WAIT_RESULT_TIMEOUT_SECONDS,
    UseTrailblazePower,
)
from sr_od.interastral_peace_guide.guide_def import (
    GuideCategory,
    GuideMission,
    GuideTab,
)

# run 48 实测最坏战斗时长:20分49秒 = 1249 秒(断面证据,超时判据的下界依据)
OBSERVED_WORST_BATTLE_SECONDS: int = 1249


def _make_mission() -> GuideMission:
    """最小拟造花萼（赤）关卡对象(op 构造只用到分类/名字/体力)。"""
    cate = GuideCategory(GuideTab('生存索引'), '拟造花萼（赤）')
    return GuideMission(cate, '虚无之蕾', power=10)


class TestWaitBattleResultTimeout:
    """开拓力刷取战斗等待超时治本的语义锁。"""

    def _make_op(self, test_context: SrTestContext,
                 on_battle_success=None,
                 init_network: bool = False) -> UseTrailblazePower:
        op = UseTrailblazePower(test_context, _make_mission(),
                                team_num=1, plan_times=1,
                                on_battle_success=on_battle_success)
        if init_network:
            # 节点/边注册在 _init_network 才落到 _node_map / _node_edges_map(惰性)
            op._init_network()
        return op

    def test_main_wait_window_covers_observed_worst_case(
            self, test_context: SrTestContext) -> None:
        """主等待窗上限必须覆盖实测最坏战斗时长(run 48 的 20分49秒)+ 余量。"""
        op = self._make_op(test_context, init_network=True)
        node = op._node_map['等待战斗结果']
        assert node.timeout_seconds == WAIT_RESULT_TIMEOUT_SECONDS
        assert node.timeout_seconds > OBSERVED_WORST_BATTLE_SECONDS + 60, (
            f'主等待窗({node.timeout_seconds}s)须 > 实测最坏'
            f'({OBSERVED_WORST_BATTLE_SECONDS}s)+余量,否则贪饕侵蚀长战斗会再次被误杀'
        )

    def test_timeout_routes_to_cleanup_node(self, test_context: SrTestContext) -> None:
        """等待战斗结果的「执行超时」fail 必须路由进「战斗超时收尾」,不允许直接放弃留孤 battle。"""
        op = self._make_op(test_context, init_network=True)
        edges = op._node_edges_map.get('等待战斗结果', [])
        timeout_edges = [
            e for e in edges
            if not e.success and e.status == Operation.STATUS_TIMEOUT
        ]
        assert len(timeout_edges) == 1, (
            f'应有且仅有一条 status={Operation.STATUS_TIMEOUT} 的 fail 边,实际 {edges}'
        )
        assert timeout_edges[0].node_to.cn == '战斗超时收尾'

    def test_cleanup_node_has_deadlock_backstop(self, test_context: SrTestContext) -> None:
        """收尾节点自身必须有有限上限(防真死锁),不能退化成无限观察。"""
        op = self._make_op(test_context, init_network=True)
        node = op._node_map['战斗超时收尾']
        assert node.timeout_seconds is not None and node.timeout_seconds > 0

    def test_cleanup_on_success_counts_and_exits(
            self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
        """收尾节点看到挑战成功 → 补记完成次数 + 触发回调 + 点退出关卡。"""
        monkeypatch.setattr(
            'sr_od.challenge_mission.use_trailblaze_power.battle_screen_state.'
            'get_tp_battle_screen_state',
            lambda ctx, screen, **kw: '挑战成功')
        calls: list[str] = []
        op = self._make_op(test_context, on_battle_success=lambda t, p: calls.append((t, p)))
        monkeypatch.setattr(op, 'screenshot', lambda: None)
        clicked: list[str] = []

        def _fake_click(screen, screen_name, area_name, **kw):
            clicked.append(area_name)
            return object()

        monkeypatch.setattr(op, 'round_by_find_and_click_area', _fake_click)

        result = op._wait_battle_result_timeout()

        assert op.finish_times == 1  # 补记一次完成(主窗超时时记账缺失)
        assert calls == [(1, 10)]  # 回调收到当前次数与体力消耗(power=10 × 1 次)
        assert clicked == ['退出关卡按钮']
        assert result is not None

    def test_cleanup_on_fail_exits_without_counting(
            self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
        """收尾节点看到战斗失败 → 不补记不回调,仍要点退出关卡清场。"""
        monkeypatch.setattr(
            'sr_od.challenge_mission.use_trailblaze_power.battle_screen_state.'
            'get_tp_battle_screen_state',
            lambda ctx, screen, **kw: '战斗失败')
        op = self._make_op(test_context, on_battle_success=lambda t, p: pytest.fail('失败不应回调'))
        monkeypatch.setattr(op, 'screenshot', lambda: None)
        clicked: list[str] = []
        monkeypatch.setattr(
            op, 'round_by_find_and_click_area',
            lambda screen, sn, area_name, **kw: clicked.append(area_name) or object())

        op._wait_battle_result_timeout()

        assert op.finish_times == 0
        assert clicked == ['退出关卡按钮']

    def test_cleanup_keeps_waiting_mid_battle(
            self, test_context: SrTestContext, monkeypatch: pytest.MonkeyPatch) -> None:
        """收尾节点看不到结算画面(战斗仍在自打)→ round_wait 继续观察,不做任何点击。"""
        monkeypatch.setattr(
            'sr_od.challenge_mission.use_trailblaze_power.battle_screen_state.'
            'get_tp_battle_screen_state',
            lambda ctx, screen, **kw: '战斗')
        op = self._make_op(test_context)
        monkeypatch.setattr(op, 'screenshot', lambda: None)
        monkeypatch.setattr(
            op, 'round_by_find_and_click_area',
            lambda screen, sn, area_name, **kw: pytest.fail('未结算不应点击'))

        result = op._wait_battle_result_timeout()

        assert result.result.name == 'WAIT', f'应继续等待,实际 {result.result}'

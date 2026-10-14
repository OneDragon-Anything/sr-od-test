"""观察层对账仲裁批:星级抖动门(槽位锚定+两帧一致)。

锁 1 语义(T-35 识别优化批,取代终态契约 §A「回退即采新」临时语义):
run_20260915_054718 §5/§8 候选2 实锤「回退即采新」让同名多星单元的单帧
星读抖动直进主账(3★ 合成线整局被污染,episode ×3 全部「连续 2 帧」
形态恰好吃掉旧 N=2 确认门)。现行口径 = 槽位锚定 + 两帧一致才采新:
单帧差保旧写账 + 抖动台账行(surface='star');升/降同门、银狼升费形态无
豁免(门按锚判定与名无关);合成特效窗内星读不可信(冻结,不计两帧);
锚上身份变换(换人/落新单元)星级随身份直采。缺读帧打断两帧序列
(缺读 = 证据中断):候选锚部分缺读/整帧双空读(守卫早退)即清除,
同值复现须重新连续两帧。载体 = P6 观察链直产容器形状(备战席 BenchView /
上场位 DeployedView,语义断言自载体迁移零变)。

(tracked 第二账退役):比较基线 = 主域席位视图
(bench/deployed,锚 = (子表, 下标));门后副本经返回值交 director 观察
写主域——本文件 _recon 辅助 = 生产 director 环路的测试镜像
(reconcile → 门后视图 observe 落主域,两帧间账面与生产同源)。

锁 2(原 tracked 槽号守卫/摘除腿保洞)随 tracked 第二账退役整删:
同步腿删除后无锁面对象;主域侧「摘槽不移位/落位正确」语义由动作上报
测试族(test_cw_prep_action_ops、test_cw_gain_chain)承载。
"""
from __future__ import annotations

import numpy as np
import pytest

import sr_od.application.currency_war.kernel.cw_observe as cw_observe
import sr_od.application.currency_war.kernel.cw_reconcile as cw_reconcile
from sr_od.application.currency_war.kernel.cw_exec_state import (
    BENCH_CAPACITY,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    ChannelSig,
    DeployedView,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_reconcile import (
    reconcile_tracking,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)

_SIG_OBS = ChannelSig(family='obs', actor='cw4_seed', mode='synthesized')

@pytest.fixture(autouse=True)
def _drain_defect_buffer():
    """测试卫生(3.2):主域种子经 observe 覆盖开局种子(logic_rand 通道)
    会产预期内 logic_rand_outcome 行入进程级缓冲——前后双清,防跨用例
    顺序依赖红(同 test_cw_deploy / test_cw_effect_inventory 同款排水
    纪律)。"""
    from sr_od.application.currency_war.kernel.cw_game_state import (
        consume_defect_sink,
    )
    consume_defect_sink()
    yield
    consume_defect_sink()


def _spy_conflicts(monkeypatch) -> list[tuple]:
    """桩掉 obs_conflict(测试零真实副作用)+ 留行供仲裁断言。"""
    rows: list[tuple] = []

    def _rec(field, old, new, screen=None, *, verdict='', **ctx):
        rows.append((field, old, new, verdict))

    monkeypatch.setattr(cw_observe, 'obs_conflict', _rec)
    return rows


def _view(*specs: tuple[int, str, int]) -> BenchView:
    """P6 直产读载体:备战席 BenchView(specs = (物理槽号, 规范名, 星)),
    未列槽 = empty。"""
    slots: list[BenchSlot] = [BenchSlot(kind='empty')] * BENCH_CAPACITY
    for slot_no, name, star in specs:
        slots[slot_no - 1] = BenchSlot(
            kind='unit', unit=Unit(char_id=name, star=star))
    return BenchView(slots=slots)


_EMPTY_VIEW = BenchView()
_EMPTY_ROWS = DeployedView()


def _rows(*specs: tuple[str, int, str, int]):
    """P6 直产读载体:上场位 DeployedView(读侧
    分排读屏、对账载体 = 合一视图;specs = (排, 排内槽号, 规范名, 星),
    槽号 = 子表下标 + 1)。"""
    front: list[Unit | None] = [None] * 4
    back: list[Unit | None] = [None] * 6
    for row, slot_no, name, star in specs:
        (front if row == 'front' else back)[slot_no - 1] = \
            Unit(char_id=name, star=star)
    return DeployedView(front_slots=front, back_slots=back)


def _seed(session, bench: BenchView | None = None,
          dep: DeployedView | None = None) -> None:
    """主域账面种子(3.2:比较基线 = 主域席位视图)。"""
    gs = game_state_of(session)
    if bench is not None:
        gs.observe(gs.bench, bench, sig=_SIG_OBS)
    if dep is not None:
        gs.observe(gs.deployed, dep, sig=_SIG_OBS)


def _recon(session, bench, dep, screen=None) -> bool:
    """生产 director 环路镜像:reconcile(门后视图)→ observe 落主域。
    返回守卫是否放行(双空读守卫早退 = False,不落账)。"""
    ok, b, d = reconcile_tracking(session, bench, dep, screen=screen,
                                  source='test')
    if not ok:
        return False
    gs = game_state_of(session)
    if b is not None:
        gs.observe(gs.bench, b, sig=_SIG_OBS)
    if d is not None:
        gs.observe(gs.deployed, d, sig=_SIG_OBS)
    return True


def _bench_sig(session) -> list:
    """主域 bench 值签名(占用槽序:(名, 星);占位件 ('',1))。"""
    view = game_state_of(session).bench.value
    return [((s.unit.char_id, s.unit.star)
             if s.kind == 'unit' and s.unit is not None else ('', 1))
            for s in (view.slots if view is not None else [])
            if s.kind != 'empty']


def _deployed_sig(session) -> list:
    """主域 deployed 值签名((名, 排, 星);锚 = (排, 子表下标+1))。"""
    view = game_state_of(session).deployed.value
    out: list = []
    for row, sub in (('front', view.front_slots if view else None),
                     ('back', view.back_slots if view else None)):
        for _i, u in enumerate(sub or []):
            if u is not None:
                out.append((u.char_id, row, u.star))
    return out


# ===== 锁 1:星级抖动门(槽位锚定 + 两帧一致才采新)=====


def test_star_single_frame_jitter_held(monkeypatch):
    """单帧抖动不写账:3★@槽1 单帧读 1★ → 主域保 3★ + surface='star'
    抖动台账行;下帧读回与账一致 → 候选作废,无新增台账行(常态无噪声)。"""
    rows = _spy_conflicts(monkeypatch)
    session = StrategySession()
    _seed(session, bench=_view((1, '不死途', 3)))

    assert _recon(session, _view((1, '不死途', 1)), _EMPTY_ROWS)

    assert _bench_sig(session) == [('不死途', 3)]   # 单帧抖动保旧
    star_rows = [r for r in rows if r[0] == 'star']
    assert len(star_rows) == 1 and '保旧' in star_rows[0][3]

    assert _recon(session, _view((1, '不死途', 3)), _EMPTY_ROWS)

    assert _bench_sig(session) == [('不死途', 3)]
    assert len([r for r in rows if r[0] == 'star']) == 1   # 读账一致零噪声


def test_star_change_needs_two_frame_consistency(monkeypatch):
    """两帧一致才采新(升/降同门):3★→1★ 连续两帧才落账;1★→2★ 升星
    读数同样须两帧(合成后实读延迟一帧,防单帧抖动毒化 3★ 合成判断)。"""
    _spy_conflicts(monkeypatch)
    session = StrategySession()
    _seed(session, bench=_view((1, '不死途', 3)))

    assert _recon(session, _view((1, '不死途', 1)), _EMPTY_ROWS)
    assert _bench_sig(session) == [('不死途', 3)]   # 首帧差:保旧
    assert _recon(session, _view((1, '不死途', 1)), _EMPTY_ROWS)
    assert _bench_sig(session) == [('不死途', 1)]   # 次帧同值:采新

    assert _recon(session, _view((1, '不死途', 2)), _EMPTY_ROWS)
    assert _bench_sig(session) == [('不死途', 1)]   # 升星首帧:保旧
    assert _recon(session, _view((1, '不死途', 2)), _EMPTY_ROWS)
    assert _bench_sig(session) == [('不死途', 2)]   # 升星次帧:采新


def test_same_name_multi_star_slot_anchored_no_cross_star(monkeypatch):
    """同名多星并存槽位锚定:单槽抖动不串邻槽;真换位(整表重排)两帧
    按新槽位落账且全程不串星;换人(锚上身份变)星级随身份直采不辖门。"""
    _spy_conflicts(monkeypatch)
    session = StrategySession()
    _seed(session, bench=_view((4, '不死途', 1), (6, '不死途', 2),
                               (7, '不死途', 3)))
    # 帧1:槽7 单帧读 1★(抖动),槽4/6 照读 → 逐槽保旧,邻槽不串
    assert _recon(session, _view((4, '不死途', 1), (6, '不死途', 2),
                                 (7, '不死途', 1)), _EMPTY_ROWS)
    assert _bench_sig(session) == [('不死途', 1), ('不死途', 2),
                                   ('不死途', 3)]
    # 帧2:槽7 同抖动复现(两帧一致采新 1★);槽4 升 2★ 单帧读保旧
    assert _recon(session, _view((4, '不死途', 2), (6, '不死途', 2),
                                 (7, '不死途', 1)), _EMPTY_ROWS)
    assert _bench_sig(session) == [('不死途', 1), ('不死途', 2),
                                   ('不死途', 1)]
    # 换位:槽4↔槽7 星级互换(1★/3★ 两帧一致后落新槽位,槽6 不串)
    assert _recon(session, _view((4, '不死途', 3), (6, '不死途', 2),
                                 (7, '不死途', 1)), _EMPTY_ROWS)
    assert _bench_sig(session) == [('不死途', 1), ('不死途', 2),
                                   ('不死途', 1)]   # 换位首帧:保旧
    assert _recon(session, _view((4, '不死途', 3), (6, '不死途', 2),
                                 (7, '不死途', 1)), _EMPTY_ROWS)
    assert _bench_sig(session) == [('不死途', 3), ('不死途', 2),
                                   ('不死途', 1)]   # 次帧:新槽位落账
    # 换人:槽6 落新单元(异名)→ 直采,不受门前槽6 候选态影响
    assert _recon(session, _view((4, '不死途', 3), (6, '花火', 1),
                                 (7, '不死途', 1)), _EMPTY_ROWS)
    assert _bench_sig(session) == [('不死途', 3), ('花火', 1),
                                   ('不死途', 1)]


def test_star_gate_name_agnostic_silver_wolf(monkeypatch):
    """门按锚判定与名无关(银狼升费形态无豁免):单帧保旧,两帧采新。"""
    _spy_conflicts(monkeypatch)
    session = StrategySession()
    _seed(session, bench=_view((1, '银狼', 2)))

    assert _recon(session, _view((1, '银狼', 1)), _EMPTY_ROWS)
    assert _bench_sig(session) == [('银狼', 2)]
    assert _recon(session, _view((1, '银狼', 1)), _EMPTY_ROWS)
    assert _bench_sig(session) == [('银狼', 1)]


def test_deployed_slot_anchor_two_frame(monkeypatch):
    """deployed 侧锚 = (排, 子表下标+1)(ADR-0392;3.2:基线 = 主域
    deployed 视图):后排槽3 单帧 3★→1★ 保旧,两帧一致采新。
    读载体 = P6 直产视图。"""
    _spy_conflicts(monkeypatch)
    session = StrategySession()
    _seed(session, dep=_rows(('back', 3, '不死途', 3)))

    def _read_back3(star: int) -> tuple:
        return _rows(('back', 3, '不死途', star))

    assert _recon(session, _EMPTY_VIEW, _read_back3(1))
    assert _deployed_sig(session) == [('不死途', 'back', 3)]   # 首帧:保旧
    assert _recon(session, _EMPTY_VIEW, _read_back3(1))
    assert _deployed_sig(session) == [('不死途', 'back', 1)]   # 次帧:采新


def test_merge_effect_window_freezes_confirmation(monkeypatch):
    """合成特效窗冻结(帧态维,与两帧时间维正交):窗内星差保旧且不登记
    候选(动画帧不计两帧)——窗后干净帧须再连续两帧才采新。"""
    _spy_conflicts(monkeypatch)
    monkeypatch.setattr(cw_reconcile, '_IS_MERGE_EFFECT_FRAME',
                        lambda screen: True)
    session = StrategySession()
    _seed(session, bench=_view((1, '不死途', 3)))
    _scr = np.zeros((4, 4), dtype='uint8')   # 非 None 帧才进特效窗判别

    assert _recon(session, _view((1, '不死途', 1)), _EMPTY_ROWS,
                  screen=_scr)
    assert _recon(session, _view((1, '不死途', 1)), _EMPTY_ROWS,
                  screen=_scr)
    assert _bench_sig(session) == [('不死途', 3)]   # 窗内两帧不确认

    monkeypatch.setattr(cw_reconcile, '_IS_MERGE_EFFECT_FRAME',
                        lambda screen: False)
    assert _recon(session, _view((1, '不死途', 1)), _EMPTY_ROWS,
                  screen=_scr)
    assert _bench_sig(session) == [('不死途', 3)]   # 干净帧1:候选登记
    assert _recon(session, _view((1, '不死途', 1)), _EMPTY_ROWS,
                  screen=_scr)
    assert _bench_sig(session) == [('不死途', 1)]   # 干净帧2:采新


def test_missing_read_frame_breaks_confirmation(monkeypatch):
    """缺读帧打断两帧序列(缺读 = 证据中断,两帧重计)。P6 直产载体下
    两形态并一:
    - 部分缺读(读侧已取得但锚不在):主域随实读整表替换,缺席槽置空
      (真实部分读行为,槽1 3★ 账随实读消失)+ 后续单元重落直采
      (陈旧候选不作祟);
    - 双空读守卫早退帧:保旧 + 候选清除(探针原样序列:抖读 → 双空 →
      同值首帧重计保旧,连续次帧才采新);
    - 失读侧(None,读失败):候选态保持、主域跳过(门「不辖」分支;
      同值复现帧单帧采新 = 保持语义的可观察面)。"""
    _spy_conflicts(monkeypatch)
    # 形态一:部分缺读(帧2 读侧不含槽1 → 缺席槽随实读置空)
    session = StrategySession()
    _seed(session, bench=_view((1, '不死途', 3)))
    assert _recon(session, _view((1, '不死途', 1)), _EMPTY_ROWS)
    assert _bench_sig(session) == [('不死途', 3)]   # 帧1:抖读保旧+候选登记
    assert _recon(session, _view((2, '甲', 1)), _EMPTY_ROWS)
    assert _bench_sig(session) == [('甲', 1)]   # 帧2:部分缺读,缺席槽置空
    assert _recon(session, _view((1, '不死途', 1)), _EMPTY_ROWS)
    assert _bench_sig(session) == [('不死途', 1)]   # 帧3:单元重落,直采
    # 形态二:双空读守卫早退帧(探针原样序列)
    session2 = StrategySession()
    _seed(session2, bench=_view((1, '不死途', 3)))
    assert _recon(session2, _view((1, '不死途', 1)), _EMPTY_ROWS)
    assert _bench_sig(session2) == [('不死途', 3)]   # 抖读保旧+候选登记
    assert not _recon(session2, _EMPTY_VIEW, _EMPTY_ROWS)   # 双空守卫
    assert _bench_sig(session2) == [('不死途', 3)]   # 守卫保旧主域
    assert _recon(session2, _view((1, '不死途', 1)), _EMPTY_ROWS)
    assert _bench_sig(session2) == [('不死途', 3)]   # 缺读后同值首帧:重计保旧
    assert _recon(session2, _view((1, '不死途', 1)), _EMPTY_ROWS)
    assert _bench_sig(session2) == [('不死途', 1)]   # 连续次帧:采新
    # 形态三:bench 侧失读(None)——候选保持、主域跳过;同值复现帧
    # 单帧采新 = 「不辖」语义的可观察面(deployed 侧照常读)。
    session3 = StrategySession()
    _seed(session3, bench=_view((1, '不死途', 3)))
    assert _recon(session3, _view((1, '不死途', 1)), _EMPTY_ROWS)
    assert _bench_sig(session3) == [('不死途', 3)]   # 抖读保旧+候选登记
    assert _recon(session3, None, _rows(('back', 3, '花火', 1)))
    assert _bench_sig(session3) == [('不死途', 3)]   # bench 失读:账不动
    assert _recon(session3, _view((1, '不死途', 1)), _EMPTY_ROWS)
    assert _bench_sig(session3) == [('不死途', 1)]   # 候选跨失读帧存活:单帧采新

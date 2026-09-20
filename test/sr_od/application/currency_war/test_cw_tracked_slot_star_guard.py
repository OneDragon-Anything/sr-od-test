"""观察层对账仲裁批:星级抖动门(槽位锚定+两帧一致)+ tracked 槽号守卫。

锁 1 语义变更(T-35 识别优化批,取代终态契约 §A「回退即采新」临时语义):
run_20260915_054718 §5/§8 候选2 实锤「回退即采新」让同名多星单元的单帧
星读抖动直进 tracked 主账(3★ 合成线整局被污染,episode ×3 全部「连续
2 帧」形态恰好吃掉旧 N=2 确认门)。现行口径 = 槽位锚定 + 两帧一致才采新:
单帧差保旧写账 + 抖动台账行(surface='star');升/降同门、银狼升费形态无
豁免(门按锚判定与名无关);合成特效窗内星读不可信(冻结,不计两帧);
锚上身份变换(换人/落新单元)星级随身份直采。缺读帧打断两帧序列
(缺读 = 证据中断):候选锚部分缺读/整帧双空读(守卫早退)即清除,
同值复现须重新连续两帧。载体 = P6 观察链直产容器形状(备战席 BenchView /
上场位 (前排, 后排) Unit 行,语义断言自载体迁移零变):
部分缺读帧的写回随实读整表替换(缺席槽置空)→ 旧「缺读 + 账 intact 重计」
形态失去可达输入,由守卫早退形态(形态二)与失读侧候选保持锁承接。

锁 2(tracked 槽号守卫)随载体收窄只剩健康静默腿:摘除腿按下标置 None
(pad 态契约不破坏)+ 写点健康显影。反帧显影腿(重复/越界槽号 → 台账行)
随 BenchChar 信息位载体退役删除:tracked 容器形槽号 = 下标+1 结构性健康
(ADR-0646 无守卫槽号面随形状消失),脏输入不可构造 = 生产不可达状态不锁
(同 P6 拒写回锁退役口径)。
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

import sr_od.application.currency_war.kernel.cw_observe as cw_observe
import sr_od.application.currency_war.kernel.cw_reconcile as cw_reconcile
from sr_od.application.currency_war import prep_actions as pa
from sr_od.application.currency_war.kernel.cw_exec_state import (
    BENCH_CAPACITY,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    BenchSlot,
    BenchView,
    Unit,
    game_state_of,
)
from sr_od.application.currency_war.kernel.cw_reconcile import (
    reconcile_tracking,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)
from sr_od.application.currency_war.telemetry import defects


def _spy_conflicts(monkeypatch) -> list[tuple]:
    """桩掉 obs_conflict(测试零真实副作用)+ 留行供仲裁断言。"""
    rows: list[tuple] = []

    def _rec(field, old, new, screen=None, *, verdict='', **ctx):
        rows.append((field, old, new, verdict))

    monkeypatch.setattr(cw_observe, 'obs_conflict', _rec)
    return rows


def _spy_defects(monkeypatch) -> list[tuple]:
    """桩掉缺陷台账写入 + 留行供显影断言(同 seed_tracked_rebuild 模式)。"""
    rows: list[tuple] = []

    def _rec(surface, kind, expected, observed, **kwargs):
        rows.append((surface, kind, observed, kwargs.get('reader_source')))

    monkeypatch.setattr(defects, 'record_defect', _rec)
    return rows


def _mk_executor(session):
    """执行器替身构造(同 unified_action_2a harness;ctx 挂真 session)。"""
    ex = pa.PrepActionExecutor(
        SimpleNamespace(screenshot=lambda: np.zeros((4, 4), dtype='uint8')),
        SimpleNamespace(controller=SimpleNamespace(), cw_match=None,
                        run_context=None,
                        screen_loader=SimpleNamespace(
                            get_screen=lambda name: None)))
    ex._ctx = SimpleNamespace(
        controller=SimpleNamespace(),
        cw_match=SimpleNamespace(session=session),
        screen_loader=SimpleNamespace(get_screen=lambda name: None),
        run_context=None)
    return ex


def _tracked_sig(session) -> list:
    """tracked bench 值签名(P1 形状:BenchSlot → 内嵌 Unit 身份)。"""
    return [((b.unit.char_id, b.unit.star) if getattr(b, 'kind', None) == 'unit'
             and b.unit is not None else ('', 1))
            for b in (game_state_of(session).tracked_books.bench or [])
            if b is not None]


def _deployed_sig(session) -> list:
    """tracked deployed 值签名(P1 形状:Unit 下标表,排归属由下标派生)。"""
    return [(b.char_id, 'front' if i < 4 else 'back', b.star)
            for i, b in enumerate(
                game_state_of(session).tracked_books.deployed or [])
            if b is not None]


def _tracked_bench(*specs: tuple[int, str, int]) -> list:
    """tracked bench 种子(§2.3 定稿形状 list[BenchSlot | None],定长 9;
    specs = (物理槽号, 规范名, 星),缺席槽 = None 洞)。"""
    bench: list = [None] * BENCH_CAPACITY
    for slot_no, name, star in specs:
        bench[slot_no - 1] = BenchSlot(
            kind='unit', unit=Unit(char_id=name, star=star, slot=slot_no))
    return bench


def _view(*specs: tuple[int, str, int]) -> BenchView:
    """P6 直产读载体:备战席 BenchView(specs = (物理槽号, 规范名, 星)),
    未列槽 = empty。"""
    slots: list[BenchSlot] = [BenchSlot(kind='empty')] * BENCH_CAPACITY
    for slot_no, name, star in specs:
        slots[slot_no - 1] = BenchSlot(
            kind='unit', unit=Unit(char_id=name, star=star, slot=slot_no))
    return BenchView(slots=slots)


_EMPTY_VIEW = BenchView()
_EMPTY_ROWS: tuple = ([], [])


def _rows(*specs: tuple[str, int, str, int]) -> tuple:
    """P6 直产读载体:上场位 (前排, 后排) Unit 行
    (specs = (排, 排内槽号, 规范名, 星))。"""
    front: list[Unit] = []
    back: list[Unit] = []
    for row, slot_no, name, star in specs:
        (front if row == 'front' else back).append(
            Unit(char_id=name, star=star, slot=slot_no))
    return front, back


# ===== 锁 1:星级抖动门(槽位锚定 + 两帧一致才采新)=====


def test_star_single_frame_jitter_held(monkeypatch):
    """单帧抖动不写账:3★@槽1 单帧读 1★ → tracked 保 3★ + surface='star'
    抖动台账行;下帧读回与账一致 → 候选作废,无新增台账行(常态无噪声)。"""
    rows = _spy_conflicts(monkeypatch)
    session = StrategySession()
    game_state_of(session).tracked_books.bench = _tracked_bench(
        (1, '不死途', 3))

    reconcile_tracking(session, _view((1, '不死途', 1)), _EMPTY_ROWS,
                       source='test')

    assert _tracked_sig(session) == [('不死途', 3)]   # 单帧抖动保旧
    star_rows = [r for r in rows if r[0] == 'star']
    assert len(star_rows) == 1 and '保旧' in star_rows[0][3]

    reconcile_tracking(session, _view((1, '不死途', 3)), _EMPTY_ROWS,
                       source='test')

    assert _tracked_sig(session) == [('不死途', 3)]
    assert len([r for r in rows if r[0] == 'star']) == 1   # 读账一致零噪声


def test_star_change_needs_two_frame_consistency(monkeypatch):
    """两帧一致才采新(升/降同门):3★→1★ 连续两帧才落账;1★→2★ 升星
    读数同样须两帧(合成后实读延迟一帧,防单帧抖动毒化 3★ 合成判断)。"""
    _spy_conflicts(monkeypatch)
    session = StrategySession()
    game_state_of(session).tracked_books.bench = _tracked_bench(
        (1, '不死途', 3))

    reconcile_tracking(session, _view((1, '不死途', 1)), _EMPTY_ROWS,
                       source='test')
    assert _tracked_sig(session) == [('不死途', 3)]   # 首帧差:保旧
    reconcile_tracking(session, _view((1, '不死途', 1)), _EMPTY_ROWS,
                       source='test')
    assert _tracked_sig(session) == [('不死途', 1)]   # 次帧同值:采新

    reconcile_tracking(session, _view((1, '不死途', 2)), _EMPTY_ROWS,
                       source='test')
    assert _tracked_sig(session) == [('不死途', 1)]   # 升星首帧:保旧
    reconcile_tracking(session, _view((1, '不死途', 2)), _EMPTY_ROWS,
                       source='test')
    assert _tracked_sig(session) == [('不死途', 2)]   # 升星次帧:采新


def test_same_name_multi_star_slot_anchored_no_cross_star(monkeypatch):
    """同名多星并存槽位锚定:单槽抖动不串邻槽;真换位(整表重排)两帧
    按新槽位落账且全程不串星;换人(锚上身份变)星级随身份直采不辖门。"""
    _spy_conflicts(monkeypatch)
    session = StrategySession()
    game_state_of(session).tracked_books.bench = _tracked_bench(
        (4, '不死途', 1), (6, '不死途', 2), (7, '不死途', 3))
    # 帧1:槽7 单帧读 1★(抖动),槽4/6 照读 → 逐槽保旧,邻槽不串
    reconcile_tracking(session, _view((4, '不死途', 1), (6, '不死途', 2),
                                      (7, '不死途', 1)),
                       _EMPTY_ROWS, source='test')
    assert _tracked_sig(session) == [('不死途', 1), ('不死途', 2),
                                     ('不死途', 3)]
    # 帧2:槽7 同抖动复现(两帧一致采新 1★);槽4 升 2★ 单帧读保旧
    reconcile_tracking(session, _view((4, '不死途', 2), (6, '不死途', 2),
                                      (7, '不死途', 1)),
                       _EMPTY_ROWS, source='test')
    assert _tracked_sig(session) == [('不死途', 1), ('不死途', 2),
                                     ('不死途', 1)]
    # 换位:槽4↔槽7 星级互换(1★/3★ 两帧一致后落新槽位,槽6 不串)
    reconcile_tracking(session, _view((4, '不死途', 3), (6, '不死途', 2),
                                      (7, '不死途', 1)),
                       _EMPTY_ROWS, source='test')
    assert _tracked_sig(session) == [('不死途', 1), ('不死途', 2),
                                     ('不死途', 1)]   # 换位首帧:保旧
    reconcile_tracking(session, _view((4, '不死途', 3), (6, '不死途', 2),
                                      (7, '不死途', 1)),
                       _EMPTY_ROWS, source='test')
    assert _tracked_sig(session) == [('不死途', 3), ('不死途', 2),
                                     ('不死途', 1)]   # 次帧:新槽位落账
    # 换人:槽6 落新单元(异名)→ 直采,不受门前槽6 候选态影响
    reconcile_tracking(session, _view((4, '不死途', 3), (6, '花火', 1),
                                      (7, '不死途', 1)),
                       _EMPTY_ROWS, source='test')
    assert _tracked_sig(session) == [('不死途', 3), ('花火', 1),
                                     ('不死途', 1)]


def test_star_gate_name_agnostic_silver_wolf(monkeypatch):
    """门按锚判定与名无关(银狼升费形态无豁免):单帧保旧,两帧采新。"""
    _spy_conflicts(monkeypatch)
    session = StrategySession()
    game_state_of(session).tracked_books.bench = _tracked_bench(
        (1, '银狼', 2))

    reconcile_tracking(session, _view((1, '银狼', 1)), _EMPTY_ROWS,
                       source='test')
    assert _tracked_sig(session) == [('银狼', 2)]
    reconcile_tracking(session, _view((1, '银狼', 1)), _EMPTY_ROWS,
                       source='test')
    assert _tracked_sig(session) == [('银狼', 1)]


def test_deployed_slot_anchor_two_frame(monkeypatch):
    """deployed 侧锚 = 槽位表下标→(排, 排内槽号)(ADR-0392):后排槽3
    单帧 3★→1★ 保旧,两帧一致采新。(tracked 种子 = §2.3 定稿形状
    list[Unit | None],槽位表下标 6 = 后排槽 3 → 行内槽号 3。
    读载体 = P6 直产行域。)"""
    _spy_conflicts(monkeypatch)
    session = StrategySession()
    _dep: list = [None] * 10
    _dep[6] = Unit(char_id='不死途', star=3, slot=3)   # 下标 6 = 后排槽 3
    game_state_of(session).tracked_books.deployed = _dep

    def _read_back3(star: int) -> tuple:
        return _rows(('back', 3, '不死途', star))

    reconcile_tracking(session, _EMPTY_VIEW, _read_back3(1), source='test')
    assert _deployed_sig(session) == [('不死途', 'back', 3)]   # 首帧:保旧
    reconcile_tracking(session, _EMPTY_VIEW, _read_back3(1), source='test')
    assert _deployed_sig(session) == [('不死途', 'back', 1)]   # 次帧:采新


def test_merge_effect_window_freezes_confirmation(monkeypatch):
    """合成特效窗冻结(帧态维,与两帧时间维正交):窗内星差保旧且不登记
    候选(动画帧不计两帧)——窗后干净帧须再连续两帧才采新。"""
    _spy_conflicts(monkeypatch)
    monkeypatch.setattr(cw_reconcile, '_IS_MERGE_EFFECT_FRAME',
                        lambda screen: True)
    session = StrategySession()
    game_state_of(session).tracked_books.bench = _tracked_bench(
        (1, '不死途', 3))
    _scr = np.zeros((4, 4), dtype='uint8')   # 非 None 帧才进特效窗判别

    reconcile_tracking(session, _view((1, '不死途', 1)), _EMPTY_ROWS,
                       screen=_scr, source='test')
    reconcile_tracking(session, _view((1, '不死途', 1)), _EMPTY_ROWS,
                       screen=_scr, source='test')
    assert _tracked_sig(session) == [('不死途', 3)]   # 窗内两帧不确认

    monkeypatch.setattr(cw_reconcile, '_IS_MERGE_EFFECT_FRAME',
                        lambda screen: False)
    reconcile_tracking(session, _view((1, '不死途', 1)), _EMPTY_ROWS,
                       screen=_scr, source='test')
    assert _tracked_sig(session) == [('不死途', 3)]   # 干净帧1:候选登记
    reconcile_tracking(session, _view((1, '不死途', 1)), _EMPTY_ROWS,
                       screen=_scr, source='test')
    assert _tracked_sig(session) == [('不死途', 1)]   # 干净帧2:采新


def test_missing_read_frame_breaks_confirmation(monkeypatch):
    """缺读帧打断两帧序列(缺读 = 证据中断,两帧重计)。P6 直产载体下
    两形态并一:
    - 部分缺读(读侧已取得但锚不在):写回随实读整表替换,缺席槽置空
      (真实部分读行为,槽1 3★ 账随实读消失)+ 后续单元重落直采
      (陈旧候选不作祟);
    - 双空读守卫早退帧:保旧 + 候选清除(探针原样序列:抖读 → 双空 →
      同值首帧重计保旧,连续次帧才采新);
    - 失读侧(None,读失败):候选态保持、写回跳过(门「不辖」分支;
      同值复现帧单帧采新 = 保持语义的可观察面)。"""
    _spy_conflicts(monkeypatch)
    # 形态一:部分缺读(帧2 读侧不含槽1 → 缺席槽随实读置空)
    session = StrategySession()
    game_state_of(session).tracked_books.bench = _tracked_bench(
        (1, '不死途', 3))
    reconcile_tracking(session, _view((1, '不死途', 1)), _EMPTY_ROWS,
                       source='test')
    assert _tracked_sig(session) == [('不死途', 3)]   # 帧1:抖读保旧+候选登记
    reconcile_tracking(session, _view((2, '甲', 1)), _EMPTY_ROWS,
                       source='test')
    assert _tracked_sig(session) == [('甲', 1)]   # 帧2:部分缺读,缺席槽置空
    reconcile_tracking(session, _view((1, '不死途', 1)), _EMPTY_ROWS,
                       source='test')
    assert _tracked_sig(session) == [('不死途', 1)]   # 帧3:单元重落,直采
    # 形态二:双空读守卫早退帧(探针原样序列)
    session2 = StrategySession()
    game_state_of(session2).tracked_books.bench = _tracked_bench(
        (1, '不死途', 3))
    reconcile_tracking(session2, _view((1, '不死途', 1)), _EMPTY_ROWS,
                       source='test')
    assert _tracked_sig(session2) == [('不死途', 3)]   # 抖读保旧+候选登记
    ok, _, _ = reconcile_tracking(session2, _EMPTY_VIEW, _EMPTY_ROWS,
                                  source='test')
    assert not ok   # 双空守卫
    assert _tracked_sig(session2) == [('不死途', 3)]   # 守卫保旧 tracking
    reconcile_tracking(session2, _view((1, '不死途', 1)), _EMPTY_ROWS,
                       source='test')
    assert _tracked_sig(session2) == [('不死途', 3)]   # 缺读后同值首帧:重计保旧
    reconcile_tracking(session2, _view((1, '不死途', 1)), _EMPTY_ROWS,
                       source='test')
    assert _tracked_sig(session2) == [('不死途', 1)]   # 连续次帧:采新
    # 形态三:bench 侧失读(None)——候选保持、写回跳过;同值复现帧
    # 单帧采新 = 「不辖」语义的可观察面(deployed 侧照常读)。
    session3 = StrategySession()
    game_state_of(session3).tracked_books.bench = _tracked_bench(
        (1, '不死途', 3))
    reconcile_tracking(session3, _view((1, '不死途', 1)), _EMPTY_ROWS,
                       source='test')
    assert _tracked_sig(session3) == [('不死途', 3)]   # 抖读保旧+候选登记
    reconcile_tracking(session3, None,
                       _rows(('back', 3, '花火', 1)), source='test')
    assert _tracked_sig(session3) == [('不死途', 3)]   # bench 失读:账不动
    reconcile_tracking(session3, _view((1, '不死途', 1)), _EMPTY_ROWS,
                       source='test')
    assert _tracked_sig(session3) == [('不死途', 1)]   # 候选跨失读帧存活:单帧采新


# ===== 锁 2:tracked 槽号守卫(写点置 None + 显影 + 仲裁门)=====


def test_removal_keeps_layout_sell_and_move_legs():
    """摘除腿按下标置 None 两腿(并一):sell 腿保洞契约不破坏,存件
    不移位、槽位信息位不动;CwActionDeployMoveParam 腿同治本,bench 置 None 不移位 +
    deployed 正常落槽。(载体 = P1 tracked 新形状:BenchSlot 内嵌 Unit,
    槽位信息位 = unit.slot;断言语义逐位不变。)"""
    # sell 腿:卖槽2(下标 1)
    session = StrategySession()
    game_state_of(session).tracked_books.bench = _tracked_bench(
        (1, '花火', 1), (2, '刃', 1), (3, '椒丘', 1))
    ex = _mk_executor(session)

    ex._track_remove_bench(1)

    tracked = game_state_of(session).tracked_books.bench
    assert len(tracked) == BENCH_CAPACITY   # 定长保持
    assert tracked[1] is None
    assert tracked[0] is not None \
        and (tracked[0].unit.char_id, tracked[0].unit.slot) == ('花火', 1)
    assert tracked[2] is not None \
        and (tracked[2].unit.char_id, tracked[2].unit.slot) == ('椒丘', 3)
    # 不移位:槽3 件仍在槽3(旧紧凑重排会把它挪到槽2)
    # move 腿:花火 bench槽1 → 前排槽1
    session_m = StrategySession()
    game_state_of(session_m).tracked_books.bench = _tracked_bench(
        (1, '花火', 1), (2, '刃', 1))
    game_state_of(session_m).tracked_books.deployed = []
    ex_m = _mk_executor(session_m)

    ex_m._track_move_deployed(0, 'front', 1)

    tracked_m = game_state_of(session_m).tracked_books.bench
    assert tracked_m[0] is None \
        and tracked_m[1].unit.char_id == '刃' \
        and tracked_m[1].unit.slot == 2   # 刃 不移位
    deployed = [b for b in game_state_of(session_m).tracked_books.deployed
                if b is not None]
    assert [(b.char_id, 'front' if i < 4 else 'back')
            for i, b in enumerate(deployed)] == [('花火', 'front')]


def test_tracked_write_guard_healthy_silence(monkeypatch):
    """写点健康静默:健康账摘除零显影(常态无噪声)。(反帧显影腿随
    BenchChar 信息位载体退役删除:容器形槽号 = 下标+1 结构性健康,
    重复/越界槽号不可构造,生产不可达状态不锁——见模块头锁 2 节。)"""
    rows_h = _spy_defects(monkeypatch)
    session_h = StrategySession()
    game_state_of(session_h).tracked_books.bench = _tracked_bench(
        (1, '花火', 1), (2, '刃', 1))
    ex_h = _mk_executor(session_h)

    ex_h._track_remove_bench(1)
    assert rows_h == []

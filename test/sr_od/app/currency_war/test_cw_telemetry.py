# -*- coding: utf-8 -*-
"""test_cw_telemetry 主题锁(结构合并批,机械拼接)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- w146_intention_telemetry: test_cw_w146_intention_telemetry.py
- w148_owned_pool_chain: test_cw_w148_owned_pool_chain.py
- w209_equip_telemetry: test_cw_w209_equip_telemetry.py
- w222_telemetry_gaps: test_cw_w222_telemetry_gaps.py
- w253_boss_names_telemetry: test_cw_w253_boss_names_telemetry.py
冲突改名:后来者顶层名加来源前缀(_<tag>_原名)。
"""
from __future__ import annotations


# ==================== w146_intention_telemetry ====================

import json

from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    serialize_intention,
)

from sr_od.application.currency_war.sim.engine_p1 import simulate_p1
from sr_od.application.currency_war.kernel.cw_state import GameState

from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder


def _record_one(tmp_path, extra):
    """最小 fixture:一条 decisions 落盘并读回(tmp_path,不写真实 .debug/)。"""
    rec = TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    rec.start_run('run_w146', 'A2')
    rec.record_decision('run_w146', 'A2', GameState(), 'X',
                        {}, {}, [], extra=extra)
    rows = [json.loads(ln) for ln in
            (tmp_path / 'decisions.jsonl').read_text(encoding='utf-8'
                                                     ).splitlines()]
    assert rows
    return rows[-1]


def test_locked_row_carries_phase_and_comp(tmp_path):
    """①锁定局决策行:v3_intention.phase='locked' 且 locked_comp=目标名。"""
    row = _record_one(tmp_path, {
        'v3_intention': serialize_intention(
            IntentionState(phase='locked', locked_comp='DOT卡芙卡',
                           lock_layer=3, lock_plane=1, lock_round=4)),
    })
    ist = row['v3_intention']
    assert isinstance(ist, dict)
    assert ist['phase'] == 'locked'
    assert ist['locked_comp'] == 'DOT卡芙卡'
    # 锁定时机遥测字段随行(判读锁定时点的直读维度)
    assert ist['lock_plane'] == 1 and ist['lock_round'] == 4


def test_unlocked_row_has_explicit_empty_state(tmp_path):
    """②未锁局:v3_intention 是 dict 且 phase='unlocked'(非缺失/非猜)。"""
    row = _record_one(tmp_path, {
        'v3_intention': serialize_intention(IntentionState()),
    })
    ist = row['v3_intention']
    assert isinstance(ist, dict)
    assert ist['phase'] == 'unlocked'
    assert ist['locked_comp'] == ''
    # 非法输入退 None(不是崩);extra 缺键 → 行缺省 None(旧 schema 兼容)
    assert serialize_intention(None) is None
    assert serialize_intention('junk') is None
    row2 = _record_one(tmp_path, {})
    assert row2['v3_intention'] is None


def test_sim_ledger_rows_carry_same_key():
    """③sim 账本同构:每轮行有 v3_intention 键(形状锁,不锁锁定分布)。"""
    res = simulate_p1(seed=20260827, use_refresh=False)
    assert res.ledger, 'sim 账本非空前提'
    for r in res.ledger:
        ist = r.get('v3_intention')
        assert ist is None or isinstance(ist, dict)
        if isinstance(ist, dict):
            assert ist.get('phase') in ('unlocked', 'locked', 'weak')
            if ist.get('phase') == 'locked':
                # 锁定行必带目标名(sim 分析批分锁定/未锁局的判据)
                assert ist.get('locked_comp')


# ==================== w148_owned_pool_chain ====================

from sr_od.application.currency_war.decision.cw_strategy import StrategySession
from sr_od.application.currency_war.operations.prep.equip_all import (
    _owned_wearable_names,
)
from sr_od.application.currency_war.decision.decision_v2.strategy import (
    DecisionV2Strategy,
)


def test_owned_wearable_names_filters_tools() -> None:
    """写端过滤:工具类(冶金炉)剔除,穿戴类保留;未注册名(识别残留)剔除。"""
    hits = [('冶金炉', (1800, 240), 0.9),      # 工具类 → 剔除
            ('财富宝钻', (1850, 240), 0.9),    # 穿戴类 → 保留
            ('未注册残影', (1900, 240), 0.9)]  # 不在 EQUIPMENTS → 剔除
    assert _owned_wearable_names(hits) == ['财富宝钻']


def test_session_last_owned_equips_defaults_empty() -> None:
    """session 新局默认空列表(非 None——下游 list() 拷贝不崩)。"""
    assert StrategySession().last_owned_equips == []


def test_pseudo_state_copies_owned_pool() -> None:
    """读端拷贝(W92 验收锚点①的锁形态):session 快照 → st.equips 非空。

    EquipAll 读到 owned 穿戴池(写 session.last_owned_equips)后,决策
    state.equips 必须非空——修复前此链断裂(恒空)。
    """
    sess = StrategySession()
    sess.last_owned_equips = ['财富宝钻', '分身墨镜']
    st = DecisionV2Strategy()._pseudo_state(None, sess)
    assert st.equips == ['财富宝钻', '分身墨镜']


def test_pseudo_state_owned_pool_empty_semantics_unchanged() -> None:
    """空快照:st.equips 为空列表(默认语义不变,不造出假持有)。"""
    sess = StrategySession()
    st = DecisionV2Strategy()._pseudo_state(None, sess)
    assert st.equips == []


# ==================== w209_equip_telemetry ====================

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_ROOT / 'src'))

from sr_od.application.currency_war.kernel.cw_reconcile import _merge_equips
from sr_od.application.currency_war.kernel.cw_state import BenchChar


def _bc(cid: str, slot: int = 1, row: str = 'back') -> BenchChar:
    return BenchChar(slot=slot, char_id=cid, position_pref=row)


def test_reconcile_preserves_equips_across_drift() -> None:
    """断点①:对账合并语义——char_id 续接保留 equips(整批替换不再清零)。

    run 26 希儿场景:旧 tracking [斩首行动,电磁弹射器],SIFT 新读对象
    equips=[] 默认 → 续接后保留(纠漂反复触发也不闪零)。
    """
    old = [_bc('希儿', 1, 'front')]
    old[0].equips = ['斩首行动', '电磁弹射器']
    new = [_bc('希儿', 1, 'front')]
    assert _merge_equips(old, new)[0].equips == ['斩首行动', '电磁弹射器']


def test_reconcile_picture_truth_wins_over_stale() -> None:
    """新读自带非空 equips(画面真值,如 deploy_bench 快照链)优先不覆盖。"""
    old = [_bc('卡芙卡')]
    old[0].equips = ['光能电池', '生命之花']
    new = [_bc('卡芙卡')]
    new[0].equips = ['绝对热量']   # 穿着合成后画面真值
    assert _merge_equips(old, new)[0].equips == ['绝对热量']


def test_reconcile_multi_copy_pairing_and_departure() -> None:
    """同名多副本逐个配对消耗(次序无关);离场角色的 equips 自然丢弃。"""
    old = [_bc('卡芙卡', 1), _bc('卡芙卡', 2)]
    old[0].equips = ['A']
    old[1].equips = ['B', 'C']
    new = [_bc('卡芙卡', 1), _bc('藿藿', 3)]
    out = _merge_equips(old, new)
    assert out[0].equips == ['A']
    assert out[1].equips == []          # 藿藿无旧账 → 空
    # 第二副本配对消耗(单副本新读只拿第一份,不多发)



# ==================== w222_telemetry_gaps ====================

import json
from pathlib import Path

from one_dragon.utils import log_utils
from sr_od.application.currency_war.telemetry import recorder as cw_telemetry
from sr_od.application.currency_war.kernel.cw_state import GameState

_SRC_ROOT = Path('src/sr_od/application/currency_war')


def _src(rel: str) -> str:
    """读源码文本(相对 currency_war 包路径;repo 根运行 pytest)。"""
    return (_SRC_ROOT / rel).read_text(encoding='utf-8')


# ===== 缺口①:decisions.state.equips 落盘链(record 站点)=====


def test_shop_record_site_copies_owned_pool_before_record() -> None:
    """buy_cards.py 主 record 站点(W970 批 A 随波循环自 shop.py 迁入):
    decide_prep 之后、record_decision 之前补拷。

    顺序锁三点:①拷贝行存在;②在 decide_prep 之后(装备权重读 state.equips,
    提前拷=改决策行为);③在其后的 record_decision(state 调用之前)。
    """
    src = _src('operations/prep/buy_cards.py')
    copy_line = 'state.equips = list(getattr(match.session, \'last_owned_equips\', []) or [])'
    assert copy_line in src, 'buy_cards record 站点缺 owned 池补拷行(W222 缺口①回归)'
    # W971 P2 黑板接口(dd-014):decide_prep → decide_shop_screen,顺序锁随迁
    i_plan = src.index('actions = match.strategy.decide_shop_screen')
    i_copy = src.index(copy_line)
    i_rec = src.index('recorder.record_decision(state, target_name')
    assert i_plan < i_copy < i_rec, '补拷必须在 decide_prep 之后、record 之前(行为边界)'


def test_director_record_step_copies_owned_pool_on_state_copy() -> None:
    """cw_screen_prep._record_step 步进站点:copy 后补拷(防污染 obs 决策输入)。"""
    src = _src('operations/cw_screen/cw_screen_prep.py')
    i_step = src.index('def _record_step')
    i_copy = src.index('st = st.copy()', i_step)
    i_equips = src.index('last_owned_equips', i_step)
    i_rec = src.index('recorder.record_decision(', i_step)
    assert i_step < i_copy < i_equips < i_rec, \
        '_record_step 必须先 copy 再补拷 equips 再 record(W222 缺口①回归)'


def test_record_decision_state_carries_equips(tmp_path) -> None:
    """端到端空值/非空回归:state.equips 经 serialize 落 decisions 行。"""
    # 分包期 6 消费面重写遗留修复:本文件 import 别名是 recorder 模块
    # (recorder as cw_telemetry),TelemetryRecorder 类在 recorder 模块;
    # 单例(_RECORDER 等)在 state 模块,桩点处另引 state。
    rec = cw_telemetry.TelemetryRecorder(replay_dir=tmp_path, enabled=True)
    st = GameState(gold=50, round_num=1, plane=1)
    st.equips = ['财富宝钻', '分身墨镜', '拆装扳手']
    rec.record_decision('w222', 'A8', st, '', {}, {}, [])
    rows = [json.loads(r) for r in
            (tmp_path / 'decisions.jsonl').read_text(encoding='utf-8').splitlines()]
    # 全量语义(工具同进快照,ADR-0387):不专名、只锁非空与成员
    assert set(rows[-1]['state']['equips']) == {'财富宝钻', '分身墨镜', '拆装扳手'}
    # 空值语义:默认 GameState → [](不造出假持有)
    rec.record_decision('w222', 'A8', GameState(), '', {}, {}, [])
    rows = [json.loads(r) for r in
            (tmp_path / 'decisions.jsonl').read_text(encoding='utf-8').splitlines()]
    assert rows[-1]['state']['equips'] == []


# ===== 缺口②:简报日志可见性(死 logger)=====


def test_briefing_modules_use_framework_logger() -> None:
    """三模块 _log 必须是框架 'OneDragon' logger(裸 getLogger=__name__ 无 handler,
    INFO 从未落地——全日志 0 条的根因)。"""
    import importlib

    for mod_name, attr in (
        ('sr_od.application.currency_war.operations.cw_screen.cw_screen_briefing', 'log'),
        ('sr_od.application.currency_war.obs.cw_briefing_obs', '_log'),
        ('sr_od.application.currency_war.operations.cw_entry.cw_entry_start', '_log'),
    ):
        mod = importlib.import_module(mod_name)
        assert getattr(mod, attr) is log_utils.log, \
            f'{mod_name}.{attr} 不是框架 logger(死 logger 回归)'



# ==================== w253_boss_names_telemetry ====================

import json
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_performance import RoundOutcome
from sr_od.application.currency_war.kernel.cw_state import GameState

from sr_od.application.currency_war.telemetry.schema import OutcomeRecord

from sr_od.application.currency_war.telemetry.recorder import TelemetryRecorder

from sr_od.application.currency_war.telemetry.query import read_jsonl

from sr_od.application.currency_war.telemetry.state import set_ctx_match


def _rec(tmp_path):
    return TelemetryRecorder(replay_dir=tmp_path, enabled=True)


def test_record_outcome_boss_names_roundtrip(tmp_path) -> None:
    """session.briefing_bosses 有实采真值 → 行带 boss_names,None 徽章态**保位**透传。"""
    set_ctx_match(SimpleNamespace(session=SimpleNamespace(
        target_comp=None,
        last_state=GameState(),
        briefing_bosses=['浮黎', None, '星期日'],
        selected_difficulty='A4',
        briefing_affixes=['伤害提高', '生命降低'],
    )))
    try:
        rec = _rec(tmp_path)
        rec.record_outcome('r1', RoundOutcome(round_num=9, plane=1, node_type='boss',
                                              comp_tag='c', hp_after=60))
        lines = read_jsonl(tmp_path / 'outcomes.jsonl')
        assert len(lines) == 1
        row = lines[0]
        # 位面序全量 3 元素;None 位面照 None 写在原位(防左移错位)
        assert row['boss_names'] == ['浮黎', None, '星期日']
        assert row['selected_difficulty'] == 'A4'
        assert row['enemy_affixes'] == ['伤害提高', '生命降低']
    finally:
        set_ctx_match(None)


def test_record_outcome_no_session_defaults(tmp_path) -> None:
    """无 ctx match/session 缺字段 → 落默认值(boss_names=None),记录不被阻塞。"""
    set_ctx_match(SimpleNamespace(session=SimpleNamespace(
        target_comp=None, last_state=GameState(),
    )))   # 无 briefing_bosses/难度/词缀属性
    try:
        rec = _rec(tmp_path)
        # 接管局开局:briefing_bosses 尚空(list 空)也落 None(未采 ≠ 全 None 行)
        rec.record_outcome('r1', RoundOutcome(round_num=1, plane=1, node_type='普通战斗',
                                              comp_tag='?', hp_after=100))
        set_ctx_match(None)   # 第二行彻底无 ctx(合成补给路径等)
        rec.record_outcome('r1', RoundOutcome(round_num=2, plane=1, node_type='补给',
                                              comp_tag='?', hp_after=99))
        rows = read_jsonl(tmp_path / 'outcomes.jsonl')
        for row in rows:
            assert row['boss_names'] is None
            assert row['selected_difficulty'] == ''
            assert row['enemy_affixes'] == []
    finally:
        set_ctx_match(None)


def test_record_outcome_empty_briefing_bosses_is_none(tmp_path) -> None:
    """briefing_bosses=[](未采,接管局常态)→ boss_names=None(区分「采到但徽章态」)。"""
    set_ctx_match(SimpleNamespace(session=SimpleNamespace(
        target_comp=None, last_state=GameState(), briefing_bosses=[],
    )))
    try:
        rec = _rec(tmp_path)
        rec.record_outcome('r1', RoundOutcome(round_num=5, plane=1, node_type='普通战斗',
                                              comp_tag='c', hp_after=80))
        (row,) = read_jsonl(tmp_path / 'outcomes.jsonl')
        assert row['boss_names'] is None
    finally:
        set_ctx_match(None)


# ===== 旧 schema 兼容锁 =====


def test_legacy_row_without_fields_readable(tmp_path) -> None:
    """旧 schema 行(无三新键)读取端容忍:.get 取默认不 KeyError。

    锁的是消费端契约——历史语料(outcomes.jsonl 大量 前旧行)与新代码共存时,
    分层/Δ池生成器等读 side 必须走 .get('/默认'),不得裸下标。
    """
    legacy = {'schema_version': 1, 'ts': '2026-08-26T09:00:00', 'run_id': 'run_old',
              'round_num': 9, 'plane': 1, 'node_type': 'boss', 'comp_tag': '?',
              'hp_after': 46, 'hp_confidence': 1.0}
    p = tmp_path / 'outcomes.jsonl'
    p.open('w', encoding='utf-8').write(json.dumps(legacy, ensure_ascii=False) + '\n')
    rows = read_jsonl(p)
    assert rows[0].get('boss_names') is None          # 旧行无键 → .get 默认容忍
    assert rows[0].get('selected_difficulty') is None
    assert rows[0].get('enemy_affixes') is None
    # 新键存在且默认值正确的 dataclass 正向对拍(构造期无 TypeError)
    rec = OutcomeRecord()
    assert rec.boss_names is None and rec.selected_difficulty == ''
    assert rec.enemy_affixes == []

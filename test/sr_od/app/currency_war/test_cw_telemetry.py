"""test_cw_telemetry 主题锁(结构合并批,机械拼接;删除波 1 重写)。

成员(原文件 docstring 语义索引;逐字搬运,断言零改动):
- w146_intention_telemetry: test_cw_w146_intention_telemetry.py
- w148_owned_pool_chain: test_cw_w148_owned_pool_chain.py
- w209_equip_telemetry: test_cw_w209_equip_telemetry.py
- w222_telemetry_gaps: test_cw_w222_telemetry_gaps.py
- w253_boss_names_telemetry: test_cw_w253_boss_names_telemetry.py
冲突改名:后来者顶层名加来源前缀(_<tag>_原名)。

删除波 1(用户 2026-09-10 直迁裁定):decisions/outcomes 等收编 9 流的
写入端退役,原「经 record_* 落行」的锁面按两条路重写——①语义存活面
(serialize_intention 纯函数/序列化 schema/读端兼容)改锚现役单一源;
②写端形态面(落行顺序/行字段回读)随写端消亡,锁退役语义本身。
"""
from __future__ import annotations

# ==================== w146_intention_telemetry ====================
import json

from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    serialize_intention,
)
from sr_od.application.currency_war.sim.engine_p1 import simulate_p1


def test_locked_intention_serializes_phase_and_comp():
    """①锁定局意向序列化:v3_intention.phase='locked' 且 locked_comp=目标名。
    (原经 decisions 行落盘回读;行写入退役后锁序列化纯函数单一源。)"""
    ist = serialize_intention(
        IntentionState(phase='locked', locked_comp='DOT卡芙卡',
                       lock_layer=3, lock_plane=1, lock_round=4))
    assert isinstance(ist, dict)
    assert ist['phase'] == 'locked'
    assert ist['locked_comp'] == 'DOT卡芙卡'
    # 锁定时机遥测字段随行(判读锁定时点的直读维度)
    assert ist['lock_plane'] == 1 and ist['lock_round'] == 4


def test_unlocked_intention_has_explicit_empty_state():
    """②未锁局:v3_intention 是 dict 且 phase='unlocked'(非缺失/非猜);
    非法输入退 None(不是崩)。"""
    ist = serialize_intention(IntentionState())
    assert isinstance(ist, dict)
    assert ist['phase'] == 'unlocked'
    assert ist['locked_comp'] == ''
    assert serialize_intention(None) is None
    assert serialize_intention('junk') is None


def test_sim_ledger_rows_carry_same_key():
    """③sim 账本同构:每轮行有 v3_intention 键(形状锁,不锁锁定分布)。

    默认 pool='auto' 依赖本机生产语料(遥测根 live 流);语料被治理
    清理/新机 checkout 时 auto 池不可用 → 诚实 skip,不是代码红
    (判据 = test_cw_replay_to_md 真档 smoke 同款「本地易失缺席 skip」)。
    """
    import pytest as _pytest

    from sr_od.application.currency_war.sim.pool import DeltaPoolUnavailable
    try:
        res = simulate_p1(seed=20260827, use_refresh=False)
    except DeltaPoolUnavailable as e:
        _pytest.skip(f'本机无生产语料(auto 池不可用): {e}')
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

from sr_od.application.currency_war.operations.cw_op.cw_op_equip_all import (
    _owned_wearable_names,
)
from sr_od.application.currency_war.strategies.impl.cw_strategy import StrategySession


def test_owned_wearable_names_filters_tools() -> None:
    """写端过滤:工具类(冶金炉)剔除,穿戴类保留;未注册名(识别残留)剔除。"""
    hits = [('冶金炉', (1800, 240), 0.9),      # 工具类 → 剔除
            ('财富宝钻', (1850, 240), 0.9),    # 穿戴类 → 保留
            ('未注册残影', (1900, 240), 0.9)]  # 不在 EQUIPMENTS → 剔除
    assert _owned_wearable_names(hits) == ['财富宝钻']


def test_session_last_owned_equips_defaults_empty() -> None:
    """session 新局默认空列表(非 None——下游 list() 拷贝不崩)。"""
    assert StrategySession().last_owned_equips == []


# ==================== w209_equip_telemetry ====================

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_ROOT / 'src'))

from sr_od.application.currency_war.kernel.cw_reconcile import (
    _merge_equips,  # noqa: E402
)
from sr_od.application.currency_war.kernel.cw_state import BenchChar  # noqa: E402


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

from pathlib import Path

from one_dragon.utils import log_utils

_SRC_ROOT = Path('src/sr_od/application/currency_war')


def _src(rel: str) -> str:
    """读源码文本(相对 currency_war 包路径;repo 根运行 pytest)。"""
    return (_SRC_ROOT / rel).read_text(encoding='utf-8')


# ===== 缺口①:decisions.state.equips 落盘链(record 站点)=====


def test_shop_record_site_copies_owned_pool_before_decision_loop() -> None:
    """buy_cards.py 段收尾 equips 补拷(ADR-0517 单动作迁移后 = 段循环后):
    拷贝行存在且在 decide_shop_action 循环之后(装备权重读 state.equips,
    提前拷=改决策行为)。删除波 1:原第三锚 record_decision 调用已退役,
    顺序锁退化为两锚(plan 循环 < 补拷)。"""
    src = _src('operations/cw_op/cw_op_buy_cards.py')
    copy_line = 'state.equips = list(getattr(match.session, \'last_owned_equips\', []) or [])'
    assert copy_line in src, 'buy_cards 段收尾缺 owned 池补拷行(W222 缺口①回归)'
    i_plan = src.index('action = match.strategy.decide_shop_action')
    i_copy = src.index(copy_line)
    assert i_plan < i_copy, '补拷必须在决策循环之后(行为边界)'


def test_director_record_step_is_retired_noop_shell() -> None:
    """cw_screen_prep._record_step = 退役 no-op 壳(删除波 1):方法在场
    (harness 桩面契约)但零落盘;旧「copy→补拷→record」顺序锁随写端消亡。"""
    src = _src('operations/cw_screen/cw_screen_prep.py')
    i_step = src.index('def _record_step')
    assert 'record_decision' not in src[i_step:i_step + 600], \
        '_record_step 壳内不得残留 decisions 写入(防半删)'


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
# 删除波 1:boss_names/难度/词缀的 outcomes 行落盘面(record_outcome)已退役;
# 三态语义(实采保位透传/缺省/空采)现役归宿 = session 直写链
# (briefing_bosses/selected_difficulty/briefing_affixes → 观察半), 行内
# 三键按历史数据只读口径冻结。存档读端兼容锁保留(下方)。

from sr_od.application.currency_war.telemetry.query import read_jsonl
from sr_od.application.currency_war.telemetry.schema import OutcomeRecord

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

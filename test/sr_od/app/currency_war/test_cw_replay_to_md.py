"""对局档案 → markdown 复盘渲染器(tools/cw/replay_to_md.py,op 粒度两遍式)的行为锁。

被测工具 = 主仓 ``tools/cw/replay_to_md.py``(纯 stdlib,零 src 导入),
经 importlib 按路径装载(先例:test_cw_v6_cleanup.py 装载 ab_judge.py)。

锁面五件(渲染缺口清偿 = 084421 复盘完整性审计的渲染缺 R1-R12 逐条销项;
审计出处 = ``.debug/currency_war/deep_review/g_20260907_084421.md`` §C2,
编号以该审计为准):
1. **真档 smoke**:渲染 075840 实机档案不断言数值,只锁结构(四大节 +
   op 记录密度 = 重建 op 数、判定槽密度 = 决策承载 op 数 ×3)。真档是
   本地易失产物:存在性门槛 + 结构断言,数据缺失即 skip,不锁任何会随
   重装配漂移的数值/缺口条目。
2. **op 序列重建锁**(第一遍):备战投影终结切分 / 商店连续帧合并与
   开店步记录 / 零买入段行(phase)识别 / 补给分流+拾取帧合并、节点锁
   分流帧 / 遭遇与投资选卡按「下一个结算收口」归属 / 合成补给行挂靠
   补给 op——全部对合成流行断言,零真实副作用。
3. **op 渲染锁**(第二遍):op 标题四件套(序号/分支/处理类/入口时间戳)、
   逐帧动作与拒因、终结标记、快照分段、判定三槽承载面。
4. **渲染缺口清偿锁**:R1-R12 每条一个合成档案用例钉死渲染面(含补给轮
   has_decision 误报的回归锁),测试名带 R 号供审计对照。
5. **字段缺省容忍 + 缺口零假阳性**:最小合成档案不炸;全字段齐备的合成
   档案(含 op 路径)缺口清单必须为空——假缺口会污染遥测缺口清单的
   判读价值,这条红 = 渲染器在冤枉数据。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[5]
_TOOL_PATH = _REPO_ROOT / 'tools' / 'cw' / 'replay_to_md.py'
#: 实机 live 流根与按局档案根(工具的缺省数据源;2026-09-07 布局裁定
#: .debug/currency_war/telemetry/{live,matches}。本地易失,缺席 skip)
_REAL_REPLAY_DIR = (_REPO_ROOT / '.debug' / 'currency_war' / 'telemetry'
                    / 'live')
_REAL_MATCHES_DIR = (_REPO_ROOT / '.debug' / 'currency_war' / 'telemetry'
                     / 'matches')
_REAL_GAME_ID = 'g_20260907_075840'

_MODULE_NAME = 'cw_replay_to_md_tool'

#: 判定三槽的承载 op 类型(与工具侧 _DECISION_OP_KINDS 同义;此处独立
#: 声明 = 锁的就是这份承载面定义,工具侧改面时本锁应红)
DECISION_OP_KINDS = {'prep', 'shop', 'supply', 'encounter', 'invest', 'env'}

#: 渲染输入的流切片名(合成档案 slices 的键全集)
_STREAM_NAMES = (
    'decisions.jsonl', 'outcomes.jsonl', 'shop_snapshots.jsonl',
    'exogenous.jsonl', 'invest_cards.jsonl', 'spend_ledger.jsonl',
)


def _load_tool() -> Any:
    """按路径装载被测工具(模块级缓存,跨用例只 exec 一次)。"""
    import importlib.util

    if _MODULE_NAME in sys.modules:
        return sys.modules[_MODULE_NAME]
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _TOOL_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# 合成数据工厂(全部零真实副作用:渲染走 render_match,不落真实 .debug)
# ---------------------------------------------------------------------------

#: 统一测试时间基(ISO 前缀;_ts_short 显示 T 后时分秒)
_T0 = '2026-01-01T00:05:00'


def _ts(h: int, m: int, s: int) -> str:
    return f'2026-01-01T{h:02d}:{m:02d}:{s:02d}'


def _unit(char: str, star: int = 1, slot: int = 1, faction: str = '羁绊',
          pos: str = 'back', equips: list[str] | None = None) -> dict[str, Any]:
    return {'slot': slot, 'char_id': char, 'faction': faction, 'star': star,
            'position_pref': pos, 'equips': equips or [], 'is_item_slot': False}


def _state(**over: Any) -> dict[str, Any]:
    """备战帧 state 快照(curated 面 + state 面残余字段各覆盖几格)。"""
    st: dict[str, Any] = {
        'gold': 3, 'gold_readable': True, 'hp': 80, 'hp_readable': True,
        'hp_trusted': True, 'level': 3, 'level_readable': True,
        'xp_progress': [0, 4], 'level_up_cost': 4, 'node_type': 'reward',
        'enemy_difficulty': 117, 'enemy_difficulty_live': True,
        'active_env': '二手市场', 'active_strategies': ['双人舞'],
        'deploy_cap': 5, 'front_max': 4, 'back_max': 6,
        'bench_full_flag': None, 'streak': 1,
        'deployed': [_unit('姬子', pos='front')],
        'bench': [_unit('三月七'), None],
        'shop': [], 'board': {'列车同行': 1}, 'refresh_probs': None,
        'match_type': 'standard',
    }
    st.update(over)
    return st


def _frame(ts: str, plane: int = 1, rnd: int = 1, acts: tuple[Any, ...] = (),
           phase: str = '', run_id: str = 'run_t',
           state: dict[str, Any] | None = None,
           rejects: dict[str, str] | None = None, **kw: Any) -> dict[str, Any]:
    """decisions 帧行(单动作决策循环口径:acts 多为单元素)。"""
    row: dict[str, Any] = {
        'ts': ts, 'plane': plane, 'round_num': rnd, 'run_id': run_id,
        'schema_version': 1, 'phase': phase,
        'actions': [{'__type__': a} if isinstance(a, str) else dict(a)
                    for a in acts],
        'shop_rejects': rejects or {}, 'v3_intention': None,
        'target_comp': '配方甲', 'sess_p1_pair': '',
        'state': state if state is not None else _state(),
    }
    row.update(kw)
    return row


def _paired(rows: list[dict[str, Any]]) -> list[tuple[int, dict[str, Any]]]:
    """帧行 → (切片全局行序, 行) 列表(build_op_sequence 入参口径)。"""
    return list(enumerate(rows))


def _outcome(ts: str, plane: int = 1, rnd: int = 1, **over: Any) -> dict[str, Any]:
    o: dict[str, Any] = {
        'ts': ts, 'plane': plane, 'round_num': rnd, 'run_id': 'run_t',
        'schema_version': 1, 'node_type': '普通战斗', 'comp_tag': '配方甲',
        'killed': True, 'hp_after': 90, 'hp_confidence': 1.0,
        'enemy_hp_after': None, 'damage_dealt': 1000,
        'progress_fill_ratio': None, 'progress_delta': None, 'streak': 1,
        'boss_names': ['Boss甲'], 'enemy_affixes': [], 'source': '',
        'selected_difficulty': 'A3', 'bench_count': 0, 'board_before': {},
        'intentional_fold': False,
    }
    o.update(over)
    return o


def _exog(kind: str, ts: str, **over: Any) -> dict[str, Any]:
    e: dict[str, Any] = {'ts': ts, 'run_id': 'run_t', 'round_num': 1,
                         'kind': kind, 'detail': f'{kind} detail 摘要',
                         'choice': None, 'state_snapshot': {}}
    e.update(over)
    return e


def _archive(slices: dict[str, list[dict[str, Any]]] | None = None,
             **kw: Any) -> dict[str, Any]:
    """合成档案骨架:键齐值空(字段缺省容忍的输入面),按需覆盖。"""
    a: dict[str, Any] = {
        'game_id': 'g_t', 'schema_version': 9,
        'rounds': [], 'segments': [], 'resume_reconciliation': [],
        'hp_events': [], 'hp_pay_defects': [], 'loss_nodes': [],
        'slices': {name: [] for name in _STREAM_NAMES} if slices is None
        else slices,
    }
    a.update(kw)
    return a


def _render(mod: Any, archive: dict[str, Any], tmp_path: Path) -> str:
    """渲染到 tmp(空 obs_conflicts.jsonl:文件在但零行,不产生缺口噪声)。"""
    (tmp_path / 'obs_conflicts.jsonl').write_text('', encoding='utf-8')
    return mod.render_match(archive, tmp_path)


# ---------------------------------------------------------------------------
# 1. 真档 smoke(结构锁,数值零断言)
# ---------------------------------------------------------------------------


class TestSmokeRealArchive:
    """真档 smoke:渲染 075840,只锁结构与密度(纪律:形状锁)。"""

    def test_render_real_archive_structure(self, tmp_path: Path) -> None:
        mod = _load_tool()
        archive_path = _REAL_MATCHES_DIR / f'match_{_REAL_GAME_ID}.json'
        if not archive_path.exists():
            pytest.skip(f'本地易失档案不存在: {archive_path}')
        archive = json.loads(archive_path.read_text(encoding='utf-8'))
        md = mod.render_match(archive, _REAL_REPLAY_DIR)

        assert md.startswith(f'# 货币战争复盘 {_REAL_GAME_ID}')
        for section in ('## 1. 局头', '## 2. 逐 op 复盘(外层循环画面 op 粒度)',
                        '## 3. 全局', '## 4. 本次未能渲染的字段'):
            assert section in md, section
        # op 记录密度:标题数 = 第一遍重建的 op 数(全序,不分段)
        gaps = mod.GapLog()
        streams = mod.collect_streams(archive, _REAL_REPLAY_DIR, None, gaps)
        ops = mod.build_op_sequence(
            streams['decisions'], streams['outcomes'], streams['exogenous'],
            streams['invest_cards'], streams['shop_snapshots'],
            streams['spend_ledger'])
        assert len(ops) > 0
        assert md.count('#### op') == len(ops)
        # 开局段/收口段按数据条件断言(075840 是 v8 旧档:无简报行/环境字段
        # 时开局段合法缺席;收口段跟随 endgame 汇总在场性)
        if any(o['segment'] == 'open' for o in ops):
            assert '### 开局段(局前,非节点)' in md
        if isinstance(archive.get('endgame'), dict):
            assert '### 收口段' in md
        # 判定槽密度:决策承载 op 数 ×3,无决策承载 op(战斗窗/简报/收口)无槽
        n_decision = sum(1 for o in ops if o['kind'] in DECISION_OP_KINDS)
        assert n_decision > 0
        assert md.count(mod.JUDGMENT_SLOTS[0]) == n_decision
        # CLI 路径同源:--out 写 tmp_path(纪律 2:不落真实 .debug)
        out = tmp_path / 'review.md'
        rc = mod.main(['--match', _REAL_GAME_ID, '--out', str(out)])
        assert rc == 0
        assert out.exists() and out.read_text(encoding='utf-8').startswith('# ')

    def test_main_missing_archive_exit_code(self, tmp_path: Path) -> None:
        """CLI 对不存在的档案返回退出码 2(不抛栈,给装配指引)。"""
        mod = _load_tool()
        rc = mod.main(['--match', 'g_no_such_game', '--replay-dir',
                       str(tmp_path)])
        assert rc == 2


# ---------------------------------------------------------------------------
# 2. op 序列重建锁(第一遍;纯函数,合成流行直调)
# ---------------------------------------------------------------------------


class TestOpSequenceRebuild:
    """op 边界重建规则(match-review.md 阶段 2)的确定性实现锁。"""

    def test_prep_ops_split_on_projection_and_battle(self) -> None:
        """备战 op 切分:投影未建模动作(RunDeploy/RunEquip/LevelUp)与出战
        (StartBattle)闭合当前访问;下一个备战帧 = 新一次访问
        (flow/prep_visit.md §1 投影规则 + §3 出战完成态)。

        state 关 active_env:环境 op 不是本锁主角,防它混进序列断言
        (序列契约:帧级 op 之后恒有收口 op)。"""
        mod = _load_tool()
        st = _state(active_env='')
        frames = [
            _frame(_ts(0, 0, 0), acts=['ClickSpheres'], state=st),
            _frame(_ts(0, 0, 3), acts=['RunDeploy'], state=st),
            _frame(_ts(0, 0, 10), acts=['StartBattle'], state=st),
            _frame(_ts(0, 1, 0), acts=['ClickSpheres'], state=st),
            _frame(_ts(0, 1, 4), acts=['LevelUp'], state=st),
        ]
        ops = mod.build_op_sequence(_paired(frames), [], [], [], [], [])
        assert [o['kind'] for o in ops] == ['prep', 'prep', 'prep', 'closure']
        preps = [o for o in ops if o['kind'] == 'prep']
        assert [[g for g, _ in o['frames']] for o in preps] == [[0, 1], [2], [3, 4]]

    def test_shop_visit_groups_consecutive_and_records_open_step(self) -> None:
        """商店访问 op:连续商店帧(含 OpenShop 行)合并一次访问,开店步
        已记录;前后备战帧不并入。"""
        mod = _load_tool()
        st = _state(active_env='')
        frames = [
            _frame(_ts(0, 0, 0), acts=['ClickSpheres'], state=st),
            _frame(_ts(0, 0, 3), acts=['RunDeploy'], state=st),
            _frame(_ts(0, 0, 10), acts=['OpenShop'], state=st),
            _frame(_ts(0, 0, 20), acts=['BuyCard'], rejects={'甲': 'non_line'},
                   state=st),
            _frame(_ts(0, 0, 30), acts=['StartBattle'], state=st),
        ]
        snaps = [{'ts': _ts(0, 0, 15), 'event': 'offer', 'gold': 5,
                  'shop': [{'name': '甲', 'cost': 1, 'star': 1}]}]
        ops = mod.build_op_sequence(_paired(frames), [], [], [], snaps, [])
        assert [o['kind'] for o in ops] == ['prep', 'shop', 'prep', 'closure']
        shop = next(o for o in ops if o['kind'] == 'shop')
        assert [g for g, _ in shop['frames']] == [2, 3]
        assert shop['open_shop_recorded'] is True
        assert len(shop['snapshots']) == 1

    def test_zero_buy_form_row_counts_as_shop_wave(self) -> None:
        """零买入段行(acts=[]、行级 phase 非空)按 phase 识别为商店帧;
        无 OpenShop 行 = 开店通道未记录,入口时间取快照(最早证据)。"""
        mod = _load_tool()
        frames = [
            _frame(_ts(0, 0, 20), acts=[], phase='FORM',
                   rejects={'甲': 'non_line'}, state=_state(active_env='')),
        ]
        snaps = [{'ts': _ts(0, 0, 12), 'event': 'offer', 'gold': 7,
                  'shop': [{'name': '甲', 'cost': 1, 'star': 1}]}]
        ops = mod.build_op_sequence(_paired(frames), [], [], [], snaps, [])
        assert [o['kind'] for o in ops] == ['shop', 'closure']
        op = next(o for o in ops if o['kind'] == 'shop')
        assert op['open_shop_recorded'] is False
        assert op['ts'] == _ts(0, 0, 12), '入口时间应为快照 ts(最早证据)'
        assert len(op['snapshots']) == 1

    def test_supply_pair_merges_with_detour_key(self) -> None:
        """补给 op:分流帧(detour)与拾取帧(pick)合并一个 op;节点键锁
        分流帧(拾取帧轮号有跨轮漂移先例,084421 审计 S5)。"""
        mod = _load_tool()
        st = _state(active_env='')
        frames = [
            _frame(_ts(0, 0, 0), phase='supply_detour', plane=1, rnd=5,
                   state=st),
            _frame(_ts(0, 0, 12), phase='supply_pick', plane=1, rnd=6,
                   state=st),
        ]
        ops = mod.build_op_sequence(_paired(frames), [], [], [], [], [])
        assert [o['kind'] for o in ops] == ['supply', 'closure']
        assert ops[0]['key'] == (1, 5)
        assert [g for g, _ in ops[0]['frames']] == [0, 1]

    def test_encounter_and_invest_attribute_to_next_closure(self) -> None:
        """遭遇/投资选卡 op 无 decisions 行,节点归属 = 下一个结算收口行
        (节点窗口 = 上一次结算到本次结算之间)。"""
        mod = _load_tool()
        outcomes = [
            _outcome(_ts(0, 0, 8), plane=1, rnd=1),
            _outcome(_ts(0, 0, 40), plane=1, rnd=2),
        ]
        exog = [_exog('event_choice', _ts(0, 0, 20),
                      choice={'event': 'encounter', 'n_options': 2,
                              'options': [{'difficulty': 1, 'rewards': ['金币']},
                                          {'difficulty': 2, 'rewards': ['经验']}],
                              'pick_idx': 0, 'reason': 'r:x'})]
        invest = [
            {'ts': _ts(0, 0, 30), 'run_id': 'run_t', 'kind': 'strategy',
             'idx': i, 'name': n, 'chosen': i == 1, 'effect_text': 'e'}
            for i, n in enumerate(('甲卡', '乙卡', '丙卡'))]
        ops = mod.build_op_sequence(_paired([]), outcomes, exog, invest, [], [])
        kinds = {o['kind']: o for o in ops}
        assert kinds['encounter']['key'] == (1, 2)
        assert kinds['invest']['key'] == (1, 2)
        assert len(kinds['invest']['invest_rows']) == 3

    def test_battle_ops_skip_synthetic_and_attach_supply(self) -> None:
        """战斗窗 op = 每个非合成 outcome 行一个;合成补给行(source=
        synthetic_supply)不另立 op,挂靠最近补给 op(陈旧快照口径)。"""
        mod = _load_tool()
        frames = [
            _frame(_ts(0, 0, 0), phase='supply_detour', plane=1, rnd=5),
            _frame(_ts(0, 0, 12), phase='supply_pick', plane=1, rnd=6),
        ]
        synthetic = _outcome(_ts(0, 0, 15), plane=1, rnd=6,
                             source='synthetic_supply',
                             supply_pick={'char': '翡翠', 'equip': '红钻',
                                          'refreshed': False, 'gold': 14,
                                          'options': [], 'n_options': 5})
        normal = _outcome(_ts(0, 1, 0), plane=1, rnd=6)
        ops = mod.build_op_sequence(_paired(frames), [normal, synthetic],
                                    [], [], [], [])
        kinds = [o['kind'] for o in ops]
        assert kinds.count('battle') == 1
        supply = next(o for o in ops if o['kind'] == 'supply')
        assert supply['supply_outcome'] is synthetic


# ---------------------------------------------------------------------------
# 3. op 渲染锁(第二遍)
# ---------------------------------------------------------------------------


class TestOpRendering:
    """op 记录渲染面:标题四件套 / 入口观察 / 决策循环 / 终结 / 槽承载。"""

    def _prep_archive(self) -> dict[str, Any]:
        # state 关 active_env:环境 op 非本锁主角,槽计数只应看到备战 op
        frame = _frame(_T0, acts=['ClickSpheres'],
                       state=_state(active_env=''))
        return _archive(
            slices=_archive()['slices'] | {
                'decisions.jsonl': [frame],
                'outcomes.jsonl': [_outcome(_ts(0, 6, 0))],
            },
            rounds=[{'plane': 1, 'round': 1, 'node_type': '普通战斗',
                     'gold': 3, 'gold_readable': True, 'actions': [],
                     'evidence': []}],
            endgame={'result': 'win', 'abandoned': False, 'plane_reached': 1,
                     'rounds_survived': 1, 'final_hp': 90, 'difficulty': 'A3'})

    def test_prep_op_full_render_face(self, tmp_path: Path) -> None:
        """备战 op:标题(序号/分支/处理类/入口时间戳/帧区间)+ 入口观察
        (state 面)+ 逐帧决策循环 + 终结标记 + 判定三槽;战斗窗无槽。"""
        mod = _load_tool()
        md = _render(mod, self._prep_archive(), tmp_path)

        assert '#### op① 分支1 备战 → CwScreenPrep.execute(00:05:00,帧 [00])' in md
        # 终结:无终结动作、下一调度是战斗窗 → 交回外循环重识别
        assert '- 终结:访问交回外循环重识别(下一调度:战斗窗/结算)' in md
        assert '- 决策循环:' in md and '帧 [00] 00:05:00 → #1 ClickSpheres' in md
        # 槽承载:备战 1 个 ×3 槽,战斗窗不承载
        assert md.count(mod.JUDGMENT_SLOTS[0]) == 1
        battle_i = md.index('#### op② 战斗窗 战斗窗/结算 → CwScreenBattleWait')
        slot_i = md.index(mod.JUDGMENT_SLOTS[0])
        assert slot_i < battle_i, '备战 op 的槽应先于战斗窗 op 出现'
        assert '| 结算判定 | 胜(killed) |' in md

    def test_shop_op_waves_per_frame_rejects_spend(self, tmp_path: Path) -> None:
        """商店 op:快照分段(offer/refresh)+ 逐帧拒因 + 金账对拍 +
        CloseShop 终结标记。"""
        mod = _load_tool()
        frames = [
            _frame(_ts(0, 0, 10), acts=['OpenShop']),
            _frame(_ts(0, 0, 20), acts=['BuyCard'],
                   rejects={'甲': 'non_line', '乙': 'owned'}),
            _frame(_ts(0, 0, 40), acts=['BuyCard', 'RefreshShop'],
                   rejects={'丙': 'transition_char'}),
        ]
        snaps = [
            {'ts': _ts(0, 0, 12), 'event': 'offer', 'gold': 15,
             'shop': [{'name': '甲', 'cost': 1, 'star': 1, 'faction': '羁绊'},
                      {'name': '乙', 'cost': 2, 'star': 2, 'faction': '羁绊'}],
             'rho_obs': {'systems': {'列车同行': 1}, 'pair': '', 'n_shop': 2}},
            {'ts': _ts(0, 0, 35), 'event': 'refresh', 'gold': 13, 'shop': []},
            {'ts': _ts(0, 0, 42), 'event': 'offer', 'gold': 13,
             'shop': [{'name': '丙', 'cost': 3, 'star': 1, 'faction': '羁绊'}]},
        ]
        spend = [{'ts': _ts(0, 0, 50), 'run_id': 'run_t', 'plane': 1,
                  'round_num': 1, 'boundary': 'closed', 'duration_s': 41.0,
                  'gold_before': 15, 'gold_before_trusted': True,
                  'gold_close': 12, 'gold_close_trusted': True,
                  'detail': '买牌 plan 买2张 刷1次'}]
        archive = _archive(
            slices=_archive()['slices'] | {
                'decisions.jsonl': frames,
                'shop_snapshots.jsonl': snaps,
                'spend_ledger.jsonl': spend,
            },
            rounds=[{'plane': 1, 'round': 1, 'node_type': '奖励', 'gold': 12,
                     'gold_readable': True, 'actions': [], 'evidence': []}])
        md = _render(mod, archive, tmp_path)

        assert '分支0n 备战-开商店 → CwScreenPrep.visit_open_shop' in md
        assert '段1(offer@00:00:12) 店面:甲1金、乙2金2★' in md
        assert '刷新@00:00:35' in md
        assert '段2(offer@00:00:42) 店面:丙3金' in md
        assert '拒因(帧 [01]):甲=non_line、乙=owned' in md
        assert '拒因(帧 [02]):丙=transition_char' in md
        assert '- 终结:CloseShop(结构性不入行,收店)' in md
        assert '金账对拍(spend_ledger):[closed] 41.0s 金15(可信)→12(可信)' in md

    def test_shop_without_open_step_annotated(self, tmp_path: Path) -> None:
        """开店通道未记录(S11 同型:11/14 访问无 OpenShop 行)→ 标题与
        入口观察双标注,防把快照起点误读成决策行。"""
        mod = _load_tool()
        frames = [_frame(_ts(0, 0, 20), acts=['BuyCard'],
                         rejects={'甲': 'non_line'})]
        snaps = [{'ts': _ts(0, 0, 12), 'event': 'offer', 'gold': 7,
                  'shop': [{'name': '甲', 'cost': 1, 'star': 1}]}]
        archive = _archive(
            slices=_archive()['slices'] | {
                'decisions.jsonl': frames, 'shop_snapshots.jsonl': snaps},
            rounds=[{'plane': 1, 'round': 1, 'node_type': '奖励', 'gold': 6,
                     'gold_readable': True, 'actions': [], 'evidence': []}])
        md = _render(mod, archive, tmp_path)

        assert '开店通道未记录' in md
        assert '(00:00:12,帧 [00]' in md, '入口时间应取快照 ts'

    def test_supply_op_pick_render_and_no_false_gap(self, tmp_path: Path) -> None:
        """补给 op:分流帧入口 + 拾取 N 选 1 + 合成结算行注;补给轮
        (actions=[] 带 decision_detail)不再产生 rounds[].actions 误报缺口
        (前版 has_decision 判据与 gaps.miss 自相矛盾)。"""
        mod = _load_tool()
        frames = [
            _frame(_ts(0, 0, 0), plane=1, rnd=5, phase='supply_detour'),
            _frame(_ts(0, 0, 12), plane=1, rnd=6, phase='supply_pick'),
        ]
        synthetic = _outcome(_ts(0, 0, 15), plane=1, rnd=6,
                             source='synthetic_supply',
                             supply_pick={'char': '翡翠', 'equip': '红钻',
                                          'has_diamond': True,
                                          'refreshed': True, 'gold': 14,
                                          'n_options': 5,
                                          'options': [
                                              {'char': '甲', 'equip': 'X',
                                               'has_diamond': False},
                                              {'char': '翡翠', 'equip': '红钻',
                                               'has_diamond': True}]})
        archive = _archive(
            slices=_archive()['slices'] | {
                'decisions.jsonl': frames,
                'outcomes.jsonl': [synthetic],
            },
            # 旧误报形态:补给轮 decision_detail 在场而 actions 空
            rounds=[{'plane': 1, 'round': 5, 'node_type': 'supply',
                     'gold': 22, 'gold_readable': True, 'actions': [],
                     'decision_detail': {'shop_rejects': {}},
                     'evidence': []}])
        md = _render(mod, archive, tmp_path)

        assert '### 1. P1·R5(补给)' in md, '节点键应锁分流帧(r5 非 pick 帧的 r6)'
        assert '分支0e1 补给 → CwScreenSupplyNode' in md
        assert '拾取 5 选 1:' in md and '→ 取 翡翠+红钻(带钻石标)' in md
        assert 'refreshed=是(刷过 1 次)' in md
        assert '结算行:source=synthetic_supply' in md
        assert '`rounds[].actions`' not in md.split('## 4.')[-1], \
            '补给轮结构性为空不是遥测缺(误报回归锁)'

    def test_encounter_briefing_env_invest_ops(self, tmp_path: Path) -> None:
        """四类无 decisions 行的 op:遭遇(event_choice)/BOSS 简报/投资环境
        (state.active_env)/投资选卡(invest_cards),各有独立记录与三槽。"""
        mod = _load_tool()
        frames = [_frame(_T0, acts=['ClickSpheres'], state=_state())]
        outcomes = [_outcome(_ts(0, 6, 0))]
        exog = [
            _exog('briefing', _ts(0, 0, 30),
                  detail='affixes=[词缀甲] bosses=[Boss甲] difficulty=108'),
            _exog('event_choice', _ts(0, 1, 0),
                  choice={'event': 'encounter', 'n_options': 2,
                          'options': [{'difficulty': 1, 'rewards': ['金币']},
                                      {'difficulty': 2, 'rewards': ['经验']}],
                          'pick_idx': 0, 'reason': 'e3:reward_unmodeled'}),
        ]
        invest = [{'ts': _ts(0, 2, 0), 'run_id': 'run_t', 'kind': 'strategy',
                   'idx': i, 'name': n, 'chosen': i == 1, 'effect_text': '效果'}
                  for i, n in enumerate(('甲卡', '双人舞', '丙卡'))]
        archive = _archive(
            slices=_archive()['slices'] | {
                'decisions.jsonl': frames, 'outcomes.jsonl': outcomes,
                'exogenous.jsonl': exog, 'invest_cards.jsonl': invest},
            rounds=[{'plane': 1, 'round': 1, 'node_type': '遭遇', 'gold': 3,
                     'gold_readable': True, 'actions': [], 'evidence': []}])
        md = _render(mod, archive, tmp_path)

        assert '分支0p BOSS 简报 → CwScreenBossBriefing' in md
        assert 'affixes=[词缀甲] bosses=[Boss甲] difficulty=108' in md
        assert '分支0s 投资环境 → CwScreenInvestEnv' in md
        assert '环境 二手市场' in md
        assert '分支0e 投资策略三选一 → CwScreenInvestStrategy' in md
        assert '双人舞' in md and '✓已选' in md
        assert '分支0c 遭遇事件选择 → CwScreenEncounter' in md
        assert '难度1=金币 / 难度2=经验' in md
        assert 'pick=idx0 · reason=e3:reward_unmodeled' in md
        # encounter 的 event_choice 行被入口观察消费,不再重复为外生行
        assert '外生行 event_choice' not in md

    def test_exogenous_annotation_lines(self, tmp_path: Path) -> None:
        """非 op 外生行(node_enter/sell_income/level_up/resumed_match)挂靠
        时间最近 op 渲染,全量可见不丢行。"""
        mod = _load_tool()
        frames = [_frame(_T0, acts=['LevelUp'], state=_state())]
        outcomes = [_outcome(_ts(0, 6, 0))]
        exog = [
            _exog('node_enter', _ts(0, 6, 0), detail='battle_done:普通战斗'),
            _exog('sell_income', _ts(0, 5, 10),
                  choice={'slot': 3, 'char': '丹恒·腾荒', 'gold_delta': 2}),
            _exog('level_up', _ts(0, 5, 2), detail='level 4->5'),
            _exog('resumed_match', _ts(0, 5, 55), detail='P1-r6 残局续跑'),
        ]
        archive = _archive(
            slices=_archive()['slices'] | {
                'decisions.jsonl': frames, 'outcomes.jsonl': outcomes,
                'exogenous.jsonl': exog},
            rounds=[{'plane': 1, 'round': 1, 'node_type': '普通战斗',
                     'gold': 3, 'gold_readable': True, 'actions': [],
                     'evidence': []}])
        md = _render(mod, archive, tmp_path)

        for kind in ('node_enter', 'sell_income', 'level_up', 'resumed_match'):
            assert f'外生行 {kind}@' in md, kind
        assert '丹恒·腾荒 +2金' in md

    def test_terminal_closure_row_typed_not_battle_verdict(
            self, tmp_path: Path) -> None:
        """收口终局行(T-185)显示面分型:killed=False 是对局级终了真值非
        战斗结算——fill 轨迹胜负列与战斗窗观察面「结算判定」均专项标注
        「收口(未通关·stopped)」,禁渲染成战斗败轮(旧法走 killed is False
        → '败')或「存活(killed=False)」;op 标题时间戳标签用「收口」替代
        「结算」(先例:补给合成行「合成快照非结算事件」专项标注)。"""
        mod = _load_tool()
        frame = _frame(_ts(0, 0, 0), plane=1, rnd=3)
        terminal = _outcome(_ts(0, 6, 0), plane=1, rnd=3,
                            source='terminal_closure', node_type='',
                            killed=False, hp_after=None, hp_confidence=0.0,
                            match_result='stopped', streak=None,
                            damage_dealt=None)
        archive = _archive(
            slices=_archive()['slices'] | {
                'decisions.jsonl': [frame],
                'outcomes.jsonl': [terminal],
            },
            rounds=[], endgame={'result': 'stopped', 'abandoned': False,
                                'plane_reached': 1, 'rounds_survived': 3,
                                'final_hp': 55, 'difficulty': 'A3'})
        md = _render(mod, archive, tmp_path)

        # fill 轨迹行:胜负列 = 收口标注,禁「败」
        fill_row = next(ln for ln in md.splitlines()
                        if ln.startswith('| P1·R3 '))
        assert '收口(未通关·stopped)' in fill_row
        assert '败' not in fill_row
        # 战斗窗观察面「结算判定」:同款收口标注(非战斗结算显式声明)
        assert ('| 结算判定 | 收口(未通关·stopped)·非战斗结算 |' in md)
        # op 标题:时间戳标签「收口」(「(收口 」形态,替代战斗行的「(结算 」)
        assert '(收口 00:06:00' in md
        # 正常备战行标题不带结算/收口标签(时间戳裸形态,对照不受影响)
        assert '(00:00:00,帧 [00]' in md


# ---------------------------------------------------------------------------
# 4. 渲染缺口清偿锁(084421 审计 R1-R12 逐条 + 误报回归)
# ---------------------------------------------------------------------------


class TestRenderGapRemediation:
    """每条渲染缺一个合成档案用例,钉死「数据在档案 → 渲染稿可见」。"""

    def test_r1_state_face_rendered(self, tmp_path: Path) -> None:
        """R1:decisions 帧 state 字段面此前零消费——环境/敌难度/升级缺口/
        cap/席满等复盘关键事实必须进入口观察;curated 之外的字段进 state 面。"""
        mod = _load_tool()
        frame = _frame(_T0, acts=['ClickSpheres'], state=_state())
        archive = _archive(slices=_archive()['slices'] |
                           {'decisions.jsonl': [frame]})
        md = _render(mod, archive, tmp_path)

        for bit in ('环境 二手市场', '敌难度 117(live)', 'cap 5(前4/后6)',
                    '等级 3(xp 0/4,升级 4金)', '席满 —', '连胜 1',
                    '持卡 双人舞', '- state 面:', 'match_type=standard',
                    '备战栏 三月七1★'):
            assert bit in md, bit

    def test_r2_exogenous_rows_rendered(self, tmp_path: Path) -> None:
        """R2:exogenous 流此前零渲染(briefing/sell_income/level_up/
        node_enter/event_choice/resumed_match)——现以独立 op + 挂靠注记
        全量可见(独立 op 面见 TestOpRendering,此处锁 kind 全覆盖)。"""
        mod = _load_tool()
        # 夹具带一帧备战 op:注记行挂靠时间最近 op 才渲染(无 op 时走
        # 「未挂靠」防丢行兜底,形态不同,那是收口段的另一条渲染路径)
        frame = _frame(_T0, acts=['ClickSpheres'])
        outcome = _outcome(_ts(0, 6, 0))
        exog = [_exog(k, _ts(0, 5, s), detail=f'{k} 明细')
                for k, s in (('briefing', 0), ('node_enter', 10),
                             ('sell_income', 20), ('level_up', 30),
                             ('resumed_match', 40))]
        archive = _archive(slices=_archive()['slices'] |
                           {'decisions.jsonl': [frame],
                            'outcomes.jsonl': [outcome],
                            'exogenous.jsonl': exog})
        md = _render(mod, archive, tmp_path)

        assert '分支0p BOSS 简报' in md
        for kind in ('node_enter', 'sell_income', 'level_up', 'resumed_match'):
            assert f'外生行 {kind}@' in md, kind

    def test_r3_spend_ledger_on_shop_op(self, tmp_path: Path) -> None:
        """R3:spend_ledger 此前只在零决策轮内联——商店访问的金账对拍必须
        出现在该访问 op 内(渲染面见 TestOpRendering.test_shop_op_*;此处锁
        挂靠正确性:单元落在窗口内才出现)。"""
        mod = _load_tool()
        frames = [_frame(_ts(0, 0, 10), acts=['OpenShop']),
                  _frame(_ts(0, 0, 20), acts=['BuyCard'])]
        snaps = [{'ts': _ts(0, 0, 12), 'event': 'offer', 'gold': 15,
                  'shop': [{'name': '甲', 'cost': 1, 'star': 1}]}]
        spend_in = [{'ts': _ts(0, 0, 25), 'run_id': 'run_t', 'plane': 1,
                     'round_num': 1, 'boundary': 'closed', 'duration_s': 15.0,
                     'gold_before': 15, 'gold_before_trusted': True,
                     'gold_close': 12, 'gold_close_trusted': True,
                     'detail': '买牌 plan 买1张'}]
        archive = _archive(slices=_archive()['slices'] | {
            'decisions.jsonl': frames, 'shop_snapshots.jsonl': snaps,
            'spend_ledger.jsonl': spend_in})
        md = _render(mod, archive, tmp_path)
        assert '金账对拍(spend_ledger):[closed] 15.0s 金15(可信)→12(可信)' in md

    def test_r4_battle_from_outcomes_slice(self, tmp_path: Path) -> None:
        """R4:战斗/结算此前只读 rounds[].outcome 内嵌面——现以 outcomes
        切片行为一体 op 的数据源,轮行无 outcome 也有战斗窗记录。"""
        mod = _load_tool()
        archive = _archive(
            slices=_archive()['slices'] |
            {'outcomes.jsonl': [_outcome(_ts(0, 6, 0))]},
            rounds=[{'plane': 1, 'round': 1, 'node_type': '普通战斗',
                     'gold': 3, 'gold_readable': True, 'actions': [],
                     'evidence': []}])  # 轮行刻意不带 outcome 键
        md = _render(mod, archive, tmp_path)
        assert 'CwScreenBattleWait' in md
        assert '| 结算判定 | 胜(killed) |' in md

    def test_r5_fill_metrics_and_fill_traj(self, tmp_path: Path) -> None:
        """R5:progress_fill_ratio 等结算细字段此前不渲染——「打赢但进度
        填不满」死因主线必须在战斗窗 op 与全局 fill 轨迹两处可见。"""
        mod = _load_tool()
        outcome = _outcome(_ts(0, 6, 0), progress_fill_ratio=0.25,
                           progress_delta=2, damage_dealt=1000,
                           damage_base=800, damage_unfinished_progress=200,
                           damage_breakdown_visible=True, bench_count=3,
                           source='settlement')
        archive = _archive(
            slices=_archive()['slices'] | {'outcomes.jsonl': [outcome]},
            rounds=[{'plane': 1, 'round': 1, 'node_type': '普通战斗',
                     'gold': 3, 'gold_readable': True, 'actions': [],
                     'evidence': []}])
        md = _render(mod, archive, tmp_path)
        assert '| 进度 fill | 0.25 |' in md
        assert '| progress_delta | 2 |' in md
        assert '拆解 基础 800+未完成 200' in md
        assert '| 备战席(战后) | 3 |' in md
        assert '### 进度 fill 轨迹' in md
        assert '| P1·R1 | 普通战斗 | 胜 | 0.25 | 2 | 1,000 |' in md

    def test_r6_endgame_final_snapshot(self, tmp_path: Path) -> None:
        """R6:endgame.final_snapshot 此前零消费——终局板面/板凳/terminal
        必须在收口段可见。"""
        mod = _load_tool()
        archive = _archive(endgame={
            'result': 'loss', 'abandoned': False, 'plane_reached': 2,
            'rounds_survived': 7, 'final_hp': 0, 'difficulty': '',
            'final_snapshot': {
                'ts': _ts(1, 0, 0), 'source': 'last_decision_frame',
                'closure': 'start_battle', 'gold': 47, 'level': 7,
                'board': {'列车同行': 3},
                'terminal': {'deployed_count': 7, 'bench_count': 8,
                             'equips_worn': 8, 'equips_owned': 2},
                'deployed': [_unit('姬子', pos='front')],
                'bench': [None]}})
        md = _render(mod, archive, tmp_path)
        assert '终局面面(final_snapshot@01:00:00' in md
        assert '仓位(终态):场7/备8/穿8/持2' in md
        assert '板面:{"列车同行":3}' in md

    def test_r7_segment_list_code_commit_notes(self, tmp_path: Path) -> None:
        """R7:段列表此前不含 code_commit/notes——跨段双码与停局原因必须
        在段表可见(局头 strategy_version 只记末段)。"""
        mod = _load_tool()
        archive = _archive(segments=[
            {'run_id': 'run_a', 'first_frame': [1, 1],
             'summary': {'result': 'stopped', 'rounds_survived': 6,
                         'final_hp': 88, 'code_commit': 'bdd9487e',
                         'notes': 'stopped:operation 收口(W75)'}},
            {'run_id': 'run_b', 'first_frame': [1, 6],
             'summary': {'result': 'loss', 'rounds_survived': 7,
                         'final_hp': 0, 'code_commit': '6aa2eb62',
                         'notes': 'auto'}}])
        md = _render(mod, archive, tmp_path)
        assert 'bdd9487e' in md and '6aa2eb62' in md
        assert 'stopped:operation 收口(W75)' in md

    def test_r8_opening_ts_and_env(self, tmp_path: Path) -> None:
        """R8:开局面投资卡表此前无 ts——选卡时点必须可见(对应轮的选卡 op
        见逐 op 复盘);环境结果由投资环境 op 承载(见 TestOpRendering)。"""
        mod = _load_tool()
        archive = _archive(opening={'difficulty': 'A3', 'invest_cards': [
            {'kind': 'strategy', 'idx': 0, 'ts': _ts(0, 4, 0),
             'name': '卡名', 'chosen': True, 'effect_text': '效果'}],
            'chosen_strategies': ['卡名']})
        md = _render(mod, archive, tmp_path)
        assert '### 开局面' in md
        assert f'| strategy | 0 | {_ts(0, 4, 0)} | 卡名 | 是 |' in md

    def test_r9_v3_lock_chain(self, tmp_path: Path) -> None:
        """R9:v3_intention 此前只渲染 phase/locked——锁线证据链(lock_layer/
        lock_plane/lock_round/last_event)必须在入口观察可见。"""
        mod = _load_tool()
        v3 = {'phase': 'locked', 'locked_comp': '列车同行', 'lock_layer': 3,
              'lock_plane': 2, 'lock_round': 1, 'forced': False,
              'last_event': 'lock:列车同行'}
        frame = _frame(_T0, acts=['ClickSpheres'], v3_intention=v3)
        archive = _archive(slices=_archive()['slices'] |
                           {'decisions.jsonl': [frame]})
        md = _render(mod, archive, tmp_path)
        assert '意向 (locked;列车同行;锁 层3/P2R1;last_event=lock:列车同行)' in md

    def test_r10_per_frame_rejects(self, tmp_path: Path) -> None:
        """R10:shop_rejects 此前只取末帧聚合——多波访问逐帧拒因必须各自
        可见(首段拒因不丢、残留不误标)。逐帧口径渲染面亦见
        TestOpRendering.test_shop_op_*。"""
        mod = _load_tool()
        frames = [
            _frame(_ts(0, 0, 10), acts=['BuyCard'],
                   rejects={'甲': 'transition_char'}),
            _frame(_ts(0, 0, 30), acts=['BuyCard'], rejects={'乙': 'non_line'}),
        ]
        archive = _archive(slices=_archive()['slices'] |
                           {'decisions.jsonl': frames})
        md = _render(mod, archive, tmp_path)
        assert '拒因(帧 [00]):甲=transition_char' in md
        assert '拒因(帧 [01]):乙=non_line' in md

    def test_r11_upgrade_count_both_channels(self, tmp_path: Path) -> None:
        """R11:强化计数此前只数 LevelUpShop+ClickSpheres——备战 LevelUp
        (买经验升 6 渲染成 ×0 的矛盾)必须计入。轮级事实随节点组渲染,
        故夹具带一帧使分组存在。"""
        mod = _load_tool()
        frame = _frame(_T0, plane=1, rnd=6, acts=['ClickSpheres'])
        archive = _archive(
            slices=_archive()['slices'] | {'decisions.jsonl': [frame]},
            rounds=[{
                'plane': 1, 'round': 6, 'node_type': '普通战斗', 'gold': 0,
                'gold_readable': True, 'evidence': [],
                'actions': [{'__type__': 'LevelUp'},
                            {'__type__': 'LevelUpShop'},
                            {'__type__': 'ClickSpheres'},
                            {'__type__': 'OpenBox'}]}])
        md = _render(mod, archive, tmp_path)
        assert '**强化动作计数**(升级含店内 LevelUpShop 与备战 LevelUp 两通道)' \
            in md
        assert '升级 店内×1+备战×1' in md
        assert '点经验×1' in md and '开箱×1' in md

    def test_r12_bench_none_is_empty_slot(self, tmp_path: Path) -> None:
        """R12:固定槽位列表的 None 此前渲染成「? (非 dict 行: None)」噪声
        ——空槽合法语义必须渲染 (空槽)。"""
        mod = _load_tool()
        archive = _archive(endgame={
            'result': 'loss', 'abandoned': False, 'plane_reached': 2,
            'rounds_survived': 7, 'final_hp': 0, 'difficulty': '',
            'final_snapshot': {'ts': _ts(1, 0, 0), 'source': 'x',
                               'closure': 'start_battle', 'gold': 1,
                               'level': 6, 'board': {},
                               'terminal': {'deployed_count': 1,
                                            'bench_count': 1,
                                            'equips_worn': 0,
                                            'equips_owned': 0},
                               'deployed': [], 'bench': [None, None]}})
        md = _render(mod, archive, tmp_path)
        assert '| — | (空槽) |' in md
        assert '非 dict 行: None' not in md

    def test_supply_round_no_false_gap_regression(self, tmp_path: Path) -> None:
        """误报回归锁:补给轮 has_decision(decision_detail 在场)与
        _action_table 空 actions 记缺的自相矛盾——op 粒度重建后补给轮不产生
        任何 rounds[].actions 缺口(主体锁见
        TestOpRendering.test_supply_op_pick_render_and_no_false_gap,此处从
        缺口清单面再钉一次)。"""
        mod = _load_tool()
        frames = [_frame(_ts(0, 0, 0), phase='supply_detour'),
                  _frame(_ts(0, 0, 12), phase='supply_pick')]
        archive = _archive(
            slices=_archive()['slices'] | {'decisions.jsonl': frames},
            rounds=[{'plane': 1, 'round': 5, 'node_type': 'supply',
                     'gold': 22, 'gold_readable': True, 'actions': [],
                     'decision_detail': {'shop_rejects': {}},
                     'evidence': []}])
        md = _render(mod, archive, tmp_path)
        assert '`rounds[].actions`' not in md.split('## 4.')[-1]


# ---------------------------------------------------------------------------
# 4b. cw4_counters 判读可见性(语义出处 = retirement.md §3 定谳落码形态:
# 流载体退役,局终级全键聚合改由局终域行载荷 MatchFinal.cw4_counters 携带)
# ---------------------------------------------------------------------------


def _endgame_with_cw4(cw4: Any) -> dict[str, Any]:
    """新档案收口面骨架:endgame.match_final.final.cw4_counters 显影位
    (局终行载荷透传,装配端纯读派生;None=无策略载体,{}=零计数)。"""
    return {'result': 'loss', 'abandoned': False, 'plane_reached': 1,
            'rounds_survived': 2, 'final_hp': 0, 'difficulty': 'A3',
            'match_final': {'final': {'final_type': 'loss',
                                      'cw4_counters': cw4}}}


class TestCw4CountersCarrierVisibility:
    """cw4_counters 判读可见性(cw4 流退役后):新档案顶层键已拆,渲染
    回落 endgame.match_final.final.cw4_counters 显影位。语义出处(持久
    索引,纪律 7)= docs/develop/sr_od/application/currency_war/
    game_state/retirement.md §3「定谳落码形态」:键收编归策略 state 容器,
    流载体退役,局终级全键聚合改由局终域行载荷 ``MatchFinal.cw4_counters``
    携带。锁红时该重推的语义 = 「局终快照→档案→复盘渲染」可见性链(新
    显影位曾在判读工具零读者 = 断链事故形态);旧档案顶层键渲染路径不变
    (存量只读,出处 = 同 §3 存量兼容口径)。"""

    def test_new_archive_renders_from_match_final(self, tmp_path: Path) -> None:
        """新档案:顶层无键、显影位有计数 → 分键统计照渲染,缺口清单
        零 cw4 条目(可见性链接通的主锁)。"""
        mod = _load_tool()
        archive = _archive(endgame=_endgame_with_cw4({
            'shop_churn_pair_buy': 3, 'advisor_bloodline_armed': 1}))
        md = _render(mod, archive, tmp_path)
        assert 'shop_churn_pair_buy: 3' in md
        assert 'advisor_bloodline_armed: 1' in md
        assert 'armed 与拒因分键统计' in md
        assert '`cw4_counters' not in md.split('## 4.')[-1]

    def test_new_archive_none_carrier_honest_missing(self, tmp_path: Path) -> None:
        """新档案:显影位 None(局终行无策略载体,诚实缺省)→ 缺口如实
        记录,不静默留白也不误报成旧流缺口。"""
        mod = _load_tool()
        archive = _archive(endgame=_endgame_with_cw4(None))
        md = _render(mod, archive, tmp_path)
        assert '`cw4_counters' in md.split('## 4.')[-1]

    def test_new_archive_zero_count_form_no_gap(self, tmp_path: Path) -> None:
        """新档案:显影位 {} = 局内真实零计数(与 None 分型)→ 不产缺口。"""
        mod = _load_tool()
        archive = _archive(endgame=_endgame_with_cw4({}))
        md = _render(mod, archive, tmp_path)
        assert '局内真实零计数' in md
        assert '`cw4_counters' not in md.split('## 4.')[-1]

    def test_new_archive_missing_match_final_structure(self, tmp_path: Path) -> None:
        """新档案:endgame 在而 match_final 缺(装配残缺形态)→ 回落取
        不到,缺口如实记录,渲染不炸。"""
        mod = _load_tool()
        archive = _archive(endgame={'result': 'loss', 'abandoned': False})
        md = _render(mod, archive, tmp_path)
        assert 'armed 与拒因分键统计' in md
        assert '`cw4_counters' in md.split('## 4.')[-1]

    def test_old_archive_top_level_key_still_rendered(self, tmp_path: Path) -> None:
        """旧档案:顶层流装配键(存量只读)优先,渲染路径不变。"""
        mod = _load_tool()
        archive = _archive(cw4_counters={'advisor_armed': 2})
        md = _render(mod, archive, tmp_path)
        assert 'advisor_armed: 2' in md
        assert '`cw4_counters' not in md.split('## 4.')[-1]


# ---------------------------------------------------------------------------
# 5. 字段缺省容忍 + 缺口零假阳性
# ---------------------------------------------------------------------------


def _minimal_archive() -> dict[str, Any]:
    """最小合成档案:除 game_id 外全缺(字段缺省容忍的输入面)。"""
    return {'game_id': 'g_test_min', 'schema_version': 1}


class TestFieldMissingTolerance:
    """字段缺省容忍:缺槽打「(无此数据)」+ 缺口清单,渲染不炸。"""

    def test_minimal_archive_renders_without_raise(self, tmp_path: Path) -> None:
        mod = _load_tool()
        md = _render(mod, _minimal_archive(), tmp_path)

        assert '# 货币战争复盘 g_test_min' in md
        assert mod.MISSING in md
        # 无轮数据且流无决策帧时显式声明,不静默留白
        assert '档案无逐轮数据' in md
        # 缺口清单必须记录顶层缺列
        assert '## 4. 本次未能渲染的字段' in md
        assert '`rounds`' in md
        assert '`endgame`' in md
        # 零轮 → 零判定槽(槽只在 op 记录内)
        assert md.count(mod.JUDGMENT_SLOTS[0]) == 0

    def test_bare_round_renders_no_ops_note(self, tmp_path: Path) -> None:
        """只有轮键的轮行(零决策帧零流行):不出 op 组,但在轮号连续性节
        如实标注「有轮行但无任何 op」——op 粒度渲染不静默吞轮行。"""
        mod = _load_tool()
        archive = _minimal_archive() | {
            'rounds': [{'plane': 1, 'round': 1}],
            'resume_reconciliation': [],
        }
        md = _render(mod, archive, tmp_path)

        assert '有轮行但无任何 op' in md
        assert 'P1·R1' in md
        assert mod.JUDGMENT_SLOTS[0] not in md
        assert mod.MISSING in md


class TestEmptyArchiveGapSummary:
    """空档汇总:空档案缺口节存在;全字段档案缺口为零(零假阳性锁)。"""

    def test_all_empty_archive_has_gap_section(self, tmp_path: Path) -> None:
        mod = _load_tool()
        archive = _minimal_archive() | {
            'rounds': [], 'segments': [], 'resume_reconciliation': [],
            'cw4_counters': {}, 'slices': {},
        }
        md = _render(mod, archive, tmp_path)

        assert '## 4. 本次未能渲染的字段' in md
        assert mod.MISSING in md
        # 「局内真实零计数」分型断言已并
        # TestCw4CountersCarrierVisibility.test_new_archive_zero_count_form_
        # no_gap(纪律 7 同事实择一取超集:回落路径解析+零计数形态一并
        # 覆盖);本处只辖零缺口形态下缺口节标题仍渲染(节形状恒在)。
        assert '`cw4_counters' not in md

    def test_full_archive_zero_false_gaps(self, tmp_path: Path) -> None:
        """全字段齐备的合成档案(含 op 路径:备战/遭遇/投资/战斗/简报/环境/
        收口):缺口清单必须为空。

        这条锁的是缺口追踪器的准确率——任何「数据其实在、渲染器却喊缺」
        的假阳性都会污染真档判读(缺口清单唯一价值 = 差异信噪比)。
        """
        mod = _load_tool()
        frame = _frame(_T0, acts=['ClickSpheres'], state=_state(),
                       target_comp='配方甲')
        outcome = _outcome(_ts(0, 6, 0), progress_fill_ratio=0.5,
                           progress_delta=2, damage_dealt=1000)
        exog = [
            _exog('briefing', _ts(0, 0, 30),
                  detail='affixes=[词缀甲] bosses=[Boss甲] difficulty=108'),
            _exog('event_choice', _ts(0, 4, 0),
                  choice={'event': 'encounter', 'n_options': 2,
                          'options': [{'difficulty': 1, 'rewards': ['金币']},
                                      {'difficulty': 2, 'rewards': ['经验']}],
                          'pick_idx': 0, 'reason': 'r:x'}),
            _exog('node_enter', _ts(0, 6, 0), detail='battle_done:普通战斗'),
            _exog('sell_income', _ts(0, 5, 10),
                  choice={'slot': 1, 'char': '甲', 'gold_delta': 2}),
        ]
        invest = [{'ts': _ts(0, 4, 30), 'run_id': 'run_t', 'kind': 'strategy',
                   'idx': i, 'name': n, 'chosen': i == 0, 'effect_text': '效果'}
                  for i, n in enumerate(('卡名', '乙卡', '丙卡'))]
        archive = {
            'game_id': 'g_test_full', 'schema_version': 9,
            'start_ts': _ts(0, 0, 0), 'end_ts': _ts(1, 0, 0),
            'continuity_note': '',
            'cw4_counters': {'advisor_armed': 2},
            'strategy_version': {'code_commit': 'abc1234',
                                 'registry_fingerprint': 'deadbeef'},
            'segments': [{'run_id': 'run_t', 'first_frame': [1, 1],
                          'summary': {
                              'result': 'win', 'difficulty': 'A3',
                              'rounds_survived': 1, 'final_hp': 90,
                              'gold_trajectory': [10],
                              'comps_committed': ['配方甲'], 'pivot_count': 0,
                              'code_commit': 'abc1234', 'notes': 'auto'}}],
            'resume_reconciliation': [],
            'hp_events': [], 'hp_pay_defects': [], 'loss_nodes': [],
            'opening': {'difficulty': 'A3', 'invest_cards': [
                {'kind': 'strategy', 'idx': 0, 'ts': _ts(0, 4, 30),
                 'name': '卡名', 'chosen': True, 'effect_text': '效果'}],
                'chosen_strategies': ['卡名']},
            'endgame': {'result': 'win', 'abandoned': False,
                        'plane_reached': 1, 'rounds_survived': 1,
                        'final_hp': 90, 'difficulty': 'A3',
                        'final_snapshot': {
                            'ts': _ts(0, 6, 30), 'source': 'last_decision_frame',
                            'closure': 'start_battle', 'gold': 10, 'level': 3,
                            'board': {'羁绊一': 1},
                            'terminal': {'deployed_count': 1, 'bench_count': 1,
                                         'equips_worn': 0, 'equips_owned': 0},
                            'deployed': [_unit('角色甲', pos='front')],
                            'bench': [None]}},
            'rounds': [{'plane': 1, 'round': 1, 'node_type': '普通战斗',
                        'gold': 10, 'gold_readable': True,
                        'actions': [{'__type__': 'ClickSpheres'}],
                        'evidence': []}],
            'slices': {
                'decisions.jsonl': [frame],
                'outcomes.jsonl': [outcome],
                'exogenous.jsonl': exog,
                'invest_cards.jsonl': invest,
                'shop_snapshots.jsonl': [],
                'spend_ledger.jsonl': [],
            },
        }
        md = _render(mod, archive, tmp_path)

        assert '全部字段渲染成功,无遥测缺口。' in md
        assert mod.MISSING not in md
        # op 路径集成:6 类记录在场,判定槽 = 决策承载 op 数(备战+遭遇+
        # 投资+环境 = 4)×3
        for heading in ('分支1 备战 → CwScreenPrep.execute',
                        '分支0c 遭遇事件选择', '分支0e 投资策略三选一',
                        '分支0s 投资环境', '分支0p BOSS 简报',
                        '战斗窗/结算 → CwScreenBattleWait', '局终收口'):
            assert heading in md, heading
        assert md.count(mod.JUDGMENT_SLOTS[0]) == 4
        assert '帧 [00]' in md

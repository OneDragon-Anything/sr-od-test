"""星级抖动门监控脚本锁面(skills/sr-od-dev-currency-war/scripts/cw_star_gate_monitor.py
``analyze_run`` 纯函数 + 模块级契约键)。输入全在内存构造,零文件 IO、不读活 journal
(活 journal 零采新行,采回 / 离槽 / 金币路径分支对任何实现都输出 0,只能用合成
fixture 锁判定分支)。

三条:
1. 契约键交叉锁:脚本三前缀 == kernel/cw_reconcile.py 三个前缀常量(任一侧改措辞
   即红 —— 保旧键是「保旧于随机态基线」违例的筛选键,单向字面量锁会让门侧措辞
   一改就在监控上静默归零);
2. 合成 journal 计数矩阵:剧本与门机制因果一致 —— 直采后字段翻 observation,基线
   保持非随机态时真值回来必先经一帧「登记候选 + 保旧」(产一条基线 observation 的
   保旧行)再采新,采回落在第 ≥ 3 个该域 heavy 写行;域被采晶矿「未变标记」翻回
   logic_rand 时第 2 个写行即经采新路径直采回真值(帧距 2,同帧落方向相反的回翻行);
   (iv) 锚 = 离槽写行与退款写金行同 ``sig.group_id``,不枚举证据串、不依赖 gold
   证据串(卖完即买的主流形态退款证据会被覆盖)。期望数 32/15/1 · 14/4/1 · 采回 4
   (帧距 3/3/4 two_frame + 2 rand_adopt)/ 回翻 1 / 样本 13 / 离槽 8 / 局末未决 1 ·
   gold 路径 4 · ① 真失配 2 · ② 违例 0;
3. 修前签名的 ② 双向违例:保旧行基线 logic_rand(= 验证局 run_20261124_030405 v123 /
   v333 形态)+ 采新行基线 observation → 2 条违例带方向;特效窗行不计。

fixture 行形状 = journal 实形(write 行带 v/ts/field/after/same_value/state.values/
state.prov/sig;obs_event star 行带 observed{old,new,char,slot,domain}/verdict/state;
逻辑写行同组同 ``sig.group_id``;行行内嵌写后 state,故每行 prov 即该行自身的写来源,
下一行的「基线」读它)。剧本段序标签 H<n>(heavy 写行)/ A<n>(采新行)为 fixture 内的
段序号;守恒式「采新行 14 = 采回 4 + 离槽 8 + 局末未决 1 + 回翻 1」贯穿全剧本。
"""

from __future__ import annotations

import copy
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path


def _load_monitor_module():
    """从仓库根定位 skills 脚本并加载(sr-od-test 独立仓,无包路径可达)。"""
    for anc in Path(__file__).resolve().parents:
        p = (anc / 'skills' / 'sr-od-dev-currency-war' / 'scripts'
             / 'cw_star_gate_monitor.py')
        if p.is_file():
            spec = importlib.util.spec_from_file_location(
                '_cw_star_gate_monitor_under_test', p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise AssertionError('自 __file__ 向上找不到 cw_star_gate_monitor.py(仓库根?)')


_mod = _load_monitor_module()

_BASE = datetime(2026, 11, 24, 3, 4, 0)
_MISMATCH = 'observe_vs_logic_mismatch'


def _unit(char_id: str, star: int) -> dict:
    return {'char_id': char_id, 'star': star, 'equips': [], 'uid': None}


def _bv(mapping: dict[int, tuple[str, int]]) -> dict:
    """bench 值:9 槽,键 = 1 基物理槽 → (角色, 星);未列槽 = 空。"""
    slots = [{'kind': 'empty', 'unit': None, 'item': None} for _ in range(9)]
    for k, (c, s) in mapping.items():
        slots[k - 1] = {'kind': 'unit', 'unit': _unit(c, s), 'item': None}
    return {'slots': slots, 'capacity': 9}


def _dv(front: dict[int, tuple[str, int]] | None = None,
        back: dict[int, tuple[str, int]] | None = None) -> dict:
    """deployed 值:定长子表(前 4 / 后 6),空位 None,键 = 1 基物理槽。"""
    f: list = [None] * 4
    b: list = [None] * 6
    for k, (c, s) in (front or {}).items():
        f[k - 1] = _unit(c, s)
    for k, (c, s) in (back or {}).items():
        b[k - 1] = _unit(c, s)
    return {'front_slots': f, 'back_slots': b}


class _Journal:
    """单 run 合成 journal:维护账面(values / prov),每行内嵌写后快照。"""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.defects: list[dict] = []
        self.values: dict = {}
        self.prov: dict = {}
        self._n = 0

    def next_ts(self) -> str:
        """下一行将取得的 ts(给「写行之后、下一 heavy 之前」的台账行用)。"""
        return (_BASE + timedelta(seconds=self._n)).isoformat()

    def _emit(self, row: dict) -> None:
        row['v'] = len(self.rows) + 1
        row['ts'] = self.next_ts()
        row['run_id'] = 'run_fixture'
        self.rows.append(row)
        self._n += 1

    def _write(self, field: str, value, *, family: str, actor: str,
               evidence: str | None, source: str, group_id: str | None = None,
               screen: str | None = None) -> str:
        old = self.values.get(field)
        self.values[field] = copy.deepcopy(value)
        if source == 'observation' and evidence is None:
            self.prov.pop(field, None)      # 观察写回不带 evidence → prov 无条目
        else:
            self.prov[field] = {'source': source, 'evidence': evidence}
        self._emit({
            'row': 'write', 'field': field, 'after': copy.deepcopy(value),
            'same_value': old == value,
            'state': {'values': copy.deepcopy(self.values),
                      'prov': copy.deepcopy(self.prov)},
            'sig': {'family': family, 'actor': actor, 'screen': screen,
                    'mode': 'read' if family == 'obs' else 'compute',
                    'quality': {}, 'group_id': group_id},
            'note': '', 'evidence_refs': []})
        return self.rows[-1]['ts']

    def heavy(self, field: str, value) -> str:
        """heavy 观察写行(obs / CwScreenPrep / read);返回行 ts。"""
        return self._write(field, value, family='obs', actor='CwScreenPrep',
                           evidence=None, source='observation',
                           screen='货币战争-备战')

    def rand(self, field: str, value, evidence: str, *,
             actor: str = 'CwActionCollectOreParam',
             group_id: str | None = None) -> None:
        self._write(field, value, family='logic_action', actor=actor,
                    evidence=evidence, source='logic_rand', group_id=group_id)

    def logic(self, field: str, value, evidence: str, actor: str, *,
              group_id: str | None = None, family: str = 'logic_action') -> None:
        self._write(field, value, family=family, actor=actor, evidence=evidence,
                    source='logic', group_id=group_id)

    def star(self, prefix: str, old: int, new: int, char: str, slot: int,
             domain: str) -> int:
        """star 披露行(state = 门调用时点 = observe 之前的账面);返回行 v。"""
        tail = {
            _mod.ADOPT_PREFIX: '门不保旧:字段来源 logic_rand,星差按读采;',
            _mod.HOLD_JITTER_PREFIX: '单帧差弃读,两帧一致才采新;',
            _mod.HOLD_WINDOW_PREFIX: '窗内星读不可信,不计两帧;',
        }[prefix]
        self._emit({
            'row': 'obs_event', 'event': 'arbitrate', 'field': 'star',
            'observed': {'old': old, 'new': new, 'source': 'director',
                         'char': char, 'slot': slot, 'domain': domain},
            'verdict': f'{prefix}({tail}source=director)', 'obs_phase': '',
            'state': {'values': copy.deepcopy(self.values),
                      'prov': copy.deepcopy(self.prov)},
            'sig': {'family': 'obs', 'actor': 'obs_conflict', 'screen': None,
                    'mode': 'read', 'quality': {}, 'group_id': None},
            'note': '', 'evidence_refs': []})
        return self.rows[-1]['v']

    def defect(self, kind: str, field: str, ts: str,
               logic_evidence: str | None = None) -> None:
        self.defects.append({
            'kind': kind, 'field': field, 'expected': None, 'actual': None,
            'observed_evidence': None, 'ts': ts, 'screen': None, 'actor': None,
            'group_id': None, 'logic_evidence': logic_evidence})


class _Bench:
    """当前 bench 槽表(1 基槽 → (角色, 星));``view()`` 产 journal 值形状。"""

    def __init__(self, mapping: dict[int, tuple[str, int]]) -> None:
        self.m: dict[int, tuple[str, int]] = dict(mapping)

    def set(self, kv: dict) -> None:
        for k, v in kv.items():
            if v is None:
                self.m.pop(k, None)
            else:
                self.m[k] = v

    def view(self) -> dict:
        return _bv(self.m)


def _build_run() -> tuple[_Journal, dict]:
    """32 个 heavy 写行的合成剧本(段序见行内注释);返回 journal 与采新行 v 表。"""
    j = _Journal()
    A: dict[str, int] = {}
    # run 首行之前的 bench 真失配 R2 → 按首末行 ts 切台账时排除
    j.defect(_MISMATCH, 'bench', (_BASE - timedelta(seconds=10)).isoformat(),
             'proj_other#0')                                             # R2(切片排除)
    # ── 开局:H1 种子帧(前一行 prov bench = logic_rand / seed:opening,读全部走
    #    身份更替分支);窗帧只有一条特效窗 star 行、无写行;H2 / H3 观察态基线 ──
    j.rand('bench', _bv({}), 'seed:opening', actor='GsOpeningSeed')
    b = _Bench({1: ('灵砂', 2), 2: ('姬子', 2), 3: ('忘归人', 1), 4: ('知更鸟', 2),
                5: ('黑天鹅', 1), 6: ('桂乃芬', 1), 8: ('真珠', 1), 9: ('老虎', 2)})
    j.heavy('bench', b.view())                                           # H1
    j.star(_mod.HOLD_WINDOW_PREFIX, 1, 2, '黑天鹅', 5, 'bench')          # 窗帧
    j.star(_mod.HOLD_JITTER_PREFIX, 1, 2, '桂乃芬', 6, 'bench')
    j.heavy('bench', b.view())                                           # H2
    j.heavy('deployed', _dv({2: ('托帕', 1), 3: ('停云', 1)},
                            {1: ('火花', 1), 2: ('希儿', 2), 3: ('希儿', 2)}))  # H3
    # ── A1:采样落位幻影 ★2 → 直采 ★1;真值 ★2 回来经一帧保旧(H5)再采新(H6),
    #    保旧窗内落确定写 → H6 采回帧判真失配 C1 ──
    b.set({5: ('黑天鹅', 2)})
    j.rand('bench', b.view(), 'proj_ore_reward_char#ore3')
    A['A1'] = j.star(_mod.ADOPT_PREFIX, 2, 1, '黑天鹅', 5, 'bench')
    b.set({5: ('黑天鹅', 1)})
    j.heavy('bench', b.view())                                           # H4
    j.star(_mod.HOLD_JITTER_PREFIX, 1, 2, '黑天鹅', 5, 'bench')
    j.heavy('bench', b.view())                                           # H5
    j.logic('bench', b.view(), 'proj_buy_place', 'CwActionBuyCardOp',
            group_id='act:CwActionBuyCardOp@1')
    b.set({5: ('黑天鹅', 2)})
    h6 = j.heavy('bench', b.view())                                      # H6 采回帧
    j.defect(_MISMATCH, 'bench', h6, 'proj_buy_place')                   # C1
    # ── A2:deployed 载体合成幻影(证据串含 proj_ore_merge 子串)→ 直采;H9 采回帧
    #    同帧 back 槽 1 身份差(火花 → 灵砂)→ 真失配 R1 ──
    j.rand('deployed', _dv({2: ('托帕', 2), 3: ('停云', 1)},
                           {1: ('火花', 1), 2: ('希儿', 2), 3: ('希儿', 2)}),
          'ore_reward_attach_missing#proj_ore_merge#1#ore2')
    A['A2'] = j.star(_mod.ADOPT_PREFIX, 2, 1, '托帕', 2, 'front')
    j.heavy('deployed', _dv({2: ('托帕', 1), 3: ('停云', 1)},
                            {1: ('火花', 1), 2: ('希儿', 2), 3: ('希儿', 2)}))  # H7
    j.star(_mod.HOLD_JITTER_PREFIX, 1, 2, '托帕', 2, 'front')
    j.heavy('deployed', _dv({2: ('托帕', 1), 3: ('停云', 1)},
                            {1: ('火花', 1), 2: ('希儿', 2), 3: ('希儿', 2)}))  # H8
    j.logic('deployed', _dv({2: ('托帕', 1), 3: ('停云', 1)},
                            {1: ('火花', 1), 2: ('希儿', 2), 3: ('希儿', 2)}),
            'proj_move_unit_deployed', 'CwActionDeployOp',
            group_id='act:CwActionDeployOp@1')
    h9 = j.heavy('deployed', _dv({2: ('托帕', 2), 3: ('停云', 1)},
                                 {1: ('灵砂', 1), 2: ('希儿', 2), 3: ('希儿', 2)}))
    j.defect(_MISMATCH, 'deployed', h9, 'proj_move_unit_deployed')       # H9 / R1
    # ── A3:未变标记基线;直采后下一 heavy 读成他人(长夜月)→ identity_changed ──
    j.rand('bench', b.view(), 'proj_ore_mark_bench#ore3')
    A['A3'] = j.star(_mod.ADOPT_PREFIX, 1, 2, '忘归人', 3, 'bench')
    b.set({3: ('忘归人', 2)})
    j.heavy('bench', b.view())                                           # H10
    b.set({3: ('长夜月', 1)})
    j.heavy('bench', b.view())                                           # H11
    # ── A4:读高(直采 ★2 > 基线 ★1);中间一帧同值(H13)→ 保旧(H14)→ 采回(H15,帧距 4)──
    b.set({7: ('桂乃芬', 1)})
    j.rand('bench', b.view(), 'proj_ore_reward_char#ore3')
    A['A4'] = j.star(_mod.ADOPT_PREFIX, 1, 2, '桂乃芬', 7, 'bench')
    b.set({7: ('桂乃芬', 2)})
    j.heavy('bench', b.view())                                           # H12
    j.heavy('bench', b.view())                                           # H13
    j.star(_mod.HOLD_JITTER_PREFIX, 2, 1, '桂乃芬', 7, 'bench')
    j.heavy('bench', b.view())                                           # H14
    b.set({7: ('桂乃芬', 1)})
    j.heavy('bench', b.view())                                           # H15 采回帧
    # ── A12 → H16 → 投资卡全场出售(三写同组)→ gold 真失配 → H17 ──
    b.set({6: ('桂乃芬', 2)})
    j.rand('bench', b.view(), 'proj_ore_reward_char#ore8')
    A['A12'] = j.star(_mod.ADOPT_PREFIX, 2, 1, '桂乃芬', 6, 'bench')
    b.set({6: ('桂乃芬', 1)})
    j.heavy('bench', b.view())                                           # H16
    j.logic('deployed', _dv(), 'effect_board_rewrite', 'EffectLedgerBridge',
            group_id='hook:EffectLedgerBridge@7', family='logic_hook')
    j.logic('bench', _bv({}), 'effect_board_rewrite', 'EffectLedgerBridge',
            group_id='hook:EffectLedgerBridge@7', family='logic_hook')
    j.logic('gold', 50, 'effect_board_rewrite', 'EffectLedgerBridge',
            group_id='hook:EffectLedgerBridge@7', family='logic_hook')
    j.defect(_MISMATCH, 'gold', j.next_ts(), 'effect_board_rewrite')     # G12
    b = _Bench({1: ('灵砂', 2), 2: ('姬子', 2), 3: ('希儿', 2), 4: ('知更鸟', 2),
                5: ('黑天鹅', 2), 6: ('桂乃芬', 1), 7: ('桂乃芬', 1),
                8: ('真珠', 1), 9: ('老虎', 2)})
    refill = _Bench({})
    for k in range(1, 10):     # 全场出售后重新买满(每买一张一行)
        refill.set({k: b.m[k]})
        j.logic('bench', refill.view(), 'proj_buy_place', 'CwActionBuyCardOp',
                group_id=f'act:CwActionBuyCardOp@{1 + k}')
    j.heavy('bench', b.view())                                           # H17
    # ── A5:至 run 末既未采回也未离槽 ──
    j.rand('bench', b.view(), 'proj_ore_mark_bench#ore3')
    A['A5'] = j.star(_mod.ADOPT_PREFIX, 1, 2, '真珠', 8, 'bench')
    b.set({8: ('真珠', 2)})
    j.heavy('bench', b.view())                                           # H18
    j.heavy('bench', b.view())                                           # H19
    # ── A6:备战卖出(清槽写行与退款写金行同组);此前另有一条无关 gold 真失配 ──
    j.defect(_MISMATCH, 'gold', h9, 'proj_sell_refund#9')                # 无关 U1
    j.rand('bench', b.view(), 'proj_ore_mark_bench#ore3')
    A['A6'] = j.star(_mod.ADOPT_PREFIX, 2, 1, '老虎', 9, 'bench')
    b.set({9: ('老虎', 1)})
    j.heavy('bench', b.view())                                           # H20
    b.set({9: None})
    j.logic('bench', b.view(), 'proj_sell_bench', 'CwActionSellBenchOp',
            group_id='act:CwActionSellBenchOp@a')
    j.logic('gold', 53, 'proj_sell_refund#1', 'CwActionSellBenchOp',
            group_id='act:CwActionSellBenchOp@a')
    j.defect(_MISMATCH, 'gold', j.next_ts(), 'proj_sell_refund#1')        # G6
    # ── A7:场上卖出(deployed 子表空位 None);H22 之后一条无关 gold 真失配 ──
    j.logic('deployed', _dv({}, {3: ('希儿', 2)}), 'proj_move_unit_deployed',
            'CwActionDeployOp', group_id='act:CwActionDeployOp@2')
    b.set({3: None})
    j.logic('bench', b.view(), 'proj_move_unit_bench#0', 'CwActionDeployOp',
            group_id='act:CwActionDeployOp@2')
    j.rand('deployed', _dv({}, {3: ('希儿', 2)}), 'proj_ore_mark_deployed#ore5')
    A['A7'] = j.star(_mod.ADOPT_PREFIX, 2, 1, '希儿', 3, 'back')
    j.heavy('deployed', _dv({}, {3: ('希儿', 1)}))                       # H21
    j.logic('deployed', _dv(), 'proj_sell_deployed', 'CwActionSellDeployedOp',
            group_id='act:CwActionSellDeployedOp@b')
    j.logic('gold', 55, 'proj_sell_deployed_gold#2', 'CwActionSellDeployedOp',
            group_id='act:CwActionSellDeployedOp@b')
    j.defect(_MISMATCH, 'gold', j.next_ts(), 'proj_sell_deployed_gold#2')  # G7
    h22 = j.heavy('deployed', _dv())                                     # H22
    j.defect(_MISMATCH, 'gold', h22, 'proj_other#1')                      # 无关 U2
    # ── A8:卖完即买(退款证据被 proj_buy_gold 覆盖;台账行 ts = 下一 heavy 同秒)──
    b.set({9: ('真珠', 1)})
    j.rand('bench', b.view(), 'proj_ore_reward_char#ore6')
    A['A8'] = j.star(_mod.ADOPT_PREFIX, 2, 1, '姬子', 2, 'bench')
    b.set({2: ('姬子', 1), 9: None})
    j.heavy('bench', b.view())                                           # H23
    b.set({2: None})
    j.logic('bench', b.view(), 'proj_sell_bench', 'CwActionSellBenchOp',
            group_id='act:CwActionSellBenchOp@c')
    j.logic('gold', 56, 'proj_sell_refund#3', 'CwActionSellBenchOp',
            group_id='act:CwActionSellBenchOp@c')
    j.logic('gold', 55, 'proj_buy_gold#3', 'CwActionBuyCardOp',
            group_id='act:CwActionBuyCardOp@d')
    b.set({2: ('三月七', 1)})
    j.logic('bench', b.view(), 'proj_buy_place', 'CwActionBuyCardOp',
            group_id='act:CwActionBuyCardOp@d')
    h24 = j.heavy('bench', b.view())                                     # H24
    j.defect(_MISMATCH, 'gold', h24, 'proj_buy_gold#3')                  # G8
    # ── A10:真合成负例 —— 买牌合成组内 proj_buy_place 把载体槽写成 ★2(与
    #    proj_buy_gold 同组),按槽内容先判 → logic_overwritten,不作 (iv) 锚 ──
    b.set({6: ('桂乃芬', 2)})
    j.rand('bench', b.view(), 'proj_ore_reward_char#ore9')
    A['A10'] = j.star(_mod.ADOPT_PREFIX, 2, 1, '桂乃芬', 6, 'bench')
    b.set({6: ('桂乃芬', 1)})
    j.heavy('bench', b.view())                                           # H25
    j.logic('gold', 54, 'proj_buy_gold#4', 'CwActionBuyCardOp',
            group_id='act:CwActionBuyCardOp@f')
    b.set({6: ('桂乃芬', 2), 7: None})
    j.logic('bench', b.view(), 'proj_buy_place', 'CwActionBuyCardOp',
            group_id='act:CwActionBuyCardOp@f')
    j.logic('bench', b.view(), 'proj_merge_upgrade#1', 'CwActionBuyCardOp',
            group_id='act:CwActionBuyCardOp@g')
    j.heavy('bench', b.view())                                           # H26
    # ── A9:离槽后卖新单位(守卫负例)—— 上阵腾空(组内无 gold)→ emptied,
    #    其后新单位卖出组的 gold 真失配不计 ──
    j.rand('bench', b.view(), 'proj_ore_mark_bench#ore7')
    A['A9'] = j.star(_mod.ADOPT_PREFIX, 2, 1, '知更鸟', 4, 'bench')
    b.set({4: ('知更鸟', 1)})
    j.heavy('bench', b.view())                                           # H27
    b.set({4: None})
    j.logic('bench', b.view(), 'proj_move_unit_bench#1', 'CwActionDeployOp',
            group_id='act:CwActionDeployOp@3')
    b.set({4: ('三月七', 1)})
    j.logic('bench', b.view(), 'proj_buy_place#4', 'CwActionBuyCardOp',
            group_id='act:CwActionBuyCardOp@h')
    b.set({4: None})
    j.logic('bench', b.view(), 'proj_sell_bench', 'CwActionSellBenchOp',
            group_id='act:CwActionSellBenchOp@e')
    j.logic('gold', 55, 'proj_sell_refund#4', 'CwActionSellBenchOp',
            group_id='act:CwActionSellBenchOp@e')
    h28 = j.heavy('bench', b.view())                                     # H28
    j.defect(_MISMATCH, 'gold', h28, 'proj_sell_refund#4')               # G9(不计)
    # ── A11:同名 ★2 副本逻辑移入同槽 → logic_overwritten ──
    j.rand('bench', b.view(), 'proj_ore_mark_bench#ore9')
    A['A11'] = j.star(_mod.ADOPT_PREFIX, 2, 1, '灵砂', 1, 'bench')
    b.set({1: ('灵砂', 1)})
    j.heavy('bench', b.view())                                           # H29
    b.set({1: ('灵砂', 2)})
    j.logic('bench', b.view(), 'proj_move_unit_bench#2', 'CwActionDeployOp',
            group_id='act:CwActionDeployOp@4')
    j.heavy('bench', b.view())                                           # H30
    # ── A13:帧距 2 回翻 —— 采新后域被未变标记翻回 logic_rand,第 2 个写行经采新
    #    路径直采回真值,同帧落方向相反的回翻行 A13′ ──
    b.set({5: ('停云', 2)})
    j.logic('bench', b.view(), 'proj_move_unit_bench#3', 'CwActionDeployOp',
            group_id='act:CwActionDeployOp@5')
    b.set({9: ('真珠', 1)})
    j.rand('bench', b.view(), 'proj_ore_reward_char#ore10')
    A['A13'] = j.star(_mod.ADOPT_PREFIX, 2, 1, '停云', 5, 'bench')
    b.set({5: ('停云', 1)})
    j.heavy('bench', b.view())                                           # H31
    j.rand('bench', b.view(), 'proj_ore_mark_bench#ore10')
    A["A13'"] = j.star(_mod.ADOPT_PREFIX, 1, 2, '停云', 5, 'bench')      # 回翻行
    b.set({5: ('停云', 2)})
    j.heavy('bench', b.view())                                           # H32 采回帧
    return j, A


def test_contract_prefix_pinned_to_gate_constant():
    """契约键交叉锁(三键同法):脚本筛选键 ↔ 门的三个 verdict 前缀常量。"""
    from sr_od.application.currency_war.kernel import cw_reconcile

    assert _mod.ADOPT_PREFIX == cw_reconcile.STAR_ADOPT_RAND_BASELINE_PREFIX
    assert _mod.HOLD_JITTER_PREFIX == cw_reconcile.STAR_HOLD_JITTER_PREFIX
    assert _mod.HOLD_WINDOW_PREFIX == cw_reconcile.STAR_HOLD_WINDOW_PREFIX


def test_analyze_run_counts_on_synthetic_journal():
    """合成 journal 计数矩阵:④(i)-(iv) + ① 事实清单 + ② 零违例,逐数对应剧本。"""
    j, A = _build_run()
    res = _mod.analyze_run(j.rows, j.defects)

    # ④(i) heavy 写行 32 = 随机态基线 15(含开局种子 1)+ 非随机态 17
    assert (res['heavy_total'], res['heavy_rand_baseline'],
            res['heavy_rand_seed']) == (32, 15, 1)
    # ④(ii) star 行:采新 14(A1-A13 + 回翻行,基线全 logic_rand)/ 保旧-抖动 4
    # (基线全 observation)/ 保旧-窗 1
    sbp = res['star_by_prefix']
    assert sbp[_mod.ADOPT_PREFIX] == {'total': 14, 'by_baseline': {'logic_rand': 14}}
    assert sbp[_mod.HOLD_JITTER_PREFIX] == {'total': 4,
                                            'by_baseline': {'observation': 4}}
    assert sbp[_mod.HOLD_WINDOW_PREFIX] == {'total': 1,
                                            'by_baseline': {'observation': 1}}
    # ④(iii) 采回 4:帧距与途径按上下文判(A1/A2 帧距 3、A4 帧距 4 走 two_frame;
    # A13 帧距 2 走 rand_adopt);回翻行单列不计样本
    rev = {r['v']: r for r in res['adopt_reverted']}
    assert res['adopt_reverted_count'] == 4
    assert {k: (r['revert_frame_distance'], r['revert_via']) for k, r in rev.items()} == {
        A['A1']: (3, 'two_frame'), A['A2']: (3, 'two_frame'),
        A['A4']: (4, 'two_frame'), A['A13']: (2, 'rand_adopt')}
    assert (rev[A['A1']]['domain'], rev[A['A1']]['slot'], rev[A['A1']]['char'],
            rev[A['A1']]['baseline_star'], rev[A['A1']]['adopted_star'],
            rev[A['A1']]['baseline_evidence']) == (
        'bench', 5, '黑天鹅', 2, 1, 'proj_ore_reward_char#ore3')
    assert (rev[A['A2']]['domain'], rev[A['A2']]['slot']) == ('front', 2)
    # 标签:A4 读高;A2 基线证据串含 proj_ore_merge 子串 → 窗漏检嫌疑;A1/A13 读低非合成
    assert rev[A['A4']]['label'] == _mod.LABEL_READ_HIGH
    assert rev[A['A2']]['label'] == _mod.LABEL_READ_LOW_MERGE
    assert rev[A['A1']]['label'] == _mod.LABEL_READ_LOW_OTHER
    assert rev[A['A13']]['label'] == _mod.LABEL_READ_LOW_OTHER
    assert res['adopt_reverse_count'] == 1
    assert res['adopt_reverse'] == [{
        'domain': 'bench', 'slot': 5, 'char': '停云', 'old': 1, 'new': 2,
        'v': A["A13'"], 'is_reverse_of': A['A13']}]
    assert res['adopt_sample_count'] == 13
    # 离槽 8:A3 identity_changed / A9 emptied / A12·A6·A7·A8 sold / A10·A11
    # logic_overwritten(A10 关闭行虽与 proj_buy_gold 同组,reason 按槽内容先判)
    changed = {r['v']: r['reason'] for r in res['adopt_slot_changed']}
    assert res['adopt_slot_changed_count'] == 8
    assert changed == {
        A['A3']: 'identity_changed', A['A9']: 'emptied',
        A['A12']: 'sold', A['A6']: 'sold', A['A7']: 'sold', A['A8']: 'sold',
        A['A10']: 'logic_overwritten', A['A11']: 'logic_overwritten'}
    assert res['adopt_open_at_run_end'] == 1
    # 守恒:采新 14 = 采回 4 + 离槽 8 + 局末未决 1 + 回翻 1
    assert (sbp[_mod.ADOPT_PREFIX]['total'] == res['adopt_reverted_count']
            + res['adopt_slot_changed_count'] + res['adopt_open_at_run_end']
            + res['adopt_reverse_count'])
    # ④(iv) 金币路径 4:A6 备战卖出 / A7 场上卖出 / A8 卖完即买 / A12 全场出售;
    # A9 不计(其卖出组清的是新单位);两条无关 gold 行不计;不依赖 gold 证据串
    assert res['gold_path_mismatch'] == 4
    gpr = {(r['char'], r['gold_evidence'], r['depart_evidence'],
            r['sell_frame_distance'], r['depart_reason']) for r in res['gold_path_rows']}
    assert gpr == {
        ('桂乃芬', 'effect_board_rewrite', 'effect_board_rewrite', 1, 'sold'),
        ('老虎', 'proj_sell_refund#1', 'proj_sell_bench', 1, 'sold'),
        ('希儿', 'proj_sell_deployed_gold#2', 'proj_sell_deployed', 1, 'sold'),
        ('姬子', 'proj_buy_gold#3', 'proj_sell_bench', 1, 'sold')}
    # ① 只报事实不归因:C1(bench,对齐 H6)差异槽 (bench,5) 黑天鹅 1 → 2,
    #   linked = [A1];R1(deployed,对齐 H9)差异槽 (front,2) 托帕 1 → 2 与
    #   (back,1) 火花 → 灵砂,linked = [A2];run 之前的 R2 切片排除;无归因位
    assert res['mismatch_count'] == 2
    mr = res['mismatch_rows']
    assert [m['field'] for m in mr] == ['bench', 'deployed']
    assert mr[0]['diff_slots'] == [{
        'domain': 'bench', 'slot': 5, 'char': '黑天鹅', 'prev_char': '黑天鹅',
        'prev_kind': 'unit', 'prev_star': 1, 'after_char': '黑天鹅',
        'after_kind': 'unit', 'after_star': 2}]
    assert mr[0]['linked_adoptions'] == [{
        'v': A['A1'], 'domain': 'bench', 'slot': 5, 'char': '黑天鹅',
        'old': 2, 'new': 1}]
    assert [(d['domain'], d['slot'], d['prev_char'], d['after_char'])
            for d in mr[1]['diff_slots']] == [('front', 2, '托帕', '托帕'),
                                              ('back', 1, '火花', '灵砂')]
    assert [lk['v'] for lk in mr[1]['linked_adoptions']] == [A['A2']]
    assert all('attributable' not in m for m in mr)
    # ② 本 run 零违例
    assert res['hold_violation_count'] == 0


def test_hold_violations_bidirectional():
    """修前签名:保旧行落在 logic_rand 基线 + 采新行落在 observation 基线 → 2 条
    违例带方向;特效窗行无来源约束不计。"""
    j = _Journal()
    B = _bv({3: ('忘归人', 1)})
    j.rand('bench', B, 'proj_ore_reward_char#ore1')
    j.star(_mod.HOLD_JITTER_PREFIX, 1, 2, '忘归人', 3, 'bench')   # 基线 logic_rand
    j.heavy('bench', B)                                             # 基线翻 observation
    j.star(_mod.ADOPT_PREFIX, 1, 2, '忘归人', 3, 'bench')          # 基线 observation
    j.heavy('bench', _bv({3: ('忘归人', 2)}))
    j.star(_mod.HOLD_WINDOW_PREFIX, 2, 1, '忘归人', 3, 'bench')    # 窗行不计
    res = _mod.analyze_run(j.rows, j.defects)
    assert res['hold_violation_count'] == 2
    assert [(v['prefix'], v['baseline_source'], v['direction'])
            for v in res['hold_violations']] == [
        (_mod.HOLD_JITTER_PREFIX, 'logic_rand', '保旧于随机态基线'),
        (_mod.ADOPT_PREFIX, 'observation', '采新于非随机态基线')]

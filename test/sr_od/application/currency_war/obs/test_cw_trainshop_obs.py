"""开拓商店(银轨商店)面板读数层测试(纯函数解析 + 归档帧真读真值)。

锁的设计约定(obs/cw_trainshop_obs.py,读法标定证据帧 =
sr-od-test/screens/货币战争-备战-开拓商店/panel_*_r13、panel_slots_{d,e}_r15):

- 纯函数:名行「名字+行尾标价」拆分 / 属性卡档位后缀「|」→「Ⅰ」读音修复 /
  帕姆「N/500」解析(分母非 500 拒信)/「全部刷新」锚 lcs 判定 / 刷新钮名行
  数字条目标价提取(「1力/次」混合形态);
- 槽带帧真值:mode=slots,定长 4 槽(刷新钮轮转占位——r13 帧槽 1 刷新钮
  kind=refresh 标价 1;r15 两帧四槽全商品、refresh_slot=None),角色卡 SIFT
  身份(faction=注册表首阵营,Momojie 显示名读规范名「开拓者」= 换季改名归一表),
  属性卡 OCR 名(item_type=other),余额 / 帕姆进度实读;
- 展示卡帧真值(首开空池软锁 013105 与恢复态死锁 122630 画面同构):
  mode=showcase、四槽键 None、展示卡 {name 星穹列车,跃迁! cost 0} +
  解锁点击点 (1045,281)、帕姆块缺席 → None。

真帧测试走 test_context 真实 OCR + SIFT 立绘库(conftest 磁盘 memo 温缓存);
逐帧执行、断言共享(慢计算只算一次)。
"""

from __future__ import annotations

from test.conftest import SrTestContext

from sr_od.application.currency_war.obs.cw_trainshop_obs import (
    _refresh_cost_from_entries,
    is_refresh_anchor,
    normalize_attr_name,
    parse_pam_text,
    read_pam_progress,
    read_trainshop_balance,
    read_trainshop_panel,
    split_name_cost,
)

_SCREEN: str = '货币战争-备战-开拓商店'


def test_normalize_attr_name() -> None:
    """档位后缀读音修复:|/l/I/1 → Ⅰ(仅 CJK 结尾);英文名与干净名不碰。"""
    assert normalize_attr_name('后台强度|') == '后台强度Ⅰ'
    assert normalize_attr_name('幸运一击率l') == '幸运一击率Ⅰ'
    assert normalize_attr_name('速度增幅I') == '速度增幅Ⅰ'
    assert normalize_attr_name('速度增幅1') == '速度增幅Ⅰ'
    assert normalize_attr_name('Momojie') == 'Momojie'
    assert normalize_attr_name('三月七') == '三月七'
    assert normalize_attr_name(' 全部刷新 ') == '全部刷新'


def test_split_name_cost() -> None:
    """名行条目拆分:名字拼接(按 x 序)+ 行尾纯数字 = 标价;无数字 → None。"""
    assert split_name_cost([('Momojie', 746), ('50', 863)]) == ('Momojie', 50)
    assert split_name_cost([('三月七', 983), ('15', 1127)]) == ('三月七', 15)
    # 乱序输入按 x 重排(OCR 条目序不保证)
    assert split_name_cost([('15', 1127), ('三月七', 983)]) == ('三月七', 15)
    # 属性卡档位数字尾巴并入名字修复(「后台强度|」x 在标价左侧)
    assert split_name_cost([('后台强度|', 1248), ('15', 1360)]) == ('后台强度Ⅰ', 15)
    assert split_name_cost([('全部刷新', 496)]) == ('全部刷新', None)
    assert split_name_cost([]) == ('', None)


def test_refresh_cost_from_entries() -> None:
    """刷新钮名行标价提取:纯数字条目与「1力/次」混合条目同判;纯文字跳过。"""
    assert _refresh_cost_from_entries([('全部刷新', 496), ('1', 610)]) == 1
    assert _refresh_cost_from_entries([('全部刷新', 496), ('1力/次', 610)]) == 1
    assert _refresh_cost_from_entries([('全部刷新', 496)]) is None
    assert _refresh_cost_from_entries([]) is None


def test_parse_pam_text_guards() -> None:
    """帕姆解析防线:N/500 采信;分母非 500 / 倒挂 / 无斜杠形态拒信不猜。"""
    assert parse_pam_text(['0/500']) == (0, 500)
    assert parse_pam_text(['136/500']) == (136, 500)
    assert parse_pam_text(['帕姆王', '累计消耗解锁', '60/500']) == (60, 500)
    assert parse_pam_text(['60/508']) is None   # 分母误读
    assert parse_pam_text(['600/500']) is None  # 进度越分母
    assert parse_pam_text(['0']) is None        # 无斜杠形态
    assert parse_pam_text([]) is None


def test_refresh_anchor_lcs() -> None:
    """「全部刷新」锚 lcs 判定:全等与轻度误读命中;异词与空不命中。"""
    assert is_refresh_anchor(['全部刷新'])
    assert is_refresh_anchor(['全部刷断'])       # 轻度误读 lcs 3/4 = 0.75
    assert not is_refresh_anchor(['三月七'])
    assert not is_refresh_anchor([''])
    assert not is_refresh_anchor([])


def test_slots_frames_truth(test_context: SrTestContext) -> None:
    """槽带帧真值(三帧):mode=slots + 四槽结构 + 余额 + 帕姆进度实读。

    帧真值 = 2026-11-21 第十一局归档(013815/015114/021858,人工读数对拍:
    槽 3 三月七→幸运一击率Ⅰ = 一笔 15 价购买后的买一补一,帕姆 0→15;
    帧帕姆 60 对齐玩家卡五档采样 0→15→…→60→110 的第三档)。
    """
    expected = {
        'panel_slots_a_r13': {
            'balance': 20, 'pam': (0, 500),
            'slots': [('refresh', '全部刷新', '?', 1),
                      ('content', '开拓者', '开拓银轨', 50),
                      ('content', '三月七', '开拓银轨', 15),
                      ('content', '后台强度Ⅰ', '?', 15)],
        },
        'panel_slots_b_r13': {
            'balance': 45, 'pam': (15, 500),
            'slots': [('refresh', '全部刷新', '?', 1),
                      ('content', '开拓者', '开拓银轨', 50),
                      ('content', '幸运一击率Ⅰ', '?', 15),
                      ('content', '后台强度Ⅰ', '?', 15)],
        },
        'panel_slots_c_r13': {
            'balance': 80, 'pam': (60, 500),
            'slots': [('refresh', '全部刷新', '?', 1),
                      ('content', '开拓者', '开拓银轨', 50),
                      ('content', '三月七', '开拓银轨', 15),
                      ('content', '后台强度Ⅰ', '?', 15)],
        },
    }
    for frame_name, want in expected.items():
        frame = test_context.load_screen(_SCREEN, frame_name)
        panel = read_trainshop_panel(test_context, frame)
        balance = read_trainshop_balance(test_context, frame)
        pam = read_pam_progress(test_context, frame)
        assert panel['mode'] == 'slots', frame_name
        assert panel['showcase_card'] is None, frame_name
        assert panel['refresh_slot'] == 1, frame_name
        assert balance == want['balance'], frame_name
        assert pam == want['pam'], frame_name
        cards = panel['shop_cards']
        assert cards is not None and len(cards) == 4, frame_name
        for i, (kind, name, faction, cost) in enumerate(want['slots']):
            entry = cards[i]
            assert entry['kind'] == kind, (frame_name, i)
            card = entry['card']
            assert card is not None, (frame_name, i)
            assert (card['name'], card['faction'], card['cost']) == \
                (name, faction, cost), (frame_name, i)
            assert card['slot'] == i + 1, (frame_name, i)
            assert card['star'] is None, (frame_name, i)
            assert card['trial'] is False, (frame_name, i)
        # 槽位身份双源结构性断言:角色卡 item_type=char,属性/刷新钮 = other
        assert cards[0]['card']['item_type'] == 'other'
        assert cards[1]['card']['item_type'] == 'char'
        assert cards[2]['card']['item_type'] == (
            'char' if cards[2]['card']['name'] == '三月七' else 'other')


def test_full4_slots_frames_truth(test_context: SrTestContext) -> None:
    """四槽全商品帧真值(r15 两帧,第二十四局 1-6 实拍):刷新钮不在场形态。

    mode=slots + refresh_slot=None + 四槽全 content(槽 1 = 角色卡「星期日」,
    槽 2 = 开拓者变体,槽 3/4 = 属性卡)+ 余额/帕姆实读(25→10 / 15→30,
    首购前台强度Ⅰ一笔的对账实录)。锁「槽 1 = 刷新钮」旧锚作废后的槽带
    判定与四商品读卡。
    """
    expected = {
        'panel_slots_d_r15': {
            'balance': 25, 'pam': (15, 500),
            'slots': [('星期日', 35), ('开拓者', 50),
                      ('速度增幅Ⅰ', 15), ('前台强度Ⅰ', 15)],
        },
        'panel_slots_e_r15': {
            'balance': 10, 'pam': (30, 500),
            'slots': [('星期日', 35), ('开拓者', 50),
                      ('速度增幅Ⅰ', 15), ('幸运一击率Ⅰ', 15)],
        },
    }
    for frame_name, want in expected.items():
        frame = test_context.load_screen(_SCREEN, frame_name)
        panel = read_trainshop_panel(test_context, frame)
        assert panel['mode'] == 'slots', frame_name
        assert panel['showcase_card'] is None, frame_name
        assert panel['refresh_slot'] is None, frame_name
        assert read_trainshop_balance(test_context, frame) == want['balance'], \
            frame_name
        assert read_pam_progress(test_context, frame) == want['pam'], frame_name
        cards = panel['shop_cards']
        assert cards is not None and len(cards) == 4, frame_name
        for i, (name, cost) in enumerate(want['slots']):
            entry = cards[i]
            assert entry['kind'] == 'content', (frame_name, i)
            card = entry['card']
            assert card is not None, (frame_name, i)
            assert (card['name'], card['cost']) == (name, cost), \
                (frame_name, i)
            assert card['slot'] == i + 1, (frame_name, i)
        # 槽 2 开拓者变体 = SIFT 角色卡身份(与 r13 同源口径)
        assert cards[1]['card']['item_type'] == 'char', frame_name


def test_showcase_frames_truth(test_context: SrTestContext) -> None:
    """展示卡帧真值(软锁 013105 + 恢复态死锁 122630,画面同构双帧):
    mode=showcase + 四槽键 None + 展示卡读数与解锁点击点 + 帕姆块缺席。"""
    for frame_name in ('panel_showcase_r13', 'panel_showcase_deadlock_r13'):
        frame = test_context.load_screen(_SCREEN, frame_name)
        panel = read_trainshop_panel(test_context, frame)
        assert panel['mode'] == 'showcase', frame_name
        assert panel['shop_cards'] is None, frame_name
        card = panel['showcase_card']
        assert card is not None, frame_name
        assert card['name'] == '星穹列车，跃迁！', frame_name
        assert card['cost'] == 0, frame_name
        assert (card['cx'], card['cy']) == (1045, 281), frame_name
        assert read_trainshop_balance(test_context, frame) == 0, frame_name
        assert read_pam_progress(test_context, frame) is None, frame_name

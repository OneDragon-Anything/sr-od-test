import os

import yaml

from one_dragon.base.geometry.point import Point
from sr_od.context.sr_context import SrContext
from sr_od.sr_map.sr_map_def import Region


class TestCase:

    def __init__(self, region: Region, pos: Point, num: int, running: bool, possible_pos: list[int],
                 real_move_time: float = 0, tol: float = 5):
        self.region: Region = region
        self.pos: Point = pos
        self.num: int = num
        self.running: bool = running
        self.possible_pos: list[int] = possible_pos
        self.real_move_time: float = real_move_time
        self.tol: float = tol  # 本样本精度阈值(px);默认 5,均匀走廊等匹配歧义场景按实测登记放宽

    @property
    def unique_id(self) -> str:
        return f'{self.region.prl_id}_{self.num:02d}'

    @property
    def image_name(self) -> str:
        return f'{self.region.prl_id}_{self.num:02d}.png'


class TestCaseLoader:

    def __init__(self, ctx: SrContext):
        self.ctx: SrContext = ctx

    def read_test_cases(self, case_file_path: str) -> list[TestCase]:
        data = []
        if os.path.exists(case_file_path):
            with open(case_file_path, encoding='utf-8') as file:
                data = yaml.safe_load(file)

        return [self.dict_2_case(row) for row in data['cases']]

    def save_test_cases(self, case_list: list[TestCase], case_file_path: str):
        cfg = ''

        if len(case_list) == 0:
            cfg += 'cases: []'
        else:
            cfg += 'cases:\n'

        for case in case_list:
            cfg += f'- region: {case.region.prl_id}\n'
            cfg += f'  num: {case.num}\n'
            cfg += f'  pos: [{case.pos.x}, {case.pos.y}]\n'
            cfg += f'  possible_pos: [{case.possible_pos[0]}, {case.possible_pos[1]}, {case.possible_pos[2]}]\n'
            cfg += f'  running: {case.running}\n'
            cfg += f'  real_move_time: {case.real_move_time}\n'

        with open(case_file_path, 'w', encoding='utf-8') as file:
            file.write(cfg)

    def dict_2_case(self, data: dict) -> TestCase:
        region = [r for r in self.ctx.map_data.region_list if r.prl_id == data['region']][0]
        pos = Point(data['pos'][0], data['pos'][1])
        num = data['num']
        running = data['running']
        real_move_time = data.get('real_move_time', 0)
        possible_pos = data['possible_pos']
        tol = data.get('tol', 5)
        return TestCase(region, pos, num, running, possible_pos, real_move_time, tol)

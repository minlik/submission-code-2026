from typing import Optional, Sequence, Dict
from collections import defaultdict
import secrets
import random
from mha.syntax import Entity
from mha.config import Config
from .device import Device
from .room import Room
from .env import Outdoor
from .home import Home


__all__ = ['HomeSampler']


class HomeSampler(object):

    _LOAD_HOME_CONF = False

    @staticmethod
    def sample(entities: Sequence[Entity]) -> Home:
        try:
            from homemaker.home import Home as HMHome, DeviceInfo as HMDeviceInfo, Behavior as HMBehavior
        except ImportError:
            raise ImportError("please install homemaker to sample home data")
        
        if not HomeSampler._LOAD_HOME_CONF:
            HMDeviceInfo.load_config(Config.load_device())
            HMBehavior.load_config(Config.load_behavior())
            HomeSampler._LOAD_HOME_CONF = True
            
        home_data = HMHome.rand().to_dict()
        return HomeSampler.sample_by(home_data, entities)

    @staticmethod
    def sample_by(hm_home_data: Dict, entities: Sequence[Entity]) -> Home:
        # rooms
        room_dict = {room['id']: room for room in hm_home_data['house']['rooms']}
        for indoor in hm_home_data['indoor']:
            room_dict[indoor['room']]['env'] = indoor
        rooms = [Room.from_dict(d) for d in room_dict.values()]

        # outdoor
        outdoor = Outdoor.from_dict(hm_home_data['outdoor'])

        # devices
        cat2entities = defaultdict(list)
        for entity in entities:
            cat2entities[entity.userdata["subcategory"]].append(entity)

        devices = []
        for dev_data in hm_home_data['devices']:
            cand_entities = cat2entities.get(dev_data['type'], None)
            assert cand_entities is not None, f"no such entity of type '{dev_data['type']}'"
            entity = random.choice(cand_entities)
            did = secrets.token_urlsafe(6)[:8]
            devices.append(Device.make(entity=entity.rand(), did=did, room=dev_data["room"]))

        return Home(rooms, devices, outdoor)

    @staticmethod
    def sample_test() -> Home:
        try:
            from homemaker.home import Home as HMHome
        except ImportError:
            raise ImportError("please install homemaker to sample home data")
        
        home_data = HMHome.rand().to_dict()
        entities = HomeSampler.load_test_entities()

        # rooms
        room_dict = {room['id']: room for room in home_data['house']['rooms']}
        for indoor in home_data['indoor']:
            room_dict[indoor['room']]['env'] = indoor
        rooms = [Room.from_dict(d) for d in room_dict.values()]

        # outdoor
        outdoor = Outdoor.from_dict(home_data['outdoor'])

        # devices
        devices = []
        for i, entity in enumerate(entities):
            room = rooms[i % len(rooms)]
            did = secrets.token_urlsafe(6)[:8]
            devices.append(Device.make(entity=entity.rand(), did=did, room=room.id))

        # replenish devices
        if len(entities) < len(rooms):
            cnt = len(rooms) - len(entities)
            sel_entities = random.choices(entities, k=cnt)
            for room, entity in zip(rooms[-cnt:], sel_entities):
                did = secrets.token_urlsafe(6)[:8]
                devices.append(Device.make(entity=entity.rand(), did=did, room=room.id))

        return Home(rooms, devices, outdoor)


    @staticmethod
    def load_test_entities() -> Sequence[Entity]:
        if HomeSampler.__TEST_ENTITIES__ is None:
            HomeSampler.__TEST_ENTITIES__ = Entity.load(HomeSampler.__TEST_ENTITY_CONF__)
        return HomeSampler.__TEST_ENTITIES__


    __TEST_ENTITIES__: Optional[Sequence[Entity]] = None

    __TEST_ENTITY_CONF__ = """
- name: Yeelight Pro
  userdata:
    category: light
    subcategory: light
    brand: none
    spid: "100001"
    tags: [light]
  attributes:
  - name: state
    type: str
    options: ["on", "off"]
  - name: brightness
    type: int
    range: [1, 100]
    unit: percentage
  - name: hs_color
    type: tuple
    items:
      - type: float
        range: [0.0, 360]
        precision: 1.0
      - type: float
        range: [0, 100]
        precision: 1.0
  services:
  - name: turn_on
    code: self.state = "on"
  - name: turn_off
    code: self.state = "off"
  - name: set_brightness
    arguments:
      - name: brightness
        type: int
        range: [1, 100]
    code: self.brightness = brightness
  - name: set_hs_color
    arguments:
      - name: hs_color
        type: tuple
        items:
          - type: float
            range: [0.0, 360]
          - type: float
            range: [0, 100]
    code: self.hs_color = hs_color

    
- name: AC
  userdata:
    category: ac
    subcategory: ac
    brand: none
    spid: "100001"
    tags: [ac]
  attributes:
  - name: state
    type: str
    options: ["on", "off"]
  - name: target_temperature
    type: float
    range: [18.0, 30.0]
    unit: celsius
    precision: 1.0
  - name: current_temperature
    type: float
    range: [18.0, 30.0]
    unit: celsius
    precision: 1.0
  - name: hvac_mode
    type: str
    options: [heat, cool, dry, fan_only]
  - name: fan_mode
    type: str
    options: [fan_auto, fan_low, fan_medium, fan_high]
  services:
  - name: turn_on
    code: self.state = "on"
  - name: turn_off
    code: self.state = "off"
  - name: set_target_temperature
    arguments:
      - name: target_temperature
        type: float
        range: [18.0, 30.0]
        unit: celsius
        precision: 1.0
    code: self.target_temperature = target_temperature
  - name: set_hvac_mode
    arguments:
      - name: hvac_mode
        type: str
        options: [heat, cool, dry, fan_only]
    code: self.hvac_mode = hvac_mode
  - name: set_fan_mode
    arguments:
      - name: fan_mode
        type: str
        options: [fan_auto, fan_low, fan_medium, fan_high]
    code: self.fan_mode = fan_mode



- name: compound washing machine
  description: 复式洗衣机，上部有左、右两个桶，下部有一个桶，共三个桶

  userdata:
    brand: none
    category: wm
    spid: "20000006"
    subcategory: compound-washer
    tags: [wm, voice]

  components:
  - name: washer_left
    description: 上方左侧桶，为滚筒洗衣机。
    attributes:
      - name: work_state
        type: str
        options: [ idle, working, pause, finish ]
        description: |
          左桶整体运行状态，字符串类型。
          取值含义：
            - idle：待机状态，洗衣机未启动，可接受新的洗涤指令。
            - working：运行中，正在执行洗涤、漂洗或脱水等流程。
            - pause：暂停状态，用户主动暂停或开门导致程序中断，可随时恢复。
            - finish：已完成本次洗涤任务，可取出衣物或执行新的程序。

      - name: work_mode
        type: str
        options: [ normal, quick_wash, heavy_duty, delicate, cotton, wool, eco, rinse_and_spin, spin_only, drum_clean ]
        description: |
          当前选择的模式，字符串类型。
          各程序适用场景：
            - normal：标准洗，适合日常耐洗衣物，均衡时间与洁净度。
            - quick_wash：快洗，15–30 分钟完成，适合少量轻微污渍衣物。
            - heavy_duty：强力洗，高水温加长洗涤，适合重度污渍、工装、床单等。
            - delicate：轻柔洗，低转速、低水温，适合丝绸、蕾丝、内衣等娇贵面料。
            - cotton：棉麻专护，针对棉麻类衣物优化，防缩水、防褶皱。
            - wool：羊毛专护，获得国际羊毛局认证，低转速低水温，保护羊毛衫不变形。
            - eco：节能洗，低温主洗+多次漂洗，省水省电，适合普通脏污衣物。
            - rinse_and_spin：单漂洗+脱水，用于已手洗或过水衣物，去除残留洗涤剂。
            - spin_only：单脱水，仅执行高速甩干，适合手洗后快速脱水。
            - drum_clean：筒自洁，95 ℃高温高水位清洗内筒，去除霉菌与异味，建议每月一次空筒运行。

      - name: work_duration
        type: int
        range: [ 0, 86400 ]
        unit: second
        description: 正在运行任务的总时长，整数诶类型，单位秒，范围 0–86400 秒

      - name: child_lock_switch
        description: 童锁开关。true-童锁开启，false-童锁关闭
        type: bool

      - name: remaining_running_time
        description: 运行剩余时间, 以秒为单位。
        type: int
        range: [ 1, 86400 ]
        unit: second

      - name: appointment_left_time
        description: 预约剩余时间, 以秒为单位。
        type: int
        range: [ 1, 86400 ]
        unit: second

      - name: keep_fresh_switch
        description: 忘取无忧开关。true-开启，false-关闭
        type: bool

      - name: water_level
        description: 水位。支持0～7档，其中第0档表示无水位，第7档表示自动挡，其他档位数字对应水位依次增高
        type: int
        range: [ 0, 7 ]

      - name: dry_level
        description: 烘干程度。支持0～10档，其中第0档表示不烘干，其他档位数字对应烘干强度依次增高
        type: int
        range: [ 0, 10 ]

      - name: rinse_count
        description: 漂洗次数。支持0～5档，其中第0档表示智能漂洗，其他档位数字对应漂洗次数
        type: int
        range: [ 0, 5 ]

      - name: temperature_level
        description: ｜
          温度档位，具体编号意义如下：
          0-智能温度
          1-冷水
          2-20度
          3-30度
          4-40度
          5-50度
          6-60度
          7-70度
          8-80度
          9-90度
        type: int
        range: [ 0, 9 ]

      - name: dehydration_time_level
        description: ｜
          脱水时间档位，具体编号意义如下：
          1-10分钟
          2-20分钟
          3-30分钟
        type: int
        range: [ 1, 3 ]

      - name: softener_lack_state
        description: 洗衣液缺液状态。true-缺液，false-未缺液
        type: bool

      - name: detergent_lack_state
        description: 柔顺剂缺液状态。true-缺液，false-未缺液
        type: bool


    services:
      - name: start
        description: 启动左桶洗衣机，按指定模式与时长开始洗涤流程。
        arguments:
          - name: work_mode
            type: str
            options: [ normal, quick_wash, heavy_duty, delicate, cotton, wool, eco, rinse_and_spin, spin_only, drum_clean ]
            description: |
              当前选择的模式，字符串类型。
              各程序适用场景：
                - normal：标准洗，适合日常耐洗衣物，均衡时间与洁净度。
                - quick_wash：快洗，15–30 分钟完成，适合少量轻微污渍衣物。
                - heavy_duty：强力洗，高水温加长洗涤，适合重度污渍、工装、床单等。
                - delicate：轻柔洗，低转速、低水温，适合丝绸、蕾丝、内衣等娇贵面料。
                - cotton：棉麻专护，针对棉麻类衣物优化，防缩水、防褶皱。
                - wool：羊毛专护，获得国际羊毛局认证，低转速低水温，保护羊毛衫不变形。
                - eco：节能洗，低温主洗+多次漂洗，省水省电，适合普通脏污衣物。
                - rinse_and_spin：单漂洗+脱水，用于已手洗或过水衣物，去除残留洗涤剂。
                - spin_only：单脱水，仅执行高速甩干，适合手洗后快速脱水。
                - drum_clean：筒自洁，95°高温高水位清洗内筒，去除霉菌与异味，建议每月一次空筒运行。

          - name: work_duration
            type: int
            unit: second
            range: [ 0, 86400 ]
            description: 预计运行任务的总时长，整数诶类型，单位秒，范围 0–86400 秒

          - name: child_lock_switch
            description: 童锁开关状态。true-童锁开启，false-童锁关闭
            type: bool
            value: true

          - name: keep_fresh_switch
            description: 忘取无忧开关。true-开启，false-关闭
            type: bool
            value: true

          - name: water_level
            description: 水位。支持0～7档，其中第0档表示无水位，第7档表示自动挡，其他档位数字对应水位依次增高
            type: int
            range: [ 0, 7 ]
            value: 3

          - name: dry_level
            description: 烘干程度。支持0～10档，其中第0档表示不烘干，其他档位数字对应烘干强度依次增高
            type: int
            range: [ 0, 10 ]
            value: 0

          - name: rinse_count
            description: 漂洗次数。支持1～5档，其中第0档表示智能漂洗，其他档位数字对应漂洗次数
            type: int
            range: [ 1, 5 ]
            value: 1

          - name: temperature_level
            description: ｜
              温度档位，具体编号意义如下：
              0-智能温度
              1-冷水
              2-20度
              3-30度
              4-40度
              5-50度
              6-60度
              7-70度
              8-80度
              9-90度
            type: int
            range: [ 0, 9 ]
            value: 0

          - name: dehydration_time_level
            description: ｜
              脱水时间档位，具体编号意义如下：
              1-10分钟
              2-20分钟
              3-30分钟
            type: int
            range: [ 1, 3 ]
            value: 2

        code: |
          if work_mode == 'drum_clean':
              self.work_state = 'working'
              self.work_mode = work_mode
              self.child_lock_switch = child_lock_switch
              self.temperature_level = temperature_level
              self.work_duration = work_duration
          
          elif work_mode not in ['cotton', 'wool'] or ( work_mode in ['cotton', 'wool'] and not self.detergent_lack_state ):
            if not self.softener_lack_state:
                self.work_state = 'working'
                self.work_mode = work_mode
                self.child_lock_switch = child_lock_switch
                self.keep_fresh_switch = keep_fresh_switch
                self.water_level = water_level
                self.dry_level = dry_level
                self.rinse_count = rinse_count
                self.temperature_level = temperature_level
                self.dehydration_time_level = dehydration_time_level
                self.work_duration = work_duration
              

      - name: stop
        description: 立即停止当前正在运行的洗涤程序，并清空剩余时间
        code: |
          self.work_state = "idle"
          self.work_duration = None

      - name: pause
        description: 暂停正在运行的程序，保留当前剩余时间与模式
        code: self.work_state = "pause"

      - name: resume
        description: 从暂停状态恢复运行，继续执行被中断的洗涤程序
        code: |
          if self.work_state == "pause":
            self.work_state = 'working'


  - name: washer_right
    description: 上方右侧桶，为滚筒洗衣机。
    attributes:
      - name: work_state
        type: str
        options: [ idle, working, pause, finish ]
        description: |
          右桶整体运行状态，字符串类型。
          取值含义：
            - idle：待机状态，洗衣机未启动，可接受新的洗涤指令。
            - working：运行中，正在执行洗涤、漂洗或脱水等流程。
            - pause：暂停状态，用户主动暂停或开门导致程序中断，可随时恢复。
            - finish：已完成本次洗涤任务，可取出衣物或执行新的程序。

      - name: work_mode
        type: str
        options: [ normal, quick_wash, heavy_duty, delicate, cotton, wool, eco, rinse_and_spin, spin_only, drum_clean ]
        description: |
          当前选择的模式，字符串类型。
          各程序适用场景：
            - normal：标准洗，适合日常耐洗衣物，均衡时间与洁净度。
            - quick_wash：快洗，15–30 分钟完成，适合少量轻微污渍衣物。
            - heavy_duty：强力洗，高水温加长洗涤，适合重度污渍、工装、床单等。
            - delicate：轻柔洗，低转速、低水温，适合丝绸、蕾丝、内衣等娇贵面料。
            - cotton：棉麻专护，针对棉麻类衣物优化，防缩水、防褶皱。
            - wool：羊毛专护，获得国际羊毛局认证，低转速低水温，保护羊毛衫不变形。
            - eco：节能洗，低温主洗+多次漂洗，省水省电，适合普通脏污衣物。
            - rinse_and_spin：单漂洗+脱水，用于已手洗或过水衣物，去除残留洗涤剂。
            - spin_only：单脱水，仅执行高速甩干，适合手洗后快速脱水。
            - drum_clean：筒自洁，95 ℃高温高水位清洗内筒，去除霉菌与异味，建议每月一次空筒运行。

      - name: work_duration
        type: int
        range: [ 0, 86400 ]
        unit: second
        description: 正在运行任务的总时长，整数诶类型，单位秒，范围 0–86400 秒

      - name: child_lock_switch
        description: 童锁开关。true-童锁开启，false-童锁关闭
        type: bool

      - name: remaining_running_time
        description: 运行剩余时间, 以秒为单位。
        type: int
        range: [ 1, 86400 ]
        unit: second

      - name: appointment_left_time
        description: 预约剩余时间, 以秒为单位。
        type: int
        range: [ 1, 86400 ]
        unit: second

      - name: keep_fresh_switch
        description: 忘取无忧开关。true-开启，false-关闭
        type: bool

      - name: water_level
        description: 水位。支持0～7档，其中第0档表示无水位，第7档表示自动挡，其他档位数字对应水位依次增高
        type: int
        range: [ 0, 7 ]

      - name: dry_level
        description: 烘干程度。支持0～10档，其中第0档表示不烘干，其他档位数字对应烘干强度依次增高
        type: int
        range: [ 0, 10 ]

      - name: rinse_count
        description: 漂洗次数。支持0～5档，其中第0档表示智能漂洗，其他档位数字对应漂洗次数
        type: int
        range: [ 0, 5 ]

      - name: temperature_level
        description: ｜
          温度档位，具体编号意义如下：
          0-智能温度
          1-冷水
          2-20度
          3-30度
          4-40度
          5-50度
          6-60度
          7-70度
          8-80度
          9-90度
        type: int
        range: [ 0, 9 ]

      - name: dehydration_time_level
        description: ｜
          脱水时间档位，具体编号意义如下：
          1-10分钟
          2-20分钟
          3-30分钟
        type: int
        range: [ 1, 3 ]

      - name: softener_lack_state
        description: 洗衣液缺液状态。true-缺液，false-未缺液
        type: bool

      - name: detergent_lack_state
        description: 柔顺剂缺液状态。true-缺液，false-未缺液
        type: bool


    services:
      - name: start
        description: 启动右桶洗衣机，按指定模式与时长开始洗涤流程。
        arguments:
          - name: work_mode
            type: str
            options: [ normal, quick_wash, heavy_duty, delicate, cotton, wool, eco, rinse_and_spin, spin_only, drum_clean ]
            description: |
              当前选择的模式，字符串类型。
              各程序适用场景：
                - normal：标准洗，适合日常耐洗衣物，均衡时间与洁净度。
                - quick_wash：快洗，15–30 分钟完成，适合少量轻微污渍衣物。
                - heavy_duty：强力洗，高水温加长洗涤，适合重度污渍、工装、床单等。
                - delicate：轻柔洗，低转速、低水温，适合丝绸、蕾丝、内衣等娇贵面料。
                - cotton：棉麻专护，针对棉麻类衣物优化，防缩水、防褶皱。
                - wool：羊毛专护，获得国际羊毛局认证，低转速低水温，保护羊毛衫不变形。
                - eco：节能洗，低温主洗+多次漂洗，省水省电，适合普通脏污衣物。
                - rinse_and_spin：单漂洗+脱水，用于已手洗或过水衣物，去除残留洗涤剂。
                - spin_only：单脱水，仅执行高速甩干，适合手洗后快速脱水。
                - drum_clean：筒自洁，95°高温高水位清洗内筒，去除霉菌与异味，建议每月一次空筒运行。

          - name: work_duration
            type: int
            unit: second
            range: [ 0, 86400 ]
            description: 预计运行任务的总时长，整数诶类型，单位秒，范围 0–86400 秒

          - name: child_lock_switch
            description: 童锁开关状态。true-童锁开启，false-童锁关闭
            type: bool
            value: true

          - name: keep_fresh_switch
            description: 忘取无忧开关。true-开启，false-关闭
            type: bool
            value: true

          - name: water_level
            description: 水位。支持0～7档，其中第0档表示无水位，第7档表示自动挡，其他档位数字对应水位依次增高
            type: int
            range: [ 0, 7 ]
            value: 3

          - name: dry_level
            description: 烘干程度。支持0～10档，其中第0档表示不烘干，其他档位数字对应烘干强度依次增高
            type: int
            range: [ 0, 10 ]
            value: 0

          - name: rinse_count
            description: 漂洗次数。支持1～5档，其中第0档表示智能漂洗，其他档位数字对应漂洗次数
            type: int
            range: [ 1, 5 ]
            value: 1

          - name: temperature_level
            description: ｜
              温度档位，具体编号意义如下：
              0-智能温度
              1-冷水
              2-20度
              3-30度
              4-40度
              5-50度
              6-60度
              7-70度
              8-80度
              9-90度
            type: int
            range: [ 0, 9 ]
            value: 0

          - name: dehydration_time_level
            description: ｜
              脱水时间档位，具体编号意义如下：
              1-10分钟
              2-20分钟
              3-30分钟
            type: int
            range: [ 1, 3 ]
            value: 2

        code: |
          if work_mode == 'drum_clean':
              self.work_state = 'working'
              self.work_mode = work_mode
              self.child_lock_switch = child_lock_switch
              self.temperature_level = temperature_level
              self.work_duration = work_duration
          
          elif work_mode not in ['cotton', 'wool'] or ( work_mode in ['cotton', 'wool'] and not self.detergent_lack_state ):
            if not self.softener_lack_state:
                self.work_state = 'working'
                self.work_mode = work_mode
                self.child_lock_switch = child_lock_switch
                self.keep_fresh_switch = keep_fresh_switch
                self.water_level = water_level
                self.dry_level = dry_level
                self.rinse_count = rinse_count
                self.temperature_level = temperature_level
                self.dehydration_time_level = dehydration_time_level
                self.work_duration = work_duration
              

      - name: stop
        description: 立即停止当前正在运行的洗涤程序，并清空剩余时间
        code: |
          self.work_state = "idle"
          self.work_duration = None

      - name: pause
        description: 暂停正在运行的程序，保留当前剩余时间与模式
        code: self.work_state = "pause"

      - name: resume
        description: 从暂停状态恢复运行，继续执行被中断的洗涤程序
        code: |
          if self.work_state == "pause":
            self.work_state = 'working'
          
          

  - name: washer_down
    description: 下方桶，为滚筒洗衣机。
    attributes:
      - name: work_state
        type: str
        options: [ idle, working, pause, finish ]
        description: |
          下桶整体运行状态，字符串类型。
          取值含义：
            - idle：待机状态，洗衣机未启动，可接受新的洗涤指令。
            - working：运行中，正在执行洗涤、漂洗或脱水等流程。
            - pause：暂停状态，用户主动暂停或开门导致程序中断，可随时恢复。
            - finish：已完成本次洗涤任务，可取出衣物或执行新的程序。

      - name: work_mode
        type: str
        options: [ normal, quick_wash, heavy_duty, delicate, cotton, wool, eco, rinse_and_spin, spin_only, drum_clean ]
        description: |
          当前选择的模式，字符串类型。
          各程序适用场景：
            - normal：标准洗，适合日常耐洗衣物，均衡时间与洁净度。
            - quick_wash：快洗，15–30 分钟完成，适合少量轻微污渍衣物。
            - heavy_duty：强力洗，高水温加长洗涤，适合重度污渍、工装、床单等。
            - delicate：轻柔洗，低转速、低水温，适合丝绸、蕾丝、内衣等娇贵面料。
            - cotton：棉麻专护，针对棉麻类衣物优化，防缩水、防褶皱。
            - wool：羊毛专护，获得国际羊毛局认证，低转速低水温，保护羊毛衫不变形。
            - eco：节能洗，低温主洗+多次漂洗，省水省电，适合普通脏污衣物。
            - rinse_and_spin：单漂洗+脱水，用于已手洗或过水衣物，去除残留洗涤剂。
            - spin_only：单脱水，仅执行高速甩干，适合手洗后快速脱水。
            - drum_clean：筒自洁，95 ℃高温高水位清洗内筒，去除霉菌与异味，建议每月一次空筒运行。

      - name: work_duration
        type: int
        range: [ 0, 86400 ]
        unit: second
        description: 正在运行任务的总时长，整数诶类型，单位秒，范围 0–86400 秒

      - name: child_lock_switch
        description: 童锁开关。true-童锁开启，false-童锁关闭
        type: bool

      - name: remaining_running_time
        description: 运行剩余时间, 以秒为单位。
        type: int
        range: [ 1, 86400 ]
        unit: second

      - name: appointment_left_time
        description: 预约剩余时间, 以秒为单位。
        type: int
        range: [ 1, 86400 ]
        unit: second

      - name: keep_fresh_switch
        description: 忘取无忧开关。true-开启，false-关闭
        type: bool

      - name: water_level
        description: 水位。支持0～7档，其中第0档表示无水位，第7档表示自动挡，其他档位数字对应水位依次增高
        type: int
        range: [ 0, 7 ]

      - name: dry_level
        description: 烘干程度。支持0～10档，其中第0档表示不烘干，其他档位数字对应烘干强度依次增高
        type: int
        range: [ 0, 10 ]

      - name: rinse_count
        description: 漂洗次数。支持0～5档，其中第0档表示智能漂洗，其他档位数字对应漂洗次数
        type: int
        range: [ 0, 5 ]

      - name: temperature_level
        description: ｜
          温度档位，具体编号意义如下：
          0-智能温度
          1-冷水
          2-20度
          3-30度
          4-40度
          5-50度
          6-60度
          7-70度
          8-80度
          9-90度
        type: int
        range: [ 0, 9 ]

      - name: dehydration_time_level
        description: ｜
          脱水时间档位，具体编号意义如下：
          1-10分钟
          2-20分钟
          3-30分钟
        type: int
        range: [ 1, 3 ]

      - name: softener_lack_state
        description: 洗衣液缺液状态。true-缺液，false-未缺液
        type: bool

      - name: detergent_lack_state
        description: 柔顺剂缺液状态。true-缺液，false-未缺液
        type: bool


    services:
      - name: start
        description: 启动下桶洗衣机，按指定模式与时长开始洗涤流程。
        arguments:
          - name: work_mode
            type: str
            options: [ normal, quick_wash, heavy_duty, delicate, cotton, wool, eco, rinse_and_spin, spin_only, drum_clean ]
            description: |
              当前选择的模式，字符串类型。
              各程序适用场景：
                - normal：标准洗，适合日常耐洗衣物，均衡时间与洁净度。
                - quick_wash：快洗，15–30 分钟完成，适合少量轻微污渍衣物。
                - heavy_duty：强力洗，高水温加长洗涤，适合重度污渍、工装、床单等。
                - delicate：轻柔洗，低转速、低水温，适合丝绸、蕾丝、内衣等娇贵面料。
                - cotton：棉麻专护，针对棉麻类衣物优化，防缩水、防褶皱。
                - wool：羊毛专护，获得国际羊毛局认证，低转速低水温，保护羊毛衫不变形。
                - eco：节能洗，低温主洗+多次漂洗，省水省电，适合普通脏污衣物。
                - rinse_and_spin：单漂洗+脱水，用于已手洗或过水衣物，去除残留洗涤剂。
                - spin_only：单脱水，仅执行高速甩干，适合手洗后快速脱水。
                - drum_clean：筒自洁，95°高温高水位清洗内筒，去除霉菌与异味，建议每月一次空筒运行。

          - name: work_duration
            type: int
            unit: second
            range: [ 0, 86400 ]
            description: 预计运行任务的总时长，整数诶类型，单位秒，范围 0–86400 秒

          - name: child_lock_switch
            description: 童锁开关状态。true-童锁开启，false-童锁关闭
            type: bool
            value: true

          - name: keep_fresh_switch
            description: 忘取无忧开关。true-开启，false-关闭
            type: bool
            value: true

          - name: water_level
            description: 水位。支持0～7档，其中第0档表示无水位，第7档表示自动挡，其他档位数字对应水位依次增高
            type: int
            range: [ 0, 7 ]
            value: 3

          - name: dry_level
            description: 烘干程度。支持0～10档，其中第0档表示不烘干，其他档位数字对应烘干强度依次增高
            type: int
            range: [ 0, 10 ]
            value: 0

          - name: rinse_count
            description: 漂洗次数。支持1～5档，其中第0档表示智能漂洗，其他档位数字对应漂洗次数
            type: int
            range: [ 1, 5 ]
            value: 1

          - name: temperature_level
            description: ｜
              温度档位，具体编号意义如下：
              0-智能温度
              1-冷水
              2-20度
              3-30度
              4-40度
              5-50度
              6-60度
              7-70度
              8-80度
              9-90度
            type: int
            range: [ 0, 9 ]
            value: 0

          - name: dehydration_time_level
            description: ｜
              脱水时间档位，具体编号意义如下：
              1-10分钟
              2-20分钟
              3-30分钟
            type: int
            range: [ 1, 3 ]
            value: 2

        code: |
          if work_mode == 'drum_clean':
              self.work_state = 'working'
              self.work_mode = work_mode
              self.child_lock_switch = child_lock_switch
              self.temperature_level = temperature_level
              self.work_duration = work_duration
          
          elif work_mode not in ['cotton', 'wool'] or ( work_mode in ['cotton', 'wool'] and not self.detergent_lack_state ):
            if not self.softener_lack_state:
                self.work_state = 'working'
                self.work_mode = work_mode
                self.child_lock_switch = child_lock_switch
                self.keep_fresh_switch = keep_fresh_switch
                self.water_level = water_level
                self.dry_level = dry_level
                self.rinse_count = rinse_count
                self.temperature_level = temperature_level
                self.dehydration_time_level = dehydration_time_level
                self.work_duration = work_duration
              

      - name: stop
        description: 立即停止当前正在运行的洗涤程序，并清空剩余时间
        code: |
          self.work_state = "idle"
          self.work_duration = None

      - name: pause
        description: 暂停正在运行的程序，保留当前剩余时间与模式
        code: self.work_state = "pause"

      - name: resume
        description: 从暂停状态恢复运行，继续执行被中断的洗涤程序
        code: |
          if self.work_state == "pause":
            self.work_state = 'working'


  - name: voice_broadcast
    description: 语音播报功能，三桶共用。
    attributes:
      - name: prompt_tone_switch
        description: 提示音。打开：on, 关闭：off
        type: str
        options: [ "on", "off" ]
      - name: volumn
        description: 提示音音量。分三挡 low-小，middle-中，high-大。依次递增150%
        type: str
        options: ['low', 'middle', 'high']
    services:
      - name: set_prompt_tone_switch
        description: 打开或关闭提示音。
        arguments:
          - name: prompt_tone_switch
            type: str
            options: [ "on", "off" ]
            description: 提示音开关。打开：on, 关闭：off。
        code: self.prompt_tone_switch = prompt_tone_switch

      - name: set_volumn
        description: 设定提示音音量。
        arguments:
          - name: volumn
            type: str
            options: ['low', 'middle', 'high']
            description: 提示音音量。
        code: |
          self.prompt_tone_switch = "on"
          self.volumn = volumn

- name: 创明智能窗帘（卷帘）
  description: 创明智能窗帘（卷帘）
  attributes:
  - name: alias
    description: 设备的别名，通常由用户设置
    type: str
  - name: position
    description: 窗帘开的百分比。0表示全关闭，100表示全打开
    type: int
    range: [0, 100]
    unit: percentage
  services:
  - name: open
    description: 打开窗帘
    code: |
      self.position = 100
  - name: close
    description: 关闭窗帘
    code: |
      self.position = 0
  - name: set_position
    description: 设置窗帘关合的位置，并开始开/合窗帘
    arguments:
    - name: position
      description: 窗帘开的百分比。0表示全关闭，100表示全打开
      type: int
      range: [0, 100]
    code: self.position = position
  userdata:
    spid: '10006363'
    brand: wintom
    category: cover
    subcategory: cover
    tags: [cover]
"""



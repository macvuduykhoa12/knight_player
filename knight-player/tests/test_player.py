"""Test logic của Player (không cần cửa sổ game). Chạy:  python -m pytest -q"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame  # noqa: E402

from knight_player import Player, PlayerConfig  # noqa: E402


class Keys(dict):
    """Giả lập pygame.key.get_pressed(): phím không có trong dict = không bấm."""

    def __getitem__(self, k):
        return self.get(k, False)


class Dummy:
    def __init__(self, x, y, hp=4):
        self.rect = pygame.Rect(x, y, 28, 52)
        self.hp = hp
        self.hits = []

    def take_damage(self, amount, direction):
        self.hp -= amount
        self.hits.append((amount, direction))


GROUND = pygame.Rect(-1000, 480, 5000, 60)
NO_KEYS = Keys()


def make_player():
    p = Player(200, 400)
    for _ in range(30):                       # rơi xuống đất
        p.update(NO_KEYS, [GROUND])
    return p


def test_lands_on_ground():
    p = make_player()
    assert p.on_ground
    assert p.rect.bottom == GROUND.top


def test_moves_and_faces_direction():
    p = make_player()
    x0 = p.rect.x
    for _ in range(10):
        p.update(Keys({pygame.K_a: True}), [GROUND])
    assert p.rect.x < x0 and p.facing == -1
    for _ in range(10):
        p.update(Keys({pygame.K_RIGHT: True}), [GROUND])
    assert p.facing == 1


def test_jump_only_from_ground():
    p = make_player()
    assert p.jump() is True
    p.update(NO_KEYS, [GROUND])
    assert not p.on_ground and p.vy < 0
    assert p.jump() is False                  # đang ở trên không


def test_wall_blocks_movement():
    wall = pygame.Rect(260, 0, 40, 600)
    p = make_player()
    for _ in range(60):
        p.update(Keys({pygame.K_d: True}), [GROUND, wall])
    assert p.rect.right == wall.left and p.hit_wall


def test_melee_hits_each_enemy_once_per_swing():
    p = make_player()
    e = Dummy(p.rect.right + 10, p.rect.y)
    assert p.melee()
    hits = []
    for _ in range(25):
        hits += p.update(NO_KEYS, [GROUND], [e])
    assert e.hp == 4 - p.cfg.melee_damage and len(e.hits) == 1
    assert hits and hits[0][2] == "melee"


def test_melee_ignores_enemy_behind():
    p = make_player()
    e = Dummy(p.rect.left - 60, p.rect.y)
    p.melee()
    for _ in range(25):
        p.update(NO_KEYS, [GROUND], [e])
    assert e.hp == 4


def test_arrow_is_released_after_draw_and_flies_straight():
    p = make_player()
    assert p.shoot()
    for _ in range(p.cfg.bow_draw_frames - 1):
        p.update(NO_KEYS, [GROUND])
        assert not p.arrows                   # chưa thả tên khi còn đang giương
    p.update(NO_KEYS, [GROUND])
    assert len(p.arrows) == 1
    arrow = p.arrows[0]
    y0, x0 = arrow.y, arrow.x
    for _ in range(20):
        p.update(NO_KEYS, [GROUND])
    assert arrow.y == y0                      # không có trọng lực: bay ngang
    assert arrow.x > x0 + 100


def test_arrow_hits_enemy_and_disappears():
    p = make_player()
    e = Dummy(p.rect.right + 300, GROUND.top - 52)
    p.shoot()
    for _ in range(80):
        p.update(NO_KEYS, [GROUND], [e])
    assert e.hp == 4 - p.cfg.arrow_damage
    assert not p.arrows


def test_arrow_stopped_by_wall():
    wall = pygame.Rect(700, 0, 40, 600)
    p = make_player()
    p.shoot()
    for _ in range(100):
        p.update(NO_KEYS, [GROUND, wall])
    assert not p.arrows


def test_take_damage_invulnerability_and_knockback():
    p = make_player()
    assert p.take_damage(1, source_x=p.rect.centerx - 50) is True
    assert p.hp == p.cfg.max_hp - 1 and p.vx > 0      # bị hất ra xa kẻ đánh (kẻ đánh ở bên trái)
    assert p.take_damage(1) is False                  # đang bất tử
    assert p.hp == p.cfg.max_hp - 1


def test_damage_cancels_bow_draw():
    p = make_player()
    p.shoot()
    p.update(NO_KEYS, [GROUND])
    p.take_damage(1)
    for _ in range(60):
        p.update(NO_KEYS, [GROUND])
    assert not p.arrows


def test_death_and_respawn():
    cfg = PlayerConfig(max_hp=1)
    p = Player(200, 400, cfg)
    events = []
    p.on_event = lambda name, **info: events.append(name)
    p.take_damage(1)
    assert p.is_dead and "died" in events
    assert p.melee() is False and p.shoot() is False
    p.respawn(50, 50)
    assert not p.is_dead and p.rect.topleft == (50, 50)

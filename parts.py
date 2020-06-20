import math

import pymunk

id2partclass = {}


class Part:
    def __init__(self, img, connectlist, mass, thrust, powcon, powgen, powstr, numvert, pid):
        self.connected = connectlist
        self.connectedto = None
        self.direction = 0
        # --#
        self.phased = False
        self.owner = None
        self.mass = mass
        self.image = img
        self.thrust = thrust
        self.powcon = powcon
        self.powgen = powgen
        self.powstr = powstr
        self.body = pymunk.Body()
        # self.body.dampening = 0.9
        self.poly = pymunk.Poly(self.body, [(math.cos(2 * math.pi * i / numvert + math.pi / 4) * 12.5,
                                             math.sin(2 * math.pi * i / numvert + math.pi / 4) * 12.5) for i in range(
            numvert)])
        self.poly.elasticity = 0
        self.poly.mass = mass
        self.poly.friction = 0.5
        self.body.filter = pymunk.ShapeFilter(categories=0b01, mask=0b11)
        self.body.collision_type = 1
        self.poly.part = self
        self.pinjoint = None
        self.rljoint = None
        self.iscargo = False
        self.fired = False
        self.partid = pid

    def getquadranthelper(self):
        if self.connectedto is False or self.connectedto is None:
            return [0, 0]
        h = self.connectedto.getquadrant()
        h[0] += 1 if self.direction == 0 else 0
        h[0] -= 1 if self.direction == 2 else 0
        h[1] += 1 if self.direction == 1 else 0
        h[1] -= 1 if self.direction == 3 else 0
        return h

    def getquadrant(self):
        h = self.getquadranthelper()
        if h[0] > 0:
            h[0] = 1
        if h[0] < 0:
            h[0] = -1
        if h[1] > 0:
            h[1] = 1
        if h[1] < 0:
            h[1] = -1
        return h

    def getequivdir(self):
        if self.connectedto is False or self.connectedto is None:
            return 2
        sconnectedto = self.connectedto.getequivdir()
        if sconnectedto == 0:
            return (2 + self.direction) % 4
        if sconnectedto == 1:
            return (3 + self.direction) % 4
        if sconnectedto == 2:
            return (4 + self.direction) % 4
        return (1 + self.direction) % 4

    def getfire(self):
        q = self.getquadrant()
        d = self.getequivdir()
        # Directions: Front Right Back Left
        a = [d == 2, False, d == 0, False]
        if q[1] == -1:
            if d == 0:
                a[1] = True
            if d == 2:
                a[3] = True
        if q[1] == 1:
            if d == 0:
                a[3] = True
            if d == 2:
                a[1] = True
        if q[0] == -1:
            if d == 1:
                a[3] = True
            if d == 3:
                a[1] = True
        if q[0] == 1:
            if d == 1:
                a[1] = True
            if d == 3:
                a[3] = True
        return a

    def getequivangle(self):
        if self.connectedto is False or self.connectedto is None:
            return self.body.angle
        return self.body.angle + self.connectedto.getequivangle()

    def getpower(self):
        ans = self.powstr
        for part in self.connected:
            if part is None or part is False:
                continue
            ans += part.getpower()
        return ans


class User(Part):
    def __init__(self, usernm):
        super().__init__("user", [None, None, None, None], 30, 100, 2, 3, 1000, 4, 0)
        self.usernm = usernm
        self.direction = 0
        self.rotation = 0
        self.fuel = 1000

    def tick(self): ...


id2partclass[0] = User


class Cargo(Part):
    def __init__(self):
        super().__init__("cargo", [False, False, False, False], 15, 0, 0, 0, 300, 4, 1)
        self.iscargo = True


id2partclass[1] = Cargo


class LandingBooster(Part):
    def __init__(self):
        super().__init__("landing_booster", [False, False, False, False], 15, 100, 2, 0, 150, 4, 2)


id2partclass[2] = LandingBooster


class Booster(Part):
    def __init__(self):
        super().__init__("booster", [False, False, False, False], 15, 100, 2, 0, 250, 4, 3)


id2partclass[3] = Booster


class EcoBooster(Part):
    def __init__(self):
        super().__init__("eco_booster", [False, False, False, False], 15, 90, 1, 0, 200, 4, 4)


id2partclass[4] = EcoBooster


class HubBooster(Part):
    def __init__(self):
        super().__init__("hub_booster", [False, None, False, None], 15, 90, 2, 0, 300, 4, 5)


id2partclass[5] = HubBooster


class SuperBooster(Part):
    def __init__(self):
        super().__init__("super_booster", [False, False, False, False], 15, 350, 3, 0, 150, 4, 6)


id2partclass[6] = SuperBooster


class SolarPanel(Part):
    def __init__(self):
        super().__init__("solar_panel", [False, False, False, False], 15, 0, 0, 1, 200, 4, 7)


id2partclass[7] = SolarPanel


class SuperSolarPanel(Part):
    def __init__(self):
        super().__init__("super_solar", [False, False, False, False], 15, 0, 0, 2, 250, 4, 8)


id2partclass[8] = SuperSolarPanel


class Hub(Part):
    def __init__(self):
        super().__init__("hub", [False, None, None, None], 15, 0, 0, 0, 250, 4, 9)


id2partclass[9] = Hub


class PoweredHub(Part):
    def __init__(self):
        super().__init__("powered_hub", [False, None, None, None], 15, 0, 0, 0, 900, 4, 10)


id2partclass[10] = PoweredHub


class FadyHub(Part):
    def __init__(self):
        super().__init__("fady_hub", [False, None, None, None], 15, 0, 0, 0, 1000, 4, 11)


id2partclass[11] = FadyHub


class PentagonHub(Part):
    def __init__(self):
        super().__init__("pentagon_hub", [False, None, None, None, None], 15, 0, 0, 0, 250, 5, 12)


id2partclass[12] = PentagonHub


class LandingGear(Part):
    def __init__(self):
        super().__init__("landing_gear", [False, False, False, False], 15, 0, 0, 0, 0, 200, 13)


id2partclass[13] = LandingGear


class GeneratorHub(Part):
    def __init__(self):
        super().__init__("generator_hub", [False, None, None, None], 15, 0, 0, 3, 0, 4, 14)


id2partclass[14] = GeneratorHub

import math
import random

import pymunk

import gamedaemon


class planet:
    def __init__(self, d, r, c, m, partclass, partargs, partchance, color, space, img, eradius):
        self.f = random.random() * math.pi
        self.part = partclass
        self.partargs = partargs
        self.partchance = partchance
        self.distance = d
        self.center = c
        self.color = color
        self.radius = r
        self.body = pymunk.Body()
        self.circle = pymunk.Circle(self.body, r)
        self.body.body_type = pymunk.Body.KINEMATIC  # planets have... infinite mass
        self.mass = m  # except... they don't?
        self.img = img
        self.circle.mass = m
        self.eradius = eradius
        if d != 0:
            x = self.distance * math.sin(self.f) + c.body.position.x
            y = self.distance * math.cos(self.f) + c.body.position.y
            self.body.position = (x, y)
        else:
            self.body.position.x = 0
            self.body.position.y = 0
        if random.random() < .5:
            self.body.position.x *= -1
        if random.random() < .5:
            self.body.position.y *= -1
        self.body.filter = pymunk.ShapeFilter(categories=0b1, mask=0b11)
        self.body.collision_type = 0
        self.circle.planet = self
        self.circle.friction = 0.5
        space.add(self.body, self.circle)

    def tick(self):
        if random.random() < self.partchance:
            gamedaemon.createpart(self, self.part(*self.partargs))
        self.f += .0001


def planetcollisionhandler(arbiter, space, data):
    try:
        planet = arbiter.shapes[0].planet
        part = arbiter.shapes[1].part
    except AttributeError:
        try:
            planet = arbiter.shapes[1].planet
            part = arbiter.shapes[0].part
        except AttributeError:
            return True
    if part is not None and part.owner is not None and planet.partchance == -1:
        turncargointoparts(gamedaemon.userparts[part.owner], planet, space)
    if part is not None and part.owner is not None:
        gamedaemon.userparts[part.owner].fuel = gamedaemon.userparts[part.owner].getpower()
    return True


def turncargointoparts(part, planet, space):
    if part == None or part == False or part.owner == None: return
    if part.iscargo:
        newpart = planet.part()
        newpart.connectedto = part.connectedto
        newpart.direction = part.direction
        newpart.owner = part.owner
        newpart.rotation = part.rotation
        gamedaemon.unattach(part, part.owner)
        newpart.connectedto.connected[part.direction] = newpart
        gamedaemon.allparts[gamedaemon.allparts.index(part)] = newpart
        gamedaemon.ownedparts[newpart.owner].append(newpart)
        space.remove(part.body, part.poly)
        space.add(newpart.body, newpart.poly)
        gamedaemon.attachpt(newpart)
        del gamedaemon.looseparts[part]
        return
    for p in part.connected:
        turncargointoparts(p, planet, space)

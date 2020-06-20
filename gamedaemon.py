import gc
import math
import random
import threading
import time
import traceback
import tornado.gen

import pymunk
from pymunk.constraint import PinJoint, RotaryLimitJoint
from pymunk.vec2d import Vec2d

import parts
import planet
import orjson as json

gc.enable()
userparts = {}
planets = []
looseparts = {}
allparts = []
userfire = {}
usermouse = {}
userctl = {}
ownedparts = {}
userrefiretimeout = {}
name2role = {}

space = pymunk.Space()
space.damping = .95
space.gravity = (0., 0.)
space.collision_slop = .1

# measure health
reps = [0 for i in range(10)]
timereps = [0 for i in range(10)]

def ignoreselfcollisons(arbiter, space_, data):
    planet.planetcollisionhandler(arbiter, space_, data)
    try:
        if arbiter.shapes[1].part.owner == arbiter.shapes[0].part.owner and arbiter.shapes[1].part.owner is not None:
            return False
    except AttributeError:
        ...
    try:
        if arbiter.shapes[0].planet:
            return True
    except AttributeError:
        ...
    try:
        if arbiter.shapes[1].planet:
            return True
    except AttributeError:
        ...
    try:
        if arbiter.shapes[0].part in userctl.values():
            return False
    except AttributeError:
        ...
    try:
        if arbiter.shapes[1].part in userctl.values():
            return False
    except AttributeError:
        ...
    return True


space.add_default_collision_handler().begin = ignoreselfcollisons


def getpartarray(part):
    if part is None:
        return None
    if part is False:
        return False
    return [part.partid, [getpartarray(p) for p in part.connected]]


def getshipstring(user):
    return json.dumps(getpartarray(userparts[user])).decode("utf-8")


def loadparts(partload, parent):
    for i in range(len(partload)):
        if partload[i] is None:
            parent.connected[i] = None
            continue
        if partload[i] is False:
            parent.connected[i] = False
            continue
        part = parts.id2partclass[partload[i][0]]()
        part.direction = i
        part.owner = parent.owner
        space.add(part.body, part.poly)
        allparts.append(part)
        parent.connected[i] = part
        part.connectedto = parent
        ownedparts[parent.owner].append(part)
        attachpt(part)
        b = ((part.body.angle - userparts[part.owner].body.angle) % (math.pi * 2))
        if 0 <= b < math.pi / 4:
            part.rotation = 0
        elif math.pi / 4 <= b < math.pi / 4 * 3:
            part.rotation = 3
        elif math.pi / 4 * 3 <= b < math.pi / 4 * 5:
            part.rotation = 2
        elif math.pi / 4 * 5 <= b < math.pi / 4 * 7:
            part.rotation = 1
        else:
            part.rotation = 0
        loadparts(partload[i][1], part)
    return parent


def adduser(usernm, shipstr, role):
    from math import sqrt
    try:
        userparts[usernm]
    except KeyError:
        ...
    else:
        return False
    name2role[usernm] = role
    userparts[usernm] = parts.User(usernm)
    userparts[usernm].owner = usernm
    x = 2. * (100. + planets[1].radius) * (random.random() - .5)
    y = (1. if random.random() >= .5 else -1.) * sqrt((100. + planets[1].radius) * (100. + planets[1].radius) - x * x)
    x += planets[1].body.position.x
    y += planets[1].body.position.y
    userparts[usernm].body.position = (x, y)
    allparts.append(userparts[usernm])
    space.add(userparts[usernm].body, userparts[usernm].poly)
    userfire[usernm] = [False, False, False, False]
    usermouse[usernm] = [False, 0, 0]
    userctl[usernm] = None
    ownedparts[usernm] = [userparts[usernm]]
    userrefiretimeout[usernm] = 0
    partload = json.loads(shipstr)
    loadparts(partload[1], userparts[usernm])
    return True


def mouse(user, mode, down, x, y):
    try:
        if mode:
            v = Vec2d(x, y)
            if usermouse[user][0] and userctl[user] is not None:
                userctl[user].body.angular_velocity = Vec2d(usermouse[user][1], usermouse[user][2]).get_angle_between(
                    v) - userctl[user].body.angle
            usermouse[user][1] = v.x
            usermouse[user][2] = v.y
        else:
            usermouse[user][0] = down
            if down:
                for part in allparts:
                    if not (part in ownedparts[user] or part in looseparts) or part in userparts.values():
                        continue

                    if abs(usermouse[user][1] + userparts[user].body.position.x - part.body.position.x) <= 12 and abs(
                            usermouse[user][2] + userparts[user].body.position.y - part.body.position.y) <= 12:
                        userctl[user] = part

                        if part.connectedto is not None:
                            unattach(part, user)

                        # So was this
                        try:
                            del looseparts[part]
                        except KeyError:
                            ...
                        ownedparts[user].append(part)
                        break
            else:
                if userctl[user] is not None:
                    userctl[user].body.velocity = Vec2d(0., 0.)
                    userctl[user] = None
    except Exception as e:
        print(e)
        print(traceback.format_exc())


def removepart(part):
    space.remove(part.body, part.poly)
    space.remove(part.rljoint)
    space.remove(part.pinjoint)
    allparts.remove(part)
    for p in part.connected:
        if p is not None and p is not False:
            removepart(p)


def removeuser(usernm):
    removepart(userparts[usernm])
    del userfire[usernm]
    del usermouse[usernm]
    del userctl[usernm]
    del ownedparts[usernm]
    del userrefiretimeout[usernm]
    del userparts[usernm]


def fixpos(part, user):
    if part == False or part is None:
        return
    if part.connectedto != False and part.connectedto is not None and part.pinjoint.impulse >= 1000:
        unattach(part, user)
    for part_ in part.connected:
        if part_ == part:
            continue  # bugs happen
        fixpos(part_, user)


def getthrustpart(part, n, realuser):
    if part == False or part is None:
        return ""
    code = ""
    if part not in userparts.values() and part.thrust != 0 and part.fired:
        code += "draw_fire(ctx, " + str(
            int(round(part.body.position.x - userparts[realuser].body.position.x))) + "," + str(
            int(round(part.body.position.y - userparts[realuser].body.position.y))) + "," + str(part.body.angle) + ");"
    for p in part.connected:
        code += getthrustpart(p, n, realuser)
    return code


def get_world_2(user):
    # Format: parts,planets,fuel,selfpos,selfvel
    # parts format: [id, position, velocity, fired (1 if true 0 if false), *usernm (if userpart), *role (if userpart), *fires (for each, 1 if true else 0, userpart only)]
    # planets format: [id, position, center]
    selfpos = userparts[user].body.position
    selfvel = userparts[user].body.velocity
    returnval = [[], [], userparts[user].fuel, [.1 * round(10 * selfpos.x), .1 * round(10 * selfpos.y)],
                 [.1 * round(10 * selfvel.x), .1 * round(10 * selfvel.y)]]
    # rotation not relevant to rendering
    for part in allparts:
        dx = part.body.position.x-userparts[user].body.position.x
        dy = part.body.position.y-userparts[user].body.position.y
        if dx * dx + dy * dy > 1000000:  # render distance
            continue
        pos = part.body.position
        vel = part.body.velocity
        returnval[0].append(
            [part.partid, [.1 * round(10 * pos.x), .1 * round(10 * pos.y), .1 * round(10 * part.body.angle)],
             [.1 * round(10 * vel.x), .1 * round(10 * vel.y), .1 * round(10 * part.body.angular_velocity)], 1 if part.fired else 0])
        try:
            returnval[0][-1].append(part.usernm)
            returnval[0][-1].append(int(name2role[part.usernm]) if part.usernm in name2role.keys() else 0)
            returnval[0][-1].append(userfire[user])
        except AttributeError:
            ...
    for planetid in range(len(planets)):
        planet_ = planets[planetid]
        planetpos = planet_.body.position
        returnval[1].append(
            [planetid, [.1 * round(10 * planetpos.x), .1 * round(10 * planetpos.y)], planets.index(planet_.center) if planet_.center != None else None])
    return json.dumps(returnval).decode("utf-8")


def get_world(user):
    if user not in userparts.keys():
        adduser(user, "", 0)
    code = "drawbg(ctx, " + str(int(round(userparts[user].body.position.x))) + ", " + str(
        int(round(userparts[user].body.position.y))) + ");"
    # draw planets
    for planet_ in planets:
        if abs(planet_.body.position.x - userparts[user].body.position.x) <= 1000 + planet_.radius and abs(
                planet_.body.position.y - userparts[user].body.position.y) <= 1000 + planet_.radius:
            code += "drawplanet(ctx, " + str(
                int(round(planet_.body.position.x - userparts[user].body.position.x))) + "," + str(
                int(round(planet_.body.position.y - userparts[user].body.position.y))) + "," + str(
                planet_.eradius) + ", " + planet_.img + ");"
        else:
            code += "drawarrow(ctx, " + str(int(round(Vec2d(planet_.body.position.x - userparts[user].body.position.x,
                                                            planet_.body.position.y - userparts[
                                                                user].body.position.y).normalized().x * 100))) + "," + str(
                int(round(Vec2d(planet_.body.position.x - userparts[user].body.position.x,
                                planet_.body.position.y - userparts[
                                    user].body.position.y).normalized().y * 100))) + "," + str(int(round(
                Vec2d(planet_.body.position.x - userparts[user].body.position.x, planet_.body.position.y - userparts[
                    user].body.position.y).length))) + ",\"" + planet_.img + "\");"
    for user_ in userparts.keys():
        # draw fires
        if userfire[user_][0]:
            code += "drawminifire(ctx, -1,-1," + str(userparts[user_].body.angle) + "," + str(
                int(round(userparts[user_].body.position.x - userparts[user].body.position.x))) + "," + str(int(round(
                userparts[user_].body.position.y - userparts[
                    user].body.position.y))) + ");drawminifire(ctx, 1,-1," + str(
                userparts[user_].body.angle) + "," + str(
                int(round(userparts[user_].body.position.x - userparts[user].body.position.x))) + "," + str(
                int(round(userparts[user_].body.position.y - userparts[user].body.position.y))) + ");" if userparts[
                user_].fired else ""
            code += getthrustpart(userparts[user_], 0, user)
        if userfire[user_][1]:
            code += "drawminifire(ctx, -1,-1," + str(userparts[user_].body.angle) + "," + str(
                int(round(userparts[user_].body.position.x - userparts[user].body.position.x))) + "," + str(int(round(
                userparts[user_].body.position.y - userparts[
                    user].body.position.y))) + ");drawminifire(ctx, 1,1," + str(
                userparts[user_].body.angle) + "," + str(
                int(round(userparts[user_].body.position.x - userparts[user].body.position.x))) + "," + str(
                int(round(userparts[user_].body.position.y - userparts[user].body.position.y))) + ");" if userparts[
                user_].fired else ""
            code += getthrustpart(userparts[user_], 1, user)
        if userfire[user_][2]:
            code += "drawminifire(ctx, -1,1," + str(userparts[user_].body.angle) + "," + str(
                int(round(userparts[user_].body.position.x - userparts[user].body.position.x))) + "," + str(int(round(
                userparts[user_].body.position.y - userparts[
                    user].body.position.y))) + ");drawminifire(ctx, 1,1," + str(
                userparts[user_].body.angle) + "," + str(
                int(round(userparts[user_].body.position.x - userparts[user].body.position.x))) + "," + str(
                int(round(userparts[user_].body.position.y - userparts[user].body.position.y))) + ");" if userparts[
                user_].fired else ""
            code += getthrustpart(userparts[user_], 2, user)
        if userfire[user_][3]:
            code += "drawminifire(ctx, -1,1," + str(userparts[user_].body.angle) + "," + str(
                int(round(userparts[user_].body.position.x - userparts[user].body.position.x))) + "," + str(int(round(
                userparts[user_].body.position.y - userparts[
                    user].body.position.y))) + ");drawminifire(ctx, 1,-1," + str(
                userparts[user_].body.angle) + "," + str(
                int(round(userparts[user_].body.position.x - userparts[user].body.position.x))) + "," + str(
                int(round(userparts[user_].body.position.y - userparts[user].body.position.y))) + ");" if userparts[
                user_].fired else ""
            code += getthrustpart(userparts[user_], 3, user)
    # draw parts
    for part in allparts:
        if abs(part.body.position.x - userparts[user].body.position.x) > 1000:
            continue
        if abs(part.body.position.y - userparts[user].body.position.y) > 1000:
            continue
        code += \
            "drawpart(ctx, " + str(int(round(part.body.position.x - userparts[user].body.position.x))) + "," + str(
                int(round(part.body.position.y - userparts[user].body.position.y))) + "," + str(
                part.body.angle) + "," + part.image + ");"
        if type(part) == parts.User:
            try:
                code += "drawusernm(ctx, \"" + part.usernm + "\"," + name2role[part.usernm] + "," + str(
                    part.body.position.x - userparts[user].body.position.x) + "," + str(
                    part.body.position.y - userparts[user].body.position.y - 35.) + ");"
            except KeyError:
                code += "drawusernm(ctx, \"" + part.usernm + "\",0," + str(
                    part.body.position.x - userparts[user].body.position.x) + "," + str(
                    part.body.position.y - userparts[user].body.position.y - 35.) + ");"
    code += "drawstatus(ctx, " + str(int(round(60. * userparts[user].fuel / userparts[user].getpower()))) + ");"
    if name2role[user] == "2":
        code += "ctx.textAlign='center';ctx.fillStyle='white';ctx.fillText('" + str(
            [round(100. * i / sum(timings)) for i in timings]) + "',0,-100);"
    return code


def trigger(user, key, down):
    if down is True:
        if userrefiretimeout[user] == 0:
            userfire[user][key] = True
        else:
            userrefiretimeout[user] = 0
    else:
        userrefiretimeout[user] = 0
        userfire[user][key] = False


def createpart(planet_, part):
    x = 2 * (100 + planet_.radius) * (random.random() - .5)
    y = (1 if random.random() >= .5 else -1) * math.sqrt((100 + planet_.radius) * (100 + planet_.radius) - x * x)
    x += planet_.body.position.x
    y += planet_.body.position.y
    part.body.position = (x, y)
    looseparts[part] = 1000
    space.add(part.body, part.poly)
    allparts.append(part)
    return part


def tickplayer(part):
    part.tick()
    for part_ in part.connected:
        if part_ == False or part_ is None:
            continue
        tickplayer(part_)


def unattach(part, user):
    userparts[part.owner].fuel -= part.powstr
    ownedparts[part.owner].pop(ownedparts[user].index(part))
    ownedparts[part.owner].remove(part)
    part.connectedto.connected[part.direction] = None
    part.connectedto = None
    try:
        space.remove(part.pinjoint, part.rljoint)
    except AttributeError:
        ...
    part.pinjoint = None
    part.rljoint = None
    looseparts[part] = 1000
    part.owner = None
    for part_ in part.connected:
        if part_ is False or part_ is None:
            continue
        unattach(part_, user)


def ageparts():
    delete = []
    for part in looseparts:
        looseparts[part] -= 1
        if looseparts[part] == 0:
            space.remove(part.body, part.poly)
            del allparts[allparts.index(part)]
            delete.append(part)
    for part in delete:
        del looseparts[part]


def makeparts():
    for planet_ in planets:
        planet_.tick()


def rmspeed():
    for part in allparts:
        part.body.angular_velocity *= .99
        part.body.velocity *= .99


def gravity():
    for part in allparts:
        for planet_ in planets:
            from math import sqrt
            delta = planet_.body.position - part.body.position
            if abs(delta.x) + abs(delta.y) > planet_.radius * planet_.mass / 10:
                continue
            deltadistcubed = delta.x * delta.x + delta.y * delta.y
            deltadistcubed = deltadistcubed * sqrt(deltadistcubed)
            part.body.velocity += (10 * planet_.mass / deltadistcubed) * delta


def attachpt(part):
    try:
        del looseparts[part]
    except KeyError:
        ...
    part.owner = part.connectedto.owner
    part.body.position = part.connectedto.body.position + Vec2d(0, 25).rotated(
        part.connectedto.body.angle + math.pi / 2 * part.direction)
    part.body.angle = part.connectedto.body.angle + math.pi / 2 * part.direction - math.pi
    part.body.force = part.connectedto.body.force
    part.body.torque = part.connectedto.body.torque
    part.body.velocity = part.connectedto.body.velocity
    part.body.angular_velocity = part.connectedto.body.angular_velocity
    userparts[part.owner].fuel += part.powstr
    corrrotlimang = max(part.body.angle - part.connectedto.body.angle, part.connectedto.body.angle - part.body.angle)
    if part.direction == 3:
        corrrotlimang *= -1
    part.rljoint = RotaryLimitJoint(part.body, part.connectedto.body, corrrotlimang, corrrotlimang)
    part.pinjoint = PinJoint(part.connectedto.body, part.body, Vec2d(0, 12.5).rotated(math.pi / 2 * part.direction),
                             Vec2d(0, 12.5))
    space.add(part.pinjoint, part.rljoint)
    ownedparts[part.owner].append(part)
    userctl[part.owner] = None


def attach():
    for user in userparts:
        if userctl[user] is None:
            continue
        for part in allparts:
            if part == userctl[user]:
                continue
            dx = usermouse[user][1] + userparts[user].body.position.x - part.body.position.x
            dy = usermouse[user][2] + userparts[user].body.position.y - part.body.position.y
            dy *= -1
            if part == False in ownedparts[user] or userctl[user] == part or abs(dx) >= 15 or abs(dy) >= 15:
                continue
            d = Vec2d(dx, dy)
            a = (d.get_angle() + part.body.angle + math.pi * (6. / 2) - math.pi / 4.) % (math.pi * 2)
            if 0 <= a < math.pi / 2:
                userctl[user].direction = 0
            elif math.pi / 2 <= a < math.pi:
                userctl[user].direction = 3
            elif math.pi <= a < 3 * math.pi / 2:
                userctl[user].direction = 2
            elif 3 * math.pi / 2 <= a < 2 * math.pi:
                userctl[user].direction = 1
            else:
                userctl[user].direction = 0

            if part.connected[userctl[user].direction] is not None:
                continue

            part.connected[userctl[user].direction] = userctl[user]
            mypart = userctl[user]
            userctl[user].connectedto = part
            attachpt(userctl[user])

            b = ((mypart.body.angle - userparts[part.owner].body.angle) % (math.pi * 2))
            if 0 <= b < math.pi / 4:
                mypart.rotation = 0
            elif math.pi / 4 <= b < math.pi / 4 * 3:
                mypart.rotation = 3
            elif math.pi / 4 * 3 <= b < math.pi / 4 * 5:
                mypart.rotation = 2
            elif math.pi / 4 * 5 <= b < math.pi / 4 * 7:
                mypart.rotation = 1
            else:
                mypart.rotation = 0
            break


def thrustpart(part, n, x, y):
    if part is False or part is None:
        return
    if part not in userparts.values():
        doon1 = ((part.getequivdir() == 0 and x > 0) or (part.getequivdir() == 1 and y < 0) or (
                part.getequivdir() == 2 and x < 0) or (part.getequivdir() == 3 and y > 0))
        doon3 = ((part.getequivdir() == 0 and x < 0) or (part.getequivdir() == 1 and y > 0) or (
                part.getequivdir() == 2 and x > 0) or (part.getequivdir() == 3 and y < 0))
        shouldfire = (part.rotation == n or (n == 1 and doon1) or (n == 3 and doon3))

        if shouldfire and userparts[part.owner].fuel >= part.powcon / 10.:
            part.fired = True
            userparts[part.owner].fuel -= part.powcon / 10.
            part.body.apply_force_at_local_point((0, part.thrust), (0, -12.5))
    thrustpart(part.connected[part.direction], n, x, y + 1)
    thrustpart(part.connected[(part.direction + 1) % 4], n, x - 1, y)
    thrustpart(part.connected[(part.direction + 2) % 4], n, x, y - 1)
    thrustpart(part.connected[(part.direction + 3) % 4], n, x + 1, y)


def thrust():
    for part in allparts:
        part.fired = False
    for user in userparts.keys():
        try:
            if userparts[user].fuel < 2 / 10.:
                continue
            planetboost = False
            for planet_ in planets:
                if planet_.body.position.get_distance(userparts[user].body.position) <= planet_.radius + 25:
                    planetboost = True
                    break
            if userfire[user][0]:
                userparts[user].body.apply_force_at_local_point(
                    (0, userparts[user].thrust * (10 if planetboost else 1)), (0., -12.5))
                userparts[user].fired = True
                userparts[user].fuel -= 1 / 10.
                thrustpart(userparts[user], 0, 0, 0)
            if userfire[user][1]:
                userparts[user].body.apply_force_at_local_point(Vec2d(0, -userparts[user].thrust / 2) * (.1 if userparts[user].connected == [None, None, None, None] else 1), (12.5, 12.5))
                userparts[user].body.apply_force_at_local_point(Vec2d(0, userparts[user].thrust / 2) * (.1 if userparts[user].connected == [None, None, None, None] else 1), (-12.5, -12.5))
                userparts[user].fired = True
                userparts[user].fuel -= 1 / 10.
                thrustpart(userparts[user], 1, 0, 0)
            if userfire[user][2]:
                userparts[user].body.apply_force_at_local_point(
                    (0, -userparts[user].thrust * (10 if planetboost else 1)), (0., 12.5))
                userparts[user].fired = True
                userparts[user].fuel -= 1 / 10.
                thrustpart(userparts[user], 2, 0, 0)
            if userfire[user][3]:
                userparts[user].body.apply_force_at_local_point(Vec2d(0, userparts[user].thrust / 2) * (.1 if userparts[user].connected == [None, None, None, None] else 1), (12.5, 12.5))
                userparts[user].body.apply_force_at_local_point(Vec2d(0, -userparts[user].thrust / 2) * (.1 if userparts[user].connected == [None, None, None, None] else 1), (-12.5, -12.5))
                userparts[user].fired = True
                userparts[user].fuel -= 1 / 10.
                thrustpart(userparts[user], 3, 0, 0)
        except Exception as e:
            print(e)


def detach():
    for user in userparts:
        fixpos(userparts[user], user)


def control():
    for user in userparts:
        if userctl[user] is not None:
            userctl[user].body.velocity = (
                    (userparts[user].body.position + Vec2d(usermouse[user][1], usermouse[user][2])) - (
                    userctl[user].body.position + Vec2d(0, 12.5).rotated(userctl[user].body.angle)))
            userctl[user].body.force = (0, 0)


def powerpart(part):
    userparts[part.owner].fuel += part.powgen / 10.
    if userparts[part.owner].fuel >= userparts[part.owner].getpower():
        userparts[part.owner].fuel = userparts[part.owner].getpower()
        return
    for part_ in part.connected:
        if part_ == False or part_ is None:
            continue
        powerpart(part_)


def power():
    for user in userparts:
        if True in userfire[user]:
            continue
        powerpart(userparts[user])


timings = [0 for i in range(9)]


def loop():
    try:
        while True:
            try:
                global timereps, reps
                start_time_forstepping = time.time()
                start_time = time.time()
                ageparts()
                timings[0] += (time.time() - start_time)
                start_time = time.time()
                makeparts()
                timings[1] += (time.time() - start_time)
                start_time = time.time()
                detach()
                timings[2] += (time.time() - start_time)
                start_time = time.time()
                # gravity()
                timings[3] += (time.time() - start_time)
                start_time = time.time()
                control()
                timings[4] += (time.time() - start_time)
                start_time = time.time()
                thrust()
                timings[5] += (time.time() - start_time)
                start_time = time.time()
                attach()
                timings[6] += (time.time() - start_time)
                start_time = time.time()
                power()
                timings[7] += (time.time() - start_time)
                start_time = time.time()
                space.step(10 * (time.time() - start_time_forstepping + .01))
                timings[8] += (time.time() - start_time)
                time.sleep(.01)
            except Exception as e:
                # life goes on
                print(e)
                print(traceback.format_exc())
    except Exception as e:
        # Christian7573 take error and exit
        print(e)
        print(traceback.format_exc())
        time.sleep(20)
        exit()


def trigger_start():
    planets.append(planet.planet(0., 10000, None, 30000, None, [], -1, "yellow", space, "sun", 10000))
    planets.append(planet.planet(30000, 150, planets[0], 400., parts.Cargo, (), .01, "cyan", space, "earth", 150))
    planets.append(planet.planet(22000, 100, planets[0], 150, None, [], -1, "grey", space, "mercury", 250))
    planets.append(planet.planet(25000, 125, planets[0], 187.5, None, [], -1, "white", space, "venus", 125))
    planets.append(planet.planet(33000, 137.5, planets[0], 400, parts.Hub, [], -1, "brown", space, "mars", 137.5))
    planets.append(planet.planet(45000, 2500, planets[0], 15000, None, [], -1, "orange", space, "jupiter", 2500))
    planets.append(planet.planet(52500, 750, planets[0], 80000, None, [], -1, "beige", space, "saturn", 1500))
    planets.append(
        planet.planet(60000, 1000, planets[0], 10000 * 14.5361687877, None, [], -1, "lightblue", space, "uranus", 1000))
    planets.append(planet.planet(65000, 600, planets[0], 70000, None, [], -1, "blue", space, "neptune", 600))
    planets.append(planet.planet(46000, 400, planets[0], 1000, parts.FadyHub, [], -1, "yellow", space, "fady", 400))
    planets.append(
        planet.planet(50000, 400, planets[0], 1000, parts.GeneratorHub, [], -1, "yellow", space, "iAmAlbert", 400))
    planets.append(planet.planet(1500, 50, planets[1], 125, parts.LandingBooster, (), -1, "grey", space, "moon", 50))
    threading.Thread(target=loop, daemon=True).start()

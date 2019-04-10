"""
multibuild.py by IAmYourFriend

How to use:

Step 1: Type /mbreg and start "registering" your starting blocks.
Place blocks everywhere where you want your building to appear.

Step 2: Type /mb to start multibuilding. Important: Start building
exactly at the last starting block you placed during step 1.

You can toggle /mbreg or /mb all the time if you want to pause the
feature and build normal again.

Short video showcasing the feature:
https://twitter.com/1AmYF/status/1078610014867202048

For more advanced multibuilding:

/mbmirror <1 2>
  Mirror your multibuild, reversing (1) or non-reversing (2). Mind
  your orientation (= in which direction you look) during /mbreg
  as your multibuild will be mirrored accordingly.

/mbshape <ball box diamond land pyramid>
  Load a prefab shape instead of building your own during /mbreg.
  Your last starting block will be on the top middle of the shape
  (optionally adjust starting z by adding a number as argument).

/mbground
  Prevent destruction of ground blocks when using spade during /mb
  (optionally a custom z for the protection height can be added as
  argument).

/mbhelp
  List all multibuild commands.
"""

from pyspades.constants import *
from pyspades.contained import BlockAction, SetColor
from pyspades.server import block_action
from pyspades.common import make_color
from commands import add, admin, alias
from math import atan2, pi, sqrt
from twisted.internet.reactor import callLater


BUILD_DELAY = 0.04
SHAPES = {"ball": 5, "box": 5, "diamond": 4, "land": 6, "pyramid": 5}
HELP_TEXT = ["/mbreg     Register your starting blocks (required before /mb)",
             "/mb        Start multibuilding",
             "/mbmirror  Mirror build (mind your orientation during /mbreg)",
             "/mbshape   Load a prefab shape instead of using /mbreg",
             "/mbground  Prevent destruction of ground blocks during /mb"]


@admin
def mbreg(connection):
    connection.is_multibuilding = False
    connection.is_registering = not connection.is_registering
    if connection.is_registering:
        connection.regblocks = []
        return "Place your starting blocks now."
    else:
        return "No longer placing starting blocks."


@admin
def mb(connection):
    if len(connection.regblocks) < 1:
        return "You haven't placed any starting blocks yet. Use /mbreg"
    connection.is_registering = False
    connection.is_multibuilding = not connection.is_multibuilding
    if connection.is_multibuilding:
        return "Start multibuilding at your last placed block!"
    else:
        return "No longer multibuilding."


@admin
def mbmirror(connection, mirror=0):
    mirror = int(mirror)
    if mirror < 0 or mirror > 2:
        raise ValueError()
    connection.mirror = mirror
    if mirror == 0:
        return "Mirror disabled. Type /mbmirror 1 or /mbmirror 2 to enable."
    else:
        return ("Mirror type set to: %s (%s)" % (str(mirror),
                "reversing" if mirror == 1 else "non-reversing"))


@admin
def mbshape(connection, shape=None, adjust_z=0):
    adjust_z = int(adjust_z)
    if shape is None:
        shapes = ""
        for s in SHAPES.keys():
            shapes += s + " "
        return "Use this command with a shape name: " + shapes
    shape = shape.lower()
    if shape not in SHAPES.keys():
        return "Unknown shape name."
    radius = SHAPES[shape]
    connection.regblocks = []
    dir = get_direction(connection)
    add_bottom = shape == "ball" or shape == "box" or shape == "diamond"
    for x in range(0, radius):
        for y in range(0, radius):
            for z in range(0, radius):
                condition = False
                if shape == "ball":
                    condition = (sqrt(pow(x, 3) + pow(y, 3) + pow(z, 3)) <=
                                 radius - 2)
                elif shape == "box":
                    condition = (x <= int(radius / 2) and
                                 y <= int(radius / 2) and
                                 z <= int(radius / 2))
                elif shape == "land":
                    condition = (sqrt(pow(x, 2) + pow(y, 2) + pow(z, 1.5)) <=
                                 radius - 2 and z >= int(radius / 2))
                elif shape == "pyramid" or shape == "diamond":
                    condition = (x < z and y < z)
                if condition:
                    connection.regblocks.append((x, y, z, dir))
    parts = set()
    for regblock in connection.regblocks:
        rx, ry, rz = regblock[0], regblock[1], regblock[2]
        if shape == "pyramid" or shape == "diamond":
            rz = rz * -1 + radius
        parts.add((rx, ry, rz * -1, dir))
        parts.add((rx, ry * -1, rz * -1, dir))
        parts.add((rx * -1, ry, rz * -1, dir))
        parts.add((rx * -1, ry * -1, rz * -1, dir))
        if add_bottom:
            if shape == "diamond":
                rz -= 2
            parts.add((rx, ry, rz, dir))
            parts.add((rx, ry * -1, rz, dir))
            parts.add((rx * -1, ry, rz, dir))
            parts.add((rx * -1, ry * -1, rz, dir))
    connection.regblocks = list(parts)
    starting_z = (-int(radius / 2) if add_bottom and not shape == "diamond"
                  else -radius + 1)
    connection.regblocks.append((0, 0, starting_z + adjust_z, dir))
    return "Shape loaded. Use it now with /mb"


@admin
def mbground(connection, level=None):
    by_user = False
    if level is not None:
        level = int(level)
        by_user = True
    else:
        level = 62
    if by_user or connection.protect_ground == 99:
        connection.protect_ground = level
        return ("Ground protection enabled%s." %
                (" (above level " + str(level) + ")" if by_user else ""))
    else:
        connection.protect_ground = 99
        return "Ground protection disabled."


def mbhelp(connection):
    connection.send_lines(HELP_TEXT)


add(mbreg)
add(mb)
add(mbmirror)
add(mbshape)
add(mbground)
add(mbhelp)


def is_invalid_coord(x, y, z):
    return x < 0 or y < 0 or z < 0 or x > 511 or y > 511 or z > 62


def build_block(connection, x, y, z, color):
    set_color = SetColor()
    set_color.value = make_color(*color)
    set_color.player_id = 32
    connection.protocol.send_contained(set_color)
    block_action.player_id = 32
    block_action.x = x
    block_action.y = y
    block_action.z = z
    block_action.value = BUILD_BLOCK
    connection.protocol.map.set_point(x, y, z, color)
    connection.protocol.send_contained(block_action, save=True)


def destroy_block(connection, x, y, z):
    if connection.protocol.map.get_solid(x, y, z):
        block_action.player_id = connection.player_id
        block_action.x = x
        block_action.y = y
        block_action.z = z
        block_action.value = DESTROY_BLOCK
        connection.protocol.map.destroy_point(x, y, z)
        connection.protocol.send_contained(block_action, save=True)


def get_direction(self):
    return int(round(atan2(self.world_object.orientation.y,
                           self.world_object.orientation.x) / pi * 2) % 4)


def get_multiblock_diff(self, regblock, xyz_new):
    lastregblock = self.regblocks[len(self.regblocks) - 1]
    x = xyz_new[0] - lastregblock[0]
    y = xyz_new[1] - lastregblock[1]
    z = xyz_new[2] - lastregblock[2]
    if self.mirror > 0 and not lastregblock[3] == regblock[3]:
        if abs(lastregblock[3] - regblock[3]) == 2:
            if self.mirror == 2 or not lastregblock[3] % 2:
                x = x * -1
            if self.mirror == 2 or lastregblock[3] % 2:
                y = y * -1
        else:
            tmp_x = x
            x = y
            y = tmp_x
            if regblock[3] == 1 or regblock[3] == 2:
                x = x * -1
            else:
                y = y * -1
            if lastregblock[3] > 1:
                x = x * -1
                y = y * -1
            if self.mirror == 1 and (lastregblock[3] == regblock[3] + 1 or
                                     lastregblock[3] - regblock[3] == -3):
                if regblock[3] % 2:
                    x = x * -1
                else:
                    y = y * -1
    return (x, y, z)


def rollout_multiblocks(self, coord, destroy=False):
    delay = 0
    first = True
    for regblock in reversed(self.regblocks):
        if first:
            first = False
            continue
        block_diff = get_multiblock_diff(self, regblock, coord)
        mb_x = regblock[0] + block_diff[0]
        mb_y = regblock[1] + block_diff[1]
        mb_z = regblock[2] + block_diff[2]
        if (is_invalid_coord(mb_x, mb_y, mb_z) or
           (destroy and mb_z >= self.protect_ground)):
            continue
        is_solid = self.protocol.map.get_solid(mb_x, mb_y, mb_z)
        if destroy and is_solid:
            callLater(delay, destroy_block, self, mb_x, mb_y, mb_z)
            delay += BUILD_DELAY
        elif not destroy and not is_solid:
            callLater(delay, build_block, self, mb_x, mb_y, mb_z, self.color)
            delay += BUILD_DELAY


def apply_script(protocol, connection, config):
    class MultibuildConnection(connection):
        is_registering = False
        is_multibuilding = False
        protect_ground = 99
        mirror = 0
        # x, y, z, direction (0 = east, 1 = south, 2 = west, 3 = north)
        regblocks = []

        def on_block_build(self, x, y, z):
            if self.is_registering:
                self.regblocks.append((x, y, z, get_direction(self)))
            elif self.is_multibuilding:
                rollout_multiblocks(self, (x, y, z))
                if self.god:
                    self.refill()
            return connection.on_block_build(self, x, y, z)

        def on_line_build(self, points):
            if self.is_registering:
                for point in points:
                    self.regblocks.append((point[0], point[1], point[2],
                                           get_direction(self)))
            elif self.is_multibuilding:
                delay = 0
                for point in points:
                    callLater(delay, rollout_multiblocks, self, point)
                    delay += BUILD_DELAY
                if self.god:
                    self.refill()
            return connection.on_line_build(self, points)

        def on_block_destroy(self, x, y, z, value):
            if self.is_registering or self.is_multibuilding:
                blocks = None
                if value == DESTROY_BLOCK:
                    blocks = ((x, y, z),)
                elif value == SPADE_DESTROY:
                    blocks = ((x, y, z), (x, y, z + 1), (x, y, z - 1))
                if blocks is not None:
                    if self.is_registering:
                        for block in blocks:
                            newregblocks = []
                            for regblock in self.regblocks:
                                if not (block[0] == regblock[0] and
                                        block[1] == regblock[1] and
                                        block[2] == regblock[2]):
                                    newregblocks.append(regblock)
                            self.regblocks = newregblocks
                    elif self.is_multibuilding:
                        for block in blocks:
                            rollout_multiblocks(self, block, destroy=True)
            return connection.on_block_destroy(self, x, y, z, value)

    return protocol, MultibuildConnection

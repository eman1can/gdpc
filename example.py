#! /usr/bin/python3
"""### Generate an example village.

The source code of this module contains examples for:
* Retrieving the build area
* Basic heightmap functionality
* Single block placement
* Batch block placement

It is not meant to be imported.
"""
__all__ = []
__author__ = "Nils Gawlik <nilsgawlik@gmx.de>"
__date__ = "11 March 2021"
# __version__
__credits__ = "Nils Gawlick for being awesome and creating the framework" + \
    "Flashing Blinkenlights for general improvements"

import random

import interfaceUtils
import mapUtils
from interfaceUtils import Interface
from worldLoader import WorldSlice

# set up an interface for getting and placing blocks
interface = Interface()
# IMPORTANT: It is recommended not to use buffering during development
# How to use buffering (batch placement):
#   Allow block buffer placement
#       >>> interface.toggleBuffer()
#   Change maximum buffer size (default is 4096 blocks)
#       >>> interface.bufferlimit = 100
#   Send blocks to world
#       >>> interface.sendBlocks()
#   NOTE: The buffer will automatically place its blocks once it gets full
#   NOTE: It is a good idea to call sendBlocks() after completing a task,
#       so that you can see the result without having to wait
#   IMPORTANT: A crash may prevent the blocks from being placed

# x position, z position, x size, z size
area = (0, 0, 128, 128)  # default build area

# see if a build area has been specified
# you can set a build area in minecraft using the /setbuildarea command
buildArea = interface.requestBuildArea()
if buildArea != -1:
    area = buildArea


def heightAt(x, z):
    """Access height using local coordinates."""
    # Warning:
    # Heightmap coordinates are not equal to world coordinates!
    return heightmap[(x - area[0], z - area[1])]


def buildHouse(x1, y1, z1, x2, y2, z2):
    """Build a small house."""
    # floor
    interface.fill(x1, y1, z1, x2 - 1, y1, z2 - 1, "cobblestone")

    # walls
    interface.fill(x1 + 1, y1, z1, x2 - 2, y2, z1, "oak_planks")
    interface.fill(x1 + 1, y1, z2 - 1, x2 - 2, y2, z2 - 1, "oak_planks")
    interface.fill(x1, y1, z1 + 1, x1, y2, z2 - 2, "oak_planks")
    interface.fill(x2 - 1, y1, z1 + 1, x2 - 1, y2, z2 - 2, "oak_planks")

    # corners
    interface.fill(x1, y1, z1, x1, y2, z1, "oak_log")
    interface.fill(x2 - 1, y1, z1, x2 - 1, y2, z1, "oak_log")
    interface.fill(x1, y1, z2 - 1, x1, y2, z2 - 1, "oak_log")
    interface.fill(x2 - 1, y1, z2 - 1, x2 - 1, y2, z2 - 1, "oak_log")

    # clear interior
    for y in range(y1 + 1, y2):
        for x in range(x1 + 1, x2 - 1):
            for z in range(z1 + 1, z2 - 1):
                # check what's at that place and only delete if not air
                if "air" not in interface.getBlock(x, y, z):
                    interface.setBlock(x, y, z, "air")

    # roof
    if x2 - x1 < z2 - z1:   # if the house is longer in Z-direction
        for i in range(0, (1 - x1 + x2) // 2):
            interface.fill(x1 + i, y2 + i, z1,
                           x2 - 1 - i, y2 + i, z2 - 1, "bricks")
    else:
        # same as above but with x and z swapped
        for i in range(0, (1 - z1 + z2) // 2):
            interface.fill(x1, y2 + i, z1 + i, x2 - 1,
                           y2 + i, z2 - 1 - i, "bricks")

    if interface.Buffering:
        interface.sendBlocks()


def rectanglesOverlap(r1, r2):
    """Check that r1 and r2 do not overlap."""
    if ((r1[0] >= r2[0] + r2[2]) or (r1[0] + r1[2] <= r2[0])
            or (r1[1] + r1[3] <= r2[1]) or (r1[1] >= r2[1] + r2[3])):
        return False
    else:
        return True


if __name__ == '__main__':
    """Generate a village within the target area."""
    print(f"Build area is at position {area[0]}, {area[1]} with size {area[2]}, {area[3]}")

    # load the world data
    # this uses the /chunks endpoint in the background
    worldSlice = WorldSlice(area)

    # calculate a heightmap suitable for building:
    heightmap = mapUtils.calcGoodHeightmap(worldSlice)

    # example alternative heightmaps:
    # >>> heightmap = worldSlice.heightmaps["MOTION_BLOCKING"]
    # >>> heightmap = worldSlice.heightmaps["MOTION_BLOCKING_NO_LEAVES"]
    # >>> heightmap = worldSlice.heightmaps["OCEAN_FLOOR"]
    # >>> heightmap = worldSlice.heightmaps["WORLD_SURFACE"]

    # show the heightmap as an image
    # >>> mapUtils.visualize(heightmap, title="heightmap")

    # build a fence around the perimeter
    for x in range(area[0], area[0] + area[2]):
        z = area[1]
        y = heightAt(x, z)
        interface.setBlock(x, y - 1, z, "cobblestone")
        interface.setBlock(x, y,   z, "oak_fence")
    for z in range(area[1], area[1] + area[3]):
        x = area[0]
        y = heightAt(x, z)
        interface.setBlock(x, y - 1, z, "cobblestone")
        interface.setBlock(x, y, z, "oak_fence")
    for x in range(area[0], area[0] + area[2]):
        z = area[1] + area[3] - 1
        y = heightAt(x, z)
        interface.setBlock(x, y - 1, z, "cobblestone")
        interface.setBlock(x, y,   z, "oak_fence")
    for z in range(area[1], area[1] + area[3]):
        x = area[0] + area[2] - 1
        y = heightAt(x, z)
        interface.setBlock(x, y - 1, z, "cobblestone")
        interface.setBlock(x, y, z, "oak_fence")

    if interface.Buffering:
        interface.sendBlocks()

    houses = []
    for i in range(100):

        # pick random rectangle to place new house
        houseSizeX = random.randrange(5, 25)
        houseSizeZ = random.randrange(5, 25)
        houseX = random.randrange(
            area[0] + houseSizeX + 1, area[0] + area[2] - houseSizeX - 1)
        houseZ = random.randrange(
            area[1] + houseSizeZ + 1, area[1] + area[3] - houseSizeZ - 1)
        houseRect = (houseX, houseZ, houseSizeX, houseSizeZ)

        # check whether there are any overlaps
        overlapsExist = False
        for house in houses:
            if rectanglesOverlap(houseRect, house):
                overlapsExist = True
                break

        if not overlapsExist:

            print(f"building house at {houseRect[0]},{houseRect[1]} "
                  f"with size {houseRect[2]+1},{houseRect[3]+1}")

            # find the lowest corner of the house and give it a random height
            houseY = min(
                heightAt(houseX, houseZ),
                heightAt(houseX + houseSizeX - 1, houseZ),
                heightAt(houseX, houseZ + houseSizeZ - 1),
                heightAt(houseX + houseSizeX - 1, houseZ + houseSizeZ - 1)
            ) - 1
            houseSizeY = random.randrange(4, 7)

            # build the house!
            buildHouse(houseX, houseY, houseZ, houseX + houseSizeX,
                       houseY + houseSizeY, houseZ + houseSizeZ)
            houses.append(houseRect)

# ! /usr/bin/python3
"""### Provides tools for reading chunk data.

This module contains functions to:
* Calculate a heightmap ideal for building
* Visualise numpy arrays
"""
__all__ = ['WorldSlice']
__version__ = "v5.1"

from io import BytesIO
from time import time

import nbt
import numpy as np
from numpy import ceil, log2

from . import direct_interface as di
from .bitarray import BitArray


class CachedSection:
    """**Represents a cached chunk section (16x16x16)**."""

    def __init__(self, palette, blockStatesBitArray):
        self.palette = palette
        self.blockStatesBitArray = blockStatesBitArray

    # __repr__ displays the class well enough so __str__ is omitted
    def __repr__(self):
        return f"CachedSection({repr(self.palette)}, " \
            f"{repr(self.blockStatesBitArray)})"


class WorldSlice:
    """**Contains information on a slice of the world**."""
    def __init__(self, x1, z1, x2, z2, heightmapTypes=None):
        """**Initialise WorldSlice with region and heightmaps**.

        x1, x2, z1, z2 are global coordinates
        x2 and z2 are exclusive
        """
        if heightmapTypes is None:
            heightmapTypes = ["MOTION_BLOCKING",
                              "MOTION_BLOCKING_NO_LEAVES",
                              "OCEAN_FLOOR",
                              "WORLD_SURFACE"]
        self.rect = x1, z1, x2 - x1, z2 - z1
        cxl = int(ceil((x2 - x1) / 16))
        czl = int(ceil((z2 - z1) / 16))
        self.chunkRect = (x1 // 16, z1 // 16, cxl, czl)

        self.heightmapTypes = heightmapTypes

        self.byte_data = di.getChunks(*self.chunkRect, rtype='bytes')
        self._load_slice()

    def _load_slice(self):
        file_like = BytesIO(self.byte_data)

        self.nbtfile = nbt.nbt.NBTFile(buffer=file_like)

        rectOffset = [self.rect[0] % 16, self.rect[1] % 16]

        # heightmaps
        self.heightmaps = {}
        for hmName in self.heightmapTypes:
            self.heightmaps[hmName] = np.zeros((self.rect[2] + 1, self.rect[3] + 1), dtype=int)

        # Sections are in x,z,y order!!! (reverse minecraft order :p)
        self.sections = [[[None for _ in range(16)] for _ in range(self.chunkRect[3])] for _ in range(self.chunkRect[2])]

        # heightmaps
        for x in range(self.chunkRect[2]):
            for z in range(self.chunkRect[3]):
                chunkID = x + z * self.chunkRect[2]

                hms = self.nbtfile['Chunks'][chunkID]['Level']['Heightmaps']
                for hmName in self.heightmapTypes:
                    # hmRaw = hms['MOTION_BLOCKING']
                    hmRaw = hms[hmName]
                    heightmapBitArray = BitArray(9, 16 * 16, hmRaw)
                    heightmap = self.heightmaps[hmName]
                    for cz in range(16):
                        for cx in range(16):
                            try:
                                heightmap[-rectOffset[0] + x * 16 + cx,
                                          -rectOffset[1] + z * 16 + cz] \
                                    = heightmapBitArray.getAt(cz * 16 + cx)
                            except IndexError:
                                pass

        # sections
        for x in range(self.chunkRect[2]):
            for z in range(self.chunkRect[3]):
                chunkID = x + z * self.chunkRect[2]
                chunk = self.nbtfile['Chunks'][chunkID]
                chunkSections = chunk['Level']['Sections']

                for section in chunkSections:
                    y = section['Y'].value

                    if (not ('BlockStates' in section)
                            or len(section['BlockStates']) == 0):
                        continue

                    palette = section['Palette']
                    rawBlockStates = section['BlockStates']
                    bitsPerEntry = int(max(4, ceil(log2(len(palette)))))
                    blockStatesBitArray = BitArray(bitsPerEntry, 16 * 16 * 16, rawBlockStates)
                    self.sections[x][z][y] = CachedSection(palette, blockStatesBitArray)

    # __repr__ displays the class well enough so __str__ is omitted
    def __repr__(self):
        """**Represent the WorldSlice as a constructor**."""
        x1, z1 = self.rect[:2]
        x2, z2 = self.rect[0] + self.rect[2], self.rect[1] + self.rect[3]
        return f"WorldSlice{(x1, z1, x2, z2)}"

    def getBlockCompoundAt(self, x, y, z):
        """**Return block data**."""
        # convert to relative chunk position
        chunkX = (x // 16) - self.chunkRect[0]
        chunkZ = (z // 16) - self.chunkRect[1]
        chunkY = y // 16

        try:
            cachedSection = self.sections[chunkX][chunkZ][chunkY]
        except IndexError:
            print(f'Index Error: {chunkX} {chunkY} {chunkZ} not found')
            return None

        if cachedSection is None:
            return None  # TODO return air compound instead

        bitarray = cachedSection.blockStatesBitArray
        palette = cachedSection.palette

        # convert coordinates to chunk-relative coordinates
        blockIndex = (y % 16) * 16 * 16 + (z % 16) * 16 + x % 16
        return palette[bitarray.getAt(blockIndex)]

    def getBlockAt(self, x, y, z):
        """**Return the block's namespaced id at blockPos**."""
        blockCompound = self.getBlockCompoundAt(x, y, z)
        if blockCompound is None:
            return "minecraft:void_air"
        else:
            return blockCompound["Name"].value

    def getBiomeAt(self, x, y, z):
        """**Return biome at given coordinates**.

        Due to the noise around chunk borders,
        there is an inacurracy of +/-2 blocks.
        """
        from .lookup import BIOMES
        chunkID = (x - self.rect[0]) // 16 + \
            (z - self.rect[1]) // 16 * self.chunkRect[2]
        data = self.nbtfile['Chunks'][chunkID]['Level']['Biomes']
        x = (x % 16) // 4
        z = (z % 16) // 4
        y = y // 4
        index = x + 4 * z + 16 * y
        return BIOMES[data[index]]

    def getBiomesNear(self, x, y, z):
        """**Return a list of biomes in the same chunk**."""
        from .lookup import BIOMES
        chunkID = (x - self.rect[0]) // 16 + \
            (z - self.rect[1]) // 16 * self.chunkRect[2]
        data = self.nbtfile['Chunks'][chunkID]['Level']['Biomes']
        # "sorted(list(set(data)))" is used to remove duplicates from data
        return [BIOMES[i] for i in sorted(list(set(data)))]

    def getPrimaryBiomeNear(self, x, y, z):
        """**Return the most prevelant biome in the same chunk**."""
        from .lookup import BIOMES
        chunkID = (x - self.rect[0]) // 16 + \
            (z - self.rect[1]) // 16 * self.chunkRect[2]
        data = self.nbtfile['Chunks'][chunkID]['Level']['Biomes']
        # "max(set(data), key=data.count)" is used to find the most common item
        data = max(set(data), key=data.count)
        return BIOMES[data]

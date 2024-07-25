bl_info = {
    "name": "HMX Importer",
    "description": "A script to import milo/rnd files from most HMX games.",
    "author": "alliwantisyou3471",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "File > Import",
    "warning": "", # used for warning icon and text in addons panel
    "doc_url": "",
    "tracker_url": "",
    "support": "COMMUNITY",
    "category": "Import-Export",
}

import bpy
import zlib
import struct
import math
import mathutils
import io
import os
import numpy as np

from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

def l_int(f):
    return struct.unpack('I', f.read(4))[0]
    
def b_int(f):
    return struct.unpack('>I', f.read(4))[0]

def b_float(f):
    return struct.unpack('>f', f.read(4))[0]

def l_float(f):
    return struct.unpack('f', f.read(4))[0]
    
def l_numstring(f):
    name_len = struct.unpack('I', f.read(4))[0]
    string = f.read(name_len).decode('utf-8')
    return string
    
def b_numstring(f):
    name_len = struct.unpack('>I', f.read(4))[0]
    string = f.read(name_len).decode('utf-8')
    return string
    

class ImportMilo(Operator, ImportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "import.milo"
    bl_label = "Import Milo"

    filepath = StringProperty(subtype='FILE_PATH')

    filename_ext = ".milo_ps3"

    filter_glob: StringProperty(
        default="*.milo_ps3;*.milo_xbox;*.milo_wii;*.rnd_ps2;*.milo_ps2;*.rnd",
        options={'HIDDEN'},
    )

    low_lod_setting: BoolProperty(
        name="Skip Low LOD Meshes",
        description="Skip meshes that are lower quality",
        default=True,
    )

    shadow_setting: BoolProperty(
        name="Skip Shadow Mesh",
        description="Skip shadow mesh from characters",
        default=True,
    )       
    
    GameItems = [
        ('OPTION_A', 'LRB', ''),
        ('OPTION_B', 'GDRB', ''),
        ('OPTION_C', 'RB3', ''),
    ]
        
    bpy.types.Scene.games = EnumProperty(
        name="Game",
        description="Select a game for texture import.",
        items=GameItems,
    )
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.label(text="Select a game:")
        layout.prop(context.scene, "games", text="")
        layout.prop(self, "low_lod_setting")
        layout.prop(self, "shadow_setting")
        layout.prop(self, "trans_anim_setting")
        layout.prop(self, "prop_anim_setting")
        layout.prop(self, "venue_setting")

    def execute(self, context):
        with open(self.filepath, 'rb') as f:
            basename = os.path.basename(self.filepath)
            # Seek over magic
            f.seek(4)
            # Grab zlib start and block count
            StartOffset = l_int(f)
            FileCount = l_int(f)
            f.seek(16)
            compressed = []
            file = bytes()
            for x in range(FileCount):
                compressed.append(l_int(f))
            f.seek(StartOffset)
            # Hacky way to guess endian
            Versions = [6, 10, 24, 25, 28, 32]
            LittleEndian = False
            BigEndian = False
            Version = struct.unpack('I', f.read(4))[0]
            if Version not in Versions:
                BigEndian = True
                f.seek(-4, 1)
                Version = struct.unpack('>I', f.read(4))[0]
            elif Version in Versions:
                LittleEndian = True
            dirs = []
            filenames = []
            MatTexNames = []
            MatTexFiles = []
            # GH1
            if Version == 10 and LittleEndian == True:
                EntryCount = l_int(f)
                for x in range(EntryCount):
                    dirs.append(l_numstring(f))
                    filenames.append(l_numstring(f))
                ExtCount = l_int(f)
                for x in range(ExtCount):
                    ExtPath = l_numstring(f)
                rest_file = f.read()
                files = rest_file.split(b'\xAD\xDE\xAD\xDE')
                for directory, name, file in zip(dirs, filenames, files):
                    if ".mat" in name and "Mat" in directory:
                        MatTexNames.append(name)
                        MatTexFiles.append(file)
                    if "Tex" in directory:
                        if not "TexBlend" in directory:
                            MatTexNames.append(name)
                            MatTexFiles.append(file)
                    if ".mesh" in name and "Mesh" in directory:
                        Mesh(self, name, file, basename, MatTexNames, MatTexFiles)
                    if "bone" in name and "Mesh" in directory:
                        Trans(basename, name, file)
                    if "TransAnim" in directory:
                        TransAnim(file)
            # GH2 PS2
            elif Version == 24 and LittleEndian == True:
                DirType = l_numstring(f)
                DirName = l_numstring(f)
                dirs.append(DirType)
                filenames.append(DirName)
                f.seek(8, 1)
                EntryCount = l_int(f)
                for x in range(EntryCount):
                    dirs.append(l_numstring(f))
                    filenames.append(l_numstring(f))
                rest_file = f.read()
                files = rest_file.split(b'\xAD\xDE\xAD\xDE')                
                for directory, name, file in zip(dirs, filenames, files):
                    if ".mat" in name and "Mat" in directory:
                        MatTexNames.append(name)
                        MatTexFiles.append(file)
                    if "Tex" in directory:
                        if not "TexBlend" in directory:
                            MatTexNames.append(name)
                            MatTexFiles.append(file)
                    if ".mesh" in name and "Mesh" in directory:
                        Mesh(self, name, file, basename, MatTexNames, MatTexFiles)
                    if ".mesh" in name and "Trans" in directory:
                        Trans(basename, name, file)            
                    if "TransAnim" in directory:
                        TransAnim(file)
            # GH2 360
            elif Version == 25 and LittleEndian == True:
                DirType = l_numstring(f)
                DirName = l_numstring(f)
                dirs.append(DirType)
                filenames.append(DirName)
                f.seek(8, 1)
                EntryCount = l_int(f)
                for x in range(EntryCount):
                    dirs.append(l_numstring(f))
                    filenames.append(l_numstring(f))
                rest_file = f.read()
                files = rest_file.split(b'\xAD\xDE\xAD\xDE')
                for directory, name, file in zip(dirs, filenames, files):
                    if ".mat" in name and "Mat" in directory:
                        MatTexNames.append(name)
                        MatTexFiles.append(file)
                    if "Tex" in directory:
                        if not "TexBlend" in directory:
                            Tex(context, basename, self, name, file)
                            MatTexNames.append(name)
                            MatTexFiles.append(file)
                    if ".mesh" in name and "Mesh" in directory:
                        Mesh(self, name, file, basename, MatTexNames, MatTexFiles)
                    if ".mesh" in name and "Trans" in directory:
                        Trans(basename, name, file)
                    if "TransAnim" in directory:
                        TransAnim(file)
            # RB2-GDRB
            elif Version == 25 and BigEndian == True:
                DirType = b_numstring(f)
                DirName = b_numstring(f)
                dirs.append(DirType)
                filenames.append(DirName)
                f.seek(8, 1)
                EntryCount = b_int(f)
                for x in range(EntryCount):
                    dirs.append(b_numstring(f))
                    filenames.append(b_numstring(f))
                rest_file = f.read()
                files = rest_file.split(b'\xAD\xDE\xAD\xDE')
                for directory, name, file in zip(dirs, filenames, files):
                    if ".mat" in name and "Mat" in directory:
                        MatTexNames.append(name)
                        MatTexFiles.append(file)
                    if "Tex" in directory:
                        if not "TexBlend" in directory:
                            Tex(context, basename, self, name, file)
                            MatTexNames.append(name)
                            MatTexFiles.append(file)
                    if ".mesh" in name and "Mesh" in directory:
                        Mesh(self, name, file, basename, MatTexNames, MatTexFiles)
                    if ".mesh" in name and "Trans" in directory:
                        Trans(basename, name, file)
                    if "TransAnim" in directory:
                        TransAnim(file)
            # RB3-DC2
            elif Version == 28 and BigEndian == True:
                DirType = b_numstring(f)
                DirName = b_numstring(f)
                dirs.append(DirType)
                filenames.append(DirName)
                f.seek(8, 1)
                EntryCount = b_int(f)
                for x in range(EntryCount):
                    dirs.append(b_numstring(f))
                    filenames.append(b_numstring(f))
                rest_file = f.read()
                files = rest_file.split(b'\xAD\xDE\xAD\xDE')
                for directory, name, file in zip(dirs, filenames, files):
                    if ".mat" in name and "Mat" in directory:
                        MatTexNames.append(name)
                        MatTexFiles.append(file)
                    if "Tex" in directory:
                        if not "TexBlend" in directory:
                            Tex(context, basename, self, name, file)
                            MatTexNames.append(name)
                            MatTexFiles.append(file)
                    if ".mesh" in name and "Mesh" in directory:
                        Mesh(self, name, file, basename, MatTexNames, MatTexFiles)
                    if ".mesh" in name and "Trans" in directory:
                        Trans(basename, name, file)
                    if "TransAnim" in directory:
                        TransAnim(file)
            # DC3-and on
            elif Version == 32 and BigEndian == True:
                DirType = b_numstring(f)
                DirName = b_numstring(f)
                dirs.append(DirType)
                filenames.append(DirName)
                f.seek(9, 1)
                EntryCount = b_int(f)
                for x in range(EntryCount):
                    dirs.append(b_numstring(f))
                    filenames.append(b_numstring(f))
                rest_file = f.read()
                files = rest_file.split(b'\xAD\xDE\xAD\xDE')
                for file in files:
                    header = file[:4]
                    if header == b'\x00\x00\x00\x26':
                        DC3Mesh(self, file)
                    elif header == b'\x00\x00\x00\x0B':
                        DC3Tex(self, file)
        return {'FINISHED'}                

def Tex(context, basename, self, filename, file):
    try:
        directory = os.path.dirname(self.filepath)
        f = io.BytesIO(file)
        # Hacky way to guess endian
        Versions = [5, 7, 8, 10, 11]
        LittleEndian = False
        BigEndian = False
        Version = struct.unpack('I', f.read(4))[0]
        if Version not in Versions:
            BigEndian = True
            f.seek(-4, 1)
            Version = struct.unpack('>I', f.read(4))[0]
        elif Version in Versions:
            LittleEndian = True
        if Version == 10:
            f.seek(17)
            # Extract width and height
            if LittleEndian == True:
                Width = l_int(f)
                Height = l_int(f)
            if BigEndian == True:
                Width = b_int(f)
                Height = b_int(f)
            f.seek(4, 1)
            # Grab texture name
            # Lego developers were on something...
            if LittleEndian == True:
                TextureName = l_numstring(f)
            if BigEndian == True:
                TextureName = b_numstring(f)
            f.seek(11, 1)
            if LittleEndian == True:
                Encoding = l_int(f)
            if BigEndian == True:
                Encoding = b_int(f)
            # Grab mipmap count
            if LittleEndian == True:
                MipMapCount = struct.unpack('B', f.read(1))
            if BigEndian == True:
                MipMapCount = struct.unpack('>B', f.read(1))
            MipMapCount = int.from_bytes(MipMapCount, byteorder='little')
            EncodeOut = b''
            if Encoding == 8:
                EncodeOut = b'\x44\x58\x54\x31'
            elif Encoding == 24:
                EncodeOut = b'\x44\x58\x54\x35'
            elif Encoding == 32:
                EncodeOut = b'\x41\x54\x49\x32'
            f.seek(25, 1)
            # Read bitmap (just reads the rest of the file as we already grabbed all important header data)
            if not basename.endswith('.milo_xbox'):
                Bitmap = f.read()
            else:
                BitmapOffset = f.tell()
                Bitmap = f.read()
                f.seek(BitmapOffset)
                Pixels = []
                for x in range(len(Bitmap)):
                    Pixel1 = f.read(1)
                    Pixel2 = f.read(1)
                    Pixels.append((Pixel2, Pixel1))
            if basename.endswith('.milo_wii'):
                file_path = os.path.join(directory, filename[:-4] + ".tpl")
            else:
                file_path = os.path.join(directory, filename[:-4] + ".dds")

            # Export texture out
            if basename.endswith('.milo_wii'):
                with open(file_path, 'wb') as output_file:
                    output_file.write(b'\x00\x20\xAF\x30')
                    output_file.write(struct.pack('>IIII', 1, 12, 20, 0))
                    output_file.write(struct.pack('>HH', Height, Width))
                    output_file.write(struct.pack('>II', 14, 64))
                    output_file.write(struct.pack('>IIII', 0, 0, 1, 1))
                    output_file.write(struct.pack('>f', 0))
                    output_file.write(struct.pack('>BBBB', 0, 0, 0, 0))
                    for x in range(2):
                        output_file.write(struct.pack('>I', 0))
                    output_file.write(Bitmap)
            else:
                with open(file_path, 'wb') as output_file:
                    output_file.write(struct.pack('ccc', b'D', b'D', b'S',))
                    output_file.write(b'\x20')
                    output_file.write(struct.pack('I', 124))
                    output_file.write(struct.pack('I', 528391))
                    output_file.write(struct.pack('I', Height))
                    output_file.write(struct.pack('I', Width))
                    output_file.write(struct.pack('III', 0, 0, MipMapCount))
                    for x in range(11):
                        output_file.write(struct.pack('I', 0))
                    output_file.write(struct.pack('I', 32))
                    output_file.write(struct.pack('I', 4))
                    output_file.write(EncodeOut)
                    output_file.write(struct.pack('IIIII', 0, 0, 0, 0, 0))
                    output_file.write(struct.pack('I', 4096))
                    output_file.write(struct.pack('IIII', 0, 0, 0, 0))
                    if not basename.endswith('.milo_xbox'):            
                        output_file.write(Bitmap)
                    else:
                        for Pixel in Pixels:
                            byte1, byte2 = Pixel
                            output_file.write(byte1)
                            output_file.write(byte2)
            
            print("Exported texture:", file_path)
        if context.scene.games == 'OPTION_A':
            f.seek(17)
            # Extract width and height
            if LittleEndian == True:
                Width = l_int(f)
                Height = l_int(f)
            if BigEndian == True:
                Width = b_int(f)
                Height = b_int(f)                
            # Grab texture name
            # Lego developers were on something...
            f.seek(8, 1)
            if LittleEndian == True:
                TextureName = l_numstring(f)
            if BigEndian == True:
                TextureName = b_numstring(f)
            f.seek(11, 1)
            if LittleEndian == True:
                Encoding = l_int(f)
            if BigEndian == True:
                Encoding = b_int(f)
            # Grab mipmap count
            if LittleEndian == True:
                MipMapCount = struct.unpack('B', f.read(1))
            if BigEndian == True:
                MipMapCount = struct.unpack('>B', f.read(1))
            MipMapCount = int.from_bytes(MipMapCount, byteorder='little')
            EncodeOut = b''
            if Encoding == 8:
                EncodeOut = b'\x44\x58\x54\x31'
            elif Encoding == 24:
                EncodeOut = b'\x44\x58\x54\x35'
            elif Encoding == 32:
                EncodeOut = b'\x41\x54\x49\x32'
            f.seek(25, 1)
            # Read bitmap (just reads the rest of the file as we already grabbed all important header data)
            if not basename.endswith('.milo_xbox'):
                Bitmap = f.read()
            else:
                BitmapOffset = f.tell()
                Bitmap = f.read()
                f.seek(BitmapOffset)
                Pixels = []
                for x in range(len(Bitmap)):
                    Pixel1 = f.read(1)
                    Pixel2 = f.read(1)
                    Pixels.append((Pixel2, Pixel1))
            if basename.endswith('.milo_wii'):
                file_path = os.path.join(directory, filename[:-4] + ".tpl")
            else:
                file_path = os.path.join(directory, filename[:-4] + ".dds")

            # Export texture out
            if basename.endswith('.milo_wii'):
                with open(file_path, 'wb') as output_file:
                    output_file.write(b'\x00\x20\xAF\x30')
                    output_file.write(struct.pack('>IIIIII', 1, 12, 20, 0, Height, Width))
                    output_file.write(struct.pack('>II', 14, 64))
                    output_file.write(struct.pack('>IIII', 0, 0, 1, 1))
                    output_file.write(struct.pack('>f', 0))
                    output_file.write(struct.pack('>BBBB', 0, 0, 0, 0))
                    output_file.write(Bitmap)
            else:
                with open(file_path, 'wb') as output_file:
                    output_file.write(struct.pack('ccc', b'D', b'D', b'S',))
                    output_file.write(b'\x20')
                    output_file.write(struct.pack('I', 124))
                    output_file.write(struct.pack('I', 528391))
                    output_file.write(struct.pack('I', Height))
                    output_file.write(struct.pack('I', Width))
                    output_file.write(struct.pack('III', 0, 0, MipMapCount))
                    for x in range(11):
                        output_file.write(struct.pack('I', 0))
                    output_file.write(struct.pack('I', 32))
                    output_file.write(struct.pack('I', 4))
                    output_file.write(EncodeOut)
                    output_file.write(struct.pack('IIIII', 0, 0, 0, 0, 0))
                    output_file.write(struct.pack('I', 4096))
                    output_file.write(struct.pack('IIII', 0, 0, 0, 0))
                    if not basename.endswith('.milo_xbox'):            
                        output_file.write(Bitmap)
                    else:
                        for Pixel in Pixels:
                            byte1, byte2 = Pixel
                            output_file.write(byte1)
                            output_file.write(byte2)
            
            print("Exported texture:", file_path)
        elif context.scene.games == 'OPTION_B':
            f.seek(18)
            # Extract width and height
            if LittleEndian == True:
                Width = l_int(f)
                Height = l_int(f)
            if BigEndian == True:
                Width = b_int(f)
                Height = b_int(f)                
            # Grab texture name
            # Lego developers were on something...
            f.seek(4, 1)
            if LittleEndian == True:
                TextureName = l_numstring(f)
            if BigEndian == True:
                TextureName = b_numstring(f)
            f.seek(11, 1)
            if LittleEndian == True:
                Encoding = l_int(f)
            if BigEndian == True:
                Encoding = b_int(f)
            # Grab mipmap count
            if LittleEndian == True:
                MipMapCount = struct.unpack('B', f.read(1))
            if BigEndian == True:
                MipMapCount = struct.unpack('>B', f.read(1))
            MipMapCount = int.from_bytes(MipMapCount, byteorder='little')
            EncodeOut = b''
            if Encoding == 8:
                EncodeOut = b'\x44\x58\x54\x31'
            elif Encoding == 24:
                EncodeOut = b'\x44\x58\x54\x35'
            elif Encoding == 32:
                EncodeOut = b'\x41\x54\x49\x32'
            f.seek(25, 1)
            # Read bitmap (just reads the rest of the file as we already grabbed all important header data)
            if not basename.endswith('.milo_xbox'):
                Bitmap = f.read()
            else:
                BitmapOffset = f.tell()
                Bitmap = f.read()
                f.seek(BitmapOffset)
                Pixels = []
                for x in range(len(Bitmap)):
                    Pixel1 = f.read(1)
                    Pixel2 = f.read(1)
                    Pixels.append((Pixel2, Pixel1))
            if basename.endswith('.milo_wii'):
                file_path = os.path.join(directory, filename[:-4] + ".tpl")
            else:
                file_path = os.path.join(directory, filename[:-4] + ".dds")

            # Export texture out
            if basename.endswith('.milo_wii'):
                with open(file_path, 'wb') as output_file:
                    output_file.write(b'\x00\x20\xAF\x30')
                    output_file.write(struct.pack('>IIIIII', 1, 12, 20, 0, Height, Width))
                    output_file.write(struct.pack('>II', 14, 64))
                    output_file.write(struct.pack('>IIII', 0, 0, 1, 1))
                    output_file.write(struct.pack('>f', 0))
                    output_file.write(struct.pack('>BBBB', 0, 0, 0, 0))
                    output_file.write(Bitmap)
            else:
                with open(file_path, 'wb') as output_file:
                    output_file.write(struct.pack('ccc', b'D', b'D', b'S',))
                    output_file.write(b'\x20')
                    output_file.write(struct.pack('I', 124))
                    output_file.write(struct.pack('I', 528391))
                    output_file.write(struct.pack('I', Height))
                    output_file.write(struct.pack('I', Width))
                    output_file.write(struct.pack('III', 0, 0, MipMapCount))
                    for x in range(11):
                        output_file.write(struct.pack('I', 0))
                    output_file.write(struct.pack('I', 32))
                    output_file.write(struct.pack('I', 4))
                    output_file.write(EncodeOut)
                    output_file.write(struct.pack('IIIII', 0, 0, 0, 0, 0))
                    output_file.write(struct.pack('I', 4096))
                    output_file.write(struct.pack('IIII', 0, 0, 0, 0))
                    if not basename.endswith('.milo_xbox'):            
                        output_file.write(Bitmap)
                    else:
                        for Pixel in Pixels:
                            byte1, byte2 = Pixel
                            output_file.write(byte1)
                            output_file.write(byte2)
            
            print("Exported texture:", file_path)            
        elif context.scene.games == 'OPTION_C':
            f.seek(17)
            # Extract width and height
            if LittleEndian == True:
                Width = l_int(f)
                Height = l_int(f)
            if BigEndian == True:
                Width = b_int(f)
                Height = b_int(f)
            f.seek(4, 1)
            # Grab texture name
            # Lego developers were on something...
            if LittleEndian == True:
                TextureName = l_numstring(f)
            if BigEndian == True:
                TextureName = b_numstring(f)
            f.seek(12, 1)
            if LittleEndian == True:
                Encoding = l_int(f)
            if BigEndian == True:
                Encoding = b_int(f)
            # Grab mipmap count
            if LittleEndian == True:
                MipMapCount = struct.unpack('B', f.read(1))
            if BigEndian == True:
                MipMapCount = struct.unpack('>B', f.read(1))
            MipMapCount = int.from_bytes(MipMapCount, byteorder='little')
            EncodeOut = b''
            if Encoding == 8:
                EncodeOut = b'\x44\x58\x54\x31'
            elif Encoding == 24:
                EncodeOut = b'\x44\x58\x54\x35'
            elif Encoding == 32:
                EncodeOut = b'\x41\x54\x49\x32'
            f.seek(25, 1)
            # Read bitmap (just reads the rest of the file as we already grabbed all important header data)
            if not basename.endswith('.milo_xbox'):
                Bitmap = f.read()
            else:
                BitmapOffset = f.tell()
                Bitmap = f.read()
                f.seek(BitmapOffset)
                Pixels = []
                for x in range(len(Bitmap)):
                    Pixel1 = f.read(1)
                    Pixel2 = f.read(1)
                    Pixels.append((Pixel2, Pixel1))
            if basename.endswith('.milo_wii'):
                file_path = os.path.join(directory, filename[:-4] + ".tpl")
            else:
                file_path = os.path.join(directory, filename[:-4] + ".dds")

            # Export texture out
            if basename.endswith('.milo_wii'):
                with open(file_path, 'wb') as output_file:
                    output_file.write(b'\x00\x20\xAF\x30')
                    output_file.write(struct.pack('>IIIIII', 1, 12, 20, 0, Height, Width))
                    output_file.write(struct.pack('>II', 14, 64))
                    output_file.write(struct.pack('>IIII', 0, 0, 1, 1))
                    output_file.write(struct.pack('>f', 0))
                    output_file.write(struct.pack('>BBBB', 0, 0, 0, 0))
                    output_file.write(Bitmap)
            else:
                with open(file_path, 'wb') as output_file:
                    output_file.write(struct.pack('ccc', b'D', b'D', b'S',))
                    output_file.write(b'\x20')
                    output_file.write(struct.pack('I', 124))
                    output_file.write(struct.pack('I', 528391))
                    output_file.write(struct.pack('I', Height))
                    output_file.write(struct.pack('I', Width))
                    output_file.write(struct.pack('III', 0, 0, MipMapCount))
                    for x in range(11):
                        output_file.write(struct.pack('I', 0))
                    output_file.write(struct.pack('I', 32))
                    output_file.write(struct.pack('I', 4))
                    output_file.write(EncodeOut)
                    output_file.write(struct.pack('IIIII', 0, 0, 0, 0, 0))
                    output_file.write(struct.pack('I', 4096))
                    output_file.write(struct.pack('IIII', 0, 0, 0, 0))
                    if not basename.endswith('.milo_xbox'):            
                        output_file.write(Bitmap)
                    else:
                        for Pixel in Pixels:
                            byte1, byte2 = Pixel
                            output_file.write(byte1)
                            output_file.write(byte2)
            
            print("Exported texture:", file_path)
        f.close()
        del f
    except Exception as e:
        print(e)
        
def Mesh(self, filename, file, basename, MatTexNames, MatTexFiles):
    f = io.BytesIO(file)
    # Hacky way to guess endian
    Versions = [10, 13, 14, 22, 25, 28, 29, 34, 36, 37, 38]
    LittleEndian = False
    BigEndian = False
    Version = struct.unpack('I', f.read(4))[0]
    if Version not in Versions:
        BigEndian = True
        f.seek(-4, 1)
        Version = struct.unpack('>I', f.read(4))[0]
    if Version in Versions:
        LittleEndian = True
    if Version == 14 and LittleEndian == True:
        f.seek(8)
        LocalTFM = struct.unpack('12f', f.read(48))
        WorldTFM = struct.unpack('12f', f.read(48))
        TransCount = l_int(f)
        for x in range(TransCount):
            TransObject = l_numstring(f)
        f.seek(16, 1)
        f.seek(5, 1)
        DrawCount = l_int(f)
        for x in range(DrawCount):
            DrawObject = l_numstring(f)
        f.seek(4, 1)
        BoneCount = l_int(f)
        for x in range(BoneCount):
            Bone = l_numstring(f)
        f.seek(8, 1)
        MatName = l_numstring(f)
        MeshName = l_numstring(f)
        TransParent = l_numstring(f)
        f.seek(16, 1)
        UnkString = l_numstring(f)
        f.seek(5, 1)
        VertCount = l_int(f)
        Verts = []
        Normals = []
        Weights = []
        UVs = []
        Indices = []
        for i in range(VertCount):
            x, y, z = struct.unpack('fff', f.read(12))
            b1, b2, b3, b4 = struct.unpack('HHHH', f.read(8))
            nx, ny, nz = struct.unpack('fff', f.read(12))
            w1, w2, w3, w4 = struct.unpack('ffff', f.read(16))
            u, v = struct.unpack('ff', f.read(8))
            Verts.append((x, y, z))
            Normals.append((nx, ny, nz))
            Weights.append((w1, w2, w3, w4))
            UVs.append((u, v))
            Indices.append((b1, b2, b3, b4))
        FaceCount = l_int(f)
        Faces = []
        for x in range(FaceCount):
            Face = struct.unpack('HHH', f.read(6))
            Faces.append(Face)
        mesh = bpy.data.meshes.new(name=filename)
        obj = bpy.data.objects.new(filename, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.matrix_world = mathutils.Matrix((
            (WorldTFM[0], WorldTFM[3], WorldTFM[6], WorldTFM[9],),
            (WorldTFM[1], WorldTFM[4], WorldTFM[7], WorldTFM[10],),
            (WorldTFM[2], WorldTFM[5], WorldTFM[8], WorldTFM[11],),
            (0.0, 0.0, 0.0, 1.0),
        ))
        mesh.from_pydata(Verts, [], Faces)
        mesh.use_auto_smooth = True
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for face in mesh.polygons:
            face.use_smooth = True
            for loop_index in face.loop_indices:
                vertex_index = mesh.loops[loop_index].vertex_index
                uv = UVs[vertex_index]
                flip = (uv[0], 1 - uv[1])
                uv_layer.data[loop_index].uv = flip
        mesh.update()            
    if Version == 22 and LittleEndian == True:
        f.seek(8)
        LocalTFM = struct.unpack('12f', f.read(48))
        WorldTFM = struct.unpack('12f', f.read(48))
        TransCount = l_int(f)
        for x in range(TransCount):
            TransObject = l_numstring(f)
        f.seek(4, 1)
        Target = l_numstring(f)
        f.seek(1, 1)
        Parent = l_numstring(f)
        f.seek(5, 1)
        DrawCount = l_int(f)
        for x in range(DrawCount):
            DrawObject = l_numstring(f)
        f.seek(16, 1)
        MatName = l_numstring(f)
        MeshName = l_numstring(f)
        f.seek(8, 1)
        HasTree = struct.unpack('B', f.read(1))[0]
        if HasTree == 1:
            return
        VertCount = l_int(f)
        Verts = []
        Normals = []
        Weights = []
        UVs = []
        Indices = []
        for i in range(VertCount):
            x, y, z = struct.unpack('fff', f.read(12))
            b1, b2, b3, b4 = struct.unpack('HHHH', f.read(8))
            nx, ny, nz = struct.unpack('fff', f.read(12))
            w1, w2, w3, w4 = struct.unpack('ffff', f.read(16))
            u, v = struct.unpack('ff', f.read(8))
            Verts.append((x, y, z))
            Normals.append((nx, ny, nz))
            Weights.append((w1, w2, w3, w4))
            UVs.append((u, v))
            Indices.append((b1, b2, b3, b4))
        FaceCount = l_int(f)
        Faces = []
        for x in range(FaceCount):
            Face = struct.unpack('HHH', f.read(6))
            Faces.append(Face)
        mesh = bpy.data.meshes.new(name=filename)
        obj = bpy.data.objects.new(filename, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.matrix_world = mathutils.Matrix((
            (WorldTFM[0], WorldTFM[3], WorldTFM[6], WorldTFM[9],),
            (WorldTFM[1], WorldTFM[4], WorldTFM[7], WorldTFM[10],),
            (WorldTFM[2], WorldTFM[5], WorldTFM[8], WorldTFM[11],),
            (0.0, 0.0, 0.0, 1.0),
        ))
        mesh.from_pydata(Verts, [], Faces)
        mesh.use_auto_smooth = True
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for face in mesh.polygons:
            face.use_smooth = True
            for loop_index in face.loop_indices:
                vertex_index = mesh.loops[loop_index].vertex_index
                uv = UVs[vertex_index]
                flip = (uv[0], 1 - uv[1])
                uv_layer.data[loop_index].uv = flip
        mesh.update()        
    if Version == 25 and LittleEndian == True:
        if self.shadow_setting:
            if "shadow" in filename:
                return
        f.seek(8)
        LocalTFM = struct.unpack('12f', f.read(48))
        WorldTFM = struct.unpack('12f', f.read(48))
        TransCount = l_int(f)
        for x in range(TransCount):
            TransObject = l_numstring(f)
        f.seek(4, 1)
        Target = l_numstring(f)
        f.seek(1, 1)
        Parent = l_numstring(f)
        f.seek(5, 1)
        DrawCount = l_int(f)
        for x in range(DrawCount):
            DrawObject = l_numstring(f)
        f.seek(16, 1)
        MatName = l_numstring(f)
        MeshName = l_numstring(f)
        f.seek(9, 1)
        VertCount = l_int(f)
        Verts = []
        Normals = []
        Weights = []
        UVs = []
        for i in range(VertCount):
            x, y, z = struct.unpack('fff', f.read(12))
            nx, ny, nz = struct.unpack('fff', f.read(12))
            w1, w2, w3, w4 = struct.unpack('ffff', f.read(16))
            u, v = struct.unpack('ff', f.read(8))
            Verts.append((x, y, z))
            Normals.append((nx, ny, nz))
            Weights.append((w1, w2, w3, w4))
            UVs.append((u, v))
        FaceCount = l_int(f)
        Faces = []
        for x in range(FaceCount):
            Face = struct.unpack('HHH', f.read(6))
            Faces.append(Face)
        mesh = bpy.data.meshes.new(name=filename)
        obj = bpy.data.objects.new(filename, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.matrix_world = mathutils.Matrix((
            (WorldTFM[0], WorldTFM[3], WorldTFM[6], WorldTFM[9],),
            (WorldTFM[1], WorldTFM[4], WorldTFM[7], WorldTFM[10],),
            (WorldTFM[2], WorldTFM[5], WorldTFM[8], WorldTFM[11],),
            (0.0, 0.0, 0.0, 1.0),
        ))
        mesh.from_pydata(Verts, [], Faces)
        mesh.use_auto_smooth = True
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for face in mesh.polygons:
            face.use_smooth = True
            for loop_index in face.loop_indices:
                vertex_index = mesh.loops[loop_index].vertex_index
                uv = UVs[vertex_index]
                flip = (uv[0], 1 - uv[1])
                uv_layer.data[loop_index].uv = flip
        mesh.update()
    if Version == 28 and LittleEndian == True:
        if self.shadow_setting:
            if "shadow" in filename:
                return
        if basename.endswith('.milo_xbox'):
            f.seek(21)
        else:
            f.seek(17)
        LocalTFM = struct.unpack('12f', f.read(48))
        WorldTFM = struct.unpack('12f', f.read(48))
        f.seek(4, 1)
        Target = l_int(f)
        f.seek(1, 1)
        Parent = l_numstring(f)
        f.seek(25, 1)
        MatName = l_numstring(f)
        MeshName = l_numstring(f)
        f.seek(9, 1)
        VertCount = l_int(f)
        Verts = []
        Normals = []
        Weights = []
        UVs = []
        for i in range(VertCount):
            x, y, z = struct.unpack('fff', f.read(12))
            nx, ny, nz = struct.unpack('fff', f.read(12))
            w1, w2, w3, w4 = struct.unpack('ffff', f.read(16))
            u, v = struct.unpack('ff', f.read(8))
            Verts.append((x, y, z))
            Normals.append((nx, ny, nz))
            Weights.append((w1, w2, w3, w4))
            UVs.append((u, v))
        FaceCount = l_int(f)
        Faces = []
        for x in range(FaceCount):
            Face = struct.unpack('HHH', f.read(6))
            Faces.append(Face)
        mesh = bpy.data.meshes.new(name=filename)
        obj = bpy.data.objects.new(filename, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.matrix_world = mathutils.Matrix((
            (WorldTFM[0], WorldTFM[3], WorldTFM[6], WorldTFM[9],),
            (WorldTFM[1], WorldTFM[4], WorldTFM[7], WorldTFM[10],),
            (WorldTFM[2], WorldTFM[5], WorldTFM[8], WorldTFM[11],),
            (0.0, 0.0, 0.0, 1.0),
        ))
        mesh.from_pydata(Verts, [], Faces)
        mesh.use_auto_smooth = True
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for face in mesh.polygons:
            face.use_smooth = True
            for loop_index in face.loop_indices:
                vertex_index = mesh.loops[loop_index].vertex_index
                uv = UVs[vertex_index]
                flip = (uv[0], 1 - uv[1])
                uv_layer.data[loop_index].uv = flip
        mesh.update()
        if basename.endswith('.milo_xbox'):
            if len(MatName) != 0:
                mat = bpy.data.materials.get(MatName)
                if mat is None:
                    mat = bpy.data.materials.new(name=MatName)
                obj = bpy.context.active_object
                if obj:
                    if obj.data.materials:
                        obj.data.materials[0] = mat
                    else:
                        obj.data.materials.append(mat)
            for name, file in zip(MatTexNames, MatTexFiles):
                if name.endswith('.tex'):
                    texture = bpy.data.textures.new(name=name, type='IMAGE')
                    base_folder = os.path.dirname(self.filepath)
                    texpath = os.path.join(base_folder, name[:-4] + ".dds")
                    if os.path.exists(texpath):
                        image = bpy.data.images.load(texpath)
                        texture.image = image
                elif name.endswith('.mat'):
                    mat = bpy.data.materials.get(name)
                    if mat:
                        f = io.BytesIO(file)
                        f.seek(12)
                        HasTree = struct.unpack('B', f.read(1))
                        if HasTree == 1:
                            ChildCount = struct.unpack('H', f.read(2))[0]
                            ID = l_int(f)
                            for x in range(ChildCount):
                                NodeType = l_int(f)
                                Child = l_numstring(f)
                        f.seek(88, 1)
                        TexName = l_numstring(f)
                        tex = bpy.data.textures.get(TexName)
                        if tex:
                            if not mat.use_nodes:
                                mat.use_nodes = True
                            bsdf = mat.node_tree.nodes.get("Principled BSDF")
                            if bsdf:
                                tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
                                tex_node.image = tex.image
                                links = mat.node_tree.links
                                links.new(bsdf.inputs['Base Color'], tex_node.outputs['Color'])            
                        else:
                            f.seek(12)
                            HasTree = struct.unpack('B', f.read(1))
                            if HasTree == 1:
                                ChildCount = struct.unpack('H', f.read(2))[0]
                                ID = l_int(f)
                                for x in range(ChildCount):
                                    NodeType = l_int(f)
                                    Child = l_numstring(f)
                            f.seek(8, 1)
                            r = l_float(f)
                            g = l_float(f)
                            b = l_float(f)
                            a = l_float(f)
                            mat.diffuse_color = (r, g, b, a)            
    if Version == 34 and BigEndian == True:
        if self.low_lod_setting:
            if "lod01" in filename or "lod02" in filename:
                return
        if self.shadow_setting:
            if "shadow" in filename:
                return
        f.seek(21)
        LocalTFM = struct.unpack('>12f', f.read(48))
        WorldTFM = struct.unpack('>12f', f.read(48))
        f.seek(4, 1)
        Target = b_numstring(f)
        f.seek(1, 1)
        Parent = b_numstring(f)
        f.seek(25, 1)
        MatName = b_numstring(f)
        MeshName = b_numstring(f)
        f.seek(9, 1)
        VertCount = b_int(f)
        Verts = []
        Normals = []
        Weights = []
        UVs = []
        Indices = []
        for i in range(VertCount):
            x, y, z, w = struct.unpack('>ffff', f.read(16))                
            nx, ny, nz, nw = struct.unpack('>ffff', f.read(16))
            w1, w2, w3, w4 = struct.unpack('>ffff', f.read(16))
            u, v = struct.unpack('>ff', f.read(8))
            b1, b2, b3, b4 = struct.unpack('>HHHH', f.read(8))
            f.seek(16, 1)
            Verts.append((x, y, z))
            Normals.append((nx, ny, nz))
            Weights.append((w1, w2, w3, w4))
            UVs.append((u, v))
            Indices.append((b1, b2, b3, b4))
        FaceCount = b_int(f)
        Faces = []
        for x in range(FaceCount):
            Face = struct.unpack('>HHH', f.read(6))
            Faces.append(Face)
        GroupSizesCount = b_int(f)
        for x in range(GroupSizesCount):
            f.read(1)
        BoneNames = []
        BoneCount = b_int(f)
        for x in range(BoneCount):
            BoneName = b_numstring(f)
            TFM = struct.unpack('>12f', f.read(48))
            BoneNames.append(BoneName)
        mesh = bpy.data.meshes.new(name=filename)
        obj = bpy.data.objects.new(filename, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.matrix_world = mathutils.Matrix((
            (WorldTFM[0], WorldTFM[3], WorldTFM[6], WorldTFM[9],),
            (WorldTFM[1], WorldTFM[4], WorldTFM[7], WorldTFM[10],),
            (WorldTFM[2], WorldTFM[5], WorldTFM[8], WorldTFM[11],),
            (0.0, 0.0, 0.0, 1.0),
        ))
        mesh.from_pydata(Verts, [], Faces)
        mesh.use_auto_smooth = True
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for face in mesh.polygons:
            face.use_smooth = True
            for loop_index in face.loop_indices:
                vertex_index = mesh.loops[loop_index].vertex_index
                uv = UVs[vertex_index]
                flip = (uv[0], 1 - uv[1])
                uv_layer.data[loop_index].uv = flip
        mesh.update()
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        try:
            for i, vertex in enumerate(mesh.vertices):
                if i < len(Indices):
                    group_names = [BoneNames[idx] for idx in Indices[i]]
                    group_weights = Weights[i]
                            
                    for group_name, weight in zip(group_names, group_weights):
                        if group_name not in obj.vertex_groups:
                            obj.vertex_groups.new(name=group_name)
                        group_index = obj.vertex_groups[group_name].index
                        obj.vertex_groups[group_index].add([vertex.index], weight, 'REPLACE')
            mesh.update()
            print("Bone weights assigned to:", obj.name)                
        except IndexError:
            print("Invalid weights")
        obj.select_set(False)
        bpy.context.view_layer.objects.active = obj
        if len(MatName) != 0:
            mat = bpy.data.materials.get(MatName)
            if mat is None:
                mat = bpy.data.materials.new(name=MatName)
            obj = bpy.context.active_object
            if obj:
                if obj.data.materials:
                    obj.data.materials[0] = mat
                else:
                    obj.data.materials.append(mat)
        if not basename.endswith('.milo_wii'):
            for name, file in zip(MatTexNames, MatTexFiles):
                if name.endswith('.tex'):
                    texture = bpy.data.textures.new(name=name, type='IMAGE')
                    base_folder = os.path.dirname(self.filepath)
                    texpath = os.path.join(base_folder, name[:-4] + ".dds")
                    if os.path.exists(texpath):
                        image = bpy.data.images.load(texpath)
                        texture.image = image
                elif name.endswith('.mat'):
                    mat = bpy.data.materials.get(name)
                    if mat:
                        f = io.BytesIO(file)
                        f.seek(12)
                        HasTree = struct.unpack('B', f.read(1))
                        if HasTree == 1:
                            ChildCount = struct.unpack('H', f.read(2))[0]
                            ID = l_int(f)
                            for x in range(ChildCount):
                                NodeType = l_int(f)
                                Child = l_numstring(f)
                        f.seek(92, 1)
                        TexName = b_numstring(f)
                        tex = bpy.data.textures.get(TexName)
                        if tex:
                            if not mat.use_nodes:
                                mat.use_nodes = True
                            bsdf = mat.node_tree.nodes.get("Principled BSDF")
                            if bsdf:
                                tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
                                tex_node.image = tex.image
                                links = mat.node_tree.links
                                links.new(bsdf.inputs['Base Color'], tex_node.outputs['Color'])            
                        else:
                            f.seek(12)
                            HasTree = struct.unpack('B', f.read(1))
                            if HasTree == 1:
                                ChildCount = struct.unpack('H', f.read(2))[0]
                                ID = l_int(f)
                                for x in range(ChildCount):
                                    NodeType = l_int(f)
                                    Child = l_numstring(f)
                            f.seek(8, 1)
                            r = b_float(f)
                            g = b_float(f)
                            b = b_float(f)
                            a = b_float(f)
                            mat.diffuse_color = (r, g, b, a)                    
    if Version == 36 and BigEndian == True:
        if self.low_lod_setting:
            if "lod01" in filename or "lod02" in filename:
                return
        if self.shadow_setting:
            if "shadow" in filename:
                return
        f.seek(21)
        LocalTFM = struct.unpack('>12f', f.read(48))
        WorldTFM = struct.unpack('>12f', f.read(48))
        f.seek(4, 1)
        Target = b_numstring(f)
        f.seek(1, 1)
        Parent = b_numstring(f)
        f.seek(25, 1)
        MatName = b_numstring(f)
        MeshName = b_numstring(f)
        f.seek(9, 1)
        VertCount = b_int(f)
        if basename.endswith('.milo_wii'):
            f.seek(1, 1)
        else:
            f.seek(9, 1)
        Verts = []
        Normals = []
        Weights = []
        UVs = []
        Indices = []
        for i in range(VertCount):
            x, y, z = struct.unpack('>fff', f.read(12))
            if basename.endswith('.milo_wii'):
                nx, ny, nz = struct.unpack('>fff', f.read(12))
                w1, w2, w3, w4 = struct.unpack('>ffff', f.read(16))
                u, v = struct.unpack('>ff', f.read(8))
                b1, b2, b3, b4 = struct.unpack('>HHHH', f.read(8))
                f.seek(16, 1)
            elif basename.endswith('.milo_xbox'):
                u, v = struct.unpack('>ee', f.read(4))
                f.seek(16, 1)
            elif basename.endswith('.milo_ps3'):
                u, v = struct.unpack('>ee', f.read(4))
                f.seek(20, 1)
            Verts.append((x, y, z))
            if basename.endswith('.milo_wii'):
                Normals.append((nx, ny, nz))
                Weights.append((w1, w2, w3, w4))
                Indices.append((b1, b2, b3, b4))
            UVs.append((u, v))
        FaceCount = b_int(f)
        Faces = []
        for x in range(FaceCount):
            Face = struct.unpack('>HHH', f.read(6))
            Faces.append(Face)
        GroupSizesCount = b_int(f)
        for x in range(GroupSizesCount):
            f.read(1)
        BoneNames = []
        BoneCount = b_int(f)
        for x in range(BoneCount):
            BoneName = b_numstring(f)
            TFM = struct.unpack('>12f', f.read(48))
            BoneNames.append(BoneName)
        mesh = bpy.data.meshes.new(name=filename)
        obj = bpy.data.objects.new(filename, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.matrix_world = mathutils.Matrix((
            (WorldTFM[0], WorldTFM[3], WorldTFM[6], WorldTFM[9],),
            (WorldTFM[1], WorldTFM[4], WorldTFM[7], WorldTFM[10],),
            (WorldTFM[2], WorldTFM[5], WorldTFM[8], WorldTFM[11],),
            (0.0, 0.0, 0.0, 1.0),
        ))
        mesh.from_pydata(Verts, [], Faces)
        mesh.use_auto_smooth = True
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for face in mesh.polygons:
            face.use_smooth = True
            for loop_index in face.loop_indices:
                vertex_index = mesh.loops[loop_index].vertex_index
                uv = UVs[vertex_index]
                flip = (uv[0], 1 - uv[1])
                uv_layer.data[loop_index].uv = flip
        mesh.update()
        if basename.endswith('.milo_wii'):
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            try:
                for i, vertex in enumerate(mesh.vertices):
                    if i < len(Indices):
                        group_names = [BoneNames[idx] for idx in Indices[i]]
                        group_weights = Weights[i]
                                
                        for group_name, weight in zip(group_names, group_weights):
                            if group_name not in obj.vertex_groups:
                                obj.vertex_groups.new(name=group_name)
                            group_index = obj.vertex_groups[group_name].index
                            obj.vertex_groups[group_index].add([vertex.index], weight, 'REPLACE')
                mesh.update()
                print("Bone weights assigned to:", obj.name)                
            except IndexError:
                print("Invalid weights")
            obj.select_set(False)
        bpy.context.view_layer.objects.active = obj
        if len(MatName) != 0:
            mat = bpy.data.materials.get(MatName)
            if mat is None:
                mat = bpy.data.materials.new(name=MatName)
            obj = bpy.context.active_object
            if obj:
                if obj.data.materials:
                    obj.data.materials[0] = mat
                else:
                    obj.data.materials.append(mat)
        if not basename.endswith('.milo_wii'):
            for name, file in zip(MatTexNames, MatTexFiles):
                if name.endswith('.tex'):
                    texture = bpy.data.textures.new(name=name, type='IMAGE')
                    base_folder = os.path.dirname(self.filepath)
                    texpath = os.path.join(base_folder, name[:-4] + ".dds")
                    if os.path.exists(texpath):
                        image = bpy.data.images.load(texpath)
                        texture.image = image
                elif name.endswith('.mat'):
                    mat = bpy.data.materials.get(name)
                    if mat:
                        f = io.BytesIO(file)
                        f.seek(12)
                        HasTree = struct.unpack('B', f.read(1))
                        if HasTree == 1:
                            ChildCount = struct.unpack('H', f.read(2))[0]
                            ID = l_int(f)
                            for x in range(ChildCount):
                                NodeType = l_int(f)
                                Child = l_numstring(f)
                        f.seek(92, 1)
                        TexName = b_numstring(f)
                        tex = bpy.data.textures.get(TexName)
                        if tex:
                            if not mat.use_nodes:
                                mat.use_nodes = True
                            bsdf = mat.node_tree.nodes.get("Principled BSDF")
                            if bsdf:
                                tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
                                tex_node.image = tex.image
                                links = mat.node_tree.links
                                links.new(bsdf.inputs['Base Color'], tex_node.outputs['Color'])            
                        else:
                            f.seek(12)
                            HasTree = struct.unpack('B', f.read(1))
                            if HasTree == 1:
                                ChildCount = struct.unpack('H', f.read(2))[0]
                                ID = l_int(f)
                                for x in range(ChildCount):
                                    NodeType = l_int(f)
                                    Child = l_numstring(f)
                            f.seek(8, 1)
                            r = b_float(f)
                            g = b_float(f)
                            b = b_float(f)
                            a = b_float(f)
                            mat.diffuse_color = (r, g, b, a)
    if Version == 37 and BigEndian == True:
        if self.low_lod_setting:
            if "LOD01" in filename or "LOD02" in filename:
                return
        if self.shadow_setting:
            if "shadow" in filename:
                return
        f.seek(21)
        LocalTFM = struct.unpack('>12f', f.read(48))
        WorldTFM = struct.unpack('>12f', f.read(48))
        f.seek(4, 1)
        Target = b_numstring(f)
        f.seek(1, 1)
        Parent = b_numstring(f)
        f.seek(29, 1)
        MatName = b_numstring(f)
        MeshName = b_numstring(f)
        f.seek(9, 1)
        VertCount = b_int(f)
        if basename.endswith('.milo_wii'):
            f.seek(1, 1)
        else:
            f.seek(9, 1)
        Verts = []
        Normals = []
        Weights = []
        UVs = []
        Indices = []
        for i in range(VertCount):
            x, y, z = struct.unpack('>fff', f.read(12))
            if basename.endswith('.milo_wii'):
                nx, ny, nz = struct.unpack('>fff', f.read(12))
                w1, w2, w3, w4 = struct.unpack('>ffff', f.read(16))
                u, v = struct.unpack('>ff', f.read(8))
                b1, b2, b3, b4 = struct.unpack('>HHHH', f.read(8))
                f.seek(16, 1)
            elif basename.endswith('.milo_xbox'):
                u, v = struct.unpack('>ee', f.read(4))
                f.seek(16, 1)
            elif basename.endswith('.milo_ps3'):
                u, v = struct.unpack('>ee', f.read(4))
                f.seek(20, 1)
            Verts.append((x, y, z))
            if basename.endswith('.milo_wii'):
                Normals.append((nx, ny, nz))
                Weights.append((w1, w2, w3, w4))
                Indices.append((b1, b2, b3, b4))
            UVs.append((u, v))
        FaceCount = b_int(f)
        Faces = []
        for x in range(FaceCount):
            Face = struct.unpack('>HHH', f.read(6))
            Faces.append(Face)
        GroupSizesCount = b_int(f)
        for x in range(GroupSizesCount):
            f.read(1)
        BoneNames = []
        BoneCount = b_int(f)
        for x in range(BoneCount):
            BoneName = b_numstring(f)
            TFM = struct.unpack('>12f', f.read(48))
            BoneNames.append(BoneName)
        mesh = bpy.data.meshes.new(name=filename)
        obj = bpy.data.objects.new(filename, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.matrix_world = mathutils.Matrix((
            (WorldTFM[0], WorldTFM[3], WorldTFM[6], WorldTFM[9],),
            (WorldTFM[1], WorldTFM[4], WorldTFM[7], WorldTFM[10],),
            (WorldTFM[2], WorldTFM[5], WorldTFM[8], WorldTFM[11],),
            (0.0, 0.0, 0.0, 1.0),
        ))
        mesh.from_pydata(Verts, [], Faces)
        mesh.use_auto_smooth = True
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for face in mesh.polygons:
            face.use_smooth = True
            for loop_index in face.loop_indices:
                vertex_index = mesh.loops[loop_index].vertex_index
                uv = UVs[vertex_index]
                flip = (uv[0], 1 - uv[1])
                uv_layer.data[loop_index].uv = flip
        mesh.update()
        if basename.endswith('.milo_wii'):
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            try:
                for i, vertex in enumerate(mesh.vertices):
                    if i < len(Indices):
                        group_names = [BoneNames[idx] for idx in Indices[i]]
                        group_weights = Weights[i]
                                
                        for group_name, weight in zip(group_names, group_weights):
                            if group_name not in obj.vertex_groups:
                                obj.vertex_groups.new(name=group_name)
                            group_index = obj.vertex_groups[group_name].index
                            obj.vertex_groups[group_index].add([vertex.index], weight, 'REPLACE')
                mesh.update()
                print("Bone weights assigned to:", obj.name)                
            except IndexError:
                print("Invalid weights")
            obj.select_set(False)
        bpy.context.view_layer.objects.active = obj
        if len(MatName) != 0:
            mat = bpy.data.materials.get(MatName)
            if mat is None:
                mat = bpy.data.materials.new(name=MatName)
            obj = bpy.context.active_object
            if obj:
                if obj.data.materials:
                    obj.data.materials[0] = mat
                else:
                    obj.data.materials.append(mat)
        if not basename.endswith('.milo_wii'):
            for name, file in zip(MatTexNames, MatTexFiles):
                if name.endswith('.tex'):
                    texture = bpy.data.textures.new(name=name, type='IMAGE')
                    base_folder = os.path.dirname(self.filepath)
                    texpath = os.path.join(base_folder, name[:-4] + ".dds")
                    if os.path.exists(texpath):
                        image = bpy.data.images.load(texpath)
                        texture.image = image
                elif name.endswith('.mat'):
                    mat = bpy.data.materials.get(name)
                    if mat:
                        f = io.BytesIO(file)
                        f.seek(12)
                        HasTree = struct.unpack('B', f.read(1))
                        if HasTree == 1:
                            ChildCount = struct.unpack('H', f.read(2))[0]
                            ID = l_int(f)
                            for x in range(ChildCount):
                                NodeType = l_int(f)
                                Child = l_numstring(f)
                        f.seek(92, 1)
                        TexName = b_numstring(f)
                        tex = bpy.data.textures.get(TexName)
                        if tex:
                            if not mat.use_nodes:
                                mat.use_nodes = True
                            bsdf = mat.node_tree.nodes.get("Principled BSDF")
                            if bsdf:
                                tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
                                tex_node.image = tex.image
                                links = mat.node_tree.links
                                links.new(bsdf.inputs['Base Color'], tex_node.outputs['Color'])            
                        else:
                            f.seek(12)
                            HasTree = struct.unpack('B', f.read(1))
                            if HasTree == 1:
                                ChildCount = struct.unpack('H', f.read(2))[0]
                                ID = l_int(f)
                                for x in range(ChildCount):
                                    NodeType = l_int(f)
                                    Child = l_numstring(f)
                            f.seek(8, 1)
                            r = b_float(f)
                            g = b_float(f)
                            b = b_float(f)
                            a = b_float(f)
                            mat.diffuse_color = (r, g, b, a)
    if Version == 38 and BigEndian == True:
        if self.low_lod_setting:
            if "lod01" in filename or "lod02" in filename:
                return
        if self.shadow_setting:
            if "shadow" in filename:
                return
        f.seek(21)
        LocalTFM = struct.unpack('>12f', f.read(48))
        WorldTFM = struct.unpack('>12f', f.read(48))
        f.seek(4, 1)
        Target = b_numstring(f)
        f.seek(1, 1)
        Parent = b_numstring(f)
        f.seek(25, 1)
        MatName = b_numstring(f)
        MeshName = b_numstring(f)
        f.seek(9, 1)
        VertCount = b_int(f)
        if basename.endswith('.milo_wii'):
            f.seek(1, 1)
        else:
            f.seek(9, 1)
        Verts = []
        Normals = []
        Weights = []
        UVs = []
        Indices = []
        for i in range(VertCount):
            x, y, z = struct.unpack('>fff', f.read(12))
            if basename.endswith('.milo_wii'):
                nx, ny, nz = struct.unpack('>fff', f.read(12))
                w1, w2, w3, w4 = struct.unpack('>ffff', f.read(16))
                u, v = struct.unpack('>ff', f.read(8))
                b1, b2, b3, b4 = struct.unpack('>HHHH', f.read(8))
                f.seek(16, 1)
            elif basename.endswith('.milo_xbox'):
                u, v = struct.unpack('>ee', f.read(4))
                f.seek(20, 1)
            elif basename.endswith('.milo_ps3'):
                u, v = struct.unpack('>ee', f.read(4))
                f.seek(24, 1)
            Verts.append((x, y, z))
            if basename.endswith('.milo_wii'):
                Normals.append((nx, ny, nz))
                Weights.append((w1, w2, w3, w4))
                Indices.append((b1, b2, b3, b4))
            UVs.append((u, v))
        FaceCount = b_int(f)
        Faces = []
        for x in range(FaceCount):
            Face = struct.unpack('>HHH', f.read(6))
            Faces.append(Face)
        GroupSizesCount = b_int(f)
        for x in range(GroupSizesCount):
            f.read(1)
        BoneNames = []
        BoneCount = b_int(f)
        for x in range(BoneCount):
            BoneName = b_numstring(f)
            TFM = struct.unpack('>12f', f.read(48))
            BoneNames.append(BoneName)
        mesh = bpy.data.meshes.new(name=filename)
        obj = bpy.data.objects.new(filename, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.matrix_world = mathutils.Matrix((
            (WorldTFM[0], WorldTFM[3], WorldTFM[6], WorldTFM[9],),
            (WorldTFM[1], WorldTFM[4], WorldTFM[7], WorldTFM[10],),
            (WorldTFM[2], WorldTFM[5], WorldTFM[8], WorldTFM[11],),
            (0.0, 0.0, 0.0, 1.0),
        ))
        mesh.from_pydata(Verts, [], Faces)
        mesh.use_auto_smooth = True
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for face in mesh.polygons:
            face.use_smooth = True
            for loop_index in face.loop_indices:
                vertex_index = mesh.loops[loop_index].vertex_index
                uv = UVs[vertex_index]
                flip = (uv[0], 1 - uv[1])
                uv_layer.data[loop_index].uv = flip
        mesh.update()
        if basename.endswith('.milo_wii'):
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            try:
                for i, vertex in enumerate(mesh.vertices):
                    if i < len(Indices):
                        group_names = [BoneNames[idx] for idx in Indices[i]]
                        group_weights = Weights[i]
                                
                        for group_name, weight in zip(group_names, group_weights):
                            if group_name not in obj.vertex_groups:
                                obj.vertex_groups.new(name=group_name)
                            group_index = obj.vertex_groups[group_name].index
                            obj.vertex_groups[group_index].add([vertex.index], weight, 'REPLACE')
                mesh.update()
                print("Bone weights assigned to:", obj.name)                
            except IndexError:
                print("Invalid weights")
            obj.select_set(False)
        bpy.context.view_layer.objects.active = obj
        if len(MatName) != 0:
            mat = bpy.data.materials.get(MatName)
            if mat is None:
                mat = bpy.data.materials.new(name=MatName)
            obj = bpy.context.active_object
            if obj:
                if obj.data.materials:
                    obj.data.materials[0] = mat
                else:
                    obj.data.materials.append(mat)
        if not basename.endswith('.milo_wii'):
            for name, file in zip(MatTexNames, MatTexFiles):
                if name.endswith('.tex'):
                    texture = bpy.data.textures.new(name=name, type='IMAGE')
                    base_folder = os.path.dirname(self.filepath)
                    texpath = os.path.join(base_folder, name[:-4] + ".dds")
                    if os.path.exists(texpath):
                        image = bpy.data.images.load(texpath)
                        texture.image = image
                elif name.endswith('.mat'):
                    mat = bpy.data.materials.get(name)
                    if mat:
                        f = io.BytesIO(file)
                        f.seek(12)
                        HasTree = struct.unpack('B', f.read(1))
                        if HasTree == 1:
                            ChildCount = struct.unpack('H', f.read(2))[0]
                            ID = l_int(f)
                            for x in range(ChildCount):
                                NodeType = l_int(f)
                                Child = l_numstring(f)
                        f.seek(92, 1)
                        TexName = b_numstring(f)
                        tex = bpy.data.textures.get(TexName)
                        if tex:
                            if not mat.use_nodes:
                                mat.use_nodes = True
                            bsdf = mat.node_tree.nodes.get("Principled BSDF")
                            if bsdf:
                                tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
                                tex_node.image = tex.image
                                links = mat.node_tree.links
                                links.new(bsdf.inputs['Base Color'], tex_node.outputs['Color'])            
                        else:
                            f.seek(12)
                            HasTree = struct.unpack('B', f.read(1))
                            if HasTree == 1:
                                ChildCount = struct.unpack('H', f.read(2))[0]
                                ID = l_int(f)
                                for x in range(ChildCount):
                                    NodeType = l_int(f)
                                    Child = l_numstring(f)
                            f.seek(8, 1)
                            r = b_float(f)
                            g = b_float(f)
                            b = b_float(f)
                            a = b_float(f)
                            mat.diffuse_color = (r, g, b, a)                            
def DC3Mesh(self, file):
    f = io.BytesIO(file)
    f.seek(21)
    LocalTFM = struct.unpack('>12f', f.read(48))
    WorldTFM = struct.unpack('>12f', f.read(48))
    f.seek(4, 1)
    Target = b_numstring(f)
    f.seek(1, 1)
    Parent = b_numstring(f)
    f.seek(29, 1)
    MatName = b_numstring(f)
    MeshName = b_numstring(f)
    if self.low_lod_setting:
        if "lod" in MeshName
            return
    if self.shadow_setting:
        if "shadow" in MeshName:
            return
    f.seek(9, 1)
    VertCount = b_int(f)
    f.seek(9, 1)
    Verts = []
    UVs = []
    for i in range(VertCount):
        x, y, z = struct.unpack('>fff', f.read(12))
        f.seek(4, 1)
        u, v = struct.unpack('>ee', f.read(4))
        f.seek(16, 1)
        Verts.append((x, y, z))
        UVs.append((u, v))
    FaceCount = b_int(f)
    Faces = []
    for x in range(FaceCount):
        Face = struct.unpack('>HHH', f.read(6))
        Faces.append(Face)
    GroupSizesCount = b_int(f)
    for x in range(GroupSizesCount):
        f.read(1)
    BoneNames = []
    BoneCount = b_int(f)
    for x in range(BoneCount):
        BoneName = b_numstring(f)
        TFM = struct.unpack('>12f', f.read(48))
        BoneNames.append(BoneName)
    mesh = bpy.data.meshes.new(name=MeshName)
    obj = bpy.data.objects.new(MeshName, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.matrix_world = mathutils.Matrix((
        (WorldTFM[0], WorldTFM[3], WorldTFM[6], WorldTFM[9],),
        (WorldTFM[1], WorldTFM[4], WorldTFM[7], WorldTFM[10],),
        (WorldTFM[2], WorldTFM[5], WorldTFM[8], WorldTFM[11],),
        (0.0, 0.0, 0.0, 1.0),
    ))
    mesh.from_pydata(Verts, [], Faces)
    mesh.use_auto_smooth = True
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for face in mesh.polygons:
        face.use_smooth = True
        for loop_index in face.loop_indices:
            vertex_index = mesh.loops[loop_index].vertex_index
            uv = UVs[vertex_index]
            flip = (uv[0], 1 - uv[1])
            uv_layer.data[loop_index].uv = flip
    mesh.update()
    bpy.context.view_layer.objects.active = obj
    if len(MatName) != 0:
        mat = bpy.data.materials.get(MatName)
        if mat is None:
            mat = bpy.data.materials.new(name=MatName)
        obj = bpy.context.active_object
        if obj:
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)

def DC3Tex(self, file):
    try:
        directory = os.path.dirname(self.filepath)
        f = io.BytesIO(file)
        f.seek(17)
        Width = b_int(f)
        Height = b_int(f)
        f.seek(4, 1)
        TexName = b_numstring(f)
        TexName = TexName.strip('../')
        TexName = TexName.replace('/', '_')
        f.seek(16, 1)
        Encoding = b_int(f)
        MipMapCount = struct.unpack('>B', f.read(1))
        MipMapCount = int.from_bytes(MipMapCount, byteorder='little')
        EncodeOut = b''
        if Encoding == 8:
            EncodeOut = b'\x44\x58\x54\x31'
        elif Encoding == 24:
            EncodeOut = b'\x44\x58\x54\x35'
        elif Encoding == 32:
            EncodeOut = b'\x41\x54\x49\x32'
        f.seek(21, 1)
        BitmapOffset = f.tell()
        Bitmap = f.read()
        f.seek(BitmapOffset)
        Pixels = []
        for x in range(len(Bitmap)):
            Pixel1 = f.read(1)
            Pixel2 = f.read(1)
            Pixels.append((Pixel2, Pixel1))
        file_path = os.path.join(directory, TexName[:-4] + ".dds")
        with open(file_path, 'wb') as output_file:
            output_file.write(struct.pack('ccc', b'D', b'D', b'S',))
            output_file.write(b'\x20')
            output_file.write(struct.pack('I', 124))
            output_file.write(struct.pack('I', 528391))
            output_file.write(struct.pack('I', Height))
            output_file.write(struct.pack('I', Width))
            output_file.write(struct.pack('III', 0, 0, MipMapCount))
            for x in range(11):
                output_file.write(struct.pack('I', 0))
            output_file.write(struct.pack('I', 32))
            output_file.write(struct.pack('I', 4))
            output_file.write(EncodeOut)
            output_file.write(struct.pack('IIIII', 0, 0, 0, 0, 0))
            output_file.write(struct.pack('I', 4096))
            output_file.write(struct.pack('IIII', 0, 0, 0, 0))
            for Pixel in Pixels:
                byte1, byte2 = Pixel
                output_file.write(byte1)
                output_file.write(byte2)
            
        print("Exported texture:", file_path)

        f.close()
        del f
    except Exception as e:
        print(e)
        
def Trans(basename, filename, file):        
    f = io.BytesIO(file)
    # Hacky way to guess endian
    Versions = [5, 8, 9]
    LittleEndian = False
    BigEndian = False
    Version = struct.unpack('I', f.read(4))[0]
    if Version not in Versions:
        BigEndian = True
        f.seek(-4, 1)
        Version = struct.unpack('>I', f.read(4))[0]
    elif Version in Versions:
        LittleEndian = True
    if Version == 8 and LittleEndian == True:
        f.seek(8)
        LocalUpper = struct.unpack('9f', f.read(36))
        LocalPos = struct.unpack('3f', f.read(12))
        WorldUpper = struct.unpack('9f', f.read(36))
        WorldPos = struct.unpack('3f', f.read(12))
    if Version == 9 and LittleEndian == True and basename.endswith('.milo_xbox'):
        f.seek(17)
        LocalUpper = struct.unpack('9f', f.read(36))
        LocalPos = struct.unpack('3f', f.read(12))
        WorldUpper = struct.unpack('9f', f.read(36))
        WorldPos = struct.unpack('3f', f.read(12))
    if Version == 9 and basename.endswith('.milo_ps2'):
        f.seek(13)
        LocalUpper = struct.unpack('9f', f.read(36))
        LocalPos = struct.unpack('3f', f.read(12))
        WorldUpper = struct.unpack('9f', f.read(36))
        WorldPos = struct.unpack('3f', f.read(12))
    else:
        f.seek(17)
        LocalUpper = struct.unpack('>9f', f.read(36))
        LocalPos = struct.unpack('>3f', f.read(12))
        WorldUpper = struct.unpack('>9f', f.read(36))
        WorldPos = struct.unpack('>3f', f.read(12))
    if Version == 8 and LittleEndian == True:
        TransCount = l_int(f)
        for x in range(TransCount):
            TransObject = l_numstring(f)
        f.seek(4, 1)
    if Version == 9 and LittleEndian == True and basename.endswith('.milo_ps2'):
        f.seek(113)
    else:
        f.seek(117)
    if Version == 8 or 9 and LittleEndian == True:
        Target = l_numstring(f)
    else:
        Target = b_numstring(f)
    f.seek(1, 1)
    if Version == 8 or 9 and LittleEndian == True:
        ParentName = l_numstring(f)
    else:
        ParentName = b_numstring(f)
    if "Armature" in bpy.data.armatures:
        armature_data = bpy.data.armatures["Armature"]
    else:
        armature_data = bpy.data.armatures.new("Armature")
    if "Armature" in bpy.data.objects:
        armature_obj = bpy.data.objects["Armature"]
    else:
        armature_obj = bpy.data.objects.new("Armature", armature_data)
        bpy.context.scene.collection.objects.link(armature_obj)
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')
    edit_bone = armature_obj.data.edit_bones.get(filename)
    if edit_bone is None:
        edit_bone = armature_obj.data.edit_bones.new(filename)
        edit_bone.head = (0, 0, 0)
        edit_bone.tail = (0, 1, 0)
        edit_bone.use_deform = True
    parent_bone = armature_obj.data.edit_bones.get(ParentName)
    if parent_bone is None:
        parent_bone = armature_obj.data.edit_bones.new(ParentName)
        parent_bone.head = (0, 0, 0)
        parent_bone.tail = (0, 1, 0)
        parent_bone.use_deform = True
    if parent_bone:
        edit_bone.parent = parent_bone
    bpy.ops.object.mode_set(mode='POSE')
    pose_bone = armature_obj.pose.bones.get(filename)
    if pose_bone:
        pose_bone.matrix_basis = mathutils.Matrix((
            (LocalUpper[0], LocalUpper[3], LocalUpper[6], 0.0),
            (LocalUpper[1], LocalUpper[4], LocalUpper[7], 0.0),
            (LocalUpper[2], LocalUpper[5], LocalUpper[8], 0.0),
            (0.0, 0.0, 0.0, 1.0),
        ))
        pose_bone.location = LocalPos  
    bpy.ops.object.mode_set(mode='OBJECT')
        
def TransAnim(file):
    f = io.BytesIO(file)
    # Hacky way to guess endian
    Versions = [4, 6, 7]
    LittleEndian = False
    BigEndian = False
    Version = struct.unpack('I', f.read(4))[0]
    if Version not in Versions:
        BigEndian = True
        f.seek(-4, 1)
        Version = struct.unpack('>I', f.read(4))[0]
    elif Version in Versions:
        LittleEndian = True
    bpy.context.scene.render.fps = 30
    if Version == 4 and LittleEndian == True:
        f.seek(8)
        AnimEntryCount = l_int(f)
        for x in range(AnimEntryCount):
            Name = l_numstring(f)
            F1 = l_float(f)
            F2 = l_float(f)
        AnimCount = l_int(f)
        f.seek(25, 1)
        TransObject = l_numstring(f)
        obj = bpy.data.objects.get(TransObject)
        if obj is None:
            return
        RotKeysCount = l_int(f)
        for x in range(RotKeysCount):
            Quat = struct.unpack('ffff', f.read(16))
            Pos = l_float(f)
            obj.rotation_mode = 'QUATERNION'
            obj.rotation_quaternion = (Quat[3], Quat[0], Quat[1], Quat[2])
            obj.keyframe_insert("rotation_quaternion", frame=Pos)
        TransKeysCount = l_int(f)
        for x in range(TransKeysCount):
            Location = struct.unpack('fff', f.read(12))
            Pos = l_float(f)
            obj.location = Location
            obj.keyframe_insert("location", frame=Pos)
        TransAnimOwner = l_numstring(f)
        f.seek(2, 1)
        ScaleKeysCount = l_int(f)
        for x in range(ScaleKeysCount):
            Scale = struct.unpack('fff', f.read(12))
            Pos = l_float(f)
            obj.scale = Scale
            obj.keyframe_insert("scale", frame=Pos)
    if Version == 6 and LittleEndian == True:
        f.seek(29)
        TransObject = l_numstring(f)
        obj = bpy.data.objects.get(TransObject)
        if obj is None:
            return
        RotKeysCount = l_int(f)
        for x in range(RotKeysCount):
            Quat = struct.unpack('ffff', f.read(16))
            Pos = l_float(f)
            obj.rotation_mode = 'QUATERNION'
            obj.rotation_quaternion = (Quat[3], Quat[0], Quat[1], Quat[2])
            obj.keyframe_insert("rotation_quaternion", frame=Pos)
        TransKeysCount = l_int(f)
        for x in range(TransKeysCount):
            Location = struct.unpack('fff', f.read(12))
            Pos = l_float(f)
            obj.location = Location
            obj.keyframe_insert("location", frame=Pos)
        TransAnimOwner = l_numstring(f)
        f.seek(2, 1)
        ScaleKeysCount = l_int(f)
        for x in range(ScaleKeysCount):
            Scale = struct.unpack('fff', f.read(12))
            Pos = l_float(f)
            obj.scale = Scale
            obj.keyframe_insert("scale", frame=Pos)
    if Version == 7 and BigEndian == True:
        f.seek(29)
        TransObject = b_numstring(f)
        obj = bpy.data.objects.get(TransObject)
        if obj is None:
            return
        RotKeysCount = b_int(f)
        for x in range(RotKeysCount):
            Quat = struct.unpack('>ffff', f.read(16))
            Pos = b_float(f)
            obj.rotation_mode = 'QUATERNION'
            obj.rotation_quaternion = (Quat[3], Quat[0], Quat[1], Quat[2])
            obj.keyframe_insert("rotation_quaternion", frame=Pos)
        TransKeysCount = b_int(f)
        for x in range(TransKeysCount):
            Location = struct.unpack('>fff', f.read(12))
            Pos = b_float(f)
            obj.location = Location
            obj.keyframe_insert("location", frame=Pos)
        TransAnimOwner = b_numstring(f)
        f.seek(2, 1)
        ScaleKeysCount = b_int(f)
        for x in range(ScaleKeysCount):
            Scale = struct.unpack('>fff', f.read(12))
            Pos = b_float(f)
            obj.scale = Scale
            obj.keyframe_insert("scale", frame=Pos)
        

        
def menu_func_import(self, context):
    self.layout.operator(ImportMilo.bl_idname, text="Milo Importer")
    
def register():
    bpy.utils.register_class(ImportMilo)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(ImportMilo)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import) 

if __name__ == "__main__":
    register()

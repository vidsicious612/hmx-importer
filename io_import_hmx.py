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
        default="*.milo_ps3;*.milo_xbox;*.milo_wii;*.rnd_ps2;*.milo_ps2;*.rnd;*.dds",
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

    venue_setting: BoolProperty(
        name="Venue (TBRB)",
        description="Import TBRB venue",
        default=False,
    ) 
    
    GameItems = [
        ('OPTION_A', 'GH1', ''),
        ('OPTION_B', 'GH2 / GH80s', ''),
        ('OPTION_C', 'RB1 / RB2', ''),
        ('OPTION_D', 'RB2 Prototype + LRB Wii', ''),
        ('OPTION_E', 'TBRB', ''),
        ('OPTION_F', 'LRB', ''),
        ('OPTION_G', 'GDRB', ''),
        ('OPTION_H', 'RB3', ''),
    ]
        
    bpy.types.Scene.games = EnumProperty(
        name="Game",
        description="Select a game.",
        items=GameItems,
    )
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.label(text="Select a game:")
        layout.prop(context.scene, "games", text="")
        layout.prop(self, "low_lod_setting")
        layout.prop(self, "shadow_setting")
        layout.prop(self, "venue_setting")

    def execute(self, context):
        with open(self.filepath, 'rb') as f:
            if self.filepath.endswith('.dds'):
                obj = bpy.context.active_object
                mat = obj.data.materials[0]
                image = bpy.data.images.load(self.filepath)
                if mat.use_nodes:
                    nodes = mat.node_tree.nodes
                    principled_bsdf = nodes.get('Principled BSDF')
                    tex_image = nodes.new('ShaderNodeTexImage')
                    tex_image.image = image
                    links = mat.node_tree.links
                    links.new(tex_image.outputs[0], principled_bsdf.inputs['Base Color'])
                obj.data.materials[0] = mat
            else:
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
                f.seek(4, 1)
                dirs = []
                filenames = []
                MatTexNames = []
                MatTexFiles = []
                # GH1
                if context.scene.games == 'OPTION_A':
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
                            Tex(context, basename, self, name, file)
                        if ".mesh" in name and "Mesh" in directory:
                            Mesh(self, context, name, file, basename, MatTexNames, MatTexFiles)
                        if "bone" in name and "Mesh" in directory:
                            Trans(basename, context, name, file)
                        if "TransAnim" in directory:
                            TransAnim(context, file)
                # GH2 / GH80s
                elif context.scene.games == 'OPTION_B':
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
                            Tex(context, basename, self, name, file)
                        if ".mesh" in name and "Mesh" in directory:
                            Mesh(self, context, name, file, basename, MatTexNames, MatTexFiles)
                        if ".mesh" in name and "Trans" in directory:
                            Trans(basename, context, name, file)            
                        if "TransAnim" in directory:
                            TransAnim(context, file)
                # RB2 Prototype + Lego wii
                elif context.scene.games == 'OPTION_D':
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
                            Tex(context, basename, self, name, file)
                        if ".mesh" in name and "Mesh" in directory:
                            Mesh(self, context, name, file, basename, MatTexNames, MatTexFiles)
                        if ".mesh" in name and "Trans" in directory:
                            Trans(basename, context, name, file)            
                        if "TransAnim" in directory:
                            TransAnim(context, file)
                # RB2-GDRB
                elif context.scene.games == 'OPTION_C' or 'OPTION_E' or 'OPTION_F' or 'OPTION_G':
                    DirType = b_numstring(f)
                    DirName = b_numstring(f)
                    dirs.append(DirType)
                    filenames.append(DirName)
                    f.seek(8, 1)
                    EntryCount = b_int(f)
                    for x in range(EntryCount):
                        dirs.append(b_numstring(f))
                        filenames.append(b_numstring(f))
                    if self.venue_setting:
                        f.seek(0)
                        rest_file = f.read()
                        sequence = "_geom.milo".encode('utf-8')
                        offset = rest_file.find(sequence)
                        f.seek(offset)
                        f.seek(10, 1)
                        f.seek(4, 1)
                        geomdirs = []
                        geomnames = []
                        DirType = b_numstring(f)
                        DirName = b_numstring(f)
                        geomdirs.append(DirType)
                        geomnames.append(DirName)
                        f.seek(8, 1)
                        EntryCount = b_int(f)
                        for x in range(EntryCount):
                            geomdirs.append(b_numstring(f))
                            geomnames.append(b_numstring(f))
                        rest = f.read()
                        files = rest.split(b'\xAD\xDE\xAD\xDE')
                        files = files[:len(geomnames)]
                        for directory, name, file in zip(geomdirs, geomnames, files):
                            if ".mat" in name and "Mat" in directory:
                                MatTexNames.append(name)
                                MatTexFiles.append(file)
                            if "Tex" in directory:
                                if not "TexBlend" in directory:
                                    Tex(context, basename, self, name, file)
                                    MatTexNames.append(name)
                                    MatTexFiles.append(file)
                                Tex(context, basename, self, name, file)
                            if ".mesh" in name and "Mesh" in directory:
                                Mesh(self, context, name, file, basename, MatTexNames, MatTexFiles)                            
                        if "TransAnim" in directory:
                            TransAnim(context, file)
                        elif "PropAnim" in directory:
                            PropAnim(context, file)
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
                            Tex(context, basename, self, name, file)
                        if ".mesh" in name and "Mesh" in directory:
                            Mesh(self, context, name, file, basename, MatTexNames, MatTexFiles)
                        if ".mesh" in name and "Trans" in directory:
                            Trans(basename, context, name, file)
                        if "TransAnim" in directory:
                            TransAnim(context, file)
                        elif "PropAnim" in directory:
                            PropAnim(context, file)
                        elif "CharClipSamples" in directory:
                            CharClipSamples(self, file)
                # RB3-DC2
                elif context.scene.games == 'OPTION_H':
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
                            Mesh(self, context, name, file, basename, MatTexNames, MatTexFiles)
                        if ".mesh" in name and "Trans" in directory:
                            Trans(basename, context, name, file)
                        if "TransAnim" in directory:
                            TransAnim(context, file)

        return {'FINISHED'}                

def Tex(context, basename, self, filename, file):
    try:
        directory = os.path.dirname(self.filepath)
        f = io.BytesIO(file)
        if context.scene.games == 'OPTION_B' and basename.endswith('.milo_xbox'):
            f.seek(17)
            # Extract width and height
            Width = l_int(f)
            Height = l_int(f)
            f.seek(4, 1)
            # Grab texture name
            TextureName = l_numstring(f)
            f.seek(11, 1)
            Encoding = l_int(f)
            # Grab mipmap count
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
            BitmapOffset = f.tell()
            Bitmap = f.read()
            f.seek(BitmapOffset)
            Pixels = []
            for x in range(len(Bitmap)):
                Pixel1 = f.read(1)
                Pixel2 = f.read(1)
                Pixels.append((Pixel2, Pixel1))
            file_path = os.path.join(directory, filename[:-4] + ".dds")

            # Export texture out
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
        if context.scene.games == 'OPTION_C' or 'OPTION_E':
            f.seek(17)
            # Extract width and height
            Width = b_int(f)
            Height = b_int(f)                
            # Grab texture name
            # Lego developers were on something...
            f.seek(4, 1)
            TextureName = b_numstring(f)
            f.seek(11, 1)
            Encoding = b_int(f)
            # Grab mipmap count
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
        if context.scene.games == 'OPTION_D':
            f.seek(17)
            # Extract width and height
            Width = l_int(f)
            Height = l_int(f)                
            # Grab texture name
            # Lego developers were on something...
            f.seek(4, 1)
            TextureName = l_numstring(f)
            f.seek(11, 1)
            Encoding = l_int(f)
            # Grab mipmap count
            MipMapCount = struct.unpack('B', f.read(1))
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
            Bitmap = f.read()
            file_path = os.path.join(directory, filename[:-4] + ".tpl")

            # Export texture out
            with open(file_path, 'wb') as output_file:
                output_file.write(b'\x00\x20\xAF\x30')
                output_file.write(struct.pack('>IIIIII', 1, 12, 20, 0, Height, Width))
                output_file.write(struct.pack('>II', 14, 64))
                output_file.write(struct.pack('>IIII', 0, 0, 1, 1))
                output_file.write(struct.pack('>f', 0))
                output_file.write(struct.pack('>BBBB', 0, 0, 0, 0))
                output_file.write(Bitmap)
            
            print("Exported texture:", file_path)
        if context.scene.games == 'OPTION_F':
            f.seek(17)
            # Extract width and height
            Width = b_int(f)
            Height = b_int(f)                
            # Grab texture name
            # Lego developers were on something...
            f.seek(8, 1)
            TextureName = b_numstring(f)
            f.seek(11, 1)
            Encoding = b_int(f)
            # Grab mipmap count
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
        elif context.scene.games == 'OPTION_G':
            f.seek(18)
            # Extract width and height
            Width = b_int(f)
            Height = b_int(f)                
            # Grab texture name
            # Lego developers were on something...
            f.seek(4, 1)
            TextureName = b_numstring(f)
            f.seek(11, 1)
            Encoding = b_int(f)
            # Grab mipmap count
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
        elif context.scene.games == 'OPTION_H':
            f.seek(17)
            # Extract width and height
            Width = b_int(f)
            Height = b_int(f)
            f.seek(4, 1)
            # Grab texture name
            # Lego developers were on something...
            TextureName = b_numstring(f)
            f.seek(12, 1)
            Encoding = b_int(f)
            # Grab mipmap count
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
        
def Mesh(self, context, filename, file, basename, MatTexNames, MatTexFiles):
    f = io.BytesIO(file)                    
    if context.scene.games == 'OPTION_A':
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
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for face in mesh.polygons:
            for loop_index in face.loop_indices:
                vertex_index = mesh.loops[loop_index].vertex_index
                uv = UVs[vertex_index]
                flip = (uv[0], 1 - uv[1])
                uv_layer.data[loop_index].uv = flip
        if len(Normals) != 0:
            mesh.use_auto_smooth = True
            mesh.normals_split_custom_set_from_vertices(Normals)
            mesh.update()
        else:
            mesh.use_auto_smooth = True
            for face in mesh.polygons:
                face.use_smooth = True
            mesh.update()
    elif context.scene.games == 'OPTION_B':
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
        mesh.use_auto_smooth = True
        mesh.normals_split_custom_set_from_vertices(Normals)
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
        if basename.endswith('.milo_xbox'):
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
    elif context.scene.games == 'OPTION_D':
        # RB2 prototype + Lego
        if self.low_lod_setting:
            if "lod01" in filename or "lod02" in filename:
                return
        if self.shadow_setting:
            if "shadow" in filename:
                return
        f.seek(21)
        LocalTFM = struct.unpack('12f', f.read(48))
        WorldTFM = struct.unpack('12f', f.read(48))
        f.seek(4, 1)
        Target = l_numstring(f)
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
        Indices = []
        for i in range(VertCount):
            if context.scene.games == 'OPTION_D':
                x, y, z = struct.unpack('fff', f.read(12))                
                nx, ny, nz = struct.unpack('fff', f.read(12))
                w1, w2, w3, w4 = struct.unpack('ffff', f.read(16))
                u, v = struct.unpack('ff', f.read(8))
                b1, b2, b3, b4 = struct.unpack('HHHH', f.read(8))
                f.seek(16, 1)
                Verts.append((x, y, z))
                Normals.append((nx, ny, nz))
                Weights.append((w1, w2, w3, w4))
                UVs.append((u, v))
                Indices.append((b1, b2, b3, b4))
            elif context.scene.games == 'OPTION_F':
                x, y, z, w = struct.unpack('ffff', f.read(16))                
                nx, ny, nz, nw = struct.unpack('ffff', f.read(16))
                w1, w2, w3, w4 = struct.unpack('ffff', f.read(16))
                u, v = struct.unpack('ff', f.read(8))
                b1, b2, b3, b4 = struct.unpack('HHHH', f.read(8))
                f.seek(16, 1)
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
        GroupSizesCount = l_int(f)
        for x in range(GroupSizesCount):
            f.read(1)
        BoneNames = []
        BoneCount = l_int(f)
        for x in range(BoneCount):
            BoneName = b_numstring(f)
            TFM = struct.unpack('12f', f.read(48))
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
        if len(Normals) != 0:
            mesh.use_auto_smooth = True
            mesh.normals_split_custom_set_from_vertices(Normals)
            mesh.update()
        else:
            mesh.use_auto_smooth = True
            for face in mesh.polygons:
                face.use_smooth = True
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
    elif context.scene.games == 'OPTION_C' or context.scene.games == 'OPTION_F':
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
            for loop_index in face.loop_indices:
                vertex_index = mesh.loops[loop_index].vertex_index
                uv = UVs[vertex_index]
                flip = (uv[0], 1 - uv[1])
                uv_layer.data[loop_index].uv = flip
        mesh.normals_split_custom_set_from_vertices(Normals)
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
                    HasTree = struct.unpack('>B', f.read(1))
                    if HasTree == 1:
                        ChildCount = struct.unpack('>H', f.read(2))[0]
                        ID = b_int(f)
                        for x in range(ChildCount):
                            NodeType = b_int(f)
                            Child = b_numstring(f)
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
                        HasTree = struct.unpack('>B', f.read(1))
                        if HasTree == 1:
                            ChildCount = struct.unpack('>H', f.read(2))[0]
                            ID = b_int(f)
                            for x in range(ChildCount):
                                NodeType = b_int(f)
                                Child = b_numstring(f)
                        f.seek(8, 1)
                        r = b_float(f)
                        g = b_float(f)
                        b = b_float(f)
                        a = b_float(f)
                        mat.diffuse_color = (r, g, b, a)                    
    elif context.scene.games == 'OPTION_E':
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
        f.seek(1, 1)
        if basename.endswith('.milo_ps3'):
            VertSize = b_int(f)
            if VertSize != 36:
                return
            elif VertSize == 36:
                f.seek(4, 1)
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
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for face in mesh.polygons:
            for loop_index in face.loop_indices:
                vertex_index = mesh.loops[loop_index].vertex_index
                uv = UVs[vertex_index]
                flip = (uv[0], 1 - uv[1])
                uv_layer.data[loop_index].uv = flip
        if len(Normals) != 0:
            mesh.use_auto_smooth = True
            mesh.normals_split_custom_set_from_vertices(Normals)
            mesh.update()
        else:
            mesh.use_auto_smooth = True
            for face in mesh.polygons:
                face.use_smooth = True
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
                    HasTree = struct.unpack('>B', f.read(1))
                    if HasTree == 1:
                        ChildCount = struct.unpack('>H', f.read(2))[0]
                        ID = b_int(f)
                        for x in range(ChildCount):
                            NodeType = b_int(f)
                            Child = b_numstring(f)
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
                        HasTree = struct.unpack('>B', f.read(1))
                        if HasTree == 1:
                            ChildCount = struct.unpack('>H', f.read(2))[0]
                            ID = b_int(f)
                            for x in range(ChildCount):
                                NodeType = b_int(f)
                                Child = b_numstring(f)
                        f.seek(8, 1)
                        r = b_float(f)
                        g = b_float(f)
                        b = b_float(f)
                        a = b_float(f)
                        mat.diffuse_color = (r, g, b, a)
    elif context.scene.games == 'OPTION_G':
        if not basename.endswith('.milo_wii'):
            if self.low_lod_setting:
                if "LOD01" in filename or "LOD02" in filename:
                    return
        else:
            if self.low_lod_setting:
                if "LOD02" in filename:
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
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for face in mesh.polygons:
            for loop_index in face.loop_indices:
                vertex_index = mesh.loops[loop_index].vertex_index
                uv = UVs[vertex_index]
                flip = (uv[0], 1 - uv[1])
                uv_layer.data[loop_index].uv = flip
        if len(Normals) != 0:
            mesh.use_auto_smooth = True
            mesh.normals_split_custom_set_from_vertices(Normals)
            mesh.update()
        else:
            mesh.use_auto_smooth = True
            for face in mesh.polygons:
                face.use_smooth = True
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
                    HasTree = struct.unpack('>B', f.read(1))
                    if HasTree == 1:
                        ChildCount = struct.unpack('>H', f.read(2))[0]
                        ID = b_int(f)
                        for x in range(ChildCount):
                            NodeType = b_int(f)
                            Child = b_numstring(f)
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
                        HasTree = struct.unpack('>B', f.read(1))
                        if HasTree == 1:
                            ChildCount = struct.unpack('>H', f.read(2))[0]
                            ID = b_int(f)
                            for x in range(ChildCount):
                                NodeType = b_int(f)
                                Child = b_numstring(f)
                        f.seek(8, 1)
                        r = b_float(f)
                        g = b_float(f)
                        b = b_float(f)
                        a = b_float(f)
                        mat.diffuse_color = (r, g, b, a)
    elif context.scene.games == 'OPTION_H':
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
            f.seek(1, 1)
            VertSize = b_int(f)
            if VertSize == 40:
                f.seek(4, 1)
            else:
                f.seek(-4, 1)
        Verts = []
        Normals = []
        Weights = []
        UVs = []
        Indices = []
        for i in range(VertCount):
            if basename.endswith('.milo_ps3') and VertSize != 40:
                x, y, z = struct.unpack('>fff', f.read(12))
                f.seek(16, 1)
                nx, ny, nz = struct.unpack('>fff', f.read(12))
                u, v = struct.unpack('>ff', f.read(8))
                f.seek(40, 1)
                Verts.append((x, y, z))
                Normals.append((nx, ny, nz))
                UVs.append((u, v))
            if basename.endswith('.milo_xbox') and VertSize != 40:
                x, y, z = struct.unpack('>fff', f.read(12))
                f.seek(16, 1)
                nx, ny, nz = struct.unpack('>fff', f.read(12))
                u, v = struct.unpack('>ff', f.read(8))
                f.seek(36, 1)
                Verts.append((x, y, z))
                Normals.append((nx, ny, nz))
                UVs.append((u, v))                
            if basename.endswith('.milo_wii'):
                nx, ny, nz = struct.unpack('>fff', f.read(12))
                w1, w2, w3, w4 = struct.unpack('>ffff', f.read(16))
                u, v = struct.unpack('>ff', f.read(8))
                b1, b2, b3, b4 = struct.unpack('>HHHH', f.read(8))
                f.seek(16, 1)
            if basename.endswith('.milo_ps3') and VertSize == 40:
                x, y, z = struct.unpack('>fff', f.read(12))
                u, v = struct.unpack('>ee', f.read(4))
                f.seek(24, 1)
                Verts.append((x, y, z))
                UVs.append((u, v))
            if basename.endswith('.milo_xbox') and VertSize == 40:
                x, y, z = struct.unpack('>fff', f.read(12))
                u, v = struct.unpack('>ee', f.read(4))
                f.seek(20, 1)
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
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for face in mesh.polygons:
            for loop_index in face.loop_indices:
                vertex_index = mesh.loops[loop_index].vertex_index
                uv = UVs[vertex_index]
                flip = (uv[0], 1 - uv[1])
                uv_layer.data[loop_index].uv = flip
        if len(Normals) != 0:
            mesh.use_auto_smooth = True
            mesh.normals_split_custom_set_from_vertices(Normals)
            mesh.update()
        else:
            mesh.use_auto_smooth = True
            for face in mesh.polygons:
                face.use_smooth = True
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
                    HasTree = struct.unpack('>B', f.read(1))
                    if HasTree == 1:
                        ChildCount = struct.unpack('>H', f.read(2))[0]
                        ID = b_int(f)
                        for x in range(ChildCount):
                            NodeType = b_int(f)
                            Child = b_numstring(f)
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
                        HasTree = struct.unpack('>B', f.read(1))
                        if HasTree == 1:
                            ChildCount = struct.unpack('>H', f.read(2))[0]
                            ID = b_int(f)
                            for x in range(ChildCount):
                                NodeType = b_int(f)
                                Child = b_numstring(f)
                        f.seek(8, 1)
                        r = b_float(f)
                        g = b_float(f)
                        b = b_float(f)
                        a = b_float(f)
                        mat.diffuse_color = (r, g, b, a)                            
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

def VenueTex(basename, self, file):
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
        f.seek(11, 1)
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
        f.seek(25, 1)
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
            file_path = os.path.join(directory, TexName[:-4] + ".tpl")
        else:
            file_path = os.path.join(directory, TexName[:-4] + ".dds")
        if not basename.endswith('.milo_wii'):
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
                if basename.endswith('.milo_xbox'):
                    for Pixel in Pixels:
                        byte1, byte2 = Pixel
                        output_file.write(byte1)
                        output_file.write(byte2)
                else:
                    output_file.write(Bitmap)
        else:
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

        print("Exported texture:", file_path)

        f.close()
        del f
    except Exception as e:
        print(e)

def VenueMesh(self, file):
    basename = os.path.basename(self.filepath)
    f = io.BytesIO(file)
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
    if self.low_lod_setting:
        if "lod01" in MeshName or "lod02" in MeshName:
            return
    if self.shadow_setting:
        if "shadow" in MeshName:
            return
    f.seek(9, 1)
    VertCount = b_int(f)
    if basename.endswith('.milo_wii'):
        f.seek(1, 1)
    else:
        f.seek(1, 1)
        VertSize = f.read(4)
        f.seek(4, 1)
    Verts = []
    Normals = []
    Weights = []
    UVs = []
    Indices = []
    if basename.endswith('.milo_ps3'):
        if VertSize != b'\x00\x00\x00\x24':
            f.seek(-8, 1)
    for i in range(VertCount):
        if not basename.endswith('.milo_wii'):
            if VertSize != b'\x00\x00\x00\x24':
                x, y, z, w = struct.unpack('>ffff', f.read(16))
                nx, ny, nz, nw = struct.unpack('>ffff', f.read(16))
                w1, w2, w3, w4 = struct.unpack('>ffff', f.read(16))
                u, v = struct.unpack('>ff', f.read(8))
                b1, b2, b3, b4 = struct.unpack('>HHHH', f.read(8))
                f.seek(16, 1)
        else:
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
            if VertSize == b'\x00\x00\x00\x24':
                u, v = struct.unpack('>ee', f.read(4))
                f.seek(20, 1)
        Verts.append((x, y, z))
        if basename.endswith('.milo_wii') or VertSize != b'\x00\x00\x00\x24':
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
    if basename.endswith('.milo_wii') or basename.endswith('.milo_ps3') and len(Weights) != 0:
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
        if "lod" in MeshName:
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
        

def DC3Trans(self, file, BoneNames, BoneFiles):
    for file, name in zip(BoneFiles, BoneNames):        
        f = io.BytesIO(file)
        f.seek(17)
        LocalUpper = struct.unpack('>9f', f.read(36))
        LocalPos = struct.unpack('>3f', f.read(12))
        WorldUpper = struct.unpack('>9f', f.read(36))
        WorldPos = struct.unpack('>3f', f.read(12))
        f.seek(4, 1)
        Target = b_numstring(f)
        f.seek(1, 1)
        Parent = b_numstring(f)
        if "Armature" in bpy.data.armatures:
            armature_data = bpy.data.armatures["Armature"]
        else:
            armature_data = bpy.data.armatures.new("Armature")
        if "Armature" in bpy.data.objects:
            armature_obj = bpy.data.objects["Armature"]
        else:
            armature_obj = bpy.data.objects.new("Armature", armature_data)
        if not armature_obj.name in bpy.context.scene.collection.objects:
            bpy.context.scene.collection.objects.link(armature_obj)
        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode='EDIT')
        edit_bone = armature_obj.data.edit_bones.get(name)
        if edit_bone is None:
            edit_bone = armature_obj.data.edit_bones.new(name)
            edit_bone.head = (0, 0, 0)
            edit_bone.tail = (0, 1, 0)
            edit_bone.use_deform = True
        parent_bone = armature_obj.data.edit_bones.get(Parent)
        if parent_bone is None:
            parent_bone = armature_obj.data.edit_bones.new(Parent)
            parent_bone.head = (0, 0, 0)
            parent_bone.tail = (0, 1, 0)
            parent_bone.use_deform = True
        if parent_bone:
            edit_bone.parent = parent_bone
        bpy.ops.object.mode_set(mode='POSE')
        pose_bone = armature_obj.pose.bones.get(name)
        if pose_bone:
            pose_bone.matrix_basis = mathutils.Matrix((
                (LocalUpper[0], LocalUpper[3], LocalUpper[6], 0.0),
                (LocalUpper[1], LocalUpper[4], LocalUpper[7], 0.0),
                (LocalUpper[2], LocalUpper[5], LocalUpper[8], 0.0),
                (0.0, 0.0, 0.0, 1.0),
            ))
            pose_bone.location = LocalPos  
        bpy.ops.object.mode_set(mode='OBJECT')
        armature_obj.rotation_euler = (0, 0, math.radians(-180))
    
def Trans(basename, context, filename, file):        
    f = io.BytesIO(file)
    if context.scene.games == 'OPTION_A':
        f.seek(8)
        LocalUpper = struct.unpack('9f', f.read(36))
        LocalPos = struct.unpack('3f', f.read(12))
        WorldUpper = struct.unpack('9f', f.read(36))
        WorldPos = struct.unpack('3f', f.read(12))
    if context.scene.games == 'OPTION_B' and basename.endswith('.milo_xbox'):
        f.seek(17)
        LocalUpper = struct.unpack('9f', f.read(36))
        LocalPos = struct.unpack('3f', f.read(12))
        WorldUpper = struct.unpack('9f', f.read(36))
        WorldPos = struct.unpack('3f', f.read(12))
    if context.scene.games == 'OPTION_B' and basename.endswith('.milo_ps2'):
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
    if context.scene.games == 'OPTION_A':
        TransCount = l_int(f)
        for x in range(TransCount):
            TransObject = l_numstring(f)
        f.seek(4, 1)
    if context.scene.games == 'OPTION_B' and basename.endswith('.milo_ps2'):
        f.seek(113)
    else:
        f.seek(117)
    if context.scene.games == 'OPTION_A' or context.scene.games == 'OPTION_B':
        Target = l_numstring(f)
    else:
        Target = b_numstring(f)
    f.seek(1, 1)
    if context.scene.games == 'OPTION_A' or context.scene.games == 'OPTION_B':
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
        
def TransAnim(context, file):
    f = io.BytesIO(file)
    bpy.context.scene.render.fps = 30
    if context.scene.games == 'OPTION_A':
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
    elif context.scene.games == 'OPTION_B':
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
    elif context.scene.games == 'OPTION_E' or 'OPTION_G':
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
        
def PropAnim(context, file):
    f = io.BytesIO(file)
    # Hacky way to guess endian
    if context.scene.games == 'OPTION_E' or 'OPTION_G':
        f.seek(29)
        PropKeysCount = b_int(f)
        f.seek(8, 1)
        Target = b_numstring(f)
        obj = bpy.data.objects.get(Target)
        if obj is None:
            return
        f.seek(1, 1)
        ChildCount = struct.unpack('>H', f.read(2))[0]
        ID = b_int(f)
        for x in range(ChildCount):
            f.seek(4, 1)
            # Value defines if this is position, rotation, scale, etc.
            Value = b_numstring(f)
        f.seek(12, 1)
        EventCount = b_int(f)
        for x in range(EventCount):
            if Value == "position":
                Position = struct.unpack('>fff', f.read(12))
                Pos = b_float(f)
                obj.location = Position
                obj.keyframe_insert("location", frame=Pos)
        
                    
def CharClipSamples(self, file):
    f = io.BytesIO(file)
    f.seek(12)
    AnimType = b_numstring(f)
    f.seek(59, 1)
    BoneCount = b_int(f)
    BoneNames = []
    for x in range(BoneCount):
        BoneName = b_numstring(f)
        BoneNames.append(BoneName)
        Weight = b_float(f)
    for x in range(7):
        Count = b_int(f)
    f.seek(4, 1)
    NumSamples = b_int(f)
    NumFrames = b_int(f)
    Frames = []
    for x in range(NumFrames):
        Frame = b_float(f)
        Frames.append(Frame)
    Armature = bpy.data.objects.get('Armature')
    frame_index = 0
    for x in range(NumSamples):
        for Name in BoneNames:
            if "pos" in Name:
                x, y, z = struct.unpack('>hhh', f.read(6))
                x_float = x / 32767
                y_float = y / 32767
                z_float = z / 32767
                x_float = x_float * 1345
                y_float = y_float * 1345
                z_float = z_float * 1345
                Name = Name.replace('.pos', '.mesh')
                Bone = Armature.pose.bones.get(Name)
                if Bone and frame_index < len(Frames):
                    Bone.location = (x_float, y_float, z_float)
                    Bone.keyframe_insert("location", frame=Frames[frame_index])
                frame_index += 1
            elif "quat" in Name:
                x, y, z, w = struct.unpack('>hhhh', f.read(8))
                x_float = x / 32767
                y_float = y / 32767
                z_float = z / 32767
                w_float = w / 32767
                Name = Name.replace('.quat', '.mesh')
                Bone = Armature.pose.bones.get(Name)
                if Bone and frame_index < len(Frames):
                    Bone.rotation_mode = 'QUATERNION'
                    Bone.rotation_quaternion = (w_float, x_float, -z_float, y_float)
                    Bone.keyframe_insert("rotation_quaternion", frame=Frames[frame_index])
                frame_index += 1
            elif "rotz" in Name:
                rotz = f.read(2)

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

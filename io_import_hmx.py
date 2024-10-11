bl_info = {
    "name": "HMX Importer",
    "description": "A script to import milo/rnd files from most HMX games.",
    "author": "alliwantisyou3471, neotame4",
    "version": (1, 0),
    "blender": (3, 6, 0),
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

def b_bool(f):
    struct.unpack('?', f.read(1))

def l_bool(f):
    struct.unpack('>?', f.read(1))

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
        default="*.milo_ps3;*.milo_xbox;*.milo_wii;*.rnd_ps2;*.milo_ps2;*.rnd;*.dds;*.ccs;*.lit;*.cam",
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

    little_endian_setting: BoolProperty(
        name="Little Endian",
        description="Use little endian",
        default=False,
    )
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.prop(self, "low_lod_setting")
        layout.prop(self, "shadow_setting")
        layout.prop(self, "venue_setting")
        layout.prop(self, "little_endian_setting")
    def execute(self, context):
        with open(self.filepath, 'rb') as f:
            if self.filepath.endswith('.ccs'):
                with open(self.filepath, 'rb') as f:
                    Version = b_int(f)
                    f.seek(12)
                    AnimType = b_numstring(f)
                    if Version == 15:
                        f.seek(46, 1)
                        NodeCount = b_int(f)
                        for x in range(NodeCount):
                            Name = b_numstring(f)
                            FloatCount = b_int(f)
                            for x in range(FloatCount):
                                Frame = b_float(f)
                                Weight = b_float(f)
                        f.seek(8, 1)
                    elif Version == 16:
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
                    print(NumSamples)
                    Armature = bpy.data.objects.get('Armature')
                    for i in range(NumSamples):
                        frame_index = int(i / NumSamples * NumFrames)
                        bpy.context.scene.frame_set(int(Frames[frame_index]))
                        for Name in BoneNames:
                            if "pos" in Name:
                                x, y, z = struct.unpack('>hhh', f.read(6))
                                x_float = x / 32767 * 1345
                                y_float = y / 32767 * 1345
                                z_float = z / 32767 * 1345
                                Name = Name.replace('.pos', '.mesh')
                                Bone = Armature.pose.bones.get(Name)
                                if Bone:
                                    Bone.location = (x_float, -z_float, y_float)
                                    Bone.keyframe_insert("location")
                            elif "quat" in Name:
                                x, y, z, w = struct.unpack('>hhhh', f.read(8))
                                x_float = x / 32767
                                y_float = y / 32767
                                z_float = z / 32767
                                w_float = w / 32767
                                Name = Name.replace('.quat', '.mesh')
                                Bone = Armature.pose.bones.get(Name)
                                if Bone:
                                    Bone.rotation_mode = 'QUATERNION'
                                    Bone.rotation_quaternion = (w_float, x_float, -z_float, y_float)
                                    Bone.keyframe_insert("rotation_quaternion")
                            elif "rotz" in Name:
                                rotz = f.read(2)
                    Armature.location = (-3, 140, 0)
                    Armature.rotation_euler = ((math.radians(-90)), 0, 0)
            elif self.filepath.endswith('.dds'):
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
                for x in range(FileCount):
                    compressed.append(l_int(f))
                f.seek(StartOffset)
                dirs = []
                filenames = []
                MatTexNames = []
                MatTexFiles = []
                if self.little_endian_setting:
                    Version = l_int(f)
                    if Version > 10:
                        DirType = l_numstring(f)
                        DirName = l_numstring(f)
                        dirs.append(DirType)
                        filenames.append(DirName)
                        f.seek(8, 1)
                        EntryCount = l_int(f)
                        for x in range(EntryCount):
                            DirType = l_numstring(f)
                            DirName = l_numstring(f)
                            dirs.append(DirType)
                            filenames.append(DirName)
                    elif Version == 10:
                        EntryCount = l_int(f)
                        for x in range(EntryCount):
                            DirType = l_numstring(f)
                            DirName = l_numstring(f)
                            dirs.append(DirType)
                            filenames.append(DirName)
                        ExtPathCount = l_int(f)
                        for x in range(ExtPathCount):
                            ExtPath = l_numstring(f)
                    rest = f.read()
                    files = rest.split(b'\xAD\xDE\xAD\xDE')
                    for directory, name, file in zip(dirs, filenames, files):                        
                        if ".mat" in name and "Mat" in directory:
                            MatTexNames.append(name)
                            MatTexFiles.append(file)
                        if "Tex" in directory:                                    
                            Tex(basename, self, name, file)
                            MatTexNames.append(name)
                            MatTexFiles.append(file)
                        if ".mesh" in name and "Mesh" in directory:
                            Mesh(self, context, name, file, basename, MatTexNames, MatTexFiles)
                        if ".mesh" in name and "Trans" in directory:
                            Trans(basename, self, name, file)
                        if "TransAnim" in directory:
                            TransAnim(self, name, basename, file)
                        elif "PropAnim" in directory:
                            PropAnim(self, file)
                       # if ".lit" in name and "Light" in directory:
                       #     Light(self, file, name)
                       # elif ".cam" in name and "Cam" in directory:
                       #      Cam(self, file)
                else:
                    Version = b_int(f)
                    DirType = b_numstring(f)
                    DirName = b_numstring(f)
                    dirs.append(DirType)
                    filenames.append(DirName)
                    if Version < 32:
                        f.seek(8, 1)
                    else:
                        f.seek(9, 1)
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
                        geomfiles = []
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
                        for directory, name, file in zip(geomdirs, geomnames, files):
                            if ".mat" in name and "Mat" in directory:
                                MatTexNames.append(name)
                                MatTexFiles.append(file)
                            if "Tex" in directory:                                    
                                Tex(basename, self, name, file)
                                MatTexNames.append(name)
                                MatTexFiles.append(file)
                            if ".mesh" in name and "Mesh" in directory:
                                Mesh(self, context, name, file, basename, MatTexNames, MatTexFiles)                            
                            if ".mesh" in name and "Trans" in directory:
                                Trans(basename, self, name, file)
                            if "TransAnim" in directory:
                                TransAnim(self, name, basename, file)
                            elif "PropAnim" in directory:
                                PropAnim(self, file)
                           # if ".lit" in name and "Light" in directory:
                           #     Light(self, file, name)
                           # elif ".cam" in name and "Cam" in directory:
                           #     Cam(self, file)
                    if Version < 32:
                        rest_file = f.read()
                        files = rest_file.split(b'\xAD\xDE\xAD\xDE')
                        min_length = min(len(dirs), len(filenames))
                        if len(files) > min_length:
                            files = files[:min_length]
                        if dirs and filenames and dirs[0] == "ObjectDir":
                            dirs.pop(0)
                            filenames.pop(0)
                        for directory, name, file in zip(dirs, filenames, files):
                            print(directory, name, file[:4])
                            if ".mat" in name and "Mat" in directory:
                                MatTexNames.append(name)
                                MatTexFiles.append(file)
                            if "Tex" in directory:                                    
                                Tex(basename, self, name, file)
                                MatTexNames.append(name)
                                MatTexFiles.append(file)
                            if ".mesh" in name and "Mesh" in directory:
                                Mesh(self, context, name, file, basename, MatTexNames, MatTexFiles)
                            if ".mesh" in name and "Trans" in directory:
                                Trans(basename, self, name, file)
                            if "bone" in name and "Mesh" in directory:
                                MeshTrans(basename, self, name, file)
                           # if "TransAnim" in directory:
                           #     TransAnim(self, name, basename, file)
                            elif "PropAnim" in directory:
                                PropAnim(self, file)
                           # if ".lit" in name and "Light" in directory:
                           #     Light(self, file, name,)
                           # elif ".cam" in name and "Cam" in directory:
                           #     Cam(self, file)

        return {'FINISHED'}                

def Tex(basename, self, filename, file):
    f = io.BytesIO(file)
    try:
        if self.little_endian_setting:
            Version = l_int(f)
            if Version == 8 or basename.endswith('.milo_ps2'):
                return
            else:
                f.seek(17)
                Width = l_int(f)
                Height = l_int(f)
                f.seek(29)
                TexName = l_numstring(f)
                f.seek(11, 1)
                Encoding = l_int(f)
                MipMapCount = struct.unpack('B', f.read(1))[0]
                f.seek(25, 1)
                BitmapStart = f.tell()
                Bitmap = f.read()
                Pixels = []
                f.seek(BitmapStart)
                for x in range(len(Bitmap)):
                    Pixel1 = f.read(1)
                    Pixel2 = f.read(1)
                    Pixels.append((Pixel1, Pixel2))
                path = os.path.join(os.path.dirname(self.filepath), filename[:-4] + ".dds")
                with open(path, 'wb') as out:
                    out.write(struct.pack('I', 542327876))
                    out.write(struct.pack('I', 124))
                    out.write(struct.pack('I', 528391))
                    out.write(struct.pack('II', Height, Width))
                    out.write(struct.pack('II', 0, 0))
                    out.write(struct.pack('I', MipMapCount))
                    for x in range(11):
                        out.write(struct.pack('I', 0))
                    out.write(struct.pack('I', 32))
                    out.write(struct.pack('I', 4))
                    if Encoding == 8:
                        out.write(struct.pack('I', 827611204))
                    elif Encoding == 24:
                        out.write(struct.pack('I', 894720068))
                    elif Encoding == 32:
                        out.write(struct.pack('I', 843666497))
                    for x in range(5):
                        out.write(struct.pack('I', 0))
                    out.write(struct.pack('I', 4096))
                    for x in range(4):
                        out.write(struct.pack('I', 0))
                    for Pixel in Pixels:
                        pixel1, pixel2 = Pixel
                        out.write(pixel2)
                        out.write(pixel1)
                print("Converted + exported texture:", filename)
        else:
            Version = b_int(f)
            if Version == 10:
                f.seek(17)
            elif Version == 11:
                f.seek(18)
            Width = b_int(f)
            Height = b_int(f)
            if Version == 11:
                BPP = b_int(f)
                if not BPP == 4 or BPP == 8:
                    f.seek(-13, 1)
                    Width = b_int(f)
                    Height = b_int(f)
                    f.seek(4, 1)
            if Version == 10:
                f.seek(29)
            elif Version == 11:
                f.seek(30)
            if Version == 11:
                TexNameStart = f.tell()
                try:
                    TexName = b_numstring(f)
                except:
                    f.seek(TexNameStart)
                    f.seek(-1, 1)
                    TexName = b_numstring(f)
                if len(TexName) == 0:
                    f.seek(-1, 1)
                    TexName = b_numstring(f)
            else:
                TexName = b_numstring(f)
            f.seek(11, 1)
            Encoding = b_int(f)
            if Version == 11:
                if not Encoding == 8 or Encoding == 24 or Encoding == 32:
                    f.seek(-3, 1)
                    Encoding = b_int(f)
            MipMapCount = struct.unpack('>B', f.read(1))[0]
            f.seek(25, 1)
            if basename.endswith('.milo_xbox'):
                BitmapStart = f.tell()
                Bitmap = f.read()
                Pixels = []
                f.seek(BitmapStart)
                for x in range(len(Bitmap)):
                    Pixel1 = f.read(1)
                    Pixel2 = f.read(1)
                    Pixels.append((Pixel1, Pixel2))
            else:
                Bitmap = f.read()
            path = os.path.join(os.path.dirname(self.filepath), filename[:-4] + ".dds")
            with open(path, 'wb') as out:
                out.write(struct.pack('I', 542327876))
                out.write(struct.pack('I', 124))
                out.write(struct.pack('I', 528391))
                out.write(struct.pack('II', Height, Width))
                out.write(struct.pack('II', 0, 0))
                out.write(struct.pack('I', MipMapCount))
                for x in range(11):
                    out.write(struct.pack('I', 0))
                out.write(struct.pack('I', 32))
                out.write(struct.pack('I', 4))
                if Encoding == 8:
                    out.write(struct.pack('I', 827611204))
                elif Encoding == 24:
                    out.write(struct.pack('I', 894720068))
                elif Encoding == 32:
                    out.write(struct.pack('I', 843666497))
                for x in range(5):
                    out.write(struct.pack('I', 0))
                out.write(struct.pack('I', 4096))
                for x in range(4):
                    out.write(struct.pack('I', 0))
                if basename.endswith('.milo_xbox'):
                    for Pixel in Pixels:
                        pixel1, pixel2 = Pixel
                        out.write(pixel2)
                        out.write(pixel1)
                else:
                    out.write(Bitmap)
                print("Converted + exported texture:", filename)            
    except Exception as e:
        print(e)
        
def Mesh(self, context, filename, file, basename, MatTexNames, MatTexFiles):
    f = io.BytesIO(file)
    if self.little_endian_setting:
        Version = l_int(f)
        if Version == 25:
            f.seek(8)
        elif Version == 28 and basename.endswith('.milo_ps2'):
            if self.shadow_setting:
                if "shadow" in filename:
                    return
            f.seek(17)
        else:
            if self.shadow_setting:
                if "shadow" in filename:
                    return
            f.seek(21)
        LocalTFM = struct.unpack('12f', f.read(48))
        WorldTFM = struct.unpack('12f', f.read(48))
        if Version == 25:
            TransCount = l_int(f)
            for x in range(TransCount):
                TransObject = l_numstring(f)
            f.seek(4, 1)
        else:
            f.seek(4, 1)
        Target = l_numstring(f)
        f.seek(1, 1)
        ParentName = l_numstring(f)
        if Version == 25:
            f.seek(5, 1)
            DrawCount = l_int(f)
            for x in range(DrawCount):
                DrawName = l_numstring(f)
            f.seek(16, 1)
        else:
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
            if Version == 34:
                try:
                    x, y, z = struct.unpack('fff', f.read(12))
                    Verts.append((x, y, z))
                    nx, ny, nz = struct.unpack('fff', f.read(12))
                    Normals.append((nx, ny, nz))
                    w1, w2, w3, w4 = struct.unpack('ffff', f.read(16))
                    u, v = struct.unpack('ff', f.read(8))
                    Weights.append((w1, w2, w3, w4))
                    UVs.append((u, v))
                    b1, b2, b3, b4 = struct.unpack('HHHH', f.read(8))
                    Indices.append((b1, b2, b3, b4))
                    f.seek(16, 1)
                except:
                    x, y, z, w = struct.unpack('ffff', f.read(16))
                    Verts.append((x, y, z))
                    nx, ny, nz, nw = struct.unpack('ffff', f.read(16))
                    Normals.append((nx, ny, nz))
                    w1, w2, w3, w4 = struct.unpack('ffff', f.read(16))
                    u, v = struct.unpack('ff', f.read(8))
                    Weights.append((w1, w2, w3, w4))
                    UVs.append((u, v))
                    b1, b2, b3, b4 = struct.unpack('HHHH', f.read(8))
                    Indices.append((b1, b2, b3, b4))
                    f.seek(16, 1)
            else:
                x, y, z = struct.unpack('fff', f.read(12))
                Verts.append((x, y, z))
                nx, ny, nz = struct.unpack('fff', f.read(12))
                Normals.append((nx, ny, nz))
                w1, w2, w3, w4 = struct.unpack('ffff', f.read(16))
                u, v = struct.unpack('ff', f.read(8))
                Weights.append((w1, w2, w3, w4))
                UVs.append((u, v))
                IDs = 0, 1, 2, 3
                Indices.append(IDs)
        FaceCount = l_int(f)
        Faces = []
        for x in range(FaceCount):
            Faces.append(struct.unpack('HHH', f.read(6)))
        GroupSizesCount = l_int(f)
        for x in range(GroupSizesCount):
            f.read(1)
        if Version < 34:
            BoneNames = []
            Int = l_int(f)
            if Int > 0:
                f.seek(-4, 1)
                for x in range(4):
                    BoneNames.append(l_numstring(f))
                if Version == 10:
                    BoneNames = BoneNames[:3] + ['']
        else:
            BoneNames = []
            BoneCount = l_int(f)
            for x in range(BoneCount):
                BoneNames.append(l_numstring(f))
                TFM = struct.unpack('12f', f.read(48))
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
        mesh.normals_split_custom_set_from_vertices(Normals)
        mesh.update()
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        try:
            for i, vertex in enumerate(mesh.vertices):
                group_names = [BoneNames[idx] for idx in Indices[i]]
                group_weights = Weights[i]
                group_names = [name if name else "Group" for name in group_names]                            
                for group_name, weight in zip(group_names, group_weights):
                    if group_name not in obj.vertex_groups:
                        obj.vertex_groups.new(name=group_name)
                    group_index = obj.vertex_groups[group_name].index
                    obj.vertex_groups[group_index].add([vertex.index], weight, 'ADD')
            mesh.update()
            print("Bone weights assigned to:", obj.name, group_index)                
        except IndexError:
            print("Indices don't match up!")
        obj.select_set(False)                                   
        if len(MatName) > 0:
            mat = bpy.data.materials.get(MatName)
            if mat is None:
                mat = bpy.data.materials.new(name=MatName)
            obj = bpy.context.active_object
            if obj:
                if obj.data.materials:
                    obj.data.materials[0] = mat
                else:
                    obj.data.materials.append(mat)    
        if Version == 28 and basename.endswith('.milo_xbox'):
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
                        f.seek(101)
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
                            f.seek(21)
                            r = l_float(f)
                            g = l_float(f)
                            b = l_float(f)
                            a = l_float(f)
                            mat.diffuse_color = (r, g, b, a)
    else:
        print(filename)
        Version = b_int(f)
        if Version == 37 and basename.endswith('.milo_wii') and self.low_lod_setting and self.shadow_setting:
            if "LOD01" in filename:
                return
            if "shadow" in filename:
                return
        else:
            if self.low_lod_setting and self.shadow_setting:
                if Version == 37:
                    if "LOD01" in filename or "LOD02" in filename:
                        return
                else:
                    if "lod01" in filename or "lod02" in filename:
                        return
                if "shadow" in filename:
                    return                    
        f.seek(21)
        LocalTFM = struct.unpack('>12f', f.read(48))
        WorldTFM = struct.unpack('>12f', f.read(48))
        f.seek(4, 1)
        Target = b_numstring(f)
        f.seek(1, 1)
        ParentName = b_numstring(f)
        if Version == 37:
            f.seek(29, 1)
        else:
            f.seek(25, 1)
        MatName = b_numstring(f)
        MeshName = b_numstring(f)
        f.seek(9, 1)
        VertCount = b_int(f)
        if Version > 34:
            Platform = struct.unpack('>B', f.read(1))[0]
            if Platform == 1:
                f.seek(8, 1)
        Verts = []
        Normals = []
        Weights = []
        UVs = []
        Indices = []
        for i in range(VertCount):
#lego rockband
            if Version == 34 and basename.endswith('.milo_xbox'):
                x, y, z, w = struct.unpack('>ffff', f.read(16))
                Verts.append((x, y, z))                
                nx, ny, nz, nw = struct.unpack('>ffff', f.read(16))
                Normals.append((nx, ny, nz))
                w1, w2, w3, w4 = struct.unpack('>ffff', f.read(16))
                Weights.append((w1, w2, w3, w4))
                u, v = struct.unpack('>ff', f.read(8))
                UVs.append((u, v))
                b1, b2, b3, b4 = struct.unpack('>HHHH', f.read(8))
                Indices.append((b1, b2, b3, b4))
                f.seek(16, 1)
            if (Version == 36 or Version == 37) and basename.endswith('.milo_wii'):
                x, y, z = struct.unpack('>fff', f.read(12))
                Verts.append((x, y, z))
                nx, ny, nz = struct.unpack('>fff', f.read(12))
                Normals.append((nx, ny, nz))
                w1, w2, w3, w4 = struct.unpack('>ffff', f.read(16))
                Weights.append((w1, w2, w3, w4))
                u, v = struct.unpack('>ff', f.read(8))
                UVs.append((u, v))
                b1, b2, b3, b4 = struct.unpack('>HHHH', f.read(8))
                Indices.append((b1, b2, b3, b4))
                f.seek(16, 1)
#                           TBRB             GDRB
            elif (Version == 36 or Version == 37) and basename.endswith('.milo_ps3'):
               # print("MILO_PS3 format", "mesh version", Version)
                x, y, z = struct.unpack('>fff', f.read(12))
                Verts.append((x, y, z))
                u, v = struct.unpack('>ee', f.read(4))
                UVs.append((u, v))
               # no normals on ps3
               # nx, ny, nz, nw = struct.unpack('>fff', f.read(12))
               # Normals.append((nx, ny, nz, nw))
               # no normals on ps3
                f.seek(8, 1)
#  / 255
                w11, w22, w33, w44 = struct.unpack('>BBBB', f.read(4))
                w1 = w11 / 255.0
                w2 = w22 / 255.0
                w4 = w33 / 255.0
                w3 = w44 / 255.0
                Weights.append((w1, w2, w3, w4))
               # Weights.append((w1, w2, w3, w4))
                b1, b2, b3, b4 = struct.unpack('>HHHH', f.read(8))
               # b1 = struct.unpack('H', f.read(2))
               # b2 = struct.unpack('H', f.read(2))
               # b3 = struct.unpack('H', f.read(2))
               # b4 = struct.unpack('H', f.read(2))
                Indices.append((b1, b2, b3, b4))
                print("weights", w1, w2, w3, w4, "bone ids", b1, b2, b3, b4)
#                           TBRB             GDRB
            elif (Version == 36 or Version == 37) and basename.endswith('.milo_xbox'):
                x, y, z = struct.unpack('>fff', f.read(12))
                Verts.append((x, y, z))
                f.seek(4, 1)
                u, v = struct.unpack('>ee', f.read(4))
                UVs.append((u, v))
                normalv = b_int(f)
                nx = float(normalv & 1023) / float(1023)
                ny = float((normalv >> 10) & 1023) / float(1023)
                nz = float((normalv >> 20) & 1023) / float(1023)
                nw = float((normalv >> 30) & 3) / float(3)
                Normals.append((nx, ny, nz))
       #         w_bits = (normalv >> 30) & 3
       #         z_bits = (normalv >> 20) & 1023
       #         y_bits = (normalv >> 10) & 1023
       #         x_bits = normalv & 1023
       #         if x_bits > 512:
       #             x_bits = -1 * (~((x_bits - 1) & (1023 >> 1)))
       #         if y_bits > 512:
       #             y_bits = -1 * (~((y_bits - 1) & (1023 >> 1)))
       #         if z_bits > 512:
       #             z_bits = -1 * (~((z_bits - 1) & (1023 >> 1)))
       #         if w_bits > 1:
       #             w_bits = -1 * (~((w_bits - 1) & (3 >> 1)))
                f.seek(4, 1)
                weightv = b_int(f)
                Ww_bits = (weightv >> 30) & 3
                Wz_bits = (weightv >> 20) & 1023
                Wy_bits = (weightv >> 10) & 1023
                Wx_bits = weightv & 1023
                w1 = float(Wx_bits) / float(1023)
                w2 = float(Wy_bits) / float(1023)
                w3 = float(Wz_bits) / float(1023)
                w4 = float(Ww_bits) / float(3)
                Weights.append((w1, w2, w3, w4))
               # Weights = ((w1, w2, w3, w4))
               # Weights.append((w1))
               # Weights.append((w2))
               # Weights.append((w3))
               # Weights.append((w4))
                b1, b2, b3, b4 = struct.unpack('>BBBB', f.read(4))
                Indices.append((b1, b2, b3, b4))
               # print("weightv", weightv, "wzyxbits", Ww_bits, Wz_bits, Wy_bits, Wx_bits, "xyzwweight", wx, wy, wz, ww, "bones", b1, b2, b3, b4, "xyz", x, y, z)
            if Version == 38 and basename.endswith('.milo_ps3'):
                x, y, z = struct.unpack('>fff', f.read(12))
                Verts.append((x, y, z))
                u, v = struct.unpack('>ee', f.read(4))
                UVs.append((u, v))
                f.seek(8, 1)
                w1, w2, w3, w4 = struct.unpack('>BBBB', f.read(4))
                Weights.append((w1 / 255.0, w2 / 255.0, w3 / 255.0, w4 / 255.0))
                f.seek(4, 1)
                b1, b2, b3, b4 = struct.unpack('>HHHH', f.read(8))
                Indices.append((b1, b2, b3, b4))
            elif Version == 38 and basename.endswith('.milo_xbox'):
                x, y, z = struct.unpack('>fff', f.read(12))
                Verts.append((x, y, z))
                u, v = struct.unpack('>ee', f.read(4))
                UVs.append((u, v))
                f.seek(8, 1)
                w1, w2, w3, w4 = struct.unpack('>BBBB', f.read(4))
                Weights.append((w1 / 255.0, w2 / 255.0, w3 / 255.0, w4 / 255.0))
                f.seek(4, 1)
                b1, b2, b3, b4 = struct.unpack('>BBBB', f.read(4))
                Indices.append((b1, b2, b3, b4))            
            elif Version == 38 and VertSize != 40:
                x, y, z = struct.unpack('>fff', f.read(12))
                Verts.append((x, y, z))
                f.seek(16, 1)
                nx, ny, nz = struct.unpack('>fff', f.read(12))
                Normals.append((nx, ny, nz))
                u, v = struct.unpack('>ff', f.read(8))
                UVs.append((u, v))
                w1, w2, w3, w4 = struct.unpack('>ffff', f.read(16))
                Weights.append((w1, w2, w3, w4))
                b1, b2, b3, b4 = struct.unpack('>HHHH', f.read(8))
                Indices.append((b1, b2, b3, b4))
                f.seek(16, 1)
        FaceCount = b_int(f)
        Faces = []
        for x in range(FaceCount):
            Faces.append(struct.unpack('>HHH', f.read(6)))
        GroupSizesCount = b_int(f)
        for x in range(GroupSizesCount):
            f.read(1)
        BoneNames = []
        BoneCount = b_int(f)
        for x in range(BoneCount):
            BoneNames.append(b_numstring(f))
            TFM = struct.unpack('>12f', f.read(48))
# not basename.endswith('.milo_wii')
        if (Version == 36 or Version == 37) and basename.endswith('.milo_xbox'):
            index = 0
            for Normal in Normals:
                w_bits = (normalv >> 30) & 3
                z_bits = (normalv >> 20) & 1023
                y_bits = (normalv >> 10) & 1023
                x_bits = normalv & 1023
                if x_bits > 512:
                    x_bits = -1 * (~((x_bits - 1) & (1023 >> 1)))
                if y_bits > 512:
                    y_bits = -1 * (~((y_bits - 1) & (1023 >> 1)))
                if z_bits > 512:
                    z_bits = -1 * (~((z_bits - 1) & (1023 >> 1)))
                if w_bits > 1:
                    w_bits = -1 * (~((w_bits - 1) & (3 >> 1)))
                x = max(x_bits / float(512), -1.0)
                y = max(y_bits / float(512), -1.0)
                z = max(z_bits / float(512), -1.0)
                w = max(w_bits / float(1), -1.0)
                Normals[index] = (x, y, z)
                index += 1
       # if (Version == 36 or Version == 37) and not basename.endswith('.milo_wii'):
       #     index = 0
       #     for Weight in Weights:
       #         w_bits = (weightv >> 30) & 3
       #         z_bits = (weightv >> 20) & 1023
       #         y_bits = (weightv >> 10) & 1023
       #         x_bits = weightv & 1023
       #         w1 = float((weightv & 1023) / float(1023))
       #         w2 = float((weightv >> 10) & 1023) / float(1023)
       #         w3 = float((weightv >> 20) & 1023) / float(1023)
       #         w4 = float((weightv >> 30) & 3) / float(3)
       #         Weights[index] = (w1, w2, w3, w4)
       #         index += 1
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
            if len(Normals) == 0:
                face.use_smooth = True
            for loop_index in face.loop_indices:
                vertex_index = mesh.loops[loop_index].vertex_index
                uv = UVs[vertex_index]
                flip = (uv[0], 1 - uv[1])
                uv_layer.data[loop_index].uv = flip
        if len(Normals) > 0:
            mesh.normals_split_custom_set_from_vertices(Normals)
        mesh.update()
        try:
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            for i, vertex in enumerate(mesh.vertices):
                group_name1, group_name2, group_name3, group_name4 = group_names = [BoneNames[idx] for idx in Indices[i]]
               # print("bone names", BoneNames, "length", len(BoneNames))
                w1, w2, w3, w4 = Weights[i]
               # Weights[i] = w1, w2, w3, w4
               # w1, w2, w3, w4 =  w1, w2, w3, w4
           # if len(BoneNames) == 1 
           # just do one of these
                for group_name in (group_names):
                   # print("weight encoding")
                    if group_name1 not in obj.vertex_groups:
                        obj.vertex_groups.new(name=group_name1)
                    group_index = obj.vertex_groups[group_name1].index
                    obj.vertex_groups[group_name1].add([vertex.index], w4, 'ADD')
                   # print("name", group_name1, "weight4", w4)

                    if group_name2 not in obj.vertex_groups:
                        obj.vertex_groups.new(name=group_name2)
                    group_index = obj.vertex_groups[group_name2].index
                    obj.vertex_groups[group_name2].add([vertex.index], w3, 'ADD')
                   # print("name", group_name2, "weight3", w3)

                    if group_name3 not in obj.vertex_groups:
                        obj.vertex_groups.new(name=group_name3)
                    group_index = obj.vertex_groups[group_name3].index
                    obj.vertex_groups[group_name3].add([vertex.index], w2, 'ADD')
                   # print("name", group_name3, "weight2", w2)

                    if group_name4 not in obj.vertex_groups:
                        obj.vertex_groups.new(name=group_name4)
                    group_index = obj.vertex_groups[group_name4].index
                    obj.vertex_groups[group_name4].add([vertex.index], w1, 'ADD')
                   # print("name", group_name4, "weight1", w1)


                   # print("group_names1", group_names[1], "group_names2", group_names[2],"group_name", group_name, "vertex.index", vertex.index, "4321weight", w4, w3, w2, w1)
                   # print("groups", group_name1, group_name2, group_name3, group_name4, "vertex", vertex.index, "weightv", weightv, "wzyxbits", Wx_bits, Wy_bits, Wz_bits, Ww_bits, "1234weight", w1, w2, w3, w4, "xyz", x, y, z)
#  "bone", b1, b2, b3, b4,
                   # print("vertex", vertex.index, "weightv", weightv, "xbits", Wx_bits, "1weight", w1, "bone", b1, b2, b3, b4, "xyz", x, y, z)

            mesh.update()
            print("Bone weights assigned to:", obj.name, group_index)                
            obj.select_set(False)
        except:
            print("Indices don't match up!")
            print("BoneName length", BoneNames, len(BoneNames))

        if len(MatName) > 0:
            bpy.context.view_layer.objects.active = obj
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
                        Version = b_int(f)
                        if Version == 28:
                            f.seek(21)
                            r = b_float(f)
                            g = b_float(f)
                            b = b_float(f)
                            a = b_float(f)
                            mat.diffuse_color = (r, g, b, a)
                           # f.seek(101)
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
                 # version size + metadata size + blend size = file seek number/9+10=21
                           # blend = b_float(f)
   # 4h/ 00 00 00 00/01/02/03/04/05/06
   # kBlendDest,             00
   # kBlendSrc,              01
   # kBlendAdd,              02
   # kBlendSrcAlpha,         03
   # kBlendSubtract,         04
   # kBlendMultiply,         05
   # kPreMultAlpha,          06
                            f.seek(21)
                            r = b_float(f)
                            g = b_float(f)
                            b = b_float(f)
                            a = b_float(f)
                            mat.diffuse_color = (r, g, b, a)
                            print("diff rgb", r, g, b)
                            alpha = b_float(f)
                            prelit = b_bool(f)
                            use_environ = b_bool(f)
                            z_mode = b_float(f)
   # 4h/ 00 00 00 00/01/02/03/04
   # kZModeDisable,         00
   # kZModeNormal,          01
   # kZModeTransparent,     02
   # kZModeForce,           03
   # kZModeDecal,           04
                            alpha_cut = b_bool(f)
                            alpha_threshold = l_int(f)
                            alpha_write = b_bool(f)
                            tex_gen = b_float(f)
   # 4h/ 00 00 00 00/01/02/03/04/05
   # kTexGenNone,           00
   # kTexGenXfm,            01
   # kTexGenSphere,         02
   # kTexGenProjected,      03
   # kTexGenXfmOrigin,      04
   # kTexGenEnviron,        05
                            tex_wrap = b_float(f)
   # 4h/ 00 00 00 00/01/02/03/04
   # kTexWrapClamp,         00
   # kTexWrapRepeat,        01
   # kTexBorderBlack,       02
   # kTexBorderWhite,       03
   # kTexWrapMirror,        04
                           # tex_xfm = 30h MATRIX
                         # skip tex xfm. WE DONT NEED IT
                            f.seek(30)
                            f.seek(105)
                     # DIFFUSE TEXTURE
                            TexName = b_numstring(f)
                            tex = bpy.data.textures.get(TexName)
                            print("material", MatName, "DIFF TEX name", TexName)
                            if tex:
                                if not mat.use_nodes:
                                    mat.use_nodes = True
                                bsdf = mat.node_tree.nodes.get("Principled BSDF")
                                if bsdf:
                                    tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
                                    tex_node.image = tex.image
                                    links = mat.node_tree.links
                                    links.new(bsdf.inputs['Base Color'], tex_node.outputs['Color'])
                                                      # BSDF input#1
                                    links.new(bsdf.inputs['Alpha'], tex_node.outputs['Alpha'])
                                                      # BSDF input#4
                            next_pass = b_numstring(f)
                            intensify = b_bool(f)
                            cull = b_bool(f)
                            emissive_multiplier = b_float(f)
                           # f.seek(10, 1)
                           # specular rgb
                            r = b_float(f)
                            g = b_float(f)
                            b = b_float(f)
                            mat.specular_color = (r, g, b)
                            print("spec rgb", r, g, b)
                            specular_power = b_float(f)
                          # most milos have this set to tex.tex
                            normal_map = b_numstring(f)
                       # emissive_map
                       # BSDF input #26 on blender 4
                            EMTexName = b_numstring(f)
                            tex = bpy.data.textures.get(EMTexName)
                            print("EMISSIVE TEX name", EMTexName)
                            if tex:
                                if not mat.use_nodes:
                                    mat.use_nodes = True
                                bsdf = mat.node_tree.nodes.get("Principled BSDF")
                                if bsdf:
                                    tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
                                    tex_node.image = tex.image
                                    links = mat.node_tree.links
                                    links.new(bsdf.inputs['Emission'], tex_node.outputs['Color'])
                       # specular_map
                       # BSDF input #13 on blender 4
                       # BSDF Specular on blender 3
                           # f.seek(167)
                            SPECTexName = b_numstring(f)
                            tex = bpy.data.textures.get(SPECTexName)
                            print("SPEC TEX name", SPECTexName)
                            if tex:
                                if not mat.use_nodes:
                                    mat.use_nodes = True
                                bsdf = mat.node_tree.nodes.get("Principled BSDF")
                                if bsdf:
                                    tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
                                    tex_node.image = tex.image
                                    links = mat.node_tree.links                   
                                    links.new(bsdf.inputs['Specular'], tex_node.outputs['Color'])
                                    # BSDF input#13 on blender 4/specular on blender 3
                            environ_map = b_numstring(f)
                           # reflection map??? just reuse the tex code from above^^^
                            per_pixel_light = b_bool(f)
                            stencil_mode = b_float(f)
   # 4h/ 00 00 00 00/01/02
   # kStencilIgnore,        00
   # kStencilWrite,         01
   # kStencilTest,          02
                            fur = b_numstring(f)
                            de_normal = b_float(f)
                            anisotropy = b_float(f)
                            norm_detail_tiling = b_float(f)
                            norm_detail_strength = b_float(f)
                       # norm_detail_map
                       # BSDF input #5 on blender 4
                            NTexName = b_numstring(f)
                            tex = bpy.data.textures.get(NTexName)
                            print("NORM TEX name", NTexName, "normal detail strength", norm_detail_strength)
                            if tex:
                                if not mat.use_nodes:
                                    mat.use_nodes = True
                                bsdf = mat.node_tree.nodes.get("Principled BSDF")
                                if bsdf:
                                    tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
                                    NORM_node = mat.node_tree.nodes.new('ShaderNodeNormalMap')
                                    tex_node.image = tex.image
                                    links = mat.node_tree.links
                                   # TODO: make the strength value be 'norm_detail_strength'
                                    links.new(NORM_node.inputs[1], tex_node.outputs['Color'])
                                    links.new(bsdf.inputs['Normal'], NORM_node.outputs['Normal'])
                                                      # BSDF input#5 on blender 4/normal on blender 3&4

                            point_lights = b_bool(f)
                            proj_lights = b_bool(f)
                            fog = b_bool(f)
                            fade_out = b_bool(f)
                            color_adjust = b_bool(f)
             #               rim_rgb
                          #  r = b_float(f)
                          #  g = b_float(f)
                          #  b = b_float(f)
                          #  mat.rim_color = (r, g, b)
                          #  rim_power = b_float(f)
                          #  rim_map = b_numstring(f)
             # rim???? outer glow/outline glow??? just reuse the tex code from above^^^
             # if we can even do that
                          #  rim_always_show = b_bool(f)
                          #  screen_aligned = b_bool(f)
                          #  shader_varition = b_float(f)
   # 4h/ 00 00 00 00/01/02
   # kShaderVariationNone,  00
   # kShaderVariationSkin,  01
   # kShaderVariationHair,  02
             #               specular2_rgb
                          #  r = b_float(f)
                          #  g = b_float(f)
                          #  b = b_float(f)
                          #  mat.specular2_color = (r, g, b)
                          #  val_0x160 = b_float(f)
                          #  val_0x170 = b_float(f)
                          #  val_0x174 = b_float(f)
                          #  val_0x178 = b_float(f)
                          #  val_0x17c = b_float(f)
             #               five weird varibles
                          #  alpha_mask = b_numstring(f)
                          #  ps3_force_trilinear = b_bool(f)
             #  weird this is in xbox milos^
                            
def Trans(basename, self, filename, file):        
    f = io.BytesIO(file)
    if self.little_endian_setting:
        Version = l_int(f)
        if Version == 8:
            f.seek(8)
            LocalUpper = struct.unpack('9f', f.read(36))
            LocalPos = struct.unpack('3f', f.read(12))
            WorldUpper = struct.unpack('9f', f.read(36))
            WorldPos = struct.unpack('3f', f.read(12))
        elif Version == 9 and basename.endswith('.milo_xbox'):
            f.seek(17)
            LocalUpper = struct.unpack('9f', f.read(36))
            LocalPos = struct.unpack('3f', f.read(12))
            WorldUpper = struct.unpack('9f', f.read(36))
            WorldPos = struct.unpack('3f', f.read(12))
        elif Version == 9 and basename.endswith('.milo_ps2'):
            f.seek(17)
            LocalUpper = struct.unpack('9f', f.read(36))
            LocalPos = struct.unpack('3f', f.read(12))
            WorldUpper = struct.unpack('9f', f.read(36))
            WorldPos = struct.unpack('3f', f.read(12))
        if Version == 8:
            TransCount = l_int(f)
            for x in range(TransCount):
                TransObject = l_numstring(f)
            f.seek(4, 1)
        if Version == 9 and basename.endswith('.milo_ps2'):
            f.seek(113)
        else:
            f.seek(117)
        Target = l_numstring(f)
        f.seek(1, 1)
        ParentName = l_numstring(f)
    else:
        f.seek(17)
        LocalUpper = struct.unpack('>9f', f.read(36))
        LocalPos = struct.unpack('>3f', f.read(12))
        WorldUpper = struct.unpack('>9f', f.read(36))
        WorldPos = struct.unpack('>3f', f.read(12))
        f.seek(117)
        Target = b_numstring(f)
        f.seek(1, 1)
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
        bpy.ops.mesh.primitive_ico_sphere_add()
        bpy.ops.mesh.primitive_cube_add()
        bpy.ops.object.empty_add(type='PLAIN_AXES')



# make skeleton have file name instead
# useful for GDRB
#    if Basename in bpy.data.armatures:
#        armature_data = bpy.data.armatures[Basename]
#    else:
#        armature_data = bpy.data.armatures.new(Basename)
#    if Armature in bpy.data.objects:
#        armature_obj = bpy.data.objects[Basename]
#    else:
#        armature_obj = bpy.data.objects.new(Basename, armature_data)
#        bpy.context.scene.collection.objects.link(armature_obj)
#

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
       # if "hair" in filename:
       #     bpy.ops.object.mode_set(mode='POSE')
       #     pose_bone.matrix = mathutils.Matrix((
       #         (WorldUpper[0], WorldUpper[3], WorldUpper[6], 0.0),
       #         (WorldUpper[1], WorldUpper[4], WorldUpper[7], 0.0),
       #         (WorldUpper[2], WorldUpper[5], WorldUpper[8], 0.0),
       #         (0.0, 0.0, 0.0, 1.0),
       #     ))
       #     pose_bone.location = LocalPos
       # if "hair" in ParentName:
       #     bpy.ops.object.mode_set(mode='POSE')
       #     pose_bone.matrix = mathutils.Matrix((
       #         (WorldUpper[0], WorldUpper[3], WorldUpper[6], 0.0),
       #         (WorldUpper[1], WorldUpper[4], WorldUpper[7], 0.0),
       #         (WorldUpper[2], WorldUpper[5], WorldUpper[8], 0.0),
       #         (0.0, 0.0, 0.0, 1.0),
       #     ))
       #     pose_bone.location = LocalPos
      #  if "spine" in filename:
      #      bpy.ops.object.mode_set(mode='POSE')
      #      pose_bone.matrix_basis = mathutils.Matrix((
      #          (WorldUpper[0], WorldUpper[3], WorldUpper[6], 0.0),
      #          (WorldUpper[1], WorldUpper[4], WorldUpper[7], 0.0),
      #          (WorldUpper[2], WorldUpper[5], WorldUpper[8], 0.0),
      #          (0.0, 0.0, 0.0, 1.0),
      #      ))
      #      pose_bone.location = LocalPos
      #  else:
#^^^^^^^^^OLD PROBABLY UNNEEDED CODE^^^^^^^^^^^
        pose_bone.matrix_basis = mathutils.Matrix((
            (LocalUpper[0], LocalUpper[3], LocalUpper[6], 0.0),
            (LocalUpper[1], LocalUpper[4], LocalUpper[7], 0.0),
            (LocalUpper[2], LocalUpper[5], LocalUpper[8], 0.0),
            (0.0, 0.0, 0.0, 1.0),
        ))
        pose_bone.location = LocalPos
# BONE SHAPES
# BONE SHAPES
# BONE SHAPES
# BONE SHAPES
# BONE SHAPES
# BONE SHAPES
# the three or four eye bones
        if (filename == "bone_L-eye.mesh" or filename == "bone_R-eye.mesh"):
            print("eye bone. No bone shape wanted")
        elif (filename == "bone_L-eye_back.mesh" or filename == "bone_R-eye_back.mesh"):
            print("eye bone. No bone shape wanted")
        elif (filename == "bone_L-lid.mesh" or filename == "bone_R-lid.mesh"):
            print("eyelid bone. No bone shape wanted")
        elif (filename == "bone_L-eyelid-low.mesh" or filename == "bone_R-eyelid-low.mesh"):
            print("eyelid bone. No bone shape wanted")

        elif "spot" in filename:
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Cube']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 0.1
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 0.25
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 0.1

        elif (filename == "bone_head_lookat.mesh"):
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Cube']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 0.4
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 0.1
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 0.1
        elif (filename == "bone_eyes.mesh"):
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Icosphere']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 0.3
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 0.3
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 0.3

        elif (filename == "bone_guitar.mesh"):
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Cube']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 0.5
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 0.5
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 0.5

        elif (filename == "bone_jaw.mesh"):
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Cube']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 0.25
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 0.1
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 0.1

# microphone bones

        elif (filename == "bone_mic.mesh"):
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Cube']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 0.25
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 0.5
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 0.5
        elif (filename == "bone_mic_stand_top.mesh"):
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Cube']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 0.5
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 0.25
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 0.5
        elif (filename == "bone_mic_stand_bottom.mesh"):
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Cube']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 1.0
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 1.0
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 0.25

# the three head bones
        elif (filename == "bone_head.mesh"):
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Cube']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 0.05
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 0.2
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 0.2
        elif (filename == "bone_head_nod.mesh"):
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Cube']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 0.2
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 0.05
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 0.2
        elif (filename == "bone_headscale.mesh"):
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Cube']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 0.2
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 0.2
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 0.05

# the two neck bones
        elif (filename == "bone_neck.mesh"):
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Cube']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 0.5
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 0.5
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 0.5
        elif (filename == "bone_neckTwist.mesh"):
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Cube']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 0.8
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 0.25
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 0.25

# reference point bones
# these bone shouldn't have any weights *ASSUMING* use by the mic lean system to figure out where the mouth is
        elif (filename == "bone_nose.mesh" or filename == "bone_forehead.mesh" or filename == "bone_chin.mesh"):
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Empty']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 1.0
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 1.0
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 1.0

# arm twist bones
        elif (filename == "bone_L-upperTwist1.mesh" or filename == "bone_R-upperTwist1.mesh"):
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Empty']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 1.0
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 1.0
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 1.0
        elif (filename == "bone_L-upperTwist2.mesh" or filename == "bone_R-upperTwist2.mesh"):
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Empty']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 1.0
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 1.0
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 1.0

        elif (filename == "bone_L-foreTwist1.mesh" or filename == "bone_R-foreTwist1.mesh"):
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Empty']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 1.0
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 1.0
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 1.0
        elif (filename == "bone_L-foreTwist2.mesh" or filename == "bone_R-foreTwist2.mesh"):
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Empty']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 1.0
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 1.0
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 1.0



        else:
            bpy.data.objects['Armature'].pose.bones[filename].custom_shape = bpy.data.objects['Icosphere']
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[0] = 0.25
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[1] = 0.25
            bpy.data.objects["Armature"].pose.bones[filename].custom_shape_scale_xyz[2] = 0.25

    bpy.ops.object.mode_set(mode='OBJECT')

def MeshTrans(basename, self, filename, file):        
    f = io.BytesIO(file)
    f.seek(21)
    LocalUpper = struct.unpack('>9f', f.read(36))
    LocalPos = struct.unpack('>3f', f.read(12))
    WorldUpper = struct.unpack('>9f', f.read(36))
    WorldPos = struct.unpack('>3f', f.read(12))
    f.seek(117)
    Target = b_numstring(f)
    f.seek(1, 1)
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
            (WorldUpper[0], WorldUpper[3], WorldUpper[6], 0.0),
            (WorldUpper[1], WorldUpper[4], WorldUpper[7], 0.0),
            (WorldUpper[2], WorldUpper[5], WorldUpper[8], 0.0),
            (0.0, 0.0, 0.0, 1.0),
        ))
        pose_bone.location = WorldPos  
    bpy.ops.object.mode_set(mode='OBJECT')
    
def TransAnim(self, filename, basename, file):
    print(filename)
    f = io.BytesIO(file)
    bpy.context.scene.render.fps = 30
    if self.little_endian_setting:
        Version = l_int(f)
        if Version == 4:
            f.seek(8)
            AnimEntryCount = l_int(f)
            for x in range(AnimEntryCount):
                Name = l_numstring(f)
                F1 = l_float(f)
                F2 = l_float(f)
            AnimCount = l_int(f)
            for x in range(AnimCount):
                AnimObject = l_numstring(f)
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
        elif Version == 6 and basename.endswith('.milo_xbox'):
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
        elif Version == 6 and basename.endswith('.milo_ps2'):
            f.seek(25)
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
    else:
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
        
def PropAnim(self, file):
    f = io.BytesIO(file)
    Version = b_int(f)
    if Version == 11:
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
    Version = b_int(f)
    f.seek(12)
    AnimType = b_numstring(f)
    if Version == 15:
        f.seek(46, 1)
        NodeCount = b_int(f)
        for x in range(NodeCount):
            Name = b_numstring(f)
            FloatCount = b_int(f)
            for x in range(FloatCount):
                Frame = b_float(f)
                Weight = b_float(f)
        f.seek(8, 1)
    elif Version == 16:
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
    print(NumSamples)
    Armature = bpy.data.objects.get('Armature')
    for i in range(NumSamples):
        frame_index = int(i / NumSamples * NumFrames)
        bpy.context.scene.frame_set(int(Frames[frame_index]))
        for Name in BoneNames:
            if "pos" in Name:
                x, y, z = struct.unpack('>hhh', f.read(6))
                x_float = x / 32767 * 1345
                y_float = y / 32767 * 1345
                z_float = z / 32767 * 1345
                Name = Name.replace('.pos', '.mesh')
                Bone = Armature.pose.bones.get(Name)
                if Bone:
                    Bone.location = (x_float, -z_float, y_float)
                    Bone.keyframe_insert("location")
            elif "quat" in Name:
                x, y, z, w = struct.unpack('>hhhh', f.read(8))
                x_float = x / 32767
                y_float = y / 32767
                z_float = z / 32767
                w_float = w / 32767
                Name = Name.replace('.quat', '.mesh')
                Bone = Armature.pose.bones.get(Name)
                if Bone:
                    Bone.rotation_mode = 'QUATERNION'
                    Bone.rotation_quaternion = (w_float, x_float, -z_float, y_float)
                    print("frame", frame_index, "bone", Bone, "ROTATION", Bone.rotation_quaternion, "LOCATION", Bone.location)
                    Bone.keyframe_insert("rotation_quaternion")
            elif "rotz" in Name:
                rotz = f.read(2)
    Armature.location = (-3, 140, 0)
    Armature.rotation_euler = ((math.radians(-90)), 0, 0)

#def CharCollide(self, file):
# .coll
# TODO
#figure out how to read the data

#def Group(self, file):
# .grp
# basically just an empty with objects parented to it
#hh_lod00.grp contains lod00 meshes
#hh_lod01.grp contains lod01 meshes
#hh_lod02.grp contains lod02 meshes


#def Light(self, file, name):
#    f = io.BytesIO(file)
    Version = b_int(f)
#  3 (GH1), 6 (GH2), 9 (GH2 360), 14 (TBRB)
#    print("light", Version, "name", name)
#    #f.seek(12)
# light_type_enum / light types in game
#    kLightPoint,
#    kLightDirectional,
#    kLightFakeSpot,
#    kLightFloorSpot,
#    kLightShadowRef

   # LightType = b_numstring(f)
#    if Version == 13:
#        f.seek(58, 1)
#        NodeCount = b_int(f)
       # trans = b_float(f)
#        x, y, z = struct.unpack('>fff', f.read(12))
       # Color = struct.unpack('fff', f.read(6))
#        r = b_float(f)
#        g = b_float(f)
#        b = b_float(f)
# c++ method for the color value from common.bt
# define COLOR ((struct (r float) (g float) (b float)))
#        Intensity = b_float(f)
#        Range = b_float(f)
#        light_type_enum = b_float(f)
#        # should be a 1-5 or 0-4
        #       ^I THINK^
#        falloff_start = b_float(f)
        # bool animate_color_from_preset
#        animate_color_from_preset = struct.unpack('>?', f.read(1))
        # bool animate_position_from_preset
#        animate_position_from_preset = struct.unpack('>?', f.read(1))
#        topradius = b_float(f)
#        botradius = b_float(f)
#        Smoothness = b_float(f)
#        Displacement = b_float(f)
#        texture = b_float(f)
# Projected floor spot texture
      # Intensity = b_float(f)
      # Intensity = b_float(f
#        print("xyz", x, y, z, "RGBcolor", r, g, b, "intensity", Intensity, "range", Range, "light_type_enum", light_type_enum, "falloff", falloff_start,"animate_color_from_preset", animate_color_from_preset, "animate_position_from_preset", animate_position_from_preset, "topradius", topradius, "botradius", botradius, "smoothness", Smoothness, "displacement", Displacement, "texture", texture)
       # f.seek(8, 1)
#        return
#    elif Version == 16:
#        f.seek(59, 1)
# lamp_data = bpy.data.lights.new(name="New Light", type='POINT')
# lamp_object = bpy.data.objects.new(name="New Light", object_data=lamp_data)
# view_layer.active_layer_collection.collection.objects.link(lamp_object)
# lamp_object.location = (5.0, 5.0, 5.0)
# lamp_object.select_set(True)
# view_layer.objects.active = lamp_object

#def Cam(self, file):
#    f = io.BytesIO(file)
#    Version = b_int(f)
# 9 (GH1), 12 (GH2/GH2 360/TBRB)
#    f.seek(12)
#    AnimType = b_numstring(f)
#    if Version == 15:
#        f.seek(46, 1)
#        NodeCount = b_int(f)
#        for x in range(NodeCount):
#            Name = b_numstring(f)
#            FloatCount = b_int(f)
#            for x in range(FloatCount):
#                near_plane = b_float(f)
#                far_plane = b_float(f)
#                Y_fov = b_float(f)
#        f.seek(8, 1)
#    elif Version == 16:
#        f.seek(59, 1)

#def BandCamShot(self, file):
# .shot
# just create an empty for this if it has location data with whatever values it has in the name
# same for EventTrigger/.trig

#def TexBlendController(self, file):
# .texblendctl
# TexBlendController: TexBlendController.texblendctl

#def EventTrigger(self, file):
# .trig

#def TriggerGroup(self, file):
# .tgrp
# greenday rockband only????

#def Spotlight(self, file):
# .spot

#def Environ(self, file):
# .env

#def WorldInstance(self, file):
# .

#def CharInterest(self, file):
# .intr

#def WorldDir(self, file):
# .intr

#def RndDir(self, file):
# .

#def CamAnim(self, file):
# .cnm
# greenday rockband only????

#def Set(self, file):
# .set
# greenday rockband only????

#def LightPreset(self, file):
# .pst
# greenday rockband only????

#def Flare(self, file):
# .flare
# greenday rockband only????

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

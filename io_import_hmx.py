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
        default="*.milo_ps3;*.milo_xbox;*.milo_wii;*.rnd_ps2;*.milo_ps2;*.rnd;*.dds;*.ccs",
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
                            TransAnim(self, file)
                        elif "PropAnim" in directory:
                            PropAnim(self, file)
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
                                TransAnim(self, file)
                            elif "PropAnim" in directory:
                                PropAnim(self, file)
                    if Version < 32:
                        rest_file = f.read()
                        files = rest_file.split(b'\xAD\xDE\xAD\xDE')
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
                                TransAnim(self, file)
                            elif "PropAnim" in directory:
                                PropAnim(self, file)

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
    except:
        print("Invalid texture")
        return
        
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
                    obj.vertex_groups[group_index].add([vertex.index], weight, 'REPLACE')
            mesh.update()
            print("Bone weights assigned to:", obj.name)                
        except IndexError:
            print("Invalid weights")
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
            if (basename.endswith('.milo_ps3') or basename.endswith('.milo_xbox')) and (Version == 34 or (Version == 36 and Platform == 0)):
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
            elif (Version == 36 or Version == 37) and basename.endswith('.milo_ps3'):
                x, y, z = struct.unpack('>fff', f.read(12))
                Verts.append((x, y, z))
                u, v = struct.unpack('>ee', f.read(4))
                UVs.append((u, v))
                normals = b_int(f)
                Normals.append(normals)
                f.seek(4, 1)
                w1, w2, w3, w4 = struct.unpack('>BBBB', f.read(4))
                Weights.append((w1 / 255.0, w2 / 255.0, w3 / 255.0, w4 / 255.0))
                b1, b2, b3, b4 = struct.unpack('>HHHH', f.read(8))
                Indices.append((b1, b2, b3, b4))
            elif (Version == 36 or Version == 37) and basename.endswith('.milo_xbox'):
                x, y, z = struct.unpack('>fff', f.read(12))
                Verts.append((x, y, z))
                f.seek(4, 1)
                u, v = struct.unpack('>ee', f.read(4))
                UVs.append((u, v))
                normals = b_int(f)
                Normals.append(normals)
                f.seek(4, 1)
                weights = b_int(f)
                Weights.append(Weights)
                b1, b2, b3, b4 = struct.unpack('>BBBB', f.read(4))
                Indices.append((b1, b2, b3, b4))
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
        if (Version == 36 or Version == 37) and not basename.endswith('.milo_wii'):
            index = 0
            for Normal in Normals:
                w_bits = (Normal >> 30) & 3
                z_bits = (Normal >> 20) & 1023
                y_bits = (Normal >> 10) & 1023
                x_bits = Normal & 1023
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
        if BoneCount == 1:
            index = 0
            for ID in Indices:
                Indices[index] = (0, 0, 0, 0)
                index += 1
        if BoneCount != 0:
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            for i, vertex in enumerate(mesh.vertices):
                group_names = [BoneNames[idx] for idx in Indices[i]]
                group_weights = Weights[i]                            
                for group_name, weight in zip(group_names, group_weights):
                    if group_name not in obj.vertex_groups:
                        obj.vertex_groups.new(name=group_name)
                    group_index = obj.vertex_groups[group_name].index
                    obj.vertex_groups[group_index].add([vertex.index], weight, 'ADD')
            mesh.update()
            print("Bone weights assigned to:", obj.name)                
            obj.select_set(False)        
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
                        f.seek(21)
                        r = b_float(f)
                        g = b_float(f)
                        b = b_float(f)
                        a = b_float(f)
                        mat.diffuse_color = (r, g, b, a)
                        f.seek(105)
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
        
def TransAnim(self, file):
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
        elif Version == 6:
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
                    Bone.keyframe_insert("rotation_quaternion")
            elif "rotz" in Name:
                rotz = f.read(2)
    Armature.location = (-3, 140, 0)
    Armature.rotation_euler = ((math.radians(-90)), 0, 0)

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

# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import os
import numpy as np
# import math as m

import bgl
import bpy
from bpy.props import (
    FloatProperty, EnumProperty, StringProperty, BoolProperty, IntProperty
)

from sverchok.data_structure import updateNode, node_id
from sverchok.node_tree import SverchCustomTreeNode
from sverchok.ui import nodeview_bgl_viewer_draw_mk2 as nvBGL2
from sverchok.ui import sv_image as svIMG

from sverchok.utils.sv_operator_mixins import (
    SvGenericDirectorySelector, SvGenericCallbackWithParams
)


class SvTextureViewerOperator(bpy.types.Operator, SvGenericCallbackWithParams):
    """ Save the image with passed settings """
    bl_idname = "node.sv_texview_callback"
    bl_label = "Execute a function on the calling node"


class SvTextureViewerDirSelect(bpy.types.Operator, SvGenericDirectorySelector):
    """ Pick the directory to store images in """
    bl_idname = "node.sv_texview_dirselect"
    bl_label = "Pick directory"


size_tex_list = [
    ('XS', 'XS', 'extra small squared tex: 64px', '', 64),
    ('S', 'S', 'small squared tex: 128px', '', 128),
    ('M', 'M', 'medium squared tex: 256px', '', 256),
    ('L', 'L', 'large squared tex: 512px', '', 512),
    ('XL', 'XL', 'extra large squared tex: 1024px', '', 1024)
]

size_tex_dict = {item[0]: item[4] for item in size_tex_list}

bitmap_format_list = [
    ('PNG', '.png', 'save texture in .png format', '', 0),
    ('TARGA', '.tga', 'save texture in .tga format', '', 1),
    ('TARGA_RAW', '.tga (raw)', 'save texture in .tga(raw) format', '', 2),
    ('TIFF', '.tiff', 'save texture in .tiff format', '', 3),
    ('BMP', '.bmp', 'save texture in .tiff format', '', 4),
    ('JPEG', '.jpeg', 'save texture in .jpeg format', '', 5),
    ('JPEG2000', '.jp2', 'save texture in .jpeg (2000) format', '', 6),
    ('OPEN_EXR_MULTILAYER', '.exr (multilayer)', 'save texture in .exr (multilayer) format', '', 7),
    ('OPEN_EXR', '.exr', 'save texture in .exr format', '', 8),
]

format_mapping = {
    'TARGA': 'tga',
    'TARGA_RAW': 'tga',
    'JPEG2000': 'jp2',
    'OPEN_EXR_MULTILAYER': 'exr',
    'OPEN_EXR': 'exr',
}

gl_color_list = [
    ('BW', 'bw', 'grayscale texture', '', 0),
    ('RGB', 'rgb', 'rgb colored texture', '', 1),
    ('RGBA', 'rgba', 'rgba colored texture', '', 2)
]

gl_color_dict = {
    'BW': 6409,  # GL_LUMINANCE
    'RGB': 6407,  # GL_RGB
    'RGBA': 6408  # GL_RGBA
}

factor_buffer_dict = {
    'BW': 1,  # GL_LUMINANCE
    'RGB': 3,  # GL_RGB
    'RGBA': 4  # GL_RGBA
}


def transfer_to_image(pixels, name, width, height, mode):
    # transfer pixels(data) from Node tree to image viewer
    image = bpy.data.images.get(name)
    if not image:
        image = bpy.data.images.new(name, width, height, alpha=False)
        image.pack
    else:
        image.scale(width, height)
    if mode == 'BW':
        svIMG.assign_BW_image(image, pixels)
    elif mode == 'RGB':
        new = svIMG.array_as(pixels, (width * height * 3,))
        svIMG.assign_RGB_image(image, width, height, new)
    else:
        image.pixels[:] = pixels
    image.update_tag()


def init_texture(width, height, texname, texture, clr):
    # function to init the texture
    bgl.glPixelStorei(bgl.GL_UNPACK_ALIGNMENT, 1)

    bgl.glEnable(bgl.GL_TEXTURE_2D)
    bgl.glBindTexture(bgl.GL_TEXTURE_2D, texname)
    bgl.glActiveTexture(bgl.GL_TEXTURE0)

    bgl.glTexParameterf(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_WRAP_S, bgl.GL_CLAMP)
    bgl.glTexParameterf(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_WRAP_T, bgl.GL_CLAMP)
    bgl.glTexParameterf(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MAG_FILTER, bgl.GL_LINEAR)
    bgl.glTexParameterf(bgl.GL_TEXTURE_2D, bgl.GL_TEXTURE_MIN_FILTER, bgl.GL_LINEAR)

    bgl.glTexImage2D(
        bgl.GL_TEXTURE_2D,
        0, clr, width, height,
        0, clr, bgl.GL_FLOAT, texture
    )

def simple_screen(x, y, args):
    # draw a simple scren display for the texture
    border_color = (0.390805, 0.754022, 1.000000, 1.00)

    texture, texname, width, height = args

    def draw_borders(x=0, y=0, w=30, h=10, color=(0.0, 0.0, 0.0, 1.0)):
        # function to draw a border color around the texture
        bgl.glColor4f(*color)
        bgl.glBegin(bgl.GL_LINE_LOOP)

        for coord in [(x, y), (x + w, y), (w + x, y - h), (x, y - h)]:
            bgl.glVertex2f(*coord)

        bgl.glEnd()

    def draw_texture(x=0, y=0, w=30, h=10, texname=texname):
        # function to draw a texture
        bgl.glDisable(bgl.GL_DEPTH_TEST)

        act_tex = bgl.Buffer(bgl.GL_INT, 1)
        bgl.glGetIntegerv(bgl.GL_TEXTURE_2D, act_tex)

        bgl.glEnable(bgl.GL_TEXTURE_2D)
        bgl.glActiveTexture(bgl.GL_TEXTURE0)

        bgl.glTexEnvf(bgl.GL_TEXTURE_ENV,
                      bgl.GL_TEXTURE_ENV_MODE,
                      bgl.GL_REPLACE)

        bgl.glBindTexture(bgl.GL_TEXTURE_2D, texname)

        texco = [(0, 1), (1, 1), (1, 0), (0, 0)]
        verco = [(x, y), (x + w, y), (x + w, y - h), (x, y - h)]

        bgl.glPolygonMode(bgl.GL_FRONT_AND_BACK, bgl.GL_FILL)

        bgl.glBegin(bgl.GL_QUADS)

        for i in range(4):
            bgl.glTexCoord3f(texco[i][0], texco[i][1], 0.0)
            bgl.glVertex2f(verco[i][0], verco[i][1])

        bgl.glEnd()

        # restoring settings
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, act_tex[0])

        bgl.glDisable(bgl.GL_TEXTURE_2D)

    draw_texture(x=x, y=y, w=width, h=height, texname=texname)

    draw_borders(x=x, y=y, w=width, h=height, color=border_color)


class SvTextureViewerNode(bpy.types.Node, SverchCustomTreeNode):
    '''Texture Viewer node'''
    bl_idname = 'SvTextureViewerNode'
    bl_label = 'Texture viewer'
    texture = {}

    n_id = StringProperty(default='')
    to_image_viewer = BoolProperty(
        name='Pass', description='Transfer pixels to image viewer',
        default=False, update=updateNode)

    activate = BoolProperty(
        name='Show', description='Activate texture drawing',
        default=True, update=updateNode)

    selected_mode = EnumProperty(
        items=size_tex_list, description="Offers display sizing",
        default="S", update=updateNode)

    selected_custom_tex = BoolProperty(
        name='Custom tex', description='Activate custom texture drawing',
        default=False, update=updateNode)

    width_custom_tex = IntProperty(
        min=0, max=1024, default=206, name='Width Tex',
        description="set the custom texture size", update=updateNode)

    height_custom_tex = IntProperty(
        min=0, max=1024, default=124, name='Height Tex',
        description="set the custom texture size", update=updateNode)

    bitmap_format = EnumProperty(
        items=bitmap_format_list,
        description="Offers bitmap saving", default="PNG")

    color_mode = EnumProperty(
        items=gl_color_list, description="Offers color options",
        default="BW", update=updateNode)

    color_mode_save = EnumProperty(
        items=gl_color_list, description="Offers color options",
        default="BW", update=updateNode)

    compression_level = IntProperty(
        min=0, max=100, default=0, name='compression',
        description="set compression level", update=updateNode)

    quality_level = IntProperty(
        min=0, max=100, default=0, name='quality',
        description="set quality level", update=updateNode)

    in_float = FloatProperty(
        min=0.0, max=1.0, default=0.0, name='Float Input',
        description='Input for texture', update=updateNode)

    base_dir = StringProperty(default='/tmp/')
    image_name = StringProperty(default='image_name', description='name (minus filetype)')
    texture_name = StringProperty(
        default='texture',
        description='set name (minus filetype) for exporting to image viewer')
    total_size = IntProperty(default=0)

    @property
    def xy_offset(self):
        a = self.location[:]
        b = int(self.width) + 20
        return int(a[0] + b), int(a[1])

    @property
    def custom_size(self):
        sockets = self.inputs["Width"], self.inputs["Height"]
        return [s.sv_get(deepcopy=False)[0][0] for s in sockets]

    @property
    def texture_width_height(self):
        #  get the width and height for the texture
        if self.selected_custom_tex:
            # width, height = self.get_from_c_size()
            width, height = self.custom_size
        else:
            size_tex = size_tex_dict.get(self.selected_mode)
            width, height = size_tex, size_tex
        return width, height

    def reshape_data(self, data):
        self.total_size = self.calculate_total_size()
        if len(data) < self.total_size:
            default_value = 0
            new_data = [default_value for j in range(self.total_size)]
            new_data[:len(data)] = data[:]
            data = new_data
        elif len(data) > self.total_size:
            data = data[:self.total_size]

    def calculate_total_size(self):
        ''' buffer need adequate size multiplying '''
        width, height = self.texture_width_height
        return width * height * factor_buffer_dict.get(self.color_mode)

    def get_buffer(self):
        data = np.array(self.inputs['Float'].sv_get(deepcopy=False)).flatten()
        self.total_size = self.calculate_total_size()
        self.reshape_data(data)
        texture = bgl.Buffer(bgl.GL_FLOAT, self.total_size, data)
        return texture

    def draw_buttons(self, context, layout):
        c = layout.column()
        c.label(text="Set texture display:")
        row = c.row()
        row.prop(self, "selected_mode", expand=True)
        c.prop(self, 'activate')
        c.prop(self, 'to_image_viewer')
        c.label(text='Set color mode')
        row = layout.row(align=True)
        row.prop(self, 'color_mode', expand=True)
        layout.separator()
        c = layout.column()
        row = c.row()
        c.label(text="Set custom texture display")
        row.prop(self, "selected_custom_tex", expand=True)

    def draw_buttons_ext(self, context, layout):
        img_format = self.bitmap_format
        callback_to_self = "node.sv_texview_callback"
        directory_select = "node.sv_texview_dirselect"

        layout.label(text="Save texture as a bitmap")

        layout.separator()
        layout.prop(self, "bitmap_format", text='format')
        layout.separator()
        # row = layout.row()
        # row.prop(self, 'color_mode_save', expand=True)
        # layout.separator()
        if img_format == 'PNG':
            row = layout.row()
            row.prop(self, 'compression_level', text='set compression')
            layout.separator()
        if img_format in {'JPEG', 'JPEG2000'}:
            row = layout.row()
            row.prop(self, 'quality_level', text='set quality')
            layout.separator()
        row = layout.row(align=True)
        leftside = row.split(0.7)
        leftside.prop(self, 'image_name', text='')
        rightside = leftside.split().row(align=True)
        rightside.operator(callback_to_self, text="Save").fn_name = "save_bitmap"
        rightside.operator(directory_select, text="", icon='IMASEL').fn_name = "set_dir"
        transfer = layout.column(align=True)
        transfer.separator()
        transfer.label(text="Transfer to image viewer")
        transfer.prop(self, 'texture_name', text='', icon='EXPORT')

    def draw_label(self):
        if self.selected_custom_tex:
            width, height = self.get_from_c_size()
            label = (self.label or self.name) + ' {0} x {1}'.format(width, height)
        else:
            label = (self.label or self.name) + ' ' + str(size_tex_dict.get(self.selected_mode)) + "^2"
        return label

    def sv_init(self, context):
        self.inputs.new('StringsSocket', "Float").prop_name = 'in_float'
        self.inputs.new('StringsSocket', "Width").prop_name = 'width_custom_tex'
        self.inputs.new('StringsSocket', "Height").prop_name = 'height_custom_tex'

    def delete_texture(self):
        n_id = node_id(self)
        if n_id in self.texture:
            names = bgl.Buffer(bgl.GL_INT, 1, [self.texture[n_id]])
            bgl.glDeleteTextures(1, names)

    def process(self):
        n_id = node_id(self)
        size_tex = 0
        width = 0
        height = 0
        # end early
        nvBGL2.callback_disable(n_id)
        self.delete_texture()

        if self.to_image_viewer:
            mode = self.color_mode
            self.activate = False
            pixels = np.array(self.inputs['Float'].sv_get(deepcopy=False)).flatten()
            width, height = self.texture_width_height

            transfer_to_image(pixels, self.texture_name, width, height, mode)

        if self.activate:
            texture = self.get_buffer()
            width, height = self.texture_width_height
            x, y = self.xy_offset
            gl_color_constant = gl_color_dict.get(self.color_mode)
            name = bgl.Buffer(bgl.GL_INT, 1)
            bgl.glGenTextures(1, name)
            self.texture[n_id] = name[0]
            init_texture(width, height, name[0], texture, gl_color_constant)

            draw_data = {
                'tree_name': self.id_data.name[:],
                'mode': 'custom_function',
                'custom_function': simple_screen,
                'loc': (x, y),
                'args': (texture, self.texture[n_id], width, height)
            }

            nvBGL2.callback_enable(n_id, draw_data)

    def free(self):
        nvBGL2.callback_disable(node_id(self))
        self.delete_texture()

    # reset n_id on copy
    def copy(self, node):
        self.n_id = ''

    def set_dir(self, operator):
        self.base_dir = operator.directory
        print('new base dir:', self.base_dir)
        return {'FINISHED'}

    def set_compression(self):
        pass

    def save_bitmap(self, operator):
        alpha = False

        # if self.image_name was empty it will give a default
        image_name = self.image_name or 'image_name'

        # save a texture in a bitmap image
        # in different formats supported by blender
        buf = self.get_buffer()
        img_format = self.bitmap_format
        col_mod = self.color_mode
        # col_mod_s = self.color_mode_save
        quality = self.quality_level
        compression = self.compression_level
        print('col_mod is: {0}'.format(col_mod))
        # print('col_mod_s is: {0}'.format(col_mod_s))
        print('img_format is: {0}'.format(img_format))
        if img_format in format_mapping:
            extension = '.' + format_mapping.get(img_format, img_format.lower())
        else:
            extension = '.' + img_format.lower()
        image_name = image_name + extension
        width, height = self.texture_width_height
        if image_name in bpy.data.images:
            img = bpy.data.images[image_name]
        else:
            img = bpy.data.images.new(name=image_name, width=width,
                                      height=height, alpha=alpha,
                                      float_buffer=True)
        # img.scale(width, height)
        # print('img size: ', img.size(width, height))
        print('width is: {0}'.format(width))
        print('length img pixels: {0}'.format(len(img.pixels)))
        if col_mod == 'BW':
            print("passing data from buf to pixels BW")
            svIMG.assign_BW_image(img, buf)
        elif col_mod == 'RGB':
            print("passing data from buf to pixels RGB")
            svIMG.assign_RGB_image(img, width, height, buf)
        elif col_mod == 'RGBA':
            print("passing data from buf to pixels RGBA")
            img.pixels[:] = buf
        # get the scene context
        scene = bpy.context.scene
        # set the scene quality to the maximum
        scene.render.image_settings.quality = quality
        if img_format in {'JPEG', 'JPEG2000'}:
            scene.render.image_settings.color_depth = '16'
        else:
            scene.render.image_settings.color_depth = '8'
        # set compression level to no compression(0)
        scene.render.image_settings.compression = compression
        scene.render.image_settings.color_mode = col_mod
        scene.render.image_settings.file_format = img_format
        print('settings done!')
        # get the path for the file and save the image
        desired_path = os.path.join(self.base_dir, self.image_name + extension)
        # saving the image
        img.save_render(desired_path, scene)

        print('Bitmap saved!  path is:', desired_path)


def register():
    bpy.utils.register_class(SvTextureViewerOperator)
    bpy.utils.register_class(SvTextureViewerDirSelect)
    bpy.utils.register_class(SvTextureViewerNode)


def unregister():
    bpy.utils.unregister_class(SvTextureViewerNode)
    bpy.utils.unregister_class(SvTextureViewerDirSelect)
    bpy.utils.unregister_class(SvTextureViewerOperator)

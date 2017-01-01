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

import bpy
from bpy.props import FloatProperty, BoolProperty
from sverchok.node_tree import SverchCustomTreeNode, StringsSocket
from sverchok.data_structure import updateNode, fullList, SvGetSocketAnyType, SvSetSocketAnyType
from sverchok.utils.sv_itertools import sv_zip_longest

color_nodular_color = (0.899, 0.8052, 0.0, 1.0)


def fprop_generator(**altprops):
    # min can be overwritten by passing in min=some_value into the altprops dict
    return FloatProperty(update=updateNode, precision=3, min=0.0, max=1.0, **altprops)


class SvColorsInNode(bpy.types.Node, SverchCustomTreeNode):
    ''' Generator for Color data , color combine'''
    bl_idname = 'SvColorsInNode'
    bl_label = 'Color in'
    bl_icon = 'OUTLINER_OB_EMPTY'

    r_ = fprop_generator(name='R', description='Red (0..1)')
    g_ = fprop_generator(name='G', description='Green (0..1)')
    b_ = fprop_generator(name='B', description='Blue (0..1)')
    a_ = fprop_generator(name='A', description='Alpha (0..1) - opacity')

    y_ = fprop_generator(name='Y', description='Luma')
    i_ = fprop_generator(name='I', min=-1.0, description='orange-blue range (-1..1) - chrominance')
    q_ = fprop_generator(name='Q', min=-1.0, description='purple-green (-1..1) - chrominance')

    h_ = fprop_generator(name='H', description='Hue')
    s_ = fprop_generator(name='S', description='Saturation (different for hsv and hsl)')
    l_ = fprop_generator(name='L', description='Lightness / Brightness')
    v_ = fprop_generator(name='V', description='Value / Brightness')


    def sv_init(self, context):
        self.width = 100
        inew = self.inputs.new
        inew('StringsSocket', "X").prop_name = 'r_'
        inew('StringsSocket', "Y").prop_name = 'g_'
        inew('StringsSocket', "Z").prop_name = 'b_'
        onew = self.outputs.new
        onew('VerticesSocket', "Vectors").nodular_color = color_nodular_color
        
    
    def process(self):
        if not self.outputs['Vectors'].is_linked:
            return
        inputs = self.inputs
        X_ = inputs['X'].sv_get()
        Y_ = inputs['Y'].sv_get()
        Z_= inputs['Z'].sv_get()
        series_vec = []
        max_obj = max(map(len,(X_,Y_,Z_)))
        fullList(X_, max_obj)
        fullList(Y_, max_obj)
        fullList(Z_, max_obj)
        for i in range(max_obj):
                
            max_v = max(map(len,(X_[i],Y_[i],Z_[i])))
            fullList(X_[i], max_v)
            fullList(Y_[i], max_v)
            fullList(Z_[i], max_v)
            series_vec.append(list(zip(X_[i], Y_[i], Z_[i])))
        
        self.outputs['Vectors'].sv_set(series_vec)
    
    
def register():
    bpy.utils.register_class(SvColorsInNode)


def unregister():
    bpy.utils.unregister_class(SvColorsInNode)

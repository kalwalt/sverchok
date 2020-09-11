# This file is part of project Sverchok. It's copyrighted by the contributors
# recorded in the version control history of the file, available from
# its original location https://github.com/nortikin/sverchok/commit/master
#
# SPDX-License-Identifier: GPL3
# License-Filename: LICENSE


import bpy

from sverchok.core.update_system import process_from_nodes


class SV_PT_3DPanel(bpy.types.Panel):
    """Panel to manipulate parameters in Sverchok layouts"""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'
    bl_label = "Sverchok"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        col = self.layout.column()
        if context.scene.SvShowIn3D_active:
            col.operator('wm.sv_obj_modal_update', text='Stop live update', icon='CANCEL').mode = 'end'
        else:
            col.operator('wm.sv_obj_modal_update', text='Start live update', icon='EDITMODE_HLT').mode = 'start'

        col.operator('node.sverchok_update_all', text='Update all trees')
        col.operator('node.sv_scan_properties', text='Scan for props')

        col_edit = col.column()
        col_edit.use_property_split = True
        col_edit.prop(context.scene.sv_ui_node_props, 'edit')
        col.template_list("SV_UL_NodeTreePropertyList", "", context.scene.sv_ui_node_props, 'props',
                          context.scene.sv_ui_node_props, "selected")


class SV_UL_NodeTreePropertyList(bpy.types.UIList):
    """Show in 3D tool panel"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        prop = item

        row = layout.row(align=True)

        if prop.type == 'TREE':
            prop.draw_tree(row, data)

            if data.edit:
                row = row.row(align=True)
                row.alignment = 'RIGHT'
                move_up = row.operator('node.sv_move_3d_panel_item', text='', icon='TRIA_UP')
                move_up.direction = 'UP'
                move_up.prop_index = index

                move_down = row.operator('node.sv_move_3d_panel_item', text='', icon='TRIA_DOWN')
                move_down.direction = 'DOWN'
                move_down.prop_index = index

                row.operator('node.popup_edit_label', text='', icon='GREASEPENCIL').tree_name = prop.tree.name

        elif prop.type == 'NODE':
            row_space = row.row()
            row_space.alignment = 'LEFT'
            row_space.ui_units_x = 1
            row_space.label(text='')

            prop.draw_node(row)

            if data.edit:
                move_up = row.operator('node.sv_move_3d_panel_item', text='', icon='TRIA_UP')
                move_up.direction = 'UP'
                move_up.prop_index = index

                move_down = row.operator('node.sv_move_3d_panel_item', text='', icon='TRIA_DOWN')
                move_down.direction = 'DOWN'
                move_down.prop_index = index

                edit_label = row.operator('node.popup_edit_label', text='', icon='GREASEPENCIL')
                edit_label.tree_name = prop.tree.name
                edit_label.node_name = prop.node_name

                row.operator('node.sv_remove_3dviewprop_item', text='', icon='CANCEL').prop_index = index

    def filter_items(self, context, data, prop_name):
        ui_list = data

        filter_trees = [prop.type == 'TREE' for prop in ui_list.props]
        filter_props = [prop.type == 'TREE' or prop.tree.sv_show_in_3d for prop in ui_list.props]

        filter_names = [self.filter_name.lower() in (prop.node_label or prop.node_name).lower() for
                        prop in ui_list.props]
        filter_names = [not f for f in filter_names] if self.use_filter_invert else filter_names

        mix_filters = [ft or (fp and fn) for ft, fp, fn in zip(filter_trees, filter_props, filter_names)]
        # next code is needed for hiding wrong tree types
        mix_with_inverse = [not f for f in mix_filters] if self.use_filter_invert else mix_filters
        mix_with_inverse = [self.bitflag_filter_item if f else 0 for f in mix_with_inverse]
        return mix_with_inverse, []


class Sv3dPropItem(bpy.types.PropertyGroup):
    """It represents property of a node item in 3D panel"""
    node_name: bpy.props.StringProperty()
    node_label: bpy.props.StringProperty()
    tree: bpy.props.PointerProperty(type=bpy.types.NodeTree)

    @property
    def type(self):
        """
        Items are divided into two categories: 'NODE' and 'TREE'
        'TREE' shows properties of a tree and 'NODE' properties of a node for 3D panel
         """
        return 'NODE' if self.node_name else 'TREE'

    def draw_node(self, layout):
        node = self.tree.nodes.get(self.node_name, None)
        if not node:
            # properties are not automatically removed from Sv3DProps when a node is deleted.
            row = layout.row()
            row.alert = True
            row.label(icon='ERROR', text=f'missing node: "{self.node_name}"')
        else:
            node.draw_buttons_3dpanel(layout.column())

    def draw_tree(self, row, ui_list):
        row.prop(self.tree, 'sv_show_in_3d', icon='DOWNARROW_HLT' if self.tree.sv_show_in_3d else 'RIGHTARROW',
                 emboss=False, text='')
        row = row.row()
        row.label(text=self.tree.name)

        # buttons
        if not ui_list.edit:
            row = row.row(align=True)
            row.alignment = 'RIGHT'
            row.ui_units_x = 7
            row.operator('node.sverchok_bake_all', text='B').node_tree_name = self.tree.name
            row.prop(self.tree, 'sv_show', icon=f"RESTRICT_VIEW_{'OFF' if self.tree.sv_show else 'ON'}", text=' ')
            row.prop(self.tree, 'sv_animate', icon='ANIM', text=' ')
            row.prop(self.tree, "sv_process", toggle=True, text="P")
            row.prop(self.tree, "sv_draft", toggle=True, text="D")
            row.prop(self.tree, 'use_fake_user', toggle=True, text='F')


class Sv3DNodeProperties(bpy.types.PropertyGroup):
    """It stores list of trees and node properties items in 3D panel"""
    props: bpy.props.CollectionProperty(type=Sv3dPropItem)
    edit: bpy.props.BoolProperty(name="Edit properties", description="Edit position of node properties in 3D panel",
                                 default=False, options=set())
    selected: bpy.props.IntProperty()  # selected item

    def move_prop(self, direction: str, from_index: int):
        """
        Only node type items can be moved, if above or below will be tree type item nothing happens
        :param from_index: index of item which should be moved
        :param direction: 'UP' or 'DOWN'
        """
        if direction == 'UP':
            above_item = None if from_index == 0 else self.props[from_index - 1]
            if above_item and above_item.node_name:
                self.props.move(from_index, from_index - 1)
        elif direction == 'DOWN':
            below_item = None if from_index == len(self.props) - 1 else self.props[from_index + 1]
            if below_item and below_item.node_name:
                self.props.move(from_index, from_index + 1)
        else:
            raise TypeError(f'Unsupported direction="{direction}", possible values="UP", "DOWN"')

    def move_tree(self, direction: str, from_index: str):
        """
        Only tree type items can be moved
        :param from_index: index of item which should be moved
        :param direction: 'UP' or 'DOWN'
        """
        tree_name = self.props[from_index].tree.name
        list_structure = self.generate_data_structure()  # {tree_name: {prop1: _, prop2:, _}, tree_name2: ...}
        trees = list(list_structure.keys())  # [tree_name, tree_name2, ...]
        current_index = trees.index(tree_name)
        if direction == 'UP':
            if current_index > 0:
                upper_index = current_index - 1
                trees[upper_index], trees[current_index] = trees[current_index], trees[upper_index]
        elif direction == 'DOWN':
            if current_index + 1 < len(trees):
                below_index = current_index + 1
                trees[current_index], trees[below_index] = trees[below_index], trees[current_index]
        else:
            raise TypeError(f'Unsupported direction="{direction}", possible values="UP", "DOWN"')
        self.recreate_list({tree_name: list_structure[tree_name] for tree_name in trees})

    def update_properties(self):
        """It will add or remove properties from list according state of existing layouts"""
        # 1. Recreate hierarchical data structure from list
        # 2. Update the data structure
        # 3. Recreate list from scratch
        props = self.generate_data_structure()

        for tree in bpy.data.node_groups:
            if tree.bl_idname != 'SverchCustomTreeType':
                continue

            nodes_to_show = set()
            for node in tree.nodes:
                if hasattr(node, 'draw_3dpanel'):
                    if node.draw_3dpanel:
                        nodes_to_show.add(node.name)

            showed_nodes = props.get(tree.name, {})
            for name_to_show in nodes_to_show:
                if name_to_show not in showed_nodes:
                    showed_nodes[name_to_show] = None

            for showed_name in showed_nodes.copy():
                if showed_name not in nodes_to_show:
                    del showed_nodes[showed_name]

            props[tree.name] = showed_nodes

        self.recreate_list(props)

    def generate_data_structure(self):
        """
        create more complex data structure:
        {tree_name: {prop1: 0, prop2: 1},
        tree_name2: {prop1: 0,}, ...}
        """
        trees = dict()
        for prop in self.props:
            if not prop.node_name:
                trees[prop.tree.name] = dict()
            else:
                trees[prop.tree.name][prop.node_name] = None
        return trees

    def recreate_list(self, props: dict):
        """
        It will recreate list from scratch with new given data
        :param props: it will expect the same data structure as output of generate_data_structure method
        """
        self.props.clear()
        for tree_name in props:
            tree = bpy.data.node_groups[tree_name]

            self.add(tree=tree)

            for node_name in props[tree_name]:
                node = tree.nodes.get(node_name)
                self.add(tree=tree, node_name=node.name, node_label=node.label)

    def update_name(self, tree_name, name, node_name=None):
        """It will update label of given node in the list or name of given tree"""
        if node_name:
            node_index = self.search_node(node_name, tree_name)
            if node_index is not None:
                self.props[node_index].node_label = name
        else:
            tree_index = self.search_tree(tree_name)
            if tree_index is not None:
                self.props[tree_index].tree.name = name

    def add(self, tree=None, node_name=None, node_label=None):
        prop = self.props.add()
        if tree:
            prop.tree = tree
        if node_name:
            prop.node_name = node_name
        if node_label:
            prop.node_label = node_label
        return prop

    def search_node(self, node_name, tree_name):
        """
        It returns index of given node in list or None
        Several trees can have nodes with similar names
        """
        for i, prop in enumerate(self.props):
            if prop.type == 'NODE':
                if prop.tree.name == tree_name and prop.node_name == node_name:
                    return i
        return None

    def search_tree(self, tree_name):
        """
        It returns index of given tree in list or None
        """
        for i, prop in enumerate(self.props):
            if prop.type == 'TREE':
                if prop.tree.name == tree_name:
                    return i
        return None


class SvLayoutScanProperties(bpy.types.Operator):
    """
    Scan layouts of Sverchok for properties
    Nodes with available "Show in 3D" properties on will be added to property list
    """
    bl_idname = "node.sv_scan_properties"
    bl_label = "scan for properties in Sverchok layouts"

    def execute(self, context):
        context.scene.sv_ui_node_props.update_properties()
        return {'FINISHED'}


class SvMove3DPanelItem(bpy.types.Operator):
    """Move property in 3D panel"""
    bl_idname = "node.sv_move_3d_panel_item"
    bl_label = "move property in 3D panel"

    direction: bpy.props.EnumProperty(items=[(i, i, '') for i in ['UP', 'DOWN']])
    prop_index: bpy.props.IntProperty(min=0)

    def execute(self, context):
        ui_list = context.scene.sv_ui_node_props
        if ui_list.props[self.prop_index].type == 'NODE':
            ui_list.move_prop(self.direction, self.prop_index)
        else:
            ui_list.move_tree(self.direction, self.prop_index)
        return {'FINISHED'}


class Sv3dPropRemoveItem(bpy.types.Operator):
    ''' remove item by node_name from tree.Sv3Dprops  '''

    bl_idname = "node.sv_remove_3dviewprop_item"
    bl_label = "remove item from Sv3Dprops - useful for removed nodes"

    prop_index: bpy.props.IntProperty()

    def execute(self, context):
        prop = context.scene.sv_ui_node_props.props[self.prop_index]
        node = prop.tree.nodes.get(prop.node_name)
        if node:
            # assume that node will delete its itself
            node.draw_3dpanel = False
        else:
            context.scene.sv_ui_node_props.props.remove(self.prop_index)
        return {'FINISHED'}


class SvPopupEditLabel(bpy.types.Operator):
    """Menu for editing node labels and tree names"""
    bl_idname = "node.popup_edit_label"
    bl_label = "Edit label"
    bl_options = {'INTERNAL'}

    tree_name: bpy.props.StringProperty()
    node_name: bpy.props.StringProperty()

    new_tree_name: bpy.props.StringProperty()  # for internal usage

    def execute(self, context):
        tree = bpy.data.node_groups.get(self.tree_name)
        node = tree.nodes.get(self.node_name)
        if node:
            context.scene.sv_ui_node_props.update_name(self.tree_name, node.label, self.node_name)
        else:
            context.scene.sv_ui_node_props.update_name(self.tree_name, self.new_tree_name)
        return {'FINISHED'}

    def invoke(self, context, event):
        tree = bpy.data.node_groups.get(self.tree_name)
        self.new_tree_name = tree.name

        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        tree = bpy.data.node_groups.get(self.tree_name)
        node = tree.nodes.get(self.node_name)
        if node:
            self.layout.label(text=f'Edit label of node="{node.label or node.name}"')
            self.layout.prop(node, 'label')
        else:
            self.layout.label(text=f'Edit tree name="{tree.name}"')
            self.layout.prop(self, 'new_tree_name')


class Sv3DViewObjInUpdater(bpy.types.Operator, object):
    """For automatic trees reevaluation upon changes in 3D space"""
    bl_idname = "wm.sv_obj_modal_update"
    bl_label = "start n stop obj updating"

    _timer = None
    mode: bpy.props.StringProperty(default='toggle')
    node_name: bpy.props.StringProperty(default='')
    node_group: bpy.props.StringProperty(default='')
    speed: bpy.props.FloatProperty(default=1 / 13)

    def modal(self, context, event):

        if not context.scene.SvShowIn3D_active:
            self.cancel(context)
            return {'FINISHED'}

        if not (event.type == 'TIMER'):
            return {'PASS_THROUGH'}

        objects_nodes_set = {'ObjectsNode', 'ObjectsNodeMK2', 'SvObjectsNodeMK3', 'SvExNurbsInNode', 'SvBezierInNode'}
        obj_nodes = []
        for ng in bpy.data.node_groups:
            if ng.bl_idname == 'SverchCustomTreeType':
                if ng.sv_process:
                    nodes = []
                    for n in ng.nodes:
                        if n.bl_idname in objects_nodes_set:
                            nodes.append(n)
                    if nodes:
                        obj_nodes.append(nodes)

        ''' reaches here only if event is TIMER and self.active '''
        for n in obj_nodes:
            # print('calling process on:', n.name, n.id_data)
            process_from_nodes(n)

        return {'PASS_THROUGH'}

    def start(self, context):
        context.scene.SvShowIn3D_active = True

        # rate can only be set in event_timer_add (I think...)
        # self.speed = 1 / context.node.updateRate

        wm = context.window_manager
        self._timer = wm.event_timer_add(self.speed, window=context.window)
        wm.modal_handler_add(self)
        self.report({'INFO'}, "Live Update mode enabled")

    def stop(self, context):
        context.scene.SvShowIn3D_active = False

    def toggle(self, context):
        if context.scene.SvShowIn3D_active:
            self.stop(context)
        else:
            self.start(context)

    def event_dispatcher(self, context, type_op):
        if type_op == 'start':
            self.start(context)
        elif type_op == 'end':
            self.stop(context)
        else:
            self.toggle(context)

    def execute(self, context):
        # n  = context.node
        # self.node_name = context.node.name
        # self.node_group = context.node.id_data.name

        self.event_dispatcher(context, self.mode)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        self.report({'INFO'}, "Live Update mode disabled")


classes = [
    SV_PT_3DPanel,
    SV_UL_NodeTreePropertyList,
    Sv3dPropItem,
    SvLayoutScanProperties,
    SvMove3DPanelItem,
    Sv3dPropRemoveItem,
    Sv3DNodeProperties,
    SvPopupEditLabel,
    Sv3DViewObjInUpdater
]


def register():
    [bpy.utils.register_class(cls) for cls in classes]

    bpy.types.Scene.sv_ui_node_props = bpy.props.PointerProperty(type=Sv3DNodeProperties)
    bpy.types.NodeTree.sv_show_in_3d = bpy.props.BoolProperty(
        name='show in panel',
        default=True,
        description='Show properties in 3d panel or not')


def unregister():
    [bpy.utils.unregister_class(cls) for cls in classes[::-1]]

    del bpy.types.Scene.sv_ui_node_props
    del bpy.types.NodeTree.sv_show_in_3d

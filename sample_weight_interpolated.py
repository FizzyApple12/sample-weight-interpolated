bl_info = {
    "name": "Sample Weight Interpolated",
    "author": "FizzyApple12",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "Weight Paint Mode",
    "description": "Sample weight values interpolated across faces",
    "category": "Paint",
}


import math

import bmesh
import bpy
import bpy_extras.view3d_utils
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc


class WeightSampleInterpolatedOperator(bpy.types.Operator):
    bl_idname = "paint.weight_sample_interpolated"
    bl_label = "Sample Weight Interpolated"
    bl_options = {"REGISTER", "UNDO", "DEPENDS_ON_CURSOR"}
    bl_cursor_pending = "EYEDROPPER"

    from_tool: bpy.props.BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})

    def modal(self, context, event):
        context.area.header_text_set("Input pending Sample Weight Interpolated")

        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            self.sample_weight(context, event)

            context.area.header_text_set(None)

            return {"FINISHED"}

        elif event.type in {"RIGHTMOUSE", "ESC"} and event.value == "PRESS":
            context.area.header_text_set(None)

            return {"CANCELLED"}

        return {"RUNNING_MODAL"}

    def invoke(self, context, event):
        if context.mode != "PAINT_WEIGHT":
            return {"CANCELLED"}

        if context.object.type != "MESH":
            return {"CANCELLED"}

        if self.from_tool:
            self.sample_weight(context, event)

            self.from_tool = False

            return {"FINISHED"}
        else:
            context.window_manager.modal_handler_add(self)

            return {"RUNNING_MODAL"}

    def sample_weight(self, context, event):
        if context.object.vertex_groups.active is None:
            return

        active_vertex_group_index = context.object.vertex_groups.active.index

        mouse_coordinates = (event.mouse_region_x, event.mouse_region_y)

        view_vector = bpy_extras.view3d_utils.region_2d_to_vector_3d(
            context.region, context.region_data, mouse_coordinates
        )
        ray_origin = bpy_extras.view3d_utils.region_2d_to_origin_3d(
            context.region, context.region_data, mouse_coordinates
        )

        inverse_object_matrix = context.object.matrix_world.inverted()
        ray_origin_object = inverse_object_matrix @ ray_origin
        ray_direction_object = inverse_object_matrix.to_3x3() @ view_vector

        active_object_bmesh = bmesh.new()
        active_object_bmesh.from_mesh(context.object.data)
        active_object_bmesh.faces.ensure_lookup_table()
        active_object_bmesh.faces.index_update()

        active_object_bvhtree = BVHTree.FromBMesh(active_object_bmesh)

        raycast_position, _, raycast_index, _ = active_object_bvhtree.ray_cast(
            ray_origin_object, ray_direction_object
        )

        if raycast_position is None:
            active_object_bmesh.free()

            return

        target_face = active_object_bmesh.faces[raycast_index]
        target_face.verts.index_update()

        target_face_barycentric_coordinates = poly_3d_calc(
            [context.object.matrix_world @ vertex.co for vertex in target_face.verts],
            raycast_position.xyz,
        )

        active_deform_layer = active_object_bmesh.verts.layers.deform.active

        if active_deform_layer is None:
            active_object_bmesh.free()

            return

        final_weight = 0.0

        for vertex in target_face.verts:
            if active_vertex_group_index in vertex[active_deform_layer]:
                final_weight += (
                    target_face_barycentric_coordinates[vertex.index]
                    * vertex[active_deform_layer][active_vertex_group_index]
                )

        context.tool_settings.unified_paint_settings.weight = final_weight

        active_object_bmesh.free()


class WeightSampleInterpolatedTool(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "PAINT_WEIGHT"
    bl_idname = "paint.sample_weight_interpolated"
    bl_label = "Sample Weight Interpolated"
    bl_description = "Use the mouse to sample a weight on a face in the 3D view."
    bl_icon = "ops.paint.weight_sample"
    bl_keymap = (
        (
            "paint.weight_sample_interpolated",
            {"type": "LEFTMOUSE", "value": "PRESS"},
            {"properties": [("from_tool", True)]},
        ),
    )
    bl_cursor = "EYEDROPPER"

    def draw_settings(context, layout, tool):
        layout.label(
            text=f"Weight: {context.tool_settings.unified_paint_settings.weight:1.3f}"
        )


def menu_func(self, context):
    self.layout.separator()
    self.layout.operator(
        WeightSampleInterpolatedOperator.bl_idname, text="Sample Weight Interpolated"
    )


def register():
    bpy.utils.register_class(WeightSampleInterpolatedOperator)
    bpy.utils.register_tool(
        WeightSampleInterpolatedTool,
        after={"builtin.sample_weight"},
        separator=False,
        group=False,
    )

    bpy.types.VIEW3D_MT_paint_weight.append(menu_func)

    addon_keyconfigs = bpy.context.window_manager.keyconfigs.addon

    if addon_keyconfigs:
        keymap = addon_keyconfigs.keymaps.new(name="Weight Paint", space_type="EMPTY")

        keymap.keymap_items.new(
            WeightSampleInterpolatedOperator.bl_idname,
            type="X",
            value="PRESS",
            ctrl=False,
            shift=True,
            alt=True,
        )


def unregister():
    bpy.types.VIEW3D_MT_paint_weight.remove(menu_func)

    bpy.utils.unregister_tool(WeightSampleInterpolatedTool)
    bpy.utils.unregister_class(WeightSampleInterpolatedOperator)

    addon_keyconfigs = bpy.context.window_manager.keyconfigs.addon

    if addon_keyconfigs:
        keymap = addon_keyconfigs.keymaps.get("Weight Paint")

        if keymap:
            for keymap_item in keymap.keymap_items:
                if keymap_item.idname == WeightSampleInterpolatedOperator.bl_idname:
                    keymap.keymap_items.remove(keymap_item)


if __name__ == "__main__":
    register()
